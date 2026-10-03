"""Ops health probe for /health — no boto3, no AWS calls, import-safe.

`collect_health()` returns a plain dict main.py can jsonify directly:

    {
      "ok": True,
      "ts": 1696...,           # unix seconds
      "build_sha": "abc123",   # $BUILD_SHA, else `git rev-parse --short HEAD`
      "version": "0.2.0",      # $APP_VERSION / pyproject, else "dev"
      "uptime_s": 123.4,       # seconds since this module was imported
      "field_age_s": 812.0,    # age of newest file in data/field/snapshots
      "sources": {             # up=None means "not probed", never a guess
        "model":    {"up": null, "detail": "..."},
        "stations": {"up": null, "detail": "..."},
        "fires":    {"up": null, "detail": "..."},
        "location": {"up": null, "detail": "..."}
      }
    }

Probing policy: we never make network calls here — a /health handler must
answer even when every upstream is down (that is exactly when it is hit
hardest). `up` is therefore tri-state:
  * True/False — explicit override via env SOURCE_<NAME>_UP=true|false
    (set by the deploy pipeline or a future probe lane)
  * None — credentials/config presence only; detail says what was found.
"""
import os
import subprocess
import time

_STARTED = time.time()
_HERE = os.path.dirname(os.path.abspath(__file__))

# env vars that count as "this source is configured"
_SOURCE_ENV = {
    "model": (["OPEN_METEO_BASE"], "Open-Meteo/CAMS public grid — no key required"),
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


def _field_age_s(now):
    """Seconds since the newest field snapshot was written, or None.

    Snapshots land in server/data/field/snapshots (mirroring
    s3://alive108-air/field/YYYY/MM/DD/HHmm.json.gz). We take max mtime
    across the tree; a missing/empty dir means the worker has never run
    on this box -> None, not an exception.
    """
    snapdir = os.path.join(_HERE, "data", "field", "snapshots")
    newest = None
    try:
        for root, _dirs, files in os.walk(snapdir):
            for name in files:
                try:
                    mt = os.path.getmtime(os.path.join(root, name))
                except OSError:
                    continue
                if newest is None or mt > newest:
                    newest = mt
    except OSError:
        return None
    return round(now - newest, 1) if newest is not None else None


def _source(name):
    """Tri-state source status. Explicit env override wins; otherwise we
    report config presence only — up=None, never a fabricated healthy."""
    override = os.environ.get("SOURCE_%s_UP" % name.upper(), "").strip().lower()
    if override in ("1", "true", "yes", "up"):
        return {"up": True, "detail": "forced up via SOURCE_%s_UP" % name.upper()}
    if override in ("0", "false", "no", "down"):
        return {"up": False, "detail": "forced down via SOURCE_%s_UP" % name.upper()}
    env_keys, default_detail = _SOURCE_ENV[name]
    present = [k for k in env_keys if os.environ.get(k)]
    if present:
        detail = "%s (%s set)" % (default_detail, ",".join(present))
    else:
        detail = default_detail
    return {"up": None, "detail": detail}


def collect_health():
    """Full health payload — safe to call from any route, any worker."""
    now = time.time()
    return {
        "ok": True,
        "ts": now,
        "build_sha": _build_sha(),
        "version": _version(),
        "uptime_s": round(now - _STARTED, 1),
        "field_age_s": _field_age_s(now),
        "sources": {name: _source(name) for name in
                    ("model", "stations", "fires", "location")},
    }


if __name__ == "__main__":
    import json
    print(json.dumps(collect_health(), indent=2, default=str))
