"""Community air layer — commuters as the sensor network.

Two honest contributions, no fake sensing:

1. Trip observations: anonymized traversals (mode + polyline + timing)
   the app donates after a journey. Aggregated they answer what no
   station can — where, when and how Delhi actually breathes: per-
   corridor counts, modal split, cumulative inhaled mass, and the µg
   avoided by dose-aware choices. Delhi's grid is ~65% unmonitored;
   phones can't measure PM2.5, but traversal density IS real data.

2. Hazard reports: user flags (dust, smoke, burning smell, visibly
   clean air) with a 6h TTL — the Waze model applied to air. Stored
   in-memory, snapshotted to data/community.json for restart survival.

Privacy: observations carry no identity. A shared anonymous id lets a
device be counted once for 'contributors' without tracking who it is.
"""
import json
import math
import os
import time
from pathlib import Path
from typing import Optional

_FILE = Path(__file__).parent / "data" / "community.json"
_REPORT_TTL_S = 6 * 3600
_REPORT_KINDS = {"dust", "smoke", "burning", "clean"}

# S3 persistence — Fargate has an ephemeral FS, so the community layer
# would reset on every deploy. When COMMUNITY_BUCKET is set the snapshot
# is pushed at most every _S3_MIN_GAP_S and pulled back on boot.
_BUCKET = os.environ.get("COMMUNITY_BUCKET", "")
_S3_KEY = "community/state.json"
_S3_MIN_GAP_S = 60
_s3_client = None
_last_s3_put = 0.0

_obs: list[dict] = []
_reports: list[dict] = []
_loaded = False


def _s3():
    global _s3_client
    if _s3_client is None and _BUCKET:
        try:
            import boto3
            _s3_client = boto3.client("s3", region_name=os.environ.get("AWS_REGION", "ap-south-1"))
        except Exception:
            _s3_client = False
    return _s3_client or None


def _apply(d: dict) -> None:
    global _obs, _reports
    _obs = d.get("obs", [])[-20000:]
    _reports = d.get("reports", [])[-2000:]


def _load() -> None:
    global _loaded
    if _loaded:
        return
    _loaded = True
    s3 = _s3()
    if s3:
        try:
            body = s3.get_object(Bucket=_BUCKET, Key=_S3_KEY)["Body"].read()
            _apply(json.loads(body))
            _prune_reports()
            return
        except Exception:
            pass
    if _FILE.exists():
        try:
            _apply(json.loads(_FILE.read_text()))
        except Exception:
            pass
    _prune_reports()


def _save() -> None:
    global _last_s3_put
    payload = {"obs": _obs[-20000:], "reports": _reports[-2000:]}
    try:
        _FILE.parent.mkdir(parents=True, exist_ok=True)
        _FILE.write_text(json.dumps(payload))
    except Exception:
        pass
    now = time.time()
    s3 = _s3()
    if s3 and now - _last_s3_put > _S3_MIN_GAP_S:
        _last_s3_put = now
        try:
            s3.put_object(Bucket=_BUCKET, Key=_S3_KEY,
                          Body=json.dumps(payload), ContentType="application/json")
        except Exception:
            pass


def _prune_reports() -> None:
    cutoff = time.time() - _REPORT_TTL_S
    _reports[:] = [r for r in _reports if r.get("ts", 0) > cutoff]


def observe(vehicle: str, coords: list, duration_s: float,
            dose_ug: Optional[float], avoided_ug: Optional[float],
            contributor: Optional[str]) -> dict:
    """Store an anonymized traversal. coords: [[lon, lat], ...] sampled."""
    _load()
    obs = {
        "ts": time.time(),
        "vehicle": vehicle,
        "duration_s": round(float(duration_s), 1),
        "dose_ug": None if dose_ug is None else round(float(dose_ug), 1),
        "avoided_ug": None if avoided_ug is None else round(float(avoided_ug), 1),
        "contributor": (contributor or "")[:16],
        "points": [[round(float(c[0]), 5), round(float(c[1]), 5)]
                   for c in coords[:400] if len(c) >= 2],
    }
    _obs.append(obs)
    _save()
    return {"stored": True, "total_obs": len(_obs)}


def report(kind: str, lat: float, lon: float, contributor: Optional[str]) -> dict:
    if kind not in _REPORT_KINDS:
        return {"stored": False, "error": f"kind must be one of {sorted(_REPORT_KINDS)}"}
    _load()
    r = {"ts": time.time(), "kind": kind,
         "lat": round(float(lat), 5), "lon": round(float(lon), 5)}
    _reports.append(r)
    _save()
    return {"stored": True, "active_reports": len(_reports)}


def reports_geojson() -> dict:
    _load()
    _prune_reports()
    feats = [{
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [r["lon"], r["lat"]]},
        "properties": {"kind": r["kind"], "age_min": round((time.time() - r["ts"]) / 60)},
    } for r in _reports]
    return {"type": "FeatureCollection", "features": feats}


def contributors_detail() -> list[dict]:
    """Per-contributor rollup for the admin dashboard — anon ids only."""
    _load()
    by: dict = {}
    for o in _obs:
        c = by.setdefault(o["contributor"] or "anon", {
            "trips": 0, "dose_ug": 0.0, "avoided_ug": 0.0,
            "km": 0.0, "last_ts": 0, "modes": set(),
        })
        c["trips"] += 1
        c["dose_ug"] += o["dose_ug"] or 0
        c["avoided_ug"] += o["avoided_ug"] or 0
        c["last_ts"] = max(c["last_ts"], o["ts"])
        c["modes"].add(o["vehicle"])
        pts = o["points"]
        for a, b in zip(pts, pts[1:]):
            c["km"] += 6371 * 2 * math.asin(min(1, math.sqrt(
                math.sin(math.radians(b[1] - a[1]) / 2) ** 2 +
                math.cos(math.radians(a[1])) * math.cos(math.radians(b[1])) *
                math.sin(math.radians(b[0] - a[0]) / 2) ** 2)))
    out = [{
        "contributor": k,
        "trips": v["trips"], "km": round(v["km"], 1),
        "dose_ug": round(v["dose_ug"], 1), "avoided_ug": round(v["avoided_ug"], 1),
        "last_seen_min_ago": round((time.time() - v["last_ts"]) / 60),
        "modes": sorted(v["modes"]),
    } for k, v in by.items()]
    out.sort(key=lambda x: x["last_seen_min_ago"])
    return out


def recent_obs(limit: int = 20) -> list[dict]:
    _load()
    return [{
        "ts": o["ts"], "age_min": round((time.time() - o["ts"]) / 60, 1),
        "vehicle": o["vehicle"], "duration_s": o["duration_s"],
        "dose_ug": o["dose_ug"], "avoided_ug": o["avoided_ug"],
        "contributor": o["contributor"],
    } for o in _obs[-limit:]][::-1]


def live_reports() -> list[dict]:
    _load()
    _prune_reports()
    return [{
        "kind": r["kind"], "lat": r["lat"], "lon": r["lon"],
        "age_min": round((time.time() - r["ts"]) / 60),
        "contributor": r.get("contributor"),
    } for r in _reports]


def journeys_per_hour(hours: int = 24) -> list[int]:
    """Observations bucketed per hour, oldest→newest — the ops sparkline."""
    _load()
    now = time.time()
    out = [0] * hours
    for o in _obs:
        i = hours - 1 - int((now - o["ts"]) // 3600)
        if 0 <= i < hours:
            out[i] += 1
    return out


def _cell(lon: float, lat: float) -> tuple[float, float]:
    """~500m snap — groups traversals into corridors."""
    return (round(lon / 0.005) * 0.005, round(lat / 0.005) * 0.005)


# mode microenv + ventilation lookups for backing ambient concentration
# out of an inhaled dose — the environmental evidence a traversal carries
from exposure import MICROENV, VENTILATION_LPM  # noqa: E402

_OBS_FRESH_S = 72 * 3600  # traversals older than 3 days stop informing


def corridor_field_samples() -> list:
    """Traversal-implied ambient PM2.5 per corridor cell — the citizen
    sensor network's real output.

    Every observation carries dose(µg) = ∫ C·microenv·ve dt along its
    path. Inverting it gives the ambient concentration the traveler
    effectively breathed through, mode-corrected:
        C_implied = dose_ug / (ve_lpm/1000 · duration_min · microenv)
    Median per ~500m cell needs ≥3 fresh traversals — one journey is an
    anecdote, a corridor of commutes is a measurement. Returned in the
    (lat, lon, name, vals) sample shape AirField consumes; unnamed so
    they weigh like model points (1×), never like stations (3×)."""
    _load()
    now = time.time()
    cells: dict = {}
    for o in _obs:
        if now - o["ts"] > _OBS_FRESH_S or not o.get("dose_ug") or not o.get("duration_s"):
            continue
        ve = VENTILATION_LPM.get(o["vehicle"], 8.0) / 1000.0
        me = MICROENV.get(o["vehicle"], 1.0)
        dur_min = o["duration_s"] / 60.0
        if dur_min < 0.5:
            continue
        c = o["dose_ug"] / (ve * dur_min * me)
        if not (10 <= c <= 900):
            continue
        for lon, lat in o["points"]:
            cell = _cell(lon, lat)
            cells.setdefault(cell, []).append(c)
    out = []
    for (lon, lat), vals in cells.items():
        if len(vals) < 3:
            continue
        vals.sort()
        med = vals[len(vals) // 2]
        out.append((lat, lon, None, {"pm2_5": round(med, 1)}))
    return out


def corridor_estimate(lat: float, lon: float):
    """Traversal-implied ambient pm25 at a point: (µg, std-dev, n_obs).

    IDW (p=2) over corridor cells within ~3km; the spread across cells
    plus the shallow-sample noise sets the std-dev. None when the
    citizen layer has no coverage there — no invented confidence."""
    cells = corridor_field_samples()
    if not cells:
        return None
    num = den = var_sum = n = 0.0
    for slat, slon, _n, vals in cells:
        c = (vals or {}).get("pm2_5")
        if c is None:
            continue
        d = math.hypot(slat - lat, slon - lon)
        if d > 0.03:  # ~3km coherence — citizen data is local
            continue
        w = 1.0 / max(d * d, 1e-8)
        num += w * c
        den += w
        var_sum += w * c * c
        n += 1
    if not den or n == 0:
        return None
    mu = num / den
    var = max(0.0, var_sum / den - mu * mu)
    # instrument noise of a traversal-implied read ~40µg + spatial spread
    sd = math.sqrt(var + 1600.0 / max(n, 1))
    return mu, sd, n


def corridors(limit: int = 10) -> list[dict]:
    """Where Delhi actually travels, ranked — donated traversal density
    per ~500m cell with average inhaled dose. This is street-level
    movement data no station grid or routing API can produce."""
    _load()
    cells: dict = {}
    for o in _obs:
        for lon, lat in o["points"]:
            c = _cell(lon, lat)
            v = cells.setdefault(c, {"count": 0, "dose_sum": 0.0, "modes": {}})
            v["count"] += 1
            v["dose_sum"] += o["dose_ug"] or 0
            v["modes"][o["vehicle"]] = v["modes"].get(o["vehicle"], 0) + 1
    out = []
    for (lon, lat), v in cells.items():
        out.append({
            "lon": lon, "lat": lat, "samples": v["count"],
            "avg_dose_ug": round(v["dose_sum"] / max(v["count"], 1), 1),
            "top_mode": max(v["modes"], key=v["modes"].get) if v["modes"] else None,
        })
    out.sort(key=lambda x: -x["samples"])
    return out[:limit]


def totals() -> dict:
    """City rollup — the collective ledger judges can read at a glance."""
    _load()
    day = time.time() - 86400
    recent = [o for o in _obs if o["ts"] > day]
    def _km(o):
        pts = o["points"]
        d = 0.0
        for a, b in zip(pts, pts[1:]):
            d += 6371 * 2 * math.asin(min(1, math.sqrt(
                math.sin(math.radians(b[1] - a[1]) / 2) ** 2 +
                math.cos(math.radians(a[1])) * math.cos(math.radians(b[1])) *
                math.sin(math.radians(b[0] - a[0]) / 2) ** 2)))
        return d
    contrib = {o["contributor"] for o in _obs if o["contributor"]}
    return {
        "obs_total": len(_obs),
        "obs_24h": len(recent),
        "contributors": len(contrib),
        "km_24h": round(sum(_km(o) for o in recent), 1),
        "dose_ug_24h": round(sum(o["dose_ug"] or 0 for o in recent), 1),
        "avoided_ug_24h": round(sum(o["avoided_ug"] or 0 for o in recent), 1),
        "avoided_ug_all": round(sum(o["avoided_ug"] or 0 for o in _obs), 1),
        "active_reports": len(_reports),
        "modes_24h": {v: sum(1 for o in recent if o["vehicle"] == v)
                      for v in {o["vehicle"] for o in recent}},
        "latest_obs_age_min": round((time.time() - max((o["ts"] for o in _obs), default=0)) / 60) if _obs else None,
        "top_corridors": corridors(5),
    }
