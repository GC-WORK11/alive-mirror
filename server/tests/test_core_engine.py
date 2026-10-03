"""core_engine shim — adapter contract on whichever engine is loaded.

Runs under the plain venv (no .so → Python path) AND under the core
build (PYTHONPATH=core/build → alive_core path). Assertions hold for
both: the adapter must be a drop-in for krige.KrigeField either way.
"""

import math

import core_engine
import krige


def _samples(n=30, base=28.6, lon0=77.0, spread=0.35):
    """n unique stations, deterministic z = lat*10 + lon — a smoothly
    varying non-flat field (sill >> _MIN_SILL)."""
    out = []
    for i in range(n):
        la = base + (i % 6) * spread / 6.0
        lo = lon0 + (i // 6) * spread / 5.0
        out.append((la, lo, f"st{i}", {"pm2_5": 40.0 + i * 1.7}))
    return out


def test_engine_label_matches_loaded_extension():
    assert core_engine.ENGINE in ("alive_core", "python")
    assert (core_engine.ENGINE == "alive_core") == core_engine._CPP_KRIGE


def test_fit_and_estimate_contract():
    kf = core_engine.KrigeField().fit(_samples())
    # C++ kriges without numpy; the Python ref can't fit without it —
    # off is the honest state, matching krige.py exactly.
    if core_engine._CPP_KRIGE or krige.np is not None:
        assert kf.on is True
        est = kf.estimate(28.62, 77.10)
        assert est is not None
        mu, sd = est
        assert math.isfinite(mu) and math.isfinite(sd)
        assert sd > 0
    else:
        assert kf.on is False
        assert kf.estimate(28.62, 77.10) is None


def test_unfitted_estimate_is_none():
    kf = core_engine.KrigeField()
    assert kf.estimate(28.6, 77.1) is None


def test_malformed_and_duplicate_samples():
    # bad rows skipped, identical (lat, lon) merged by mean — krige.py
    # contract; below _MIN_SAMPLES unique -> off
    bad = [
        (28.6, 77.1, "a", {"pm2_5": 50.0}),
        (28.6, 77.1, "dup", {"pm2_5": 60.0}),   # merges with row 0 -> 55
        (None, None, "bad1", {"pm2_5": 10.0}),  # non-finite — skipped
        (28.7, "x", "bad2", {"pm2_5": 10.0}),   # uncoercible — skipped
        (28.7, 77.2, "noval", {}),              # missing key — skipped
    ]
    kf = core_engine.KrigeField().fit(bad)
    assert kf.on is False  # only 1 unique location << _MIN_SAMPLES


def test_flat_field_goes_off():
    # identical z everywhere -> sill 0 < _MIN_SILL -> off (both impls)
    flat = [(28.6 + i * 0.01, 77.0 + i * 0.01, f"s{i}",
             {"pm2_5": 42.0}) for i in range(30)]
    kf = core_engine.KrigeField().fit(flat)
    assert kf.on is False
    assert kf.estimate(28.6, 77.1) is None


def test_adapter_matches_python_reference():
    """Whatever the active engine, estimates must equal krige.py's —
    the parity the whole shim exists for. Without numpy the reference
    can't fit, so there is nothing to compare against."""
    if krige.np is None:
        return
    samples = _samples()
    ad = core_engine.KrigeField().fit(samples)
    ref = krige.KrigeField().fit(samples)
    assert ad.on == ref.on
    for la, lo in [(28.62, 77.10), (28.7, 77.2), (28.55, 77.05)]:
        a, r = ad.estimate(la, lo), ref.estimate(la, lo)
        assert (a is None) == (r is None)
        if a is not None:
            assert abs(a[0] - r[0]) < 1e-6
            assert abs(a[1] - r[1]) < 1e-6


def test_module_kf_is_field_instance():
    assert isinstance(core_engine.KF, core_engine.KrigeField)
    assert core_engine.KF.on is False
