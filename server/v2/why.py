"""GET /v2/why — "why is the air like this right now?"

The one question the product never answered: a causal read, not a
number. Everything here is recomposed from ingredients the server
already owns — nothing is observed twice, nothing is invented:

  stubble_smoke  NASA FIRMS detections in the NW burn belt, ADMITTED
                 only when the wind actually carries the plume toward
                 Delhi — the same 270-360° FROM-quadrant gate
                 fires.smoke_modifier() applies (one rule across the
                 product), plus a minimum transport speed.
  stagnation     the field's own ventilation terms: VC = BLH × wind
                 (m²/s, the IITM/IMD dispersion proxy). Current slot
                 read from the warm forecast met grid; else the newest
                 built snapshot's met block — the build's own record.
  trend          the served field, recorded: stats.mean_pm25 across
                 the newest snapshots under data/field/snapshots
                 (ingest_worker writes one every 15 min). Rising /
                 falling vs the last hours — only when enough recorded
                 builds exist to compare.

A driver that can't be observed can't be claimed: each ingredient that
fails freshness or coverage lands in `cannot_tell`, and when nothing
clears the bar the honest answer is "local background — no single
driver stands out".

`history` (the driver sparkline) ships only when >=MIN_HISTORY_POINTS
recorded builds span >=3 h — the per-build belt_fires / vc_m2s /
mean_pm25 series IS each driver's recorded contribution.
"""
import asyncio
import concurrent.futures
import glob
import os
import statistics
import sys
import time
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter

_SERVER_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _SERVER_DIR not in sys.path:
    sys.path.insert(0, _SERVER_DIR)

from . import deps  # noqa: E402

router = APIRouter()

DELHI = (28.6139, 77.2090)          # lat, lon — default query point

# The reads+scoring tail of build_why is sync CPU + file/S3 enumeration
# (snapshot series, met block, multi-MB build deserializes). It used to
# run ON the event loop — a cold first call parked every concurrent
# request behind it. Run it on a private pool: off the loop, and off
# the shared default executor the boot-warm fleet squats (executor-
# audit lane). Two workers — /v2/why and the /v2/city why-block overlap.
_WHY_EXEC = concurrent.futures.ThreadPoolExecutor(
    max_workers=2, thread_name_prefix="alive-why")

# --- admission bars (documented constants, not magic) ----------------------
SMOKE_MIN_BELT = 10        # below this the belt isn't a headline claim
SMOKE_BASELINE = 160.0     # fires.BASELINE_FIRES_48H — keep in step
CARRY_FROM_MIN, CARRY_FROM_MAX = 270.0, 360.0   # fires.py's NW quadrant
CARRY_MIN_KMH = 4.0        # ~100-300 km belt->Delhi needs real advection

VC_REF_M2S = 3000.0        # forecast.BLH_REF x forecast.U_REF (1000x3)
STAG_FACTOR_MIN = 1.25     # vc < 2400 m²/s — IMD 'poor dispersion' regime

TREND_MIN_DELTA_UG = 12.0  # µg/m³ city-mean move that reads as a trend
TREND_WINDOW_S = 6 * 3600  # 'vs the last hours' = the trailing 6 h
TREND_MIN_SNAPS = 3        # ...with at least this many recorded builds
TREND_MIN_SPAN_S = 3600    # covering at least an hour of history
SNAP_MAX_AGE_S = 2.5 * 3600  # a build this old can't speak for 'now'

MIN_HISTORY_POINTS = 4     # sparkline ships only when it spans >= 3 h
HISTORY_MIN_SPAN_S = 3 * 3600

WIND_GONE_S = 3600.0       # a wind read older than this can't gate smoke

_REFRESH_BUDGET_S = 6.0    # never hold a 'why' answer hostage upstream

# The ingest worker stores 15-min builds S3-only (ingest_worker.store_blob:
# "15-min snapshots stay S3-only") so a healthy task's local snapshot dir
# is near-empty — the trend series must read the bucket too. Keys are
# field/YYYY/MM/DD/HHmm.json.gz in UTC. The series is rebuilt per call,
# so cache it briefly: builds land on a 15-min cadence anyway.
_SNAP_S3_MAX_KEYS = 40     # ~10 h at 15-min — dup-key pairs eat a few
_SNAP_S3_GET_BUDGET_S = 4.0
_SERIES_TTL_S = 300.0      # snaps land every ~15 min; 5-min cache is safe
_SERIES_CACHE: dict = {"at": 0.0, "key": None, "rows": []}

_CARRY_WORDS = ((337.5, "N"), (292.5, "NW"), (247.5, "W"), (202.5, "SW"),
                (157.5, "S"), (112.5, "SE"), (67.5, "E"), (22.5, "NE"))


def _compass(deg: Optional[float]) -> Optional[str]:
    if deg is None:
        return None
    d = deg % 360.0
    for top, name in _CARRY_WORDS:
        if d >= top:
            return name
    return "N"


def _snap_root() -> str:
    """Snapshot dir — ALIVE_SNAPSHOT_DIR wins, else the ingest worker's
    local mirror (same convention health._snapshot_root uses)."""
    env = os.environ.get("ALIVE_SNAPSHOT_DIR")
    if env:
        return env
    try:
        from ingest_worker import SNAPSHOT_DIR
        return SNAPSHOT_DIR
    except Exception:  # pragma: no cover - module always ships together
        return os.path.join(_SERVER_DIR, "data", "field", "snapshots")


# ------------------------------------------------------------- ingredients

async def _refresh_fires_bounded() -> None:
    """Wake the fires feed if it's cold — bounded, never raises."""
    try:
        from fires import FIRES
        # refresh() itself TTL-gates — call it every time, bounded
        await asyncio.wait_for(FIRES.refresh(deps.http()),
                               timeout=_REFRESH_BUDGET_S)
    except Exception:
        pass


def _fires_read() -> dict:
    """What the fires feed can honestly say right now.

    Live status when the feed is warm; the newest snapshot's provenance
    as a last-resort record (labelled, with its build age). FRP sums only
    real detection rows — never estimated."""
    try:
        from fires import FIRES
        st = FIRES.status() or {}
    except Exception:
        st = {}
    belt_frp = st.get("belt_frp_mw")
    if belt_frp is None:
        try:
            rows = [f for f in (FIRES._fires or []) if f.get("belt")]
            belt_frp = (round(sum(float(f.get("frp") or 0)
                                  for f in rows), 1) if rows else 0.0)
        except Exception:
            pass
    out = {
        "status": st.get("status"),
        "source": st.get("source") or "nasa-firms",
        "n_fires": st.get("fires"),
        "belt_fires": st.get("belt_fires"),
        "belt_frp_mw": belt_frp,
        "modifier": st.get("modifier"),
        "age_s": st.get("age_s"),
        "fetched_at": st.get("fetched_at"),
        "feed_wind_deg": st.get("wind_deg"),
    }
    if st.get("status") == "live" or st.get("fires"):
        return out
    # feed cold — the last BUILD's provenance still records what was seen
    prov = _newest_prov()
    fp = prov.get("fires") or {}
    if fp.get("n_fires") or fp.get("belt_fires"):
        return {
            "status": "recorded",
            "source": fp.get("source") or "snapshot-provenance",
            "n_fires": fp.get("n_fires"),
            "belt_fires": fp.get("belt_fires"),
            "belt_frp_mw": None,   # provenance records counts, not FRP
            "modifier": fp.get("modifier"),
            "age_s": prov.get("_age_s"),
            "fetched_at": fp.get("fetched_at"),
            "feed_wind_deg": None,
        }
    return out


def _wind_read() -> dict:
    """Freshest boundary wind. Live field wind first (15-min cadence);
    the fires feed's own fetch and the last build's met block as
    recorded fallbacks — each labelled with source + age."""
    out = {"speed_kmh": None, "from_deg": None, "age_s": None,
           "source": None, "known": False}
    try:
        F = deps.field()
        w = F.wind() if hasattr(F, "wind") else {}
        expired = (F._wind_expired() if hasattr(F, "_wind_expired")
                   else False)
        if w.get("speed_kmh") is not None and not expired:
            out.update(speed_kmh=w.get("speed_kmh"),
                       from_deg=w.get("from_deg"),
                       age_s=w.get("age_s"),  # newer fields stamp it
                       source="field", known=True)
            return out
    except Exception:
        pass
    try:
        from fires import FIRES
        if FIRES._wind_deg is not None and FIRES._fetched_at:
            out.update(from_deg=float(FIRES._wind_deg),
                       age_s=round(time.time() - FIRES._fetched_at),
                       source="fires-feed", known=True)
            return out
    except Exception:
        pass
    prov = _newest_prov()
    met = prov.get("met") or {}
    if met.get("wind_ms") is not None or met.get("wind_deg") is not None:
        out.update(speed_kmh=(round(met["wind_ms"] * 3.6, 1)
                             if met.get("wind_ms") is not None else None),
                   from_deg=met.get("wind_deg"),
                   age_s=prov.get("_age_s"),
                   source="snapshot-met", known=True)
    return out


def _newest_prov() -> dict:
    """Newest snapshot's provenance block + its build age — the field's
    own record of what fed it. {} when nothing readable exists."""
    try:
        import health as _h
        probe = _h._field_probe(time.time())
        doc = (probe.get("payload") or {})
        prov = dict(doc.get("provenance") or {})
        met = doc.get("met")
        if met and "met" not in prov:
            prov["met"] = met
        prov["_age_s"] = probe.get("age_s") or doc.get("_age_s")
        prov["_built_epoch"] = doc.get("built_epoch")
        return prov
    except Exception:
        return {}


def _row_from_build(f: dict) -> Optional[dict]:
    """One snapshot doc -> {t, pm25, vc_m2s, blh_m, belt_fires, modifier}
    or None when it carries no build time."""
    t = f.get("built_epoch")
    if not isinstance(t, (int, float)):
        try:
            t = datetime.fromisoformat(
                str(f.get("built_at")).replace("Z", "+00:00")
            ).timestamp()
        except Exception:
            return None
    prov = f.get("provenance") or {}
    met = f.get("met") or (prov.get("met") or {})
    fr = prov.get("fires") or {}
    stats = f.get("stats") or {}
    pm = stats.get("mean_pm25")
    if pm is None:
        cells = f.get("cells") or {}
        vals = [c.get("pm25") for c in cells.values()
                if isinstance(c, dict) and isinstance(
                    c.get("pm25"), (int, float))]
        pm = statistics.fmean(vals) if vals else None
    return {"t": float(t),
            "pm25": round(float(pm), 1) if pm is not None else None,
            "vc_m2s": met.get("vc_m2s"),
            "blh_m": met.get("blh_m"),
            "belt_fires": fr.get("belt_fires"),
            "modifier": fr.get("modifier")}


def _local_series(window_s: float) -> list:
    """Newest->oldest recorded builds on this task's disk — the dev
    path; production writes are S3-only so this is usually thin."""
    root = _snap_root()
    try:
        paths = sorted(
            glob.glob(os.path.join(root, "**", "*.json.gz"),
                      recursive=True),
            key=lambda p: (os.path.getmtime(p), p), reverse=True)
    except Exception:
        return []
    import airindex
    now = time.time()
    rows = []
    for p in paths[:40]:
        try:
            with open(p, "rb") as fh:
                row = _row_from_build(airindex.deserialize(fh.read()))
        except Exception:
            continue
        if row is None:
            continue
        if now - row["t"] > window_s:
            break  # sorted newest-first: past the window, stop
        rows.append(row)
    rows.reverse()  # oldest -> newest
    return rows


def _s3_series(window_s: float) -> list:
    """Newest->oldest recorded builds out of the bucket — the
    production path. Lists at most two UTC day-prefixes, fetches only
    as many keys as the window needs, bounded and fully optional: any
    failure yields the local view."""
    bucket = os.environ.get("ALIVE_AIR_BUCKET")
    if not bucket:
        return []
    try:
        import boto3
        s3 = boto3.client("s3")
    except Exception:
        return []
    now = time.time()
    days = sorted({datetime.fromtimestamp(now, tz=timezone.utc),
                   datetime.fromtimestamp(now - window_s,
                                          tz=timezone.utc)},
                  reverse=True)
    keys: list = []
    try:
        for d in days:
            pref = f"field/{d:%Y/%m/%d}/"
            r = s3.list_objects_v2(Bucket=bucket, Prefix=pref)
            for o in r.get("Contents", []):
                keys.append((o["LastModified"].timestamp(), o["Key"]))
    except Exception:
        return []
    keys.sort(reverse=True)
    import airindex
    deadline = now + _SNAP_S3_GET_BUDGET_S

    def _fetch(key):
        try:
            body = s3.get_object(Bucket=bucket, Key=key)["Body"].read()
            return _row_from_build(airindex.deserialize(body))
        except Exception:
            return None

    # Serial get+deserialize of ~14k-cell builds costs ~0.3 s each and the
    # 4 s budget starved the series at ~15 rows — newest only, hiding the
    # older half of the window. Bounded parallel fetch keeps the budget.
    from concurrent.futures import ThreadPoolExecutor
    rows = []
    seen_t: set = set()
    want = [k for _, k in keys[:_SNAP_S3_MAX_KEYS]]
    with ThreadPoolExecutor(max_workers=8) as ex:
        for row in ex.map(_fetch, want):
            if time.time() > deadline:
                break
            if row is None or row["t"] in seen_t:
                continue  # the same build can persist under two keys
            if now - row["t"] > window_s:
                continue
            seen_t.add(row["t"])
            rows.append(row)
    rows.sort(key=lambda r: r["t"])  # oldest -> newest
    return rows


def _snapshot_series(window_s: float = TREND_WINDOW_S) -> list:
    """Recorded builds inside `window_s` — local disk first (dev), the
    bucket when local is thin (production), merged and deduped by build
    time, cached for _SERIES_TTL_S."""
    key = _snap_root()  # tests swap the root — cache is per-root
    if _SERIES_CACHE["key"] == key and _SERIES_CACHE["at"] and \
            time.time() - _SERIES_CACHE["at"] < _SERIES_TTL_S:
        return _SERIES_CACHE["rows"]
    rows = _local_series(window_s)
    if len(rows) < TREND_MIN_SNAPS:
        seen = {r["t"] for r in rows}
        rows += [r for r in _s3_series(window_s) if r["t"] not in seen]
        rows.sort(key=lambda r: r["t"])
    _SERIES_CACHE.update({"at": time.time(), "key": key, "rows": rows})
    return rows


def _ventilation_read(lat: float, lon: float) -> dict:
    """VC for the current hour at the query point.

    Order: the warm forecast met grid (fresh model analysis for THIS
    slot at THIS point), else the newest build's recorded met block —
    the field's own ventilation terms, labelled with its age."""
    out = {"vc_m2s": None, "blh_m": None, "wind_ms": None,
           "factor": None, "source": None, "age_s": None}
    try:
        from forecast import FORECAST
        idx0 = FORECAST.hour_index(0)
        det = (FORECAST.stagnation_detail(lat, lon, idx0)
               if idx0 is not None else None)
        if det and not det.get("estimated") and det.get("blh_m") is not None:
            vc = det["blh_m"] * max(det.get("wind_ms") or 0.0, 0.5)
            out.update(vc_m2s=round(vc, 1), blh_m=det["blh_m"],
                       wind_ms=det["wind_ms"], factor=det["factor"],
                       source="forecast",
                       age_s=(round(time.time() - FORECAST._fetched_at)
                              if FORECAST._fetched_at else None))
            return out
    except Exception:
        pass
    prov = _newest_prov()
    met = prov.get("met") or {}
    vc = met.get("vc_m2s")
    if vc is None and met.get("blh_m") is not None \
            and met.get("wind_ms") is not None:
        vc = met["blh_m"] * max(met["wind_ms"], 0.5)
    if vc is not None:
        out.update(vc_m2s=round(float(vc), 1), blh_m=met.get("blh_m"),
                   wind_ms=met.get("wind_ms"),
                   factor=round(VC_REF_M2S / float(vc), 2),
                   source="snapshot-met", age_s=prov.get("_age_s"))
    return out


# ------------------------------------------------------------- attribution

def _carries_toward_delhi(from_deg: Optional[float],
                        speed_kmh: Optional[float]) -> Optional[bool]:
    """The smoke gate: fires only count when the wind can actually carry
    the NW belt's plume to Delhi. None when the wind isn't known — a
    gate that can't be checked can't admit."""
    if from_deg is None:
        return None
    if speed_kmh is not None and speed_kmh < CARRY_MIN_KMH:
        return False
    deg = from_deg % 360.0 or 360.0   # 0 == 360 == due north
    return CARRY_FROM_MIN <= deg <= CARRY_FROM_MAX


def _eval_fires(fires: dict, wind: dict) -> tuple:
    """-> (driver|None, evaluated-block, cannot_tell|None)."""
    ev = {"seen": bool(fires.get("n_fires") or fires.get("belt_fires")),
          "belt_fires": fires.get("belt_fires"),
          "belt_frp_mw": fires.get("belt_frp_mw"),
          "n_fires": fires.get("n_fires"),
          "modifier": fires.get("modifier"),
          "feed": fires.get("source"), "feed_status": fires.get("status"),
          "feed_age_s": fires.get("age_s"),
          "carrying": _carries_toward_delhi(wind.get("from_deg"),
                                          wind.get("speed_kmh"))}
    belt = fires.get("belt_fires") or 0
    if not ev["seen"]:
        return None, ev, {"kind": "stubble_smoke",
                          "reason": "fires feed cold — can't read the "
                                    "burn belt right now"}
    if ev["carrying"] is None:
        return None, ev, {"kind": "stubble_smoke",
                          "reason": f"{belt} belt fires burning but wind "
                                    "unknown — can't tell if the smoke "
                                    "is coming here"}
    if belt < SMOKE_MIN_BELT:
        return None, ev, None   # too thin to claim — background
    if not ev["carrying"]:
        return None, ev, None   # burning, but not coming this way
    score = min(1.0, belt / SMOKE_BASELINE)
    kmh = wind.get("speed_kmh")
    wind_bit = (f"wind {kmh:g} km/h from the {_compass(wind.get('from_deg'))}"
                if kmh is not None else
                f"wind from the {_compass(wind.get('from_deg'))}")
    frp_bit = (f" · belt FRP {fires['belt_frp_mw']:g} MW"
               if fires.get("belt_frp_mw") is not None else "")
    mod_bit = (f" · model smoke uplift ×{fires['modifier']:g}"
               if fires.get("modifier") not in (None, 1.0) else "")
    rec = " (recorded build)" if fires.get("status") == "recorded" else ""
    driver = {
        "kind": "stubble_smoke", "score": round(score, 3),
        "evidence": (f"{belt} fires in the NW burn belt{rec} · "
                     f"{wind_bit} — carrying toward Delhi"
                     f"{frp_bit}{mod_bit}"),
        "detail": {"belt_fires": belt, "n_fires": fires.get("n_fires"),
                   "belt_frp_mw": fires.get("belt_frp_mw"),
                   "modifier": fires.get("modifier"),
                   "wind_from_deg": wind.get("from_deg"),
                   "wind_kmh": kmh, "feed_age_s": fires.get("age_s")},
    }
    return driver, ev, None


def _eval_stagnation(vent: dict) -> tuple:
    vc = vent.get("vc_m2s")
    ev = {"vc_m2s": vc, "blh_m": vent.get("blh_m"),
          "wind_ms": vent.get("wind_ms"), "factor": vent.get("factor"),
          "source": vent.get("source"), "age_s": vent.get("age_s"),
          "vc_ref_m2s": VC_REF_M2S}
    if vc is None:
        return None, ev, {"kind": "stagnation",
                          "reason": "no ventilation read — forecast met "
                                    "and snapshot met both empty"}
    factor = VC_REF_M2S / max(vc, 1.0)
    ev["factor"] = round(factor, 2)
    if factor < STAG_FACTOR_MIN:
        return None, ev, None   # mixing fine — not a driver
    score = min(1.0, (factor - 1.0) / 1.2)
    blh = vent.get("blh_m")
    u = vent.get("wind_ms")
    bits = []
    if blh is not None:
        bits.append(f"boundary layer {blh:g} m")
    if u is not None:
        bits.append(f"wind {u:g} m/s")
    src = " · recorded build" if vent.get("source") == "snapshot-met" else ""
    driver = {
        "kind": "stagnation", "score": round(score, 3),
        "evidence": (f"{' + '.join(bits)} → ventilation "
                     f"{round(vc):,} m²/s vs ~{int(VC_REF_M2S):,} typical"
                     f"{src} — the air is barely mixing"),
        "detail": dict(ev),
    }
    return driver, ev, None


def _eval_trend(series: list) -> tuple:
    """Served field, recorded: split the 6 h window in half and compare
    city means. Admitted only with enough builds over enough span, and a
    newest build fresh enough to speak for 'now'."""
    snaps = [s for s in series if s.get("pm25") is not None]
    now = time.time()
    ev = {"n_snapshots": len(snaps), "window_h": TREND_WINDOW_S / 3600.0,
          "newest_age_s": (round(now - snaps[-1]["t"]) if snaps else None),
          "delta_ug": None}
    if len(snaps) < TREND_MIN_SNAPS:
        return None, ev, {"kind": "trend",
                          "reason": f"only {len(snaps)} recorded build(s) "
                                    "in 6 h — can't compare hours"}
    if now - snaps[-1]["t"] > SNAP_MAX_AGE_S:
        return None, ev, {"kind": "trend",
                          "reason": "newest recorded build is "
                          f"{round((now - snaps[-1]['t']) / 3600, 1)} h "
                          "old — can't speak for right now"}
    if snaps[-1]["t"] - snaps[0]["t"] < TREND_MIN_SPAN_S:
        return None, ev, {"kind": "trend",
                          "reason": "recorded builds span under an hour "
                                    "— no honest trend yet"}
    mid = snaps[0]["t"] + (snaps[-1]["t"] - snaps[0]["t"]) / 2.0
    older = [s["pm25"] for s in snaps if s["t"] <= mid]
    newer = [s["pm25"] for s in snaps if s["t"] > mid]
    if not older or not newer:
        return None, ev, {"kind": "trend",
                          "reason": "recorded builds all bunch in one "
                                    "half of the window"}
    d_new = statistics.fmean(newer)
    d_old = statistics.fmean(older)
    delta = d_new - d_old
    span_h = (snaps[-1]["t"] - snaps[0]["t"]) / 3600.0
    ev.update({"delta_ug": round(delta, 1), "span_h": round(span_h, 1),
               "from_pm25": round(d_old, 1), "to_pm25": round(d_new, 1)})
    if abs(delta) < TREND_MIN_DELTA_UG:
        return None, ev, None   # flat — no honest trend claim
    direction = "rising" if delta > 0 else "falling"
    score = min(1.0, abs(delta) / 40.0)
    driver = {
        "kind": "trend", "score": round(score, 3),
        "direction": direction,
        "evidence": (f"city field mean {d_old:g} → {d_new:g} µg/m³ over "
                     f"{span_h:.1f} h ({len(snaps)} recorded builds)"),
        "detail": dict(ev),
    }
    return driver, ev, None


# ---------------------------------------------------------------- compose

_LINE_BITS = {
    "stubble_smoke": "stubble smoke drifting in on the {dir} wind",
    "stagnation": "the air is barely moving — the day's pollution is "
                  "sitting over the city",
    "trend_rising": "levels still climbing",
    "trend_falling": "easing off the earlier high",
}


def _line(drivers: list, wind: dict) -> str:
    """One spoken line — plain Delhiite English, never a fake cause."""
    if not drivers:
        return "local background — no single driver stands out"
    parts = []
    for d in drivers[:2]:
        key = (d["kind"] if d["kind"] != "trend"
               else f"trend_{d.get('direction', 'rising')}")
        bit = _LINE_BITS.get(key, d["kind"])
        if "{dir}" in bit:
            compass = _compass(wind.get("from_deg")) or "north-west"
            # 'from the NW wind' reads better expanded on first use
            bit = bit.format(dir={
                "NW": "north-west", "N": "northerly", "W": "westerly",
                "NE": "north-east", "SW": "south-west", "S": "southerly",
                "SE": "south-east", "E": "easterly"}.get(compass, "NW"))
        parts.append(bit)
    return " + ".join(parts)


def _history(series: list) -> Optional[dict]:
    """The bonus sparkline — each driver's recorded contribution per
    build. Ships only when the record genuinely covers ~3+ hours."""
    if len(series) < MIN_HISTORY_POINTS:
        return None
    if series[-1]["t"] - series[0]["t"] < HISTORY_MIN_SPAN_S:
        return None
    return {
        "window_h": round((series[-1]["t"] - series[0]["t"]) / 3600.0, 2),
        "points": [{
            "t": s["t"],
            "pm25": s.get("pm25"),
            "vc_m2s": s.get("vc_m2s"),
            "belt_fires": s.get("belt_fires"),
            "modifier": s.get("modifier"),
        } for s in series],
        "note": ("one row per recorded field build — the contribution "
                 "each driver carried at build time"),
    }


async def build_why(lat: float, lon: float) -> dict:
    """The full 'why' read — shared by /v2/why and the /v2/city block."""
    from .plan import _field_refresh_bounded
    await _field_refresh_bounded()   # best-effort, budgeted (city pattern)
    await _refresh_fires_bounded()

    def _sync_tail():
        wind = _wind_read()
        fires = _fires_read()
        vent = _ventilation_read(lat, lon)
        series = _snapshot_series()

        evaluated, cannot_tell, drivers = {}, [], []
        for key, fn, arg in (("fires", _eval_fires, (fires, wind)),
                             ("ventilation", _eval_stagnation, (vent,)),
                             ("trend", _eval_trend, (series,))):
            d, ev, ct = fn(*arg)
            evaluated[key] = ev
            if d:
                drivers.append(d)
            if ct:
                cannot_tell.append(ct)

        drivers.sort(key=lambda d: -d["score"])
        for i, d in enumerate(drivers):
            d["weight"] = "primary" if i == 0 else "secondary"

        now = time.time()
        return {
            "generated_at": datetime.fromtimestamp(
                now, tz=timezone.utc).isoformat(timespec="seconds"),
            "lat": lat, "lon": lon,
            "scope": "city — fires/stagnation/trend are city-scale "
                     "drivers; lat/lon localizes the ventilation read",
            "line": _line(drivers, wind),
            "drivers": drivers,
            "evaluated": evaluated,
            "cannot_tell": cannot_tell,
            "wind": wind,
            "history": _history(series),
            "honesty": ("a driver that can't be observed isn't claimed — "
                        "checked-but-failed ingredients are under "
                        "cannot_tell; 'local background' is the honest "
                        "empty answer, not an error"),
        }

    # sync reads + scoring off the event loop AND off the shared default
    # executor (see _WHY_EXEC): a cold first call used to park the loop
    # behind S3 enumeration + multi-MB build deserializes
    return await asyncio.get_running_loop().run_in_executor(
        _WHY_EXEC, _sync_tail)


@router.get("/why")
async def why(lat: Optional[float] = None, lon: Optional[float] = None):
    """Why is the air like this right now — one honest causal read.

    Machine-graded `drivers` (kind/weight/score/evidence) + a spoken
    `line`. lat/lon default to the city centre; drivers are city-scale
    (the burn belt feeds Delhi, not a lane), the point localizes the
    ventilation read."""
    la = lat if lat is not None else DELHI[0]
    lo = lon if lon is not None else DELHI[1]
    return await build_why(float(la), float(lo))
