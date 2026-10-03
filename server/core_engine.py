"""alive_core runtime shim — the C++ engine where the extension loads,
the verified Python reference where it doesn't (docs/plan/08).

`ENGINE` is the serving label: /health reports it, so the API never
claims C++ while answering from Python. Every adapter here reproduces
its counterpart's exact contract — krige.py's sample coercion/merge and
estimate semantics — and the parity suite (tests/test_core_parity.py,
tests/test_parity_field.py) bit-checks C++ vs Python on the same inputs.
"""

import math
from typing import Optional

import krige
import alive_core_ref

try:  # compiled extension — needs the eigen build for KrigeField
    import alive_core as _ac

    _CPP_KRIGE = hasattr(_ac, "KrigeField")
except Exception:  # no .so on this interpreter — Python serves
    _ac = None
    _CPP_KRIGE = False

# alive_core when the extension serves ANY hot path (FieldView/search/
# integrators aren't eigen-gated); krige separately reports per-adapter.
ENGINE = "alive_core" if _ac is not None else "python"


def field_view(src, coverage_km: float):
    """Snapshot field view — alive_core.FieldView when the extension
    loads, PyFieldView (identical semantics) otherwise. Wraps
    alive_core_ref.get_field_view; raises only what it raises."""
    return alive_core_ref.get_field_view(src, coverage_km, prefer_cpp=True)


class KrigeField:
    """Drop-in for krige.KrigeField — same fit(samples)/on/estimate.

    C++ KrigeField takes parallel (lat, lon, z) arrays and does no sample
    coercion, so the adapter replicates krige.py's contract around it:
    coerce + finite-check, merge bit-identical (lat, lon) by mean keeping
    first occurrence. Fit/estimate math is then identical by
    test_core_parity.
    """

    def __init__(self):
        self.on = False
        if _CPP_KRIGE:
            self._impl = "cpp"
            self._kf = _ac.KrigeField()
        else:
            self._impl = "py"
            self._kf = krige.KrigeField()

    def fit(self, samples, key="pm2_5"):
        self.on = False
        if self._impl == "py":
            self._kf.fit(samples, key=key)
            self.on = self._kf.on
            return self
        merged = {}  # (lat, lon) -> [z_sum, count]; dicts keep order
        for s in samples:
            try:
                lat, lon, _name, vals = s
                zf = float((vals or {}).get(key))
                latf, lonf = float(lat), float(lon)
            except (TypeError, ValueError, OverflowError, AttributeError):
                continue
            if not (math.isfinite(latf) and math.isfinite(lonf)
                    and math.isfinite(zf)):
                continue
            e = merged.get((latf, lonf))
            if e is None:
                merged[(latf, lonf)] = [latf, lonf, zf, 1.0]
            else:
                e[2] += zf
                e[3] += 1.0
        recs = list(merged.values())
        self.on = bool(self._kf.fit(
            [r[0] for r in recs], [r[1] for r in recs],
            [r[2] / r[3] for r in recs], _ac.KrigeParams()))
        return self

    def estimate(self, lat, lon) -> Optional[tuple]:
        if self._impl == "py":
            return self._kf.estimate(lat, lon)
        if not self.on:
            return None
        try:
            est = self._kf.estimate(float(lat), float(lon))
        except (TypeError, ValueError, OverflowError):
            return None
        if est is None:
            return None
        mu, sd = float(est[0]), float(est[1])
        return (mu, sd) if math.isfinite(mu) and math.isfinite(sd) else None


# airfield.py's module-level field — same role as krige.KF.
KF = KrigeField()
