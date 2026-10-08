"""GET /v2/stays + GET /v2/playtime — the hackathon's 'stay & play'
surfaces: where in Delhi to sleep tonight (least average pollution),
and when in the coming day your area's air is at its lightest.

Both stand on the same two live primitives the rest of /v2 serves:

  * airfield.FIELD — the current concentration field. value() is the
    advection-weighted IDW over live station reads (named stations x3,
    upwind gain) with the krige posterior where the variogram fit holds,
    or the snapshot cell when the snapshot is fresher. sigma(),
    nearest_station_km() and beyond_field_edge() are what 'honest now'
    means here.
  * forecast.FORECAST — the live-anchored CAMS hourly horizon (120 h),
    readable at ARBITRARY points: IDW over the fetched grid, ventilation
    stagnation correction, semi-Lagrangian advected-origin sampling on
    10 m wind, parcel-bias delta (decays ~9 h) + the fitted persistence
    blend (w=1 through h+2, linear to 0 by h+40). That is what lets
    /v2/stays score a stay's own coordinates over the next 24 h — not a
    district average relabelled.

/v2/playtime folds the next 24 served forecast hours at a point into
the best and worst contiguous windows — '06:30-09:30 tomorrow is the
light stretch'. The hour rows and window machinery are v2.day's own
(same _hour_entry/_resolve_slot/_window shapes, krige->climatology band
blend, anchor-decay confidence); this endpoint's fold rolls past IST
midnight, which is exactly where /v2/day stops by design.

/v2/stays scans the committed corpus' lodging rows (hotel / hostel /
guest-house / resort / lodging kinds — ~15k of the 344,923 entries),
takes the nearest pool, reads each row's own next-24h forecast mean and
live-now at ITS coordinates, and ranks by the air you would actually
breathe there. Rows the field can't read (edge, no forecast slot) sort
last flagged 'unrated' — never a borrowed number.

near= accepts 'lat,lon' or a place name resolved through the same T1
engine /v2/search picks (alive_core when the extension loads, the
bit-identical ref otherwise — the plain-gazetteer scan as last resort).
Nothing is invented: a dead forecast scores 'now' only and says so; an
unresolvable place is a 404, not a centre-of-Delhi guess.
"""
import asyncio
import math
import re
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse

from . import deps
from .day import (_BAND_BASIS, _IST, _MODEL, _TZ_NAME, _conf, _finite,
                  _hour_entry, _point_anchor, _refresh_both,
                  _resolve_slot, summarize_day)
from .gazetteer import GAZ, _haversine_m

router = APIRouter()

# same 60 s (cell, hour, epoch) response cache as /v2/day/outlook —
# repeat opens share one compute; a field/forecast refresh invalidates
# through deps.data_epoch() inside the key
_EXPLORE_CACHE = deps.TTLCache(60.0, max_entries=128)

_H_WINDOW = 24            # 'the next day' — the window both surfaces share
_STAY_POOL = 40           # nearest lodging rows fully field-scored per ask
# 'sparse' = the point sits outside the served field's extent, has no
# live monitor answer at all, or is farther than ~2x Delhi's mean
# instrument spacing (~6 km) from a named station — the read is real but
# thin, and the wire says so with the distance itself
_SPARSE_STATION_KM = 12.0

_LL = re.compile(r"^\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*$")


# ------------------------------------------------------------------ near=
async def _resolve_near(near: Optional[str], lat, lon) -> Optional[dict]:
    """{lat, lon, name, kind, via} for the ask — explicit lat/lon query
    params win, then near='lat,lon', then a place phrase through the
    /v2/search T1 engine (off-loop: a first-hit gazetteer index build
    can cost seconds). None = unresolvable, caller answers honestly.
    Raises 422 when the request carries no anchor at all."""
    if lat is not None and lon is not None:
        return {"lat": float(lat), "lon": float(lon),
                "name": None, "via": "coords"}
    if near is None:
        raise HTTPException(422, "near or lat+lon required")
    s = str(near).strip()
    if not s:
        raise HTTPException(422, "empty near")
    m = _LL.match(s)
    if m:
        return {"lat": float(m.group(1)), "lon": float(m.group(2)),
                "name": None, "via": "coords"}
    from .search import _t1, _T1_EXEC
    loop = asyncio.get_running_loop()
    try:
        rows = await loop.run_in_executor(
            _T1_EXEC, _t1, s, deps.DELHI_CENTER["lat"],
            deps.DELHI_CENTER["lon"], 1)
    except Exception:
        rows = []
    if not rows:
        return None
    r = rows[0]
    return {"lat": float(r["lat"]), "lon": float(r["lon"]),
            "name": r.get("name"), "kind": r.get("kind"),
            "via": "search"}


def _sparsity(F, lat: float, lon: float) -> dict:
    """The thin-read disclosure: beyond the served field's edge the
    value is extrapolated edge evidence, and a point far from any named
    monitor leans on model fill — real, but the client must be able to
    say 'nearest monitor ~N km' instead of implying a local read."""
    try:
        beyond = bool(F.beyond_field_edge(lat, lon))
    except Exception:
        beyond = False
    try:
        km = F.nearest_station_km(lat, lon)
        station_km = round(km, 1) if math.isfinite(km) else None
    except Exception:
        station_km = None
    return {
        "sparse": beyond or station_km is None
                  or station_km > _SPARSE_STATION_KM,
        "beyond_edge": beyond,
        "nearest_station_km": station_km,
    }


# ---------------------------------------------------------------- lodging
# every corpus/gazetteer kind that means 'a roof you can sleep under'
# (STATS.md categories: overture:hotel 6732, overture:resort 3608,
# hotel 2627, overture:lodging 2020, tourism:hotel 534, tourism:hostel
# 182, overture:private_lodging 223, tourism:guest_house 82,
# tourism:apartment 57, building:hotel 18, amenity/landuse strays ~20)
_LODGE_PREFIX = ("overture:hotel", "overture:resort", "overture:lodging",
                 "overture:private_lodging")
_LODGE_MARK = ("hotel", "hostel", "lodg", "resort", "guest_house",
               "guesthouse", "motel", "dharamshala", "accommodation",
               "tourism:apartment")


def _is_lodging(kind: Optional[str]) -> bool:
    k = (kind or "").lower()
    return (k.startswith(_LODGE_PREFIX)
            or any(m in k for m in _LODGE_MARK))


_LODGE_ROWS: Optional[list] = None


def _lodging_rows() -> list:
    """The corpus' lodging slice — the same deduped slim rows the T1
    index and /v2/place read (GAZ._load is process-shared: the parse is
    paid once for every consumer)."""
    global _LODGE_ROWS
    if _LODGE_ROWS is None:
        _LODGE_ROWS = [r for r in GAZ._load()
                       if r.get("lat") is not None
                       and r.get("lon") is not None
                       and _is_lodging(r.get("kind"))]
    return _LODGE_ROWS


def _band_of(pm25: Optional[float]) -> str:
    import districts
    return districts.cpcb_band(districts.cpcb_aqi(pm25))[0] \
        if pm25 is not None else "No data"


# ------------------------------------------------------------------ stays
@router.get("/stays")
async def stays(near: Optional[str] = None,
                lat: Optional[float] = None, lon: Optional[float] = None,
                k: int = Query(default=8, ge=1, le=15)):
    """Lodging rows ranked by the air at their own coordinates.

    Score = mean of the live-anchored forecast over the next _H_WINDOW
    hours at the stay's lat/lon — 'least average pollution', not the
    anchor's air relabelled. Rows with no honest read sort last,
    flagged."""
    place = await _resolve_near(near, lat, lon)
    if place is None:
        return JSONResponse(status_code=404, content={
            "error": "place not found — pass near=lat,lon or a name "
                     "the gazetteer knows"})
    alat, alon = place["lat"], place["lon"]
    if not _finite(alat, alon):
        raise HTTPException(422, "non-finite coordinate")
    from airfield import in_service_area, OUT_OF_AREA
    if not in_service_area(alat, alon):
        return {"near": place, "stays": [], "error": OUT_OF_AREA}

    await _refresh_both()

    cache_key = ("stays", round(alat, 3), round(alon, 3), k,
                 datetime.now(_IST).hour, deps.data_epoch())
    hit = _EXPLORE_CACHE.get(cache_key)
    if hit is not None:
        return JSONResponse(hit, headers={"x-alive-cache": "hit"})

    from forecast import FORECAST
    F = deps.field()

    try:
        anchor_now = F.value(alat, alon)
        anchor_now = float(anchor_now) if anchor_now is not None else None
    except Exception:
        anchor_now = None

    # nearest _STAY_POOL lodging rows by distance get a full score —
    # ranking air-first inside a bounded neighbourhood, not the whole
    # corpus (an uncapped scan would grade rows 60 km away as 'near')
    rows = _lodging_rows()
    pool = sorted(
        (r for r in rows),
        key=lambda r: _haversine_m(alat, alon, r["lat"], r["lon"]))[:_STAY_POOL]

    window_h = 0
    out_rows = []
    for r in pool:
        slat, slon = float(r["lat"]), float(r["lon"])
        dist_m = _haversine_m(alat, alon, slat, slon)
        try:
            pm_now = F.value(slat, slon)
            pm_now = float(pm_now) if pm_now is not None else None
        except Exception:
            pm_now = None
        vals = []
        for h in range(_H_WINDOW):
            try:
                v = FORECAST.pm25(slat, slon, h)
            except Exception:
                v = None
            if v is not None:
                vals.append(v)
        wmean = (sum(vals) / len(vals)) if vals else None
        if vals:
            window_h = max(window_h, len(vals))
        # the ranked number prefers the window mean (the stay's next
        # day); with a dead horizon the live read alone still ranks,
        # disclosed per row via scored_on
        score = wmean if wmean is not None else pm_now
        sp = _sparsity(F, slat, slon)
        out_rows.append({
            "id": (f"gaz:{r['idx']}" if isinstance(r.get("idx"), int)
                   else f"cor:{r.get('idx')}"),
            "name": r["name"],
            "kind": r.get("kind") or "lodging",
            "lat": slat, "lon": slon,
            "dist_km": round(dist_m / 1000.0, 1),
            "pm25_now": round(pm_now, 1) if pm_now is not None else None,
            "window_mean_ug": round(wmean, 1) if wmean is not None else None,
            "n_hours": len(vals),
            "scored_on": ("next24h" if wmean is not None
                          else "now" if pm_now is not None else "unrated"),
            "band": _band_of(score),
            "cleaner_by_ug": (round(anchor_now - pm_now, 1)
                              if anchor_now is not None
                              and pm_now is not None else None),
            "sparse": sp["sparse"],
            "nearest_station_km": sp["nearest_station_km"],
        })

    out_rows.sort(key=lambda r: (
        r["scored_on"] == "unrated",
        r["window_mean_ug"] if r["window_mean_ug"] is not None else 1e9,
        r["pm25_now"] if r["pm25_now"] is not None else 1e9,
        r["dist_km"]))
    out_rows = out_rows[:k]

    fstat, fcstat = {}, {}
    try:
        fstat = F.status() or {}
    except Exception:
        pass
    try:
        fcstat = FORECAST.status() or {}
    except Exception:
        pass

    anchor_sparse = _sparsity(F, alat, alon)
    payload = {
        "near": place,
        "stays": out_rows,
        "k": k,
        "window_h": _H_WINDOW if window_h else 0,
        "scored_h": window_h,
        "lodging_rows": len(rows),
        "ranked_on": ("mean of the anchored forecast over the next "
                      f"{window_h} h at each stay's coordinates"
                      if window_h else
                      "the live field read only — forecast unavailable"),
        "anchor_pm25_now": (round(anchor_now, 1)
                            if anchor_now is not None else None),
        "anchor_band": _band_of(anchor_now),
        "sparse": anchor_sparse["sparse"],
        "beyond_edge": anchor_sparse["beyond_edge"],
        "nearest_station_km": anchor_sparse["nearest_station_km"],
        "model": _MODEL,
        "field_age_s": fstat.get("age_s"),
        "field": fstat,
        "forecast": fcstat,
        "ts": round(datetime.now(_IST).timestamp()),
    }
    _EXPLORE_CACHE.put(cache_key, payload)
    return payload


# ---------------------------------------------------------------- playtime
@router.get("/playtime")
async def playtime(near: Optional[str] = None,
                   lat: Optional[float] = None, lon: Optional[float] = None):
    """The next-24 h air curve at a place → its lightest contiguous
    window — 'kids out 06:30-09:30, ~34 µg/m³ lighter than now'.

    Same served hours as /v2/day (same _hour_entry bands + confidence),
    folded across the IST midnight it stops at: the clean stretch in
    Delhi winter is usually tomorrow morning, and this endpoint exists
    to reach it."""
    place = await _resolve_near(near, lat, lon)
    if place is None:
        return JSONResponse(status_code=404, content={
            "error": "place not found — pass near=lat,lon or a name "
                     "the gazetteer knows"})
    alat, alon = place["lat"], place["lon"]
    if not _finite(alat, alon):
        raise HTTPException(422, "non-finite coordinate")
    from airfield import in_service_area, OUT_OF_AREA
    if not in_service_area(alat, alon):
        return {"near": place, "hours": [], "error": OUT_OF_AREA}

    await _refresh_both()

    cache_key = ("play", round(alat, 3), round(alon, 3),
                 datetime.now(_IST).hour, deps.data_epoch())
    hit = _EXPLORE_CACHE.get(cache_key)
    if hit is not None:
        return JSONResponse(hit, headers={"x-alive-cache": "hit"})

    from forecast import FORECAST, anchor_w as _aw
    F = deps.field()
    ist_now = datetime.now(_IST)
    today = ist_now.date()
    sigma0, adj = _point_anchor(F, alat, alon, ist_now)

    hours = []
    for h in range(_H_WINDOW):
        slot = _resolve_slot(h)
        if slot is None:
            break                       # the model's end, not a hole
        _idx, t_iso, dt_utc = slot
        entry = _hour_entry(alat, alon, h, t_iso, dt_utc, sigma0, adj,
                            _aw)
        if entry is None:
            continue                  # real hole — skipped, never 0
        row = entry[0]
        row["date_ist"] = str(dt_utc.astimezone(_IST).date())
        row["day_offset"] = (dt_utc.astimezone(_IST).date() - today).days
        hours.append(row)

    fstat, fcstat = {}, {}
    try:
        fstat = F.status() or {}
    except Exception:
        pass
    try:
        fcstat = FORECAST.status() or {}
    except Exception:
        pass

    base = {
        "near": place,
        "tz": _TZ_NAME,
        "generated_ist": ist_now.isoformat(timespec="seconds"),
        "model": _MODEL,
        "band_basis": _BAND_BASIS,
        "field_age_s": fstat.get("age_s"),
        "field": fstat,
        "forecast": fcstat,
    }

    if not hours:
        return {**base, "hours": [], "served_h": 0,
                "now_pm25": None, "mean_pm25": None,
                "best_window": None, "worst_window": None,
                "cleaner_by_ug": None, "flat": True,
                "confidence": None, "verdict": "forecast unavailable",
                "decisions": [],
                "sparse": True, "beyond_edge": None,
                "nearest_station_km": None,
                "error": "forecast unavailable"}

    fold = summarize_day(hours)
    by_h = {r["h"]: r for r in hours}
    for wkey in ("cleanest_window", "heavy_window"):
        w = fold.get(wkey)
        if not w:
            continue
        st = by_h.get(w["start_h"])
        en = by_h.get(w["end_h"]) if w["end_h"] is not None else None
        w["start_day_offset"] = st["day_offset"] if st else 0
        w["end_day_offset"] = en["day_offset"] if en else st["day_offset"] if st else 0
        w["basis"] = w["basis"].replace("day mean", "next-24h mean")

    best, worst = fold["cleanest_window"], fold["heavy_window"]
    now_pm = hours[0]["pm25_mid"]
    mean = fold["day_mean"]
    cleaner = (round(now_pm - best["pm25_mid"], 1)
               if best is not None else None)
    flat = best is None and worst is None

    rank = {"lo": 0, "med": 1, "hi": 2}
    conf = min((r["confidence"] for r in hours),
               key=lambda c: rank.get(c, -1), default=None)
    sp = _sparsity(F, alat, alon)

    def _day_word(off):
        return "today" if off == 0 else "tomorrow" if off == 1 else \
            f"in {off} days"

    if flat:
        verdict = ("air barely moves across the next day — "
                   f"~{mean:.0f} µg/m³ on average, no window")
    elif best is not None:
        word = "cleanest" if best["pm25_mid"] <= 60.0 else "least-bad"
        end = best["end_label"] or "on"
        delta = (f" — {cleaner:.0f} µg/m³ lighter than now"
                 if cleaner is not None and cleaner > 0 else "")
        verdict = (f"{word} window {best['start_label']}-{end} "
                   f"{_day_word(best['start_day_offset'])}, ~"
                   f"{best['pm25_mid']:.0f} µg/m³ avg{delta}")
    else:
        verdict = ("no clean stretch on the horizon — lightest reads "
                   f"{fold['day_min']:.0f} µg/m³")

    payload = {**base,
               "hours": hours,
               "served_h": len(hours),
               "window_h": _H_WINDOW,
               "now_pm25": now_pm,
               "mean_pm25": mean,
               "best_window": best,
               "worst_window": worst,
               "cleaner_by_ug": cleaner,
               "flat": flat,
               "confidence": conf,
               "verdict": verdict,
               "decisions": fold["decisions"],
               "sparse": sp["sparse"],
               "beyond_edge": sp["beyond_edge"],
               "nearest_station_km": sp["nearest_station_km"]}
    _EXPLORE_CACHE.put(cache_key, payload)
    return payload
