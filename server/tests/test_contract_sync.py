"""Contract sync — Bridge/contract.ts ↔ live /v2 (and v1) responses.

Parses the TypeScript interfaces out of Bridge/contract.ts (top-level
fields only, `?` = optional) and diffs them against what the server
actually emits on the wire, in both directions:

  * every REQUIRED contract field must exist in the live response
    (contract-ahead-of-wire drift — client would read undefined)
  * every live response key should be declared in the contract
    (wire-ahead-of-contract drift — undocumented surface)

The interface→endpoint mapping below is hand-maintained by design:
small, explicit, and each entry is reviewed when either side changes.
A fetcher key may carry an "@tag" suffix (e.g. "ReverseResponse@v2")
when two endpoints share one contract interface.

Offline: location client faked, main.http()/OSRM/AWS faked (a canned
OSRM route keeps /route /compare /decide /depart on their real option
paths), FIELD seeded, TRIPS seeded — every fetcher hits a deterministic
path.

Run from server/:
    .venv/bin/python -m pytest tests/test_contract_sync.py -v
"""
import math
import os
import re
import sys
import time
from datetime import datetime, timedelta, timezone

import httpx
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_REPO = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
CONTRACT_TS = os.path.join(_REPO, "Bridge", "contract.ts")

from fastapi.testclient import TestClient  # noqa: E402

import main  # noqa: E402
from airfield import FIELD  # noqa: E402
from forecast import FORECAST  # noqa: E402
from v2 import deps, store  # noqa: E402

client = TestClient(main.app, raise_server_exceptions=False)

CP = (28.6315, 77.2167)
LINE = {"type": "LineString",
        "coordinates": [[77.20 + i * 0.001, 28.63] for i in range(30)]}
OSRM_ROUTE = {"code": "Ok", "routes": [
    {"distance": 6200.0, "duration": 780.0, "geometry": LINE,
     "legs": []}]}


# --- contract.ts parser ---------------------------------------------------------
def parse_contract(path: str) -> dict:
    """{interface: {field_name: is_required}} — top-level fields only."""
    src = open(path, encoding="utf-8").read()
    src = re.sub(r"//[^\n]*", "", src)          # strip line comments
    src = re.sub(r"/\*.*?\*/", "", src, flags=re.S)  # and block comments
    out = {}
    for m in re.finditer(r"export interface (\w+)[^{]*\{", src):
        name, i, depth = m.group(1), m.end(), 1
        start = i
        while depth and i < len(src):
            depth += (src[i] == "{") - (src[i] == "}")
            i += 1
        body = src[start:i - 1]
        fields, d = {}, 1
        for line in body.split("\n"):
            fm = re.match(r"\s*(\w+)(\?)?\s*:", line)
            if d == 1 and fm:
                fields[fm.group(1)] = not fm.group(2)
            d += line.count("{") - line.count("}")
        out[name] = fields
    return out


CONTRACT = parse_contract(CONTRACT_TS)


# --- offline wiring ---------------------------------------------------------------
class FakeLoc:
    def __init__(self, enabled=True):
        self.enabled = enabled

    async def suggest(self, q, lat, lon, limit=8):
        return [{
            "id": "amz:X1", "place_id": "X1",
            "name": "Connaught Place", "subtitle": "New Delhi",
            "lat": 28.6315, "lon": 77.2167,
            "kind": "PointOfInterest", "distance_m": 210,
            "source": "amazon"}]

    async def get_place(self, place_id):
        return {"id": f"amz:{place_id}", "place_id": place_id,
                "name": "Select Citywalk", "subtitle": "Saket",
                "lat": 28.5285, "lon": 77.2185,
                "kind": "PointOfInterest", "source": "amazon"}

    async def reverse_geocode(self, lat, lon, limit=10):
        return [{"place_id": "r1", "street": "Rajpath",
                 "locality": "Central Secretariat",
                 "label": "Rajpath, Central Secretariat, New Delhi",
                 "lat": 28.6150, "lon": 77.2150, "distance_m": 40,
                 "kind": "Street", "source": "amazon"}]

    async def calculate_routes(self, flat, flon, tlat, tlon,
                               travel_mode="Car", alternatives=2,
                               depart_at=None):
        return [{"distance_m": 6200.0, "duration_s": 780.0,
                 "freeflow_s": 640.0, "geometry": LINE,
                 "notices": [], "source": "fake"}]


class _FakeResp:
    def __init__(self, payload):
        self._p = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._p


class FakeHttp:
    """main.http() stand-in: serves the canned OSRM route so /route,
    /compare, /decide and /depart exercise their real option paths,
    and fails everything else the way an offline night does."""

    async def get(self, url, params=None):
        if "router.project-osrm.org" in str(url):
            return _FakeResp(OSRM_ROUTE)
        raise httpx.ConnectError("offline contract test")


async def _fake_aws_suggest(q, lat, lon, limit=8):
    return [{"name": "Connaught Place", "subtitle": "New Delhi",
             "lat": 28.6315, "lon": 77.2167, "kind": "place",
             "outside_ncr": False}]


async def _fake_photon(q, lat, lon, limit=8, extra=None):
    return [{"name": "Palika Bazar", "subtitle": "Connaught Place",
             "lat": 28.6304, "lon": 77.2173, "kind": "retail",
             "outside_ncr": False}]


async def _fake_aws_reverse(lat, lon):
    return [(0, 0.04, "Rajpath", "Central Secretariat, New Delhi")]


def _seed_moves():
    """4 donated trips, 4 distinct devices, one decodable ll: cell →
    /v2/city/moves emits a real mode_share row + publishable corridor
    (k>=3 on both), and /v2/city's corridors list is non-empty."""
    for i in range(4):
        store.TRIPS.record_trip(
            ["ll:28.6315,77.2167"],
            {"mode": "car", "distance_km": 6.2, "dose_ug": 120.0 + i,
             "co2_kg_mid": 1.2, "pm25_g_mid": 0.03},
            token_hash=f"contractdev{i}")


def _seed_forecast():
    """Synthetic CAMS horizon starting today 00:00 UTC — /v2/day's
    fetcher reads real slots; refresh() short-circuits on the seeded TTL
    so no network is touched."""
    t0 = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0,
                                            microsecond=0)
    times = [(t0 + timedelta(hours=i)).isoformat() for i in range(120)]
    FORECAST._aq = [{"lat": CP[0], "lon": CP[1], "name": None, "t0": t0,
                     "times": times, "vars": {"pm2_5": [150.0] * 120}}]
    FORECAST._met = []
    FORECAST._fetched_at = time.time()


@pytest.fixture(autouse=True)
def wired(monkeypatch):
    deps.set_location(FakeLoc())
    FIELD._samples = [
        (28.6315, 77.2167, "test-station", {"pm2_5": 150.0}),
        (28.6519, 77.1907, None, {"pm2_5": 185.0}),
    ]
    FIELD._fetched_at = time.time()
    _seed_forecast()

    async def _noop(*a, **k):
        return None
    monkeypatch.setattr(deps, "field_refresh", _noop)
    monkeypatch.setattr(deps, "osrm_route", _noop)          # no routes
    monkeypatch.setattr(FIELD, "refresh", _noop)
    monkeypatch.setattr(main.FIRES, "refresh", _noop)
    # v1 surface: one canned OSRM route, deterministic AWS/Photon fakes —
    # the compare/decide/depart/search/reverse fetchers below then check
    # real option rows, not just the error path.
    monkeypatch.setattr(main, "http", lambda: FakeHttp())
    monkeypatch.setattr(main, "_aws_suggest", _fake_aws_suggest)
    monkeypatch.setattr(main, "_photon_search", _fake_photon)
    monkeypatch.setattr(main, "_aws_reverse", _fake_aws_reverse)
    store.TRIPS.reset()
    store.ROUTES._routes.clear()
    yield
    deps.set_location(None)
    FIELD._samples = []
    FORECAST._aq = []
    FORECAST._met = []
    FORECAST._fetched_at = 0.0


# --- live fetchers: interface name → response body ---------------------------------
# Keys are contract interface names; "Iface@tag" covers a second endpoint
# that emits the same interface (e.g. /v2/reverse → ReverseResponse).
def _seed_route():
    return store.ROUTES.put({"geometry": LINE, "mode": "car",
                             "duration_s": 600, "vehicle": "car"})


def _fetchers():
    return {
        # v1 (error/fallback paths still honor the contract's required set)
        "HealthResponse": lambda: client.get("/health").json(),
        "SearchResponse": lambda: client.get(
            "/search", params={"q": "connaught"}).json(),
        "TodayResponse": lambda: client.get(
            "/today", params={"lat": 28.6, "lon": 77.2}).json(),
        "AqiResponse": lambda: client.get(
            "/aqi", params={"lat": 28.6, "lon": 77.2}).json(),
        "GridResponse": lambda: client.get("/grid").json(),
        "ReverseResponse": lambda: client.get(
            "/reverse", params={"lat": 28.6, "lon": 77.2}).json(),
        # /v2/reverse emits the same shape (+lat/lon/distance_m/source)
        "ReverseResponse@v2": lambda: client.get(
            "/v2/reverse", params={"lat": CP[0], "lon": CP[1]}).json(),
        "RouteResponse": lambda: client.get("/route", params={
            "from_lat": 28.6, "from_lon": 77.2,
            "to_lat": 28.7, "to_lon": 77.3}).json(),
        "CompareResponse": lambda: client.get("/compare", params={
            "from_lat": 28.6, "from_lon": 77.2,
            "to_lat": 28.7, "to_lon": 77.3}).json(),
        "DecideResponse": lambda: client.get("/decide", params={
            "from_lat": 28.6, "from_lon": 77.2,
            "to_lat": 28.7, "to_lon": 77.3}).json(),
        "DepartResponse": lambda: client.get("/depart", params={
            "from_lat": 28.6, "from_lon": 77.2,
            "to_lat": 28.7, "to_lon": 77.3}).json(),
        # v2
        "V2SearchResponse": lambda: client.get("/v2/search", params={
            "q": "connaught", "lat": CP[0], "lon": CP[1]}).json(),
        "V2PlanResponse": lambda: client.post("/v2/plan", json={
            "from": {"lat": CP[0], "lon": CP[1]},
            "to": {"lat": 28.5708, "lon": 77.3260},
            "vehicle": "car"}).json(),
        "V2RerouteResponse": lambda: client.post(
            "/v2/reroute", json={}).json(),
        "V2TripResponse": lambda: client.post("/v2/trip", json={
            "device_token": "contract-tok",
            "summary": {"mode": "car", "distance_km": 3.0,
                    "duration_s": 480, "dose_ug": 40.0},
            "trajectory": LINE["coordinates"]}).json(),
        "V2LedgerResponse": lambda: client.get("/v2/ledger", params={
            "token": "contract-tok"}).json(),
        "V2StripResponse": lambda: client.get("/v2/strip", params={
            "route_id": _seed_route()}).json(),
        "V2CityResponse": lambda: (
            _seed_moves(), client.get("/v2/city").json())[1],
        "V2CityMovesResponse": lambda: (
            _seed_moves(), client.get("/v2/city/moves").json())[1],
        "V2Place": lambda: client.get("/v2/place/gaz:0").json(),
        "V2DistrictsResponse": lambda: client.get("/v2/districts").json(),
        "V2DayResponse": lambda: client.get("/v2/day", params={
            "lat": CP[0], "lon": CP[1]}).json(),
    }


# extra keys an interface inherits via `extends`/GeoJSON (not visible to
# the flat field parser) — required AND declared, both directions
EXTRA_DECLARED = {
    "GridResponse": {"type"},          # GeoJSON.FeatureCollection.type
}
EXTRA_REQUIRED = {
    "GridResponse": ["type"],          # GeoJSON.FeatureCollection
}
# response keys the contract knowingly does not model (allow-list)
ALLOW_UNCONTRACTED: dict = {}
# nested checks: (parent fetcher key, list-key, child interface)
NESTED = [
    ("V2SearchResponse", "results", "Place"),
    ("V2SearchResponse", "t1", "Place"),
    ("V2SearchResponse", "t2", "Place"),
    ("V2PlanResponse", "options", "V2PlanOption"),
    ("V2StripResponse", "samples", "V2StripSample"),
    ("V2StripResponse", "roads", "V2StripRoad"),
    ("V2LedgerResponse", "trips", "V2LedgerTrip"),
    ("SearchResponse", "results", "Place"),
    ("RouteResponse", "routes", "RouteResult"),
    ("CompareResponse", "options", "CompareOption"),
    ("DecideResponse", "options", "CompareOption"),
    ("DepartResponse", "options", "CompareOption"),
    ("V2RerouteResponse", "options", "V2PlanOption"),
    ("V2CityResponse", "corridors", "V2CityCorridor"),
    ("V2CityMovesResponse", "mode_share", "V2CityModeShare"),
    ("V2DistrictsResponse", "districts", "V2DistrictRow"),
    ("V2DayResponse", "hours", "V2DayHour"),
    ("V2DayResponse", "decisions", "V2DayDecision"),
]
# object-valued keys get the same two-direction check:
# (parent fetcher key, object-key, child interface | None)
# V2PlanOption.{dose,emissions} are checked per-row in
# test_nested_v2_option_and_band_shapes (V2PlanOption is a row type,
# not a fetcher key, so it can't sit here).
NESTED_OBJ = [
    ("V2TripResponse", "privacy", None),            # checked inline below
    ("V2PlanResponse", "field", "FieldStatus"),
    ("V2StripResponse", "field", "FieldStatus"),
    ("V2CityResponse", "field", "FieldStatus"),
    ("V2RerouteResponse", "field", "FieldStatus"),
    ("AqiResponse", "field", "FieldStatus"),
    ("CompareResponse", "field", "FieldStatus"),
    ("DecideResponse", "field", "FieldStatus"),
    ("RouteResponse", "field", "FieldStatus"),
    ("V2CityMovesResponse", "window", "V2MovesWindow"),
    ("V2CityMovesResponse", "corridors", "V2MovesCorridors"),
    ("V2CityMovesResponse", "per_trip", "V2MovesPerTrip"),
    ("V2DayResponse", "field", "FieldStatus"),
    ("V2DayResponse", "forecast", "V2ForecastStatus"),
    ("V2DayResponse", "heavy_window", "V2DayWindow"),
    ("V2DayResponse", "cleanest_window", "V2DayWindow"),
]


def _iface(key: str) -> str:
    """Fetcher key → contract interface ("ReverseResponse@v2" →
    "ReverseResponse")."""
    return key.split("@", 1)[0]


def _required(iface):
    return {f for f, req in CONTRACT[_iface(iface)].items() if req}


def _declared(iface):
    return set(CONTRACT[_iface(iface)]) | EXTRA_DECLARED.get(
        _iface(iface), set())


def _body(iface):
    """Fetch a response body; None when the endpoint is on a flaky /
    non-JSON path tonight (boto3 IMDS, upstream timeouts) — drift can
    only be judged on an actual object."""
    try:
        resp = _fetchers()[iface]()
    except Exception:  # noqa: BLE001
        return None
    return resp if isinstance(resp, dict) else None


# --- tests -------------------------------------------------------------------------
def test_contract_file_parses():
    assert CONTRACT, "no interfaces parsed from contract.ts"
    for name in ("Place", "SearchResponse", "V2SearchResponse",
                     "V2PlanResponse", "V2TripResponse", "V2StripResponse",
                     "V2CityResponse", "V2CityMovesResponse",
                     "V2RerouteResponse", "V2Place", "FieldStatus",
                     "DecideResponse", "V2MovesBand", "V2CityModeShare",
                     "V2MovesWindow", "V2MovesCorridors", "V2MovesPerTrip"):
        assert name in CONTRACT, f"{name} missing from contract.ts"


@pytest.mark.parametrize("iface", sorted(_fetchers()))
def test_required_contract_fields_on_the_wire(iface):
    """Contract-ahead-of-wire: a client reading a required field must
    never hit undefined."""
    body = _body(iface)
    if body is None:
        pytest.skip(f"{iface}: endpoint on a flaky/non-JSON path tonight")
    missing = _required(iface) - set(body)
    missing |= set(EXTRA_REQUIRED.get(iface, ())) - set(body)
    assert not missing, (
        f"{iface}: contract requires fields the server doesn't emit: "
        f"{sorted(missing)}")


@pytest.mark.parametrize("iface", sorted(_fetchers()))
def test_no_uncontracted_server_fields(iface):
    """Wire-ahead-of-contract: everything the server emits should be
    declared (allow-list only where intentional)."""
    body = _body(iface)
    if body is None:
        pytest.skip(f"{iface}: endpoint on a flaky/non-JSON path tonight")
    extra = set(body) - _declared(iface) - ALLOW_UNCONTRACTED.get(iface, set())
    assert not extra, (
        f"{iface}: server emits undeclared fields {sorted(extra)} — "
        f"add to contract.ts or the allow-list")


def test_nested_v2_option_and_band_shapes():
    body = _body("V2PlanResponse")
    assert body is not None
    opts = [o for o in body.get("options", []) if isinstance(o, dict)]
    assert opts, "no options to check against V2PlanOption"
    for o in opts:
        missing = _required("V2PlanOption") - set(o)
        assert not missing, f"option {o.get('mode')}: missing {missing}"
        extra = set(o) - _declared("V2PlanOption")
        assert not extra, f"option {o.get('mode')}: undeclared {extra}"
        for key, child in (("dose", "DoseBand"),
                           ("emissions", "EmissionBand")):
            sub = o.get(key) or {}
            miss = _required(child) - set(sub)
            assert not miss, f"{o.get('mode')}.{key}: missing {miss}"
            extra = set(sub) - _declared(child)
            assert not extra, (
                f"{o.get('mode')}.{key}: undeclared {extra} — "
                f"add to contract.ts")


def test_nested_place_and_strip_rows():
    for parent, key, child in NESTED:
        body = _body(parent)
        if body is None:
            continue
        rows = body.get(key) or []
        for row in rows:
            if not isinstance(row, dict):
                continue
            missing = _required(child) - set(row)
            assert not missing, (
                f"{parent}.{key} row missing contract fields {missing}")
            extra = set(row) - _declared(child)
            assert not extra, (
                f"{parent}.{key} row has undeclared fields {extra}")


def test_v2_trip_privacy_block_contract():
    body = _body("V2TripResponse")
    assert body is not None
    priv = body.get("privacy") or {}
    want = {"endpoint_trim_m", "thin_m", "rounded_decimals",
            "cell_scheme", "trimmed_start_m", "trimmed_end_m",
            "raw_trajectory"}
    assert want <= set(priv), f"privacy block missing {want - set(priv)}"


def test_nested_object_shapes():
    """Object-valued keys (field/window/corridors/…) honour the same
    two-direction rule as list rows — every required contract field on
    the wire, nothing undeclared emitted."""
    for parent, key, child in NESTED_OBJ:
        if child is None:
            continue  # dedicated test covers it (e.g. trip.privacy)
        body = _body(parent)
        if body is None:
            continue
        sub = body.get(key)
        if not isinstance(sub, dict):
            continue            # key absent/null on this path — honest
        missing = _required(child) - set(sub)
        assert not missing, (
            f"{parent}.{key}: contract requires {sorted(missing)} "
            f"the server doesn't emit")
        extra = set(sub) - _declared(child)
        assert not extra, (
            f"{parent}.{key}: server emits undeclared {sorted(extra)} "
            f"— add to contract.ts")


def test_field_status_serving_honesty_block():
    """FieldStatus must carry the serving-honesty keys wherever `field`
    ships: serving mode, field age, staleness verdict, source, and both
    sample/station counts — the FreshnessChip depends on all of them."""
    want = {"serving", "age_s", "stale", "source", "samples",
            "station_readings"}
    missing_contract = want - _declared("FieldStatus")
    assert not missing_contract, (
        f"FieldStatus contract missing {sorted(missing_contract)}")
    checked = 0
    for iface in ("AqiResponse", "V2CityResponse", "V2PlanResponse",
                  "V2StripResponse"):
        body = _body(iface)
        if body is None:
            continue
        f = body.get("field")
        if not isinstance(f, dict):
            continue
        checked += 1
        missing = want - set(f)
        assert not missing, f"{iface}.field: wire missing {missing}"
        assert f["serving"] in ("snapshot", "live", "none"), f
        assert f["stale"] in (True, False, None), f
        assert f["age_s"] is None or f["age_s"] >= 0, f
        assert isinstance(f["samples"], int), f
        assert isinstance(f["station_readings"], int), f
    assert checked, "no endpoint emitted a field block to check"


def test_aqi_pollutant_keys_on_wire():
    """/aqi's widened pollutant surface (o3/co/so2/nh3/european_aqi —
    realtime ingest) is declared in the contract AND actually emitted —
    values may be null, the keys may not be absent."""
    body = _body("AqiResponse")
    if body is None:
        pytest.skip("/aqi on a flaky path tonight")
    want = {"pm25", "pm10", "no2", "o3", "co", "so2", "nh3",
            "us_aqi", "european_aqi"}
    missing = want - set(body)
    assert not missing, f"/aqi not emitting {sorted(missing)}"
    undeclared = want - _declared("AqiResponse")
    assert not undeclared, f"contract missing {sorted(undeclared)}"


def test_v1_city_is_html_not_json():
    """/city (v1) serves the 'City Breathes' editorial page — text/html,
    deliberately outside the JSON contract (see ENDPOINTS note)."""
    r = client.get("/city")
    assert r.status_code == 200
    assert "text/html" in (r.headers.get("content-type") or "")


def test_v2_search_t2_rows_reachable():
    """BUG probe: with the fake location client enabled, t2 runs and
    returns a row — the response must expose the rows somewhere a
    client can read them (list, not just a status string)."""
    body = _body("V2SearchResponse")
    assert body is not None
    assert "t2" in body["tiers"], "t2 tier didn't run under FakeLoc"
    t2 = body.get("t2")
    rows = t2 if isinstance(t2, list) else body.get("t2_rows") or []
    assert rows and isinstance(rows[0], dict), (
        f"t2 rows unreachable: body['t2']={t2!r} — duplicate dict key "
        f"in server/v2/search.py shadows the row list")


def test_endpoint_constants_hit_real_routes():
    """Every path in ENDPOINTS + V2_ENDPOINTS resolves to a live route
    (no 404/405) — guards against a renamed or unmounted endpoint."""
    src = open(CONTRACT_TS, encoding="utf-8").read()
    paths = re.findall(r'"(/(?:v2/)?[a-z_]+(?:\{[^}]*\}|/[a-z_]+)?)"\s*,', src)
    assert "/v2/plan" in paths and "/health" in paths
    for p in set(paths):
        if "{" in p:
            p = p.split("{")[0] + "gaz:0"      # /v2/place/{id}
        if p == "/v2/place":
            p = "/v2/place/gaz:0"
        if p in ("/v2/trip", "/v2/plan", "/v2/reroute"):
            r = client.post(p, json={})
        else:
            r = client.get(p)
        assert r.status_code != 404, f"contract path {p} → 404"
        assert r.status_code != 405, f"contract path {p} → 405"


def test_drift_summary_print(capsys):
    """Human-readable drift table — always passes, feeds test-report."""
    rows = []
    for iface in sorted(_fetchers()):
        body = _body(iface)
        if body is None:
            rows.append((iface, "no-object-response", "", ""))
            continue
        missing = sorted(_required(iface) - set(body))
        opt_missing = sorted(f for f, req in CONTRACT[_iface(iface)].items()
                             if not req and f not in body)
        extra = sorted(set(body) - _declared(iface))
        rows.append((iface, ",".join(missing) or "-",
                     ",".join(opt_missing) or "-",
                     ",".join(extra) or "-"))
    print("\n\n=== contract drift table ===")
    print(f"{'interface':<22} {'missing-required':<22} "
          f"{'optional-not-emitted':<30} {'undeclared-emitted'}")
    for r in rows:
        print(f"{r[0]:<22} {r[1]:<22} {r[2]:<30} {r[3]}")


def test_us_aqi_grid_is_pm25_projection():
    """param=us_aqi serves the same cells as pm2_5, each projected
    through the EPA breakpoints — one story across the toggles, conf
    inherited. (The model-native index read ~3× our station field.)"""
    import districts
    pm = client.get("/grid", params={"param": "pm2_5", "cells": 8}).json()
    aq = client.get("/grid", params={"param": "us_aqi", "cells": 8}).json()
    assert len(aq["features"]) == len(pm["features"]) > 0
    for fa, fp in zip(aq["features"], pm["features"]):
        pa, pp = fa["properties"], fp["properties"]
        assert pa["param"] == "us_aqi"
        assert pa["derived"]
        assert fa["geometry"] == fp["geometry"]
        assert pa["us_aqi"] == districts.us_aqi(pp["pm25"])
        assert pa["conf"] == pp["conf"]


def test_non_finite_coords_never_500():
    """nan/inf coords are client errors, not crashes — every lat/lon
    endpoint answers honestly (error envelope or 422), never 500."""
    cases = [
        # NaN isn't valid JSON but Python json.loads accepts the literal —
        # raw bytes because a strict client serializer refuses it too
        ("/v2/plan", {"method": "post",
                      "content": b'{"from":{"lat":NaN,"lon":77.2},'
                                 b'"to":{"lat":28.4,"lon":77.0}}',
                      "headers": {"content-type": "application/json"}}),
        ("/aqi", {"params": {"lat": "inf", "lon": 77.2}}),
        ("/today", {"params": {"lat": "nan", "lon": 77.2}}),
        ("/escape", {"params": {"lat": "nan", "lon": 77.2}}),
        ("/shift", {"params": {"lat": "inf", "lon": 77.2}}),
        ("/v2/reverse", {"params": {"lat": "nan", "lon": 77.2}}),
    ]
    for path, kw in cases:
        r = getattr(client, kw.pop("method", "get"))(path, **kw)
        assert r.status_code != 500, f"{path} 500ed on non-finite coord"
        if path == "/v2/plan":
            body = r.json()
            assert body["options"] == []
            assert "non-finite" in body["error"]
        elif path == "/aqi":
            assert r.json()["error"]
        else:
            assert r.status_code == 422


def test_malformed_values_never_500():
    """Bad types/bounds in non-coord params must also fail honestly."""
    r = client.post("/v2/feedback", json={"stars": 3, "note": {"a": 1}})
    assert r.status_code == 422 and "note" in r.json()["detail"]
    r = client.post("/v2/feedback", json={"stars": 3, "build": {"a": 1}})
    assert r.status_code == 422 and "build" in r.json()["detail"]
    assert client.get("/grid", params={"cells": 0}).status_code == 422
    assert client.get("/grid", params={"cells": 999}).status_code == 422
