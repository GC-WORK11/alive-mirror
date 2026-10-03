"""ALive-108 — kriging kernels, Python reference implementation.

Parity oracle for alive_core.KrigeField (server/core/src/krige.cpp) and the
runtime fallback shape it replaces. Ordinary mode mirrors
server/krige.py::KrigeField semantics exactly (same sill/nugget, same
covariance kernel, same augmented solve, same variance formula);
universal mode extends it with a per-station drift design for regression
kriging.

KrigeParams.legacy_variance selects the sigma formula:
  True  -> var = sill - w.k + lam.f0          (krige.py, drop-in parity)
  False -> var = (sill+nugget) - w.k - lam.f0 (exact error variance;
           krige.py under-reports sigma ~20-30% off-station — see
           docs/plan/bench-krige.md)

Signatures mirror the C++ class one-for-one:
  fit(lat, lon, z, params=None) -> bool
  fit_universal(lat, lon, z, drift, params=None) -> bool
  estimate(lat, lon, drift=None) -> (mu, sigma) | None
  weights(lat, lon, drift=None) -> [w | lam] | None

numpy is used for the (n+p)^2 solve when installed (krige.py needs it too);
a pure-Python partial-pivot LU fallback keeps the reference runnable
everywhere — parity-critical tests only need it on small systems.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional, Sequence

try:
    import numpy as _np
except ImportError:  # pragma: no cover - exercised only on numpy-less hosts
    _np = None

# lat/lon -> km at Delhi's latitude (identical to krige.py)
_KY = 110.6
_KX = 99.4
_RANGE_KM = 15.0
_NUGGET_FRAC = 0.15
_MIN_SAMPLES = 20
_SILL_FLOOR = 2.0


@dataclass
class KrigeParams:
    ky: float = _KY
    kx: float = _KX
    range_km: float = _RANGE_KM
    nugget_frac: float = _NUGGET_FRAC
    min_samples: int = _MIN_SAMPLES
    sill_floor: float = _SILL_FLOOR
    legacy_variance: bool = True


def _to_km(lat: float, lon: float, p: KrigeParams) -> tuple[float, float]:
    return lat * p.ky, lon * p.kx


def _covar(d: float, nugget: float, sill: float, rng: float) -> float:
    """krige.py covariance kernel: C(d) = nugget + sill*exp(-d/range)."""
    return nugget + sill * math.exp(-d / rng)


def _lu_solve(a: list[list[float]], b: list[float]) -> Optional[list[float]]:
    """Gaussian elimination with partial pivoting. -> x or None (singular)."""
    n = len(b)
    m = [row[:] + [b[i]] for i, row in enumerate(a)]
    for col in range(n):
        piv = max(range(col, n), key=lambda r: abs(m[r][col]))
        if abs(m[piv][col]) < 1e-300:
            return None
        if piv != col:
            m[col], m[piv] = m[piv], m[col]
        for r in range(col + 1, n):
            f = m[r][col] / m[col][col]
            if f == 0.0:
                continue
            for c in range(col, n + 1):
                m[r][c] -= f * m[col][c]
    x = [0.0] * n
    for i in range(n - 1, -1, -1):
        s = m[i][n] - sum(m[i][j] * x[j] for j in range(i + 1, n))
        x[i] = s / m[i][i]
    if not all(math.isfinite(v) for v in x):
        return None
    return x


class PyKrigeField:
    """Python reference for alive_core.KrigeField (see module docstring)."""

    def __init__(self) -> None:
        self._pts: list[tuple[float, float]] = []
        self._z: list[float] = []
        self._drift: list[list[float]] = []
        self._p = 0
        self._sill = 0.0
        self._nugget = 0.0
        self._params = KrigeParams()
        self._universal = False
        self._f0_default: list[float] = []   # ones(p) when ordinary
        self._ainv = None      # numpy inverse of the augmented matrix
        self._lu = None        # pure-python LU-factored augmented matrix
        self.on = False

    # ------------------------------------------------------------- fit
    def fit(self, lat: Sequence[float], lon: Sequence[float],
            z: Sequence[float], params: Optional[KrigeParams] = None) -> bool:
        """Ordinary kriging (drift = constant 1), krige.py-compatible."""
        return self._fit_impl(lat, lon, z, [[1.0]] * len(z), params, False)

    def fit_universal(self, lat: Sequence[float], lon: Sequence[float],
                      z: Sequence[float], drift: Sequence[Sequence[float]],
                      params: Optional[KrigeParams] = None) -> bool:
        return self._fit_impl(lat, lon, z, drift, params, True)

    def _fit_impl(self, lat, lon, z, drift, params, universal: bool) -> bool:
        self.on = False
        self._universal = universal
        self._params = params if params is not None else KrigeParams()
        p = self._params
        n = len(z)
        if not (n == len(lat) == len(lon) == len(drift)):
            return False
        if n < p.min_samples or not drift or not drift[0]:
            return False
        pw = len(drift[0])
        if any(len(row) != pw for row in drift):
            return False

        mean = sum(z) / n
        sill = sum((v - mean) ** 2 for v in z) / n   # population var (np.var)
        if not (sill >= p.sill_floor):
            return False
        self._sill = sill
        self._nugget = p.nugget_frac * sill
        self._p = pw
        self._pts = [_to_km(lat[i], lon[i], p) for i in range(n)]
        self._z = [float(v) for v in z]
        self._drift = [[float(v) for v in row] for row in drift]
        # bare estimate(lat, lon) works on ordinary fields, like krige.py;
        # universal queries must pass their target drift row
        self._f0_default = [] if self._universal else [1.0] * pw

        # augmented system [K F; F^T 0]
        m = n + pw
        A = [[0.0] * m for _ in range(m)]
        for i in range(n):
            xi, yi = self._pts[i]
            for j in range(n):
                xj, yj = self._pts[j]
                A[i][j] = _covar(math.hypot(xi - xj, yi - yj),
                                 self._nugget, sill, p.range_km)
            for a in range(pw):
                A[i][n + a] = self._drift[i][a]
                A[n + a][i] = self._drift[i][a]

        if _np is not None:
            try:
                self._ainv = _np.linalg.inv(_np.asarray(A))
            except _np.linalg.LinAlgError:
                return False
            self._lu = None
        else:
            self._ainv = None
            self._lu = A  # solved per-query with partial pivoting
            probe = _lu_solve([row[:] for row in A], [0.0] * (m - 1) + [1.0])
            if probe is None:
                return False
        self.on = True
        return True

    # ------------------------------------------------------- solve/query
    def _solve(self, lat: float, lon: float,
               drift: Optional[Sequence[float]]):
        if not self.on:
            return None
        f0 = list(drift) if drift is not None else []
        if not f0:
            f0 = self._f0_default
        if len(f0) != self._p:
            return None
        x, y = _to_km(lat, lon, self._params)
        n = len(self._z)
        rhs = [0.0] * (n + self._p)
        for i, (xi, yi) in enumerate(self._pts):
            rhs[i] = _covar(math.hypot(xi - x, yi - y), self._nugget,
                            self._sill, self._params.range_km)
        for a in range(self._p):
            rhs[n + a] = f0[a]
        if _np is not None:
            w = self._ainv @ _np.asarray(rhs)
            if not _np.all(_np.isfinite(w)):
                return None
            return w.tolist(), rhs
        w = _lu_solve([row[:] for row in self._lu], rhs)
        if w is None:
            return None
        return w, rhs

    def weights(self, lat: float, lon: float,
                drift: Optional[Sequence[float]] = None
                ) -> Optional[list[float]]:
        """Solved [w (n) | lam (p)] weight vector at the target."""
        out = self._solve(lat, lon, drift)
        return None if out is None else out[0]

    def estimate(self, lat: float, lon: float,
                 drift: Optional[Sequence[float]] = None
                 ) -> Optional[tuple[float, float]]:
        """-> (mu, sigma); mu clamped >= 0, sigma >= 1 (krige.py contract)."""
        out = self._solve(lat, lon, drift)
        if out is None:
            return None
        w, rhs = out
        n = len(self._z)
        k = rhs[:n]
        f0 = rhs[n:]
        wv, lam = w[:n], w[n:]
        mu = sum(wi * zi for wi, zi in zip(wv, self._z))
        wk = sum(wi * ki for wi, ki in zip(wv, k))
        lam_f = sum(li * fi for li, fi in zip(lam, f0))
        if self._params.legacy_variance:
            var = self._sill - wk + lam_f               # krige.py formula
        else:
            var = (self._sill + self._nugget) - wk - lam_f  # exact error var
        return max(0.0, mu), math.sqrt(max(1.0, var))

    # ------------------------------------------------------- introspection
    def fitted(self) -> bool:
        return self.on

    def n(self) -> int:
        return len(self._z)

    def n_drift(self) -> int:
        return self._p

    def sill(self) -> float:
        return self._sill

    def nugget(self) -> float:
        return self._nugget

    def range_km(self) -> float:
        return self._params.range_km
