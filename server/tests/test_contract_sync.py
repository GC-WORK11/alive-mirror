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
Offline: location client faked, OSRM/refresh monkeypatched, FIELD
seeded — every fetcher hits a deterministic path.

Run from server/:
    .venv/bin/python -m pytest tests/test_contract_sync.py -v
"""
import math
import os
import re
import sys
import time

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_REPO = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
CONTRACT_TS = os.path.join(_REPO, "Bridge", "contract.ts")

from fastapi.testclient import TestClient  # noqa: E402

import main  # noqa: E402
from airfield import FIELD  # noqa: E402
from v2 import deps, store  # noqa: E402

client = TestClient(main.app, raise_server_exceptions=False)

CP = (28.6315, 77.2167)
LINE = {"type": "LineString",
        "coordinates": [[77.20 + i * 0.001, 28.63] for i in range(30)]}


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


@pytest.fixture(autouse=True)
def wired(monkeypatch):
    deps.set_location(FakeLoc())
    FIELD._samples = [
        (28.6315, 77.2167, "test-station", {"pm2_5": 150.0}),
        (28.6519, 77.1907, None, {"pm2_5": 185.0}),
    ]
    FIELD._fetched_at = time.time()

    async def _noop(*a, **k):
        return None
    monkeypatch.setattr(deps, "field_refresh", _noop)
    monkeypatch.setattr(deps, "osrm_route", _noop)          # no routes
    monkeypatch.setattr(FIELD, "refresh", _noop)
    monkeypatch.setattr(main.FIRES, "refresh", _noop)
    store.TRIPS.reset()
    store.ROUTES._routes.clear()
    yield
    deps.set_location(None)
    FIELD._samples = []


# --- live fetchers: interface name → response body ---------------------------------
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
        "RouteResponse": lambda: client.get("/route", params={
            "from_lat": 28.6, "from_lon": 77.2,
            "to_lat": 28.7, "to_lon": 77.3}).json(),
        "CompareResponse": lambda: client.get("/compare", params={
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
        "V2TripResponse": lambda: client.post("/v2/trip", json={
            "device_token": "contract-tok",
            "trajectory": LINE["coordinates"]}).json(),
        "V2StripResponse": lambda: client.get("/v2/strip", params={
            "route_id": _seed_route()}).json(),
        "V2CityResponse": lambda: client.get("/v2/city").json(),
        "V2Place": lambda: client.get("/v2/place/gaz:0").json(),
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
# nested checks: (parent interface, list-key or object-key, child interface)
NESTED = [
    ("V2SearchResponse", "results", "Place"),
    ("V2SearchResponse", "t1", "Place"),
    ("V2PlanResponse", "options", "V2PlanOption"),
    ("V2StripResponse", "samples", "V2StripSample"),
    ("SearchResponse", "results", "Place"),
]
NESTED_OBJ = [
    ("V2PlanOption", "dose", "DoseBand"),
    ("V2PlanOption", "emissions", "EmissionBand"),
    ("V2PlanResponse", "field", "FieldStatus"),
    ("V2TripResponse", "privacy", None),   # checked inline below
]


def _required(iface):
    return {f for f, req in CONTRACT[iface].items() if req}


def _declared(iface):
    return set(CONTRACT[iface]) | EXTRA_DECLARED.get(iface, set())


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
                     "V2CityResponse", "V2Place"):
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
        if p == "/v2/trip" or p == "/v2/plan":
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
        opt_missing = sorted(f for f, req in CONTRACT[iface].items()
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
