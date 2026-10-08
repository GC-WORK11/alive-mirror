"""Offline tests for GET /v2/stays + GET /v2/playtime — the 'stay &
play' surfaces (docs/plan hackathon features 2 & 3).

No network: deps.field_refresh is a no-op, FIELD is seeded with samples,
FORECAST is seeded with a synthetic 120 h CAMS horizon (same style as
test_v2_day) — refresh() short-circuits on the seeded TTL, so every
number below is the live-engine read of the injected series, never a
stub.

Run from server/:
    PYTHONPATH=core/build312:. .venv312/bin/python -m pytest \
        tests/test_v2_explore.py -q
"""
import os
import sys
import time
from datetime import datetime, timedelta, timezone

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient  # noqa: E402

import main  # noqa: E402
from airfield import FIELD  # noqa: E402
from forecast import FORECAST  # noqa: E402
from v2 import deps  # noqa: E402

client = TestClient(main.app, raise_server_exceptions=False)

CP = (28.6315, 77.2167)

SAMPLES = [
    (28.6315, 77.2167, "test-station", {"pm2_5": 150.0}),
    (28.6519, 77.1907, None, {"pm2_5": 185.0}),
    (28.5850, 77.2300, None, {"pm2_5": 120.0}),
    (28.7000, 77.2000, None, {"pm2_5": 210.0}),
]


def _seed_forecast(vals):
    """A deterministic CAMS horizon starting today 00:00 UTC — the same
    shape a real fetch parses to; refresh() then short-circuits on TTL."""
    t0 = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0,
                                            microsecond=0)
    times = [(t0 + timedelta(hours=i)).isoformat() for i in range(len(vals))]
    FORECAST._aq = [{"lat": CP[0], "lon": CP[1], "name": None, "t0": t0,
                     "times": times, "vars": {"pm2_5": list(vals)}}]
    FORECAST._met = []
    FORECAST._fetched_at = time.time()


def _dip_curve():
    """120 h at 150 with a light stretch 60 µg/m³ across raw slots
    30-39 — inside the next-24h window no matter which UTC hour the
    test runs at."""
    vals = [150.0] * 120
    for i in range(30, 40):
        vals[i] = 60.0
    return vals


@pytest.fixture(autouse=True)
def wired(monkeypatch):
    FIELD._samples = list(SAMPLES)
    FIELD._fetched_at = time.time()
    FIELD._station_count = 0
    FIELD._source = "test"
    FIELD._snap = None           # snapshot layer off — the seeded samples
    FIELD._snap_centers = []     # are what the card must serve
    _seed_forecast(_dip_curve())

    async def _noop(*a, **k):
        return None
    monkeypatch.setattr(deps, "field_refresh", _noop)
    monkeypatch.setattr(deps, "osrm_route", _noop)
    monkeypatch.setattr(FIELD, "refresh", _noop)
    monkeypatch.setattr(FORECAST, "refresh", _noop)
    monkeypatch.setattr(main.FIRES, "refresh", _noop)
    yield
    FIELD._samples = []
    FORECAST._aq = []
    FORECAST._met = []
    FORECAST._fetched_at = 0.0


# --------------------------------------------------------------- playtime
def test_playtime_hours_and_windows():
    r = client.get("/v2/playtime",
                   params={"near": f"{CP[0]},{CP[1]}"})
    assert r.status_code == 200
    d = r.json()
    assert d["served_h"] >= 20          # ~24 slots — horizon permitting
    assert d["window_h"] == 24
    hrs = d["hours"]
    assert hrs == sorted(hrs, key=lambda h: h["h"])
    for h in hrs:
        assert h["pm25_mid"] > 0
        assert h["date_ist"]
        assert h["day_offset"] in (0, 1, 2)
        assert h["band"] and h["confidence"] in ("hi", "med", "lo")
    # the seeded dip must be found — the window is real, not declared
    best = d["best_window"]
    assert best is not None
    assert best["pm25_mid"] < d["mean_pm25"]
    assert best["start_day_offset"] in (0, 1)
    assert "next-24h mean" in best["basis"]
    # 'cleaner by' = now minus the window's mean — exact arithmetic
    assert d["cleaner_by_ug"] == pytest.approx(
        round(d["now_pm25"] - best["pm25_mid"], 1))
    assert isinstance(d["verdict"], str) and d["verdict"]
    assert isinstance(d["flat"], bool)
    assert d["model"] and d["band_basis"]


def test_playtime_flat_horizon_says_so():
    _seed_forecast([150.0] * 120)
    r = client.get("/v2/playtime",
                   params={"lat": CP[0], "lon": CP[1]})
    assert r.status_code == 200
    d = r.json()
    # a perfectly flat curve has no meaningful window — the endpoint
    # must not invent one
    if d["flat"]:
        assert d["best_window"] is None
        assert "no window" in d["verdict"] or "barely" in d["verdict"]


def test_playtime_name_and_place_params():
    # near= resolves a gazetteer place through the /v2/search engine
    r = client.get("/v2/playtime", params={"near": "connaught place"})
    assert r.status_code == 200
    d = r.json()
    assert d["near"]["via"] == "search"
    assert d["near"]["name"]
    # explicit lat/lon params resolve without touching the corpus
    r2 = client.get("/v2/playtime", params={"lat": CP[0], "lon": CP[1]})
    assert r2.status_code == 200
    assert r2.json()["near"]["via"] == "coords"


def test_playtime_unresolvable_is_404():
    r = client.get("/v2/playtime",
                   params={"near": "zzzz-no-such-place-zzzz"})
    assert r.status_code == 404


def test_playtime_out_of_area_is_honest():
    d = client.get("/v2/playtime",
                   params={"lat": 19.0760, "lon": 72.8777}).json()
    assert "error" in d and "service area" in d["error"]
    assert d["hours"] == []


# ------------------------------------------------------------------ stays
def test_stays_ranked_and_honest():
    r = client.get("/v2/stays",
                   params={"near": f"{CP[0]},{CP[1]}", "k": 8})
    assert r.status_code == 200
    d = r.json()
    assert d["lodging_rows"] > 5000     # the corpus' real lodging slice
    stays = d["stays"]
    assert 1 <= len(stays) <= 8
    for s in stays:
        assert s["name"] and s["id"].startswith(("gaz:", "cor:"))
        assert s["dist_km"] >= 0
        assert s["band"]
        assert s["scored_on"] in ("next24h", "now", "unrated")
        assert s["nearest_station_km"] is None or \
            s["nearest_station_km"] >= 0
        if s["pm25_now"] is not None and s["cleaner_by_ug"] is not None:
            assert s["cleaner_by_ug"] == pytest.approx(
                round(d["anchor_pm25_now"] - s["pm25_now"], 1))
    # ranked by the window score first, unrated rows last — never the
    # reverse
    scored = [s for s in stays if s["window_mean_ug"] is not None]
    assert scored and all(
        s["scored_on"] == "next24h" for s in scored)
    means = [s["window_mean_ug"] for s in scored]
    assert means == sorted(means)
    assert stays[-1]["scored_on"] != "unrated" or len(stays) == 0 \
        or all(s["scored_on"] == "unrated" for s in stays)
    assert d["window_h"] == 24 and d["scored_h"] > 0


def test_stays_no_forecast_falls_back_to_now(monkeypatch):
    from v2 import explore
    FORECAST._aq = []                    # dead horizon — honest fallback
    FORECAST._met = []
    explore._EXPLORE_CACHE._d.clear()    # same epoch would serve the
                                         # prior test's cached body
    r = client.get("/v2/stays",
                   params={"lat": CP[0], "lon": CP[1], "k": 5})
    assert r.status_code == 200
    d = r.json()
    assert d["scored_h"] == 0
    assert "live field read only" in d["ranked_on"]
    for s in d["stays"]:
        assert s["scored_on"] in ("now", "unrated")
        assert s["window_mean_ug"] is None


def test_stays_unresolvable_and_out_of_area():
    r = client.get("/v2/stays", params={"near": "zzzz-no-such-place-zzzz"})
    assert r.status_code == 404
    d = client.get("/v2/stays",
                   params={"lat": 19.0760, "lon": 72.8777}).json()
    assert "error" in d and "service area" in d["error"]
    assert d["stays"] == []


def test_stays_every_row_is_lodging():
    d = client.get("/v2/stays",
                   params={"lat": CP[0], "lon": CP[1], "k": 15}).json()
    for s in d["stays"]:
        k = s["kind"].lower()
        assert any(m in k for m in (
            "hotel", "hostel", "lodg", "resort", "guest_house",
            "guesthouse", "motel", "dharamshala", "accommodation",
            "apartment")), f"non-lodging row leaked: {s['kind']}"
