"""Parity tests — C++ dose/emission integrators vs Python reference.

Dose: segment_samples + integrate_dose over generated NCR routes, incl.
edge cases (empty polyline, single point, route leaving field coverage).
Emissions: integrate_emissions over random span sets, plus a cross-check
against server/emissions.py's own integrate() (the production path).
Tolerance: search parity convention — 1e-9 (relative for dose/emission
magnitudes, absolute for near-zero fields); sums are Neumaier-matched so
values are expected bit-identical in practice.
"""
import glob
import gzip
import json
import math
import os
import random
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "core", "build"))

import alive_core_ref as ref  # noqa: E402
import emissions  # noqa: E402

SERVER_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SNAP_DIR = os.path.join(SERVER_DIR, "data", "field", "snapshots")
BBOX = (76.75, 28.15, 77.95, 28.98)  # lon_min, lat_min, lon_max, lat_max
REL = 1e-9
MODES = ["metro", "driving_car_ac", "driving_car_open", "bus",
         "driving_two_wheeler", "auto_rickshaw", "cycling", "walking"]


def _latest_snapshot():
    files = sorted(glob.glob(os.path.join(SNAP_DIR, "**", "*.json.gz"),
                             recursive=True))
    assert files
    with gzip.open(files[-1], "rt", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def rows():
    return ref.field_rows(_latest_snapshot())


@pytest.fixture(scope="module")
def py_fv(rows):
    return ref.PyFieldView(rows)


@pytest.fixture(scope="module")
def cpp_fv(rows):
    cpp = pytest.importorskip(
        "alive_core", reason="C++ module not built (server/core/build)")
    return cpp.FieldView(rows)


@pytest.fixture(scope="module")
def cpp_mod():
    return pytest.importorskip(
        "alive_core", reason="C++ module not built (server/core/build)")


def _route(rng, off_field_prob=0.15):
    """A-to-B polyline with jittered waypoints; coords are [lon, lat]."""
    w, s, e, n = BBOX
    pad = 0.12 if rng.random() < off_field_prob else 0.0
    lon1 = w - pad + rng.random() * (e - w + 2 * pad)
    lat1 = s - pad + rng.random() * (n - s + 2 * pad)
    lon2 = w - pad + rng.random() * (e - w + 2 * pad)
    lat2 = s - pad + rng.random() * (n - s + 2 * pad)
    k = rng.randint(2, 40)
    coords = []
    for i in range(k + 1):
        t = i / k
        coords.append([
            lon1 + (lon2 - lon1) * t + rng.gauss(0, 0.004),
            lat1 + (lat2 - lat1) * t + rng.gauss(0, 0.004)])
    return coords


def _routes(n, seed=108):
    rng = random.Random(seed)
    return [(_route(rng), rng.uniform(300, 3600)) for _ in range(n)]


def _close(a, b):
    if a is None or b is None:
        assert a is b
        return
    assert math.isclose(a, b, rel_tol=REL, abs_tol=1e-9), f"{a} vs {b}"


# ------------------------------------------------------------------ dose

def test_segment_samples_parity(cpp_mod):
    for coords, dur in _routes(300):
        cs = cpp_mod.segment_samples(coords, dur)
        ps = ref.segment_samples(coords, dur)
        assert len(cs) == len(ps)
        for c, p in zip(cs, ps):
            assert c[0] == p["lat"] and c[1] == p["lon"]
            assert c[2] == p["seconds"] and c[3] == p["dist_m"]


def test_integrate_dose_parity(cpp_mod, cpp_fv, py_fv):
    routes = _routes(1000)
    assert len(routes) == 1000
    for coords, dur in routes:
        mode = random.Random(hash(coords[0][0])).choice(MODES)
        me, ve = ref.mode_factors(mode)
        rc = cpp_mod.integrate_dose(coords, cpp_fv, me, ve, dur)
        rp = ref.integrate_dose(coords, py_fv, me, ve, dur)
        assert rc["n_samples"] == rp["n_samples"]
        assert rc["n_hit"] == rp["n_hit"]
        assert rc["coverage"] == rp["coverage"]
        assert rc["dist_km"] == rp["dist_km"]
        for k in ("lo", "mid", "hi"):
            _close(rc[k], rp[k])


def test_dose_edge_cases(cpp_mod, cpp_fv, py_fv):
    me, ve = ref.mode_factors("walking")
    cases = [
        [],                                    # empty polyline
        [[77.2, 28.6]],                        # single point
        [[77.2, 28.6], [77.2, 28.6]],          # zero-length (total == 0)
        [[77.2, 28.6], [77.20001, 28.60001]],  # sub-metre
        [[70.0, 25.0], [71.0, 26.0]],          # fully off-field
        [[77.2, 28.6], [79.5, 28.6]],          # leaves coverage mid-route
        [[76.80, 28.20], [77.90, 28.95]],      # bbox corner to corner
    ]
    for coords in cases:
        for dur in (0.0, 900.0):
            rc = cpp_mod.integrate_dose(coords, cpp_fv, me, ve, dur)
            rp = ref.integrate_dose(coords, py_fv, me, ve, dur)
            assert rc["n_samples"] == rp["n_samples"]
            assert rc["n_hit"] == rp["n_hit"]
            for k in ("lo", "mid", "hi"):
                _close(rc[k], rp[k])


def test_dose_band_ordering(cpp_mod, cpp_fv):
    """On an in-field route the conservative band brackets the mid."""
    coords, dur = _routes(1)[0]
    # force a definitely in-field route
    coords = [[77.20 + i * 0.005, 28.60 + i * 0.003] for i in range(30)]
    r = cpp_mod.integrate_dose(coords, cpp_fv, 1.0, 0.014, 1800.0)
    assert r["coverage"] == 1.0
    assert r["lo"] <= r["mid"] <= r["hi"]


# -------------------------------------------------------------- emissions

def _rand_spans(rng):
    out = []
    for _ in range(rng.randint(1, 8)):
        if rng.random() < 0.7:
            out.append({"dist_m": rng.uniform(50, 9000),
                        "speed_mps": rng.uniform(0.5, 30),
                        "moving": True})
        else:
            s = {"dist_m": 0.0, "moving": False}
            if rng.random() < 0.8:
                s["dur_s"] = rng.uniform(5, 600)
            else:  # exercise the dist_m/v dur fallback path
                s["dist_m"] = rng.uniform(0, 20)
                s["speed_mps"] = rng.uniform(0.4, 5)
            out.append(s)
    return out


def _check_em(cpp_mod, spans, vb, cold_km_done=0.0, occ_override=None):
    occ = occ_override if occ_override is not None else vb["occupancy"]
    rc = cpp_mod.integrate_emissions(
        spans, vb["ef_band"], vb["idle_band"], vb["cold_mult"],
        vb["nx_band"], cold_km_done, occ)
    rp = ref.integrate_emissions(
        spans, vb["ef_band"], vb["idle_band"], vb["cold_mult"],
        vb["nx_band"], cold_km_done, occ)
    for k in ("co2_g", "pm25_g", "nox_g", "non_exhaust_pm10_g"):
        for i in range(3):
            _close(rc[k][i], rp[k][i])
    _close(rc["distance_km"], rp["distance_km"])
    for mk in ("moving_mid_g", "idle_mid_g", "cold_extra_mid_g"):
        for p in ref.EM_POLS:
            _close(rc[mk][p], rp[mk][p])
    return rc


def test_emission_speed_factor_parity(cpp_mod):
    for pol in ref.EM_POLS:
        for v in (0.0, 0.1, 2.5, 5.0, 8.333, 13.89, 20.0, 33.3, 50.0):
            assert cpp_mod.emission_speed_factor(pol, v) == \
                ref.emission_speed_factor(pol, v) == \
                emissions.speed_factor(pol, v)


def test_integrate_emissions_parity(cpp_mod):
    rng = random.Random(108)
    vehicles = [
        {"class": "car", "fuel": "petrol", "year_bucket": "2010_2016"},
        {"class": "car", "fuel": "diesel", "year_bucket": "2020_plus"},
        {"class": "cab", "fuel": "cng", "year_bucket": "not_sure"},
        {"class": "scooter", "year_bucket": "before_2010"},
        {"class": "auto", "year_bucket": "2017_2019"},
        {"class": "bus", "fuel": "diesel", "year_bucket": "not_sure"},
        {"class": "bus", "fuel": "cng"},
        {"class": "car", "fuel": "electric"},
        {"class": "bike", "fuel": "petrol", "year_bucket": "2020_plus"},
    ]
    for veh in vehicles:
        vb = ref.vehicle_bands(veh)
        for _ in range(30):
            spans = _rand_spans(rng)
            cold = rng.choice([0.0, 0.0, 0.0, 1.5, 3.9])
            _check_em(cpp_mod, spans, vb, cold)


def test_integrate_emissions_vs_emissions_py(cpp_mod):
    """Cross-check the kernel against production emissions.integrate."""
    rng = random.Random(7)
    for veh in ({"class": "car", "fuel": "diesel", "year_bucket": "2010_2016"},
                {"class": "auto", "year_bucket": "not_sure"},
                {"class": "bus", "fuel": "cng", "year_bucket": "2020_plus"}):
        vb = ref.vehicle_bands(veh)
        spans = _rand_spans(rng)
        prod = emissions.integrate(veh, spans)
        mine = cpp_mod.integrate_emissions(
            spans, vb["ef_band"], vb["idle_band"], vb["cold_mult"],
            vb["nx_band"], 0.0, vb["occupancy"])
        # production rounds to 4 decimals — compare within that rounding
        for ours, prod_band in (
                (mine["co2_g"], prod["co2_kg"]),
                (mine["pm25_g"], prod["pm25_g"]),
                (mine["nox_g"], prod["nox_g"])):
            for i, k in enumerate(("lo", "mid", "hi")):
                got = ours[i] / (1000.0 if prod_band is prod["co2_kg"] else 1.0)
                assert abs(got - prod_band[k]) <= 5e-5 + 1e-9 * abs(
                    prod_band[k]), f"{veh} {k}: {got} vs {prod_band[k]}"
        for i, k in enumerate(("lo", "mid", "hi")):
            got = mine["non_exhaust_pm10_g"][i]
            assert abs(got - prod["non_exhaust"]["pm10_g"][k]) <= \
                5e-5 + 1e-9 * abs(prod["non_exhaust"]["pm10_g"][k])


def test_emissions_edge_cases(cpp_mod):
    vb = ref.vehicle_bands({"class": "car", "fuel": "petrol"})
    zero = cpp_mod.integrate_emissions([], vb["ef_band"], vb["idle_band"],
                                       vb["cold_mult"], vb["nx_band"])
    assert zero["co2_g"] == (0.0, 0.0, 0.0)
    assert zero["distance_km"] == 0.0
    rp = ref.integrate_emissions([], vb["ef_band"], vb["idle_band"],
                                 vb["cold_mult"], vb["nx_band"])
    assert rp["co2_g"] == (0.0, 0.0, 0.0)
    # idle-only span: dur_s present
    r = cpp_mod.integrate_emissions(
        [{"dist_m": 0.0, "speed_mps": 0.0, "moving": False, "dur_s": 120.0}],
        vb["ef_band"], vb["idle_band"], vb["cold_mult"], vb["nx_band"])
    rp = ref.integrate_emissions(
        [{"dist_m": 0.0, "speed_mps": 0.0, "moving": False, "dur_s": 120.0}],
        vb["ef_band"], vb["idle_band"], vb["cold_mult"], vb["nx_band"])
    for i in range(3):
        assert r["co2_g"][i] == rp["co2_g"][i] > 0
