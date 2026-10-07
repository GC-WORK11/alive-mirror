"""Pytest path setup — make `server/` and the alive_core build dir importable."""
import glob
import os
import sys

_SERVER = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# the compiled ext lands in a versioned dir (core/build312/ etc. since
# 0b93eaa) — glob any build* so the suite exercises the real C++ path,
# not the pure-python reference fallback (which is ~10x slower and made
# test_search_latency_compound_path fail under pytest while standalone
# runs passed).
_paths = [_SERVER] + sorted(glob.glob(os.path.join(_SERVER, "core", "build*")))
for _p in _paths:
    if _p not in sys.path:
        sys.path.insert(0, _p)

# The suite fires hundreds of requests through the mounted rate limiter —
# it must test payloads, not throttling. Production keeps the limiter on;
# test_security.py covers it with its own tuned instance.
os.environ.setdefault("ALIVE_RATE_LIMIT", "0")
# tests never spawn the 15-min ingest thread (real network builds)
os.environ.setdefault("ALIVE_INGEST_IN_APP", "0")
# ...nor the hourly field archiver (writes data/archive/ + S3)
os.environ.setdefault("ALIVE_ARCHIVE", "0")


def pytest_configure(config):
    config.addinivalue_line(
        "markers", "live: hits real upstreams (Open-Meteo/FIRMS); "
        "skipped unless LIVE=1 — see tests/test_e2e_live.py")
