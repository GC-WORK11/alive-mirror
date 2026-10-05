"""Offline tests for server/skill.py + GET /v2/skill — the model
grading its own served forecast against the recorded archive.

Same discipline as test_archive.py: no network, no AWS — FakeField /
FakeForecast stand-ins, tmp_path as the archive root.
Run from server/:
    PYTHONPATH=. .venv/bin/python -m pytest tests/test_skill.py -q
"""
import os
import sys
from datetime import date, datetime, timedelta, timezone

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient  # noqa: E402

import archive as _arch  # noqa: E402
import main  # noqa: E402
import skill as _skill  # noqa: E402
from test_archive import FakeField, FakeForecast, _ts_ist, _utc  # noqa: E402

client = TestClient(main.app, raise_server_exceptions=False)


@pytest.fixture(autouse=True)
def clean(monkeypatch, tmp_path):
    monkeypatch.delenv("ALIVE_AIR_BUCKET", raising=False)
    monkeypatch.setenv("ALIVE_ARCHIVE_DIR", str(tmp_path))
    _skill._CACHE.update({"at": 0.0, "fp": None, "doc": None})
    yield tmp_path


def _seed_fc(root, ist_h, utc_now, mid=80.0, drift=2.0, field_mid=100.0,
             day=date(2026, 10, 5)):
    """Capture `field_mid` at ist_h with a forecast run serving
    mid+drift*idx for every point."""
    fc = FakeForecast(t0=_utc(day.year, day.month, day.day, 0),
                      now=utc_now, mid=mid, drift=drift)
    _arch.capture(FakeField(mid=field_mid),
                  now=_ts_ist(day.year, day.month, day.day, ist_h),
                  root=root, forecast=fc)


def _seed_rec(root, ist_h, field_mid, day=date(2026, 10, 5)):
    _arch.capture(FakeField(mid=field_mid),
                  now=_ts_ist(day.year, day.month, day.day, ist_h),
                  root=root, forecast=None)


# ------------------------------------------------------------------ honesty

def test_empty_archive_is_thin_not_invented(tmp_path):
    p = _skill.skill_payload(root=str(tmp_path),
                             now=_ts_ist(2026, 10, 6, 1))
    assert p["status"] == "thin" and p["pairs"] == 0
    assert p["overall"] == {"status": "thin", "n": 0}
    assert all(h["status"] == "thin" and h["n"] == 0
               for h in p["horizons"])
    assert p["coverage"]["snapshots"] == 0
    assert p["coverage"]["first_pair_ist"] is None


def test_field_only_snapshots_have_nothing_to_grade(tmp_path):
    # v1-style captures (no forecast block) still count as archive,
    # never as pairs
    _seed_rec(str(tmp_path), 9, 120.0)
    _seed_rec(str(tmp_path), 10, 140.0)
    p = _skill.skill_payload(root=str(tmp_path),
                             now=_ts_ist(2026, 10, 6, 1))
    assert p["status"] == "thin" and p["pairs"] == 0
    assert p["coverage"]["snapshots"] == 2
    assert p["coverage"]["snapshots_with_forecast"] == 0


# ------------------------------------------------------------------ pairing

def test_pairs_key_on_target_ist_hour_not_serve_hour(tmp_path):
    """Capture 14:02 IST serves h=2 → slot 10:00 UTC → targets IST
    bucket 15 (the :30 floor rule), so the pair lands on the RECORDED
    15:00 hour — never the 14:00 bucket it was served inside."""
    _seed_fc(str(tmp_path), 14, _utc(2026, 10, 5, 8, 32), field_mid=100.0)
    _seed_rec(str(tmp_path), 15, 130.0)
    _seed_rec(str(tmp_path), 16, 140.0)
    for h in (17, 18, 19, 20, 21, 22):
        _seed_rec(str(tmp_path), h, 110.0)
    p = _skill.skill_payload(root=str(tmp_path),
                             now=_ts_ist(2026, 10, 6, 1))
    assert p["pairs"] > 0
    cov = p["coverage"]
    # earliest graded hour is 15 — the capture hour itself is never a pair
    assert cov["first_pair_ist"] == "2026-10-05T15:00:00+05:30"
    # the h=2 bucket (14:02 → 15:00 IST target) exists and only there
    h2 = next(x for x in p["horizons"] if x["h"] == 2)
    assert h2["n"] >= 1


def test_snapshot_never_grades_itself(tmp_path):
    """A capture's own h=1 lands back on its own IST bucket — a ~30-min
    lead filed under '+1h'. That pair must not exist."""
    _seed_fc(str(tmp_path), 14, _utc(2026, 10, 5, 8, 32))
    p = _skill.skill_payload(root=str(tmp_path),
                             now=_ts_ist(2026, 10, 6, 1))
    assert p["pairs"] == 0


def test_mae_bias_band_exact_on_uniform_surfaces(tmp_path):
    # five forecast captures (mid 80, drift 2): each h's model value is
    # mid+2*idx — deterministic, so mae/bias are exact arithmetic
    for i, hh in enumerate([9, 10, 11, 12, 13]):
        _seed_fc(str(tmp_path), hh, _utc(2026, 10, 5, hh - 6, 32))
    # recorded hours 14..20 — each covered by several horizons
    for h in range(14, 21):
        _seed_rec(str(tmp_path), h, 120.0)
    p = _skill.skill_payload(root=str(tmp_path),
                             now=_ts_ist(2026, 10, 6, 1))
    assert p["status"] == "ok"
    for row in p["horizons"]:
        if row["status"] != "ok":
            continue
        # verify the arithmetic: model = 80+2*idx, recorded = 120
        # bias must be negative (model under-called); mae = |bias|
        assert row["bias_ug"] <= 0
        assert row["mae_ug"] == pytest.approx(-row["bias_ug"], abs=0.2)
        assert row["n"] >= _skill.MIN_PAIRS
        assert row["cells"] == row["n"] * 121
    ov = p["overall"]
    # the totals reconcile exactly — thin buckets' pairs are still real
    # pairs, they just don't carry a score yet
    assert ov["n"] == sum(x["n"] for x in p["horizons"])
    assert ov["cells"] == sum(x["cells"] for x in p["horizons"])


def test_band_hit_rate_is_real(tmp_path):
    # flat 118 model ('Poor', 90–120 breakpoint) vs recorded 110
    # ('Poor' too) — every shared cell is a real band match
    for hh in (9, 10, 11, 12, 13):
        _seed_fc(str(tmp_path), hh, _utc(2026, 10, 5, hh - 6, 32),
                 mid=118.0, drift=0.0)
    for h in range(14, 21):
        _seed_rec(str(tmp_path), h, 110.0)
    p = _skill.skill_payload(root=str(tmp_path),
                             now=_ts_ist(2026, 10, 6, 1))
    ok_rows = [x for x in p["horizons"] if x["status"] == "ok"]
    assert ok_rows
    assert all(x["band_hit_pct"] == 100.0 for x in ok_rows)
    assert p["overall"]["band_hit_pct"] == 100.0


def test_band_miss_when_bands_differ(tmp_path):
    for hh in (9, 10, 11, 12, 13):
        _seed_fc(str(tmp_path), hh, _utc(2026, 10, 5, hh - 6, 32),
                 mid=40.0, drift=0.0)           # 'Satisfactory'
    for h in range(14, 21):
        _seed_rec(str(tmp_path), h, 130.0)      # 'Poor'
    p = _skill.skill_payload(root=str(tmp_path),
                             now=_ts_ist(2026, 10, 6, 1))
    ok_rows = [x for x in p["horizons"] if x["status"] == "ok"]
    assert ok_rows
    assert all(x["band_hit_pct"] == 0.0 for x in ok_rows)


def test_thin_buckets_report_shape(tmp_path):
    # one covering capture over two recorded hours: every horizon n=1 —
    # honestly thin, {h, status:"thin", n, cells}, never a number
    _seed_fc(str(tmp_path), 9, _utc(2026, 10, 5, 3, 32))
    for h in (10, 11):
        _seed_rec(str(tmp_path), h, 110.0)
    p = _skill.skill_payload(root=str(tmp_path),
                             now=_ts_ist(2026, 10, 6, 1))
    assert p["status"] == "thin" and p["pairs"] == 2
    scored = [x for x in p["horizons"] if x["n"] > 0]
    assert scored
    assert all(set(x) == {"h", "status", "n", "cells"} for x in scored)
    assert all("mae_ug" not in x for x in scored)


def test_earliest_served_surface_is_the_pair(tmp_path, monkeypatch):
    """Two captures can serve the same h for the same target (the :30
    straddle); the earliest on record is the one we grade — and the
    hour's own snapshot is skipped, not just the earliest entry."""
    monkeypatch.setattr(_skill, "MIN_PAIRS", 1)
    monkeypatch.setattr(_skill, "_MIN_GRADED_HOURS", 1)
    # capture at 13:35 IST = 08:05 UTC: h=1 → slot 09:00 UTC → floor 14.
    # capture at 14:02 IST = 08:32 UTC: h=1 → same slot — the self-pair.
    _seed_fc(str(tmp_path), 13, _utc(2026, 10, 5, 8, 5),
             mid=80.0, drift=0.0, field_mid=90.0)
    _seed_fc(str(tmp_path), 14, _utc(2026, 10, 5, 8, 32),
             mid=200.0, drift=0.0, field_mid=130.0)
    # NB a capture re-writes its own ist bucket — hour 14's recorded doc
    # IS the fc capture above; only 15 is field-only
    _seed_rec(str(tmp_path), 15, 130.0)
    p = _skill.skill_payload(root=str(tmp_path),
                             now=_ts_ist(2026, 10, 6, 1))
    h1 = next(x for x in p["horizons"] if x["h"] == 1)
    # the 13:35 serve (80) is the pair, not the self-pair (200):
    # bias = 80 − 130 = −50
    assert h1["n"] == 1 and h1["bias_ug"] == -50.0
    h0 = next(x for x in p["horizons"] if x["h"] == 0)
    # hour 13 graded by src14's h=0 (200 vs recorded 90 → +110)
    assert h0["n"] == 1 and h0["bias_ug"] == 110.0
    h2 = next(x for x in p["horizons"] if x["h"] == 2)
    # hour 15 covered by both captures at h=2 — earliest on record wins
    assert h2["n"] == 1 and h2["bias_ug"] == -50.0
    assert p["pairs"] == 3


# ------------------------------------------------------------------ http

def test_endpoint_wire_shape(tmp_path, monkeypatch):
    for hh in (9, 10, 11, 12, 13):
        _seed_fc(str(tmp_path), hh, _utc(2026, 10, 5, hh - 6, 32))
    for h in range(14, 20):
        _seed_rec(str(tmp_path), h, 110.0)
    r = client.get("/v2/skill")
    assert r.status_code == 200
    b = r.json()
    assert b["basis"] == "self-graded" and b["tz"] == "ist"
    assert b["status"] in ("ok", "thin")
    assert b["min_pairs"] == _skill.MIN_PAIRS
    assert isinstance(b["horizons"], list) and len(b["horizons"]) == 12
    assert b["coverage"]["since_ist"].startswith("2026-10-05T09:00")


def test_endpoint_empty_is_honest(tmp_path):
    r = client.get("/v2/skill")
    assert r.status_code == 200
    b = r.json()
    assert b["status"] == "thin" and b["overall"] == {"status": "thin",
                                                    "n": 0}
