"""Field-snapshot lifecycle: local mirror -> S3 sync + retention (doc 05 §4).

The ingest worker writes every 15-min snapshot to
s3://$ALIVE_AIR_BUCKET/field/YYYY/MM/DD/HHmm.json.gz when AWS is usable and
to the local mirror server/data/field/snapshots/ otherwise (and store_blob
degrades S3 failures back to local). This module converges the two:

  sync — upload every local snapshot the bucket doesn't already have
         (covers local-fallback writes and any drift)
  gc   — prune local files older than ALIVE_SNAPSHOT_KEEP_DAYS
         (default 7 — the admin dashboard's "last 7 days" slider window,
         doc 07 §2) but ONLY once they're confirmed archived in S3.
         Retention beyond that is the bucket's job: provision.sh
         --glacier adds the field/ -> GLACIER@90d lifecycle.

Safety contract:
  * dry-run by default — run_gc(apply=False) / CLI without --apply
    reports the full plan and changes nothing
  * no ALIVE_AIR_BUCKET (or boto3/credentials missing) -> nothing is
    uploaded AND nothing is deleted: a local-only copy is the only copy
  * a file whose upload failed is never deleted in the same run

Works with any injected `s3_client` (fake/stub/moto) for offline tests.

CLI:
    python3 snapshot_gc.py                 # dry-run plan
    python3 snapshot_gc.py --apply         # sync + prune
    python3 snapshot_gc.py --keep-days 30  # override retention
"""
import argparse
import glob
import json
import os
import sys
import time

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from ingest_worker import SNAPSHOT_DIR, _aws_ready  # noqa: E402

DEFAULT_KEEP_DAYS = 7.0   # admin "last 7 days" window (docs/plan/07 §2)
S3_PREFIX = "field/"


# ----------------------------------------------------------------- S3

def _s3_keys(s3, bucket: str, prefix: str = S3_PREFIX) -> set:
    keys, token = set(), None
    while True:
        kw = {"Bucket": bucket, "Prefix": prefix}
        if token:
            kw["ContinuationToken"] = token
        r = s3.list_objects_v2(**kw)
        for o in r.get("Contents", []):
            keys.add(o["Key"])
        if not r.get("IsTruncated"):
            return keys
        token = r.get("NextContinuationToken")


def _resolve_s3(bucket, s3_client):
    """-> (s3_client_or_None, note). Never raises."""
    if not bucket:
        return None, "ALIVE_AIR_BUCKET unset — snapshots stay local"
    if s3_client is not None:
        return s3_client, None
    b3, why = _aws_ready()
    if b3 is None:
        return None, f"bucket set but {why} — nothing synced or deleted"
    try:
        return b3.client("s3"), None
    except Exception as e:  # noqa: BLE001
        return None, f"bucket set but s3 client failed: {type(e).__name__}"


# --------------------------------------------------------------- files

def _local_files(root: str):
    """[(path, s3_key, mtime, size)] for every snapshot under root."""
    out = []
    pat = os.path.join(root, "*", "*", "*", "*.json.gz")
    for p in sorted(glob.glob(pat)):
        rel = os.path.relpath(p, root).replace(os.sep, "/")
        st = os.stat(p)
        out.append({"path": p, "key": S3_PREFIX + rel,
                    "mtime": st.st_mtime, "size": st.st_size})
    return out


# ---------------------------------------------------------------- plan

def plan(root: str = None, bucket: str = None, keep_days: float = None,
         now: float = None, s3_client=None) -> dict:
    """What a run would do — pure, changes nothing."""
    root = root or os.environ.get("ALIVE_SNAPSHOT_DIR") or SNAPSHOT_DIR
    bucket = bucket if bucket is not None \
        else os.environ.get("ALIVE_AIR_BUCKET")
    if keep_days is None:
        keep_days = float(
            os.environ.get("ALIVE_SNAPSHOT_KEEP_DAYS", DEFAULT_KEEP_DAYS))
    now = now or time.time()

    s3, note = _resolve_s3(bucket, s3_client)
    files = _local_files(root)
    have = _s3_keys(s3, bucket) if s3 is not None else None

    to_upload, old, protected = [], [], []
    cutoff = now - keep_days * 86400
    for f in files:
        archived = have is not None and f["key"] in have
        pending = have is not None and not archived
        if pending:
            to_upload.append(f)
        if f["mtime"] < cutoff:
            f2 = dict(f, age_days=round((now - f["mtime"]) / 86400, 2))
            if archived or pending:
                # already in S3, or this run will put it there
                old.append(dict(f2, archived=archived))
            else:
                protected.append(dict(f2, reason="not in S3 — only copy"))

    return {
        "root": root, "bucket": bucket, "keep_days": keep_days,
        "files": len(files),
        "to_upload": to_upload if have is not None else [],
        "already_in_s3": (len(files) - len(to_upload))
        if have is not None else None,
        "to_delete": old if have is not None else [],
        "protected": protected,
        "note": note,
        "dry_run": True,
    }


def run_gc(root: str = None, bucket: str = None, keep_days: float = None,
           apply: bool = False, s3_client=None, now: float = None) -> dict:
    """Sync local->S3 then prune archived locals. Dry-run unless apply."""
    root = root or os.environ.get("ALIVE_SNAPSHOT_DIR") or SNAPSHOT_DIR
    bucket = bucket if bucket is not None \
        else os.environ.get("ALIVE_AIR_BUCKET")
    p = plan(root=root, bucket=bucket, keep_days=keep_days,
             now=now, s3_client=s3_client)
    p["apply"] = apply
    p["uploaded"], p["deleted"], p["errors"] = [], [], []
    if not apply:
        return p

    s3, _ = _resolve_s3(bucket, s3_client)
    archived = set()
    if s3 is not None:
        try:
            archived = _s3_keys(s3, bucket)
        except Exception as e:  # noqa: BLE001
            p["errors"].append(f"list failed: {type(e).__name__}: {e}")
            s3 = None
    for f in p["to_upload"]:
        try:
            with open(f["path"], "rb") as fh:
                body = fh.read()
            s3.put_object(Bucket=bucket, Key=f["key"], Body=body,
                          ContentType="application/json",
                          ContentEncoding="gzip")
            archived.add(f["key"])
            p["uploaded"].append(f["key"])
        except Exception as e:  # noqa: BLE001 - keep the local file
            p["errors"].append(
                f"upload {f['key']}: {type(e).__name__}: {e}")
    for f in p["to_delete"]:
        if f["key"] not in archived:
            continue  # upload failed this run — keep the only copy
        try:
            os.remove(f["path"])
            p["deleted"].append(f["path"])
        except OSError as e:
            p["errors"].append(f"delete {f['path']}: {e}")
    p["dry_run"] = False
    return p


def handler(event=None, context=None) -> dict:
    """Optional schedule entry (e.g. nightly GC) — apply only when the
    event/env explicitly asks, so a bare invoke can never prune."""
    event = event or {}
    apply = bool(event.get("apply")
                 or os.environ.get("ALIVE_GC_APPLY") == "1")
    return run_gc(root=event.get("root") or None,
                  keep_days=(event.get("keep_days")
                             if event.get("keep_days") is not None else None),
                  apply=apply)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--apply", action="store_true",
                    help="actually upload + delete (default: dry-run)")
    ap.add_argument("--keep-days", type=float, default=None)
    ap.add_argument("--root", default=None)
    ap.add_argument("--bucket", default=None)
    a = ap.parse_args()
    print(json.dumps(run_gc(root=a.root, bucket=a.bucket,
                            keep_days=a.keep_days, apply=a.apply),
                     indent=1, default=str))
