"""GET /v2/day?lat&lon — the morning card's day-at-a-point
(docs/plan/alive-depth.md L2).

One honest answer for the rest of today: the hourly PM2.5 series at the
queried point from the same live-anchored CAMS horizon /depart and
/grid?h= serve, folded into the two windows a Delhiite plans around —
today's heavy stretch and the cleanest slot — plus the one decision each
window changes ("run after 11", "kids out before 5"). Flat days say so
honestly; a window is a contiguous run of >=2 hours, never a lone dip.

Coverage is the remaining hours of the current IST day, not a padded
24 h — forecast slots are UTC-hourly (the model's own grid), so IST
labels land on :30 boundaries. Slots with no model value are skipped,
never zero-filled.

Bands: pm25_lo/hi open at the krige sigma the live field carries at the
point and widen toward this clock-hour's measured climatological spread
(OpenAQ p25-p75, ~9M station-hours — /shift's band basis) as the live
anchor decays. The blend weight is the horizon's own e-fold
(forecast.ANCHOR_TAU_H, ~9 h): at h=0 the band is the krige band; past
the anchor's reach it is the measured variability of that hour. When
neither band source exists the keys are null — no invented precision.
`confidence` is the anchor-decay grade (hi while the nowcast dominates,
lo once raw CAMS does), capped at 'med' when the point carries no krige
band at all.
"""
import asyncio
import math
import time
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException

from . import deps

router = APIRouter()

_IST = timezone(timedelta(hours=5, minutes=30))
_H_DAY = 24          # hard cap — the served window is today's remainder
_MIN_RUN = 2         # a lone hour is noise, not a window
_FLAT_UG = 15.0      # spread below this reads flat whatever the level
_FLAT_REL = 0.15     # …or below 15% of the day's own mean
_WIN_FRAC = 0.25     # a window must sit >= 1/4 of the day spread off the mean

_TZ_NAME = "Asia/Kolkata"
_MODEL = ("CAMS hourly forecast x ventilation stagnation correction, "
          "advected on 10 m wind, anchored to the live station field "
          "(anchor decays ~9 h)")


def _finite(lat, lon) -> bool:
    return math.isfinite(lat) and math.isfinite(lon)


def _ist_label(dt_utc: datetime) -> str:
    """Slot-start rendered as a Delhi clock time, e.g. '17:30'."""
    return dt_utc.astimezone(_IST).strftime("%H:%M")


def _conf(anchor_w: float, has_krige_sigma: bool) -> str:
    """Anchor-decay confidence grade: hi while the nowcast dominates
    (w>=0.7 ~ h<=3), med through the e-fold (w>=0.35 ~ h<=9), lo where raw
    CAMS leads. No krige band at the point caps at 'med' — the band there
    is climatological spread, not a measured interpolation error."""
    g = "hi" if anchor_w >= 0.7 else "med" if anchor_w >= 0.35 else "lo"
    if g == "hi" and not has_krige_sigma:
        return "med"
    return g


# ------------------------------------------------------------------ windows
def _runs(mids: list, thr: float, above: bool) -> list:
    """Maximal contiguous index runs with mid >=/<= thr, len>=_MIN_RUN."""
    runs, start = [], None
    for i, m in enumerate(mids):
        hit = m >= thr if above else m <= thr
        if hit and start is None:
            start = i
        elif not hit and start is not None:
            if i - start >= _MIN_RUN:
                runs.append((start, i - 1))
            start = None
    if start is not None and len(mids) - start >= _MIN_RUN:
        runs.append((start, len(mids) - 1))
    return runs


def _pick(runs: list, mids: list, best=max) -> tuple:
    """Run with the extremal mean mid (best=max for heavy, min for
    clean); ties go to the longer run."""
    pick, pick_mean = None, None
    for a, b in runs:
        mean = sum(mids[a:b + 1]) / (b - a + 1)
        if pick is None or best(mean, pick_mean) != pick_mean or (
                mean == pick_mean and b - a > pick[1] - pick[0]):
            pick, pick_mean = (a, b), mean
    return pick, pick_mean


def _window(run, mean, mids, hours, open_end: bool) -> dict:
    """Window dict for a contiguous run — h-indexed, IST labels carried
    for the card. end_h=None marks a run still open at the day's last
    served hour ('through day end'), only honest where the day could
    continue beyond the card — the heavy window. The clean window's end
    is always known: the card ends at day end."""
    a, b = run
    end_open = open_end and b == len(mids) - 1
    return {
        "start_h": hours[a]["h"],
        "end_h": None if end_open else hours[b]["h"],
        "start_label": hours[a]["ist_label"],
        "end_label": None if end_open else _end_label(hours[b]),
        "pm25_mid": round(mean, 1),
        "basis": ("pm25 %.0f vs day mean %.0f ug/m3 — %s" % (
            mean, sum(mids) / len(mids),
            "runs to day end" if end_open else "contiguous run")),
    }


def _end_label(hour_entry: dict) -> str:
    """IST clock label of a slot's END (its start + 1 h)."""
    return (datetime.fromisoformat(hour_entry["start"])
            + timedelta(hours=1)).astimezone(_IST).strftime("%H:%M") \
        if hour_entry.get("start") else hour_entry["ist_label"]


def _fmt_window(w: dict) -> str:
    """'~06:30-08:30' or '~22:30-' for an open-ended run."""
    return "~%s-%s" % (w["start_label"], w["end_label"] or "")


def summarize_day(hours: list) -> dict:
    """Fold the hour series into the card's windows + decisions.

    hours: [{h, ist_label, pm25_mid, band, ...}] — pure function over the
    served mids, no network. Returns {day_mean, day_min, day_max,
    heavy_window, cleanest_window, decisions} — windows null when no
    contiguous run clears the spread rule, and on a flat/short day both
    are null with the decisions saying so in plain words."""
    mids = [hh["pm25_mid"] for hh in hours]
    n = len(mids)
    mean = sum(mids) / n
    lo_d, hi_d = min(mids), max(mids)
    out = {"day_mean": round(mean, 1), "day_min": lo_d, "day_max": hi_d,
           "heavy_window": None, "cleanest_window": None, "decisions": []}

    if n < 3:
        out["decisions"].append({
            "label": "today",
            "line": ("only ~%dh of today left on the card — %s throughout"
                     % (n, hours[-1]["band"]))})
        return out

    spread = hi_d - lo_d
    if spread < max(_FLAT_UG, _FLAT_REL * mean):
        # a flat day is a real finding — the card must not invent a
        # 'best hour' out of noise
        out["decisions"].append({
            "label": "today",
            "line": ("no meaningful window today — %s air all day "
                     "(%.0f-%.0f ug/m3)"
                     % (_day_band_word(hours), lo_d, hi_d))})
        return out

    thr_heavy = mean + _WIN_FRAC * spread
    thr_clean = mean - _WIN_FRAC * spread
    heavy = _pick(_runs(mids, thr_heavy, above=True), mids, best=max)
    clean = _pick(_runs(mids, thr_clean, above=False), mids, best=min)

    if heavy[0] is not None:
        out["heavy_window"] = _window(
            heavy[0], heavy[1], mids, hours, open_end=True)
    if clean[0] is not None:
        out["cleanest_window"] = _window(
            clean[0], clean[1], mids, hours, open_end=False)

    out["decisions"] = _decisions(hours, out, mean)
    return out


def _day_band_word(hours: list) -> str:
    """The day's modal CPCB band — 'very poor', 'severe'…"""
    bands = [h.get("band") or "unknown" for h in hours]
    return max(set(bands), key=bands.count).lower()


def _decisions(hours: list, day: dict, mean: float) -> list:
    """The one honest line each window changes. Generated from the
    windows actually found — a clean dip, a heavy stretch, both, or a
    day that never eases. No line asserts a health outcome; each just
    names the slot the data argues for."""
    ds = []
    clean, heavy = day["cleanest_window"], day["heavy_window"]

    if clean is not None:
        # 'cleanest' never claims clean — under a poor-grade window the
        # card says 'least-bad', which is what the numbers mean
        word = ("least-bad" if clean["pm25_mid"] > 60.0 else "cleanest")
        ds.append({
            "label": "outdoor exercise",
            "line": "%s window %s IST (avg %.0f ug/m3 vs day %.0f)"
                    % (word, _fmt_window(clean), clean["pm25_mid"], mean)})
    elif heavy is not None:
        ds.append({
            "label": "outdoor exercise",
            "line": "no clean slot left today — lightest is %.0f ug/m3"
                    % day["day_min"]})

    if heavy is not None:
        if heavy["end_h"] is None and heavy["start_h"] <= hours[0]["h"]:
            ds.append({
                "label": "kids outdoors",
                "line": ("indoors today — heavy all day "
                         "(~%.0f ug/m3 avg)" % mean)})
        else:
            ds.append({
                "label": "kids outdoors",
                "line": "before ~%s IST%s"
                        % (heavy["start_label"],
                           "" if heavy["end_h"] is not None
                           else "; heavy through day end")})
    elif clean is not None:
        ds.append({
            "label": "kids outdoors",
            "line": ("no heavy window today — worst is %.0f ug/m3; "
                     "easiest %s" % (day["day_max"], _fmt_window(clean)))})

    if clean is not None and heavy is not None:
        ds.append({
            "label": "windows open",
            "line": "open %s; shut from ~%s IST"
                    % (_fmt_window(clean), heavy["start_label"])})
    return ds


# ------------------------------------------------------------------ endpoint
async def _refresh_both() -> None:
    """Field + forecast refresh — both bounded, neither may raise."""
    async def _f():
        try:
            await asyncio.wait_for(deps.field_refresh(), timeout=10.0)
        except Exception:
            pass

    async def _fc():
        try:
            from forecast import FORECAST
            await asyncio.wait_for(FORECAST.refresh(deps.http()),
                                   timeout=12.0)
        except Exception:
            pass

    await asyncio.gather(_f(), _fc())


def _hour_sigma0(F, lat: float, lon: float) -> Optional[float]:
    """The live field's own krige band at the point (None on IDW /
    sigma-less serving — honest absence, same as /aqi)."""
    try:
        return F.sigma(lat, lon)
    except Exception:
        return None


def _clim_half_iqr(lat: float, lon: float, month: int, hour_ist: int,
                   adj: float) -> Optional[float]:
    """Measured spread of this clock-hour at this point: half the
    interquartile range of ~9 M station-hour climatology, scaled by
    today's live-vs-typical delta (the /shift convention). None when the
    archive has no band for the bucket."""
    try:
        import history
        band = history.typical_band(lat, lon, month, hour_ist)
    except Exception:
        return None
    p25, p75 = band.get("p25"), band.get("p75")
    if p25 is None or p75 is None or p75 <= p25:
        return None
    return (p75 - p25) / 2.0 * adj


@router.get("/day")
async def day(lat: float, lon: float):
    """The day at a point for the morning card."""
    if not _finite(lat, lon):
        raise HTTPException(422, "non-finite coordinate")
    from airfield import in_service_area, OUT_OF_AREA
    if not in_service_area(lat, lon):
        return {"lat": lat, "lon": lon, "hours": [], "error": OUT_OF_AREA}

    await _refresh_both()

    from forecast import FORECAST
    import districts
    F = deps.field()
    ist_now = datetime.now(_IST)
    today = ist_now.date()

    # the anchor σ is read once — one krige estimate per request, not per
    # hour; the forecast likewise re-samples its fetched arrays (no 12x
    # rebuilds — the whole card is one snapshot's worth of lookups)
    sigma0 = _hour_sigma0(F, lat, lon)
    live_now = None
    try:
        live_now = F.value(lat, lon, "pm2_5")
    except Exception:
        pass
    adj = 1.0
    try:
        import history
        typ0 = (history.typical_band(lat, lon, ist_now.month,
                                     ist_now.hour) or {}).get("median")
        if live_now and typ0:
            adj = live_now / typ0
    except Exception:
        pass

    hours = []
    try:
        from forecast import ANCHOR_TAU_H
    except Exception:
        ANCHOR_TAU_H = 9.0
    for h in range(_H_DAY):
        idx = None
        try:
            idx = FORECAST.hour_index(h)
        except Exception:
            break
        if idx is None:
            break
        t_iso = None
        try:
            t_iso = FORECAST.time_at(idx)
        except Exception:
            pass
        if t_iso is None:
            break
        dt_utc = datetime.fromisoformat(t_iso)
        if dt_utc.tzinfo is None:
            dt_utc = dt_utc.replace(tzinfo=timezone.utc)
        ist_dt = dt_utc.astimezone(_IST)
        # today only — the first slot crossing IST midnight is tomorrow's
        if ist_dt.date() > today:
            break
        try:
            v = FORECAST.pm25(lat, lon, h)
        except Exception:
            v = None
        if v is None:
            # the slot exists but the model has no value — a real hole,
            # not a zero (never fabricate the hour)
            continue
        w = math.exp(-h / ANCHOR_TAU_H)
        half_iqr = _clim_half_iqr(lat, lon, ist_dt.month, ist_dt.hour, adj)
        if sigma0 is not None and half_iqr is not None:
            band_half = w * sigma0 + (1.0 - w) * half_iqr
        elif sigma0 is not None:
            band_half = sigma0          # no climatology: krige σ stands
        elif half_iqr is not None:
            band_half = half_iqr        # no krige: measured spread stands
        else:
            band_half = None            # honest absence — lo/hi go null
        mid = round(v, 1)
        aqi = districts.us_aqi(mid)
        band_name, _color = districts.cpcb_band(districts.cpcb_aqi(mid))
        hours.append({
            "h": h,
            "start": t_iso,
            "ist_label": _ist_label(dt_utc),
            "pm25_mid": mid,
            "pm25_lo": round(max(0.0, mid - band_half), 1)
            if band_half is not None else None,
            "pm25_hi": round(mid + band_half, 1)
            if band_half is not None else None,
            "us_aqi": aqi,
            "band": band_name,
            "confidence": _conf(w, sigma0 is not None),
        })

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

    if not hours:
        # cold or dead forecast — the honest answer is no card, not a
        # card full of holes (/depart precedent: 'forecast unavailable')
        return {
            "lat": lat, "lon": lon, "date_ist": str(today), "tz": _TZ_NAME,
            "hours": [], "now_idx": None, "day_mean_pm25": None,
            "heavy_window": None, "cleanest_window": None,
            "decisions": [], "model": _MODEL,
            "band_basis": _BAND_BASIS,
            "field_age_s": fstat.get("age_s"),
            "field": fstat, "forecast": fcstat,
            "error": "forecast unavailable",
        }

    day_sum = summarize_day(hours)
    return {
        "lat": lat,
        "lon": lon,
        "date_ist": str(today),
        "tz": _TZ_NAME,
        "hours": hours,
        "now_idx": 0,                    # hours[0] is the slot holding now
        "day_mean_pm25": day_sum["day_mean"],
        "heavy_window": day_sum["heavy_window"],
        "cleanest_window": day_sum["cleanest_window"],
        "decisions": day_sum["decisions"],
        "model": _MODEL,
        "band_basis": _BAND_BASIS,
        "field_age_s": fstat.get("age_s"),
        "field": fstat,
        "forecast": fcstat,
    }


_BAND_BASIS = (
    "lo/hi = krige sigma at the point while the live anchor holds "
    "(exp(-h/9h) weight), blended toward the clock-hour's measured "
    "climatological interquartile spread (OpenAQ p25-p75) as the anchor "
    "decays; null when neither band exists")
