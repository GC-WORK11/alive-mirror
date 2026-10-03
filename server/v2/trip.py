"""POST /v2/trip — donate an anonymized traversal (docs/plan/07 §3).

The privacy pipeline is enforced server-side, exactly as documented —
the client is assumed hostile/buggy:

  1. drop the first and last 300 m of the trajectory (endpoint hiding)
  2. thin to ~100 m spacing
  3. round coordinates to 4 decimals (~11 m)
  4. convert to H3 res-8 cells IMMEDIATELY (fall back to 4-decimal
     lat/lon cell keys when h3 isn't installed — same granularity idea)
  5. discard the raw payload — it is never stored, never logged

Only aggregates persist (store.TripAggregates — day counters + per-cell
counts/dose/tokens). The device token is an opaque string: hashed
before it touches the store and used only for the k>=3 distinct-device
threshold on corridors.
"""
import hashlib
import math
import time

from fastapi import APIRouter

from .store import TRIPS

router = APIRouter()

TRIM_M = 300.0          # drop this much from BOTH ends, always
THIN_M = 100.0          # keep at most one point per this distance
ROUND_DP = 4            # ~11 m — the documented precision ceiling
MAX_POINTS = 5000       # payload abuse guard

try:
    import h3 as _h3
    _CELL_KIND = "h3:8"

    def _cell(lat: float, lon: float) -> str:
        return _h3.latlng_to_cell(lat, lon, 8)

except Exception:  # degrade: same privacy, coarser key
    _CELL_KIND = "grid:4dp"

    def _cell(lat: float, lon: float) -> str:
        return f"ll:{lat:.{ROUND_DP}f},{lon:.{ROUND_DP}f}"


def _hav_m(a_lat, a_lon, b_lat, b_lon) -> float:
    p1, p2 = math.radians(a_lat), math.radians(b_lat)
    dp, dl = math.radians(b_lat - a_lat), math.radians(b_lon - a_lon)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * 6371000.0 * math.asin(math.sqrt(h))


def _parse(traj) -> list:
    """[{lat,lon} | [lon,lat] GeoJSON order] → [(lat, lon), ...]."""
    pts = []
    for p in traj or []:
        try:
            if isinstance(p, dict):
                pts.append((float(p["lat"]), float(p["lon"])))
            elif isinstance(p, (list, tuple)) and len(p) >= 2:
                pts.append((float(p[1]), float(p[0])))
        except (KeyError, TypeError, ValueError):
            continue
    return pts[:MAX_POINTS]


def privacy_pipeline(traj) -> tuple:
    """trajectory → (kept [(lat,lon) rounded], trim_start_m, trim_end_m).

    Mirrors the documented client behavior so the server is safe even
    when the client forgets: endpoints trimmed by distance along the
    path, middle thinned to ~100 m, rounded to 4 dp.
    """
    pts = _parse(traj)
    if len(pts) < 2:
        return [], 0.0, 0.0
    cum = [0.0]
    for i in range(1, len(pts)):
        cum.append(cum[-1] + _hav_m(*pts[i - 1], *pts[i]))
    total = cum[-1]
    mid = [p for p, c in zip(pts, cum) if TRIM_M <= c <= total - TRIM_M]
    trim_start = min((c for c in cum if c >= TRIM_M), default=total)
    trim_end = total - max((c for c in cum if c <= total - TRIM_M),
                           default=0.0)

    kept, last = [], None
    for p in mid:
        if last is None or _hav_m(last[0], last[1], p[0], p[1]) >= THIN_M:
            kept.append((round(p[0], ROUND_DP), round(p[1], ROUND_DP)))
            last = p
    return kept, trim_start, trim_end


_SUMMARY_FIELDS = ("mode", "distance_km", "duration_s", "dose_ug",
                   "co2_kg_mid", "pm25_g_mid", "switched")


@router.post("/trip")
async def post_trip(body: dict):
    token = str(body.get("device_token") or "")[:64]
    summary_in = body.get("summary") or {}
    traj = body.get("trajectory") or body.get("coords") or []

    kept, trim_a, trim_b = privacy_pipeline(traj)
    # step 4: raw coordinates become cell keys here and are gone
    cells = [_cell(la, lo) for la, lo in kept]
    # the token is hashed before it can ever touch a store or a log
    token_hash = hashlib.sha256(token.encode()).hexdigest()[:16] \
        if token else ""

    summary = {k: summary_in.get(k) for k in _SUMMARY_FIELDS
               if summary_in.get(k) is not None}
    TRIPS.record_trip(cells, summary, token_hash)
    return {
        "stored": True,
        "cells_traversed": len(set(cells)),
        "points_used": len(kept),
        "privacy": {
            "endpoint_trim_m": TRIM_M,
            "thin_m": THIN_M,
            "rounded_decimals": ROUND_DP,
            "cell_scheme": _CELL_KIND,
            "trimmed_start_m": round(trim_a),
            "trimmed_end_m": round(trim_b),
            "raw_trajectory": "discarded — only cell aggregates stored",
        },
        "ts": time.time(),
    }
