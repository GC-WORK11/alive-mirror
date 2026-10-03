"""Pytest path setup — make `server/` and the alive_core build dir importable."""
import os
import sys

_SERVER = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in (_SERVER, os.path.join(_SERVER, "core", "build")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

# The suite fires hundreds of requests through the mounted rate limiter —
# it must test payloads, not throttling. Production keeps the limiter on;
# test_security.py covers it with its own tuned instance.
os.environ.setdefault("ALIVE_RATE_LIMIT", "0")
# tests never spawn the 15-min ingest thread (real network builds)
os.environ.setdefault("ALIVE_INGEST_IN_APP", "0")
