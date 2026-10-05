"""/v2 response caches — 60 s, epoch-keyed, honestly declared.

What the cache must prove:
  * a repeat request inside the TTL is a byte/dict hit (x-alive-cache
    header marks it — the cache is declared, never silent)
  * a data refresh mid-TTL invalidates: the field/forecast epoch is
    part of the key, so seeded-test bumps behave like a live refresh
  * error payloads are never cached — a dead forecast retries honestly
  * the stored reach veil serves took_ms spliced to real serve time

Offline like the rest of the v2 suite: seeded FIELD + FORECAST, no
network. The reach cases skip cleanly when the graph/engine is absent.
"""
import os
import sys
import time
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))

import main  # noqa: E402
from airfield import FIELD  # noqa: E402
from forecast import FORECAST  # noqa: E402
from v2 import deps  # noqa: E402

client = TestClient(main.app, raise_server_exceptions=False)

CP = (28.6315, 77.2167)

SAMPLES = [
    (28.6315, 77.2167, "test-station", {"pm2_5": 150.0}),
    (28.6519, 77.1907, None, {"pm2_5": 185.0}),
    (28.5850, 77.2300, None, {"pm2_5": 120.0}),
    (28.7000, 77.2000, None, {"pm2_5": 210.0}),
]


def _seed_forecast(vals):
    t0 = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0,
                                            microsecond=0)
    times = [(t0 + timedelta(hours=i)).isoformat()
             for i in range(len(vals))]
    FORECAST._aq = [{"lat": CP[0], "lon": CP[1], "name": None, "t0": t0,
                     "times": times, "vars": {"pm2_5": list(vals)}}]
    FORECAST._met = []
    FORECAST._fetched_at = time.time()


@pytest.fixture(autouse=True)
def wired(monkeypatch):
    FIELD._samples = list(SAMPLES)
    FIELD._fetched_at = time.time()
    FIELD._station_count = 0
    FIELD._source = "test"
    FIELD._snap = None
    FIELD._snap_centers = []
    FIELD._snap_epoch = 0.0
    _seed_forecast([120.0] * 120)

    async def _noop(*a, **k):
        return None
    monkeypatch.setattr(deps, "field_refresh", _noop)
    monkeypatch.setattr(FIELD, "refresh", _noop)
    monkeypatch.setattr(FORECAST, "refresh", _noop)
    yield
    FIELD._samples = []
    FORECAST._aq = []
    FORECAST._met = []
    FORECAST._fetched_at = 0.0


# ------------------------------------------------------------- TTLCache
def test_ttl_cache_expires_and_evicts():
    c = deps.TTLCache(0.05, max_entries=3)
    c.put("a", 1)
    assert c.get("a") == 1
    time.sleep(0.06)
    assert c.get("a") is None            # expired reads drop the entry
    for i in range(5):
        c.put(i, i)
    assert len(c._d) <= 3                # bound holds under overflow
    assert c.get(4) == 4


def test_data_epoch_moves_with_refresh():
    e0 = deps.data_epoch()
    assert e0 > 0
    FIELD._fetched_at = time.time() + 5.0
    e1 = deps.data_epoch()
    assert e1 > e0                       # a fresher field moves the key


# ------------------------------------------------------------ /v2/day
def test_day_hit_is_declared_and_identical():
    params = {"lat": CP[0], "lon": CP[1]}
    r1 = client.get("/v2/day", params=params)
    assert r1.status_code == 200
    if not r1.json().get("hours"):
        pytest.skip("seeded forecast produced no card")
    assert r1.headers.get("x-alive-cache") is None
    r2 = client.get("/v2/day", params=params)
    assert r2.status_code == 200
    assert r2.headers.get("x-alive-cache") == "hit"
    assert r2.json() == r1.json()        # same fold, byte-stable


def test_day_epoch_bump_is_a_miss():
    params = {"lat": CP[0], "lon": CP[1]}
    r1 = client.get("/v2/day", params=params)
    if not r1.json().get("hours"):
        pytest.skip("seeded forecast produced no card")
    FIELD._fetched_at = time.time() + 5.0   # a refresh lands mid-TTL
    r2 = client.get("/v2/day", params=params)
    assert r2.headers.get("x-alive-cache") != "hit"


def test_day_error_payload_is_never_cached():
    FORECAST._aq = []                     # dead horizon → honest error
    params = {"lat": CP[0], "lon": CP[1]}
    r1 = client.get("/v2/day", params=params)
    assert r1.json().get("error")
    # same epoch, same key — if error payloads were cached this would
    # return a 'hit' and freeze the outage for the TTL
    r2 = client.get("/v2/day", params=params)
    assert r2.headers.get("x-alive-cache") != "hit"
    assert r2.json().get("error")
    _seed_forecast([120.0] * 120)         # horizon recovers, epoch moves
    r3 = client.get("/v2/day", params=params)
    assert r3.headers.get("x-alive-cache") != "hit"
    assert not r3.json().get("error") or r3.json().get("hours")


# --------------------------------------------------------- /v2/outlook
def test_outlook_hit_is_declared():
    params = {"lat": CP[0], "lon": CP[1]}
    r1 = client.get("/v2/outlook", params=params)
    assert r1.status_code == 200
    if not r1.json().get("days"):
        pytest.skip("seeded forecast produced no outlook")
    r2 = client.get("/v2/outlook", params=params)
    assert r2.headers.get("x-alive-cache") == "hit"
    assert r2.json() == r1.json()


# ----------------------------------------------------------- /v2/reach
def test_reach_cache_splices_took_ms():
    from v2 import reach as vr
    body = b'{"a":1,"edges_e6":[[1,2]],"took_ms":1234.5}'
    t0 = time.perf_counter()
    resp = vr._cache_hit(body, t0)
    assert resp.headers.get("x-alive-cache") == "hit"
    out = bytes(resp.body).decode()
    assert out.endswith("}")
    assert '"took_ms":1234.5' not in out   # real serve time, not the
    assert '"took_ms":' in out             # stale solve's number


def test_reach_hit_serves_same_body(monkeypatch):
    # the Python-twin engine needs ~18 s for its first raster reprice
    # here (the C++ build does it in ~1 s) — give this env room; the
    # 8 s prod bound is untouched
    from v2 import reach as vr
    monkeypatch.setattr(vr, "REACH_BUDGET_S", 60.0)
    params = {"lat": CP[0], "lon": CP[1], "mode": "walk",
              "budget_ug": 25}
    r1 = client.get("/v2/reach", params=params)
    body1 = r1.json()
    if body1.get("code") in ("engine_unavailable", "timeout"):
        pytest.skip("graph/engine not shipped in this env")
    if body1.get("error"):
        pytest.skip("no snap in this env")
    assert r1.headers.get("x-alive-cache") == "miss"
    r2 = client.get("/v2/reach", params=params)
    assert r2.headers.get("x-alive-cache") == "hit"
    b2 = r2.json()
    assert b2["edges_e6"] == body1["edges_e6"]
    assert b2["took_ms"] < body1["took_ms"]   # hit is the cheap path
    assert set(b2.keys()) == set(body1.keys())  # contract keys stable
