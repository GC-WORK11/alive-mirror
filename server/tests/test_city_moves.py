"""Tests for GET /v2/city/moves — the 'how Delhi moves' aggregate view.

Same contract as the rest of the city surface: everything is a
TripAggregates number, every emitted row is k>=3, and an empty/thin
store answers insufficient_data — never a distribution drawn from
nothing. Trips are seeded straight into store.TRIPS (already-privacized
shape: cell keys + hashed tokens + summary, exactly what /v2/trip
hands the store). Run from server/:
    uv run pytest tests/test_city_moves.py -q
"""
import time

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from v2 import city as v2city
from v2.store import TRIPS

app = FastAPI()
app.include_router(v2city.router, prefix="/v2")
client = TestClient(app)

# Field names that must never appear in the payload, at any depth.
BANNED_KEYS = {
    "token", "tokens", "token_hash", "device_token", "device_id",
    "lat", "lon", "latitude", "longitude", "coord", "coords",
    "trajectory", "points", "geometry", "route",
    "user", "users", "uid", "uuid", "ip", "contributor",
}


@pytest.fixture(autouse=True)
def clean_store():
    TRIPS.reset()
    yield
    TRIPS.reset()


def _donate(n, mode="metro", days_ago=0, dose=40.0, co2=1.2, pm25=5.0,
            cell="cellX", tok=None):
    """`n` trips of one mode on one UTC day — mirrors record_trip calls
    a real /v2/trip POST produces. Distinct tokens per trip."""
    ts = time.time() - days_ago * 86400.0
    for i in range(n):
        TRIPS.record_trip(
            [f"{cell}-{i}"],
            {"mode": mode, "distance_km": 4.0, "dose_ug": dose,
             "co2_kg_mid": co2, "pm25_g_mid": pm25},
            token_hash=f"{tok or mode}-{days_ago}-{i}", ts=ts)


def _keys(obj):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield str(k)
            yield from _keys(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _keys(v)


# --- shape -------------------------------------------------------------------

def test_shape_and_provenance_keys():
    d = client.get("/v2/city/moves").json()
    for k in ("ts", "generated_at", "window", "min_k", "n_trips",
              "n_days", "insufficient_data", "mode_share",
              "mode_share_suppressed_trips", "corridors",
              "per_trip", "basis"):
        assert k in d, f"missing {k}"
    assert d["min_k"] == 3
    assert d["window"]["days"] == 7
    assert d["window"]["from"] <= d["window"]["to"]
    assert {"window_h", "active", "tracked", "avg_dose_ug"} \
        <= set(d["corridors"])


# --- honesty at the bottom ----------------------------------------------------

def test_empty_store_is_insufficient_not_zeroed():
    d = client.get("/v2/city/moves").json()
    assert d["insufficient_data"] is True
    assert d["n_trips"] == 0 and d["n_days"] == 0
    assert d["mode_share"] == []
    assert d["mode_share_suppressed_trips"] == 0
    # null bands, never a 0 posing as a measurement
    assert d["per_trip"]["dose_ug"] is None
    assert d["per_trip"]["co2_kg"] is None
    assert d["per_trip"]["pm25_g"] is None
    assert d["corridors"]["avg_dose_ug"] is None
    assert d["corridors"]["active"] == 0


def test_below_min_k_still_insufficient_but_counted():
    _donate(2, mode="metro")              # real trips, just not enough
    d = client.get("/v2/city/moves").json()
    assert d["insufficient_data"] is True
    assert d["n_trips"] == 2              # the count itself is real data
    assert d["mode_share"] == []         # a 2-trip mode is not a row
    assert d["mode_share_suppressed_trips"] == 2


# --- mode share: the k>=3 row rule ---------------------------------------------

def test_mode_share_rows_and_other_pool():
    _donate(5, mode="metro")
    _donate(3, mode="car", tok="c")
    _donate(2, mode="walk", tok="w")      # pooled…
    _donate(1, mode="cycle", tok="cy")    # …into one k=3 'other' row
    d = client.get("/v2/city/moves").json()
    assert d["insufficient_data"] is False
    assert d["n_trips"] == 11
    rows = {r["mode"]: r for r in d["mode_share"]}
    assert set(rows) == {"metro", "car", "other"}
    assert rows["metro"]["trips"] == 5
    assert abs(rows["metro"]["share"] - 5 / 11) < 0.001
    assert rows["other"]["trips"] == 3    # walk + cycle pooled
    assert d["mode_share_suppressed_trips"] == 0
    # heaviest share first, 'other' last
    assert [r["mode"] for r in d["mode_share"]] == ["metro", "car", "other"]


def test_mode_share_sub_k_pool_suppressed_not_rowed():
    _donate(5, mode="metro")
    _donate(2, mode="walk", tok="w")      # pool of 2 < k=3
    d = client.get("/v2/city/moves").json()
    rows = {r["mode"]: r for r in d["mode_share"]}
    assert set(rows) == {"metro"}         # no 'other' row at k=2
    assert d["mode_share_suppressed_trips"] == 2
    # every emitted row clears the threshold — the literal contract
    assert all(r["trips"] >= 3 for r in d["mode_share"])


# --- per-trip percentile bands --------------------------------------------------

def test_per_trip_bands_use_qualifying_days_only():
    # two qualifying days (>=3 trips each) with different recorded dose
    _donate(3, mode="metro", days_ago=0, dose=30.0, co2=0.0, pm25=0.0)
    _donate(3, mode="car", days_ago=1, dose=60.0, tok="c", pm25=0.0)
    # a thin day (2 trips) with huge dose — must not move the band
    _donate(2, mode="auto", days_ago=2, dose=999.0, tok="a")
    d = client.get("/v2/city/moves").json()
    band = d["per_trip"]["dose_ug"]
    assert band["n"] == 2
    # inclusive quartiles of the two day-means [30, 60]
    assert band["p25"] == 37.5 and band["p50"] == 45.0
    assert band["p75"] == 52.5
    assert band["p25"] <= band["p50"] <= band["p75"]
    # co2 recorded on one day only — n reports the thinness honestly
    co2 = d["per_trip"]["co2_kg"]
    assert co2["n"] == 1 and co2["p50"] == round(3.6 / 3, 2)
    # pm25 recorded nowhere -> null band, not a fabricated 0 g
    assert d["per_trip"]["pm25_g"] is None
    assert d["per_trip"]["n_days"] == 2


def test_band_single_day_collapses_to_point():
    _donate(4, mode="bus", dose=48.0)
    d = client.get("/v2/city/moves").json()
    band = d["per_trip"]["dose_ug"]
    assert band["n"] == 1
    assert band["p25"] == band["p50"] == band["p75"] == 48.0


# --- corridors + window ---------------------------------------------------------

def test_corridors_active_count_and_dose_band():
    cell = "cellQ"
    for i, tok in enumerate(("d1", "d2", "d3")):   # k=3 devices, one cell
        TRIPS.record_trip([cell], {"mode": "car", "dose_ug": 60.0},
                          token_hash=tok)
    d = client.get("/v2/city/moves").json()
    assert d["corridors"]["active"] == 1
    assert d["corridors"]["tracked"] >= 1
    band = d["corridors"]["avg_dose_ug"]
    assert band["n"] == 1 and band["p50"] == 60.0


def test_window_excludes_old_days():
    _donate(5, mode="metro", days_ago=10)          # outside the 7-day cut
    d = client.get("/v2/city/moves").json()
    assert d["n_trips"] == 0
    assert d["insufficient_data"] is True
    _donate(4, mode="metro", days_ago=6)           # inside
    d = client.get("/v2/city/moves").json()
    assert d["n_trips"] == 4
    assert d["insufficient_data"] is False


# --- privacy scan ----------------------------------------------------------------

def test_no_identity_or_coordinate_fields_anywhere():
    _donate(4, mode="metro")
    for i, tok in enumerate(("d1", "d2", "d3")):
        TRIPS.record_trip(["cellQ"], {"mode": "car", "dose_ug": 60.0},
                          token_hash=tok)
    d = client.get("/v2/city/moves").json()
    leaked = {k.lower() for k in _keys(d)} & BANNED_KEYS
    assert not leaked, f"payload leaks field(s): {leaked}"


# --- helper unit checks -----------------------------------------------------------

def test_pct_band_edges():
    assert v2city._pct_band([]) is None
    b = v2city._pct_band([7.5])
    assert b == {"p25": 7.5, "p50": 7.5, "p75": 7.5, "n": 1}
    b = v2city._pct_band([10.0, 20.0, 30.0, 40.0])
    assert b["p25"] <= b["p50"] <= b["p75"] and b["n"] == 4
