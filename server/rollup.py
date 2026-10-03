"""Daily rollup + weekly validation for the air index (doc 05 §2).

daily_rollup("YYYY-MM-DD"):
  reads the day's snapshots (s3://{ALIVE_AIR_BUCKET}/field/YYYY/MM/DD/*.json.gz
  when configured, else the local mirror under
  server/data/field/snapshots/) and writes
      daily/YYYY-MM-DD.json            (S3)  or  data/field/daily/YYYY-MM-DD.json
  containing per-cell mean/max/worst-hours plus the city summary:
  median, % cells above the WHO 24 h guideline (15 µg/m³) and the CPCB
  24 h NAAQS (60 µg/m³), and the ventilation-coefficient (BLH x wind)
  series sampled from each snapshot's met block.

weekly_validation():
  two honest checks, both wired to real machinery:
    - leave-one-station-out on the week's latest snapshot: each used
      station's residual is re-estimated from the OTHER stations via the
      same krige.KrigeField the builder uses (IDW fallback when too few
      to fit) -> MAE/RMSE/bias of held-out predictions
    - validate_field.validate() — the archive replay against OpenAQ S3
      ground truth (network + archive cache required; reported as
      'unavailable' with the reason when it can't run)
"""
import glob
import gzip
import json
import math
import os
import sys
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


# ------------------------------------------------------------ snapshot IO

def _iter_snapshot_blobs(date: str, snapshot_root: str = None):
    """Yield (label, gzip-bytes) for every snapshot of `date`.

    Local mirror first; when ALIVE_AIR_BUCKET + boto3 are usable, also
    list the S3 prefix (labels tell which source each blob came from)."""
    dt = datetime.strptime(date, "%Y-%m-%d")
    root = snapshot_root or SNAPSHOT_DIR
    pat = os.path.join(root, f"{dt:%Y}", f"{dt:%m}", f"{dt:%d}", "*.json.gz")
    for p in sorted(glob.glob(pat)):
        try:
            with open(p, "rb") as f:
                yield p, f.read()
        except OSError:
            continue
    bucket = os.environ.get("ALIVE_AIR_BUCKET")
    b3 = _boto3() if bucket else None
    if b3 is None:
        return
    try:
        s3 = b3.client("s3")
        prefix = f"field/{dt:%Y/%m/%d}/"
        for page in s3.get_paginator("list_objects_v2").paginate(
                Bucket=bucket, Prefix=prefix):
            for obj in page.get("Contents", []):
                try:
                    body = s3.get_object(Bucket=bucket,
                                         Key=obj["Key"])["Body"].read()
                    yield f"s3://{bucket}/{obj['Key']}", body
                except Exception:  # noqa: BLE001
                    continue
    except Exception:  # noqa: BLE001 - S3 listing is best-effort
        return


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


# ------------------------------------------------------------ daily rollup

def daily_rollup(date: str, snapshot_root: str = None,
                 daily_dir: str = None) -> dict:
    """-> the rollup dict; also persists daily/{date}.json via store_blob."""
    fields = _load_fields(date, snapshot_root)
    cells = {}   # cid -> {"sum","max","hours":{ist_hour:[v]}}
    vent = []
    for f in fields:
        ep = f.get("built_epoch")
        ist_h = (datetime.fromtimestamp(ep, tz=IST).hour
                 if ep is not None else None)
        for cid, c in (f.get("cells") or {}).items():
            v = c.get("pm25")
            if v is None:
                continue
            a = cells.setdefault(cid, {"sum": 0.0, "n": 0,
                                       "max": -1e18, "hours": {}})
            a["sum"] += v
            a["n"] += 1
            a["max"] = max(a["max"], v)
            if ist_h is not None:
                a["hours"].setdefault(ist_h, []).append(v)
        vc = (f.get("met") or {}).get("vc_m2s")
        if vc is not None:
            vent.append({"t": f.get("built_at"), "vc_m2s": vc})

    out_cells = {}
    means = []
    for cid, a in cells.items():
        mean = a["sum"] / a["n"]
        hour_mean = sorted(
            ((sum(vs) / len(vs), h) for h, vs in a["hours"].items()),
            reverse=True)
        out_cells[cid] = {
            "mean": round(mean, 2),
            "max": round(a["max"], 2),
            "worst_hours": [h for _m, h in hour_mean[:6]],
            "n_snapshots": a["n"],
        }
        means.append(mean)
    means.sort()
    n = len(means)
    median = means[n // 2] if n else None
    city = {
        "median_pm25": round(median, 2) if median is not None else None,
        "pct_cells_gt15_who": round(100.0 * sum(m > WHO_24H for m in means) / n, 1) if n else None,
        "pct_cells_gt60_cpcb": round(100.0 * sum(m > CPCB_24H for m in means) / n, 1) if n else None,
        "ventilation_m2s": vent,
    }
    rollup = {
        "schema": "alive-rollup/1",
        "date": date,
        "hours_tz": "IST",
        "n_snapshots": len(fields),
        "snapshots": [f["_snapshot"] for f in fields],
        "n_cells": len(out_cells),
        "thresholds": {"who_24h_pm25": WHO_24H, "cpcb_24h_pm25": CPCB_24H},
        "city": city,
        "cells": out_cells,
    }
    payload = json.dumps(rollup, sort_keys=True).encode("utf-8")
    uri, backend, note = store_blob(
        f"daily/{date}.json", payload,
        os.path.join(daily_dir or DAILY_DIR, f"{date}.json"))
    rollup["written_to"] = uri
    rollup["backend"] = backend
    if note:
        rollup["note"] = note
    return rollup


# ------------------------------------------------------------ validation

def loso_validation(field: dict) -> dict:
    """Leave-one-station-out on a built field.

    Each used station's kriged residual is re-estimated from the OTHER
    stations only; held-out error = resid_est - resid_obs (the model prior
    cancels exactly, so residual-space error == concentration-space error).
    -> per-station errors + MAE/RMSE/bias."""
    sts = [s for s in (field.get("stations") or [])
           if s.get("residual") is not None]
    if len(sts) < 4:
        return {"status": "insufficient stations", "n": len(sts)}
    errs = []
    per = []
    for i, s in enumerate(sts):
        others = [(o["lat"], o["lon"], o["name"],
                   {"pm2_5": o["residual"]})
                  for j, o in enumerate(sts) if j != i]
        kf = KrigeField().fit(others)
        est = kf.estimate(s["lat"], s["lon"])
        if est is None:
            est_mu = airindex._idw(
                [(o["lat"], o["lon"], o["residual"])
                 for j, o in enumerate(sts) if j != i],
                s["lat"], s["lon"])
            if est_mu is None:
                continue
        else:
            est_mu = est[0]
        e = est_mu - s["residual"]
        errs.append(e)
        per.append({"station": s["name"], "err_ugm3": round(e, 2)})
    n = len(errs)
    if not n:
        return {"status": "no pairs", "n": 0}
    mae = sum(abs(e) for e in errs) / n
    rmse = math.sqrt(sum(e * e for e in errs) / n)
    bias = sum(errs) / n
    return {"status": "ok", "n": n,
            "mae_ugm3": round(mae, 2), "rmse_ugm3": round(rmse, 2),
            "bias_ugm3": round(bias, 2),
            "method": "krige" , "per_station": per}


def weekly_validation(week: str = None, snapshot_root: str = None,
                      valid_dir: str = None) -> dict:
    """Weekly LOSO + archive replay -> validation/{week}.json."""
    now = datetime.now(timezone.utc)
    iso_y, iso_w, _ = now.isocalendar()
    week = week or f"{iso_y}-W{iso_w:02d}"

    field = latest_snapshot(snapshot_root)
    loso = (loso_validation(field) if field
            else {"status": "no snapshot available"})

    # archive replay — same machinery validate_field.py writes its report
    # from (OpenAQ S3 ground truth vs rebuilt model field). Needs network
    # and the openaq_recent cache; failure is reported, not raised.
    archive = {"status": "not attempted"}
    try:
        import validate_field
        _truth, pairs = validate_field.validate(hours_back=168)
        if pairs:
            errs = [m - o for _s, _h, o, m, _i in pairs]
            obs = [o for _s, _h, o, _m, _i in pairs]
            nn = len(errs)
            archive = {"status": "ok", "pairs": nn,
                       "mae_ugm3": round(sum(abs(e) for e in errs) / nn, 2),
                       "rmse_ugm3": round(math.sqrt(
                           sum(e * e for e in errs) / nn), 2),
                       "bias_ugm3": round(sum(errs) / nn, 2),
                       "mean_obs": round(sum(obs) / nn, 2)}
        else:
            archive = {"status": "no overlapping pairs"}
    except Exception as e:  # noqa: BLE001
        archive = {"status": f"unavailable: {type(e).__name__}: {e}"[:160]}

    out = {
        "schema": "alive-validation/1",
        "week": week,
        "generated": now.isoformat(timespec="seconds"),
        "snapshot": field.get("built_at") if field else None,
        "loso": loso,
        "archive_replay": archive,
    }
    payload = json.dumps(out, sort_keys=True, indent=1).encode("utf-8")
    uri, backend, note = store_blob(
        f"validation/{week}.json", payload,
        os.path.join(valid_dir or VALID_DIR, f"{week}.json"))
    out["written_to"] = uri
    out["backend"] = backend
    if note:
        out["note"] = note
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
        print(json.dumps(weekly_validation(a.arg), indent=1))
