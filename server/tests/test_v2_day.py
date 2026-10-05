"""Offline tests for GET /v2/day — the morning card's day-at-a-point.

No network: deps.field_refresh is a no-op, FIELD is seeded with samples,
FORECAST is seeded with a synthetic 120 h CAMS curve (same seeding style
as test_airindex_realtime._forecast_field) — refresh() short-circuits on
the seeded TTL so the endpoint reads only the injected series.

Run from server/:
    PYTHONPATH=core/build312:. .venv312/bin/python -m pytest \
        tests/test_v2_day.py -q
"""
import os
import sys
import time
from datetime import datetime, timedelta, timezone

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient  # noqa: E402

import main  # noqa: E402
import forecast  # noqa: E402
from airfield import FIELD  # noqa: E402
from forecast import FORECAST  # noqa: E402
from v2 import day as v2day  # noqa: E402
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


@pytest.fixture(autouse=True)
def wired(monkeypatch):
    FIELD._samples = list(SAMPLES)
    FIELD._fetched_at = time.time()
    FIELD._station_count = 0
    FIELD._source = "test"
    FIELD._snap = None           # snapshot layer off — the seeded samples
    FIELD._snap_centers = []     # are what the card must serve
    FIELD._snap_epoch = 0.0
    _seed_forecast([120.0] * 120)

    async def _noop(*a, **k):
        return None
    monkeypatch.setattr(deps, "field_refresh", _noop)
    monkeypatch.setattr(FIELD, "refresh", _noop)
    monkeypatch.setattr(FORECAST, "refresh", _noop)  # no live fetch —
    # the seeded _aq above is the only horizon these tests may see
    yield
    FIELD._samples = []
    FORECAST._aq = []
    FORECAST._met = []
    FORECAST._fetched_at = 0.0


# ------------------------------------------------------------------ shape
def test_happy_path_shape():
    b = client.get("/v2/day", params={"lat": CP[0], "lon": CP[1]}).json()
    for k in ("lat", "lon", "date_ist", "tz", "hours", "now_idx",
              "day_mean_pm25", "heavy_window", "cleanest_window",
              "decisions", "model", "band_basis", "field_age_s",
              "field", "forecast"):
        assert k in b, f"missing {k}"
    assert "error" not in b
    assert b["hours"], "seeded forecast must serve today's slots"
    assert b["now_idx"] == 0
    for hh in b["hours"]:
        for k in ("h", "ist_label", "pm25_mid", "pm25_lo", "pm25_hi",
                  "us_aqi", "band", "confidence"):
            assert k in hh, f"hour missing {k}"
        assert hh["pm25_mid"] is not None
        if hh["pm25_lo"] is not None:
            assert hh["pm25_lo"] <= hh["pm25_mid"] <= hh["pm25_hi"]
        assert hh["confidence"] in ("hi", "med", "lo")
    # the first hour is the live-anchored read — the field's own value
    assert abs(b["hours"][0]["pm25_mid"]
               - FIELD.value(*CP, "pm2_5")) < 1.0
    assert isinstance(b["decisions"], list)


def test_hours_cover_today_only():
    b = client.get("/v2/day", params={"lat": CP[0], "lon": CP[1]}).json()
    today = b["date_ist"]
    assert today
    # every served slot must start on the served IST date (labels are
    # HH:MM — the array ends before tomorrow)
    assert len(b["hours"]) <= 24
    assert b["hours"][-1]["h"] >= b["hours"][0]["h"]
    hs = [hh["h"] for hh in b["hours"]]
    assert hs == sorted(hs)          # hours in time order


def test_confidence_fades_with_horizon():
    """The anchor-decay grade must be non-increasing down the horizon —
    h+0 never grades below h+10."""
    b = client.get("/v2/day", params={"lat": CP[0], "lon": CP[1]}).json()
    grade = {"hi": 2, "med": 1, "lo": 0}
    gs = [grade[hh["confidence"]] for hh in b["hours"]]
    assert all(a >= b_ for a, b_ in zip(gs, gs[1:])), gs


def test_outside_service_area_rejection():
    b = client.get("/v2/day", params={"lat": 51.5, "lon": -0.12}).json()
    assert b["hours"] == []
    assert "outside service area" in b["error"]
    # finite-but-outside latitude — /aqi's rejection, not a crash
    b2 = client.get("/v2/day", params={"lat": -91.0, "lon": 77.2}).json()
    assert "outside service area" in b2["error"]


def test_malformed_coords_4xx():
    r = client.get("/v2/day", params={"lat": "nan", "lon": 77.2})
    assert r.status_code == 422
    r = client.get("/v2/day", params={"lat": "abc", "lon": 77.2})
    assert r.status_code == 422
    r = client.get("/v2/day", params={"lat": CP[0]})   # missing lon
    assert r.status_code == 422


def test_forecast_unavailable_is_honest():
    FORECAST._aq = []
    b = client.get("/v2/day", params={"lat": CP[0], "lon": CP[1]}).json()
    assert b["hours"] == []
    assert b["error"] == "forecast unavailable"
    assert b["now_idx"] is None


# ------------------------------------------------------------------ summarize
def _mk_hours(mids, band="Very Poor"):
    """Synthetic hour rows for summarize_day — ist_label/start placeholders."""
    return [{"h": i, "ist_label": f"{(17 + i) % 24:02d}:30",
             "start": "2026-10-05T12:00", "pm25_mid": m, "band": band}
            for i, m in enumerate(mids)]


def test_flat_day_has_no_window():
    s = v2day.summarize_day(_mk_hours([100.0] * 12))
    assert s["heavy_window"] is None
    assert s["cleanest_window"] is None
    lines = " ".join(d["line"] for d in s["decisions"])
    assert "no meaningful window" in lines


def test_single_clean_dip_finds_window():
    mids = [200, 200, 200, 50, 50, 50, 200, 200, 200, 200]
    s = v2day.summarize_day(_mk_hours(mids))
    cw = s["cleanest_window"]
    assert cw is not None
    assert cw["start_h"] == 3 and cw["end_h"] == 5
    assert cw["pm25_mid"] == 50.0


def test_two_dips_picks_the_better_one():
    mids = [200, 200, 80, 80, 200, 200, 60, 60, 60, 200, 200]
    s = v2day.summarize_day(_mk_hours(mids))
    cw = s["cleanest_window"]
    assert cw is not None
    # the deeper dip wins even though it's shorter... it is longer AND
    # lower here — assert the clean run is the 60s, not the 80s
    assert cw["pm25_mid"] == 60.0
    assert cw["start_h"] == 6 and cw["end_h"] == 8


def test_two_dips_picks_lower_over_longer():
    """A lower-but-shorter dip beats a longer-but-shallower one."""
    mids = [200, 200, 70, 70, 70, 70, 200, 200, 55, 55, 200, 200]
    s = v2day.summarize_day(_mk_hours(mids))
    assert s["cleanest_window"]["pm25_mid"] == 55.0


def test_heavy_window_open_end():
    """A heavy run reaching the last served hour stays open-ended."""
    mids = [60, 60, 200, 200, 300, 300]
    s = v2day.summarize_day(_mk_hours(mids))
    hw = s["heavy_window"]
    assert hw is not None
    assert hw["end_h"] is None        # runs through day end — never a fake stop


def test_decisions_come_from_windows_not_copy():
    """Every decision line names a slot from the actual curve."""
    mids = [300, 300, 300, 60, 60, 300, 300, 300, 300, 300]
    s = v2day.summarize_day(_mk_hours(mids))
    labels = {d["label"] for d in s["decisions"]}
    assert "outdoor exercise" in labels
    ex = [d for d in s["decisions"] if d["label"] == "outdoor exercise"][0]
    assert "~" in ex["line"] and "IST" in ex["line"]


def test_short_day_honest():
    s = v2day.summarize_day(_mk_hours([150.0, 160.0]))
    assert s["heavy_window"] is None and s["cleanest_window"] is None
    assert "left on the card" in s["decisions"][0]["line"]
