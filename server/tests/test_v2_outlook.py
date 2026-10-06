"""Offline tests for GET /v2/outlook — the per-day fold of the real
120 h horizon (the morning card's companion for the days ahead).

No network: deps.field_refresh is a no-op, FIELD is seeded with samples,
FORECAST is seeded with a synthetic 120 h CAMS curve (same seeding style
as test_v2_day) — refresh() short-circuits on the seeded TTL so the
endpoint reads only the injected series.

Run from server/:
    PYTHONPATH=core/build312:. .venv312/bin/python -m pytest \
        tests/test_v2_outlook.py -q
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
from forecast import FORECAST, anchor_w  # noqa: E402
from v2 import deps  # noqa: E402
from v2 import outlook as v2out  # noqa: E402

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
    FIELD._snap_centers = []     # are what the endpoint must serve
    FIELD._snap_epoch = 0.0
    _seed_forecast([150.0] * 120)

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
    b = client.get("/v2/outlook", params={"lat": CP[0], "lon": CP[1]}).json()
    for k in ("lat", "lon", "tz", "generated_ist", "horizon_days",
              "horizon_hours", "days", "best_day", "flat", "verdict",
              "model", "band_basis", "field_age_s", "field", "forecast"):
        assert k in b, f"missing {k}"
    assert "error" not in b
    assert b["days"], "seeded forecast must serve day rows"
    assert 1 <= b["horizon_days"] <= 5
    assert b["horizon_days"] == len(b["days"])
    assert b["horizon_hours"] == sum(d["n_hours"] for d in b["days"])
    for d in b["days"]:
        for k in ("date_ist", "label", "partial", "n_hours", "pm25_mid",
                  "pm25_lo", "pm25_hi", "band", "heavy_hours_ist",
                  "cleanest_window", "confidence", "anchor_w"):
            assert k in d, f"day missing {k}"
        assert d["pm25_mid"] is not None and d["n_hours"] >= 1
        if d["pm25_lo"] is not None:
            assert d["pm25_lo"] <= d["pm25_mid"] <= d["pm25_hi"]
        assert d["confidence"] in ("hi", "med", "lo")
        assert isinstance(d["heavy_hours_ist"], list)


def test_days_are_today_plus_four_max():
    """The fold is today's remainder + up to 4 more IST days — the real
    horizon, never a padded week."""
    b = client.get("/v2/outlook", params={"lat": CP[0], "lon": CP[1]}).json()
    labels = [d["label"] for d in b["days"]]
    assert labels[0] == "today"
    if len(labels) > 1:
        assert labels[1] == "tomorrow"
    dates = [d["date_ist"] for d in b["days"]]
    assert dates == sorted(dates)               # chronological
    assert len(set(dates)) == len(dates)        # one row per IST date
    # a day row never holds more than a day's slots
    assert all(d["n_hours"] <= 24 for d in b["days"])


def test_today_is_partial_remainder():
    """Queried mid-day, 'today' can only hold the hours left — partial
    must say so rather than read as a full-day mean."""
    b = client.get("/v2/outlook", params={"lat": CP[0], "lon": CP[1]}).json()
    today = b["days"][0]
    assert today["label"] == "today"
    assert today["partial"] == (today["n_hours"] < 24)


def test_flat_horizon_says_so():
    """A constant horizon: every day within noise → no pick, and the
    verdict names the flatness instead of inventing a best day."""
    b = client.get("/v2/outlook", params={"lat": CP[0], "lon": CP[1]}).json()
    assert b["flat"] is True
    assert b["best_day"] is None
    assert "no meaningful difference" in b["verdict"]
    for d in b["days"]:
        assert d["heavy_hours_ist"] == []
        assert d["cleanest_window"] is None


def test_declining_horizon_picks_least_bad_day():
    """A monotone decline: the last served day is the real least-bad
    pick — and a non-flat verdict."""
    _seed_forecast([300.0 - 1.5 * i for i in range(120)])
    b = client.get("/v2/outlook", params={"lat": CP[0], "lon": CP[1]}).json()
    assert b["flat"] is False
    bd = b["best_day"]
    assert bd is not None
    means = [d["pm25_mid"] for d in b["days"]]
    assert abs(bd["pm25_mid"] - min(means)) < 0.2
    assert bd["delta_vs_mean"] < 0
    assert bd["label"] in b["verdict"]
    assert "µg/m³" in b["verdict"]


def test_confidence_fades_monotonic_over_days():
    """Per-day anchor weight must be non-increasing down the horizon —
    day-4 never pretends to day-0 certainty."""
    b = client.get("/v2/outlook", params={"lat": CP[0], "lon": CP[1]}).json()
    ws = [d["anchor_w"] for d in b["days"]]
    assert all(a >= c for a, c in zip(ws, ws[1:])), ws
    grade = {"hi": 2, "med": 1, "lo": 0}
    gs = [grade[d["confidence"]] for d in b["days"]]
    assert all(a >= c for a, c in zip(gs, gs[1:])), gs
    # the last served day sits ~4 days out — the anchor has decayed to
    # nothing, and it must say so
    last = b["days"][-1]
    assert last["confidence"] == "lo"
    assert "note" in last and "raw CAMS" in last["note"]


def test_outside_service_area_rejection():
    b = client.get("/v2/outlook", params={"lat": 51.5, "lon": -0.12}).json()
    assert b["days"] == []
    assert "outside service area" in b["error"]
    b2 = client.get("/v2/outlook", params={"lat": -91.0, "lon": 77.2}).json()
    assert "outside service area" in b2["error"]


def test_malformed_coords_4xx():
    r = client.get("/v2/outlook", params={"lat": "nan", "lon": 77.2})
    assert r.status_code == 422
    r = client.get("/v2/outlook", params={"lat": "abc", "lon": 77.2})
    assert r.status_code == 422
    r = client.get("/v2/outlook", params={"lat": CP[0]})   # missing lon
    assert r.status_code == 422


def test_forecast_unavailable_is_honest():
    FORECAST._aq = []
    b = client.get("/v2/outlook", params={"lat": CP[0], "lon": CP[1]}).json()
    assert b["days"] == []
    assert b["error"] == "forecast unavailable"
    assert b["horizon_days"] == 0
    assert b["best_day"] is None


# ------------------------------------------------------------------ fold
TODAY = datetime.now(v2out._IST).date()


_UTC = timezone.utc


def _mk_pairs(mids, h_start=0, band="Very Poor", half=20.0):
    """Synthetic (row, band_half) pairs for _fold_day/summarize_outlook —
    same keys the endpoint's real _hour_entry rows carry, with `start`
    and `ist_label` consistent the way the real ones are (a slot
    starting HH:00 UTC shows (HH+5):30 on the Delhi clock)."""
    base = datetime(2026, 10, 5, 0, 0, tzinfo=_UTC)
    return [({"h": h_start + i,
              "ist_label": f"{(i + 5) % 24:02d}:30",
              "start": (base + timedelta(hours=i)).isoformat(),
              "pm25_mid": m, "band": band}, half)
            for i, m in enumerate(mids)]


def _mk_outlook(day_mids):
    """day_mids: [ [24 mids], [24 mids], ... ] → day_pairs."""
    return [(TODAY + timedelta(days=i),
             _mk_pairs(mids, h_start=24 * i))
            for i, mids in enumerate(day_mids)]


def test_fold_flat_day_no_windows():
    d = v2out._fold_day(TODAY, _mk_pairs([100.0] * 24), TODAY, True,
                        anchor_w)
    assert d["heavy_hours_ist"] == []
    assert d["cleanest_window"] is None
    assert d["pm25_mid"] == 100.0
    assert d["n_hours"] == 24 and d["partial"] is False
    assert d["band"] == "Very Poor"


def test_fold_swinging_day_finds_windows():
    mids = [200.0] * 6 + [60.0] * 6 + [200.0] * 6 + [300.0] * 6
    d = v2out._fold_day(TODAY, _mk_pairs(mids), TODAY, True, anchor_w)
    cw = d["cleanest_window"]
    assert cw is not None
    assert cw["pm25_mid"] == 60.0
    # dip sits at idx 6-11: IST starts (6+5):30→(11+5):30, end label is
    # the last slot's end = UTC 12:00 → IST 17:30
    assert cw["start_label"] == "11:30" and cw["end_label"] == "17:30"
    # the 300s stretch is a real run — its IST labels enumerate
    assert d["heavy_hours_ist"] == ["23:30", "00:30", "01:30",
                                    "02:30", "03:30", "04:30"]
    # window rows reuse the card's declared shape — nothing undeclared
    assert set(cw) <= {"start_h", "end_h", "start_label", "end_label",
                       "pm25_mid", "basis"}


def test_fold_short_sliver_is_honest():
    """A 5-6 h last-day sliver: folded, marked partial, and too short to
    claim a window."""
    d = v2out._fold_day(TODAY, _mk_pairs([90.0, 95.0]), TODAY, True,
                        anchor_w)
    assert d["n_hours"] == 2 and d["partial"] is True
    assert d["cleanest_window"] is None
    assert d["pm25_mid"] == 92.5


def test_outlook_flat_across_days():
    s = v2out.summarize_outlook(
        _mk_outlook([[150.0] * 24] * 5), TODAY, True, anchor_w)
    assert s["flat"] is True
    assert s["best_day"] is None
    assert "no meaningful difference between days" in s["verdict"]


def test_outlook_picks_lowest_mean_day():
    days = [[200.0] * 24, [210.0] * 24, [120.0] * 24,
            [190.0] * 24, [180.0] * 24]
    s = v2out.summarize_outlook(_mk_outlook(days), TODAY, True,
                                anchor_w)
    assert s["flat"] is False
    bd = s["best_day"]
    assert bd is not None
    assert bd["pm25_mid"] == 120.0
    assert bd["label"] == (TODAY + timedelta(days=2)).strftime(
        "%A").lower()
    assert bd["delta_vs_mean"] < 0
    assert "least-bad" in s["verdict"]          # 120 > 60 — never "clean"


def test_outlook_best_can_say_cleanest():
    """A genuinely low day (<60 mean) earns 'cleanest', not least-bad."""
    days = [[200.0] * 24, [50.0] * 24, [190.0] * 24]
    s = v2out.summarize_outlook(_mk_outlook(days), TODAY, True,
                                anchor_w)
    assert "cleanest" in s["verdict"]


def test_outlook_noise_spread_is_flat():
    """Day means within _FLAT_UG of each other = noise, not a pick."""
    days = [[150.0] * 24, [158.0] * 24, [146.0] * 24]
    s = v2out.summarize_outlook(_mk_outlook(days), TODAY, True,
                                anchor_w)
    assert s["flat"] is True and s["best_day"] is None


def test_confidence_grade_follows_anchor_w():
    """h_mean drives the day grade: a day centred ~100h out is 'lo' and
    carries the raw-CAMS note."""
    far = v2out._fold_day(TODAY, _mk_pairs([100.0] * 24, h_start=96),
                          TODAY, True, anchor_w)
    assert far["confidence"] == "lo"
    assert "note" in far
    near = v2out._fold_day(TODAY, _mk_pairs([100.0] * 6, h_start=0),
                           TODAY, True, anchor_w)
    assert near["confidence"] in ("hi", "med")
    assert near["anchor_w"] > far["anchor_w"]
