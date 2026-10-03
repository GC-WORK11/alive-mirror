"""Ops health probe for /health — no boto3, no AWS calls, import-safe.

`collect_health()` returns a plain dict main.py can jsonify directly:

    {
      "ok": True,
      "ts": 1696...,           # unix seconds
      "build_sha": "abc123",   # $BUILD_SHA, else `git rev-parse --short HEAD`
      "version": "0.2.0",      # $APP_VERSION / pyproject, else "dev"
      "uptime_s": 123.4,       # seconds since this module was imported
      "field_age_s": 812.0,    # now - built_epoch of newest snapshot
      "field": {               # null-valued keys when no snapshot exists
        "snapshot": "2026/10/03/0202.json.gz",
        "built_at": "2026-10-03T02:02:20+00:00",
        "stored_at": "...mtime iso...", "cells": 12123
      },
      "disk": {"path": "...", "free_bytes": ..., "total_bytes": ...,
               "free_pct": 41.2, "low": false},
      "sources": {             # up=None means "not probed", never a guess
        "model":    {"up": null, "detail": "...", "status": "ok",
                     "fetched_at": "...iso...", "age_s": 830},
        "met":      {...},
        "stations": {"up": null, "detail": "...", "status":
                     "unavailable: no key", "fetched_at": null, "age_s": null},
        "fires":    {...},
        "location": {"up": null, "detail": "..."}
      }
    }

Field age — the number ops actually alarms on (doc 05 §6: >45 min) — is
resolved from the on-disk snapshot tree `data/field/snapshots/**` written
by ingest_worker.run_index_once (same convention rollup.latest_snapshot
and /v2/city read). A snapshot's path `YYYY/MM/DD/HHmm.json.gz` IS its
generated_at (the writer derives it from built_epoch at minute precision,
UTC); when the payload is readable we prefer its exact `built_epoch`.
Files not matching the convention are skipped — a stray `.json.gz` with a
newer mtime must not fake freshness. Null only when no valid snapshot
exists at all.

Per-source `age_s` comes from the newest snapshot's `provenance` block:
now − fetched_at, recomputed at probe time so staleness keeps growing —
an "ok" build three hours ago is honestly reported as three hours stale.

Probing policy: we never make network calls here — a /health handler must
answer even when every upstream is down (that is exactly when it is hit
hardest). `up` is therefore tri-state:
  * True/False — explicit override via env SOURCE_<NAME>_UP=true|false
    (set by the deploy pipeline or a future probe lane)
  * None — credentials/config presence only; detail says what was found.

// INTEGRATOR: server/main.py `/health` (line ~96) still answers from
// INTEGRATOR: FIELD.status() — the legacy in-memory AirField, whose
// INTEGRATOR: _fetched_at is None until a live pull, so field_age_s
// INTEGRATOR: returns null despite snapshots on disk. One-line fix:
// INTEGRATOR: `import health` then `return health.collect_health()`
// INTEGRATOR: (optionally merged with {"history": history.summary()}).
"""
import gzip
import json
import os
import re
import shutil
import subprocess
import time
from datetime import datetime, timezone

_STARTED = time.time()
_HERE = os.path.dirname(os.path.abspath(__file__))

# Where the ingest worker mirrors s3://alive108-air/field/YYYY/MM/DD/
# HHmm.json.gz locally (ingest_worker.SNAPSHOT_DIR). Env override for
# tests and for deployments that mount the mirror elsewhere.
SNAPSHOT_DIR = os.path.join(_HERE, "data", "field", "snapshots")

# A snapshot relpath is its generated_at: UTC build time at minute
# precision (ingest_worker derives it from the field's built_epoch).
_SNAP_RE = re.compile(
    r"^(\d{4})/(\d{2})/(\d{2})/(\d{2})(\d{2})\.json\.gz$")

# Disk-low heuristic for the `low` flag — raw numbers are always reported;
# the flag is policy, documented here so nobody thinks it is measured.
DISK_LOW_PCT = 5.0
DISK_LOW_BYTES = 256 * 1024 * 1024  # 256 MiB

# env vars that count as "this source is configured"
_SOURCE_ENV = {
    "model": (["OPEN_METEO_BASE"], "Open-Meteo/CAMS public grid — no key required"),
    "met": (["OPEN_METEO_BASE"],
            "Open-Meteo wind + boundary-layer height — no key required"),
    "stations": (["OPENAQ_API_KEY", "OPENAQ_KEY", "DATAGOV_KEY"],
                 "OpenAQ v3 / data.gov.in CPCB — secret alive108/openaq"),
    "fires": (["FIRMS_MAP_KEY"], "NASA FIRMS — public daily CSV fallback if unset"),
    "location": (["LOCATION_API_KEY", "AWS_EXECUTION_ENV",
                  "AWS_CONTAINER_CREDENTIALS_RELATIVE_URI", "AWS_ACCESS_KEY_ID"],
                 "Amazon Location maps/places/routes — task role or API key"),
}


def _build_sha():
    sha = os.environ.get("BUILD_SHA") or os.environ.get("GIT_SHA")
    if sha:
        return sha
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=_HERE, stderr=subprocess.DEVNULL, text=True,
        ).strip()
    except Exception:
        return "unknown"


def _version():
    v = os.environ.get("APP_VERSION") or os.environ.get("ALIVE_VERSION")
    if v:
        return v
    try:  # pyproject.toml sits next to this file; no tomllib before 3.11
        import tomllib  # type: ignore
        with open(os.path.join(_HERE, "pyproject.toml"), "rb") as f:
            return tomllib.load(f).get("project", {}).get("version", "dev")
    except Exception:
        return "dev"


def _iso(epoch_s: float) -> str:
    return datetime.fromtimestamp(epoch_s, tz=timezone.utc).isoformat(
        timespec="seconds")


def _iso_to_epoch(s):
    """ISO-8601 -> epoch, or None. Accepts the 'Z' suffix we write."""
    try:
        return datetime.fromisoformat(
            str(s).replace("Z", "+00:00")).timestamp()
    except (ValueError, TypeError):
        return None


def _snapshot_root(snapshot_root=None):
    return snapshot_root or os.environ.get("ALIVE_SNAPSHOT_DIR") or SNAPSHOT_DIR


def _path_generated_ts(rel: str):
    """'YYYY/MM/DD/HHmm.json.gz' -> epoch (UTC), or None when the name
    doesn't encode a valid time — malformed names are skipped, never
    dated by mtime (a copied file must not fake a fresh field)."""
    m = _SNAP_RE.match(rel.replace(os.sep, "/"))
    if not m:
        return None
    try:
        return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)),
                        int(m.group(4)), int(m.group(5)),
                        tzinfo=timezone.utc).timestamp()
    except ValueError:  # e.g. 2026/13/40/2561.json.gz — matches, isn't real
        return None


def _newest_snapshot(snapshot_root=None):
    """-> (abs_path, relpath, generated_ts) of the newest convention-named
    snapshot under the root, or (None, None, None). Skips names that don't
    match the writer's YYYY/MM/DD/HHmm.json.gz convention — mtime is never
    a proxy for generated_at."""
    root = _snapshot_root(snapshot_root)
    best = (None, None, None)
    try:
        for base, _dirs, files in os.walk(root):
            for name in files:
                if not name.endswith(".json.gz"):
                    continue
                path = os.path.join(base, name)
                rel = os.path.relpath(path, root)
                ts = _path_generated_ts(rel)
                if ts is None:
                    continue
                if best[2] is None or ts > best[2]:
                    best = (path, rel.replace(os.sep, "/"), ts)
    except OSError:
        return best
    return best


def _read_field(path):
    """Parse the snapshot payload, or None — a corrupt newest snapshot
    still yields an honest path-derived age, not a crash."""
    try:
        with gzip.open(path, "rb") as f:
            return json.loads(f.read().decode("utf-8"))
    except Exception:  # noqa: BLE001 - any decode error -> payload ignored
        return None


def _field_probe(now, snapshot_root=None):
    """Newest-snapshot facts for the payload. age_s is now − generated_at:
    the payload's built_epoch when readable (exact), else the timestamp
    encoded in the snapshot path (minute precision). None when there is
    no valid snapshot — never mtime, never a guess."""
    path, rel, gen_ts = _newest_snapshot(snapshot_root)
    if path is None:
        return {"age_s": None, "snapshot": None, "built_at": None,
                "stored_at": None, "cells": None, "payload": None}
    built = gen_ts
    payload = _read_field(path)
    if isinstance(payload, dict):
        try:
            built = float(payload.get("built_epoch")) or gen_ts
        except (TypeError, ValueError):
            built = gen_ts
    try:
        mtime = os.path.getmtime(path)
    except OSError:
        mtime = None
    cells = None
    if isinstance(payload, dict):
        cells = (payload.get("grid") or {}).get("n_cells")
    return {
        "age_s": round(now - built, 1),
        "snapshot": rel,
        "built_at": _iso(built),
        "stored_at": _iso(mtime) if mtime is not None else None,
        "cells": cells,
        "payload": payload if isinstance(payload, dict) else None,
    }


def _field_age_s(now, snapshot_root=None):
    """Seconds since the newest field snapshot was generated, or None."""
    return _field_probe(now, snapshot_root)["age_s"]


def _disk(snapshot_root=None):
    """Filesystem free space under the snapshot tree — the disk the worker
    writes to. `low` is a flag (DISK_LOW_PCT / DISK_LOW_BYTES), the bytes
    are the signal; both are reported so alarms can pick their own rule."""
    path = _snapshot_root(snapshot_root)
    if not os.path.isdir(path):
        path = _HERE  # tree not created yet — measure the server volume
    try:
        u = shutil.disk_usage(path)
    except OSError:
        return {"path": path, "free_bytes": None, "used_bytes": None,
                "total_bytes": None, "free_pct": None, "low": None}
    free_pct = round(100.0 * u.free / u.total, 1) if u.total else None
    low = None
    if free_pct is not None:
        low = bool(free_pct < DISK_LOW_PCT or u.free < DISK_LOW_BYTES)
    return {"path": path, "free_bytes": u.free, "used_bytes": u.used,
            "total_bytes": u.total, "free_pct": free_pct, "low": low}


def _source(name, prov=None, now=None):
    """Tri-state source status. Explicit env override wins for `up`;
    `age_s`/`status` come from the newest snapshot's provenance — real
    observed build data, recomputed against `now` so it stays honest."""
    out = {}
    override = os.environ.get("SOURCE_%s_UP" % name.upper(), "").strip().lower()
    if override in ("1", "true", "yes", "up"):
        out["up"] = True
        out["detail"] = "forced up via SOURCE_%s_UP" % name.upper()
    elif override in ("0", "false", "no", "down"):
        out["up"] = False
        out["detail"] = "forced down via SOURCE_%s_UP" % name.upper()
    else:
        out["up"] = None
        env_keys, default_detail = _SOURCE_ENV[name]
        present = [k for k in env_keys if os.environ.get(k)]
        out["detail"] = ("%s (%s set)" % (default_detail, ",".join(present))
                         if present else default_detail)
    p = prov or {}
    fetched = p.get("fetched_at")
    out["status"] = p.get("status")  # last build's own verdict, e.g. "ok"
    out["fetched_at"] = fetched
    ep = _iso_to_epoch(fetched)
    out["age_s"] = round(now - ep, 1) if (ep is not None and now) else None
    return out


def _trips_backend() -> str:
    """Which aggregate store /v2/trip writes to — memory | dynamodb | a
    failure note. Kept lazy+guarded: /health must never die on a missing
    optional module."""
    try:
        from v2.store import TRIPS
    except Exception:
        try:
            from server.v2.store import TRIPS  # type: ignore
        except Exception:
            return "unknown"
    return getattr(TRIPS, "backend", type(TRIPS).__name__)


def collect_health(now=None, snapshot_root=None):
    """Full health payload — safe to call from any route, any worker.

    `now`/`snapshot_root` are injectable for tests; production callers
    pass nothing."""
    now = time.time() if now is None else float(now)
    probe = _field_probe(now, snapshot_root)
    prov = (probe["payload"] or {}).get("provenance") or {}
    field_blk = {k: probe[k] for k in
                 ("snapshot", "built_at", "stored_at", "cells")}
    return {
        "ok": True,
        "ts": now,
        "build_sha": _build_sha(),
        "version": _version(),
        "uptime_s": round(now - _STARTED, 1),
        "field_age_s": probe["age_s"],
        "field": field_blk,
        "disk": _disk(snapshot_root),
        "sources": {name: _source(name, prov.get(name), now) for name in
                    ("model", "met", "stations", "fires", "location")},
        "trips_backend": _trips_backend(),
    }


if __name__ == "__main__":
    import json as _json
    print(_json.dumps(collect_health(), indent=2, default=str))
