"""Offline tests for /v2/plan production paths: ranking edge cases,
vehicle/vehicle_profile parsing, unified emissions, geometry+steps,
and the transit_v2 → station-model metro degradation ladder.

No network: deps.osrm_route is monkeypatched, the Amazon client is a
local fake, transit_v2.plan_transit is stubbed per test.
"""
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
from v2 import plan as v2plan  # noqa: E402
import transit  # noqa: E402
import transit_v2  # noqa: E402
import emissions  # noqa: E402

client = TestClient(main.app)

LINE = {"type": "LineString",
        "coordinates": [[77.2090, 28.6139], [77.2150, 28.6300],
                        [77.1990, 28.6450]]}
CP = (28.6315, 77.2167)
KB = (28.6519, 77.1907)

OSRM_ROUTE = {
    "distance": 6200.0, "duration": 780.0, "geometry": LINE,
    "legs": [{"steps": [
        {"maneuver": {"type": "depart", "modifier": "north",
                      "location": [77.2090, 28.6139]},
         "name": "Rajpath", "distance": 3000.0, "duration": 400.0},
        {"maneuver": {"type": "turn", "modifier": "left",
                      "location": [77.2150, 28.6300]},
         "name": "KG Marg", "distance": 3200.0, "duration": 380.0},
        {"maneuver": {"type": "arrive", "location": [77.1990, 28.6450]},
         "name": "", "distance": 0.0, "duration": 0.0},
    ]}],
}


async def fake_osrm(profile, flon, flat, tlon, tlat):
    rt = dict(OSRM_ROUTE)
    rt["steps"] = deps.osrm_steps(rt)
    return rt


class DisabledLoc:
    enabled = False


@pytest.fixture(autouse=True)
def wired(monkeypatch):
    deps.set_location(DisabledLoc())
    FIELD._samples = [
        (28.6315, 77.2167, "test-station", {"pm2_5": 150.0}),
        (28.6519, 77.1907, None, {"pm2_5": 185.0}),
        (28.5850, 77.2300, None, {"pm2_5": 120.0}),
        (28.7000, 77.2000, None, {"pm2_5": 210.0}),
    ]
    FIELD._fetched_at = time.time()
    monkeypatch.setattr(deps, "field_refresh", _noop)
    monkeypatch.setattr(deps, "osrm_route", fake_osrm)
    monkeypatch.setattr(transit_v2, "plan_transit",
                        lambda *a, **k: [])
    store.ROUTES._routes.clear()
    yield
    deps.set_location(None)
    FIELD._samples = []


async def _noop():
    return None


def _post(body):
    r = client.post("/v2/plan", json=body)
    assert r.status_code == 200
    return r.json()


# --- ranking edge cases (pure) -------------------------------------------------
def _o(mode, dose_lo, co2_mid, eta_s):
    return {"mode": mode, "eta_s": eta_s,
            "dose": {"lo": dose_lo, "mid": dose_lo},
            "emissions": {"co2_kg": {"mid": co2_mid}}}


def test_rank_tie_boundary_10pct_is_inclusive():
    # dose_lo exactly at 1.10x the minimum is still tied — the spec's
    # 'within our own error' band is inclusive, not strict.
    opts = [_o("car", 100.0, 2.0, 600), _o("metro", 110.0, 0.5, 700)]
    out = v2plan.rank_options(opts)
    assert out[0]["mode"] == "metro"          # inside the tie → emission decides
    assert out[0]["recommended"] is True


def test_rank_tie_boundary_just_outside():
    opts = [_o("car", 100.0, 0.5, 600), _o("metro", 110.5, 0.1, 700)]
    out = v2plan.rank_options(opts)
    assert out[0]["mode"] == "car"            # 110.5 > 110 → not tied
    assert out[0]["recommended"] is True


def test_rank_time_guard_emits_plus_minutes():
    opts = [_o("car", 400.0, 3.0, 300), _o("metro", 90.0, 0.2, 481)]
    out = v2plan.rank_options(opts)
    assert out[0]["mode"] == "metro"
    assert "+3 min" in out[0]["reason_line"]   # 481-300 = 181 s ≈ 3 min


def test_rank_time_guard_boundary_not_flagged():
    # exactly 1.6x the fastest ETA is allowed silently ('>' is strict)
    opts = [_o("car", 400.0, 3.0, 300), _o("metro", 90.0, 0.2, 480)]
    out = v2plan.rank_options(opts)
    assert out[0]["mode"] == "metro"
    assert "min vs fastest" not in out[0]["reason_line"]


def test_rank_recommended_is_unique():
    opts = [_o("car", 100.0, 1.0, 600), _o("car_open", 102.0, 1.1, 600),
            _o("auto", 130.0, 0.4, 800), _o("metro", 95.0, 0.3, 700),
            _o("walk", 600.0, 0.0, 3600)]
    out = v2plan.rank_options(opts)
    rec = [o for o in out if o["recommended"]]
    assert len(rec) == 1
    assert out[0] is rec[0]


def test_rank_metro_vs_car_tie_metro_wins():
    # the realistic case: car and metro dose within error → Delhi's
    # tiebreak picks the rail option — which is also the global
    # emission min, so the spec tags it 'lightest on both' and leaves
    # the dose winner untagged (the you/Delhi pair is only for splits)
    opts = [_o("car", 100.0, 1.8, 900), _o("metro", 104.0, 0.3, 1200)]
    out = v2plan.rank_options(opts)
    assert out[0]["mode"] == "metro"
    assert out[0]["recommended"] is True
    assert out[0]["tag"] == "lightest on both"
    car = [o for o in out if o["mode"] == "car"][0]
    assert car["tag"] is None


def test_rank_split_tags_when_dose_and_emission_winners_differ():
    # dose winner isn't the emission winner → the spec's two tags split
    opts = [_o("car", 100.0, 2.0, 600),      # strict dose min, heavy
            _o("metro", 105.0, 0.3, 700),    # tied dose, lightest exhaust
            _o("walk", 500.0, 0.0, 3600)]    # global emin, heavy dose
    out = v2plan.rank_options(opts)
    by = {o["mode"]: o for o in out}
    assert by["metro"]["recommended"] is True   # min emission inside tie
    assert by["car"]["tag"] == "lightest for you"
    assert by["walk"]["tag"] == "lightest for Delhi"


def test_rank_no_scored_options_passes_through():
    opts = [{"mode": "x", "eta_s": 0, "dose": {"lo": None, "mid": None},
             "emissions": {"co2_kg": {"mid": None}}}]
    out = v2plan.rank_options(opts)
    assert out[0].get("recommended") in (None, False)


def test_rank_engine_row_keys_on_priced_objective():
    # engine row's raster band reads heavier than a router row's, but
    # its engine_dose_ug — the exact criterion the path minimized — is
    # lower → the engine row must win sort AND take the leaf chip
    eng = _o("car", 120.0, 2.0, 600); eng["engine_dose_ug"] = 90.0
    rtr = _o("car_open", 110.0, 0.5, 700)
    out = v2plan.rank_options([rtr, eng])
    assert out[0] is eng
    assert eng["safest_path"] is True


def test_rank_engine_dose_maps_into_lo_space():
    # the priced dose is mid-scale; ranking maps it by the row's own
    # band ratio so keys stay commensurate — ed=55 on a 4:5 band row
    # keys at 44, beating a 50-lo router row but losing to 40
    eng = {"mode": "car", "eta_s": 600,
           "dose": {"lo": 80.0, "mid": 100.0},
           "emissions": {"co2_kg": {"mid": 2.0}},
           "engine_dose_ug": 55.0}
    lo_rtr = _o("walk", 40.0, 0.0, 700)
    hi_rtr = _o("auto", 50.0, 1.0, 650)
    out = v2plan.rank_options([hi_rtr, lo_rtr, eng])
    assert out[0] is lo_rtr        # 40 < 44
    assert out[1] is eng           # 44 < 50


def test_rank_engine_row_without_band_keys_on_priced_dose():
    # band missing entirely → the raw priced dose still ranks: engine
    # row takes the dose flag even though it holds no raster lo/mid
    eng = {"mode": "car", "eta_s": 600,
           "dose": {"lo": None, "mid": None},
           "emissions": {"co2_kg": {"mid": 2.0}},
           "engine_dose_ug": 55.0}
    rtr = _o("walk", 60.0, 1.0, 700)
    v2plan.rank_options([rtr, eng])
    assert v2plan._dose_key(eng) == 55.0
    assert eng["safest_path"] is True


# --- vehicle / vehicle_profile parsing ------------------------------------------
def test_vehicle_questionnaire_values_all_parse():
    for v in ("car", "auto", "bike", "bus", "metro", "walk", "cycle"):
        canon, profile = v2plan._parse_vehicle({"vehicle": v})
        assert canon == v
    assert v2plan._parse_vehicle({"vehicle": "scooter"})[0] == "bike"
    assert v2plan._parse_vehicle({"vehicle": "cab"})[0] == "car"
    assert v2plan._parse_vehicle({"vehicle": "bicycle"})[0] == "cycle"


def test_vehicle_unknown_value_defaults_no_error():
    body = _post({"from": {"lat": CP[0], "lon": CP[1]},
                  "to": {"lat": KB[0], "lon": KB[1]},
                  "vehicle": "hoverboard"})
    assert body["vehicle"] == "car"        # fleet-prior default, never 4xx
    assert body["options"]


def test_vehicle_profile_parsing_and_applied_to_matching_option():
    body = _post({"from": {"lat": CP[0], "lon": CP[1]},
                  "to": {"lat": KB[0], "lon": KB[1]},
                  "vehicle": "car",
                  "vehicle_profile": {"class": "car", "fuel": "diesel",
                                      "year": 2015}})
    assert body["vehicle_profile"]["fuel"] == "diesel"
    assert body["vehicle_profile"]["year_bucket"] == "2010_2016"
    by_mode = {o["mode"]: o for o in body["options"]}
    car_label = (by_mode["car"]["emissions"].get("label") or "").lower()
    assert "diesel" in car_label                       # declared vehicle used
    bus_label = (by_mode["bus"]["emissions"].get("label") or "").lower()
    assert "diesel" not in bus_label                   # profile stays on-car


def test_vehicle_profile_year_bucket_passthrough_and_bad_values():
    canon, p = v2plan._parse_vehicle({
        "vehicle": "auto",
        "vehicle_profile": {"fuel": "cng", "year_bucket": "2020_plus"}})
    assert canon == "auto" and p["year_bucket"] == "2020_plus"
    canon, p = v2plan._parse_vehicle({
        "vehicle": "car",
        "vehicle_profile": {"fuel": "unobtainium", "year": "soon"}})
    assert "fuel" not in p and "year_bucket" not in p   # → fleet prior axes


def test_option_vehicle_profile_only_on_family_match():
    prof = {"class": "car", "fuel": "diesel"}
    assert v2plan._option_vehicle("car", prof)["fuel"] == "diesel"
    assert v2plan._option_vehicle("car_open", prof)["fuel"] == "diesel"
    assert "fuel" not in v2plan._option_vehicle("bus", prof)
    assert v2plan._option_vehicle("bus", prof) == {"class": "bus"}
    cab = {"class": "cab", "fuel": "cng"}
    assert v2plan._option_vehicle("car", cab)["class"] == "cab"  # taxi uplift


# --- unified emissions + geometry/steps -----------------------------------------
def test_plan_emissions_come_from_emissions_module():
    body = _post({"from": {"lat": CP[0], "lon": CP[1]},
                  "to": {"lat": KB[0], "lon": KB[1]}, "vehicle": "car"})
    for o in body["options"]:
        em = o["emissions"]
        assert em.get("engine") == "server/emissions.py"
        assert "fallback" not in (em.get("basis") or "")
        assert {"lo", "mid", "hi"} <= set(em["co2_kg"])
        # a real engine band, not a fake point value
        assert em["co2_kg"]["hi"] >= em["co2_kg"]["mid"] >= \
            em["co2_kg"]["lo"] >= 0


def test_option_emissions_match_trip_emissions_directly():
    # same inputs through the plan helper and the engine must agree —
    # the unified path is the point of this lane.
    via_plan = v2plan._emission_band("car", 6.2, 780.0, 640.0,
                                     {"class": "car"})
    direct = emissions.trip_emissions(mode="car", distance_km=6.2,
                                      duration_s=780.0, freeflow_s=640.0,
                                      vehicle={"class": "car"})
    assert via_plan["co2_kg"] == direct["co2_kg"]
    assert via_plan["pm25_g"] == direct["pm25_g"]


def test_every_option_carries_geometry_and_steps():
    body = _post({"from": {"lat": CP[0], "lon": CP[1]},
                  "to": {"lat": KB[0], "lon": KB[1]}, "vehicle": "car"})
    assert body["options"]
    for o in body["options"]:
        assert o["geometry"]["type"] == "LineString"
        assert o["route_geojson"] == o["geometry"]
        assert o["steps"], f"{o['mode']} has no turn list"
        for s in o["steps"]:
            assert s["instruction"] and s["distance_m"] is not None
            assert s["lat"] is not None and s["lon"] is not None
    # the upstream-router car must carry real turn-by-turn — the engine
    # option may rank above it (lower dose is the point) with honest
    # endpoint steps, so select by source, not position
    road = [o for o in body["options"]
            if o["mode"] == "car" and o["steps_source"] == "osrm"][0]
    assert any("Turn" in s["instruction"] or "Continue" in s["instruction"]
               for s in road["steps"])


def test_osrm_steps_normalizer():
    steps = deps.osrm_steps(OSRM_ROUTE)
    assert steps[0]["type"] == "depart"
    assert steps[0]["lat"] == pytest.approx(28.6139)
    assert steps[-1]["instruction"] == "You'll arrive"
    assert steps[1]["instruction"] == "Turn left onto KG Marg"


# --- transit (metro) degradation ladder -----------------------------------------
def _fake_journey():
    return [{
        "mode": "metro", "duration_s": 1500, "walk_m": 400,
        "transfers": 1, "lines": ["Yellow", "Blue"],
        "depart_at": "2026-10-05T08:01:00+05:30",
        "arrive_at": "2026-10-05T08:26:00+05:30",
        "duration_model": "gtfs", "source": "gtfs connection scan",
        "legs": [
            {"type": "walk",
             "from": {"name": "Start", "lat": CP[0], "lon": CP[1]},
             "to": {"name": "Rajiv Chowk", "lat": 28.6327, "lon": 77.2195},
             "distance_m": 300, "duration_s": 216,
             "geometry": {"type": "LineString", "coordinates": [
                 [CP[1], CP[0]], [77.2195, 28.6327]]}},
            {"type": "metro", "line": "Yellow",
             "from": {"name": "Rajiv Chowk", "lat": 28.6327,
                      "lon": 77.2195},
             "to": {"name": "Central Secretariat", "lat": 28.6159,
                    "lon": 77.2123},
             "stops": 1, "duration_s": 180, "wait_s": 240,
             "distance_m": 1900,
             "geometry": {"type": "LineString", "coordinates": [
                 [77.2195, 28.6327], [77.2123, 28.6159]]}},
            {"type": "metro", "line": "Blue",
             "from": {"name": "Central Secretariat", "lat": 28.6159,
                      "lon": 77.2123},
             "to": {"name": "Karol Bagh", "lat": 28.6440,
                    "lon": 77.1885},
             "stops": 3, "duration_s": 420, "wait_s": 180,
             "distance_m": 4200,
             "geometry": {"type": "LineString", "coordinates": [
                 [77.2123, 28.6159], [77.1885, 28.6440]]}},
            {"type": "walk",
             "from": {"name": "Karol Bagh", "lat": 28.6440,
                      "lon": 77.1885},
             "to": {"name": "Destination", "lat": KB[0], "lon": KB[1]},
             "distance_m": 100, "duration_s": 72,
             "geometry": {"type": "LineString", "coordinates": [
                 [77.1885, 28.6440], [KB[1], KB[0]]]}},
        ],
    }]


def test_metro_via_transit_v2_real_legs(monkeypatch):
    monkeypatch.setattr(transit_v2, "plan_transit",
                        lambda *a, **k: _fake_journey())
    body = _post({"from": {"lat": CP[0], "lon": CP[1]},
                  "to": {"lat": KB[0], "lon": KB[1]}, "vehicle": "car"})
    metro = [o for o in body["options"] if o["mode"] == "metro"]
    assert len(metro) == 1
    o = metro[0]
    assert o["eta_model"] == "gtfs"
    assert o["stations"]["board"] == "Rajiv Chowk"
    assert o["stations"]["alight"] == "Karol Bagh"
    assert o["lines"] == ["Yellow", "Blue"]
    # steps: walk → Yellow → Blue → walk, real station names
    ins = " | ".join(s["instruction"] for s in o["steps"])
    assert "Rajiv Chowk" in ins and "Yellow" in ins and "Blue" in ins
    assert o["steps"][-1]["type"] == "arrive"
    # merged geometry is one LineString
    assert o["geometry"]["type"] == "LineString"
    assert len(o["geometry"]["coordinates"]) >= 4
    # emissions: per-pax-km metro band on the ride distance, not the
    # whole door-to-door geometry
    assert o["emissions"]["engine"] == "server/emissions.py"
    assert o["emissions"]["co2_kg"]["hi"] > 0


def test_metro_fallback_station_model_when_no_gtfs(monkeypatch):
    # plan_transit empty (no feed cached) → transit.py station model,
    # honestly labelled, lower confidence — not a fabricated timetable.
    monkeypatch.setattr(transit_v2, "plan_transit",
                        lambda *a, **k: [])
    body = _post({"from": {"lat": CP[0], "lon": CP[1]},
                  "to": {"lat": KB[0], "lon": KB[1]}, "vehicle": "car"})
    metro = [o for o in body["options"] if o["mode"] == "metro"]
    assert len(metro) == 1
    o = metro[0]
    assert o["eta_model"] == "estimated"
    assert o.get("approximate") is True
    assert "approx" in o["label"].lower()
    assert o["dose"]["confidence"] == "low"
    assert o["steps"], "synthetic option must still carry a turn list"


def test_no_metro_option_when_not_credible(monkeypatch):
    monkeypatch.setattr(transit_v2, "plan_transit",
                        lambda *a, **k: [])
    monkeypatch.setattr(transit, "metro_option",
                        lambda *a, **k: None)
    body = _post({"from": {"lat": CP[0], "lon": CP[1]},
                  "to": {"lat": KB[0], "lon": KB[1]}, "vehicle": "car"})
    assert not any(o["mode"].startswith("metro") for o in body["options"])


# --- dose engine seam -------------------------------------------------------------
def test_integrate_dose_used_when_present(monkeypatch):
    calls = []

    def fake_integrate_dose(coords, field, me, ve):
        calls.append((len(coords), me, ve))
        return {"lo": 30.0, "mid": 42.0, "hi": 55.0}

    monkeypatch.setattr(v2plan, "_integrate_dose", fake_integrate_dose)
    body = _post({"from": {"lat": CP[0], "lon": CP[1]},
                  "to": {"lat": KB[0], "lon": KB[1]}, "vehicle": "car"})
    assert calls, "integrate_dose should be invoked for road options"
    car = [o for o in body["options"] if o["mode"] == "car"][0]
    assert car["dose"]["mid"] == 42.0
    assert car["dose"]["basis"] == "alive_core_ref.integrate_dose"


def test_integrate_dose_falls_back_on_error(monkeypatch):
    def boom(*a):
        raise RuntimeError("not ready")
    monkeypatch.setattr(v2plan, "_integrate_dose", boom)
    body = _post({"from": {"lat": CP[0], "lon": CP[1]},
                  "to": {"lat": KB[0], "lon": KB[1]}, "vehicle": "car"})
    car = [o for o in body["options"] if o["mode"] == "car"][0]
    assert car["dose"]["mid"] is not None    # exposure.dose took over


# --- service-area gate (the ECS wedge regression guard) -------------------------
def test_plan_rejects_out_of_area_before_any_fetch(monkeypatch):
    """SF→Delhi: the request that wedged the ECS task on E2E — public
    OSRM returns a 9,983 km / 94k-vertex 'route' and the dose loop over
    it starved the event loop past every health check. Must fail fast
    with a structured error without a single upstream call."""
    calls = []
    async def spy(*a, **k):
        calls.append(a)
        return None
    monkeypatch.setattr(deps, "osrm_route", spy)
    monkeypatch.setattr(deps, "field_refresh", spy)
    body = _post({"from": {"lat": 37.79, "lon": -122.41},
                  "to": {"lat": CP[0], "lon": CP[1]}, "vehicle": "auto"})
    assert body["options"] == []
    assert "outside service area" in body["error"]
    assert not calls, "out-of-area OD must never reach an upstream call"


def test_plan_edge_of_area_still_serves(monkeypatch):
    """Jaipur-side OD inside the 2° margin: gate must not over-reject."""
    calls = []
    async def spy(*a, **k):
        calls.append(a)
        return None
    monkeypatch.setattr(deps, "osrm_route", spy)
    body = _post({"from": {"lat": 26.90, "lon": 75.80},   # Jaipur
                  "to": {"lat": CP[0], "lon": CP[1]}, "vehicle": "auto"})
    assert "outside service area" not in (body.get("error") or "")
    assert calls, "in-area OD should reach the router"


# --- one dose surface per response ----------------------------------------------
class _FakeFV:
    def __init__(self, tag):
        self.tag = tag
    def value(self, lat, lon, pollutant="pm2_5"):
        return ("v", self.tag)
    def sigma(self, lat, lon):
        return ("s", self.tag)


def test_dose_surface_priced_raster_wins(monkeypatch):
    """When the engine priced edges this epoch, every row — engine,
    motor, transit — doses on that raster so the compare sheet ranks
    like-for-like (regression: 'least-smoke rd' losing to an OSRM row
    it beat because the arms priced on different estimators)."""
    fv = _FakeFV("eng")
    sig = lambda la, lo: ("sig", "eng")
    monkeypatch.setattr(v2plan, "_ENG_PACK", (fv, sig))
    F = object.__new__(FIELD.__class__)   # no _snap_fv
    dval, dsig = v2plan._dose_surface(F)
    assert dval == fv.value and dsig is sig


def test_dose_surface_snapshot_when_unpriced(monkeypatch):
    """Before any reprice, all rows share the field's own snapshot
    cells — the raster /grid paints — never krige-here-raster-there."""
    monkeypatch.setattr(v2plan, "_ENG_PACK", None)
    F = object.__new__(FIELD.__class__)
    F._snap_fv = _FakeFV("snap")
    dval, dsig = v2plan._dose_surface(F)
    assert dval == F._snap_fv.value and dsig == F._snap_fv.sigma


def test_dose_surface_none_means_live_estimator(monkeypatch):
    """No raster at all → (None, None) → callers use F.value/F.sigma —
    still one estimator for the whole response."""
    monkeypatch.setattr(v2plan, "_ENG_PACK", None)
    F = object.__new__(FIELD.__class__)
    F._snap_fv = None
    assert v2plan._dose_surface(F) == (None, None)


# --- engine-first paint ---------------------------------------------------------
def test_plan_fast_returns_engine_rows_only_without_router(monkeypatch):
    """fast:true is the engine-first paint: no public-router or GTFS call,
    only least-inhalation rows, flagged partial so the client swaps in
    the full set when it lands."""
    calls = []
    async def spy(*a, **k):
        calls.append(a)
        return None
    monkeypatch.setattr(deps, "osrm_route", spy)
    monkeypatch.setattr(deps, "field_refresh", spy)
    row = {"mode": "car", "label": "Car (AC) · least-smoke rd",
           "distance_km": 5.0, "duration_min": 14.0, "dose_ug": 9.0,
           "engine_dose_ug": 9.0, "geometry": None}
    seen = {}
    def eng(*a, **k):
        seen.update(k)
        return [dict(row)]
    monkeypatch.setattr(v2plan, "_engine_options", eng)
    monkeypatch.setattr(v2plan, "_transit_options",
                        lambda *a, **k: (_ for _ in ()).throw(AssertionError("transit ran")))
    body = _post({"from": {"lat": CP[0], "lon": CP[1]},
                  "to": {"lat": 28.5494, "lon": 77.2510},
                  "vehicle": "car", "fast": True})
    assert body["partial"] is True
    assert [o["mode"] for o in body["options"]] == ["car"]
    assert seen.get("alts") is False, "fast paint buys primaries only"
    assert not [c for c in calls if c and c[0] is not None and len(c) > 1], \
        "fast path must not wait on the public router"


def test_plan_fast_engine_down_is_typed_not_hung(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("graph missing")
    async def nop(*a, **k):
        return None
    monkeypatch.setattr(deps, "field_refresh", nop)
    monkeypatch.setattr(v2plan, "_engine_options", boom)
    body = _post({"from": {"lat": CP[0], "lon": CP[1]},
                  "to": {"lat": 28.5494, "lon": 77.2510}, "fast": True})
    assert body["options"] == [] and body["error"] == "engine unavailable"
