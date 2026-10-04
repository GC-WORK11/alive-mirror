"""Offline tests for GET /v2/districts — the NCR choropleth feed.

Same wiring as test_v2_city: injected field samples, no-op refresh,
no network. Boundary geometry comes from the baked geojson — these
tests also pin the asset's contract (13 districts, centroids inside
their own polygons).
"""
import os
import sys
import time

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.pop("ALIVE_LOCATION_KEY", None)

from fastapi.testclient import TestClient  # noqa: E402

import main  # noqa: E402
import districts  # noqa: E402
from airfield import FIELD  # noqa: E402
from v2 import deps  # noqa: E402

client = TestClient(main.app)

SAMPLES = [
    (28.6315, 77.2167, "test-station", {"pm2_5": 150.0}),
    (28.6519, 77.1907, None, {"pm2_5": 185.0}),
    (28.5850, 77.2300, None, {"pm2_5": 120.0}),
    (28.7000, 77.2000, None, {"pm2_5": 210.0}),
]


@pytest.fixture(autouse=True)
def wired(monkeypatch):
    FIELD._samples = list(SAMPLES)
    FIELD._fetched_at = time.time()
    FIELD._station_count = 0
    FIELD._source = "open-meteo/cams"

    async def _no_refresh():
        return None
    monkeypatch.setattr(deps, "field_refresh", _no_refresh)
    yield
    FIELD._samples = []
    FIELD._snap = None
    FIELD._snap_centers = []
    FIELD._snap_epoch = 0.0
    FIELD._station_count = 0


# --- AQI math -----------------------------------------------------------------
def test_cpcb_breakpoints_official():
    """CPCB PM2.5 sub-index bands (airquality.cpcb.gov.in table):
    45 µg sits mid-band at 75-76; 121+ is Very Poor; >250 is Severe."""
    assert districts.cpcb_aqi(0.0) == 0
    assert districts.cpcb_aqi(30.0) == 50
    assert districts.cpcb_aqi(45.0) in (75, 76)
    assert districts.cpcb_aqi(60.0) == 100
    assert districts.cpcb_aqi(90.0) in (199, 200)
    assert districts.cpcb_aqi(120.0) == 300
    assert 400 < districts.cpcb_aqi(300.0) <= 500
    assert districts.cpcb_aqi(None) is None


def test_us_aqi_2024_breakpoints():
    """EPA 2024 PM2.5 table (Open-Meteo us_aqi parity): Good tops at 9.0,
    Hazardous re-banded 225.5-325.4 -> 301-400."""
    assert districts.us_aqi(0.0) == 0
    assert districts.us_aqi(9.0) == 50
    assert districts.us_aqi(35.4) == 100
    assert districts.us_aqi(90.0) == 175
    assert districts.us_aqi(200.0) == 275
    assert districts.us_aqi(None) is None


def test_official_palette():
    """The six CPCB colours, incl. the official Poor #FF6500
    (ind_cpcb, NOT the often-quoted #FF9900)."""
    cols = {c: col for _, _, c, col in districts.CPCB_BANDS}
    assert cols == {"Good": "#00B050", "Satisfactory": "#92D050",
                    "Moderate": "#FFFF00", "Poor": "#FF6500",
                    "Very Poor": "#FF0000", "Severe": "#C00000"}
    assert len(districts.CPCB_BANDS) == 6


# --- payload ------------------------------------------------------------------
def test_districts_shape():
    b = client.get("/v2/districts").json()
    assert {"ts", "districts", "bands", "geojson"} <= set(b)
    assert b["geojson"] == "/ncr.geojson"
    assert len(b["bands"]) == 6
    rows = b["districts"]
    assert len(rows) == 13
    names = {r["name"] for r in rows}
    assert {"Delhi NCT", "Ghaziabad", "Gautam Buddha Nagar", "Gurugram",
            "Faridabad", "Sonipat", "Jhajjar", "Nuh", "Palwal", "Meerut",
            "Baghpat", "Hapur", "Bulandshahr"} == names
    for r in rows:
        assert r["confidence"] in ("field", "sparse", "none")
        if r["confidence"] == "none":
            assert r["aqi"] is None and r["pm25"] is None
            assert r["category"] == "No data"
        else:
            assert r["aqi"] is not None and r["pm25"] is not None
            assert r["category"] in {c for _, _, c, _ in
                                   districts.CPCB_BANDS}
            assert r["color"].startswith("#")
            # category must follow the CPCB band of its own aqi
            cat = next(c for lo, hi, c, _ in districts.CPCB_BANDS
                       if r["aqi"] <= hi)
            assert r["category"] == cat


def test_districts_never_zero_fills():
    """A district with no covered cells and a dead centroid must keep
    pm25 None — a 0 would silently read 'Good' on the choropleth."""
    FIELD._samples = []          # empty field: nothing is readable
    b = client.get("/v2/districts").json()
    for r in b["districts"]:
        assert r["pm25"] in (None, 0.0) or r["pm25"] is None
        assert r["confidence"] in ("sparse", "none")
        if r["pm25"] is None:
            assert r["aqi"] is None


def test_geojson_serves_and_centroids_are_inside():
    r = client.get("/ncr.geojson")
    assert r.status_code == 200
    fc = r.json()
    assert fc["type"] == "FeatureCollection"
    assert len(fc["features"]) == 13
    # baked centroid sits inside its own outer ring (the sparse read
    # must land inside the district it represents)
    for ft in fc["features"]:
        rings = districts._rings(ft["geometry"])
        cx, cy = ft["properties"]["centroid"]
        assert any(districts._point_in_ring(cx, cy, ring)
                   for ring in rings), ft["properties"]["name"]


def test_centroid_fallback_fires_on_small_coverage(monkeypatch):
    """Force every covered count under 3 — each district must then read
    its baked centroid, not a fabricated mean."""
    import districts as _d
    rows = [{"name": "X", "state": "T", "cells_covered": 2,
             "pm25": 40.0, "_centroid": [77.2, 28.6], "_sparse": True}]
    out = _d.finalize(rows, lambda la, lo: 222.0)
    assert out[0]["pm25"] == 222.0
    assert out[0]["confidence"] == "sparse"
    assert out[0]["centroid_read"] is True

    rows[0]["_sparse"] = True
    rows[0]["_centroid"] = [77.2, 28.6]
    rows[0]["pm25"] = None
    out = _d.finalize(rows, lambda la, lo: None)
    assert out[0]["pm25"] is None
    assert out[0]["confidence"] == "none"
    assert out[0]["aqi"] is None
