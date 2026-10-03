"""Ordinary kriging on the station+model field — the honest-uncertainty layer.

IDW answers "what's the concentration here" with a weighted average; it
cannot say how wrong that answer might be. Kriging solves a small linear
system built on a fixed variogram and yields BOTH the best linear
unbiased estimate AND its variance. The variance rides downstream as the
dose band ("42–68µg") instead of fake precision on a single number.

Model (docs/plan/krige-spec.md is the normative spec — a C++ port must
reproduce these values bit-close, so ambiguity there is a bug):

    y_i = Z(x_i) + eps_i,   eps_i ~ iid noise of variance N
    cov(Z(x), Z(x')) = P * exp(-|x - x'| / R)      exponential, partial sill P
    sill = population variance of the samples;  N = 0.15*sill;  P = sill - N
    K_ij = P*exp(-d_ij/R) + N*delta_ij           observation covariance
    solve [K 1; 1^T 0] [w; lam] = [P*exp(-d_i0/R); 1]     (ordinary kriging)
    mu    = sum_i w_i y_i                        (UNCLAMPED — may go negative)
    sigma^2 = P - w.k - lam,   sigma = sqrt(max(sigma^2, 1.0))

Ordinary kriging only — the mean is a single unknown constant, no drift
terms. Spatial trend is the caller's job: airindex detrends by kriging
station-minus-model residuals (which is why `estimate` must return
unclamped values — residuals are legitimately negative), airfield kriges
the de-biased concentration field directly.

Cost: one (n+1)x(n+1) LU inversion per refresh (~145 points —
milliseconds), then O(n) per query. Below _MIN_SAMPLES usable locations,
or when the field is flatter than _MIN_SILL, `on` stays False and
callers fall back to IDW — no fake bands.

Coordinates are projected to km (equirectangular, ~28.6°N) so the
variogram range lives in real distance, not degrees. Deterministic: no
randomness anywhere; sample order = input order after exact-duplicate
merge.
"""
import math

try:
    import numpy as np
except ImportError:  # kriging silently off; IDW path remains
    np = None

# lat/lon → km at Delhi's latitude (spec §constants — C++ port uses the
# same literals, they are not derived quantities)
_KY = 110.6  # km per degree latitude
_KX = 99.4   # km per degree longitude at 28.6°N

# Exponential variogram gamma(d) = N + P*(1 - exp(-d/R)) for d > 0,
# gamma(0) = 0; total sill P + N = sill. Range ~15km = the mesoscale
# coherence length of winter PM over NCR; nugget ~15% of sill covers
# instrument noise + micro-scale variation.
_RANGE_KM = 15.0
_NUGGET_FRAC = 0.15

_MIN_SAMPLES = 20    # unique locations needed to trust the linear solve
_MIN_SILL = 2.0      # µg²/m⁶ — sample std >= ~1.41 µg/m³ or σ is noise
_VAR_FLOOR = 1.0     # µg²/m⁶ — kriging sigma never below 1 µg/m³


def _to_km(lat, lon):
    """Projected coordinates (u northing, v easting) in km."""
    return lat * _KY, lon * _KX


class KrigeField:
    """Fits once per refresh; evaluates O(n) per query point.

    Contract (callers rely on exactly this):
      fit(samples, key="pm2_5") -> self   # chainable
      .on -> bool                          # kriging usable?
      estimate(lat, lon) -> (mu, sigma) | None
    """

    def __init__(self):
        self._ainv = None        # inverted (n+1)x(n+1) kriging system
        self._pts = None         # sample locations, km (n,2)
        self._vals = None        # sample values (n,)
        self._nugget = 0.0       # N — observation-noise variance
        self._sill = 0.0         # total field variance N + P
        self._psill = 0.0        # P — structural (partial) sill
        self.on = False

    def fit(self, samples, key="pm2_5"):
        """samples: [(lat, lon, name, {key: v})]. Returns self (chainable).

        Pipeline order is normative (spec §fit):
          1. coerce + finite-check each sample in input order; malformed
             or non-finite samples are skipped, never fatal;
          2. merge samples at bit-identical (lat, lon) by arithmetic mean,
             keeping first occurrence's position;
          3. gates: n >= _MIN_SAMPLES unique locations and
             sill = population variance >= _MIN_SILL;
          4. assemble + invert the augmented system; any failure leaves
             .on False so callers fall back to IDW.
        """
        self.on = False
        self._ainv = self._pts = self._vals = None
        if np is None:
            return self
        merged = {}  # (lat, lon) -> [u, v, z_sum, count]; dicts keep order
        for s in samples:
            try:
                lat, lon, _name, vals = s
                zf = float((vals or {}).get(key))
                latf, lonf = float(lat), float(lon)
            except (TypeError, ValueError, OverflowError, AttributeError):
                continue  # malformed/missing value — skip, never fatal
            if not (math.isfinite(latf) and math.isfinite(lonf)
                    and math.isfinite(zf)):
                continue
            e = merged.get((latf, lonf))
            if e is None:
                merged[(latf, lonf)] = [latf * _KY, lonf * _KX, zf, 1]
            else:
                e[2] += zf
                e[3] += 1
        recs = list(merged.values())
        n = len(recs)
        if n < _MIN_SAMPLES:
            return self
        z = np.asarray([r[2] / r[3] for r in recs])
        sill = float(np.var(z))  # population variance (divide by n)
        if not math.isfinite(sill) or sill < _MIN_SILL:
            return self
        nugget = sill * _NUGGET_FRAC
        psill = sill - nugget

        P = np.asarray([[r[0], r[1]] for r in recs])
        d = np.sqrt((P[:, None, 0] - P[None, :, 0]) ** 2
                    + (P[:, None, 1] - P[None, :, 1]) ** 2)
        # observation covariance: structural exp + diagonal noise nugget.
        # The diagonal nugget doubles as the solve's regularizer — min
        # eigenvalue >= N even for (near-)coincident stations, so no
        # singular system can occur from duplicate locations.
        K = psill * np.exp(-d / _RANGE_KM)
        K[np.diag_indices_from(K)] += nugget
        # ordinary kriging: augment with unit row/col + Lagrange term
        n1 = n + 1
        A = np.empty((n1, n1))
        A[:n, :n] = K
        A[:n, n] = A[n, :n] = 1.0
        A[n, n] = 0.0
        try:
            ainv = np.linalg.inv(A)
        except np.linalg.LinAlgError:
            return self
        if not np.isfinite(ainv).all():
            return self
        self._ainv = ainv
        self._pts = P
        self._vals = z
        self._nugget = nugget
        self._sill = sill
        self._psill = psill
        self.on = True
        return self

    def estimate(self, lat, lon):
        """→ (µ̂ µg/m³, σ̂ µg/m³) or None when unfitted / bad query.

        µ̂ is the raw ordinary-kriging estimate — NOT clamped. It may be
        negative (residual kriging in airindex relies on that) or lie
        outside the sample range under extrapolation; clamping physical
        quantities is the caller's job. σ̂ is the std-dev of the smooth
        field estimate Z (predicting what a fresh noisy instrument would
        read adds +nugget to the variance; callers add their own
        instrument-error floors on top regardless).
        """
        if not self.on:
            return None
        try:
            u, v = _to_km(float(lat), float(lon))
        except (TypeError, ValueError, OverflowError):
            return None
        if not (math.isfinite(u) and math.isfinite(v)):
            return None
        d = np.sqrt((self._pts[:, 0] - u) ** 2
                    + (self._pts[:, 1] - v) ** 2)
        # cov(observations, smooth field at query) — no nugget term
        k = self._psill * np.exp(-d / _RANGE_KM)
        n = len(self._vals)
        rhs = np.empty(n + 1)
        rhs[:n] = k
        rhs[n] = 1.0
        w = self._ainv @ rhs
        mu = float(w[:n] @ self._vals)
        # sigma^2 = C_Z(0) - w.k - lam   (lam = w[n], the Lagrange term,
        # enters NEGATIVELY under the [K 1; 1^T 0][w;lam]=[k;1] convention)
        var = self._psill - float(w[:n] @ k) - float(w[n])
        if not (math.isfinite(mu) and math.isfinite(var)):
            return None
        return mu, math.sqrt(max(_VAR_FLOOR, var))


KF = KrigeField()
