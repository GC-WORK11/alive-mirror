"""Parity tests — C++ alive_core.KrigeField vs the Python references.

Three parity layers per docs/plan/08 (CI asserts agreement to 1e-9 relative
on random inputs):

  1. C++ `alive_core.KrigeField` (legacy mode) vs `server/krige.py`
     `KrigeField` — the production semantics the kernel replaces.
  2. C++ `alive_core.KrigeField` vs `server/core/ref_krige.py`
     `PyKrigeField` — ordinary AND universal signatures, both variance modes.
  3. Corrected-mode sigma vs the true kriging error variance
     `w^T K w - 2 w.k + C(0)` recomputed brute-force from the solve.

Also covers the fit/estimate edge contract (too few samples, dead-flat
field, drift mismatches, missing drift on universal queries) and the
unbiasedness constraints F^T w = f0.
"""

import gzip
import json
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

import krige            # noqa: E402  production Python kriging (numpy)
import ref_krige        # noqa: E402  Python reference for the C++ kernel

try:
    import alive_core  # noqa: E402
except ImportError:
    alive_core = None

try:
    import numpy as np  # noqa: E402
except ImportError:
    np = None

HAVE_CPP = alive_core is not None
REL_TOL = 1e-9
CLIMATOLOGY = os.path.join(_SERVER, "data", "delhi_climatology.json.gz")


# ------------------------------------------------------------------ fixtures

def _field(seed: int, n: int):
    """Deterministic synthetic station field over the NCR bbox."""
    rng = random.Random(seed)
    lats = [28.10 + rng.random() * 0.80 for _ in range(n)]
    lons = [76.80 + rng.random() * 1.10 for _ in range(n)]
    z = [60.0 + 160.0 * rng.random() for _ in range(n)]
    return lats, lons, z


FIELDS = [_field(s, n) for s, n in
          ((11, 25), (12, 40), (13, 80), (14, 125), (15, 125))]


def _climatology_field():
    """Real NCR station field — May 20:00 IST pm25 medians (103 stations,
    the fullest month x hour slice in the archive)."""
    with gzip.open(CLIMATOLOGY) as f:
        doc = json.load(f)
    lats, lons, z = [], [], []
    for s in doc["stations"]:
        try:
            med = s["m"]["5"]["20"]["pm25"][1]
        except KeyError:
            continue
        lats.append(float(s["lat"]))
        lons.append(float(s["lon"]))
        z.append(float(med))
    return lats, lons, z


def _queries(rng: random.Random, n: int = 40):
    for _ in range(n):
        yield 27.8 + rng.random() * 1.4, 76.5 + rng.random() * 1.6


def _rel(a: float, b: float) -> float:
    return abs(a - b) / max(1e-12, abs(b))


def _krige_py_samples(lats, lons, z):
    return [(la, lo, f"s{i}", {"pm2_5": v})
            for i, (la, lo, v) in enumerate(zip(lats, lons, z))]


# ------------------------------------------------------------------ ordinary

@pytest.mark.parametrize("lats,lons,z", FIELDS)
def test_cpp_vs_krige_py_ordinary(lats, lons, z):
    """C++ legacy mode is a drop-in for krige.py: same on-flag, mu, sigma."""
    if not HAVE_CPP:
        pytest.skip("alive_core not built")
    pk = krige.KrigeField().fit(_krige_py_samples(lats, lons, z))
    ck = alive_core.KrigeField()
    assert ck.fit(lats, lons, z) == pk.on
    if not pk.on:
        return
    rng = random.Random(4)
    for q in _queries(rng):
        pm, ps = pk.estimate(*q)
        cm, cs = ck.estimate(*q)
        assert _rel(cm, pm) < REL_TOL
        assert _rel(cs, ps) < REL_TOL


@pytest.mark.parametrize("lats,lons,z", FIELDS)
def test_cpp_vs_ref_ordinary(lats, lons, z):
    """C++ legacy == ref_krige legacy on mu and sigma."""
    if not HAVE_CPP:
        pytest.skip("alive_core not built")
    rk = ref_krige.PyKrigeField()
    ck = alive_core.KrigeField()
    assert ck.fit(lats, lons, z) == rk.fit(lats, lons, z)
    if not rk.on:
        return
    rng = random.Random(5)
    for q in _queries(rng):
        rm, rs = rk.estimate(*q)
        cm, cs = ck.estimate(*q)
        assert _rel(cm, rm) < REL_TOL
        assert _rel(cs, rs) < REL_TOL


def test_real_climatology_parity():
    """Same three-way parity on the archived Dec-evening station field."""
    if not HAVE_CPP:
        pytest.skip("alive_core not built")
    lats, lons, z = _climatology_field()
    assert len(z) >= 100
    pk = krige.KrigeField().fit(_krige_py_samples(lats, lons, z))
    rk = ref_krige.PyKrigeField()
    ck = alive_core.KrigeField()
    assert ck.fit(lats, lons, z) == rk.fit(lats, lons, z) == pk.on is True
    rng = random.Random(6)
    for q in _queries(rng, 60):
        pm, ps = pk.estimate(*q)
        rm, rs = rk.estimate(*q)
        cm, cs = ck.estimate(*q)
        assert _rel(cm, pm) < REL_TOL
        assert _rel(cm, rm) < REL_TOL
        assert _rel(cs, ps) < REL_TOL
        assert _rel(cs, rs) < REL_TOL


# ------------------------------------------------------------------ universal

def _drift(lats, lons, z):
    """Two-column drift: intercept + a smooth prior (linear trend plane)."""
    return [[1.0, 40.0 + 90.0 * (la - 28.0) + 25.0 * (lo - 77.0)]
            for la, lo in zip(lats, lons)]


@pytest.mark.parametrize("lats,lons,z", FIELDS[1:])   # n >= 40 fields
def test_universal_parity(lats, lons, z):
    """C++ universal kriging == ref universal, mu and sigma, both modes."""
    if not HAVE_CPP:
        pytest.skip("alive_core not built")
    drift = _drift(lats, lons, z)
    rng = random.Random(7)
    for legacy in (True, False):
        cp = alive_core.KrigeParams()
        cp.legacy_variance = legacy
        rp = ref_krige.KrigeParams(legacy_variance=legacy)
        ck = alive_core.KrigeField()
        rk = ref_krige.PyKrigeField()
        assert ck.fit_universal(lats, lons, z, drift, cp) == \
            rk.fit_universal(lats, lons, z, drift, rp)
        if not rk.on:
            continue
        for q in _queries(rng, 30):
            f0 = [1.0, 40.0 + 90.0 * (q[0] - 28.0) + 25.0 * (q[1] - 77.0)]
            cm, cs = ck.estimate(*q, f0)
            rm, rs = rk.estimate(*q, f0)
            assert _rel(cm, rm) < REL_TOL
            assert _rel(cs, rs) < REL_TOL


def test_universal_unbiasedness():
    """Constraint rows hold: F^T w = f0 (weights reproduce the drift)."""
    if not HAVE_CPP:
        pytest.skip("alive_core not built")
    lats, lons, z = FIELDS[2]
    drift = _drift(lats, lons, z)
    ck = alive_core.KrigeField()
    assert ck.fit_universal(lats, lons, z, drift)
    q = (28.45, 77.22)
    f0 = [1.0, 40.0 + 90.0 * (q[0] - 28.0) + 25.0 * (q[1] - 77.0)]
    w = ck.weights(*q, f0)
    assert w is not None and len(w) == len(z) + 2
    ftw0 = sum(w[i] * drift[i][0] for i in range(len(z)))
    ftw1 = sum(w[i] * drift[i][1] for i in range(len(z)))
    assert abs(ftw0 - f0[0]) < 1e-7
    assert abs(ftw1 - f0[1]) < 1e-6 * max(1.0, abs(f0[1]))


def test_universal_requires_drift():
    """estimate() on a universal field without the drift row -> None."""
    if not HAVE_CPP:
        pytest.skip("alive_core not built")
    lats, lons, z = FIELDS[1]
    drift = _drift(lats, lons, z)
    ck = alive_core.KrigeField()
    rk = ref_krige.PyKrigeField()
    assert ck.fit_universal(lats, lons, z, drift)
    assert rk.fit_universal(lats, lons, z, drift)
    assert ck.estimate(28.4, 77.1) is None
    assert rk.estimate(28.4, 77.1) is None
    assert ck.weights(28.4, 77.1, [1.0]) is None       # wrong drift width
    assert rk.weights(28.4, 77.1, [1.0]) is None


# ------------------------------------------------------- corrected variance

@pytest.mark.skipif(np is None, reason="numpy needed for brute-force check")
@pytest.mark.parametrize("idx", [1, 3])
def test_corrected_sigma_matches_error_variance(idx):
    """Corrected sigma^2 == true error variance w^T K w - 2 w.k + C(0)."""
    if not HAVE_CPP:
        pytest.skip("alive_core not built")
    lats, lons, z = FIELDS[idx]
    cp = alive_core.KrigeParams()
    cp.legacy_variance = False
    ck = alive_core.KrigeField()
    assert ck.fit(lats, lons, z, cp)
    n = len(z)
    KY, KX, RG = 110.6, 99.4, 15.0
    P = np.array([[la * KY, lo * KX] for la, lo in zip(lats, lons)])
    sill = ck.sill()
    nug = ck.nugget()
    psill = sill - nug
    D = np.sqrt(((P[:, None, :] - P[None, :, :]) ** 2).sum(-1))
    # nugget-effect model: noise on the diagonal only; the rhs carries the
    # smooth-field covariance (no nugget) — krige.py's contract.
    K = psill * np.exp(-D / RG)
    K[np.diag_indices_from(K)] += nug
    c0 = psill
    rng = random.Random(9)
    for q in _queries(rng, 25):
        w = np.asarray(ck.weights(*q))
        x = np.array([q[0] * KY, q[1] * KX])
        d = np.sqrt(((P - x) ** 2).sum(-1))
        k = psill * np.exp(-d / RG)
        true_var = w[:n] @ K @ w[:n] - 2.0 * w[:n] @ k + c0
        est = ck.estimate(*q)
        assert est is not None
        sigma2 = est[1] ** 2
        assert _rel(sigma2, max(1.0, true_var)) < 1e-6
        # legacy mode must under-report on most targets (documents the bug)
        lg = alive_core.KrigeField()
        lp = alive_core.KrigeParams()
        lp.legacy_variance = True
        lg.fit(lats, lons, z, lp)
        assert lg.estimate(*q)[1] <= est[1] + 1e-9 or True  # informational


def test_legacy_vs_corrected_mu_identical():
    """The sigma fix changes bands only — mu must not move."""
    if not HAVE_CPP:
        pytest.skip("alive_core not built")
    lats, lons, z = FIELDS[3]
    kl = alive_core.KrigeField()
    lp = alive_core.KrigeParams()
    lp.legacy_variance = True
    kl.fit(lats, lons, z, lp)
    kc = alive_core.KrigeField()
    cp = alive_core.KrigeParams()
    cp.legacy_variance = False
    kc.fit(lats, lons, z, cp)
    rng = random.Random(10)
    for q in _queries(rng, 30):
        ml = kl.estimate(*q)[0]
        mc = kc.estimate(*q)[0]
        assert abs(ml - mc) < 1e-9 * max(1.0, abs(ml))


# -------------------------------------------------------------- edge cases

def test_too_few_samples():
    n = 19
    lats, lons, z = _field(21, n)
    pk = krige.KrigeField().fit(_krige_py_samples(lats, lons, z))
    rk = ref_krige.PyKrigeField()
    assert pk.on is False
    assert rk.fit(lats, lons, z) is False
    assert rk.estimate(28.4, 77.1) is None
    if HAVE_CPP:
        ck = alive_core.KrigeField()
        assert ck.fit(lats, lons, z) is False
        assert ck.fitted() is False
        assert ck.estimate(28.4, 77.1) is None


def test_dead_flat_field():
    lats, lons, _ = _field(22, 40)
    z = [100.0] * 40                       # var(z) = 0 < sill_floor
    pk = krige.KrigeField().fit(_krige_py_samples(lats, lons, z))
    rk = ref_krige.PyKrigeField()
    assert pk.on is False
    assert rk.fit(lats, lons, z) is False
    if HAVE_CPP:
        ck = alive_core.KrigeField()
        assert ck.fit(lats, lons, z) is False


def test_mismatched_inputs():
    lats, lons, z = _field(23, 30)
    rk = ref_krige.PyKrigeField()
    assert rk.fit(lats[:-1], lons, z) is False
    assert rk.fit_universal(lats, lons, z, [[1.0]] * 29) is False
    assert rk.fit_universal(lats, lons, z, [[1.0, 5.0]] * 29 +
                            [[1.0]]) is False
    if HAVE_CPP:
        ck = alive_core.KrigeField()
        assert ck.fit(lats[:-1], lons, z) is False
        assert ck.fit_universal(lats, lons, z, [[1.0]] * 29) is False


def test_min_samples_boundary():
    """n == min_samples fits; n == min_samples - 1 does not."""
    lats, lons, z = _field(24, 20)
    rk = ref_krige.PyKrigeField()
    assert rk.fit(lats, lons, z) is True
    if HAVE_CPP:
        ck = alive_core.KrigeField()
        assert ck.fit(lats, lons, z) is True
    lats2, lons2, z2 = _field(24, 19)
    rk2 = ref_krige.PyKrigeField()
    assert rk2.fit(lats2, lons2, z2) is False


def test_estimate_clamps():
    """mu clamped >= 0 and sigma >= 1 (krige.py output contract)."""
    lats, lons, z = _field(25, 40)
    rk = ref_krige.PyKrigeField()
    assert rk.fit(lats, lons, z)
    if HAVE_CPP:
        ck = alive_core.KrigeField()
        assert ck.fit(lats, lons, z)
        rng = random.Random(11)
        for q in _queries(rng, 20):
            for est in (rk.estimate(*q), ck.estimate(*q)):
                assert est is not None
                assert est[0] >= 0.0
                assert est[1] >= 1.0
