"""EventBridge/Lambda entry points for the scheduled jobs (doc 05 §2).

Three jobs, matching the schedule payloads in infra/provision.sh and
infra/schedules/*.json:

    {"job":"ingest"}    -> field_tick()        every 15 min: build the air
                                             index + write the snapshot
    {"job":"rollup"}    -> daily_rollup()      00:30 IST: roll the last
                                             fully-closed snapshot day
    {"job":"validate"}  -> weekly_validation() Sun night: LOSO + archive
                                             replay report

Each is a plain function — `python3 rollup_lambda.py ingest|rollup|validate`
runs it locally with no Lambda and no AWS requirement; the underlying
workers already write to s3://$ALIVE_AIR_BUCKET when that env var +
credentials resolve and to server/data/field/* mirrors otherwise.

Env-configured paths (all optional, defaults = the repo's data/ mirror):
    ALIVE_SNAPSHOT_DIR      snapshot mirror root (local writes + reads)
    ALIVE_DAILY_DIR         where daily/{date}.json lands (local backend)
    ALIVE_VALID_DIR         where validation/{week}.json lands
    ALIVE_ROLLUP_DATE       force the rollup date (YYYY-MM-DD)
    ALIVE_VALIDATION_WEEK   force the validation ISO week (YYYY-Www)
    ALIVE_JOB               default job when event has none
    ALIVE_AIR_BUCKET        (consumed by ingest_worker.store_blob/rollup)
"""
import json
import os
import sys
from datetime import datetime, timedelta, timezone

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import ingest_worker  # noqa: E402
import rollup         # noqa: E402

IST = timezone(timedelta(hours=5, minutes=30))


def _env_path(name: str):
    return os.environ.get(name) or None


def _last_closed_day() -> str:
    """The last fully-closed UTC snapshot day.

    The rollup schedule fires at 19:00 UTC (00:30 IST) — snapshots are
    filed under UTC dirs field/YYYY/MM/DD/, so the day that just ended in
    UTC is complete. Override with event['date'] or ALIVE_ROLLUP_DATE."""
    return (datetime.now(timezone.utc) - timedelta(days=1)).strftime(
        "%Y-%m-%d")


# --------------------------------------------------------------- jobs

def field_tick(event=None, context=None, *, now=None, inputs=None) -> dict:
    """The 15-min ingest cycle — airindex.build_field() + snapshot write
    + CloudWatch metrics (skipped without AWS, reported in the body)."""
    return ingest_worker.run_index_once(
        now=now, inputs=inputs,
        snapshot_root=_env_path("ALIVE_SNAPSHOT_DIR"))


def daily_rollup(event=None, context=None, *, date: str = None) -> dict:
    """Roll snapshots of `date` -> daily/{date}.json (S3 or local)."""
    date = (date or (event or {}).get("date")
            or os.environ.get("ALIVE_ROLLUP_DATE") or _last_closed_day())
    return rollup.daily_rollup(
        date,
        snapshot_root=_env_path("ALIVE_SNAPSHOT_DIR"),
        daily_dir=_env_path("ALIVE_DAILY_DIR"))


def weekly_validation(event=None, context=None, *, week: str = None) -> dict:
    """Weekly LOSO + archive replay -> validation/{week}.json."""
    week = (week or (event or {}).get("week")
            or os.environ.get("ALIVE_VALIDATION_WEEK") or None)
    return rollup.weekly_validation(
        week,
        snapshot_root=_env_path("ALIVE_SNAPSHOT_DIR"),
        valid_dir=_env_path("ALIVE_VALID_DIR"))


JOBS = {
    "ingest": field_tick,     # infra/schedules/ingest-15min.json
    "rollup": daily_rollup,   # infra/schedules/rollup-daily-0030IST.json
    "validate": weekly_validation,  # infra/schedules/validate-weekly.json
}


def handler(event, context=None):
    """EventBridge Scheduler / Lambda entry — routes on event['job']."""
    job = ((event or {}).get("job")
           or os.environ.get("ALIVE_JOB") or "ingest")
    fn = JOBS.get(job)
    if fn is None:
        return {"statusCode": 400,
                "body": json.dumps({
                    "ok": False,
                    "error": f"unknown job {job!r}",
                    "jobs": sorted(JOBS)})}
    try:
        return {"statusCode": 200,
                "body": json.dumps(fn(event, context), default=str)}
    except Exception as e:  # noqa: BLE001 - surface, don't hang the schedule
        return {"statusCode": 500,
                "body": json.dumps({"ok": False, "job": job,
                                    "error": f"{type(e).__name__}: {e}"})}


if __name__ == "__main__":
    job = sys.argv[1] if len(sys.argv) > 1 else "ingest"
    extra = json.loads(sys.argv[2]) if len(sys.argv) > 2 else {}
    ev = {"job": job, **extra}
    print(json.dumps(handler(ev), indent=1, default=str))
