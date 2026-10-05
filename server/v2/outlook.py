"""GET /v2/outlook?lat&lon — the morning card's honest companion: the
days ahead, inside the REAL forecast horizon (docs/plan/alive-depth.md).

/v2/day answers "what about today"; this answers "what about this
week" — but only as far as the model actually reaches. CAMS serves 120
hourly slots, so the outlook is today's remainder plus up to four more
IST days. The last of those is usually a sliver (the horizon ends
~05:30 IST on its final day); it is served as-is with `partial`, never
padded into a fake week.

Each day folds the same served hours /v2/day emits — same live-anchored
CAMS horizon, same krige→climatology band blend, same anchor-decay
confidence machinery (imported from .day, not copied). Per-day numbers:

  pm25_mid      day mean of the served hourly mids
  pm25_lo/hi    mean ± the mean of its hours' band halves — hour errors
                are correlated, so there is no fake sqrt-n narrowing
  band          modal CPCB category of the day (its character)
  heavy_hours_ist  IST start-labels of every hour ≥ mean + ¼·spread;
                empty on flat days — a lone hot hour is noise, not a
                stretch (same rule as the card)
  cleanest_window  best contiguous ≥2 h run below mean − ¼·spread, or
                null on flat/short days
  confidence    the anchor-decay grade at the day's mid-horizon —
                'lo' where raw CAMS leads (day-4 says so in `note`)
  anchor_w      the day's anchor weight itself (exp(−h_mid/τ))

The `best_day` pick is the lowest day-mean — the honest "worth going
out" day. When every day sits within noise of the rest (same flat rule
as the card, applied to day means), there is no pick: the verdict says
"no meaningful difference between days".
"""
import math
from collections import Counter
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from . import deps
from .day import (_BAND_BASIS, _FLAT_REL, _FLAT_UG, _IST, _MODEL,
                  _TZ_NAME, _WIN_FRAC, _conf, _finite, _hour_entry,
                  _pick, _point_anchor, _refresh_both, _resolve_slot,
                  _runs, _window)

router = APIRouter()

# same 60 s (cell, hour, epoch) response cache as /v2/day — the five-day
# fold is the heaviest read on this router and repeat traffic is a judge
# pair refreshing, not new questions
_OUTLOOK_CACHE = deps.TTLCache(60.0, max_entries=256)

_MAX_EXTRA_DAYS = 4     # today's remainder + up to 4 more IST days
_H_HORIZON = 121        # probe hours 0..120 — the model's whole reach
_MIN_DAY_HOURS = 3      # a day needs >=3 served slots to read a window
_CLEAN_UG = 60.0        # 'cleanest' vs 'least-bad' honesty word (card rule)

_OUTLOOK_BAND_BASIS = _BAND_BASIS + (
    "; per-day lo/hi = day mean ± the mean of the day's hourly band "
    "halves — model error is correlated across the day, so the band is "
    "not narrowed by sqrt-n")


def _day_label(d, today) -> str:
    """'today' / 'tomorrow' / weekday name — the client's phrasing."""
    delta = (d - today).days
    if delta == 0:
        return "today"
    if delta == 1:
        return "tomorrow"
    return d.strftime("%A").lower()


def _fold_day(d, pairs, today, has_krige: bool, anchor_tau_h: float) -> dict:
    """Fold one IST day's served hours into its summary row.

    pairs: [(hour_row, band_half)] chronological — the same rows
    _hour_entry built for the card. Pure function over them."""
    rows = [p[0] for p in pairs]
    mids = [r["pm25_mid"] for r in rows]
    n = len(mids)
    mean = sum(mids) / n
    halves = [p[1] for p in pairs if p[1] is not None]
    band_half = sum(halves) / len(halves) if halves else None

    spread = max(mids) - min(mids)
    flat_day = n < _MIN_DAY_HOURS or spread < max(_FLAT_UG,
                                                  _FLAT_REL * mean)
    heavy_labels = []
    clean_win = None
    if not flat_day:
        thr_heavy = mean + _WIN_FRAC * spread
        thr_clean = mean - _WIN_FRAC * spread
        # every hour the model calls heavy — a real enumeration, not a
        # window claim; contiguity stays implicit in the labels
        heavy_labels = [r["ist_label"] for r in rows
                        if r["pm25_mid"] >= thr_heavy]
        clean = _pick(_runs(mids, thr_clean, above=False), mids, best=min)
        if clean[0] is not None:
            clean_win = _window(clean[0], clean[1], mids, rows,
                                open_end=False)

    h_mean = sum(r["h"] for r in rows) / n
    w = math.exp(-h_mean / anchor_tau_h)
    conf = _conf(w, has_krige)

    out = {
        "date_ist": str(d),
        "label": _day_label(d, today),
        "partial": n < 24,
        "n_hours": n,
        "pm25_mid": round(mean, 1),
        "pm25_lo": round(max(0.0, mean - band_half), 1)
        if band_half is not None else None,
        "pm25_hi": round(mean + band_half, 1)
        if band_half is not None else None,
        "band": Counter(r["band"] for r in rows).most_common(1)[0][0],
        "heavy_hours_ist": heavy_labels,
        "cleanest_window": clean_win,
        "confidence": conf,
        "anchor_w": round(w, 3),
    }
    if conf == "lo":
        out["note"] = (
            "past the live anchor's reach (weight ~%.1f%% at this "
            "day's mid-horizon) — raw CAMS skill only"
            % (100.0 * w))
    return out


def summarize_outlook(day_pairs, today, has_krige: bool,
                      anchor_tau_h: float) -> dict:
    """day_pairs: [(date, [(row, band_half), ...])] chronological.
    Returns {days, best_day, flat, verdict, horizon_hours} — pure, so
    tests can feed synthetic folds without the forecast field."""
    days = [_fold_day(d, pairs, today, has_krige, anchor_tau_h)
            for d, pairs in day_pairs]
    all_mids = [p[0]["pm25_mid"] for _d, pairs in day_pairs for p in pairs]
    horizon_hours = len(all_mids)

    means = [dd["pm25_mid"] for dd in days]
    day_spread = max(means) - min(means)
    mean_of_days = sum(means) / len(means)
    flat = day_spread < max(_FLAT_UG, _FLAT_REL * mean_of_days)

    out = {"days": days, "best_day": None, "flat": flat,
           "horizon_hours": horizon_hours, "verdict": ""}
    if flat:
        out["verdict"] = (
            "no meaningful difference between days — ~%.0f µg/m³ "
            "throughout the %d-day forecast" % (mean_of_days, len(days)))
        return out

    grand = sum(all_mids) / len(all_mids)
    best = min(days, key=lambda dd: dd["pm25_mid"])
    word = "least-bad" if best["pm25_mid"] > _CLEAN_UG else "cleanest"
    line = ("%s looks %s — avg ~%.0f vs ~%.0f µg/m³ across the %d-day forecast"
            % (best["label"], word, best["pm25_mid"], grand, len(days)))
    if best["n_hours"] < 12:
        line += (" (only its first ~%dh fall inside the forecast)"
                 % best["n_hours"])
    out["best_day"] = {
        "date_ist": best["date_ist"],
        "label": best["label"],
        "pm25_mid": best["pm25_mid"],
        "n_hours": best["n_hours"],
        "partial": best["partial"],
        "delta_vs_mean": round(best["pm25_mid"] - grand, 1),
        "line": line,
    }
    out["verdict"] = line
    return out


# ------------------------------------------------------------------ endpoint
@router.get("/outlook")
async def outlook(lat: float, lon: float):
    """The days ahead at a point — the honest reach of the horizon."""
    if not _finite(lat, lon):
        raise HTTPException(422, "non-finite coordinate")
    from airfield import in_service_area, OUT_OF_AREA
    if not in_service_area(lat, lon):
        return {"lat": lat, "lon": lon, "days": [], "error": OUT_OF_AREA}

    await _refresh_both()

    cache_key = (round(lat, 3), round(lon, 3),
                 datetime.now(timezone.utc).hour, deps.data_epoch())
    hit = _OUTLOOK_CACHE.get(cache_key)
    if hit is not None:
        return JSONResponse(hit, headers={"x-alive-cache": "hit"})

    from forecast import FORECAST
    try:
        from forecast import ANCHOR_TAU_H
    except Exception:
        ANCHOR_TAU_H = 9.0
    F = deps.field()
    ist_now = datetime.now(_IST)
    today = ist_now.date()
    sigma0, adj = _point_anchor(F, lat, lon, ist_now)

    # one field read per request; slots are chronological so each IST
    # date arrives contiguously — bucket on the first sight of a new date
    day_pairs = []
    cur_date = cur_rows = None
    for h in range(_H_HORIZON):
        slot = _resolve_slot(h)
        if slot is None:
            break                       # the model's end, not a hole
        _idx, t_iso, dt_utc = slot
        d = dt_utc.astimezone(_IST).date()
        delta = (d - today).days
        if delta < 0:
            continue
        if delta > _MAX_EXTRA_DAYS:
            break                       # today + up to 4 more, never a week
        if d != cur_date:
            cur_rows = []
            day_pairs.append((d, cur_rows))
            cur_date = d
        entry = _hour_entry(lat, lon, h, t_iso, dt_utc, sigma0, adj,
                            ANCHOR_TAU_H)
        if entry is None:
            continue                    # a real model hole — skipped
        cur_rows.append(entry)
    day_pairs = [(d, ps) for d, ps in day_pairs if ps]

    fstat = {}
    try:
        fstat = F.status() or {}
    except Exception:
        pass
    fcstat = {}
    try:
        fcstat = FORECAST.status() or {}
    except Exception:
        pass

    if not day_pairs:
        # cold or dead forecast — no outlook, not an outlook of holes
        # (/v2/day and /depart precedent: 'forecast unavailable')
        return {
            "lat": lat, "lon": lon, "tz": _TZ_NAME,
            "generated_ist": ist_now.isoformat(),
            "horizon_days": 0, "horizon_hours": 0,
            "days": [], "best_day": None, "flat": False,
            "verdict": "forecast unavailable — nothing honest to show",
            "model": _MODEL, "band_basis": _OUTLOOK_BAND_BASIS,
            "field_age_s": fstat.get("age_s"),
            "field": fstat, "forecast": fcstat,
            "error": "forecast unavailable",
        }

    s = summarize_outlook(day_pairs, today, sigma0 is not None,
                          ANCHOR_TAU_H)
    payload = {
        "lat": lat,
        "lon": lon,
        "tz": _TZ_NAME,
        "generated_ist": ist_now.isoformat(),
        "horizon_days": len(s["days"]),
        "horizon_hours": s["horizon_hours"],
        "days": s["days"],
        "best_day": s["best_day"],
        "flat": s["flat"],
        "verdict": s["verdict"],
        "model": _MODEL,
        "band_basis": _OUTLOOK_BAND_BASIS,
        "field_age_s": fstat.get("age_s"),
        "field": fstat,
        "forecast": fcstat,
    }
    _OUTLOOK_CACHE.put(cache_key, payload)
    return payload
