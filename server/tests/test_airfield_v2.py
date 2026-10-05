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
import asyncio
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


# ------------------------------------------------- station debias scope

def _debias_samples():
    """10 model lattice points (full CAMS dict) + 9 instruments (pm2_5
    only) on the same grid, instruments reading ~3x the model — matches
    tonight's real CAMS under-read. Returns (results, stations)."""
    model = [(28.55 + 0.01 * i, 77.15 + 0.01 * i, f"m{i}",
              {"pm2_5": 50.0, "pm10": 170.0, "ozone": 190.0,
               "nitrogen_dioxide": 12.0, "us_aqi": 150.0,
               "dust": 80.0, "aerosol_optical_depth": 0.7})
             for i in range(10)]
    inst = [(28.551 + 0.01 * i, 77.151 + 0.01 * i, f"st{i}",
             {"pm2_5": 150.0}) for i in range(9)]
    return model, inst


def test_debias_scales_pm25_only_pm10_gets_fine_fraction():
    """The instrument-measured bias is a PM2.5 fact: it must lift pm2_5
    multiplicatively and pm10 only by the fine-fraction increment —
    gases, dust, aod and the AQI indices carry no instrument evidence
    and stay raw CAMS."""
    f = airfield.AirField()
    model, inst = _debias_samples()
    out = f._debias(model, inst)
    adj = dict(out[0][3])
    assert adj["pm2_5"] == pytest.approx(150.0, rel=0.02)          # ×3
    # pm10: raw 170 + fine increment 50*(3-1) = 270, NOT 170*3 = 510
    assert adj["pm10"] == pytest.approx(270.0, rel=0.02)
    # raw everywhere there is no instrument evidence
    assert adj["ozone"] == pytest.approx(190.0, rel=1e-6)
    assert adj["nitrogen_dioxide"] == pytest.approx(12.0, rel=1e-6)
    assert adj["us_aqi"] == pytest.approx(150.0, rel=1e-6)   # index ≠ µg/m³
    assert adj["dust"] == pytest.approx(80.0, rel=1e-6)
    assert adj["aerosol_optical_depth"] == pytest.approx(0.7, rel=1e-6)


def test_debias_instrument_rows_untouched():
    f = airfield.AirField()
    model, inst = _debias_samples()
    out = f._debias(model, inst)
    inst_row = out[-1]
    assert inst_row[3] == {"pm2_5": 150.0}


def test_debias_multiparam_station_untouched_and_not_model():
    """A station carrying pm10/gases alongside pm2_5 is still an
    instrument row: it must feed the bias measurement (via pm2_5), never
    be scaled as if it were a model point, and keep every param it
    measured. (Before the tail-index split, the keys=={pm2_5} filter
    misclassified multi-param stations as model and re-scaled them.)"""
    f = airfield.AirField()
    model, inst = _debias_samples()
    inst = [(lat, lon, n, {**v, "pm10": 120.0, "ozone": 30.0})
            for lat, lon, n, v in inst]
    out = f._debias(model, inst)
    # model pm2_5 still lifted by the measured ~3x bias
    assert out[0][3]["pm2_5"] == pytest.approx(150.0, rel=0.02)
    # the multi-param station row survives verbatim
    assert out[-1][3] == {"pm2_5": 150.0, "pm10": 120.0, "ozone": 30.0}


def test_debias_station_without_pm25_does_not_count_as_instrument():
    """A pm10-only station grounds pm10 via the blend but cannot feed
    the pm2_5 bias measurement — the <8-instruments guard must see the
    real instrument count."""
    f = airfield.AirField()
    model, _inst = _debias_samples()
    thin_inst = _inst[:7] + [_inst[7][:3] + ({"pm10": 90.0},),
                             _inst[8][:3] + ({"pm10": 80.0},)]
    out = f._debias(model, thin_inst)
    # only 7 pm2_5 instruments -> no scaling
    assert out[0][3]["pm2_5"] == pytest.approx(50.0, rel=1e-6)
    # but the pm10-only rows still made it into the blend untouched
    assert out[-1][3]["pm10"] == 80.0


def test_debias_pm10_scales_multiplicatively_when_instruments_carry_it():
    """With ≥8 pm10 instruments the coarse fraction gets its own bias
    pass — tonight's real divergence: stations ~60-136µg vs CAMS
    300-600, the additive fine-fraction transfer could never fix the
    coarse residue."""
    f = airfield.AirField()
    model = [(28.55 + 0.01 * i, 77.15 + 0.01 * i, f"m{i}",
              {"pm2_5": 50.0, "pm10": 340.0, "ozone": 190.0})
             for i in range(10)]
    inst = [(28.551 + 0.01 * i, 77.151 + 0.01 * i, f"st{i}",
             {"pm2_5": 150.0, "pm10": 120.0}) for i in range(9)]
    out = f._debias(model, inst)
    adj = out[0][3]
    assert adj["pm2_5"] == pytest.approx(150.0, rel=0.02)      # ×3
    # pm10: instrument/model ≈ 120/340 ≈ 0.35 — multiplicative, NOT
    # 340 + 50·(3-1) = 440 from the additive fallback
    assert adj["pm10"] == pytest.approx(120.0, rel=0.05)
    assert adj["ozone"] == pytest.approx(190.0, rel=1e-6)      # untouched


def test_debias_pm10_additive_fallback_when_instruments_lack_it():
    """Fixture stations carry pm2_5 only → pm10 keeps the fine-fraction
    increment rather than going unscaled or fabricating a bias."""
    f = airfield.AirField()
    model, inst = _debias_samples()
    out = f._debias(model, inst)
    assert out[0][3]["pm10"] == pytest.approx(270.0, rel=0.02)


def test_debias_missing_pm10_or_pm25_never_fabricates():
    """A model point without pm2_5 must not invent a pm10 increment."""
    model = [(28.55 + 0.01 * i, 77.15 + 0.01 * i, f"m{i}",
              {"pm10": 170.0, "ozone": 190.0}) for i in range(10)]
    inst = [(28.551 + 0.01 * i, 77.151 + 0.01 * i, f"st{i}",
             {"pm2_5": 150.0}) for i in range(9)]
    # without model pm2_5 the bias cannot be measured -> raw pass-through
    f = airfield.AirField()
    out = f._debias(model, inst)
    assert out[0][3]["pm10"] == 170.0 and out[0][3]["ozone"] == 190.0


# --- wind retry cadence ----------------------------------------------------
def test_wind_retries_on_own_cadence_not_field_ttl(monkeypatch):
    """wind.known:false used to ride only the 15-min field fetch — a
    short upstream blip read as ~45 min unknown on live. An expired wind
    now retries inside every refresh() call once WIND_RETRY_S has passed,
    while the samples themselves sit fresh inside their TTL."""
    f = airfield.AirField()
    f._samples = [(28.61, 77.21, None, {"pm2_5": 50.0})]
    f._fetched_at = time.time()          # fresh: refresh() early-returns
    f._next_snap_scan = time.time() + 3600
    calls = []

    async def _grab(client):
        calls.append(1)
        f._wind_try_at = time.time()     # the real grab stamps at its top
    monkeypatch.setattr(f, "_grab_wind", _grab)

    asyncio.run(f.refresh(object()))
    assert calls == [1]                  # expired wind retried despite fresh TTL
    asyncio.run(f.refresh(object()))
    assert calls == [1]                  # gate: < WIND_RETRY_S since last attempt
    f._wind_try_at -= airfield.WIND_RETRY_S + 1
    asyncio.run(f.refresh(object()))
    assert calls == [1, 1]               # next try once the cadence opens


def test_wind_failure_stays_unknown_and_never_kills_refresh():
    """A dead/garbled met upstream leaves wind honestly unknown — and
    refresh() must finish normally (the met fetch used to share the
    field's exception path)."""
    f = airfield.AirField()
    f._samples = [(28.61, 77.21, None, {"pm2_5": 50.0})]
    f._fetched_at = time.time()
    f._next_snap_scan = time.time() + 3600

    class _C:  # non-httpx failure — e.g. a 502 HTML page failing .json()
        async def get(self, *a, **k):
            raise ValueError("not json")
        def raise_for_status(self):
            pass

    asyncio.run(f.refresh(_C()))         # must not raise
    assert f.wind()["known"] is False    # honest unknown, not fabricated calm
    assert f._wind_try_at > 0            # the attempt counted (no hammering)


def test_wind_known_until_two_cycles_then_expired():
    """known boundary = last successful fetch within two refresh cycles —
    the same boundary the retry gate uses."""
    f = airfield.AirField()
    f._wind = (12.0, 300.0)
    f._wind_at = time.time()
    assert f.wind()["known"] is True and not f._wind_expired()
    f._wind_at = time.time() - (2 * airfield.CACHE_TTL + 61)
    assert f.wind()["known"] is False and f._wind_expired()
