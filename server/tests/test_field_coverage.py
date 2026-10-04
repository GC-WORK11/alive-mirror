"""Band-coverage calibration tests.

The uncertainty band the API serves (lo/hi on /aqi, dose_lo/hi on
/v2/plan) is the product's honesty claim: these tests pin the
measurement machinery (validate_field.coverage_stats), the measured
total-error inflation (airfield.SIGMA_CAL folded into _krige_posterior
and airindex cells), and the krige-µ physical clamp that stops
Lagrange-weight overshoot past the fitted sample range.
"""
import math
import sys
import os

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "core", "build312"))

import airfield
import validate_field as vf


def _pair(obs, model, sd):
    return ("st", None, obs, model, model, sd)


# ------------------------------------------------------- coverage_stats math

def test_coverage_stats_counts_inside_band():
    # 10 pairs: errs 5,10,15,...,50 µg against a fixed sd=10
    pairs = [_pair(0.0, e, 10.0) for e in (5, 10, 15, 20, 25, 30, 35, 40, 45, 50)]
    cov = vf.coverage_stats(pairs)
    # |err| <= k*sd: k=1 -> errs {5,10}=2/10; k=2 -> {5..20}=4/10; k=3 -> 6/10
    assert cov["coverage"][1] == pytest.approx(0.2)
    assert cov["coverage"][2] == pytest.approx(0.4)
    assert cov["coverage"][3] == pytest.approx(0.6)
    assert cov["n"] == 10
    assert cov["z_median"] == pytest.approx(3.0)  # upper median of z = 0.5..5.0


def test_coverage_stats_scale_factor_backcalc():
    # errors exactly at 1,2,...,10 sd — the 95th percentile z is ~9.55,
    # so cal_2s ~ 4.77: coverage math must expose the needed widening.
    pairs = [_pair(0.0, float(z), 1.0) for z in range(1, 11)]
    cov = vf.coverage_stats(pairs)
    assert cov["coverage"][2] == pytest.approx(0.2)   # only z<=2 inside
    assert cov["cal_2s"] > 4.0                        # badly overconfident


def test_coverage_stats_ignores_missing_sigma():
    pairs = [_pair(0.0, 30.0, None), _pair(0.0, 5.0, 10.0)]
    cov = vf.coverage_stats(pairs)
    assert cov["n"] == 1
    assert cov["coverage"][3] == pytest.approx(1.0)


# ------------------------------------------------------ SIGMA_CAL in posterior

def test_krige_posterior_applies_sigma_cal(monkeypatch):
    monkeypatch.setattr(airfield, "corridor_estimate", lambda *a, **k: None)
    f = airfield.AirField()
    mu_in, sd_in = 100.0, 10.0
    _mu, sd = f._krige_posterior(28.6, 77.2, mu_in, sd_in)
    raw = math.sqrt(sd_in * sd_in + (0.12 * mu_in) ** 2)
    assert sd == pytest.approx(raw * airfield.SIGMA_CAL)


def test_sigma_cal_is_measured_magnitude():
    # The constant must stay in the measured band from
    # data/field_validation.md (cal_2s ~ 1.0 post-calibration). Guard
    # against accidental zeroing or "helpful" hand-tuning: a regression
    # test on the value itself — update it only by re-measuring.
    assert 2.0 <= airfield.SIGMA_CAL <= 5.0


# --------------------------------------------------------- krige µ clamp

def test_clamp_krige_caps_at_max_sample():
    f = airfield.AirField()
    f._samples = [
        (28.5, 77.1, None, {"pm2_5": 40.0}),
        (28.6, 77.2, None, {"pm2_5": 90.0}),
        (28.7, 77.3, None, {"pm2_5": 65.0}),
    ]
    # Lagrange overshoot: µ past the highest sample is unphysical
    mu, sd = f._clamp_krige("pm2_5", (450.0, 12.0))
    assert mu == pytest.approx(90.0)
    assert sd == pytest.approx(12.0)          # σ untouched


def test_clamp_krige_floors_at_zero():
    f = airfield.AirField()
    f._samples = [(28.5, 77.1, None, {"pm2_5": 40.0})]
    mu, _sd = f._clamp_krige("pm2_5", (-30.0, 8.0))
    assert mu == 0.0


def test_clamp_krige_passthrough_inside_range():
    f = airfield.AirField()
    f._samples = [(28.5, 77.1, None, {"pm2_5": 90.0})]
    mu, sd = f._clamp_krige("pm2_5", (55.0, 6.0))
    assert mu == pytest.approx(55.0)
    assert sd == pytest.approx(6.0)


# ------------------------------------------- airindex cells carry the same σ

def test_airindex_krige_branch_includes_sigma_cal():
    """Snapshot cells and per-query bands must mean the same thing —
    the krige-on cell formula is the airfield posterior times the same
    measured inflation. Guards the two paths drifting apart."""
    import inspect
    import airindex
    src = inspect.getsource(airindex)
    assert "airfield.SIGMA_CAL" in src
