"""Tests for rollup v2 — daily percentile bands + weighted city summary,
weekly leave-one-station-out folds with lo-hi band coverage, and honest
skip accounting for corrupt/missing inputs.

Everything is synthetic: snapshots are hand-built airindex-shaped field
dicts serialized through airindex.serialize, so no network, h3, or numpy
is needed. validate_field is stubbed via sys.modules for weekly tests.

Run from server/:  python3 -m pytest tests/test_rollup_v2.py
"""
import json
import os
import sys
import types
from datetime import date, datetime, timedelta, timezone

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(_HERE))                 # server/
sys.path.insert(0, os.path.dirname(os.path.dirname(_HERE)))  # repo root

import airindex              # noqa: E402
import rollup                # noqa: E402

WEEK = "2026-W41"
MON = date.fromisocalendar(2026, 41, 1)        # 2026-10-05
DAY = MON + timedelta(days=1)                   # snapshot day inside week
DAY_S = DAY.strftime("%Y-%m-%d")
DAY_P = DAY.strftime("%Y/%m/%d")
E0 = datetime(DAY.year, DAY.month, DAY.day, 6, 0,
              tzinfo=timezone.utc).timestamp()  # 06:00 UTC


def _field(pm_by_cell, epoch, stations=None, vc=1800.0):
    """Minimal airindex-schema field: pm25 with a ±5 µg/m³ model band."""
    cells = {}
    for cid, v in pm_by_cell.items():
        cells[cid] = {"pm25": v, "lo": v - 5.0, "hi": v + 5.0,
                      "sigma": 2.5, "n_stations_within_10km": 1,
                      "nearest_station_km": 0.5, "src": "station"}
    return {"schema": "alive-airindex/1",
            "built_at": datetime.fromtimestamp(
                epoch, tz=timezone.utc).isoformat(timespec="seconds"),
            "built_epoch": epoch,
            "met": {"vc_m2s": vc},
            "stations": stations or [],
            "cells": cells}


def _snap(root, ymd_path, hhmm, field):
    p = root / ymd_path / f"{hhmm}.json.gz"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(airindex.serialize(field))
    return p


def _stations(n=6):
    """Stations with a smooth residual surface (resid = pm25 - prior).
    base prior 40 everywhere so folds reconstruct obs = prior + resid."""
    out = []
    for i in range(n):
        lat = 28.30 + 0.12 * i
        lon = 76.90 + 0.15 * i
        resid = round(2.0 * (lat - 28.5) + (lon - 77.2), 3)
        out.append({"name": f"S{i}", "lat": lat, "lon": lon,
                    "pm25": round(40.0 + resid, 2), "residual": resid})
    return out


def _write_day(root):
    """3 snapshots on DAY: c1=[10,20,30] c2=[100,200,300] c3=[50,50,50]."""
    vals = [{"c1": 10.0, "c2": 100.0, "c3": 50.0},
            {"c1": 20.0, "c2": 200.0, "c3": 50.0},
            {"c1": 30.0, "c2": 300.0, "c3": 50.0}]
    for k, m in enumerate(vals):
        _snap(root, DAY_P, f"{6 + k:02d}00",
              _field(m, E0 + 3600 * k, vc=1000.0 + 500 * k))


# ------------------------------------------------------------- daily v2

def test_daily_percentile_bands_and_city(tmp_path, monkeypatch):
    monkeypatch.delenv("ALIVE_AIR_BUCKET", raising=False)
    _write_day(tmp_path)
    ro = rollup.daily_rollup(DAY_S, snapshot_root=str(tmp_path),
                             daily_dir=str(tmp_path))
    assert ro["schema"] == "alive-rollup/2"
    assert ro["n_snapshots"] == 3
    c1 = ro["cells"]["c1"]
    # hand-computed on [10,20,30]: mean 20, linear p10=12 p50=20 p90=28
    assert c1["mean"] == 20.0 and c1["min"] == 10.0 and c1["max"] == 30.0
    assert c1["p10"] == pytest.approx(12.0)
    assert c1["p50"] == pytest.approx(20.0)
    assert c1["p90"] == pytest.approx(28.0)
    # mean of the ±5 model band edges
    assert c1["lo_mean"] == 15.0 and c1["hi_mean"] == 25.0
    assert c1["n_snapshots"] == 3 and c1["worst_hours"]
    city = ro["city"]
    # cell means [20,50,200]: median keeps the v1 (n//2) semantics
    assert city["median_pm25"] == 50.0
    assert city["pct_cells_gt15_who"] == 100.0
    assert city["pct_cells_gt60_cpcb"] == pytest.approx(33.3, abs=0.05)
    assert len(city["ventilation_m2s"]) == 3
    # weighted block — uniform-cells (doc 05 names no population proxy)
    assert city["weighting"] == "uniform-cells"
    assert city["weighted_mean_pm25"] == pytest.approx(90.0)
    assert city["weighted_median_pm25"] == pytest.approx(50.0)
    assert city["pm25_p10"] == 20.0 and city["pm25_p90"] == 200.0
    assert os.path.exists(ro["written_to"])


def test_daily_weighted_city_hook(tmp_path, monkeypatch):
    monkeypatch.delenv("ALIVE_AIR_BUCKET", raising=False)
    _write_day(tmp_path)
    ro = rollup.daily_rollup(DAY_S, snapshot_root=str(tmp_path),
                             daily_dir=str(tmp_path),
                             cell_weights={"c3": 10.0})
    city = ro["city"]
    assert city["weighting"] == "per-cell-weights"
    # only c3 (mean 50) carries weight -> weighted mean == 50
    assert city["weighted_mean_pm25"] == pytest.approx(50.0)
    assert city["median_pm25"] == 50.0   # unweighted stats untouched


def test_daily_corrupt_snapshots_counted(tmp_path, monkeypatch):
    monkeypatch.delenv("ALIVE_AIR_BUCKET", raising=False)
    _write_day(tmp_path)
    bad = tmp_path / DAY_P / "9999.json.gz"
    bad.write_bytes(b"this is not gzip at all")
    notfld = tmp_path / DAY_P / "9998.json.gz"
    notfld.write_bytes(airindex.serialize({"foo": 1}))
    ro = rollup.daily_rollup(DAY_S, snapshot_root=str(tmp_path),
                             daily_dir=str(tmp_path))
    assert ro["n_snapshots"] == 3                     # the day still rolls up
    assert ro["inputs"]["n_skipped"] == 2             # both counted, none invented
    reasons = {s["reason"] for s in ro["inputs"]["skipped"]}
    assert all(reasons)
    labels = {os.path.basename(s["snapshot"]) for s in ro["inputs"]["skipped"]}
    assert labels == {"9998.json.gz", "9999.json.gz"}


def test_daily_empty_day_is_honest(tmp_path, monkeypatch):
    monkeypatch.delenv("ALIVE_AIR_BUCKET", raising=False)
    ro = rollup.daily_rollup(DAY_S, snapshot_root=str(tmp_path),
                             daily_dir=str(tmp_path))
    assert ro["n_snapshots"] == 0 and ro["n_cells"] == 0
    assert ro["city"]["median_pm25"] is None
    assert ro["city"]["weighted_mean_pm25"] is None


# ------------------------------------------------------------- LOSO folds

def test_loso_fold_count_matches_stations():
    field = _field({"c1": 42.0}, E0, stations=_stations(6))
    res = rollup.loso_validation(field)
    assert res["status"] == "ok"
    assert res["n_folds"] == 6 == res["n"]
    assert len(res["per_station"]) == 6
    for r in res["per_station"]:
        for k in ("obs_ugm3", "pred_ugm3", "lo_ugm3", "hi_ugm3",
                  "err_ugm3", "in_band", "method"):
            assert k in r
        assert r["lo_ugm3"] <= r["pred_ugm3"] <= r["hi_ugm3"]
        assert r["method"] in ("krige", "idw-residual")
    # residual is nearly linear -> IDW residual prediction is close
    assert res["mae_ugm3"] < 5.0
    n_in = sum(r["in_band"] for r in res["per_station"])
    assert res["coverage_pct"] == pytest.approx(100.0 * n_in / 6)


def test_loso_unusable_stations_skipped_not_fabricated():
    sts = _stations(6)
    sts[2].pop("residual")            # unusable — counts as a skip
    field = _field({"c1": 42.0}, E0, stations=sts)
    res = rollup.loso_validation(field)
    assert res["status"] == "ok"
    assert res["n_folds"] == 5        # one fold per USABLE station only
    assert res["n_skipped"] == 1
    assert res["skipped"][0]["station"] == "S2"
    assert "residual" in res["skipped"][0]["reason"]


def test_loso_insufficient_stations_honest():
    res = rollup.loso_validation(_field({"c1": 1.0}, E0,
                                        stations=_stations(3)))
    assert res["status"] == "insufficient stations"
    assert res["n_folds"] == 0


# ------------------------------------------------------------- weekly

def _stub_validate(monkeypatch, pairs):
    fake = types.SimpleNamespace(
        validate=lambda hours_back=168: ({"s": {}}, pairs))
    monkeypatch.setitem(sys.modules, "validate_field", fake)


def test_weekly_report_schema_and_artifacts(tmp_path, monkeypatch):
    monkeypatch.delenv("ALIVE_AIR_BUCKET", raising=False)
    _stub_validate(monkeypatch, [("stn", "h", 100.0, 110.0, 108.0, 0.5)])
    snap_root = tmp_path / "snaps"
    valid_dir = tmp_path / "valid"
    good = _field({"c1": 42.0}, E0, stations=_stations(6))
    _snap(snap_root, DAY_P, "1200", good)
    # a NEWER but corrupt snapshot — must be skipped and counted
    nxt = (DAY + timedelta(days=1)).strftime("%Y/%m/%d")
    bad = snap_root / nxt / "0100.json.gz"
    bad.parent.mkdir(parents=True, exist_ok=True)
    bad.write_bytes(b"corrupt not gzip")

    out = rollup.weekly_validation(WEEK, snapshot_root=str(snap_root),
                                   valid_dir=str(valid_dir))
    for k in ("schema", "week", "generated", "snapshot", "snapshot_used",
              "snapshot_in_iso_week", "inputs", "loso",
              "archive_replay", "written_to", "summary_md"):
        assert k in out, k
    assert out["schema"] == "alive-validation/2"
    assert out["snapshot_in_iso_week"] is True
    assert out["inputs"]["n_skipped"] == 1
    assert out["inputs"]["skipped"][0]["snapshot"].endswith("0100.json.gz")
    assert out["loso"]["status"] == "ok" and out["loso"]["n_folds"] == 6
    assert 0.0 <= out["loso"]["coverage_pct"] <= 100.0
    assert out["archive_replay"]["status"] == "ok"
    assert out["archive_replay"]["mae_ugm3"] == pytest.approx(10.0)
    # machine report + compat copy + human summary all on disk
    for name in (f"weekly-{WEEK}.json", f"{WEEK}.json",
                 f"weekly-{WEEK}.md"):
        assert (valid_dir / name).exists(), name
    disk = json.loads((valid_dir / f"weekly-{WEEK}.json").read_text())
    assert disk["schema"] == "alive-validation/2"
    assert disk["loso"]["n_folds"] == 6
    md = (valid_dir / f"weekly-{WEEK}.md").read_text()
    assert "Leave-one-station-out" in md and "coverage" in md.lower()


def test_weekly_out_of_week_fallback_flagged(tmp_path, monkeypatch):
    monkeypatch.delenv("ALIVE_AIR_BUCKET", raising=False)
    _stub_validate(monkeypatch, [])
    snap_root = tmp_path / "snaps"
    old = (MON - timedelta(days=10)).strftime("%Y/%m/%d")  # before the week
    _snap(snap_root, old, "1200",
          _field({"c1": 42.0}, E0, stations=_stations(5)))
    out = rollup.weekly_validation(WEEK, snapshot_root=str(snap_root),
                                   valid_dir=str(tmp_path / "v"))
    assert out["snapshot_in_iso_week"] is False   # fallback used, flagged
    assert out["loso"]["status"] == "ok" and out["loso"]["n_folds"] == 5
    assert out["archive_replay"]["status"] == "no overlapping pairs"


def test_weekly_no_snapshot_at_all(tmp_path, monkeypatch):
    monkeypatch.delenv("ALIVE_AIR_BUCKET", raising=False)
    _stub_validate(monkeypatch, [])
    out = rollup.weekly_validation(WEEK, snapshot_root=str(tmp_path),
                                   valid_dir=str(tmp_path / "v"))
    assert out["loso"]["status"] == "no usable snapshot"
    assert out["loso"]["n_folds"] == 0
    assert os.path.exists(out["written_to"])
