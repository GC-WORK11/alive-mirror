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


_SEARCH_IDX = None
_SEARCH_PIDS: list = []
_SEARCH_ENTRIES: Optional[list] = None
_REV_CELLS: Optional[dict] = None
_REV_CELL = 0.002  # ~221 m lat / ~196 m lon at Delhi's latitude


def _search_entries() -> list:
    """The T1 entry list — built once, shared by the search index and
    the reverse-lookup grid so /v2/reverse rides the same universe."""
    global _SEARCH_IDX, _SEARCH_PIDS, _SEARCH_ENTRIES
    if _SEARCH_ENTRIES is None:
        _SEARCH_ENTRIES = alive_core_ref.entries_from_gazetteer()
        _SEARCH_PIDS = [e["pid"] for e in _SEARCH_ENTRIES]
        _SEARCH_IDX = alive_core_ref.get_search_index(
            _SEARCH_ENTRIES, prefer_cpp=True)
    return _SEARCH_ENTRIES


def search_index():
    """T1 place index over the gazetteer+corpus universe — the same
    sources v2/gazetteer resolves (first readable file of each wins, so
    an image shipping only data/corpus still builds). alive_core.
    SearchIndex when the extension loads, PySearchIndex (identical
    semantics) otherwise. Built once: ~45k entries, alias-expanded."""
    _search_entries()
    return _SEARCH_IDX


def _rev_grid() -> dict:
    global _REV_CELLS
    if _REV_CELLS is None:
        cells: dict = {}
        for i, e in enumerate(_search_entries()):
            key = (math.floor(e["lat"] / _REV_CELL),
                   math.floor(e["lon"] / _REV_CELL))
            cells.setdefault(key, []).append(i)
        _REV_CELLS = cells
    return _REV_CELLS


def nearest(lat, lon, max_m: float = 150.0, limit: int = 16):
    """Reverse lookup: entry rows within max_m of a point.

    Chebyshev ring scan over a lat/lon grid of the SAME entries T1
    searches — no second index, no second data file. Returns
    [(entry_dict, distance_m)] sorted by distance."""
    ents = _search_entries()
    cells = _rev_grid()
    bi, bj = math.floor(lat / _REV_CELL), math.floor(lon / _REV_CELL)
    found: list = []
    r = 0
    # ring r's points can't sit closer than (r-1) * the cell's short
    # axis (~196 m) — stop once a ring is entirely past max_m.
    while (r - 1) * 196.0 <= max_m:
        for di in range(-r, r + 1):
            for dj in range(-r, r + 1):
                if max(abs(di), abs(dj)) != r:
                    continue
                for i in cells.get((bi + di, bj + dj), ()):
                    e = ents[i]
                    d = 1000.0 * alive_core_ref.haversine_km(
                        lat, lon, e["lat"], e["lon"])
                    if d <= max_m:
                        found.append((d, i))
        r += 1
        if r > 12:  # ~2.4 km ceiling — nothing this far is a reverse hit
            break
    found.sort()
    return [(ents[i], d) for d, i in found[:limit]]


def search(q, lat=None, lon=None, limit=8):
    """/v2/search T1 — index.query on whichever impl loaded. Index ids
    are positions (uint32 for the C++ binding); remap to the resolvable
    `pid` (gaz:<idx>/cor:<osm-id>) the gazetteer engine emits."""
    hits = search_index().query(q, lat, lon, limit)
    for h in hits:
        i = h.get("id")
        if isinstance(i, int) and 0 <= i < len(_SEARCH_PIDS):
            h["id"] = _SEARCH_PIDS[i]
    return hits


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
