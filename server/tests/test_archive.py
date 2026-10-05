"""Offline tests for server/archive.py + GET /v2/archive — the recorded
field (basis:recorded), never the forecast.

No network, no AWS: a FakeField stands in for airfield.FIELD, tmp_path
is the local archive root, and a FakeS3 exercises the bucket read path.
Run from server/:
    PYTHONPATH=. .venv/bin/python -m pytest tests/test_archive.py -q
"""
import gzip
import io
import json
import os
import sys
import time
from datetime import date, datetime, timedelta

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient  # noqa: E402

import archive as _arch  # noqa: E402
import main  # noqa: E402

client = TestClient(main.app, raise_server_exceptions=False)


def _ts_ist(y, m, d, h, minute=2):
    """Epoch seconds inside IST hour h of day y-m-d."""
    return datetime(y, m, d, h, minute, tzinfo=_arch.IST).timestamp()


class FakeField:
    """Uniform served field — same surface contract airfield.FIELD has:
    value / sigma / nearest_sample_km / status."""
    def __init__(self, mid=100.0, sd=10.0, km=4.0):
        self.mid, self.sd, self.km = mid, sd, km

    def value(self, lat, lon, param="pm2_5"):
        return self.mid if param in ("pm2_5", "pm25") else None

    def sigma(self, lat, lon):
        return self.sd

    def nearest_sample_km(self, lat, lon):
        return self.km

    def status(self):
        return {"serving": "live", "source": "test-stations+cams",
                "samples": 4, "station_readings": 2,
                "stations_src": "waqi", "age_s": 120,
                "kriging": "on", "sigma_coverage": "per-query"}


class EmptyField(FakeField):
    def value(self, lat, lon, param="pm2_5"):
        return None


class FakeS3:
    def __init__(self, objects=None):
        self.objects = dict(objects or {})

    def list_objects_v2(self, Bucket, Prefix, **kw):
        return {"IsTruncated": False,
                "Contents": [{"Key": k} for k in sorted(self.objects)
                             if k.startswith(Prefix)]}

    def get_object(self, Bucket, Key):
        return {"Body": io.BytesIO(self.objects[Key])}

    def put_object(self, Bucket, Key, Body, **kw):
        self.objects[Key] = Body
        return {}


@pytest.fixture(autouse=True)
def clean(monkeypatch, tmp_path):
    monkeypatch.delenv("ALIVE_AIR_BUCKET", raising=False)
    monkeypatch.setenv("ALIVE_ARCHIVE_DIR", str(tmp_path))
    _arch._STATUS_CACHE.update({"at": 0.0, "doc": None})
    _arch._LAST.update({"ok": None, "at": None})
    yield tmp_path


# ------------------------------------------------------------------ capture

def test_capture_writes_real_snapshot(tmp_path):
    now = _ts_ist(2026, 10, 5, 14)
    r = _arch.capture(FakeField(), now=now, root=str(tmp_path))
    assert r["ok"] and r["backend"] == "local"      # bucket unset → local
    assert r["ist_day"] == "2026-10-05" and r["ist_hour"] == 14
    assert r["cells"] == 484                        # the /grid lattice
    p = os.path.join(str(tmp_path), "field-2026100514.json.gz")
    assert os.path.exists(p) and os.path.getsize(p) < 200_000
    doc = json.loads(gzip.decompress(open(p, "rb").read()))
    assert doc["basis"] == "recorded"
    assert doc["ist_day"] == "2026-10-05" and doc["ist_hour"] == 14
    assert doc["cell_fields"] == _arch.CELL_FIELDS
    assert doc["field"]["serving"] == "live"
    assert doc["field"]["station_readings"] == 2
    c = doc["cells"][0]
    lon, lat, mid, lo, hi, conf, band = c
    assert mid == 100.0 and lo == pytest.approx(100 - 1.96 * 10, abs=0.2)
    assert hi == pytest.approx(100 + 1.96 * 10, abs=0.2)
    assert conf == "hi" and band                     # 4 km → hi conf
    # roundtrip through the module's own codec
    assert _arch._deserialize(open(p, "rb").read())["n_cells"] == 484


def test_capture_empty_field_writes_nothing(tmp_path):
    r = _arch.capture(EmptyField(), now=_ts_ist(2026, 10, 5, 9),
                      root=str(tmp_path))
    assert r["ok"] is False and "honest gap" in r["skipped"]
    assert not os.listdir(str(tmp_path))            # no fake record


def test_capture_s3_backend(tmp_path):
    s3 = FakeS3()

    def store(key, blob, local_path, mirror_local=False):
        s3.put_object(Bucket="b", Key=key, Body=blob)
        return f"s3://b/{key}", "s3", None

    r = _arch.capture(FakeField(), now=_ts_ist(2026, 10, 5, 14),
                      root=str(tmp_path), store=store)
    assert r["ok"] and r["backend"] == "s3"
    assert "archive/field-2026100514.json.gz" in s3.objects
    # store never mirrored locally — the bucket is the only copy
    assert not os.listdir(str(tmp_path))


# ------------------------------------------------------------------ day

def _seed(root, day: date, hours, mid=100.0):
    """Write real snapshots via capture() for the given IST hours."""
    for h in hours:
        _arch.capture(FakeField(mid=mid), now=_ts_ist(
            day.year, day.month, day.day, h), root=root)


def test_day_payload_gaps_serialize_honestly(tmp_path):
    day = date(2026, 10, 4)
    _seed(str(tmp_path), day, [9, 11], mid=123.0)
    after = _ts_ist(2026, 10, 6, 10)
    p = _arch.day_payload(day, root=str(tmp_path), now=after)
    assert p["basis"] == "recorded" and p["tz"] == "ist"
    assert p["day"] == "2026-10-04" and len(p["hours"]) == 24
    e9 = p["hours"][9]
    assert e9["status"] == "recorded" and e9["basis"] == "recorded"
    assert e9["n_cells"] == 484 and len(e9["cells"]) == 121  # ::4
    assert e9["cells"][0][2] == 123.0
    assert e9["serving"] == "live" and e9["field_age_s"] == 120
    for h in (0, 8, 10, 12, 23):
        e = p["hours"][h]
        assert e["status"] == "gap" and "no snapshot" in e["note"]
        assert "cells" not in e                       # never invented
    cov = p["coverage"]
    assert cov["recorded"] == [9, 11] and cov["recorded_count"] == 2
    assert cov["gap_count"] == 22 and not cov["pending"]
    assert p["archive"]["total_snapshots"] == 2
    assert p["archive"]["since_ist"].startswith("2026-10-04T09:00")


def test_empty_archive_answers_empty_hours(tmp_path):
    p = _arch.day_payload(date(2026, 10, 4), root=str(tmp_path),
                          now=_ts_ist(2026, 10, 6, 10))
    assert p["hours"] == [] and p["archive"]["total_snapshots"] == 0
    assert p["archive"]["since_ist"] is None


def test_future_hours_are_pending_not_gaps(tmp_path):
    now = _ts_ist(2026, 10, 5, 14)                    # 14:02 IST
    _seed(str(tmp_path), date(2026, 10, 5), [9])
    p = _arch.day_payload(date(2026, 10, 5), root=str(tmp_path),
                          now=now)
    assert p["hours"][9]["status"] == "recorded"
    for h in (10, 13):
        assert p["hours"][h]["status"] == "gap"      # elapsed, missing
    for h in (15, 20, 23):
        assert p["hours"][h]["status"] == "pending"  # not due yet
    assert p["coverage"]["pending"] == [15, 16, 17, 18, 19, 20, 21,
                                        22, 23]


def test_unreadable_snapshot_is_reported_not_hidden(tmp_path):
    p = os.path.join(str(tmp_path), "field-2026100409.json.gz")
    open(p, "wb").write(b"not gzip at all")
    out = _arch.day_payload(date(2026, 10, 4), root=str(tmp_path),
                            now=_ts_ist(2026, 10, 6, 10))
    e = out["hours"][9]
    assert e["status"] == "unreadable" and "failed to read" in e["note"]
    assert out["coverage"]["unreadable"] == [9]


def test_s3_only_snapshot_reads_via_bucket(tmp_path):
    s3 = FakeS3()

    def store(key, blob, local_path, mirror_local=False):
        s3.put_object(Bucket="b", Key=key, Body=blob)
        return f"s3://b/{key}", "s3", None

    _arch.capture(FakeField(mid=200.0), now=_ts_ist(2026, 10, 4, 7),
                  root=str(tmp_path), store=store)
    assert not os.listdir(str(tmp_path))            # s3-only copy
    p = _arch.day_payload(date(2026, 10, 4), root=str(tmp_path),
                          s3=s3, bucket="b", now=_ts_ist(2026, 10, 6, 9))
    e7 = p["hours"][7]
    assert e7["status"] == "recorded" and e7["cells"][0][2] == 200.0
    assert p["archive"]["total_snapshots"] == 1


# ------------------------------------------------------------------ status

def test_status_counts_real_files(tmp_path):
    _seed(str(tmp_path), date(2026, 10, 4), [9, 11])
    today = datetime.now(_arch.IST).date()
    _seed(str(tmp_path), today, [3])
    s = _arch.status(root=str(tmp_path), ttl_s=0)
    assert s["snapshots_total"] == 3
    assert s["since_ist"].startswith("2026-10-04T09:00")
    assert s["today"]["day"] == str(today)
    assert s["today"]["hours_recorded"] == 1
    assert s["last"]["backend"] == "local"


# ------------------------------------------------------------------ loop

def test_sleep_lands_on_ist_hour_boundary():
    # 14:20 IST → next boundary 15:00 IST = 40 min, not the UTC hour
    wait = _arch._sleep_to_next_ist_hour(_ts_ist(2026, 10, 5, 14, 20))
    assert wait == pytest.approx(40 * 60, abs=1)


# ------------------------------------------------------------------ http

def test_endpoint_wire_shape(tmp_path, monkeypatch):
    day = date(2026, 10, 4)
    _seed(str(tmp_path), day, [9], mid=140.0)
    r = client.get("/v2/archive", params={"day": "2026-10-04"})
    assert r.status_code == 200
    b = r.json()
    assert b["basis"] == "recorded" and b["day"] == "2026-10-04"
    e = b["hours"][9]
    assert e["status"] == "recorded" and len(e["cells"]) == 121
    assert e["cell_fields"] == _arch.CELL_FIELDS
    assert b["coverage"]["recorded"] == [9]


def test_endpoint_defaults_to_today_and_validates(tmp_path):
    r = client.get("/v2/archive")
    assert r.status_code == 200
    b = r.json()
    assert b["day"] == str(datetime.now(_arch.IST).date())
    assert client.get("/v2/archive", params={"day": "Oct 5"}) \
        .status_code == 422
    assert client.get("/v2/archive", params={"tz": "utc"}) \
        .status_code == 422


def test_endpoint_empty_archive_is_honest(tmp_path):
    b = client.get("/v2/archive", params={"day": "2026-10-04"}).json()
    assert b["hours"] == [] and b["archive"]["total_snapshots"] == 0
