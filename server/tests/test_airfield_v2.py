"""AirField v2 tests — snapshot load correctness, serving honesty, perf.

Covers the lane contract (docs/plan/05 §2/§6):
  - deterministic newest-snapshot selection (embedded generated_at stamp
    primary, file mtime the tie-break, path the last resort);
  - corrupt snapshots are skipped to next-newest with a warning count in
    status() — loading never crashes the app;
  - stale flag when the served field is older than the 45-min alarm
    threshold; sigma coverage said out loud, never implied;
  - out-of-coverage queries return None + status() carries the bounds;
  - value() lookups fast enough for /v2/strip (500-pt strip in ~5 ms).

All tests build fresh AirField() instances on tmp dirs — no network, no
module-FIELD state.
"""
import gzip
import inspect
import json
import os
import sys
import time

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import airfield  # noqa: E402

NOW = time.time()


def _cells(base=28.30, lon0=77.00, n=4, pm=100.0, sigma=10.0):
    """n x n g8-cell grid ~0.05 deg apart — dense enough for coverage."""
    out = {}
    sd = sigma if sigma is not None else 0.0
    for i in range(n):
        for j in range(n):
            c = {"pm25": pm + i + j / 10.0, "lo": pm - 1.96 * sd,
                 "hi": pm + 1.96 * sd, "src": "model"}
            if sigma is not None:
                c["sigma"] = sigma
            out[f"g8:{base + i * 0.05:.5f}:{lon0 + j * 0.05:.5f}"] = c
    return out


def _write_snap(root, name, cells, built_epoch=None, generated_at=None,
                built_at=None, mtime=None, raw=None):
    """Write one snapshot file; `raw` bypasses encoding (corrupt cases)."""
    p = root / name
    p.parent.mkdir(parents=True, exist_ok=True)
    if raw is not None:
        p.write_bytes(raw)
    else:
        f = {"schema": "alive-airindex/1", "cells": cells,
             "grid": {"system": "latlon-fallback",
                      "bbox": [76.75, 28.15, 77.95, 28.98]}}
        if built_epoch is not None:
            f["built_epoch"] = built_epoch
        if generated_at is not None:
            f["generated_at"] = generated_at
        if built_at is not None:
            f["built_at"] = built_at
        p.write_bytes(gzip.compress(json.dumps(f).encode("utf-8")))
    if mtime is not None:
        os.utime(p, (mtime, mtime))
    return p


def _field(root, warm=True):
    f = airfield.AirField()
    res = f.load_snapshot(snapshot_root=str(root), warm=warm)
    return f, res


# ------------------------------------------------- selection determinism

def test_embedded_stamp_beats_newer_mtime(tmp_path):
    """Newest data wins, not newest file: A copied later (fresh mtime,
    old embedded stamp) must lose to B (older mtime, newer build)."""
    _write_snap(tmp_path, "a/aa.json.gz", _cells(pm=100.0),
                built_epoch=NOW - 5000, mtime=NOW - 100)   # copied late
    _write_snap(tmp_path, "b/bb.json.gz", _cells(pm=222.0),
                built_epoch=NOW - 1200, mtime=NOW - 1000)  # built latest
    f, res = _field(tmp_path)
    assert res["loaded"] and res["path"].endswith("bb.json.gz")
    # exact cell center -> that cell's pm25 (piecewise-constant serving)
    assert f.value(28.30, 77.00) == pytest.approx(222.0, abs=0.01)


def test_mtime_then_path_tiebreak(tmp_path):
    """Same embedded stamp -> newer mtime wins; identical stamp+mtime ->
    lexicographically greater path wins (full determinism)."""
    _write_snap(tmp_path, "t/older.json.gz", _cells(pm=100.0),
                built_epoch=NOW - 100, mtime=NOW - 200)
    _write_snap(tmp_path, "t/newer.json.gz", _cells(pm=200.0),
                built_epoch=NOW - 100, mtime=NOW - 50)
    f, res = _field(tmp_path)
    assert res["path"].endswith("newer.json.gz")

    _write_snap(tmp_path, "u/aaa.json.gz", _cells(pm=100.0),
                built_epoch=NOW - 90, mtime=NOW - 40)
    _write_snap(tmp_path, "u/zzz.json.gz", _cells(pm=200.0),
                built_epoch=NOW - 90, mtime=NOW - 40)
    f2, res2 = _field(tmp_path)
    assert res2["path"].endswith("zzz.json.gz")


def test_generated_at_iso_stamp_used(tmp_path):
    """Files stamped only via embedded ISO `generated_at` still rank."""
    iso_old = "2020-01-01T00:00:00+00:00"
    _write_snap(tmp_path, "g/old.json.gz", _cells(pm=100.0),
                generated_at=iso_old, mtime=NOW - 10)
    _write_snap(tmp_path, "g/new.json.gz", _cells(pm=200.0),
                built_epoch=NOW - 60, mtime=NOW - 60)
    f, res = _field(tmp_path)
    assert res["path"].endswith("new.json.gz")


# --------------------------------------------------------- corrupt files

def test_corrupt_snapshot_skips_to_next_newest(tmp_path):
    """Garbage bytes, good-gzip-no-cells: both skipped, counted, no crash."""
    _write_snap(tmp_path, "s/0300.json.gz", None,
                raw=b"\x1f\x8bnot-really-gzip", mtime=NOW - 10)
    _write_snap(tmp_path, "s/0200.json.gz", {}, built_epoch=NOW - 100,
                mtime=NOW - 100)   # decodes but has no cells -> unusable
    _write_snap(tmp_path, "s/0100.json.gz", _cells(pm=140.0),
                built_epoch=NOW - 3000, mtime=NOW - 2900)
    f, res = _field(tmp_path)
    assert res["loaded"] and res["path"].endswith("0100.json.gz")
    st = f.status()
    assert st["load_warnings"] == 2
    assert st["serving"] == "snapshot"


def test_load_never_crashes(tmp_path):
    f = airfield.AirField()
    assert f.load_snapshot(snapshot_root=str(tmp_path))["loaded"] is False
    missing = tmp_path / "does-not-exist"
    assert f.load_snapshot(snapshot_root=str(missing))["loaded"] is False
    assert f.value(28.6, 77.2) is None  # still the honest empty field


# ------------------------------------------------------------- honesty

def test_stale_flag_past_45_min(tmp_path):
    """Doc 05 §6 alarm threshold: served data older than 45 min -> stale."""
    _write_snap(tmp_path, "x/old.json.gz", _cells(),
                built_epoch=NOW - 4000, mtime=NOW - 3900)
    f, _ = _field(tmp_path)
    st = f.status()
    assert st["serving"] == "snapshot"
    assert st["age_s"] >= 3900
    assert st["stale"] is True
    assert st["stale_after_s"] == 45 * 60

    _write_snap(tmp_path, "x/fresh.json.gz", _cells(),
                built_epoch=NOW - 60, mtime=NOW - 50)
    f2, _ = _field(tmp_path)
    assert f2.status()["stale"] is False


def test_out_of_coverage_returns_none_with_bounds(tmp_path):
    _write_snap(tmp_path, "c/c.json.gz", _cells(),
                built_epoch=NOW - 60, mtime=NOW - 50)
    f, _ = _field(tmp_path)
    assert f.value(51.50, -0.12) is None      # London: no cells anywhere
    assert f.sigma(51.50, -0.12) is None      # no fake precision either
    cov = f.status()["coverage"]
    w, s, e, n = cov["bbox"]
    assert w == 76.75 and s == 28.15 and e == 77.95 and n == 28.98
    assert cov["out_beyond_km"] == airfield._SNAP_COVER_KM


def test_sigma_coverage_is_said_not_implied(tmp_path):
    """Cells without sigma must surface in status(), never as a band."""
    cells = _cells(sigma=None)                      # no sigma anywhere
    cells["g8:28.35000:77.00000"]["sigma"] = 9.0    # exactly one cell has it
    _write_snap(tmp_path, "q/q.json.gz", cells,
                built_epoch=NOW - 60, mtime=NOW - 50)
    f, _ = _field(tmp_path)
    assert f.sigma(28.35, 77.00) == pytest.approx(9.0)
    assert f.sigma(28.30, 77.05) is None            # sigma-less cell -> None
    cov = f.status()["sigma_coverage"]
    assert cov.startswith("partial:")

    _write_snap(tmp_path, "q2/q2.json.gz", _cells(sigma=None),
                built_epoch=NOW - 30, mtime=NOW - 20)
    f2, _ = _field(tmp_path)
    assert f2.status()["sigma_coverage"] == "none"


def test_snapshot_carries_pm25_only(tmp_path):
    _write_snap(tmp_path, "p/p.json.gz", _cells(),
                built_epoch=NOW - 60, mtime=NOW - 50)
    f, _ = _field(tmp_path)
    assert f.value(28.32, 77.02) is not None
    assert f.value(28.32, 77.02, "pm10") is None    # honest: not covered
    assert f.value(28.32, 77.02, "nitrogen_dioxide") is None


def test_live_samples_win_when_fresher(tmp_path, monkeypatch):
    """After refresh() lands, the live layer serves — status quo for v1."""
    _write_snap(tmp_path, "m/m.json.gz", _cells(pm=200.0),
                built_epoch=NOW - 8000, mtime=NOW - 7900)
    f, _ = _field(tmp_path)
    monkeypatch.setattr(airfield.KF, "on", False)  # isolate from module state
    f._samples = [(28.30, 77.00, None, {"pm2_5": 30.0})]
    f._fetched_at = time.time()
    v = f.value(28.30, 77.00)
    assert v == pytest.approx(30.0)          # the live sample, not 200
    assert f.status()["serving"] == "live"


# --------------------------------------------------------------- perf

def test_warmed_index_identical_results(tmp_path):
    """The warmed index changes cost, never the answer."""
    _write_snap(tmp_path, "w/w.json.gz", _cells(n=6),
                built_epoch=NOW - 60, mtime=NOW - 50)
    fw, _ = _field(tmp_path, warm=True)
    fl, _ = _field(tmp_path, warm=False)
    import random
    random.seed(3)
    for _ in range(400):
        la = random.uniform(28.15, 28.98)
        lo = random.uniform(76.75, 77.95)
        assert fw.value(la, lo) == fl.value(la, lo)


def test_lookup_perf_10k_under_threshold():
    """10k value() lookups must beat 300 ms.

    Baseline measured on this box over the real 14,628-cell snapshot
    (2026-10-03): unwarmed linear scan ~18.8 s/10k; warmed index + memo
    ~136 ms/10k cold — threshold set at ~2x the measured warmed time.
    """
    f = airfield.AirField()
    res = f.load_snapshot(warm=True)
    if not res["loaded"]:
        pytest.skip("no snapshot on disk to bench against")
    import random
    random.seed(5)
    pts = [(random.uniform(28.15, 28.98), random.uniform(76.75, 77.95))
           for _ in range(10000)]
    t = time.perf_counter()
    for la, lo in pts:
        f.value(la, lo)
    dt = time.perf_counter() - t
    assert dt < 0.30, f"10k lookups took {dt*1000:.0f} ms (>300 ms)"


# ------------------------------------------------------ contract intact

def test_public_signatures_unchanged():
    sig = inspect.signature(airfield.AirField.value)
    assert list(sig.parameters) == ["self", "lat", "lon", "pollutant"]
    assert sig.parameters["pollutant"].default == "pm2_5"
    for m in ("sigma", "nearest_sample_km"):
        assert list(inspect.signature(
            getattr(airfield.AirField, m)).parameters) == ["self", "lat", "lon"]
    assert list(inspect.signature(
        airfield.AirField.status).parameters) == ["self"]
    assert inspect.iscoroutinefunction(airfield.AirField.refresh)


def test_empty_field_contract():
    """No samples, no snapshot: the old None/inf contract holds."""
    f = airfield.AirField()
    assert f.value(28.6, 77.2) is None
    assert f.sigma(28.6, 77.2) is None
    assert f.nearest_sample_km(28.6, 77.2) == float("inf")
    st = f.status()
    assert st["serving"] == "none" and st["stale"] is None
    for k in ("source", "samples", "station_readings", "age_s", "wind",
              "kriging"):  # pre-existing keys still present
        assert k in st


def test_real_snapshot_loads_clean():
    """The snapshot mirror in the repo loads with zero warnings."""
    f = airfield.AirField()
    res = f.load_snapshot()
    assert res["loaded"] and res["cells"] > 1000
    assert f.status()["load_warnings"] == 0
