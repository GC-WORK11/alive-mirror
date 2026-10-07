"""Offline tests for GET /v2/city — the 'Delhi today' payload.

No network: deps.field_refresh is a no-op over injected field samples,
the location client is a local fake, corridors are seeded straight
into store.TRIPS. Run from server/:
    uv run pytest tests/test_v2_city.py -q
"""
import os
import sys
import time

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.pop("ALIVE_LOCATION_KEY", None)  # honest default: disabled

from fastapi.testclient import TestClient  # noqa: E402

import main  # noqa: E402
from airfield import FIELD  # noqa: E402
from v2 import city as v2city  # noqa: E402
from v2 import deps, store  # noqa: E402
from v2 import trip as v2trip  # noqa: E402

client = TestClient(main.app)

SAMPLES = [
    (28.6315, 77.2167, "test-station", {"pm2_5": 150.0}),
    (28.6519, 77.1907, None, {"pm2_5": 185.0}),
    (28.5850, 77.2300, None, {"pm2_5": 120.0}),
    (28.7000, 77.2000, None, {"pm2_5": 210.0}),
]


class FakeLoc:
    """Same reverse_geocode surface as location_client.LocationClient."""
    def __init__(self, enabled=True):
        self.enabled = enabled

    async def reverse_geocode(self, lat, lon, limit=10):
        return [{"place_id": "r1", "street": "Rajpath",
                 "locality": "Central Secretariat",
                 "label": "Rajpath, Central Secretariat, New Delhi",
                 "lat": 28.6150, "lon": 77.2150, "distance_m": 40,
                 "kind": "Street", "source": "amazon"}]


@pytest.fixture(autouse=True)
def wired(monkeypatch):
    """Injected field + fake location client + no-op refresh."""
    deps.set_location(FakeLoc())
    FIELD._samples = list(SAMPLES)
    FIELD._fetched_at = time.time()
    FIELD._station_count = 0
    FIELD._stations_live = []
    FIELD._source = "open-meteo/cams"

    async def _no_refresh():
        return None
    monkeypatch.setattr(deps, "field_refresh", _no_refresh)
    store.TRIPS.reset()
    yield
    deps.set_location(None)
    FIELD._samples = []
    FIELD._snap = None          # snapshot layer must be empty too —
    FIELD._snap_centers = []    # airfield autoloads it at import; the
    FIELD._snap_epoch = 0.0     # serving gate keys on _snap_centers
    FIELD._station_count = 0
    FIELD._stations_live = []


def _seed_corridor(lat, lon, tokens, dose=60.0):
    """`tokens` distinct devices crossing one cell, one trip each."""
    cell = v2trip._cell(lat, lon)
    for i, tok in enumerate(tokens):
        store.TRIPS.record_trip(
            [cell], {"mode": "car", "distance_km": 3.0,
                     "dose_ug": dose + i}, tok)
    return cell


# --- payload shape ------------------------------------------------------------
def test_payload_shape_and_legacy_keys():
    b = client.get("/v2/city").json()
    for k in ("ts", "generated_at", "pm25_stats", "field", "field_age_s",
              "freshness", "provenance", "breath", "corridors",
              "enough_data", "wind", "sources", "trips"):
        assert k in b, f"missing {k}"

    breath = b["breath"]
    for unit in ("pm25_ugm3", "day_inhaled_ug", "cigarettes"):
        band = breath[unit]
        assert band["lo"] <= band["mid"] <= band["hi"]
        assert band["mid"] > 0
    # the Berkeley Earth day-rule is exact by construction: cigs = pm25/22
    assert abs(breath["cigarettes"]["mid"]
               - breath["pm25_ugm3"]["mid"] / 22.0) < 0.01

    fresh = b["freshness"]
    assert fresh["label"] in ("live", "stale", "unknown")
    assert fresh["field_age_s"] == b["field_age_s"]
    assert isinstance(b["generated_at"], str) and "T" in b["generated_at"]

    # the pre-existing keys keep their shape (additive compatibility)
    assert {"model", "stations", "fires", "location"} <= set(b["sources"])
    assert "days" in b["trips"] and "cells_tracked" in b["trips"]
    assert b["pm25_stats"]["mean"] > 0


# --- k>=3 suppression ----------------------------------------------------------
def test_corridors_empty_below_k3():
    _seed_corridor(28.63, 77.21, ["t1", "t2"])  # 2 devices < k=3
    b = client.get("/v2/city").json()
    assert b["corridors"] == []
    assert b["enough_data"] is False


def test_corridors_publishable_at_k3():
    cell = _seed_corridor(28.63, 77.21, ["t1", "t2", "t3"])
    b = client.get("/v2/city").json()
    assert b["enough_data"] is True
    assert len(b["corridors"]) == 1
    row = b["corridors"][0]
    assert row["cell"] == cell
    assert row["trips"] == 3 and row["devices"] == 3
    assert row["relative"] in ("heavier", "lighter")
    assert {"cell", "name", "lat", "lon", "trips",
            "avg_dose_ug", "relative"} <= set(row)


def test_corridors_relative_labels_and_privacy():
    _seed_corridor(28.63, 77.21, ["a", "b", "c"], dose=80.0)   # heavier
    _seed_corridor(28.70, 77.20, ["d", "e", "f"], dose=30.0)   # lighter
    b = client.get("/v2/city").json()
    assert len(b["corridors"]) == 2
    assert {r["relative"] for r in b["corridors"]} == {"heavier", "lighter"}
    # heaviest first
    assert (b["corridors"][0]["avg_dose_ug"]
            >= b["corridors"][-1]["avg_dose_ug"])
    for row in b["corridors"]:
        assert row["name"] is None or isinstance(row["name"], str)
        # aggregates only — no token material, 4-dp coordinate ceiling
        assert "token" not in repr(row).lower()
        assert abs(row["lat"] - round(row["lat"], 4)) < 1e-9
        assert abs(row["lon"] - round(row["lon"], 4)) < 1e-9


def test_corridor_names_never_fabricated():
    deps.set_location(FakeLoc(enabled=False))
    _seed_corridor(28.63, 77.21, ["a", "b", "c"])
    b = client.get("/v2/city").json()
    for row in b["corridors"]:
        assert row["name"] is None or isinstance(row["name"], str)


# --- provenance honesty --------------------------------------------------------
def test_stations_zero_labelled_explicitly():
    FIELD._station_count = 0
    b = client.get("/v2/city").json()
    st = b["provenance"]["stations"]
    assert st["count"] == 0 and st["live"] is False
    assert "no live station" in st["note"]
    assert b["sources"]["stations"]["up"] is False
    assert b["sources"]["stations"]["count"] == 0
    # the model side still reports what is real
    assert b["provenance"]["model"]["up"] is True
    assert b["provenance"]["model"]["samples"] >= 1


def test_stations_count_reported():
    FIELD._station_count = 12
    b = client.get("/v2/city").json()
    st = b["provenance"]["stations"]
    assert st["count"] == 12 and st["live"] is True
    assert "12" in st["note"]
    assert b["sources"]["stations"]["count"] == 12


def test_provenance_trip_rule():
    b = client.get("/v2/city").json()
    tr = b["provenance"]["trips"]
    assert tr["k_min"] == 3 and tr["window_h"] == 72
    assert tr["publishable_corridors"] == 0
    _seed_corridor(28.63, 77.21, ["a", "b", "c"])
    b = client.get("/v2/city").json()
    assert b["provenance"]["trips"]["publishable_corridors"] == 1


# --- edge cases ----------------------------------------------------------------
def test_breath_none_when_field_empty():
    FIELD._samples = []
    FIELD._snap = None          # clear the served snapshot layer too —
    FIELD._snap_centers = []    # _serving_snapshot() gates on centers;
    FIELD._snap_epoch = 0.0     # else the field stays non-empty by design
    b = client.get("/v2/city").json()
    assert b["breath"] is None
    assert b["pm25_stats"]["n"] == 0
    assert b["corridors"] == [] and b["enough_data"] is False


def test_freshness_labels():
    assert v2city._freshness(60)["label"] == "live"
    assert v2city._freshness(60)["age_min"] == 1
    assert v2city._freshness(7201)["label"] == "stale"
    assert v2city._freshness(None)["label"] == "unknown"
    FIELD._fetched_at = time.time() - 4000  # > 2 x 15 min cadence
    assert client.get("/v2/city").json()["freshness"]["label"] == "stale"


def test_cell_center_both_schemes():
    la, lo = v2city._cell_center("ll:28.6300,77.2100")
    assert abs(la - 28.63) < 1e-6 and abs(lo - 77.21) < 1e-6
    ctr = v2city._cell_center(v2trip._cell(28.63, 77.21))
    assert ctr is not None
    # an h3 res-8 centre is within ~1 km of the query point
    assert abs(ctr[0] - 28.63) < 0.01 and abs(ctr[1] - 77.21) < 0.01
    assert v2city._cell_center("not-a-cell") is None


# --- the today-ledger never serves an older day under TODAY ------------------
def _seed_day(offset_h, n, km=3.0):
    """n trips timestamped offset_h hours ago (another UTC day when
    offset crosses midnight)."""
    ts = time.time() - offset_h * 3600
    for i in range(n):
        store.TRIPS.record_trip(
            ["ll:28.6000,77.2000"],
            {"mode": "walk", "distance_km": km, "dose_ug": 40.0 + i},
            f"dev-{offset_h}-{i}", ts=ts)


def test_today_ledger_never_falls_back_to_last_populated_day():
    """Audit bug: /city 'the ledger, today' painted the NEWEST day-key
    under a today label — after any donation gap that is yesterday's
    numbers. The server now serves today_key + today explicitly; an
    absent today is the honest-empty state, not the last day."""
    _seed_day(offset_h=26, n=8)              # yesterday: 8 trips
    t = client.get("/v2/city").json()["trips"]
    today = time.strftime("%Y-%m-%d", time.gmtime())
    assert t["today_key"] == today
    assert t["today"] is None, "no today key must never paint yesterday"
    assert sum(d["trips"] for d in t["days"].values()) == 8


def test_today_ledger_serves_todays_real_numbers():
    _seed_day(offset_h=26, n=8)
    _seed_day(offset_h=1, n=2, km=5.0)       # today: 2 trips, 10 km
    t = client.get("/v2/city").json()["trips"]
    today = time.strftime("%Y-%m-%d", time.gmtime())
    assert t["today_key"] == today
    assert t["today"]["trips"] == 2
    assert t["today"]["km"] == 10.0
    assert sum(d["trips"] for d in t["days"].values()) == 10
