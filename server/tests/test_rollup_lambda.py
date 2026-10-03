"""Offline tests for rollup_lambda — the EventBridge entry points.

No network, no AWS: field_tick gets airindex `inputs` injected wholesale,
daily_rollup/weekly_validation read seeded snapshots in a tmp dir, the
AWS probe is forced offline, and validate_field is stubbed. Asserts the
env-configured paths and the job dispatch too.
Run from server/:  .venv/bin/python -m pytest tests/test_rollup_lambda.py -v
"""
import gzip
import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import airindex       # noqa: E402
import ingest_worker  # noqa: E402
import rollup_lambda  # noqa: E402
import validate_field  # noqa: E402


@pytest.fixture(autouse=True)
def offline(tmp_path, monkeypatch):
    """Hermetic: no bucket, no AWS, deterministic dirs under tmp_path."""
    monkeypatch.delenv("ALIVE_AIR_BUCKET", raising=False)
    monkeypatch.delenv("ALIVE_ROLLUP_DATE", raising=False)
    monkeypatch.delenv("ALIVE_VALIDATION_WEEK", raising=False)
    monkeypatch.delenv("ALIVE_JOB", raising=False)
    monkeypatch.setenv("ALIVE_SNAPSHOT_DIR", str(tmp_path / "snaps"))
    monkeypatch.setenv("ALIVE_DAILY_DIR", str(tmp_path / "daily"))
    monkeypatch.setenv("ALIVE_VALID_DIR", str(tmp_path / "valid"))
    monkeypatch.setattr(ingest_worker, "_aws_ready",
                        lambda: (None, "forced offline"))
    return tmp_path


def _inputs():
    """fetch_inputs-shaped bundle — one model point, no stations."""
    t = time.time()
    return {
        "model": {"status": "ok", "source": "test", "fetched_at": t,
                  "samples": [{"lat": 28.61, "lon": 77.21, "name": "pt",
                               "pm25": 50.0}]},
        "met": {"status": "ok", "source": "test", "fetched_at": t,
                "wind_ms": 3.0, "wind_deg": 300, "blh_m": 400.0,
                "vc_m2s": 1200.0},
        "fires": {"status": "ok", "source": "test", "fetched_at": t,
                  "modifier": 1.0, "n_fires": 0, "belt_fires": 0},
        "stations": {"status": "unavailable: test", "source": "test",
                     "fetched_at": t, "stations": []},
    }


def _field(ts, cells=None, stations=None):
    return {"schema": "alive-airindex/1", "built_at": airindex._iso(ts),
            "built_epoch": ts,
            "grid": {"system": "test", "n_cells": len(cells or {})},
            "provenance": {}, "met": {"vc_m2s": 1200.0},
            "qc": {"stations_used": len(stations or []),
                   "dropped": {"stale": [], "flatline": [], "spike": []},
                   "kriging": "off"},
            "stations": stations or [], "stats": {"mean_sigma": 5.0},
            "cells": cells or {}}


def _seed(root, ts, cells=None, stations=None):
    dt = datetime.fromtimestamp(ts, tz=timezone.utc)
    d = os.path.join(str(root), f"{dt:%Y}", f"{dt:%m}", f"{dt:%d}")
    os.makedirs(d, exist_ok=True)
    p = os.path.join(d, f"{dt:%H%M}.json.gz")
    with open(p, "wb") as f:
        f.write(airindex.serialize(_field(ts, cells, stations)))
    return p


# ------------------------------------------------------------- field_tick

def test_field_tick_writes_snapshot(offline):
    now = time.time()
    out = rollup_lambda.field_tick(now=now, inputs=_inputs())
    assert out["ok"] and out["backend"] == "local"
    assert out["metrics"]["emitted"] is False  # AWS forced offline
    dt = datetime.fromtimestamp(now, tz=timezone.utc)
    p = os.path.join(str(offline), "snaps",
                     f"{dt:%Y}", f"{dt:%m}", f"{dt:%d}", f"{dt:%H%M}.json.gz")
    assert out["snapshot"] == p and os.path.exists(p)
    with open(p, "rb") as fh:
        f = airindex.deserialize(fh.read())
    assert f["stats"]["mean_pm25"] == 50.0


# ------------------------------------------------------------ daily_rollup

def test_daily_rollup_rolls_seed_day(offline):
    day = (datetime.now(timezone.utc) - timedelta(days=1)).strftime(
        "%Y-%m-%d")
    ts1 = datetime.strptime(day, "%Y-%m-%d").replace(
        tzinfo=timezone.utc).timestamp()
    ts2 = ts1 + 3600
    cells = {"cell1": {"pm25": 30.0}, "cell2": {"pm25": 90.0}}
    _seed(offline / "snaps", ts1, cells)
    _seed(offline / "snaps", ts2,
          {"cell1": {"pm25": 50.0}, "cell2": {"pm25": 70.0}})
    out = rollup_lambda.daily_rollup(date=day)
    assert out["n_snapshots"] == 2 and out["backend"] == "local"
    assert out["cells"]["cell1"]["mean"] == 40.0
    assert out["cells"]["cell1"]["max"] == 50.0
    assert out["city"]["median_pm25"] is not None
    assert os.path.exists(out["written_to"])
    saved = json.load(open(out["written_to"]))
    assert saved["schema"] == "alive-rollup/1"


def test_rollup_date_env_override(offline, monkeypatch):
    monkeypatch.setenv("ALIVE_ROLLUP_DATE", "2026-09-01")
    out = rollup_lambda.daily_rollup()
    assert out["date"] == "2026-09-01"
    assert out["n_snapshots"] == 0  # empty day still writes a rollup


def test_last_closed_day_is_utc_yesterday():
    expect = (datetime.now(timezone.utc) - timedelta(days=1)).strftime(
        "%Y-%m-%d")
    assert rollup_lambda._last_closed_day() == expect


# ---------------------------------------------------------- weekly_validate

def test_weekly_validation_loso(offline, monkeypatch):
    stations = [{"name": f"s{i}", "lat": 28.5 + 0.05 * i, "lon": 77.2,
                 "pm25": 50.0, "residual": r}
                for i, r in enumerate((4.0, -2.0, 3.0, -1.0, 2.0))]
    _seed(offline / "snaps", time.time(),
          cells={"cell1": {"pm25": 50.0}}, stations=stations)
    monkeypatch.setattr(validate_field, "validate",
                        lambda hours_back: (None, [
                            ("s", "h", 40.0, 42.0, 0),
                            ("s", "h", 50.0, 48.0, 0)]))
    out = rollup_lambda.weekly_validation(week="2026-W40")
    assert out["week"] == "2026-W40"
    assert out["loso"]["status"] == "ok" and out["loso"]["n"] == 5
    assert out["archive_replay"]["status"] == "ok"
    assert out["archive_replay"]["mae_ugm3"] == 2.0
    assert os.path.exists(out["written_to"])
    saved = json.load(open(out["written_to"]))
    assert saved["schema"] == "alive-validation/1"


# ---------------------------------------------------------------- dispatch

def test_handler_routes_and_400s(offline, monkeypatch):
    monkeypatch.setattr(ingest_worker, "run_index_once",
                        lambda **kw: {"ok": True, "mocked": True})
    r = rollup_lambda.handler({"job": "ingest"})
    assert r["statusCode"] == 200
    assert json.loads(r["body"])["mocked"] is True

    r = rollup_lambda.handler({"job": "bogus"})
    assert r["statusCode"] == 400
    assert "unknown job" in r["body"]

    monkeypatch.setenv("ALIVE_JOB", "rollup")
    monkeypatch.setenv("ALIVE_ROLLUP_DATE", "2026-09-02")
    r = rollup_lambda.handler(None)
    assert r["statusCode"] == 200
    assert json.loads(r["body"])["date"] == "2026-09-02"
