"""Offline tests for POST /v2/reroute — replan from a live fix.

Contract (mobile lane): POST {route_id?, at:{lat,lon}, from?, to?,
mode?} → {route_id, geometry|route_geojson, eta_s|duration_s, ...} or
{option:{...}} — plus the full ranked option set. Every failure path
is an honest body, never a fabricated route.
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

client = TestClient(main.app)

LINE = {"type": "LineString",
        "coordinates": [[77.2090, 28.6139], [77.2150, 28.6300],
                        [77.1990, 28.6450]]}
DEST = {"lat": 28.6519, "lon": 77.1907}
FIX = {"lat": 28.6300, "lon": 77.2150}

OSRM_ROUTE = {"distance": 4200.0, "duration": 560.0, "geometry": LINE}


async def fake_osrm(profile, flon, flat, tlon, tlat):
    rt = dict(OSRM_ROUTE)
    rt["steps"] = deps.osrm_steps(rt)
    return rt


async def no_osrm(profile, flon, flat, tlon, tlat):
    return None


async def _noop():
    return None


class DisabledLoc:
    enabled = False


@pytest.fixture(autouse=True)
def wired(monkeypatch):
    deps.set_location(DisabledLoc())
    FIELD._samples = [
        (28.6315, 77.2167, "test-station", {"pm2_5": 150.0}),
        (28.6519, 77.1907, None, {"pm2_5": 185.0}),
    ]
    FIELD._fetched_at = time.time()
    monkeypatch.setattr(deps, "field_refresh", _noop)
    monkeypatch.setattr(deps, "osrm_route", fake_osrm)
    monkeypatch.setattr(transit_v2, "plan_transit", lambda *a, **k: [])
    monkeypatch.setattr(transit, "metro_option", lambda *a, **k: None)
    store.ROUTES._routes.clear()
    yield
    deps.set_location(None)
    FIELD._samples = []


def test_reroute_with_explicit_destination():
    r = client.post("/v2/reroute", json={
        "at": FIX, "to": DEST, "mode": "car"})
    assert r.status_code == 200
    body = r.json()
    assert body["route_id"]                       # fresh route_id issued
    assert body["geometry"]["type"] == "LineString"
    assert body["route_geojson"]["type"] == "LineString"
    assert body["eta_s"] > 0 and body["duration_s"] == body["eta_s"]
    assert body["mode"] == "car"
    assert body["option"]["mode"] == "car"        # `option` form also present
    assert body["options"]                        # full ranked set too
    assert body["option"]["route_id"] == body["route_id"]
    # the new route_id is real — strip can consume it
    rec = store.ROUTES.get(body["route_id"])
    assert rec is not None and rec["geometry"]["type"] == "LineString"


def test_reroute_uses_stored_destination():
    old = store.ROUTES.put({
        "geometry": LINE, "mode": "car", "duration_s": 600,
        "vehicle": "car", "to": DEST,
        "emissions_vehicle": {"class": "car", "fuel": "petrol"}})
    r = client.post("/v2/reroute", json={"route_id": old, "at": FIX})
    assert r.status_code == 200
    body = r.json()
    assert body["rerouted_from"] == old
    assert body["route_id"] and body["route_id"] != old
    assert body["to"] == DEST
    assert body["option"]["dose"]["mid"] is not None


def test_reroute_mode_hint_selects_matching_option():
    r = client.post("/v2/reroute", json={
        "at": FIX, "to": DEST, "mode": "walk"})
    body = r.json()
    assert body["mode"] == "walk"
    assert body["option"]["mode"] == "walk"


def test_reroute_missing_destination_is_honest():
    r = client.post("/v2/reroute", json={
        "route_id": "expired-or-unknown", "at": FIX})
    assert r.status_code == 200
    body = r.json()
    assert body["options"] == []
    assert "destination unknown" in body["error"]


def test_reroute_bad_fix_is_honest():
    r = client.post("/v2/reroute", json={"to": DEST})
    body = r.json()
    assert body["options"] == [] and "error" in body


def test_reroute_expired_route_id_does_not_resurrect():
    store.ROUTES._routes["stale"] = (
        time.time() - 3700,
        {"geometry": LINE, "mode": "car", "to": DEST})
    r = client.post("/v2/reroute", json={"route_id": "stale", "at": FIX})
    body = r.json()
    # expired → `to` unresolvable → honest error, no fabricated route
    assert "error" in body


def test_reroute_routing_failure_is_honest(monkeypatch):
    monkeypatch.setattr(deps, "osrm_route", no_osrm)
    monkeypatch.setattr(v2plan, "_engine", lambda: None)  # engine absent too
    r = client.post("/v2/reroute", json={"at": FIX, "to": DEST})
    body = r.json()
    assert body["route_id"] is None
    assert body["option"] is None
    assert "unavailable" in body["error"]


def test_reroute_engine_backstop(monkeypatch):
    """Upstream router dead but the least-inhalation engine alive: the
    reroute still lands an engine-sourced option — 'unavailable' only
    when truly nothing can route."""
    monkeypatch.setattr(deps, "osrm_route", no_osrm)
    if v2plan._engine() is None:
        pytest.skip("path engine/graph not shipped here")
    r = client.post("/v2/reroute", json={"at": FIX, "to": DEST})
    body = r.json()
    assert body["route_id"] is not None
    assert body["option"]["engine"] == "alive_core-path"


def test_reroute_depart_at_unparseable_flagged():
    """Same silent hole as /v2/plan — a garbage depart_at echoes verbatim
    and the transit arm falls back to the approx model with no signal.
    depart_at_parsed is the additive marker here too."""
    r = client.post("/v2/reroute", json={
        "at": FIX, "to": DEST, "mode": "car", "depart_at": "banana"})
    assert r.status_code == 200
    body = r.json()
    assert body["depart_at_parsed"] is False


def test_reroute_depart_at_parseable_marked_true():
    r = client.post("/v2/reroute", json={
        "at": FIX, "to": DEST, "mode": "car",
        "depart_at": "2026-10-07T08:30:00+05:30"})
    assert r.status_code == 200
    body = r.json()
    assert body["depart_at_parsed"] is True
