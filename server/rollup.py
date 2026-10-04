"""Daily rollup + weekly leave-one-station-out validation (doc 05 §2).

daily_rollup("YYYY-MM-DD"):
  reads the day's snapshots (s3://{ALIVE_AIR_BUCKET}/field/YYYY/MM/DD/*.json.gz
  when configured, else the local mirror under
  server/data/field/snapshots/) and writes
      daily/YYYY-MM-DD.json            (S3)  or  data/field/daily/YYYY-MM-DD.json
  as schema "alive-rollup/2": per-cell mean/min/max, intra-day percentile
  band (p10/p50/p90 of the day's pm25 readings), mean model band
  (lo_mean/hi_mean) and worst hours; plus the city summary — median,
  % cells above the WHO 24 h guideline (15 µg/m³) and the CPCB 24 h NAAQS
  (60 µg/m³), weighted city stats, and the ventilation-coefficient
  (BLH x wind) series sampled from each snapshot's met block.
  Corrupt/unreadable snapshots are skipped and COUNTED under inputs.skipped
  — a bad file never silently vanishes and never poisons the day.

weekly_validation("YYYY-Www"):
  leave-one-station-out on the newest usable snapshot inside the ISO week
  (falling back to the latest snapshot anywhere, flagged
  snapshot_in_iso_week=false). Each fold rebuilds the residual field from
  the OTHER stations with the same krige.KrigeField + IDW fallback and the
  same sigma math airindex.build_field applies to a grid cell, then scores
  the held-out observation: MAE/RMSE/bias of held-out predictions PLUS
  coverage of the rebuilt lo..hi band. Unusable stations/snapshots are
  skipped and counted, never fabricated. Writes
      validation/weekly-{week}.json  + validation/weekly-{week}.md
      (compat copy: validation/{week}.json)
  plus the archive replay from validate_field.validate() (network + cache
  required; reported as 'unavailable' with the reason when it can't run —
  SystemExit from its sys.exit included).

Full field/unit/provenance contract: docs/plan/rollup-schema.md.
Schedulable as plain functions or via `python rollup.py daily|weekly`.
"""
import glob
import gzip
import json
import math
import os
import sys
from datetime import date as _date
from datetime import datetime, timedelta, timezone

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import airindex            # noqa: E402
from ingest_worker import store_blob, SNAPSHOT_DIR, DATA_DIR, _boto3  # noqa: E402
from krige import KrigeField  # noqa: E402

try:
    import numpy as np
except ImportError:
    np = None

DAILY_DIR = os.path.join(DATA_DIR, "field", "daily")
VALID_DIR = os.path.join(DATA_DIR, "field", "validation")
IST = timezone(timedelta(hours=5, minutes=30))

WHO_24H = 15.0    # µg/m³ WHO 24-h PM2.5 guideline (doc 05)
CPCB_24H = 60.0   # µg/m³ CPCB/NAAQS 24-h PM2.5 standard (doc 05)

MIN_STATIONS_LOSO = 4   # a fold needs the held-out station + >=3 others


# ------------------------------------------------------------ snapshot IO

def _iter_local_blobs(date: str, snapshot_root: str = None):
    """Yield (label, gzip-bytes) for every readable local snapshot of `date`."""
    dt = datetime.strptime(date, "%Y-%m-%d")
    root = snapshot_root or SNAPSHOT_DIR
    pat = os.path.join(root, f"{dt:%Y}", f"{dt:%m}", f"{dt:%d}", "*.json.gz")
    for p in sorted(glob.glob(pat)):
        try:
            with open(p, "rb") as f:
                yield p, f.read()
        except OSError:
            continue


def _iter_s3_blobs(date: str, desc: bool = False):
    """Yield (s3:// label, gzip-bytes) for the day's S3 prefix; empty when
    ALIVE_AIR_BUCKET/boto3/credentials are not usable. `desc` lists the
    day's keys first, then fetches newest-first — a newest-usable scan
    costs ~1 object instead of the whole day."""
    dt = datetime.strptime(date, "%Y-%m-%d")
    bucket = os.environ.get("ALIVE_AIR_BUCKET")
    b3 = _boto3() if bucket else None
    if b3 is None:
        return
    try:
        s3 = b3.client("s3")
        prefix = f"field/{dt:%Y/%m/%d}/"
        keys = []
        for page in s3.get_paginator("list_objects_v2").paginate(
                Bucket=bucket, Prefix=prefix):
            keys.extend(obj["Key"] for obj in page.get("Contents", []))
        if desc:
            keys = keys[::-1]
        for key in keys:
            try:
                body = s3.get_object(Bucket=bucket,
                                     Key=key)["Body"].read()
                yield f"s3://{bucket}/{key}", body
            except Exception:  # noqa: BLE001
                continue
    except Exception:  # noqa: BLE001 - S3 listing is best-effort
        return


def _iter_snapshot_blobs(date: str, snapshot_root: str = None):
    """Yield (label, gzip-bytes) for every snapshot of `date`.

    Local mirror first; when ALIVE_AIR_BUCKET + boto3 are usable, also
    list the S3 prefix (labels tell which source each blob came from)."""
    yield from _iter_local_blobs(date, snapshot_root)
    yield from _iter_s3_blobs(date)


def _load_fields_verbose(date: str, snapshot_root: str = None):
    """-> (fields, skipped): every blob that can't be read/deserialized is
    counted with its label + reason — skipped honestly, never dropped
    silently and never fabricated."""
    fields, skipped = [], []
    blobs = list(_iter_snapshot_blobs(date, snapshot_root))
    # re-glob unreadable local files: _iter_local_blobs hides OSErrors
    dt = datetime.strptime(date, "%Y-%m-%d")
    root = snapshot_root or SNAPSHOT_DIR
    seen = {lbl for lbl, _b in blobs}
    pat = os.path.join(root, f"{dt:%Y}", f"{dt:%m}", f"{dt:%d}", "*.json.gz")
    for p in sorted(glob.glob(pat)):
        if p in seen:
            continue
        skipped.append({"snapshot": p, "reason": "unreadable file (OSError)"})
    for label, blob in blobs:
        try:
            f = airindex.deserialize(blob)
            if not isinstance(f, dict) or not isinstance(
                    f.get("cells"), dict):
                raise ValueError("not an airindex field (no cells dict)")
        except Exception as e:  # noqa: BLE001 - one corrupt snapshot != day lost
            skipped.append({"snapshot": label,
                            "reason": f"{type(e).__name__}: {e}"[:160]})
            continue
        f["_snapshot"] = label
        fields.append(f)
    fields.sort(key=lambda f: f.get("built_epoch") or 0)
    return fields, skipped


def _load_fields(date: str, snapshot_root: str = None):
    fields = []
    for label, blob in _iter_snapshot_blobs(date, snapshot_root):
        try:
            f = airindex.deserialize(blob)
        except Exception:  # noqa: BLE001 - one corrupt snapshot != day lost
            continue
        f["_snapshot"] = label
        fields.append(f)
    fields.sort(key=lambda f: f.get("built_epoch") or 0)
    return fields


def latest_snapshot(snapshot_root: str = None):
    """Newest snapshot anywhere under the root -> field dict or None."""
    root = snapshot_root or SNAPSHOT_DIR
    paths = sorted(glob.glob(os.path.join(root, "**", "*.json.gz"),
                             recursive=True))
    if not paths:
        return None
    try:
        with open(paths[-1], "rb") as f:
            return airindex.deserialize(f.read())
    except Exception:  # noqa: BLE001
        return None


# ------------------------------------------------------------ stats helpers

def _pct(sorted_vals: list, q: float):
    """Linear-interpolated q-th percentile (q in 0..100) of sorted vals."""
    n = len(sorted_vals)
    if not n:
        return None
    if n == 1:
        return float(sorted_vals[0])
    pos = (q / 100.0) * (n - 1)
    lo = int(pos)
    hi = min(lo + 1, n - 1)
    frac = pos - lo
    return float(sorted_vals[lo]
                 + (sorted_vals[hi] - sorted_vals[lo]) * frac)


def _weighted_pct(pairs: list, q: float):
    """Weighted percentile over [(value, weight)] sorted by value: the
    first value whose cumulative weight reaches q% of the total."""
    if not pairs:
        return None
    total = sum(w for _v, w in pairs)
    if total <= 0:
        return None
    acc = 0.0
    for v, w in pairs:
        acc += w
        if acc >= (q / 100.0) * total:
            return float(v)
    return float(pairs[-1][0])


def _city_summary(means: list, weights: list = None) -> dict:
    """Weighted city statistics over per-cell daily means.

    Weighting: doc 05 §2 names no population-density proxy for the city
    summary, so every grid cell votes equally (uniform-cells). When a
    population layer lands, pass per-cell `weights` here and the label
    flips to 'per-cell-weights' — nothing else changes."""
    pairs = sorted(zip(means, weights)) if weights else \
        sorted((m, 1.0) for m in means)
    if not pairs:
        return {"weighting": "per-cell-weights" if weights
                else "uniform-cells",
                "weighted_mean_pm25": None, "weighted_median_pm25": None,
                "pm25_p10": None, "pm25_p25": None,
                "pm25_p75": None, "pm25_p90": None}
    wmean = sum(v * w for v, w in pairs) / sum(w for _v, w in pairs)
    return {
        "weighting": "per-cell-weights" if weights else "uniform-cells",
        "weighted_mean_pm25": round(wmean, 2),
        "weighted_median_pm25": round(_weighted_pct(pairs, 50), 2),
        "pm25_p10": round(_weighted_pct(pairs, 10), 2),
        "pm25_p25": round(_weighted_pct(pairs, 25), 2),
        "pm25_p75": round(_weighted_pct(pairs, 75), 2),
        "pm25_p90": round(_weighted_pct(pairs, 90), 2),
    }


# ------------------------------------------------------------ daily rollup

def daily_rollup(date: str, snapshot_root: str = None,
                 daily_dir: str = None, cell_weights: dict = None) -> dict:
    """-> the rollup dict; also persists daily/{date}.json via store_blob.

    `cell_weights` (optional): {cell_id: weight} for a population-weighted
    city summary. Doc 05 specifies no proxy, so the default is uniform —
    see _city_summary."""
    fields, skipped = _load_fields_verbose(date, snapshot_root)
    cells = {}   # cid -> {"vals","hours","n","lo_sum","hi_sum","n_band"}
    vent = []
    for f in fields:
        ep = f.get("built_epoch")
        ist_h = (datetime.fromtimestamp(ep, tz=IST).hour
                 if ep is not None else None)
        for cid, c in (f.get("cells") or {}).items():
            v = c.get("pm25")
            if v is None:
                continue
            a = cells.setdefault(cid, {"vals": [], "hours": {},
                                       "lo_sum": 0.0, "hi_sum": 0.0,
                                       "n_band": 0})
            a["vals"].append(v)
            if c.get("lo") is not None and c.get("hi") is not None:
                a["lo_sum"] += c["lo"]
                a["hi_sum"] += c["hi"]
                a["n_band"] += 1
            if ist_h is not None:
                a["hours"].setdefault(ist_h, []).append(v)
        vc = (f.get("met") or {}).get("vc_m2s")
        if vc is not None:
            vent.append({"t": f.get("built_at"), "vc_m2s": vc})

    out_cells = {}
    means = []
    for cid, a in cells.items():
        vs = a["vals"]
        svs = sorted(vs)
        n = len(vs)
        mean = sum(vs) / n
        hour_mean = sorted(
            ((sum(x) / len(x), h) for h, x in a["hours"].items()),
            reverse=True)
        out_cells[cid] = {
            "mean": round(mean, 2),
            "min": round(svs[0], 2),
            "max": round(svs[-1], 2),
            "p10": round(_pct(svs, 10), 2),
            "p50": round(_pct(svs, 50), 2),
            "p90": round(_pct(svs, 90), 2),
            "lo_mean": (round(a["lo_sum"] / a["n_band"], 2)
                        if a["n_band"] else None),
            "hi_mean": (round(a["hi_sum"] / a["n_band"], 2)
                        if a["n_band"] else None),
            "worst_hours": [h for _m, h in hour_mean[:6]],
            "n_snapshots": n,
        }
        means.append(mean)
    # weights pair with `means` in cell order — compute before sorting
    weights = ([cell_weights.get(cid, 0.0) for cid in cells]
               if cell_weights else None)
    weighted = _city_summary(means, weights)
    means.sort()
    n = len(means)
    median = means[n // 2] if n else None
    city = {
        "median_pm25": round(median, 2) if median is not None else None,
        "pct_cells_gt15_who": round(100.0 * sum(m > WHO_24H for m in means) / n, 1) if n else None,
        "pct_cells_gt60_cpcb": round(100.0 * sum(m > CPCB_24H for m in means) / n, 1) if n else None,
        "ventilation_m2s": vent,
    }
    city.update(weighted)
    city["weighting_note"] = (
        "doc 05 §2 names no population proxy — every cell votes equally. "
        "Pass cell_weights={cid: pop} for a population-weighted summary."
        if not cell_weights else
        "city stats weighted by the supplied per-cell weights (e.g. "
        "population); unweighted median/% above thresholds kept alongside.")
    rollup = {
        "schema": "alive-rollup/2",
        "date": date,
        "hours_tz": "IST",
        "n_snapshots": len(fields),
        "snapshots": [f["_snapshot"] for f in fields],
        "inputs": {"skipped": skipped, "n_skipped": len(skipped)},
        "n_cells": len(out_cells),
        "thresholds": {"who_24h_pm25": WHO_24H, "cpcb_24h_pm25": CPCB_24H},
        "city": city,
        "cells": out_cells,
    }
    payload = json.dumps(rollup, sort_keys=True).encode("utf-8")
    uri, backend, note = store_blob(
        f"daily/{date}.json", payload,
        os.path.join(daily_dir or DAILY_DIR, f"{date}.json"),
        mirror_local=True)
    rollup["written_to"] = uri
    rollup["backend"] = backend
    if note:
        rollup["note"] = note
    return rollup


# ------------------------------------------------------------ validation

def _fold_predict(held: dict, others: list):
    """Rebuild the residual field without `held` and predict (pm, lo, hi,
    method) at its location.

    The model prior doesn't depend on stations, so a fold rebuild = refit
    the station-residual interpolator on the N-1 remaining stations —
    krige.KrigeField where it fits (>=20 varying samples + numpy), else
    the same IDW + distance-grown sigma airindex.build_field uses for a
    grid cell. base = obs - residual reconstructs the prior at the held
    station (residual = smoothed obs - prior by construction)."""
    base = held["pm25"] - held["residual"]
    pts = [(o["lat"], o["lon"], o["residual"]) for o in others]
    kf = KrigeField().fit([(o["lat"], o["lon"], o["name"],
                            {"pm2_5": o["residual"]}) for o in others])
    est = kf.estimate(held["lat"], held["lon"])
    if est is not None:
        mu_r, sd_r = est
        pm = base + mu_r
        # same band as build_field: krige sigma + 12% instrument floor
        sd = math.sqrt(sd_r * sd_r + (0.12 * pm) ** 2)
        method = "krige"
    else:
        mu_r = airindex._idw(pts, held["lat"], held["lon"])
        if mu_r is None:
            return None
        pm = base + mu_r
        near = min(airindex._km(held["lat"], held["lon"], la, lo)
                   for la, lo, _r in pts)
        if len(pts) >= 2:
            vs = sorted(p[2] for p in pts)
            mu = sum(vs) / len(vs)
            spread = math.sqrt(sum((v - mu) ** 2 for v in vs) / len(vs))
        else:
            spread = 0.0
        decay = 1.0 - math.exp(-near / 15.0)
        sd = math.sqrt((0.12 * pm) ** 2
                       + (min(spread, 60.0) * decay) ** 2
                       + (0.05 * pm) ** 2)
        method = "idw-residual"
    pm = max(0.0, pm)
    lo = max(0.0, pm - 1.96 * sd)
    hi = pm + 1.96 * sd
    return pm, lo, hi, method


def loso_validation(field: dict) -> dict:
    """Leave-one-station-out on a built field.

    For each usable station (the fold), the residual field is rebuilt from
    the OTHER stations only and predicts the held-out reading with its
    lo..hi band; held-out error = pred - obs (the model prior cancels
    exactly, so residual-space error == concentration-space error).
    -> per-station errors + in-band flags, MAE/RMSE/bias, band coverage.
    Stations missing pm25/residual/location are counted under `skipped`,
    never silently folded."""
    all_st = field.get("stations") or []
    sts, skipped = [], []
    for s in all_st:
        if (s.get("residual") is None or s.get("pm25") is None
                or s.get("lat") is None or s.get("lon") is None):
            skipped.append({"station": s.get("name"),
                            "reason": "missing pm25/residual/lat/lon"})
        else:
            sts.append(s)
    if len(sts) < MIN_STATIONS_LOSO:
        return {"status": "insufficient stations", "n": len(sts),
                "n_folds": 0, "skipped": skipped,
                "n_skipped": len(skipped)}
    errs = []
    per = []
    n_in = 0
    for i, s in enumerate(sts):
        others = [o for j, o in enumerate(sts) if j != i]
        r = _fold_predict(s, others)
        if r is None:
            skipped.append({"station": s.get("name"),
                            "reason": "no estimate from remaining stations"})
            continue
        pm, lo, hi, method = r
        obs = float(s["pm25"])
        e = pm - obs
        in_band = lo <= obs <= hi
        n_in += 1 if in_band else 0
        errs.append(e)
        per.append({"station": s["name"],
                    "obs_ugm3": round(obs, 2),
                    "pred_ugm3": round(pm, 2),
                    "lo_ugm3": round(lo, 2), "hi_ugm3": round(hi, 2),
                    "err_ugm3": round(e, 2),
                    "in_band": bool(in_band),
                    "method": method})
    n = len(errs)
    if not n:
        return {"status": "no pairs", "n": 0, "n_folds": 0,
                "skipped": skipped, "n_skipped": len(skipped)}
    mae = sum(abs(e) for e in errs) / n
    rmse = math.sqrt(sum(e * e for e in errs) / n)
    bias = sum(errs) / n
    return {"status": "ok", "n": n, "n_folds": n,
            "mae_ugm3": round(mae, 2), "rmse_ugm3": round(rmse, 2),
            "bias_ugm3": round(bias, 2),
            "coverage_pct": round(100.0 * n_in / n, 1),
            "band": "rebuilt lo..hi (±1.96·sigma, ~95% nominal)",
            "method": "krige+idw-fallback", "per_station": per,
            "skipped": skipped, "n_skipped": len(skipped)}


def _iter_week_labels(week: str, snapshot_root: str = None):
    """Local snapshot paths inside ISO `week` ("YYYY-Www"), newest first.
    Snapshots are filed by UTC date; the week runs Mon..Sun UTC."""
    try:
        y, w = week.split("-W", 1)
        mon = _date.fromisocalendar(int(y), int(w), 1)
    except (ValueError, AttributeError):
        return []
    root = snapshot_root or SNAPSHOT_DIR
    out = []
    for d in range(7):
        day = mon + timedelta(days=d)
        pat = os.path.join(root, f"{day:%Y}", f"{day:%m}", f"{day:%d}",
                           "*.json.gz")
        out.extend(sorted(glob.glob(pat)))
    return out[::-1]


def _latest_usable_in_week(week: str, snapshot_root: str = None):
    """-> (field_or_None, skipped, n_scanned): walk the week's snapshots
    newest-first; first that deserializes to an airindex field wins.
    Local mirror first, then the S3 field/ prefix — the ECS task writes
    snapshots S3-only, so without this hop a weekly LOSO on the box that
    actually runs it finds no field. Every failure is counted — corrupt
    inputs are never silently passed over and never fabricated."""
    skipped = []
    paths = _iter_week_labels(week, snapshot_root)
    for p in paths:
        try:
            with open(p, "rb") as f:
                cand = airindex.deserialize(f.read())
            if not isinstance(cand, dict) or not isinstance(
                    cand.get("cells"), dict):
                raise ValueError("not an airindex field (no cells dict)")
            cand["_snapshot"] = p
            return cand, skipped, len(paths)
        except Exception as e:  # noqa: BLE001 - count it, try the next
            skipped.append({"snapshot": p,
                            "reason": f"{type(e).__name__}: {e}"[:160]})
    n_scanned = len(paths)
    try:
        y, w = week.split("-W", 1)
        days = [_date.fromisocalendar(int(y), int(w), 1) + timedelta(days=d)
                for d in range(6, -1, -1)]   # newest day first
    except (ValueError, AttributeError):
        days = []
    for day in days:
        for label, blob in _iter_s3_blobs(day.strftime("%Y-%m-%d"),
                                          desc=True):
            n_scanned += 1
            try:
                cand = airindex.deserialize(blob)
                if not isinstance(cand, dict) or not isinstance(
                        cand.get("cells"), dict):
                    raise ValueError("not an airindex field (no cells dict)")
                cand["_snapshot"] = label
                return cand, skipped, n_scanned
            except Exception as e:  # noqa: BLE001
                skipped.append({"snapshot": label,
                                "reason": f"{type(e).__name__}: {e}"[:160]})
    return None, skipped, n_scanned


def _render_weekly_summary(out: dict) -> str:
    """Human-readable one-pager for the /city + admin dashboard link."""
    L = []
    loso = out.get("loso") or {}
    arch = out.get("archive_replay") or {}
    L.append(f"# Weekly field validation — {out['week']}")
    L.append("")
    L.append(f"Generated {out['generated']} · schema {out['schema']} · "
             f"snapshot {out.get('snapshot') or 'none'}"
             + ("" if out.get("snapshot_in_iso_week") else
                " (outside ISO week — legacy fallback)"))
    L.append("")
    L.append("## Leave-one-station-out")
    L.append("")
    if loso.get("status") == "ok":
        L.append(f"- Folds evaluated: **{loso['n_folds']}** "
                 f"(one per usable station; "
                 f"{loso.get('n_skipped', 0)} skipped)")
        L.append(f"- MAE **{loso['mae_ugm3']}** µg/m³ · "
                 f"RMSE {loso['rmse_ugm3']} · bias {loso['bias_ugm3']:+}")
        L.append(f"- Band coverage: **{loso['coverage_pct']}%** of held-out "
                 f"observations inside the rebuilt lo–hi band (~95% nominal)")
        worst = sorted(loso.get("per_station") or [],
                       key=lambda r: -abs(r["err_ugm3"]))[:10]
        if worst:
            L.append("")
            L.append("| station | obs | pred | lo | hi | err | in band | "
                     "method |")
            L.append("|---|---|---|---|---|---|---|---|")
            for r in worst:
                L.append(f"| {r['station']} | {r['obs_ugm3']} | "
                         f"{r['pred_ugm3']} | {r['lo_ugm3']} | {r['hi_ugm3']} "
                         f"| {r['err_ugm3']:+.2f} | "
                         f"{'yes' if r['in_band'] else 'NO'} | {r['method']} |")
    else:
        L.append(f"- status: **{loso.get('status')}** "
                 f"(n={loso.get('n', 0)})")
    sk = loso.get("skipped") or []
    if sk:
        L.append("")
        L.append(f"- skipped stations ({len(sk)}): " + "; ".join(
            f"{s.get('station')}: {s.get('reason')}" for s in sk[:20]))
    L.append("")
    L.append("## Archive replay vs OpenAQ ground truth")
    L.append("")
    if arch.get("status") == "ok":
        L.append(f"- pairs: {arch['pairs']} · MAE {arch['mae_ugm3']} µg/m³ · "
                 f"RMSE {arch['rmse_ugm3']} · bias {arch['bias_ugm3']:+} "
                 f"(mean obs {arch['mean_obs']})")
    else:
        L.append(f"- status: **{arch.get('status')}**")
    skipped = (out.get("inputs") or {}).get("skipped") or []
    L.append("")
    L.append("## Inputs skipped (honest accounting)")
    L.append("")
    if skipped:
        for s in skipped[:30]:
            L.append(f"- `{s['snapshot']}` — {s['reason']}")
        if len(skipped) > 30:
            L.append(f"- … and {len(skipped) - 30} more")
    else:
        L.append("- none")
    L.append("")
    return "\n".join(L)


def weekly_validation(week: str = None, snapshot_root: str = None,
                      valid_dir: str = None) -> dict:
    """Weekly LOSO + archive replay -> validation/weekly-{week}.json + .md."""
    now = datetime.now(timezone.utc)
    iso_y, iso_w, _ = now.isocalendar()
    week = week or f"{iso_y}-W{iso_w:02d}"

    field, skipped, n_scanned = _latest_usable_in_week(week, snapshot_root)
    in_week = field is not None
    if field is None:
        field = latest_snapshot(snapshot_root)   # legacy fallback, flagged
    loso = (loso_validation(field) if field
            else {"status": "no usable snapshot", "n": 0, "n_folds": 0,
                  "skipped": skipped, "n_skipped": len(skipped)})

    # archive replay — same machinery validate_field.py writes its report
    # from (OpenAQ S3 ground truth vs rebuilt model field). Needs network
    # and the openaq_recent cache; failure is reported, not raised —
    # including SystemExit from validate_field's sys.exit guard.
    archive = {"status": "not attempted"}
    try:
        import validate_field
        _truth, pairs = validate_field.validate(hours_back=168)
        if pairs:
            # pairs: (station, hour, obs, krige|None, idw, sigma, ...)
            # positional reads — the schema grew fields before and the
            # arity unpack shipped a live ValueError on the admin tile
            errs = [p[3] - p[2] for p in pairs
                    if len(p) >= 4 and p[3] is not None]
            obs = [p[2] for p in pairs
                   if len(p) >= 4 and p[3] is not None]
            nn = len(errs)
            archive = {"status": "ok", "pairs": nn,
                       "mae_ugm3": round(sum(abs(e) for e in errs) / nn, 2),
                       "rmse_ugm3": round(math.sqrt(
                           sum(e * e for e in errs) / nn), 2),
                       "bias_ugm3": round(sum(errs) / nn, 2),
                       "mean_obs": round(sum(obs) / nn, 2)}
        else:
            archive = {"status": "no overlapping pairs"}
    except (Exception, SystemExit) as e:  # noqa: BLE001
        archive = {"status": f"unavailable: {type(e).__name__}: {e}"[:160]}

    out = {
        "schema": "alive-validation/2",
        "week": week,
        "generated": now.isoformat(timespec="seconds"),
        "snapshot": field.get("built_at") if field else None,
        "snapshot_used": field.get("_snapshot") if field else None,
        "snapshot_in_iso_week": in_week,
        "inputs": {"snapshots_scanned": n_scanned,
                   "skipped": skipped, "n_skipped": len(skipped)},
        "loso": loso,
        "archive_replay": archive,
    }
    payload = json.dumps(out, sort_keys=True, indent=1).encode("utf-8")
    vdir = valid_dir or VALID_DIR
    uri, backend, note = store_blob(
        f"validation/weekly-{week}.json", payload,
        os.path.join(vdir, f"weekly-{week}.json"), mirror_local=True)
    # compat copy under the pre-v2 name — weekly-{week}.json is canonical
    _u2, _b2, _n2 = store_blob(
        f"validation/{week}.json", payload,
        os.path.join(vdir, f"{week}.json"), mirror_local=True)
    out["written_to"] = uri
    out["backend"] = backend
    if note or _n2:
        out["note"] = "; ".join(x for x in (note, _n2) if x)
    md = _render_weekly_summary(out)
    md_uri, _mb, _mn = store_blob(
        f"validation/weekly-{week}.md", md.encode("utf-8"),
        os.path.join(vdir, f"weekly-{week}.md"), mirror_local=True)
    out["summary_md"] = md_uri
    if _mn:
        out["note"] = "; ".join(x for x in (out.get("note"), _mn) if x)
    # The archive replay wrote data/field_validation.md on THIS job
    # task's disk — ship it too or the API's mirror never sees the report
    # the admin page checks for.
    try:
        fv = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          "data", "field_validation.md")
        if os.path.exists(fv):
            store_blob("validation/field_validation.md",
                       open(fv, "rb").read(), fv)
    except Exception:
        pass
    return out


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["daily", "weekly"], nargs="?",
                    default="daily")
    ap.add_argument("arg", nargs="?",
                    default=datetime.now(tz=IST).strftime("%Y-%m-%d"))
    a = ap.parse_args()
    if a.cmd == "daily":
        print(json.dumps(daily_rollup(a.arg)["city"], indent=1))
    else:
        rep = weekly_validation(a.arg)
        print(json.dumps(rep, indent=1))
        if rep.get("summary_md"):
            print(f"# human summary -> {rep['summary_md']}",
                  file=sys.stderr)
