"""Air-index ingest worker — the every-15-min job from doc 05 §2.

run_index_once():
  1. airindex.build_field()  (live upstream pulls; `inputs` injectable for
     tests/replay so nothing touches the network)
  2. snapshot -> s3://{ALIVE_AIR_BUCKET}/field/YYYY/MM/DD/HHmm.json.gz when
     the bucket env var is set AND boto3 + credentials are usable;
     otherwise -> server/data/field/snapshots/YYYY/MM/DD/HHmm.json.gz
  3. CloudWatch metrics (StationsUsed, FieldAgeSeconds, MeanSigma in
     namespace "ALive-108") — emitted only when boto3 AND AWS credentials
     resolve; skipped (reported) otherwise, never fatal.

handler(event, context) is the EventBridge/Lambda entry point — same code
path, JSON status response.

run_forever(interval_s=900) is the long-lived container form (doc 05 §1
"worker: air-index builder (every 15 min)"): per-iteration failures are
caught + logged, consecutive failures back off exponentially, and the
result history is a bounded deque — the loop holds no unbounded state.

Snapshot rotation: local snapshots are pruned to the newest
SNAPSHOT_KEEP (default 96 = 24 h of the 15-min cadence in doc 05 §2;
override with ALIVE_SNAPSHOT_KEEP). The newest file — the one a live
field would serve from (rollup.latest_snapshot, health field_age) — and
any explicitly protected path are never deleted.
"""
import collections
import glob
import json
import logging
import os
import random
import sys
import time
from datetime import datetime, timezone

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import airindex  # noqa: E402

log = logging.getLogger("alive.ingest")

DATA_DIR = os.path.join(_HERE, "data")
SNAPSHOT_DIR = os.path.join(DATA_DIR, "field", "snapshots")
METRIC_NS = "ALive-108"

# Snapshot retention: 96 files = 24 h at the 15-min rebuild cadence
# (doc 05 §2). Env override for ops; 0 = keep nothing but the live one.
def _keep_env(default=96) -> int:
    try:
        return max(0, int(os.environ.get("ALIVE_SNAPSHOT_KEEP", default)))
    except (TypeError, ValueError):
        return default


SNAPSHOT_KEEP = _keep_env()
# Extra paths rotation must never delete (comma-sep, e.g. the snapshot a
# long-lived process is currently serving).
_PROTECT_ENV = os.environ.get("ALIVE_SNAPSHOT_PROTECT", "")

INDEX_PERIOD_S = 900            # doc 05 §2: rebuild every 15 min
FAIL_BACKOFF_BASE_S = 5.0       # worker loop backoff: base * 2**(fails-1)
FAIL_BACKOFF_CAP_S = 300.0      #   ... capped well under the 15-min cadence
FAIL_JITTER_S = 1.0
WORKER_HISTORY = 64             # bounded ring of recent iteration results


def _boto3():
    """boto3 if installed (optional dep — not in requirements yet)."""
    try:
        import boto3
        return boto3
    except ImportError:
        return None


def _aws_ready() -> tuple:
    """-> (boto3_module_or_None, reason). Credentials must actually resolve
    (env vars, ~/.aws, or task role) — a boto3 install alone is not enough."""
    b3 = _boto3()
    if b3 is None:
        return None, "no boto3"
    try:
        if b3.Session().get_credentials() is None:
            return None, "no credentials"
    except Exception as e:  # noqa: BLE001
        return None, f"credential check failed: {type(e).__name__}"
    return b3, "ok"


def _atomic_write(path: str, data: bytes) -> None:
    """Write `data` to `path` via a same-dir tmp + os.replace — readers
    (airfield.load_snapshot, admin_agg._latest_json) never see a torn
    file, so a crashed writer can't leave a partial snapshot that
    decodes-as-garbage or forces serving an older field. The tmp file
    is removed when the write itself fails."""
    tmp = path + ".tmp"
    try:
        with open(tmp, "wb") as f:
            f.write(data)
        os.replace(tmp, path)
    except Exception:
        try:
            os.remove(tmp)
        except OSError:
            pass
        raise


def store_blob(s3_key: str, data: bytes, local_path: str,
               mirror_local: bool = False) -> tuple:
    """Write `data` to s3://{ALIVE_AIR_BUCKET}/{s3_key} when the bucket is
    configured and AWS is usable, else to `local_path`. Always writes
    somewhere — a failed S3 put degrades to local, never loses a snapshot.

    `mirror_local` also writes `local_path` on a successful S3 put —
    rollup outputs (daily/validation JSON) are read back by the admin
    API off THIS task's disk, which an S3-only write never reaches.
    15-min snapshots stay S3-only (~17 MB/day of ephemeral disk saved).

    -> (uri, backend, note)  backend in {"s3", "local"}.
    """
    bucket = os.environ.get("ALIVE_AIR_BUCKET")
    if bucket:
        b3, why = _aws_ready()
        if b3 is not None:
            try:
                kw = {"Bucket": bucket, "Key": s3_key, "Body": data,
                      "ContentType": "application/json"}
                if s3_key.endswith(".gz"):
                    kw["ContentEncoding"] = "gzip"
                b3.client("s3").put_object(**kw)
                if mirror_local:
                    try:
                        os.makedirs(os.path.dirname(local_path),
                                    exist_ok=True)
                        _atomic_write(local_path, data)
                    except OSError:
                        pass  # S3 copy landed; the mirror is best-effort
                return f"s3://{bucket}/{s3_key}", "s3", None
            except Exception as e:  # noqa: BLE001 - fall through to local
                note = f"s3 put failed ({type(e).__name__}: {e}) — wrote local"
        else:
            note = f"bucket set but {why} — wrote local"
    else:
        note = None
    os.makedirs(os.path.dirname(local_path), exist_ok=True)
    _atomic_write(local_path, data)
    return local_path, "local", note


# Rollup outputs the scheduled jobs publish under these S3 prefixes →
# where the admin mirror expects them on the API task's disk. The job
# tasks are one-shot Fargate runs — their disk dies with them, so S3 is
# the shared shelf and this mirror is how the API side ever sees them.
_ROLLUP_MAP = (
    ("daily/", "field/daily"),
    ("validation/", "field/validation"),
)


def sync_rollup_outputs(data_root: str = None) -> dict:
    """Pull scheduled-job outputs from s3://{ALIVE_AIR_BUCKET}/ onto the
    local mirror admin_agg reads.

    daily/*.json          -> data/field/daily/
    validation/*.{json,md}-> data/field/validation/
    validation/field_validation.md -> data/field_validation.md (the
        archive-replay report lives at data root, not under field/)

    No AWS / no bucket -> reported skipped, never raised."""
    root = data_root or DATA_DIR
    out = {"ok": False, "downloaded": [], "skipped": None}
    bucket = os.environ.get("ALIVE_AIR_BUCKET")
    if not bucket:
        out["skipped"] = "no ALIVE_AIR_BUCKET"
        return out
    b3, why = _aws_ready()
    if b3 is None:
        out["skipped"] = why
        return out
    try:
        s3 = b3.client("s3")
        for prefix, sub in _ROLLUP_MAP:
            dest = os.path.join(root, sub)
            os.makedirs(dest, exist_ok=True)
            for page in s3.get_paginator("list_objects_v2").paginate(
                    Bucket=bucket, Prefix=prefix):
                for obj in page.get("Contents") or []:
                    key = obj["Key"]
                    name = key.rsplit("/", 1)[-1]
                    if not name:
                        continue
                    lp = (os.path.join(root, "field_validation.md")
                          if name == "field_validation.md"
                          else os.path.join(dest, name))
                    body = s3.get_object(Bucket=bucket,
                                         Key=key)["Body"].read()
                    if os.path.exists(lp) \
                            and os.path.getsize(lp) == len(body):
                        continue
                    _atomic_write(lp, body)
                    out["downloaded"].append(key)
        out["ok"] = True
        return out
    except Exception as e:  # noqa: BLE001
        out["skipped"] = f"{type(e).__name__}: {e}"
        return out


# ------------------------------------------------------------- geo mirror

# Geo build artifacts the CodeBuild tiles lane publishes to the air bucket
# (scripts/geo/buildspec-tiles.yml) — too big for git or the image, so S3
# is the shelf and this pull is how the API task ever sees them.
_GEO_KEYS = ("geo/delhi.pmtiles",)


def _geo_dest(name: str) -> str:
    """Local path a geo artifact mirrors to. delhi.pmtiles lands wherever
    tiles.py serves it from (ALIVE_PMTILES or the repo data/geo default);
    anything else lands beside it."""
    try:
        import tiles as _tiles
        base = _tiles._path()
    except Exception:  # noqa: BLE001
        base = os.path.join(os.path.dirname(_HERE), "data", "geo",
                            "delhi.pmtiles")
    return base if name == "delhi.pmtiles" else os.path.join(
        os.path.dirname(base), name)


def sync_geo_artifacts() -> dict:
    """Pull s3://{ALIVE_AIR_BUCKET}/geo/* (Delhi vector tiles) onto local
    disk. Downloads to <name>.tmp then os.replace — a served path only
    ever holds a whole archive, and tiles.py re-opens on mtime/size
    change, so a rebuilt artifact hot-swaps without a redeploy.

    No AWS / no bucket / artifact not yet published -> reported skipped,
    never raised; /tiles keeps its honest 503 while the file is absent."""
    out = {"ok": False, "downloaded": [], "skipped": None}
    bucket = os.environ.get("ALIVE_AIR_BUCKET")
    if not bucket:
        out["skipped"] = "no ALIVE_AIR_BUCKET"
        return out
    b3, why = _aws_ready()
    if b3 is None:
        out["skipped"] = why
        return out
    try:
        s3 = b3.client("s3")
        for key in _GEO_KEYS:
            name = key.rsplit("/", 1)[-1]
            lp = _geo_dest(name)
            try:
                head = s3.head_object(Bucket=bucket, Key=key)
            except Exception:  # noqa: BLE001
                continue  # not published yet — nothing to pull
            if os.path.exists(lp) \
                    and os.path.getsize(lp) == head["ContentLength"]:
                continue
            os.makedirs(os.path.dirname(lp), exist_ok=True)
            tmp = lp + ".tmp"
            s3.download_file(bucket, key, tmp)
            os.replace(tmp, lp)
            out["downloaded"].append(key)
        out["ok"] = True
        return out
    except Exception as e:  # noqa: BLE001
        out["skipped"] = f"{type(e).__name__}: {e}"
        return out


def _emit_metrics(field: dict) -> dict:
    """CloudWatch for the doc-05 dashboard: stations used, field age
    (oldest input age), mean kriging sigma. Only when AWS is usable —
    reported, never raised."""
    b3, why = _aws_ready()
    if b3 is None:
        return {"emitted": False, "skipped": why}
    ages = [p["age_s"] for p in field["provenance"].values()
            if p.get("age_s") is not None]
    datum = [
        {"MetricName": "StationsUsed", "Value": field["qc"]["stations_used"],
         "Unit": "Count"},
        {"MetricName": "FieldAgeSeconds", "Value": max(ages) if ages else 0,
         "Unit": "Seconds"},
    ]
    if field["stats"].get("mean_sigma") is not None:
        datum.append({"MetricName": "MeanSigma",
                      "Value": field["stats"]["mean_sigma"], "Unit": "None"})
    try:
        b3.client("cloudwatch").put_metric_data(
            Namespace=METRIC_NS, MetricData=datum)
        return {"emitted": True, "metrics": [d["MetricName"] for d in datum],
                "namespace": METRIC_NS}
    except Exception as e:  # noqa: BLE001
        return {"emitted": False, "skipped": f"{type(e).__name__}: {e}"}


def rotate_snapshots(snapshot_root: str = None, *, keep: int = None,
                     protect=()) -> dict:
    """Prune local snapshots to the newest `keep` (default SNAPSHOT_KEEP).

    Paths are YYYY/MM/DD/HHmm.json.gz so lexicographic order == age order.
    Never deletes:
      - the lexicographically-newest file in the tree — that is the
        snapshot a live field would serve from (rollup.latest_snapshot,
        health field_age both read "newest")
      - anything in `protect` or the ALIVE_SNAPSHOT_PROTECT env list
    Empty day/month/year dirs left behind are pruned. -> counts dict."""
    root = snapshot_root or SNAPSHOT_DIR
    keep = SNAPSHOT_KEEP if keep is None else max(0, int(keep))
    files = sorted(glob.glob(os.path.join(root, "**", "*.json.gz"),
                             recursive=True))
    protected = {os.path.abspath(p) for p in protect if p}
    for p in _PROTECT_ENV.split(","):
        p = p.strip()
        if p:
            protected.add(os.path.abspath(p))
    if files:
        protected.add(os.path.abspath(files[-1]))  # the live one
    stale = files[:max(0, len(files) - keep)]
    deleted, errors = 0, []
    for p in stale:
        if os.path.abspath(p) in protected:
            continue
        try:
            os.remove(p)
            deleted += 1
        except OSError as e:
            if len(errors) < 10:  # bound the report, not the sweep
                errors.append(f"{p}: {e.strerror or e}")
    # prune dirs emptied by the sweep (deepest first; ignore non-empty)
    for dirpath, _dirs, _files in os.walk(root, topdown=False):
        if os.path.abspath(dirpath) == os.path.abspath(root):
            continue
        try:
            os.rmdir(dirpath)
        except OSError:
            pass
    return {"keep": keep, "found": len(files), "deleted": deleted,
            "protected": len(protected), "errors": errors,
            "root": root}


def run_index_once(now=None, *, inputs=None, snapshot_root: str = None,
                   keep: int = None) -> dict:
    """One 15-min index build. -> summary dict (also the handler body)."""
    t0 = time.time()
    field = airindex.build_field(now=now, inputs=inputs)
    t_build = time.time()
    blob = airindex.serialize(field)
    t_ser = time.time()
    ts = datetime.fromtimestamp(field["built_epoch"], tz=timezone.utc)
    rel = os.path.join(f"{ts:%Y/%m/%d}", f"{ts:%H%M}.json.gz")
    local_path = os.path.join(snapshot_root or SNAPSHOT_DIR, rel)
    uri, backend, note = store_blob(f"field/{ts:%Y/%m/%d/%H%M}.json.gz",
                                    blob, local_path)
    t_store = time.time()
    try:
        gc = rotate_snapshots(snapshot_root, keep=keep,
                              protect=[local_path])
    except Exception as e:  # noqa: BLE001 - GC must never sink a build
        gc = {"skipped": f"{type(e).__name__}: {e}"}
    metrics = _emit_metrics(field)
    t_done = time.time()
    # One line per iteration for the cold-build lane (docs/lanes/
    # ingest-coldbuild): build internals come from airindex's 'ingest
    # build' line; this adds serialize/store/gc/metrics so the gap
    # between loop start and S3 landing is fully attributed. warning =
    # the level that reaches /ecs/alive108 today (INFO is dropped).
    log.warning(
        "ingest run: build=%dms serialize=%dms store=%dms[%s] "
        "gc_metrics=%dms total=%dms -> %s",
        round((t_build - t0) * 1000), round((t_ser - t_build) * 1000),
        round((t_store - t_ser) * 1000), backend,
        round((t_done - t_store) * 1000), round((t_done - t0) * 1000),
        uri)
    if note:
        # an S3 put that fell back to local disk used to be invisible
        # except inside the return dict — a silent hole in the durable
        # record. Name it in the log.
        log.warning("ingest store note: %s", note)
    return {
        "ok": True,
        "snapshot": uri,
        "backend": backend,
        "note": note,
        "built_at": field["built_at"],
        "build_ms": field["build"]["duration_ms"],
        "grid_system": field["grid"]["system"],
        "cells": field["grid"]["n_cells"],
        "stations_used": field["qc"]["stations_used"],
        "qc_dropped": {k: len(v) for k, v in field["qc"]["dropped"].items()},
        "qc_dropped_total": field["qc"]["dropped_total"],
        "kriging": field["qc"]["kriging"],
        "mean_sigma": field["stats"]["mean_sigma"],
        "sources_used": field["build"]["sources_used"],
        "sources_degraded": field["build"]["sources_degraded"],
        "provenance_status": {k: v["status"]
                              for k, v in field["provenance"].items()},
        "gc": gc,
        "metrics": metrics,
    }


def run_forever(interval_s: int = INDEX_PERIOD_S, *, run=None, sleep=None,
                max_iters: int = None, on_result=None, history=None,
                snapshot_root: str = None) -> list:
    """Long-lived worker loop for the doc-05 §1 "every 15 min" container.

    Per iteration: run() (default run_index_once) is fully guarded —
    an exception is logged, recorded, and backed off exponentially
    (FAIL_BACKOFF_BASE_S * 2**consecutive, capped at FAIL_BACKOFF_CAP_S,
    + jitter) instead of killing the loop. A success resets the backoff.

    Memory: `history` is a bounded deque(maxlen=WORKER_HISTORY); nothing
    else accumulates across iterations (each build makes a fresh Kalman
    smoother + KrigeField inside airindex), so the loop holds no
    unbounded state. `max_iters` bounds the loop for tests; None = run
    until killed, as the scheduler intends."""
    if run is None:
        def run():
            return run_index_once(snapshot_root=snapshot_root) \
                if snapshot_root else run_index_once()
    sleep = sleep if sleep is not None else time.sleep
    hist = history if history is not None else \
        collections.deque(maxlen=WORKER_HISTORY)
    fails, it = 0, 0
    while max_iters is None or it < max_iters:
        it += 1
        try:
            res = run()
        except Exception as e:  # noqa: BLE001 - log, back off, keep going
            fails += 1
            wait = min(FAIL_BACKOFF_CAP_S,
                       FAIL_BACKOFF_BASE_S * (2 ** (fails - 1))) \
                + random.uniform(0.0, FAIL_JITTER_S)
            log.exception("ingest iteration %d failed (%d consecutive); "
                          "backing off %.1fs", it, fails, wait)
            entry = {"iteration": it, "ok": False,
                     "error": f"{type(e).__name__}: {e}",
                     "consecutive_failures": fails,
                     "backoff_s": round(wait, 2)}
            hist.append(entry)
            try:
                if on_result:
                    on_result(entry)
            except Exception:  # noqa: BLE001 - a bad callback is not fatal
                log.exception("on_result callback failed")
            sleep(wait)
            continue
        fails = 0
        entry = {"iteration": it, "ok": True,
                 "built_at": res.get("built_at") if isinstance(res, dict)
                 else None,
                 "cells": res.get("cells") if isinstance(res, dict) else None,
                 "snapshot": res.get("snapshot") if isinstance(res, dict)
                 else None}
        hist.append(entry)
        try:
            if on_result:
                on_result(entry)
        except Exception:  # noqa: BLE001
            log.exception("on_result callback failed")
        if max_iters is None or it < max_iters:
            sleep(interval_s)
    return list(hist)


def handler(event, context):
    """EventBridge Scheduler / Lambda entry point."""
    try:
        return {"statusCode": 200,
                "body": json.dumps(run_index_once(), default=str)}
    except Exception as e:  # noqa: BLE001 - surface, don't hang the schedule
        return {"statusCode": 500,
                "body": json.dumps({"ok": False,
                                    "error": f"{type(e).__name__}: {e}"})}


if __name__ == "__main__":
    print(json.dumps(run_index_once(), indent=1, default=str))
