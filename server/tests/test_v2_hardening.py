"""Hardening for /v2 — ranking-rule property tests over a real Delhi
OD matrix plus edge-case fuzz on /v2/plan, /v2/strip, /v2/search.

Ranking invariants (docs/plan/06 §4), asserted per response AND per
randomized unit input to rank_options:
  * exactly one option recommended (when any option is scored)
  * the recommended option is within-tie: dose_lo (or mid fallback)
    <= 1.10 × min dose among scored
  * tag consistency: 'lightest on both' only when the recommended
    option is also the global emission minimum; otherwise both
    'lightest for you' and 'lightest for Delhi' appear
  * time guard: recommended slower than 1.6× the fastest scored ETA
    must carry a '+N min' reason

Offline: FakeLoc returns distance-proportional routes, osrm_route is
monkeypatched likewise, FIELD holds injected samples.
Run from server/:
    .venv/bin/python -m pytest tests/test_v2_hardening.py -v
"""
import math
import os
import random
import re
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

client = TestClient(main.app, raise_server_exceptions=False)

# --- real Delhi OD pairs ------------------------------------------------------
CP = (28.6315, 77.2167)
PAIRS = [
    ("CP → Noida Sec-18", (28.6315, 77.2167), (28.5708, 77.3260)),
    ("CP → Gurugram CyberCity", (28.6315, 77.2167), (28.4950, 77.0890)),
    ("Dwarka-21 → Rohini", (28.5523, 77.0580), (28.7041, 77.1125)),
    ("Sarai Kale Khan → IGI T3", (28.5884, 77.2572), (28.5562, 77.1000)),
    ("Chandni Chowk → IIT-D", (28.6506, 77.2303), (28.5449, 77.1928)),
    ("Kashmere Gate → Faridabad", (28.6675, 77.2280), (28.4089, 77.3178)),
    ("Same point (0 km)", (28.6139, 77.2090), (28.6139, 77.2090)),
]


def _hav_m(la1, lo1, la2, lo2):
    p1, p2 = math.radians(la1), math.radians(la2)
    dp, dl = math.radians(la2 - la1), math.radians(lo2 - lo1)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * 6371000.0 * math.asin(math.sqrt(h))


def _geom(a, b):
    """Straight-ish LineString, [lon,lat], ~20 points along the OD."""
    return {"type": "LineString",
            "coordinates": [[a[1] + (b[1] - a[1]) * i / 19,
                             a[0] + (b[0] - a[0]) * i / 19]
                            for i in range(20)]}


class DistFakeLoc:
    """Amazon-shaped fake whose routes scale with real OD distance —
    so each OD pair exercises a different ranking regime."""
    def __init__(self, enabled=True):
        self.enabled = enabled

    async def calculate_routes(self, flat, flon, tlat, tlon,
                               travel_mode="Car", alternatives=2,
                               depart_at=None):
        d = _hav_m(flat, flon, tlat, tlon)
        if d < 100:
            return []
        base = max(120.0, d / 1000.0 / 28.0 * 3600.0)  # ~28 km/h Delhi
        routes = [{"distance_m": d * 1.18, "duration_s": base,
                   "freeflow_s": base * 0.82,
                   "geometry": _geom((flat, flon), (tlat, tlon)),
                   "notices": [], "source": "fake-amazon"}]
        for i in range(min(alternatives, 2)):          # slower alternates
            routes.append({"distance_m": d * (1.25 + 0.1 * i),
                           "duration_s": base * (1.15 + 0.2 * i),
                           "freeflow_s": base * 0.9,
                           "geometry": _geom((flat, flon), (tlat, tlon)),
                           "notices": [], "source": "fake-amazon"})
        return routes

    async def suggest(self, q, lat, lon, limit=8):
        return []

    async def get_place(self, place_id):
        return None

    async def reverse_geocode(self, lat, lon, limit=10):
        return [{"place_id": "r1", "street": "Rajpath",
                 "locality": "Central Secretariat",
                 "label": "Rajpath, Central Secretariat, New Delhi",
                 "lat": 28.6150, "lon": 77.2150, "distance_m": 40,
                 "kind": "Street", "source": "amazon"}]


@pytest.fixture(autouse=True)
def wired(monkeypatch):
    deps.set_location(DistFakeLoc())
    FIELD._samples = [
        (28.6315, 77.2167, "test-station", {"pm2_5": 150.0}),
        (28.6519, 77.1907, None, {"pm2_5": 185.0}),
        (28.5850, 77.2300, None, {"pm2_5": 120.0}),
        (28.5708, 77.3260, None, {"pm2_5": 210.0}),
        (28.4950, 77.0890, None, {"pm2_5": 95.0}),
    ]
    FIELD._fetched_at = time.time()

    async def _no_refresh():
        return None
    monkeypatch.setattr(deps, "field_refresh", _no_refresh)

    async def fake_osrm(profile, flon, flat, tlon, tlat):
        d = _hav_m(flat, flon, tlat, tlon)
        if d < 50:
            return None
        return {"distance": d * 1.15, "duration": d / 1000.0 / 25.0 * 3600.0,
                "geometry": _geom((flat, flon), (tlat, tlon))}
    monkeypatch.setattr(deps, "osrm_route", fake_osrm)

    store.TRIPS.reset()
    store.ROUTES._routes.clear()
    yield
    deps.set_location(None)
    FIELD._samples = []


# --- ranking helpers (mirror of plan.py internals) -----------------------------
def _dose_key(o):
    d = o.get("dose") or {}
    v = d.get("lo") if d.get("lo") is not None else d.get("mid")
    return float(v) if v is not None else float("inf")


def _co2_mid(o):
    e = (o.get("emissions") or {}).get("co2_kg") or {}
    v = e.get("mid")
    return float(v) if v is not None else float("inf")


def _scored(options):
    return [o for o in options
            if _dose_key(o) != float("inf") and o.get("eta_s")]


def assert_ranking_holds(options, ctx=""):
    scored = _scored(options)
    rec = [o for o in options if o.get("recommended")]
    if not scored:
        assert not rec, f"{ctx}: recommended an unscored option"
        return
    assert len(rec) == 1, f"{ctx}: {len(rec)} recommended, want exactly 1"
    win = rec[0]
    assert win in scored, f"{ctx}: recommended option isn't scored"

    dose_min = min(_dose_key(o) for o in scored)
    assert _dose_key(win) <= 1.10 * dose_min * (1 + 1e-9), (
        f"{ctx}: recommended dose {_dose_key(win)} breaches the "
        f"10% tie vs min {dose_min}")

    tags = {o.get("tag") for o in options if o.get("tag")}
    assert tags <= {"lightest on both", "lightest for you",
                    "lightest for Delhi"}, f"{ctx}: bad tag {tags}"
    emin = min(scored, key=_co2_mid)
    if win.get("tag") == "lightest on both":
        assert _co2_mid(win) == _co2_mid(emin), (
            f"{ctx}: 'lightest on both' but co2 {_co2_mid(win)} "
            f"!= min {_co2_mid(emin)}")
    elif tags:
        emis_known = _co2_mid(emin) != float("inf")
        want = ({"lightest for you", "lightest for Delhi"} if emis_known
                # no emission estimate anywhere → 'lightest for Delhi'
                # would pick an arbitrary option — only the dose tag is honest
                else {"lightest for you"})
        assert want <= tags, f"{ctx}: split tags incomplete: {tags}"

    fastest = min(o["eta_s"] for o in scored)
    if fastest and win["eta_s"] > 1.6 * fastest:
        m = re.search(r"\+(\d+)\s*min", win.get("reason_line") or "")
        assert m, (f"{ctx}: recommended is {win['eta_s']/fastest:.2f}× "
                   f"fastest without a '+N min' reason")
        want = int(round((win["eta_s"] - fastest) / 60.0))
        assert abs(int(m.group(1)) - want) <= 1, (
            f"{ctx}: reason says +{m.group(1)} min, want ~+{want}")


# --- ranking property over the real OD matrix ---------------------------------
@pytest.mark.parametrize("name,a,b", PAIRS,
                         ids=[p[0] for p in PAIRS])
def test_plan_ranking_invariants_on_real_ods(name, a, b):
    r = client.post("/v2/plan", json={
        "from": {"lat": a[0], "lon": a[1]},
        "to": {"lat": b[0], "lon": b[1]}, "vehicle": "car"})
    assert r.status_code == 200
    body = r.json()
    if not body["options"]:
        pytest.skip(f"{name}: no options returned")
    assert_ranking_holds(body["options"], ctx=name)
    # recommended is sorted first whenever one exists
    if any(o.get("recommended") for o in body["options"]):
        assert body["options"][0]["recommended"]


def test_rank_options_randomized_property():
    """200 seeded random option sets — invariants must hold for ANY
    input the builders might produce, not just tonight's field."""
    rng = random.Random(108)
    for trial in range(200):
        n = rng.randint(1, 8)
        opts = []
        for i in range(n):
            dose_lo = rng.choice([None, rng.uniform(0, 400)])
            dose_mid = rng.uniform(0, 400) if dose_lo is None else \
                dose_lo + rng.uniform(0, 40)
            co2 = rng.choice([None, rng.uniform(0, 5)])
            opts.append({
                "mode": f"m{i}", "eta_s": rng.choice([0, rng.uniform(60, 7200)]),
                "dose": {"lo": dose_lo, "mid": dose_mid},
                "emissions": {"co2_kg": {"mid": co2}},
                "recommended": rng.random() < 0.3,   # stale flags must reset
                "tag": rng.choice([None, "lightest on both"]),
                "reason_line": "stale",
            })
        v2plan.rank_options(opts)
        assert_ranking_holds(opts, ctx=f"random trial {trial}")


def test_rank_all_none_emissions_claims_nothing():
    """If every option's co2 is unknown, 'lightest on both' is a claim
    the data can't support — the tag should be suppressed."""
    opts = [
        {"mode": "x", "eta_s": 600, "dose": {"lo": 100, "mid": 100},
         "emissions": {"co2_kg": {"mid": None}}},
        {"mode": "y", "eta_s": 500, "dose": {"lo": 105, "mid": 105},
         "emissions": {"co2_kg": {"mid": None}}},
    ]
    out = v2plan.rank_options(opts)
    win = out[0]
    assert win["tag"] != "lightest on both", (
        "claimed 'lightest on both' with no emission data at all")


def test_rank_dose_only_options_still_recommend():
    """Options with dose but no emissions: recommendation still lands
    (on the dose winner) and no emission tag is invented."""
    opts = [
        {"mode": "hi", "eta_s": 600, "dose": {"lo": 300, "mid": 300},
         "emissions": {"co2_kg": {}}},
        {"mode": "lo", "eta_s": 500, "dose": {"lo": 100, "mid": 100},
         "emissions": {"co2_kg": {}}},
    ]
    out = v2plan.rank_options(opts)
    assert out[0]["mode"] == "lo" and out[0]["recommended"]


def test_rank_no_scored_options_recommends_nothing():
    opts = [{"mode": "a", "eta_s": 0, "dose": {"lo": None, "mid": None},
             "emissions": {}}]
    out = v2plan.rank_options(opts)
    assert not any(o.get("recommended") for o in out)


# --- /v2/plan malformed bodies ---------------------------------------------------
def test_plan_missing_from_returns_honest_error():
    r = client.post("/v2/plan", json={"to": {"lat": 28.5, "lon": 77.2}})
    assert r.status_code in (200, 400, 422)
    body = r.json()
    assert not body.get("options"), "options for a missing origin?!"
    assert body.get("error"), "missing 'from' produced no error field"


def test_plan_missing_to_and_empty_body():
    for body in ({"from": {"lat": 28.6, "lon": 77.2}}, {}, {"from": None}):
        r = client.post("/v2/plan", json=body)
        assert r.status_code in (200, 400, 422)
        j = r.json()
        assert not j.get("options")
        assert j.get("error") is not None


def test_plan_non_numeric_lat():
    r = client.post("/v2/plan", json={
        "from": {"lat": "abc", "lon": 77.2},
        "to": {"lat": 28.5, "lon": 77.2}})
    assert r.status_code in (200, 400, 422)
    assert r.json().get("error") or r.json().get("detail")


def test_plan_out_of_range_coordinates():
    """lat=999 is float-valid but geo-garbage — a defensive server
    either routes nothing or errors honestly; it must not 500."""
    r = client.post("/v2/plan", json={
        "from": {"lat": 999.0, "lon": 999.0},
        "to": {"lat": 28.5, "lon": 77.2}})
    assert r.status_code in (200, 400, 422)


def test_plan_point_as_list_geojson_order():
    """[lon,lat] shorthand must work (contract allows both)."""
    r = client.post("/v2/plan", json={
        "from": [77.2167, 28.6315], "to": [77.3260, 28.5708]})
    assert r.status_code == 200
    assert isinstance(r.json().get("options"), list)


def test_plan_unknown_vehicle_falls_back():
    r = client.post("/v2/plan", json={
        "from": {"lat": 28.63, "lon": 77.21},
        "to": {"lat": 28.57, "lon": 77.32}, "vehicle": "unicycle"})
    assert r.status_code == 200
    assert r.json()["vehicle"] == "car"             # modelled fallback
    assert r.json()["vehicle_requested"] == "unicycle"  # echoed, not washed


# --- /v2/strip edge cases ---------------------------------------------------------
def _seed_route(age_s=0.0):
    rid = store.ROUTES.put({"geometry": _geom(CP, (28.5708, 77.3260)),
                            "mode": "car", "duration_s": 900,
                            "vehicle": "car"})
    if age_s:
        store.ROUTES._routes[rid] = (time.time() - age_s,
                                     store.ROUTES._routes[rid][1])
    return rid


def test_strip_unknown_route_id_404_honest():
    r = client.get("/v2/strip", params={"route_id": "does-not-exist"})
    assert r.status_code == 404
    body = r.json()
    assert body.get("error") and "route_id" in body.get("error", "")
    assert body.get("detail"), "404 without the honest expiry note"


def test_strip_expired_route_id_404():
    """A route_id past its 1 h TTL dies with the same honest 404 —
    no resurrected geometry."""
    rid = _seed_route(age_s=3700)
    r = client.get("/v2/strip", params={"route_id": rid})
    assert r.status_code == 404
    assert "expire" in r.json().get("detail", "").lower() or \
        r.json().get("error")


def test_strip_empty_and_missing_route_id():
    assert client.get("/v2/strip").status_code == 422
    assert client.get("/v2/strip",
                      params={"route_id": ""}).status_code == 422


def test_strip_live_route_samples_shape():
    rid = _seed_route()
    r = client.get("/v2/strip", params={"route_id": rid})
    assert r.status_code == 200
    body = r.json()
    for s in body["samples"]:
        # strip points are rounded to 5 dp — never raw-precision
        assert s["lat"] == round(s["lat"], 5)
        assert s["lon"] == round(s["lon"], 5)
        if s["pm25"] is not None:
            assert s["pm25"] >= 0


def test_strip_route_id_sqlish_injection_is_404():
    for evil in ("'; DROP TABLE routes--", "../etc/passwd",
                 "%00", "x" * 500):
        r = client.get("/v2/strip", params={"route_id": evil})
        assert r.status_code == 404, f"{evil!r} → {r.status_code}"


# --- /v2/search edge cases -------------------------------------------------------
def test_search_oversized_limit_not_silent():
    """limit > 15: honest behavior = clamp OR 4xx — never obey blindly."""
    r = client.get("/v2/search", params={"q": "connaught", "limit": 500})
    if r.status_code == 200:
        assert len(r.json()["results"]) <= 15
    else:
        assert r.status_code == 422  # FastAPI `le=15` rejects, not clamps


def test_search_query_length_bounds():
    assert client.get("/v2/search", params={"q": "a"}).status_code == 200
    assert client.get("/v2/search",
                      params={"q": "x" * 200}).status_code == 200
    r = client.get("/v2/search", params={"q": "x" * 201})
    assert r.status_code == 422
    assert client.get("/v2/search", params={"q": ""}).status_code == 422


def test_search_unicode_and_symbols():
    for q in ("कनॉट प्लेस", "🚇🚇🚇", "<script>alert(1)</script>",
              "नई दिल्ली railway", "a" * 3 + "\x00" + "b"):
        r = client.get("/v2/search", params={"q": q})
        assert r.status_code == 200, f"q={q!r} → {r.status_code}"
        assert isinstance(r.json()["results"], list)


def test_search_whitespace_only_query():
    r = client.get("/v2/search", params={"q": "   "})
    assert r.status_code == 200
    assert r.json()["results"] == []


def test_search_non_numeric_bias_rejected():
    r = client.get("/v2/search",
                   params={"q": "cp", "lat": "abc", "lon": "def"})
    assert r.status_code == 422


def test_search_limit_zero_and_negative():
    for lim in (0, -3):
        r = client.get("/v2/search", params={"q": "cp", "limit": lim})
        assert r.status_code in (200, 422)
        if r.status_code == 200:
            # limit<=0 should mean "no results", never a negative-slice leak
            assert r.json()["results"] == [], (
                f"limit={lim} returned {len(r.json()['results'])} results")


# --- cross-endpoint --------------------------------------------------------------
def test_trip_then_city_shows_aggregates_only():
    """Donate a trip, read /v2/city: totals move, nothing per-trip
    or per-token appears in the consumer payload."""
    for tok in ("c1", "c2", "c3"):
        client.post("/v2/trip", json={
            "device_token": tok,
            "summary": {"mode": "cycle", "distance_km": 4.0,
                        "dose_ug": 30.0},
            "trajectory": [[77.20 + i * 0.0009, 28.63]
                           for i in range(50)]})
    r = client.get("/v2/city")
    assert r.status_code == 200
    text = r.text
    for tok in ("c1", "c2", "c3"):
        assert tok not in text
    trips = r.json()["trips"]
    assert trips["days"], "trip aggregates missing from /v2/city"
    day = trips["days"][time.strftime("%Y-%m-%d", time.gmtime())]
    assert day["trips"] == 3 and day["modes"] == {"cycle": 3}
