"""Parity tests — C++ tick-level series kernels vs the Python modules.

Two kernels added on r5/core-cpp (docs/plan/04 §5 live-counter contract):

  alive_core.dose_series(pm25, dt_s, ventilation_lpm, microenv) -> µg
      exposure.dose's accumulation loop in flat series form — non-finite
      concentrations skipped (uncovered field), c < 0 clamped to 0,
      c_eff = c*microenv, ve = ve_lpm/1000, dose += c_eff*ve*dt_min.

  alive_core.emission_g_km(mode, speed_kmh) -> g/km band
      ef_g_km(vehicle, v) of the strip contract: the mode's resolved
      emission_factors() fleet-prior band x speed_factor(v) with the
      speed-uncertainty widening (lo*f/sw, mid*f, hi*f*sw), v floored at
      V_FLOOR_MPS. The C++ mode table is generated from emissions.py at
      configure time — this file proves the whole chain to 1e-9.

Parity convention (docs/plan/08): 1e-9 relative for magnitudes, absolute
for near-zero fields; accumulations run in the same association order,
so values are expected bit-identical in practice.
"""
import math
import os
import random
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_SERVER = os.path.dirname(_HERE)
for _p in (_SERVER, os.path.join(_SERVER, "core"),
           os.path.join(_SERVER, "core", "build")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import emissions           # noqa: E402  production emissions engine
import exposure            # noqa: E402  production dose engine
import ref_series          # noqa: E402  oracle (server/core/ref_series.py)

cpp = pytest.importorskip(
    "alive_core", reason="C++ module not built (server/core/build)")

REL = 1e-9
POLS = ("co2", "pm25", "nox")
REF_KMH = emissions.REF_SPEED_MPS * 3.6    # 30.0 — curve is 1.0 here


def _close(a, b, label=""):
    assert math.isclose(a, b, rel_tol=REL, abs_tol=1e-12), \
        f"{label}: {a} vs {b}"


def _close_band(c_band, p_band, label=""):
    for i in range(3):
        _close(c_band[i], p_band[i], f"{label}[{i}]")


# ------------------------------------------------------------------ dose

def _rand_conc(rng):
    """One pm25 tick — with None/NaN/inf/negative holes like a real field."""
    r = rng.random()
    if r < 0.10:
        return None
    if r < 0.16:
        return float("nan")
    if r < 0.20:
        return float("inf")
    if r < 0.28:
        return rng.uniform(-50, -0.1)            # krige dip below zero
    return rng.uniform(0, 500)


def _rand_series(rng, n=None):
    return [_rand_conc(rng)
            for _ in range(n if n is not None else rng.randint(0, 40))]


def _rand_dts(rng, n):
    return [rng.choice([0.5, 1.0, 2.5, 5.0, 10.0]) if rng.random() < 0.9
            else rng.choice([float("nan"), -1.0, 0.0])
            for _ in range(n)]


def test_dose_series_scalar_dt_parity():
    rng = random.Random(108)
    for _ in range(2000):
        pm = _rand_series(rng)
        dt = rng.uniform(0, 120)
        ve = rng.choice([7.5, 8.0, 9.0, 14.0, 22.0])
        me = rng.choice([0.45, 0.7, 1.0, 1.15])
        rc = cpp.dose_series(pm, dt, ve, me)
        rp = ref_series.dose_series(pm, dt, ve, me)
        _close(rc, rp, "scalar dt")


def test_dose_series_per_sample_dt_parity():
    rng = random.Random(208)
    for _ in range(2000):
        pm = _rand_series(rng)
        dts = _rand_dts(rng, len(pm))
        rc = cpp.dose_series(pm, dts, 14.0, 1.0)
        rp = ref_series.dose_series(pm, dts, 14.0, 1.0)
        _close(rc, rp, "per-sample dt")


def test_dose_series_vs_exposure_dose():
    """End-to-end: exposure.dose's rounded output vs the unrounded kernel.

    A straight polyline is sampled by exposure.segment_samples; the same
    samples' seconds are the dt vector, a fixed concentration series is
    fed through field_value in call order. C++/oracle track the
    unrounded integral; exposure rounds dose_ug to 0.1 — compare within
    that rounding to prove identical semantics, not a coincidence of
    magnitudes.
    """
    rng = random.Random(7)
    for _ in range(300):
        k = rng.randint(2, 20)
        # straight-ish east-west polyline inside the bbox
        lon1, lat1 = 76.8, 28.5
        coords = [[lon1 + i * 0.01 + rng.gauss(0, 0.001),
                   lat1 + rng.gauss(0, 0.001)] for i in range(k + 1)]
        geom = {"type": "LineString", "coordinates": coords}
        dur = rng.uniform(60, 3600)
        samples = exposure.segment_samples(geom, dur)
        if not samples:
            continue
        pm = _rand_series(rng, len(samples))
        it = iter(pm)
        out = exposure.dose(
            geom, dur, "walking",
            lambda _la, _lo: next(it, None))
        rc = cpp.dose_series(pm, [s["seconds"] for s in samples],
                             exposure.VENTILATION_LPM["walking"],
                             exposure.MICROENV["walking"])
        rp = ref_series.dose_series(pm, [s["seconds"] for s in samples],
                                    exposure.VENTILATION_LPM["walking"],
                                    exposure.MICROENV["walking"])
        _close(rc, rp, "kernel vs oracle")
        if out["dose_ug"] is None:
            # exposure reports None when nothing hit the field; the flat
            # kernel reports 0.0 — same 'no dose' semantics
            assert rc == 0.0
        else:
            # round(x, 1) moves a value by at most 0.05
            assert abs(rc - out["dose_ug"]) <= 0.0500001


def test_dose_series_edge_cases():
    assert cpp.dose_series([], 1.0, 14.0, 1.0) == 0.0
    assert cpp.dose_series([], [], 14.0, 1.0) == 0.0
    assert cpp.dose_series([None, float("nan")], 1.0, 14.0, 1.0) == 0.0
    assert cpp.dose_series([100.0], None, 14.0, 1.0) == 0.0   # dt=None
    assert cpp.dose_series([100.0], [float("nan")], 14.0, 1.0) == 0.0
    assert cpp.dose_series([100.0], [-5.0], 14.0, 1.0) == 0.0  # neg dt
    assert cpp.dose_series([-30.0], 60.0, 14.0, 1.0) == 0.0    # neg c
    # zip truncation: shorter dt limits the sum; same for longer dt
    a = cpp.dose_series([100.0, 200.0, 300.0], [60.0], 14.0, 1.0)
    b = cpp.dose_series([100.0], 60.0, 14.0, 1.0)
    assert a == b == ref_series.dose_series([100.0], 60.0, 14.0, 1.0)
    # non-finite factors pass NaN through, like the Python loop
    assert math.isnan(cpp.dose_series([100.0], 60.0,
                                      float("nan"), 1.0))
    assert math.isnan(ref_series.dose_series([100.0], 60.0,
                                             float("nan"), 1.0))


def test_dose_series_exposure_mode_factors():
    """Every exposure mode: kernel with its tabled factors == oracle."""
    for mode in ("metro", "driving_car_ac", "bus", "auto_rickshaw",
                 "cycling", "walking"):
        fac = exposure.mode_factors(mode)
        pm = [250.0, 40.0, None, -12.0, 88.5]
        dts = [30.0, 45.0, 60.0, 60.0, 15.0]
        rc = cpp.dose_series(pm, dts, fac["ventilation_lpm"],
                             fac["microenv"])
        rp = ref_series.dose_series(pm, dts, fac["ventilation_lpm"],
                                    fac["microenv"])
        _close(rc, rp, mode)


# -------------------------------------------------------------- emissions

def test_emission_g_km_all_modes_all_speeds():
    speeds = [0.0, 1.0, 5.0, 9.0, 15.0, REF_KMH, 40.0, 50.0,
              80.0, 120.0, 180.0]
    for mode in ref_series.EMISSION_CLASSES:
        for v in speeds:
            rc = cpp.emission_g_km(mode, v)
            rp = ref_series.emission_g_km(mode, v)
            assert rc["mode"] == rp["mode"] == mode
            assert rc["units"] == rp["units"]
            for p in POLS:
                _close_band(rc[p], rp[p], f"{mode}@{v}kmh {p}")


def test_emission_g_km_aliases():
    for alias, canon in sorted(ref_series.EMISSION_MODE_ALIASES.items()):
        for v in (0.0, REF_KMH, 72.0):
            rc = cpp.emission_g_km(alias, v)
            rp = ref_series.emission_g_km(alias, v)
            assert rc["mode"] == canon == rp["mode"]
            for p in POLS:
                _close_band(rc[p], rp[p], f"{alias}@{v} {p}")


def test_emission_g_km_case_and_space():
    """_resolve() lower()+strip()s the class — the kernel must too."""
    a = cpp.emission_g_km("  Car ", 50.0)
    b = cpp.emission_g_km("car", 50.0)
    assert a == b
    c = cpp.emission_g_km("AUTO_RICKSHAW", 50.0)
    assert c["mode"] == "auto"


def test_emission_g_km_ref_speed_is_table():
    """At the MIDC reference speed the curve is exactly the resolved band
    (f = 1, sw = 1) — pins the generated table to emission_factors."""
    for cls in ref_series.EMISSION_CLASSES:
        ef = emissions.emission_factors({"class": cls})
        rc = cpp.emission_g_km(cls, REF_KMH)
        for p in POLS:
            assert rc[p] == (ef[p]["lo"], ef[p]["mid"], ef[p]["hi"]), \
                f"{cls} {p}: {rc[p]} vs {ef[p]}"


def test_emission_g_km_floor_clamping():
    """Identical clamping: below V_FLOOR (2.5 m/s = 9 km/h) the curve is
    pinned — 0 km/h, 5 km/h and 9 km/h all give the same factor."""
    for mode in ("car", "bus", "auto"):
        lo = cpp.emission_g_km(mode, 0.0)
        mid = cpp.emission_g_km(mode, 5.0)
        at = cpp.emission_g_km(mode, 9.0)
        assert lo == mid == at
        rp = ref_series.emission_g_km(mode, 0.0)
        for p in POLS:
            _close_band(lo[p], rp[p], f"{mode} floor {p}")
    # negative speed is floored identically on both sides
    assert cpp.emission_g_km("car", -20.0) == \
        cpp.emission_g_km("car", 0.0)
    rc = cpp.emission_g_km("car", -20.0)
    rp = ref_series.emission_g_km("car", -20.0)
    for p in POLS:
        _close_band(rc[p], rp[p], "neg speed")


def test_emission_g_km_above_vopt():
    """Above V_OPT the curve rises quadratically; sanity-order the band."""
    slow = cpp.emission_g_km("car", 30.0)
    fast = cpp.emission_g_km("car", 120.0)
    assert fast["co2"][1] > slow["co2"][1]
    # speed-uncertainty widening: hi/lo spread grows away from ref speed
    spread_slow = slow["co2"][2] / slow["co2"][0]
    spread_fast = fast["co2"][2] / fast["co2"][0]
    assert spread_fast > spread_slow


def test_emission_g_km_metro_speed_invariant():
    a = cpp.emission_g_km("metro", 0.0)
    b = cpp.emission_g_km("metro", 120.0)
    assert a == b
    assert a["units"] == "g/pkm"
    assert a["co2"] == emissions.METRO_CO2E_GPKM
    rp = ref_series.emission_g_km("metro", 60.0)
    for p in POLS:
        _close_band(a[p], rp[p], f"metro {p}")


def test_emission_g_km_nonmotor_zero():
    for mode in ("walk", "cycle", "walking", "bicycle"):
        rc = cpp.emission_g_km(mode, 25.0)
        assert rc["co2"] == rc["pm25"] == rc["nox"] == (0.0, 0.0, 0.0)


def test_emission_g_km_unknown_mode():
    for bad in ("spaceship", "", "  ", "carr", "e-rickshaw"):
        with pytest.raises(ValueError):
            cpp.emission_g_km(bad, 30.0)
        with pytest.raises(ValueError):
            ref_series.emission_g_km(bad, 30.0)


def test_emission_g_km_nan_speed():
    """NaN speed propagates through the curve on both sides (Python's
    max(nan, floor) is NaN; std::max matches)."""
    rc = cpp.emission_g_km("car", float("nan"))
    rp = ref_series.emission_g_km("car", float("nan"))
    for p in POLS:
        for i in range(3):
            assert math.isnan(rc[p][i])
            assert math.isnan(rp[p][i])


def test_emission_g_km_vs_production_integrate():
    """Cross-check the curve against emissions.integrate on one moving
    span: 1 km at speed v (warm — cold_km_done past COLD_KM) yields
    exactly ef(v) grams per pollutant, occupancy-divided for shared
    modes. integrate() composes UNROUNDED bands while emission_factors()
    (the public/strip contract this lookup mirrors) rounds to 4 decimals
    — so the comparison tolerance is the band's own 5e-5 rounding
    propagated through the speed factor, plus integrate()'s 4-decimal
    output rounding."""
    rng = random.Random(42)
    for cls in ("car", "cab", "auto", "bus", "bike"):
        veh = {"class": cls}
        occ = emissions._occupancy(cls)
        for _ in range(12):
            v = rng.uniform(0.0, 30.0)      # m/s
            spans = [{"dist_m": 1000.0, "speed_mps": v, "moving": True}]
            prod = emissions.integrate(
                veh, spans, cold_km_done=emissions.COLD_KM)
            rc = cpp.emission_g_km(cls, v * 3.6)
            # 1 km at ef(v): prod = ef(v)/occ; ours is the vehicle-level
            # ef(v) -> divide by occupancy to compare
            pairs = (("co2", "co2_kg", 1000.0), ("pm25", "pm25_g", 1.0),
                     ("nox", "nox_g", 1.0))
            for pol, key, scale in pairs:
                f = emissions.speed_factor(pol, v)
                sw = 1.0 + 0.2 * abs(f - 1.0)
                # table band rounding (5e-5/edge) amplified by f*sw (hi
                # edge carries the sw factor), /occ, + the production
                # output's own 4-decimal rounding
                tol = 5e-5 * f * sw / occ / scale + 5e-5
                for i, edge in enumerate(("lo", "mid", "hi")):
                    got = rc[pol][i] / occ / scale
                    want = prod[key][edge]
                    assert abs(got - want) <= tol + 1e-9 * abs(want), \
                        f"{cls}@{v} {pol}.{edge}: {got} vs {want}"
