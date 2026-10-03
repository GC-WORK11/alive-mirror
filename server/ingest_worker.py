"""Air-index ingest worker — the every-15-min job from doc 05 §2.

run_index_once():
  1. airindex.build_field()  (live upstream pulls; `inputs` injectable for
     tests/replay so nothing touches the network)
  2. snapshot -> s3://{ALIVE_AIR_BUCKET}/field/YYYY/MM/DD/HHmm.json.gz when
     the bucket env var is set AND boto3 + credentials are usable;
     otherwise -> server/data/field/snapshots/YYYY/MM/DD/HHmm.json.gz
  3. CloudWatch metrics (StationsUsed, FieldAgeSeconds, MeanSigma in
     namespace "ALive-108") — emitted only when boto3 AND AWS credentials
     resolve; skipped (reported) otherwise, never fatal.

handler(event, context) is the EventBridge/Lambda entry point — same code
path, JSON status response.
"""
import json
import os
import sys
from datetime import datetime, timezone

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import airindex  # noqa: E402

DATA_DIR = os.path.join(_HERE, "data")
SNAPSHOT_DIR = os.path.join(DATA_DIR, "field", "snapshots")
METRIC_NS = "ALive-108"


def _boto3():
    """boto3 if installed (optional dep — not in requirements yet)."""
    try:
        import boto3
        return boto3
    except ImportError:
        return None


def _aws_ready() -> tuple:
    """-> (boto3_module_or_None, reason). Credentials must actually resolve
    (env vars, ~/.aws, or task role) — a boto3 install alone is not enough."""
    b3 = _boto3()
    if b3 is None:
        return None, "no boto3"
    try:
        if b3.Session().get_credentials() is None:
            return None, "no credentials"
    except Exception as e:  # noqa: BLE001
        return None, f"credential check failed: {type(e).__name__}"
    return b3, "ok"


def store_blob(s3_key: str, data: bytes, local_path: str) -> tuple:
    """Write `data` to s3://{ALIVE_AIR_BUCKET}/{s3_key} when the bucket is
    configured and AWS is usable, else to `local_path`. Always writes
    somewhere — a failed S3 put degrades to local, never loses a snapshot.

    -> (uri, backend, note)  backend in {"s3", "local"}.
    """
    bucket = os.environ.get("ALIVE_AIR_BUCKET")
    if bucket:
        b3, why = _aws_ready()
        if b3 is not None:
            try:
                kw = {"Bucket": bucket, "Key": s3_key, "Body": data,
                      "ContentType": "application/json"}
                if s3_key.endswith(".gz"):
                    kw["ContentEncoding"] = "gzip"
                b3.client("s3").put_object(**kw)
                return f"s3://{bucket}/{s3_key}", "s3", None
            except Exception as e:  # noqa: BLE001 - fall through to local
                note = f"s3 put failed ({type(e).__name__}: {e}) — wrote local"
        else:
            note = f"bucket set but {why} — wrote local"
    else:
        note = None
    os.makedirs(os.path.dirname(local_path), exist_ok=True)
    with open(local_path, "wb") as f:
        f.write(data)
    return local_path, "local", note


def _emit_metrics(field: dict) -> dict:
    """CloudWatch for the doc-05 dashboard: stations used, field age
    (oldest input age), mean kriging sigma. Only when AWS is usable —
    reported, never raised."""
    b3, why = _aws_ready()
    if b3 is None:
        return {"emitted": False, "skipped": why}
    ages = [p["age_s"] for p in field["provenance"].values()
            if p.get("age_s") is not None]
    datum = [
        {"MetricName": "StationsUsed", "Value": field["qc"]["stations_used"],
         "Unit": "Count"},
        {"MetricName": "FieldAgeSeconds", "Value": max(ages) if ages else 0,
         "Unit": "Seconds"},
    ]
    if field["stats"].get("mean_sigma") is not None:
        datum.append({"MetricName": "MeanSigma",
                      "Value": field["stats"]["mean_sigma"], "Unit": "None"})
    try:
        b3.client("cloudwatch").put_metric_data(
            Namespace=METRIC_NS, MetricData=datum)
        return {"emitted": True, "metrics": [d["MetricName"] for d in datum],
                "namespace": METRIC_NS}
    except Exception as e:  # noqa: BLE001
        return {"emitted": False, "skipped": f"{type(e).__name__}: {e}"}


def run_index_once(now=None, *, inputs=None, snapshot_root: str = None) -> dict:
    """One 15-min index build. -> summary dict (also the handler body)."""
    field = airindex.build_field(now=now, inputs=inputs)
    blob = airindex.serialize(field)
    ts = datetime.fromtimestamp(field["built_epoch"], tz=timezone.utc)
    rel = os.path.join(f"{ts:%Y/%m/%d}", f"{ts:%H%M}.json.gz")
    uri, backend, note = store_blob(f"field/{ts:%Y/%m/%d/%H%M}.json.gz",
                                  blob,
                                  os.path.join(snapshot_root or SNAPSHOT_DIR,
                                               rel))
    metrics = _emit_metrics(field)
    return {
        "ok": True,
        "snapshot": uri,
        "backend": backend,
        "note": note,
        "built_at": field["built_at"],
        "grid_system": field["grid"]["system"],
        "cells": field["grid"]["n_cells"],
        "stations_used": field["qc"]["stations_used"],
        "qc_dropped": {k: len(v) for k, v in field["qc"]["dropped"].items()},
        "kriging": field["qc"]["kriging"],
        "mean_sigma": field["stats"]["mean_sigma"],
        "provenance_status": {k: v["status"]
                              for k, v in field["provenance"].items()},
        "metrics": metrics,
    }


def handler(event, context):
    """EventBridge Scheduler / Lambda entry point."""
    try:
        return {"statusCode": 200,
                "body": json.dumps(run_index_once(), default=str)}
    except Exception as e:  # noqa: BLE001 - surface, don't hang the schedule
        return {"statusCode": 500,
                "body": json.dumps({"ok": False,
                                    "error": f"{type(e).__name__}: {e}"})}


if __name__ == "__main__":
    print(json.dumps(run_index_once(), indent=1, default=str))
