"""Offline tests for /v2/strip — the emission curve must decompose
from server/emissions.py so strip and plan agree by construction,
and the response must report ages honestly.
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
from v2 import strip as v2strip  # noqa: E402
import emissions  # noqa: E402

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
    yield
    FIELD._samples = []


# --- curve derivation ----------------------------------------------------------
def test_curve_comes_from_emission_factors():
    veh = {"class": "car", "fuel": "petrol", "year_bucket": "2010_2016"}
    curve = v2strip._emission_curve("car", veh)
    ef = emissions.emission_factors(veh)
    assert curve["engine"] == "server/emissions.py"
    assert curve["co2_g_km"] == ef["co2"]
    assert curve["pm25_g_km"] == ef["pm25"]
    assert curve["bs_class"] == "bs4"
    assert curve["cold_start_km"] == pytest.approx(emissions.COLD_KM)
    assert curve["cold_mult_co2"] == pytest.approx(
        emissions._COLD_MULT["petrol"]["co2"])
    assert "petrol car" in (curve["label"] or "")
    assert "server/emissions.py" in curve["basis"]


def test_curve_idle_g_s_matches_engine():
    veh = {"class": "car", "fuel": "petrol"}
    curve = v2strip._emission_curve("car", veh)
    idle = emissions.integrate(
        veh, [{"dist_m": 0.0, "speed_mps": 0.0,
               "moving": False, "dur_s": 1.0}])
    assert curve["idle_g_s"] == pytest.approx(
        idle["co2_kg"]["mid"] * 1000.0)
    assert curve["idle"]["co2_g_s"]["hi"] > 0


def test_curve_trip_total_parity_with_trip_emissions():
    """Client-math on the flat curve must reproduce the engine's total
    for the same trip (within rounding): warm ef x km + cold uplift on
    the first COLD_KM + idle x seconds."""
    veh = {"class": "car", "fuel": "petrol", "year_bucket": "2010_2016"}
    curve = v2strip._emission_curve("car", veh)
    km, move_s, idle_s = 10.0, 1200.0, 300.0   # 30 km/h == REF_SPEED

    # engine truth
    trip = emissions.trip_emissions(mode="car", distance_km=km,
                                    duration_s=move_s + idle_s,
                                    freeflow_s=move_s, vehicle=veh)
    # what the client computes from the flat curve: ef mid x km with
    # the cold multiplier averaged over the first cold_start_km
    cold_len = min(km, curve["cold_start_km"])
    cold_avg = 1.0 + (curve["cold_mult_co2"] - 1.0) * (
        1.0 - cold_len / 2.0 / curve["cold_start_km"])
    client_g = (curve["co2_g_km"]["mid"]
                * (km - cold_len + cold_len * cold_avg)
                + curve["idle_g_s"] * idle_s)
    assert client_g / 1000.0 == pytest.approx(
        trip["co2_kg"]["mid"], rel=0.02)


def test_curve_metro_is_per_pax_km():
    curve = v2strip._emission_curve("metro", {"class": "metro"})
    assert curve["co2_g_pkm"]["lo"] == pytest.approx(11.0)
    assert curve["co2_g_pkm"]["hi"] == pytest.approx(25.0)
    assert curve["pm25_g_pkm"]["hi"] == pytest.approx(0.0)
    assert "electricity" in (curve["label"] or "")


def test_curve_walk_cycle_zero():
    for mode in ("walk", "cycle"):
        curve = v2strip._emission_curve(mode, {"class": mode})
        assert curve["co2_g_km"]["hi"] == 0.0
        assert curve["idle_g_s"] == pytest.approx(0.0)


def test_curve_fallback_labelled(monkeypatch):
    monkeypatch.setattr(v2strip, "_emissions_mod", None)
    curve = v2strip._emission_curve("car", {"class": "car"})
    assert curve["engine"] == "static-table fallback"
    assert "fallback" in curve["basis"]
    assert curve["co2_g_km"]["hi"] > 0


# --- strip response ---------------------------------------------------------------
def test_strip_response_curve_and_age():
    rid = store.ROUTES.put({
        "geometry": LINE, "mode": "car", "duration_s": 600,
        "vehicle": "car",
        "emissions_vehicle": {"class": "car", "fuel": "diesel",
                              "year_bucket": "2010_2016"},
        "to": {"lat": 28.6450, "lon": 77.1990}})
    r = client.get("/v2/strip", params={"route_id": rid})
    assert r.status_code == 200
    body = r.json()
    assert body["route_age_s"] is not None and body["route_age_s"] >= 0
    assert "age_s" in body["field"]
    curve = body["emissions_curve"]
    assert curve["engine"] == "server/emissions.py"
    assert "diesel" in (curve["label"] or "")   # stored profile respected
    assert curve["co2_g_km"]["hi"] > 0
    assert body["samples"]


def test_strip_expired_route_404s():
    store.ROUTES._routes["old"] = (
        time.time() - 3700, {"geometry": LINE, "mode": "car"})
    r = client.get("/v2/strip", params={"route_id": "old"})
    assert r.status_code == 404
    assert "expire" in r.json()["detail"]
