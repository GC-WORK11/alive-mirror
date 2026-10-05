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
import re
import time

from fastapi import APIRouter, HTTPException

from .store import LEDGER, TRIPS

router = APIRouter()

# community.observe folds the SAME privacy-trimmed points into ~500 m
# corridor cells — the citizen sensor layer that sharpens the kriged
# field. Only `kept` ever crosses the boundary: already trimmed of its
# endpoints, thinned, and rounded, so observe() stores nothing the
# privacy pipeline didn't already allow.

TRIM_M = 300.0          # drop this much from BOTH ends, always
THIN_M = 100.0          # keep at most one point per this distance
ROUND_DP = 4            # ~11 m — the documented precision ceiling
MAX_POINTS = 5000       # payload abuse guard

# Idempotency: a retried donation (network flake, offline queue replay)
# carries an identical trajectory — re-recording it would mint a trip
# that never happened in the totals. Signature = token hash + endpoint
# cells + distance + duration; a hit inside the window replays stored
# without double-counting. Per-worker memory is enough — the window is
# short and the privacy contract already caps corridor inflation at one
# device.
_DEDUPE: dict = {}
_DEDUPE_TTL_S = 24 * 3600
_DEDUPE_MAX = 4096


def _dupe_key(token_hash: str, cells: list, summary: dict) -> str:
    sig = "|".join([
        token_hash,
        str(cells[0]) if cells else "",
        str(cells[-1]) if cells else "",
        str(summary.get("distance_km") or ""),
        str(summary.get("duration_s") or ""),
    ])
    return hashlib.sha256(sig.encode()).hexdigest()[:24]


def _seen_dupe(key: str) -> bool:
    now = time.time()
    # expire cheaply on access; a full sweep only at the cap
    if len(_DEDUPE) >= _DEDUPE_MAX:
        for k, t in list(_DEDUPE.items()):
            if now - t > _DEDUPE_TTL_S:
                _DEDUPE.pop(k, None)
        if len(_DEDUPE) >= _DEDUPE_MAX:
            # evict the oldest slice — never clear(): a flood of fresh
            # keys must not wipe every live dedupe window and let a
            # replay double-count (hostile-read §7)
            for k, _t in sorted(_DEDUPE.items(),
                                key=lambda kv: kv[1])[:_DEDUPE_MAX // 8]:
                _DEDUPE.pop(k, None)
    if key in _DEDUPE and now - _DEDUPE[key] <= _DEDUPE_TTL_S:
        return True
    _DEDUPE[key] = now
    return False

# --- sanity bounds: the client is assumed hostile/buggy --------------------
# These don't need to be tight — they only have to kill payloads that can
# never be a real Delhi trip (e.g. distance_km=1e12 injected into the
# donations totals). Generous caps so an honest odd trip still counts.
_BOUNDS = {
    "distance_km": (0.0, 300.0),     # Delhi is ~50 km across; 300 is generous
    "duration_s": (0.0, 21600.0),    # 6 h of riding
    "dose_ug": (0.0, 50_000.0),      # worst-day × worst-ventilation orders below
    "co2_kg_mid": (0.0, 200.0),      # 300 km × heaviest fleet factor
    "pm25_g_mid": (0.0, 50.0),
    # optional phase split from the receipt's emissions.breakdown —
    # grams, mid estimates only; absent on old app builds / zero-emission
    # modes, and never fabricated server-side
    "co2_moving_g": (0.0, 300_000.0),
    "co2_idle_g": (0.0, 300_000.0),
    "co2_cold_g": (0.0, 300_000.0),
    # savings-vs-fastest fields the app computes off its own plan
    # receipt (router-dose minus taken-dose; co2 only counts when the
    # receipt was PUC-calibrated — flagged by puc_calibrated). Absent on
    # every donation that can't honestly know; never invented here.
    "avoided_ug": (0.0, 50_000.0),
    "co2_avoided_kg": (0.0, 200.0),
}
CO2_SPLIT_KEYS = ("co2_moving_g", "co2_idle_g", "co2_cold_g")
# A mode is a vehicle-class token — word characters, spaces and '+'.
# Anything carrying markup or punctuation can never reach mode_share.
# '+' is in the class because the planner itself emits multimodal modes
# ("metro+walk" in plan.py) — the server's own vocabulary must not be
# dropped on the way back in.
_MODE_RE = re.compile(r"^[a-z][a-z0-9_\- +]{0,23}$")

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
    """[{lat,lon} | [lon,lat] GeoJSON order] → [(lat, lon), ...].

    Points outside valid geo ranges are dropped — a garbage coordinate
    (lat=999 wraps onto a South-Atlantic h3 cell) must never land in the
    aggregates as a real traversal."""
    pts = []
    for p in traj or []:
        try:
            if isinstance(p, dict):
                la, lo = float(p["lat"]), float(p["lon"])
            elif isinstance(p, (list, tuple)) and len(p) >= 2:
                la, lo = float(p[1]), float(p[0])
            else:
                continue
        except (KeyError, TypeError, ValueError):
            continue
        if not (math.isfinite(la) and math.isfinite(lo)
                and -90.0 <= la <= 90.0 and -180.0 <= lo <= 180.0):
            continue
        pts.append((la, lo))
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


_SUMMARY_NUM = ("distance_km", "duration_s", "dose_ug",
                "co2_kg_mid", "pm25_g_mid") + CO2_SPLIT_KEYS + (
                "avoided_ug", "co2_avoided_kg")
_SUMMARY_FIELDS = _SUMMARY_NUM + ("mode", "switched", "puc_calibrated")


def _num(v) -> float | None:
    """Coerce a summary number; anything unparseable/non-finite is
    dropped — the store sums floats, and a hostile payload must never
    detonate a 500."""
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


@router.post("/trip")
async def post_trip(body: dict):
    token = str(body.get("device_token") or "")[:64]
    summary_in = body.get("summary") if isinstance(body.get("summary"), dict) else {}
    traj = body.get("trajectory") or body.get("coords")
    if not isinstance(traj, (list, tuple)):
        traj = []

    kept, trim_a, trim_b = privacy_pipeline(traj)
    # step 4: raw coordinates become cell keys here and are gone
    cells = [_cell(la, lo) for la, lo in kept]
    # the token is hashed before it can ever touch a store or a log
    token_hash = hashlib.sha256(token.encode()).hexdigest()[:16] \
        if token else ""

    summary = {}
    for k in _SUMMARY_NUM:
        v = _num(summary_in.get(k))
        lo, hi = _BOUNDS[k]
        if v is not None and lo <= v <= hi:
            summary[k] = v
    if summary_in.get("mode") is not None:
        m = str(summary_in["mode"]).strip().lower()
        if _MODE_RE.match(m):
            summary["mode"] = m
    if summary_in.get("switched"):
        summary["switched"] = bool(summary_in["switched"])
    if summary_in.get("puc_calibrated"):
        summary["puc_calibrated"] = bool(summary_in["puc_calibrated"])
    if not summary.get("distance_km"):
        # the one number every real trip carries — without it the payload
        # either failed every sanity check or was never a trip at all;
        # storing it would only mint a zero-km count that bumps the totals
        raise HTTPException(422, "missing or implausible distance_km")
    dupe = _seen_dupe(_dupe_key(token_hash, cells, summary))
    # endpoint areas for the admin global layer — the trimmed first/last
    # kept point snapped to its district/sub-district NAME (a string,
    # never a coordinate — the cell keys already carry the spatial
    # precision, the area just buckets them). None when the point lands
    # outside every baked boundary; the global layer skips those.
    origin_area = dest_area = None
    if kept:
        try:
            import districts as _dist
            o = _dist.area_for_point(kept[0][1], kept[0][0])
            e = _dist.area_for_point(kept[-1][1], kept[-1][0])
            origin_area = (o or {}).get("name")
            dest_area = (e or {}).get("name")
        except Exception:  # noqa: BLE001 — area rollup is cosmetic
            origin_area = dest_area = None
    if not dupe:
        TRIPS.record_trip(cells, summary, token_hash,
                          origin_area=origin_area, dest_area=dest_area)
        LEDGER.record(token_hash, summary)
    # feed the citizen layer — every donated trip is a sensor pass. The
    # coordinates that reach observe() are the trimmed/thinned/rounded
    # `kept` points (raw trajectory already gone); observe() folds them
    # straight into cells and never persists points. Without this hop a
    # trip counted in aggregates but never informed the field. A replay
    # must not mint phantom observations either — the dedupe guard holds.
    if kept and not dupe:
        try:
            import community
            community.observe(
                vehicle=str(summary.get("mode") or "unknown"),
                coords=[[lo, la] for la, lo in kept],
                duration_s=float(summary.get("duration_s") or 0.0),
                dose_ug=summary.get("dose_ug"),
                avoided_ug=summary.get("avoided_ug"),
                contributor=token or None,
                co2_kg=summary.get("co2_kg_mid"),
                # `kept` already ran privacy_pipeline above — telling
                # observe() that stops it re-trimming another 300 m off
                # the donated traversal's ends
                privacy_trimmed=True,
            )
        except Exception:  # noqa: BLE001 — aggregates already stored; a
            pass               # citizen-layer hiccup must not fail a donation
    return {
        "stored": True,
        "deduplicated": bool(dupe),
        "ledger_recorded": bool(token_hash),
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
