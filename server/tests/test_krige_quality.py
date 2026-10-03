"""Quality gates for krige.KrigeField — the honest-uncertainty layer.

Covers the contract in docs/plan/krige-spec.md: known-answer cases that
are hand-computable without rerunning the module's own solve (a circle
of points where symmetry fixes every weight), the fit gates, the
edge-case table (few/equal/collinear/duplicate samples, extrapolation),
and determinism. Spec constants are hardcoded here on purpose — a drift
in krige.py's literals must fail this file, not silently port to C++.

Run from server/:   python3 -m pytest tests/test_krige_quality.py -q
"""
import math
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

np = pytest.importorskip("numpy", reason="kriging needs numpy")

from krige import KrigeField  # noqa: E402

# --- spec constants (docs/plan/krige-spec.md §3) — literals, not imports
KY, KX = 110.6, 99.4
R_KM = 15.0
NUGGET_FRAC = 0.15
MIN_SAMPLES = 20
MIN_SILL = 2.0
VAR_FLOOR = 1.0

CENTRE = (28.60, 77.10)


def _mk(pts):
    """[(lat, lon, value)] -> samples tuple list for fit()."""
    return [(la, lo, f"s{i}", {"pm2_5": v})
            for i, (la, lo, v) in enumerate(pts)]


def _grid_pts(j0=5, i0=4, dlat=0.10, dlon=0.10):
    """20-pt grid over ~50x40 km centred near CENTRE; varied values."""
    pts = []
    for j in range(j0):
        for i in range(i0):
            lat = CENTRE[0] - 0.25 + j * dlat
            lon = CENTRE[1] - 0.15 + i * dlon
            v = 80.0 + 10.0 * j + 4.0 * i + 7.0 * math.sin(2 * i + j)
            pts.append((lat, lon, v))
    return pts


def _fitted():
    return KrigeField().fit(_mk(_grid_pts()))


# ---------------------------------------------------------------- gates

def test_estimate_before_fit_is_none():
    assert KrigeField().estimate(*CENTRE) is None
    assert KrigeField().on is False


def test_fit_returns_self_chainable():
    kf = KrigeField().fit(_mk(_grid_pts()))
    assert isinstance(kf, KrigeField) and kf.on


@pytest.mark.parametrize("n", [0, 1, 2, 3, 19])
def test_too_few_samples_off(n):
    kf = KrigeField().fit(_mk(_grid_pts()[:n]))
    assert kf.on is False
    assert kf.estimate(*CENTRE) is None


def test_all_equal_samples_off():
    pts = [(la, lo, 55.0) for la, lo, _ in _grid_pts()]
    assert KrigeField().fit(_mk(pts)).on is False


def test_flat_field_under_sill_gate_off():
    # std ~0.5 -> var ~0.25 << MIN_SILL=2.0 -> off
    pts = [(la, lo, 60.0 + 0.1 * i) for i, (la, lo, _v) in
           enumerate(_grid_pts())]
    assert KrigeField().fit(_mk(pts)).on is False


def test_exactly_min_samples_fits():
    kf = _fitted()
    assert kf.on
    assert len(kf._vals) == MIN_SAMPLES


# ------------------------------------------------------- sample hygiene

def test_malformed_samples_skipped_not_fatal():
    pts = _grid_pts()
    samples = _mk(pts)
    samples[3] = (28.4, 76.9)                          # wrong arity
    samples[5] = (28.4, 76.95, "x", None)              # no dict
    samples[7] = (28.4, 77.0, "x", {"pm2_5": "abc"})   # uncoercible
    samples[9] = (28.4, 77.05, "x", {"pm2_5": float("nan")})
    samples[11] = (28.4, 77.10, "x", {"other": 5.0})   # wrong key
    kf = KrigeField().fit(samples)
    assert kf.on is False          # 15 usable < 20 -> honest off


def test_nan_sample_dropped_result_identical():
    base = _mk(_grid_pts())
    poisoned = base + [(28.45, 77.05, "bad", {"pm2_5": float("nan")}),
                       (28.46, 77.06, "inf", {"pm2_5": float("inf")})]
    a, b = KrigeField().fit(base), KrigeField().fit(poisoned)
    assert a.on and b.on
    assert a.estimate(*CENTRE) == b.estimate(*CENTRE)  # no poisoning


def test_missing_key_skips_sample():
    samples = _mk(_grid_pts())
    kf = KrigeField().fit(samples, key="no2")
    assert kf.on is False          # no sample carries "no2"


# ---------------------------------------------------------------- edges

def test_collinear_samples_fit():
    # 22 points on a line, varying values -> kriging still solves
    pts = [(CENTRE[0] - 0.3 + i * 0.03, CENTRE[1],
            70.0 + 3.0 * i + 9.0 * math.sin(i)) for i in range(22)]
    kf = KrigeField().fit(_mk(pts))
    assert kf.on
    mu, sd = kf.estimate(CENTRE[0], CENTRE[1])
    assert math.isfinite(mu) and sd >= 1.0


def test_exact_duplicates_merged_then_identical():
    # 20 unique locations, each sent twice -> dedup -> same system
    pts = _grid_pts()
    dup = [p for p in pts for _ in (0, 1)]
    a, b = KrigeField().fit(_mk(pts)), KrigeField().fit(_mk(dup))
    assert a.on and b.on and len(b._vals) == MIN_SAMPLES
    for q in [CENTRE, (28.7, 77.2), (29.5, 78.0)]:
        assert a.estimate(*q) == b.estimate(*q)


def test_duplicate_locations_averaged():
    # duplicated location with two values merges to their mean —
    # equals an explicit single sample at the mean, bit for bit.
    pts = _grid_pts()
    p0 = pts[0]
    dup_vals = [(p0[0], p0[1], "d1", {"pm2_5": 10.0}),
                (p0[0], p0[1], "d2", {"pm2_5": 30.0})] + _mk(pts[1:])
    merged = _mk([(p0[0], p0[1], 20.0)] + pts[1:])
    a, b = KrigeField().fit(dup_vals), KrigeField().fit(merged)
    assert a.on and b.on
    assert a.estimate(*CENTRE) == b.estimate(*CENTRE)


def test_near_duplicate_locations_solve():
    # two stations ~11 cm apart used to singularize the whole field
    pts = _grid_pts() + [(28.35, 76.85, 92.0), (28.350001, 76.85, 95.0)]
    kf = KrigeField().fit(_mk(pts))
    assert kf.on
    mu, sd = kf.estimate(*CENTRE)
    assert math.isfinite(mu) and math.isfinite(sd)


def test_nonfinite_query_is_none():
    kf = _fitted()
    for bad in [(float("nan"), 77.0), (28.5, float("inf")),
                (float("-inf"), float("nan")), (None, None)]:
        assert kf.estimate(*bad) is None


# ------------------------------------------------------ known answers

def test_known_answer_circle_center():
    """20 pts on a 10 km circle, query at centre (spec §11).

    Symmetry fixes every weight to 1/20, so µ̂ = mean(z) exactly and
    σ̂² = P - 2·kc + S/n is computable by direct summation — this test
    never runs the module's solve path."""
    n, r = 20, 10.0
    zvals = [45.0 + 6.0 * i + 11.0 * math.sin(1.7 * i) for i in range(n)]
    samples = []
    for i in range(n):
        th = 2.0 * math.pi * i / n
        samples.append((CENTRE[0] + r * math.cos(th) / KY,
                        CENTRE[1] + r * math.sin(th) / KX,
                        f"c{i}", {"pm2_5": zvals[i]}))
    kf = KrigeField().fit(samples)
    assert kf.on
    sill = float(np.var(zvals))
    assert sill >= MIN_SILL
    N = NUGGET_FRAC * sill
    P = sill - N
    # circulant row-sum of K, straight from the spec formulas
    S = (P + N) + sum(P * math.exp(-(2.0 * r * math.sin(math.pi * m / n))
                                   / R_KM) for m in range(1, n))
    kc = P * math.exp(-r / R_KM)
    lam = kc - S / n                       # Lagrange term, derived
    exp_var = P - kc - lam                 # = P - 2kc + S/n
    mu, sd = kf.estimate(*CENTRE)
    assert mu == pytest.approx(sum(zvals) / n, rel=1e-9, abs=1e-9)
    assert sd == pytest.approx(math.sqrt(max(VAR_FLOOR, exp_var)),
                               rel=1e-9)


def test_weights_sum_to_one():
    """Unbiasedness: kriging weights always sum to 1 (constraint row)."""
    kf = _fitted()
    n = len(kf._vals)
    for q in [CENTRE, (28.9, 77.6), (24.0, 70.0)]:
        u, v = q[0] * KY, q[1] * KX
        d = np.sqrt((kf._pts[:, 0] - u) ** 2 + (kf._pts[:, 1] - v) ** 2)
        k = kf._psill * np.exp(-d / R_KM)
        rhs = np.concatenate([k, [1.0]])
        w = kf._ainv @ rhs
        assert float(w[:n].sum()) == pytest.approx(1.0, abs=1e-9)


# ------------------------------------------------------- sigma honesty

def test_sigma_grows_with_distance_and_saturates():
    """Interpolation inside hull is confident; far outside, σ̂² →
    P + (1ᵀK⁻¹1)⁻¹ — bounded, never the 1.0 floor (spec §9)."""
    kf = _fitted()
    inside = kf.estimate(*CENTRE)
    edge = kf.estimate(28.60, 78.10)        # ~100 km east of samples
    far = kf.estimate(24.0, 70.0)           # ~800 km away
    assert inside[1] < edge[1] < far[1]
    # independent asymptote computation (solve, not the module's inv matvec)
    n = len(kf._vals)
    K = kf._psill * np.exp(
        -np.sqrt((kf._pts[:, None, 0] - kf._pts[None, :, 0]) ** 2
                 + (kf._pts[:, None, 1] - kf._pts[None, :, 1]) ** 2)
        / R_KM) + kf._nugget * np.eye(n)
    ones = np.ones(n)
    mean_var = 1.0 / float(ones @ np.linalg.solve(K, ones))
    assert far[1] ** 2 == pytest.approx(kf._psill + mean_var, rel=1e-6)


def test_far_field_mu_reverts_to_gls_mean():
    kf = _fitted()
    n = len(kf._vals)
    K = kf._psill * np.exp(
        -np.sqrt((kf._pts[:, None, 0] - kf._pts[None, :, 0]) ** 2
                 + (kf._pts[:, None, 1] - kf._pts[None, :, 1]) ** 2)
        / R_KM) + kf._nugget * np.eye(n)
    ones = np.ones(n)
    gls = float(ones @ np.linalg.solve(K, kf._vals)
                / (ones @ np.linalg.solve(K, ones)))
    mu, _ = kf.estimate(24.0, 70.0)
    assert mu == pytest.approx(gls, rel=1e-6)


def test_sigma_floor_at_dense_confident_point():
    """σ̂ >= 1 µg/m³ everywhere, even where the field is best known —
    and the floor really binds on a low-variance fit."""
    kf = _fitted()
    for q in _grid_pts()[:6] + [CENTRE]:
        assert kf.estimate(q[0], q[1])[1] >= 1.0
    # low-variance field just past the gate (var ~2.75 >= 2.0):
    # at-sample kriging variance dips under the floor -> sd exactly 1.0
    pts = [(la, lo, 50.0 + 2.0 * math.sin(i * 1.3) + 1.0 * (i % 3))
           for i, (la, lo, _v) in enumerate(_grid_pts())]
    low = KrigeField().fit(_mk(pts))
    assert low.on
    sds = [low.estimate(la, lo)[1] for la, lo, _ in pts]
    assert min(sds) == 1.0              # floor binds, not just respected
    assert all(s >= 1.0 for s in sds)


def test_mu_not_clamped_negative_residuals():
    """Residual kriging (airindex) — negative values must survive.
    Regression test: a former max(0, µ̂) zeroed every downward
    correction."""
    pts = []
    for j in range(5):
        for i in range(4):
            lat = CENTRE[0] - 0.25 + j * 0.10
            lon = CENTRE[1] - 0.15 + i * 0.10
            pts.append((lat, lon, -40.0 + 3.0 * i + 2.0 * j))
    kf = KrigeField().fit(_mk(pts))
    assert kf.on
    mu, sd = kf.estimate(CENTRE[0] - 0.24, CENTRE[1] - 0.14)  # low corner
    assert mu < 0.0
    assert sd >= 1.0


def test_estimate_at_station_regresses_slightly():
    """At a sample location the nugget treats the obs as noisy: µ̂ is
    close to the observed value but allowed to shrink toward
    neighbours, and σ̂ is small but nonzero."""
    pts = _grid_pts()
    kf = KrigeField().fit(_mk(pts))
    la, lo, z0 = pts[7]
    mu, sd = kf.estimate(la, lo)
    assert abs(mu - z0) < 0.3 * abs(z0)   # within shrinkage distance
    assert sd >= 1.0


# ----------------------------------------------------------- determinism

def test_two_fits_identical():
    a, b = _fitted(), _fitted()
    for q in [CENTRE, (28.7, 77.4), (24.0, 70.0)]:
        assert a.estimate(*q) == b.estimate(*q)


def test_estimate_repeatable():
    kf = _fitted()
    assert kf.estimate(*CENTRE) == kf.estimate(*CENTRE)


def test_input_permutation_invariant():
    """Order changes only fp rounding — results agree to 1e-9."""
    pts = _grid_pts()
    fwd = KrigeField().fit(_mk(pts))
    rev = KrigeField().fit(_mk(list(reversed(pts))))
    for q in [CENTRE, (28.8, 77.5)]:
        ma, sa = fwd.estimate(*q)
        mb, sb = rev.estimate(*q)
        assert ma == pytest.approx(mb, rel=1e-9)
        assert sa == pytest.approx(sb, rel=1e-9)


def test_refit_resets_state():
    kf = KrigeField().fit(_mk(_grid_pts()))
    assert kf.on
    kf.fit([])                       # failed refit must clear, not keep
    assert kf.on is False
    assert kf.estimate(*CENTRE) is None
