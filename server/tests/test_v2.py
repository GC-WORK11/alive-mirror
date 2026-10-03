"""Offline tests for the /v2 API — TestClient, location client faked.

No network: deps.osrm_route is monkeypatched, the Amazon client is a
local fake, deps.field_refresh is a no-op over an injected field.
Run from server/:
    .venv/bin/python -m pytest tests/test_v2.py -v
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
from v2 import deps, store  # noqa: E402
from v2 import plan as v2plan  # noqa: E402
from v2 import search as v2search  # noqa: E402
from v2 import trip as v2trip  # noqa: E402
import location_client  # noqa: E402

client = TestClient(main.app)

LINE = {"type": "LineString",
        "coordinates": [[77.2090, 28.6139], [77.2150, 28.6300],
                        [77.1990, 28.6450]]}
CP = (28.6315, 77.2167)
KB = (28.6519, 77.1907)


class FakeLoc:
    """Same method surface as location_client.LocationClient."""
    def __init__(self, enabled=True):
        self.enabled = enabled

    async def suggest(self, q, lat, lon, limit=8):
        return [{
            "id": "amz:X1", "place_id": "X1",
            "name": "Connaught Place", "subtitle": "New Delhi",
            "lat": 28.6315, "lon": 77.2167,
            "kind": "PointOfInterest", "distance_m": 210,
            "source": "amazon",
        }, {
            "id": "amz:X2", "place_id": "X2",
            "name": "Connaught Circus Plaza", "subtitle": "New Delhi",
            "lat": 28.6330, "lon": 77.2200,
            "kind": "PointOfInterest", "distance_m": 380,
            "source": "amazon",
        }]

    async def get_place(self, place_id):
        return {"id": f"amz:{place_id}", "place_id": place_id,
                "name": "Select Citywalk", "subtitle": "Saket, New Delhi",
                "lat": 28.5285, "lon": 77.2185, "kind": "PointOfInterest",
                "source": "amazon"}

    async def reverse_geocode(self, lat, lon, limit=10):
        return [{"place_id": "r1", "street": "Rajpath",
                 "locality": "Central Secretariat",
                 "label": "Rajpath, Central Secretariat, New Delhi",
                 "lat": 28.6150, "lon": 77.2150, "distance_m": 40,
                 "kind": "Street", "source": "amazon"}]

    async def calculate_routes(self, from_lat, from_lon, to_lat, to_lon,
                               travel_mode="Car", alternatives=2,
                               depart_at=None):
        return [{"distance_m": 6200.0, "duration_s": 780.0,
                 "freeflow_s": 640.0, "geometry": LINE,
                 "notices": [], "source": "amazon-location-routes"}]


@pytest.fixture(autouse=True)
def wired(monkeypatch):
    """Injected field + fake location client + no-op refresh."""
    deps.set_location(FakeLoc())
    FIELD._samples = [
        (28.6315, 77.2167, "test-station", {"pm2_5": 150.0}),
        (28.6519, 77.1907, None, {"pm2_5": 185.0}),
        (28.5850, 77.2300, None, {"pm2_5": 120.0}),
        (28.7000, 77.2000, None, {"pm2_5": 210.0}),
    ]
    FIELD._fetched_at = time.time()

    async def _no_refresh():
        return None
    monkeypatch.setattr(deps, "field_refresh", _no_refresh)
    store.TRIPS.reset()
    store.ROUTES._routes.clear()
    yield
    deps.set_location(None)
    FIELD._samples = []


# --- search -------------------------------------------------------------------
def test_search_tiers_and_took_ms():
    r = client.get("/v2/search", params={"q": "connaught",
                                         "lat": CP[0], "lon": CP[1]})
    assert r.status_code == 200
    body = r.json()
    assert body["tiers"] == ["t1", "t2"]
    assert body["t1_engine"] in ("alive_core", "alive_core_ref", "gazetteer")
    assert isinstance(body["took_ms"]["t1"], (int, float))
    assert isinstance(body["took_ms"]["t2"], (int, float))
    assert isinstance(body["took_ms"]["total"], (int, float))
    assert body["results"], "expected merged results"
    for res in body["results"]:
        assert res["name"] and res["lat"] and res["lon"]
        assert res["match"] in ("exact-prefix", "token-prefix", "fuzzy",
                                "other")
    srcs = [s for res in body["results"] for s in res["sources"]]
    assert "t1" in srcs and "t2" in srcs


def test_search_t2_disabled_by_design():
    deps.set_location(FakeLoc(enabled=False))
    r = client.get("/v2/search", params={"q": "connaught",
                                         "lat": CP[0], "lon": CP[1]})
    assert r.status_code == 200
    body = r.json()
    assert body["tiers"] == ["t1"]
    assert body["took_ms"]["t2"] is None
    assert "disabled" in body["t2"]


def test_merge_dedupes_name_within_75m():
    t1 = [{"name": "Connaught Place", "lat": 28.6315, "lon": 77.2167,
           "match_rank": 0, "sources": ["t1"], "distance_m": 100}]
    t2 = [{"name": "connaught place", "lat": 28.6316, "lon": 77.2168,
           "match_rank": 1, "sources": ["t2"], "distance_m": 110},
          {"name": "Palika Bazaar", "lat": 28.6320, "lon": 77.2180,
           "match_rank": 1, "sources": ["t2"], "distance_m": 120}]
    out = v2search._merge(t1, t2, "connaught place", *CP)
    assert len(out) == 2
    assert sorted(out[0]["sources"]) == ["t1", "t2"]


# --- place / reverse ----------------------------------------------------------
def test_place_gazetteer_and_amazon():
    r = client.get("/v2/place/gaz:0")
    assert r.status_code == 200 and r.json()["name"]
    r = client.get("/v2/place/amz:X9")
    assert r.status_code == 200
    assert r.json()["name"] == "Select Citywalk"


def test_place_and_reverse_503_without_key():
    deps.set_location(FakeLoc(enabled=False))
    assert client.get("/v2/place/amz:X9").status_code == 503
    assert client.get("/v2/reverse",
                      params={"lat": 28.61, "lon": 77.21}).status_code == 503


def test_reverse_names_street_level():
    r = client.get("/v2/reverse", params={"lat": 28.615, "lon": 77.215})
    assert r.status_code == 200
    assert "Rajpath" in r.json()["name"]


# --- plan ---------------------------------------------------------------------
def test_plan_options_shape_and_tags():
    r = client.post("/v2/plan", json={
        "from": {"lat": CP[0], "lon": CP[1]},
        "to": {"lat": KB[0], "lon": KB[1]},
        "vehicle": "car"})
    assert r.status_code == 200
    body = r.json()
    assert body["options"], "expected at least one option"
    for o in body["options"]:
        assert o["mode"] and o["route_geojson"]["type"] == "LineString"
        assert isinstance(o["eta_s"], (int, float)) and o["eta_s"] > 0
        assert "lo" in o["dose"] and "mid" in o["dose"] and "hi" in o["dose"]
        co2, pm = o["emissions"]["co2_kg"], o["emissions"]["pm25_g"]
        assert {"lo", "mid", "hi"} <= set(co2)
        assert {"lo", "mid", "hi"} <= set(pm)
        assert o["route_id"]
        assert isinstance(o["reason_line"], str)
    tags = {o["tag"] for o in body["options"] if o["tag"]}
    assert tags <= {"lightest on both", "lightest for you",
                    "lightest for Delhi"}
    recommended = [o for o in body["options"] if o["recommended"]]
    assert len(recommended) == 1
    assert body["options"][0] is recommended[0]
    if "lightest on both" not in tags:
        assert {"lightest for you", "lightest for Delhi"} <= tags


def test_plan_osrm_fallback_when_no_key(monkeypatch):
    deps.set_location(FakeLoc(enabled=False))
    calls = []

    async def fake_osrm(profile, flon, flat, tlon, tlat):
        calls.append(profile)
        return {"distance": 6200.0, "duration": 780.0, "geometry": LINE}
    monkeypatch.setattr(deps, "osrm_route", fake_osrm)
    r = client.post("/v2/plan", json={
        "from": {"lat": CP[0], "lon": CP[1]},
        "to": {"lat": KB[0], "lon": KB[1]}, "vehicle": "auto"})
    assert r.status_code == 200
    body = r.json()
    assert body["options"]
    assert "driving" in calls
    modes = {o["mode"] for o in body["options"]}
    assert "car" in modes and "auto" in modes
    assert all(o["eta_model"].startswith(("osrm", "estimated", "gtfs"))
               for o in body["options"])


def test_rank_tie_break_min_emission_wins():
    opts = [
        {"mode": "a", "eta_s": 600, "dose": {"lo": 100, "mid": 110},
         "emissions": {"co2_kg": {"mid": 2.0}}},
        {"mode": "b", "eta_s": 700, "dose": {"lo": 105, "mid": 115},
         "emissions": {"co2_kg": {"mid": 0.5}}},   # tied dose, lighter
        {"mode": "c", "eta_s": 300, "dose": {"lo": 500, "mid": 500},
         "emissions": {"co2_kg": {"mid": 0.1}}},  # global emin, heavy dose
    ]
    out = v2plan.rank_options(opts)
    assert out[0]["mode"] == "b" and out[0]["recommended"]
    assert out[0]["tag"] == "lightest on both" or out[0]["tag"] is None
    by_mode = {o["mode"]: o for o in out}
    assert by_mode["a"]["tag"] == "lightest for you"
    assert by_mode["c"]["tag"] == "lightest for Delhi"


def test_rank_lightest_on_both():
    opts = [
        {"mode": "x", "eta_s": 600, "dose": {"lo": 100, "mid": 100},
         "emissions": {"co2_kg": {"mid": 0.4}}},
        {"mode": "y", "eta_s": 500, "dose": {"lo": 104, "mid": 104},
         "emissions": {"co2_kg": {"mid": 0.1}}},  # tied + lowest emission
    ]
    out = v2plan.rank_options(opts)
    assert out[0]["mode"] == "y"
    assert out[0]["tag"] == "lightest on both"


def test_rank_time_guard_says_plus_minutes():
    opts = [
        {"mode": "fast", "eta_s": 300, "dose": {"lo": 400, "mid": 400},
         "emissions": {"co2_kg": {"mid": 3.0}}},
        {"mode": "slow-win", "eta_s": 1200, "dose": {"lo": 90, "mid": 90},
         "emissions": {"co2_kg": {"mid": 0.2}}},
    ]
    out = v2plan.rank_options(opts)
    win = out[0]
    assert win["mode"] == "slow-win"
    assert "+15 min" in win["reason_line"]


# --- trip privacy -------------------------------------------------------------
def _line_traj(n=25, step_deg=0.0011):
    # ~2.6 km heading east from CP (~107 m steps) — 4-decimal coords
    # like a phone sends
    return [[77.20 + i * step_deg, 28.63] for i in range(n)]


def test_trip_privacy_pipeline():
    traj = _line_traj()
    r = client.post("/v2/trip", json={
        "device_token": "device-under-test-1",
        "summary": {"mode": "car", "distance_km": 2.4,
                    "duration_s": 480, "dose_ug": 60.5},
        "trajectory": traj})
    assert r.status_code == 200
    body = r.json()
    assert body["stored"]
    # ~2.6km minus 300m at each end ≈ 2km, thinned to ~100m → ~19 pts
    assert 8 <= body["points_used"] <= 22
    assert body["privacy"]["trimmed_start_m"] >= 290
    assert body["privacy"]["trimmed_end_m"] >= 290

    # raw coordinates and the token must exist NOWHERE in the store
    snap = store.TRIPS.snapshot_cells()
    assert snap, "expected at least one cell"
    for key, cell in snap.items():
        assert "28." not in key and "77." not in key  # no raw lat/lon
        assert set(cell) == {"count", "dose_sum", "devices"}
    assert "device-under-test-1" not in repr(store.TRIPS.snapshot_cells())
    days = store.TRIPS.city_aggregates()["days"]
    today = time.strftime("%Y-%m-%d", time.gmtime())
    assert days[today]["trips"] == 1
    assert days[today]["modes"] == {"car": 1}


def test_trip_pipeline_unit_endpoints_dropped():
    kept, ta, tb = v2trip.privacy_pipeline(_line_traj())
    first_lat, first_lon = kept[0]
    # nearest kept point is >= ~300 m along-path from the raw start
    d_start = v2trip._hav_m(28.63, 77.20, first_lat, first_lon)
    assert d_start >= 250  # 300 m ± thinning granularity
    for la, lo in kept:
        assert abs(la - round(la, 4)) < 1e-9
        assert abs(lo - round(lo, 4)) < 1e-9


# --- strip --------------------------------------------------------------------
def test_strip_samples_stored_route():
    rid = store.ROUTES.put({"geometry": LINE, "mode": "car",
                            "duration_s": 600, "vehicle": "car"})
    r = client.get("/v2/strip", params={"route_id": rid})
    assert r.status_code == 200
    body = r.json()
    assert body["step_m"] == 250.0 and body["samples"]
    s0 = body["samples"][0]
    assert {"lat", "lon", "pm25"} <= set(s0)
    assert body["emissions_curve"]["co2_g_km"]["hi"] > 0
    assert client.get("/v2/strip",
                      params={"route_id": "nope"}).status_code == 404


# --- city + health -------------------------------------------------------------
def test_city_summary():
    r = client.get("/v2/city")
    assert r.status_code == 200
    body = r.json()
    assert body["sources"]["model"]["up"] is True
    assert {"model", "stations", "fires", "location"} <= set(body["sources"])
    assert body["pm25_stats"]["mean"] > 0
    assert "trips" in body


def test_health_fields():
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True and body["version"] == "v2"
    assert isinstance(body["build_sha"], str) and body["build_sha"]
    assert "field_age_s" in body
    assert {"model", "stations", "fires", "location"} <= set(body["sources"])
    assert body["sources"]["location"]["up"] is True  # fake is enabled
    assert body["history"]  # pre-existing field kept


# --- location client itself ----------------------------------------------------
def test_location_client_disabled_without_key():
    import asyncio
    c = location_client.LocationClient(api_key="")
    assert c.enabled is False
    with pytest.raises(location_client.LocationDisabled):
        asyncio.run(c.suggest("x", 28.6, 77.2))
