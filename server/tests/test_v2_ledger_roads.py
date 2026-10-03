"""Offline tests for the device ledger (/v2/ledger), road-wise exposure
grouping in /v2/strip, and refresh-honesty fields (/health, field
status). No network: FIELD is seeded the same way as test_v2_strip.
"""
import hashlib
import os
import sys
import time

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.pop("ALIVE_LOCATION_KEY", None)

from fastapi.testclient import TestClient  # noqa: E402

import main  # noqa: E402
from airfield import FIELD  # noqa: E402
from v2 import deps, store  # noqa: E402
from v2 import strip as v2strip  # noqa: E402

client = TestClient(main.app)

LINE = {"type": "LineString",
        "coordinates": [[77.2090, 28.6139], [77.2150, 28.6300],
                        [77.1990, 28.6450]]}


async def _noop():
    return None


@pytest.fixture(autouse=True)
def wired(monkeypatch):
    FIELD._samples = [
        (28.6315, 77.2167, "test-station", {"pm2_5": 150.0}),
        (28.6519, 77.1907, None, {"pm2_5": 185.0}),
    ]
    FIELD._fetched_at = time.time()
    monkeypatch.setattr(deps, "field_refresh", _noop)
    store.ROUTES._routes.clear()
    store.LEDGER.reset()
    yield
    FIELD._samples = []
    store.LEDGER.reset()


def _post_trip(token: str, traj, dose=50.0, km=4.0):
    return client.post("/v2/trip", json={
        "device_token": token,
        "trajectory": traj,
        "summary": {"distance_km": km, "duration_s": 900,
                    "dose_ug": dose, "co2_kg_mid": 0.8,
                    "pm25_g_mid": 0.001, "mode": "car"},
    })


# --- /v2/ledger --------------------------------------------------------------
TRAJ = [[77.2090, 28.6139], [77.2150, 28.6300], [77.2190, 28.6450],
        [77.2050, 28.6550], [77.1990, 28.6650]]


def test_trip_then_ledger_reads_own_rows():
    r = _post_trip("tok-a", TRAJ)
    assert r.status_code == 200 and r.json()["ledger_recorded"] is True

    led = client.get("/v2/ledger", params={"token": "tok-a"})
    assert led.status_code == 200
    body = led.json()
    assert body["totals"]["trips"] == 1
    assert body["totals"]["dose_ug"] == pytest.approx(50.0)
    assert body["totals"]["km"] == pytest.approx(4.0)
    row = body["trips"][0]
    assert row["mode"] == "car" and "ts" in row
    # privacy: no trajectory or cell keys leak into per-device history
    assert not any(k in row for k in ("cells", "trajectory", "coords"))


def test_ledger_isolated_per_token_and_empty_is_honest():
    _post_trip("tok-b", TRAJ, dose=10.0, km=2.0)
    other = client.get("/v2/ledger", params={"token": "tok-c"}).json()
    assert other["trips"] == [] and other["totals"]["trips"] == 0
    own = client.get("/v2/ledger", params={"token": "tok-b"}).json()
    assert own["totals"]["trips"] == 1


def test_ledger_no_token_means_no_history():
    r = client.post("/v2/trip", json={
        "trajectory": TRAJ, "summary": {"distance_km": 1.0}})
    assert r.status_code == 200
    assert r.json()["ledger_recorded"] is False


def test_ledger_token_hashed_never_raw():
    _post_trip("tok-d", TRAJ)
    raw = hashlib.sha256(b"tok-d").hexdigest()[:16]
    assert raw in store.LEDGER._ledgers
    assert "tok-d" not in store.LEDGER._ledgers


# --- roads[] in /v2/strip -----------------------------------------------------
def _route_with_steps():
    rid = store.ROUTES.put({
        "geometry": LINE, "mode": "car", "duration_s": 900,
        "vehicle": "car", "emissions_vehicle": None,
        "steps": [
            {"instruction": "go", "street": "Ring Road",
             "distance_m": 1500, "type": "turn"},
            {"instruction": "left", "street": "Ring Road",
             "distance_m": 500, "type": "turn"},
            {"instruction": "right", "street": "Lodi Road",
             "distance_m": 1500, "type": "turn"},
            {"instruction": "arrive", "street": "",
             "distance_m": 1000, "type": "arrive"},
        ],
    })
    return rid


def test_strip_groups_samples_under_roads():
    rid = _route_with_steps()
    r = client.get("/v2/strip", params={"route_id": rid})
    assert r.status_code == 200
    roads = r.json()["roads"]
    names = [x["name"] for x in roads]
    assert "Ring Road" in names and "Lodi Road" in names
    ring = next(x for x in roads if x["name"] == "Ring Road")
    # adjacent same-name steps merged into one road entry
    assert ring["dist_m"] == pytest.approx(2000, abs=300)
    assert ring["avg_pm25"] is not None
    shares = [x["dose_share"] for x in roads if x["dose_share"]]
    assert shares and abs(sum(shares) - 1.0) < 0.05
    # unnamed step span is honestly labeled, not invented
    assert any(x["name"] == "unnamed road" for x in roads)


def test_strip_no_steps_means_empty_roads():
    rid = store.ROUTES.put({"geometry": LINE, "mode": "car",
                            "duration_s": 600})
    r = client.get("/v2/strip", params={"route_id": rid})
    assert r.status_code == 200
    assert r.json()["roads"] == []


def test_roads_for_empty_samples():
    assert v2strip._roads_for([], [{"street": "X", "distance_m": 100}]) == []


# --- refresh honesty -----------------------------------------------------------
def test_health_reports_refresh_and_stale():
    h = client.get("/health").json()
    assert "field_refresh_in_s" in h
    assert "field_stale" in h
    st = FIELD.status()
    assert "refresh_in_s" in st and "refresh_ttl_s" in st
    # live field fetched just now → a refresh is scheduled within the TTL
    assert st["refresh_in_s"] is not None
    assert 0 <= st["refresh_in_s"] <= st["refresh_ttl_s"]
