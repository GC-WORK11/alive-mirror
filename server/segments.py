"""Per-segment dose decomposition — the 'hot zone' layer.

Splits a route into ~90-second spans and scores each with the same
physics as exposure.dose (same microenv/ventilation/uplift constants —
imported, not duplicated). The app draws these as the route's colour
ramp and names the worst stretch: '62% of this trip's dose is the
Ashram flyover'.

Honesty: concentration is sampled at each segment's midpoint and its
two quarter-points, mean-weighted — an approximation flagged alongside
exposure.dose's 250 m sampling (totals agree to within sampling error,
verified in tests).
"""
from typing import Callable, Optional

from exposure import (MICROENV, ROAD_UPLIFT, VENTILATION_LPM,
                      _haversine_m)

SEG_SECONDS = 90.0
_CONC_BINS = ((60.0, "#64748b"), (130.0, "#c2415c"), (1e9, "#7f1d1d"))


def conc_color(avg_conc: Optional[float]) -> str:
    for lim, hexv in _CONC_BINS:
        if avg_conc is None or avg_conc < lim:
            return hexv
    return "#7f1d1d"


def split_geometry(geometry: dict, duration_s: float,
                   seg_seconds: float = SEG_SECONDS) -> list:
    """Cut a LineString into time-proportional spans (uniform speed —
    same documented assumption as exposure.segment_samples)."""
    coords = geometry.get("coordinates", [])
    if len(coords) < 2 or duration_s <= 0:
        return []
    total = sum(_haversine_m(coords[i - 1], coords[i])
                for i in range(1, len(coords)))
    if total <= 0:
        return []
    span_m = total * seg_seconds / duration_s
    segs, cur, cur_m, carry_i = [], [coords[0]], 0.0, 0
    acc = 0.0
    for i in range(1, len(coords)):
        a, b = coords[i - 1], coords[i]
        seg_len = _haversine_m(a, b)
        acc += seg_len
        cur.append(b)
        if (acc - cur_m >= span_m) or i == len(coords) - 1:
            segs.append({"coords": cur, "dist_m": acc - cur_m})
            cur, cur_m = [b], acc
    out = []
    dist_seen = 0.0
    for s in segs:
        f0 = dist_seen / total
        dist_seen += s["dist_m"]
        out.append({
            "start_frac": round(f0, 4),
            "end_frac": round(dist_seen / total, 4),
            "seconds": duration_s * s["dist_m"] / total,
            "dist_m": s["dist_m"],
            "coords": s["coords"],
        })
    return out


def _midpoint(coords: list) -> list:
    total = sum(_haversine_m(coords[i - 1], coords[i])
                for i in range(1, len(coords)))
    half, acc = total / 2, 0.0
    for i in range(1, len(coords)):
        acc += _haversine_m(coords[i - 1], coords[i])
        if acc >= half:
            return coords[i]
    return coords[-1]


def segment_doses(geometry: dict, duration_s: float, mode: str,
                  field_value: Callable[[float, float], Optional[float]],
                  seg_seconds: float = SEG_SECONDS,
                  road_class: Optional[str] = None) -> list:
    """Per-segment records for one option. Field sampled at the
    midpoint + two quarter-points, mean-weighted."""
    microenv = MICROENV.get(mode, 1.0)
    ve = VENTILATION_LPM.get(mode, 8.0) / 1000.0
    uplift = ROAD_UPLIFT.get(road_class or "", 1.0)
    out = []
    for s in split_geometry(geometry, duration_s, seg_seconds):
        coords = s["coords"]
        pts = [coords[0], _midpoint(coords), coords[-1]]
        cs = [field_value(p[1], p[0]) for p in pts]
        cs = [c for c in cs if c is not None]
        conc = (sum(cs) / len(cs) * microenv * uplift) if cs else None
        minutes = s["seconds"] / 60.0
        out.append({
            "start_frac": s["start_frac"], "end_frac": s["end_frac"],
            "minutes": round(minutes, 2),
            "coords": coords,
            "avg_conc_ugm3": round(conc, 1) if conc is not None else None,
            "dose_ug": round(conc * ve * minutes, 1) if conc is not None else None,
            "color": conc_color(conc),
        })
    return out


def hotspots(segments: list) -> list:
    """1-3 contiguous worst-dose regions by dose share."""
    scored = [(i, s) for i, s in enumerate(segments)
              if s.get("dose_ug") is not None]
    if not scored:
        return []
    total = sum(s["dose_ug"] for _, s in scored) or 1.0
    ordered = sorted(scored, key=lambda t: t[1]["dose_ug"], reverse=True)
    out = []
    for i, s in ordered[:3]:
        mid = _midpoint(s["coords"])
        out.append({
            "label": "hot zone",
            "dose_ug": s["dose_ug"],
            "share_pct": round(s["dose_ug"] / total * 100, 1),
            "midpoint_coord": mid,
            "span_frac": [s["start_frac"], s["end_frac"]],
        })
    return out


def summary(segments: list) -> dict:
    doses = [s["dose_ug"] for s in segments if s.get("dose_ug") is not None]
    if not doses:
        return {"total_dose_ug": None, "hottest_share_pct": None,
                "hottest_span": None}
    total = sum(doses)
    hot = hotspots(segments)
    return {
        "total_dose_ug": round(total, 1),
        "hottest_share_pct": hot[0]["share_pct"] if hot else None,
        "hottest_span": hot[0]["span_frac"] if hot else None,
    }
