"""Ordinary kriging on the station+model field — the honest-uncertainty layer.

IDW answers "what's the concentration here" with a weighted average; it
cannot say how wrong that answer might be. Kriging solves a small linear
system built on a fitted variogram and yields BOTH the best linear
unbiased estimate AND its variance. The variance rides downstream as the
dose band ("42–68µg") instead of fake precision on a single number.

Cost: one (n+1)×(n+1) LU solve per refresh for the left-hand matrix
(~145 points — milliseconds), then O(n) per query. Kriging replaces the
raw-distance blend only where samples are dense enough to fit a
variogram (>=20 non-constant samples); elsewhere IDW still applies.

Coordinates are projected to km (equirectangular, ~29°N) so the
variogram range lives in real distance, not degrees.
"""
import math

try:
    import numpy as np
except ImportError:  # kriging silently off; IDW path remains
    np = None

# lat/lon → km at Delhi's latitude
_KY = 110.6  # km per degree latitude
_KX = 99.4   # km per degree longitude at 28.6°N

# Exponential variogram: γ(d) = nugget + sill*(1 - exp(-d/range)).
# Range ~15km = the mesoscale coherence length of winter PM over NCR;
# nugget ~15% of sill covers instrument noise + micro-scale variation.
_RANGE_KM = 15.0
_NUGGET_FRAC = 0.15


def _to_km(lat, lon):
    return lat * _KY, lon * _KX


def _gamma(d, nugget, sill):
    return nugget + (sill - nugget) * (1.0 - math.exp(-d / _RANGE_KM))


class KrigeField:
    """Fits once per refresh; evaluates O(n) per query point."""

    def __init__(self):
        self._lu = None          # solved kriging system matrix (cholesky)
        self._pts = None         # sample points in km
        self._vals = None        # sample values
        self._nugget = 0.0
        self._sill = 0.0
        self.on = False

    def fit(self, samples, key="pm2_5"):
        """samples: [(lat, lon, name, {key: v})]. Returns self (chainable)."""
        self.on = False
        if np is None:
            return self
        pts, vals = [], []
        for lat, lon, _n, v in samples:
            z = (v or {}).get(key)
            if z is None:
                continue
            pts.append(_to_km(lat, lon))
            vals.append(float(z))
        n = len(pts)
        if n < 20:
            return self
        z = np.asarray(vals)
        sill_est = float(np.var(z))
        if sill_est < 25.0:      # field is ~flat — kriging adds nothing
            return self
        self._sill = sill_est
        self._nugget = sill_est * _NUGGET_FRAC

        P = np.asarray(pts)
        d2 = ((P[:, None, 0] - P[None, :, 0]) ** 2
              + (P[:, None, 1] - P[None, :, 1]) ** 2)
        d = np.sqrt(d2)
        K = self._nugget + self._sill * np.exp(-d / _RANGE_KM)
        # ordinary kriging: augment with unit row/col + Lagrange term
        n1 = n + 1
        A = np.empty((n1, n1))
        A[:n, :n] = K
        A[:n, n] = A[n, :n] = 1.0
        A[n, n] = 0.0
        try:
            self._lu = np.linalg.inv(A)
        except np.linalg.LinAlgError:
            return self
        self._pts = P
        self._vals = z
        self.on = True
        return self

    def estimate(self, lat, lon):
        """→ (µ̂ µg/m³, σ̂ µg/m³) or None when unfitted."""
        if not self.on:
            return None
        x, y = _to_km(lat, lon)
        d = np.sqrt((self._pts[:, 0] - x) ** 2 + (self._pts[:, 1] - y) ** 2)
        k = self._nugget + self._sill * np.exp(-d / _RANGE_KM)
        n = len(self._vals)
        rhs = np.empty(n + 1)
        rhs[:n] = k
        rhs[n] = 1.0
        w = self._lu @ rhs
        mu = float(w[:n] @ self._vals)
        # σ² = sill - w·k + λ   (Lagrange term is w[n])
        var = self._sill - float(w[:n] @ k) + w[n]
        return max(0.0, mu), math.sqrt(max(1.0, var))


KF = KrigeField()
