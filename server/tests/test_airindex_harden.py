"""Hardening tests for the 15-min air index — fully synthetic, no network.

Covers the r3 contract:
  - per-source retry/backoff: a source that stays down degrades ONLY its
    own contribution; the field still builds and says so in provenance
  - snapshot rotation keeps the newest N files and never deletes the
    snapshot a live field serves from
  - every built field carries sources-used, source-ages, QC reject
    counts and a build duration
  - the worker loop survives throwing iterations with exponential
    backoff and bounded history

Run from server/:   uv run --with 'pytest,h3,boto3,httpx' pytest tests -x -q
"""
import collections
import glob
import json
import os
import sys
import time
from datetime import datetime, timezone

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(_HERE))          # server/ on sys.path

import httpx                                       # noqa: E402
import pytest                                      # noqa: E402

import airindex                                    # noqa: E402
import ingest_worker                               # noqa: E402

NOW = 1_780_000_000.0  # fixed epoch — deterministic ages


def _model_samples():
    """Small synthetic CAMS grid over the NCR bbox, N-S gradient."""
    out = []
    for i in range(8):
        for j in range(6):
            lat = 28.20 + j * 0.14
            lon = 76.80 + i * 0.16
            out.append({"lat": lat, "lon": lon, "name": None,
                        "pm25": 60.0 + 5.0 * j + 1.5 * i})
    return out


def _stations(now, n=24):
    out = []
    k = 0
    for j in range(4):
        for i in range(6):
            if k >= n:
                break
            lat = 28.25 + j * 0.20
            lon = 76.85 + i * 0.20
            v = 80.0 + 8.0 * j + 3.0 * i + (k % 3)
            out.append({"name": f"Stn-{k:02d}", "lat": lat, "lon": lon,
                        "pm25": v, "ts": now - 300,
                        "series": [v - 2, v, v + 1]})
            k += 1
    return out


def _inputs(now=NOW):
    return {
        "model": {"status": "ok", "source": "open-meteo/cams",
                  "fetched_at": now - 45, "samples": _model_samples()},
        "stations": {"status": "ok", "source": "openaq-v3",
                     "fetched_at": now - 120, "stations": _stations(now)},
        "fires": {"status": "ok", "source": "nasa-firms-public-csv",
                  "fetched_at": now - 900, "modifier": 1.0,
                  "n_fires": 4, "belt_fires": 1},
        "met": {"status": "ok", "source": "open-meteo",
                "fetched_at": now - 60, "wind_ms": 2.5, "wind_deg": 315,
                "blh_m": 800.0, "vc_m2s": 2000.0},
    }


class _Resp:
    def __init__(self, payload, status=200):
        self._payload = payload
        self.status_code = status
        self.text = payload if isinstance(payload, str) else json.dumps(payload)

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError(
                f"{self.status_code}", request=None, response=None)

    def json(self):
        return self._payload


class _FlakyClient:
    """Fails `fail_times` gets then serves the CAMS-shaped payload."""
    def __init__(self, fail_times=0):
        self.calls = 0
        self.fail_times = fail_times

    def get(self, url, **kw):
        self.calls += 1
        if self.calls <= self.fail_times:
            raise httpx.ConnectError("simulated upstream flake")
        import airfield
        return _Resp([{"current": {"pm2_5": 55.0}}
                      for _ in airfield._grid_points()])


# ------------------------------------------------------- retry/backoff

def test_retry_recovers_after_flakes():
    client = _FlakyClient(fail_times=2)
    sleeps = []
    out = airindex._fetch_model(client, sleep=sleeps.append)
    assert out["status"] == "ok"
    assert out["attempts"] == 3
    assert len(out["samples"]) > 0
    assert len(sleeps) == 2                    # one backoff between each try
    for s in sleeps:                           # capped exponential + jitter
        assert 0 < s <= airindex.RETRY_CAP_S + airindex.RETRY_JITTER_S


def test_retry_exhaustion_degrades_source_only():
    client = _FlakyClient(fail_times=99)
    out = airindex._fetch_model(client, sleep=lambda s: None)
    assert out["status"].startswith("unavailable")
    assert out["attempts"] == airindex.RETRY_ATTEMPTS["model"]
    assert out["samples"] == []                # empty-bundle shape intact


def test_fires_all_csvs_down_retries_then_degrades():
    class _Dead:
        def get(self, url, **kw):
            raise httpx.ConnectError("firms down")
    out = airindex._fetch_fires(_Dead(), 315, sleep=lambda s: None)
    assert out["status"].startswith("unavailable")
    assert out["attempts"] == airindex.RETRY_ATTEMPTS["fires"]
    assert out["modifier"] == 1.0 and out["n_fires"] == 0


def test_stations_no_key_is_definitive_not_retried(monkeypatch):
    monkeypatch.delenv("OPENAQ_API_KEY", raising=False)
    out = airindex._fetch_stations(object(), sleep=lambda s: None)
    assert "no key" in out["status"]
    assert out["attempts"] == 1                # not an exception -> no retry


# ------------------------------------------------- per-source degrade

def test_monkeypatched_fetcher_cannot_kill_fetch_inputs(monkeypatch):
    """A fetcher that raises straight through still yields a well-formed
    'unavailable' bundle; the other three sources are untouched."""
    monkeypatch.setattr(airindex, "_fetch_model",
                        lambda c: (_ for _ in ()).throw(RuntimeError("x")))
    monkeypatch.setattr(airindex, "_fetch_met",
                        lambda c: {"status": "ok", "source": "open-meteo",
                                   "fetched_at": NOW - 60, "wind_ms": 2.0,
                                   "wind_deg": 300, "blh_m": 700.0,
                                   "vc_m2s": 1400.0})
    monkeypatch.setattr(airindex, "_fetch_fires",
                        lambda c, w: {"status": "ok",
                                      "source": "nasa-firms-public-csv",
                                      "fetched_at": NOW - 900,
                                      "modifier": 1.0, "n_fires": 0,
                                      "belt_fires": 0})
    monkeypatch.setattr(airindex, "_fetch_stations",
                        lambda c: {"status": "ok", "source": "openaq-v3",
                                   "fetched_at": NOW - 120,
                                   "stations": _stations(NOW)})
    inp = airindex.fetch_inputs(now=NOW, client=object())
    assert inp["model"]["status"].startswith("unavailable")
    assert inp["met"]["status"] == "ok"
    assert inp["fires"]["status"] == "ok"
    assert inp["stations"]["status"] == "ok"

    field = airindex.build_field(now=NOW, inputs=inp)
    assert field["grid"]["n_cells"] > 0        # field still built
    prov = field["provenance"]
    assert prov["model"]["status"].startswith("unavailable")
    assert "model" in field["build"]["sources_degraded"]
    assert "model" not in field["build"]["sources_used"]
    for k in ("met", "fires", "stations"):
        assert k in field["build"]["sources_used"]


def test_all_sources_down_still_builds_empty_not_crash():
    dead = {k: {"status": "unavailable: test", "source": "x",
                "fetched_at": NOW - 30, "samples": [], "stations": [],
                "modifier": 1.0, "wind_ms": None} for k in
            ("model", "stations", "fires", "met")}
    field = airindex.build_field(now=NOW, inputs=dead)
    assert field["grid"]["n_cells"] == 0       # nothing invented
    assert sorted(field["build"]["sources_degraded"]) == \
        ["fires", "met", "model", "stations"]
    assert field["build"]["sources_used"] == []


def test_malformed_station_rows_dropped_not_crashing():
    inputs = _inputs()
    inputs["stations"]["stations"] = (
        _stations(NOW)
        + [{"name": "NoPm", "lat": 28.5, "lon": 77.2, "pm25": None,
            "ts": NOW - 60},
           {"name": "NoLoc", "lat": None, "lon": 77.2, "pm25": 90,
            "ts": NOW - 60},
           {"name": "BadPm", "lat": 28.5, "lon": 77.2, "pm25": "abc",
            "ts": NOW - 60}])
    field = airindex.build_field(now=NOW, inputs=inputs)
    d = field["qc"]["dropped"]
    assert "NoPm" in d["malformed"] and "NoLoc" in d["malformed"]
    assert len(d["malformed"]) == 3
    assert field["qc"]["dropped_counts"]["malformed"] == 3
    assert field["qc"]["stations_used"] == 24


# ------------------------------------------------------- provenance

def test_build_metadata_complete():
    field = airindex.build_field(now=NOW, inputs=_inputs())
    b = field["build"]
    assert isinstance(b["duration_ms"], (int, float)) and b["duration_ms"] >= 0
    assert b["inputs"] == "injected"
    assert sorted(b["sources_used"]) == ["fires", "met", "model", "stations"]
    assert b["sources_degraded"] == []
    qc = field["qc"]
    assert qc["dropped_counts"]["flatline"] == \
        len(qc["dropped"]["flatline"])
    assert qc["dropped_total"] == sum(qc["dropped_counts"].values())
    for src, p in field["provenance"].items():
        assert p["status"] == "ok", src
        assert isinstance(p["age_s"], int) and p["age_s"] >= 0
        assert "attempts" in p               # key present even if None
        assert p["source"]


# ------------------------------------------------------- rotation

def _snap(root, day, hhmm):
    p = root / day / f"{hhmm}.json.gz"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(b"gz")
    return str(p)


def test_rotation_keeps_newest_n_and_prunes_dirs(tmp_path):
    paths = []
    for day, hmm in (("2026/06/01", ("0800", "0900", "1000")),
                     ("2026/06/02", ("0800", "0900", "1000"))):
        for h in hmm:
            paths.append(_snap(tmp_path, day, h))
    res = ingest_worker.rotate_snapshots(str(tmp_path), keep=3)
    left = sorted(glob.glob(str(tmp_path / "**" / "*.json.gz"),
                            recursive=True))
    assert res["deleted"] == 3 and res["keep"] == 3
    assert left == sorted(paths)[-3:]
    assert not (tmp_path / "2026/06/01").exists()   # emptied dir pruned


def test_rotation_never_deletes_live_or_protected(tmp_path):
    live = _snap(tmp_path, "2026/06/02", "1000")
    mid = _snap(tmp_path, "2026/06/01", "0900")
    old = _snap(tmp_path, "2026/06/01", "0800")
    # keep=0 would delete everything — but the newest (the file a live
    # field serves) always stays, and an explicitly protected file too
    res = ingest_worker.rotate_snapshots(str(tmp_path), keep=0,
                                         protect=[old])
    assert res["deleted"] == 1
    assert os.path.exists(live) and os.path.exists(old)
    assert not os.path.exists(mid)


def test_run_index_once_reports_gc_and_build(tmp_path, monkeypatch):
    monkeypatch.delenv("ALIVE_AIR_BUCKET", raising=False)
    res = ingest_worker.run_index_once(now=NOW, inputs=_inputs(),
                                       snapshot_root=str(tmp_path))
    assert res["ok"] and res["backend"] == "local"
    assert res["gc"]["keep"] == ingest_worker.SNAPSHOT_KEEP
    assert res["gc"]["deleted"] == 0
    assert isinstance(res["build_ms"], (int, float))
    assert "model" in res["sources_used"]
    assert res["qc_dropped_total"] == sum(res["qc_dropped"].values())


# ------------------------------------------------------- worker loop

def test_worker_survives_throwing_iterations():
    calls = {"n": 0}
    waits = []

    def flaky():
        calls["n"] += 1
        if calls["n"] <= 2:
            raise RuntimeError(f"boom {calls['n']}")
        return {"ok": True, "built_at": "t", "cells": 5, "snapshot": "s"}

    hist = ingest_worker.run_forever(
        interval_s=900, run=flaky, sleep=waits.append, max_iters=4)
    assert calls["n"] == 4
    assert [h["ok"] for h in hist] == [False, False, True, True]
    assert hist[0]["consecutive_failures"] == 1
    assert hist[1]["consecutive_failures"] == 2
    assert "RuntimeError" in hist[0]["error"]
    # exponential backoff between consecutive failures, then cadence
    assert waits[0] >= ingest_worker.FAIL_BACKOFF_BASE_S
    assert waits[1] >= 2 * ingest_worker.FAIL_BACKOFF_BASE_S
    assert waits[2] == 900                     # success -> normal interval


def test_worker_bounded_history_and_callback():
    ring = collections.deque(maxlen=3)
    seen = []
    hist = ingest_worker.run_forever(
        run=lambda: {"ok": True, "cells": 1},
        sleep=lambda s: None, max_iters=5, history=ring,
        on_result=seen.append)
    assert len(hist) == 3                      # deque bound held
    assert len(seen) == 5                      # callback fires per iteration
    assert all(h["ok"] for h in hist)


def test_worker_bad_callback_is_not_fatal():
    def bad(_e):
        raise ValueError("callback exploded")
    hist = ingest_worker.run_forever(
        run=lambda: {"ok": True}, sleep=lambda s: None,
        max_iters=2, on_result=bad)
    assert len(hist) == 2 and all(h["ok"] for h in hist)


# ==================================================================== r5
# Realtime honesty: degraded statuses carry the upstream verdict verbatim
# (HTTP codes for quota/auth), per-source bundles surface
# fetched_at / n / age_s, and a source whose every read failed says so —
# never "ok" with an empty list.

class _OAResp:
    """httpx.Response stand-in whose raise_for_status raises an
    HTTPStatusError carrying a REAL status_code — the r5 contract
    requires the code to survive into the bundle status."""
    def __init__(self, status=200, payload=None):
        self.status_code = status
        self._p = payload if payload is not None else {}
        req = httpx.Request("GET", "https://api.openaq.org/v3/x")
        self._real = httpx.Response(status, request=req)

    def json(self):
        return self._p

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError(
                f"HTTP {self.status_code}", request=self._real.request,
                response=self._real)


class _OAClient:
    """url -> _OAResp map for the airindex OpenAQ path; records calls."""
    def __init__(self, routes):
        self.routes = dict(routes)
        self.calls = []

    def get(self, url, **kw):
        self.calls.append(url)
        entry = self.routes[url]
        if isinstance(entry, type) and issubclass(entry, BaseException):
            raise entry("boom")
        return entry


_OA_LOCS = f"{airindex.OPENAQ_V3}/locations"
_OA_LATEST = {lid: f"{airindex.OPENAQ_V3}/locations/{lid}/latest"
              for lid in (100, 101)}


def _oa_locations(n=2):
    return {"results": [
        {"id": 100 + i, "name": f"Loc-{i}",
         "coordinates": {"latitude": 28.5 + i * 0.1,
                         "longitude": 77.1 + i * 0.1},
         "sensors": [{"id": 9000 + i,
                      "parameter": {"id": 2, "name": "pm25"}}]}
        for i in range(n)]}


def _oa_latest(sensor_id, value=88.0, epoch=None):
    ts = datetime.fromtimestamp(epoch or time.time(), tz=timezone.utc) \
        .strftime("%Y-%m-%dT%H:%M:%SZ")
    return {"results": [{"value": value, "sensorsId": sensor_id,
                         "datetime": {"utc": ts}}]}


def test_openaq_auth_401_status_carries_http_code(monkeypatch):
    """Key configured, API says 401 — the status must name the code,
    not collapse to 'unavailable'/'HTTPStatusError'."""
    monkeypatch.setenv("OPENAQ_API_KEY", "test-key")
    c = _OAClient({_OA_LOCS: _OAResp(401)})
    out = airindex._fetch_stations(c, sleep=lambda s: None)
    assert out["status"].startswith("unavailable")
    assert "401" in out["status"]
    assert out["stations"] == []
    assert out["attempts"] == airindex.RETRY_ATTEMPTS["stations"]
    assert out["n"] == 0


def test_openaq_quota_429_status_carries_http_code(monkeypatch):
    monkeypatch.setenv("OPENAQ_API_KEY", "test-key")
    c = _OAClient({_OA_LOCS: _OAResp(429)})
    out = airindex._fetch_stations(c, sleep=lambda s: None)
    assert "429" in out["status"]
    assert out["status"].startswith("unavailable")


def test_openaq_every_latest_failed_is_unavailable_not_ok(monkeypatch):
    """/locations works but every /latest 401s: the source is DOWN — an
    'ok' bundle with zero stations would be a lie."""
    monkeypatch.setenv("OPENAQ_API_KEY", "test-key")
    c = _OAClient({_OA_LOCS: _OAResp(200, _oa_locations(2)),
                   _OA_LATEST[100]: _OAResp(401),
                   _OA_LATEST[101]: _OAResp(401)})
    out = airindex._fetch_stations(c, sleep=lambda s: None)
    assert out["status"].startswith("unavailable")
    assert "401" in out["status"]
    assert out["stations"] == []


def test_openaq_partial_latest_failure_stays_ok_but_counted(monkeypatch):
    monkeypatch.setenv("OPENAQ_API_KEY", "test-key")
    c = _OAClient({_OA_LOCS: _OAResp(200, _oa_locations(2)),
                   _OA_LATEST[100]: _OAResp(200, _oa_latest(9000)),
                   _OA_LATEST[101]: _OAResp(500)})
    out = airindex._fetch_stations(c, sleep=lambda s: None)
    assert out["status"] == "ok"
    assert len(out["stations"]) == 1
    assert out["n"] == 1
    assert out["n_locations"] == 2
    assert out["locations_failed"] == 1
    assert any("500" in e for e in out["location_errors"])


def test_failed_source_fetched_at_is_last_attempt_not_first(monkeypatch):
    """A degraded bundle's fetched_at stamps the LAST try — an age
    computed from it must not include the retry backoff time."""
    monkeypatch.setenv("OPENAQ_API_KEY", "test-key")
    c = _OAClient({_OA_LOCS: _OAResp(503)})
    before = time.time()
    out = airindex._fetch_stations(c, sleep=lambda s: None)
    assert before - 1 <= out["fetched_at"] <= time.time() + 1


def test_fetch_inputs_bundles_surface_fetched_at_age_and_n(monkeypatch):
    """'model: 48 pts, 42s old' — every bundle carries fetched_at, n and
    age_s so /health can render the line without guessing."""
    monkeypatch.setattr(airindex, "_fetch_met",
                        lambda c: {"status": "ok", "source": "open-meteo",
                                   "fetched_at": NOW - 10, "wind_ms": 2.0,
                                   "wind_deg": 300, "blh_m": 700.0,
                                   "vc_m2s": 1400.0})
    monkeypatch.setattr(airindex, "_fetch_model",
                        lambda c: {"status": "ok",
                                   "source": "open-meteo/cams",
                                   "fetched_at": NOW - 42,
                                   "samples": _model_samples()})
    monkeypatch.setattr(airindex, "_fetch_fires",
                        lambda c, w: {"status": "ok",
                                      "source": "nasa-firms-public-csv",
                                      "fetched_at": NOW - 900,
                                      "modifier": 1.0, "n_fires": 4,
                                      "belt_fires": 1})
    monkeypatch.setattr(airindex, "_fetch_stations",
                        lambda c: {"status": "ok", "source": "openaq-v3",
                                   "fetched_at": NOW - 120,
                                   "stations": _stations(NOW)})
    inp = airindex.fetch_inputs(now=NOW, client=object())
    assert inp["model"]["n"] == len(_model_samples())
    assert inp["model"]["age_s"] == pytest.approx(42.0)
    assert inp["model"]["fetched_at"] == NOW - 42
    assert inp["met"]["n"] == 1 and inp["met"]["age_s"] == pytest.approx(10.0)
    assert inp["fires"]["n"] == 4
    assert inp["fires"]["age_s"] == pytest.approx(900.0)
    assert inp["stations"]["n"] == len(_stations(NOW))
    assert inp["stations"]["age_s"] == pytest.approx(120.0)


def test_fetch_inputs_degraded_bundle_still_carries_age_and_n(monkeypatch):
    """An 'unavailable' bundle is still a well-formed health row:
    fetched_at stamps the last try, n is honestly 0."""
    monkeypatch.setattr(airindex, "_fetch_met",
                        lambda c: {"status": "ok", "source": "open-meteo",
                                   "fetched_at": NOW - 10, "wind_ms": 2.0,
                                   "wind_deg": 300, "blh_m": 700.0,
                                   "vc_m2s": 1400.0})
    monkeypatch.setattr(airindex, "_fetch_model",
                        lambda c: {"status": "ok",
                                   "source": "open-meteo/cams",
                                   "fetched_at": NOW - 42,
                                   "samples": _model_samples()})
    monkeypatch.setattr(airindex, "_fetch_fires",
                        lambda c, w: {"status": "ok",
                                      "source": "nasa-firms-public-csv",
                                      "fetched_at": NOW - 900,
                                      "modifier": 1.0, "n_fires": 0,
                                      "belt_fires": 0})
    monkeypatch.setattr(
        airindex, "_fetch_stations",
        lambda c: (_ for _ in ()).throw(httpx.ConnectError("refused")))
    inp = airindex.fetch_inputs(now=NOW, client=object())
    st = inp["stations"]
    assert st["status"].startswith("unavailable: ConnectError")
    assert st["n"] == 0
    assert st["fetched_at"] is not None
    assert isinstance(st["age_s"], (int, float))


def test_provenance_carries_n_counts():
    field = airindex.build_field(now=NOW, inputs=_inputs())
    prov = field["provenance"]
    assert prov["model"]["n"] == len(_model_samples())
    assert prov["stations"]["n"] == len(_stations(NOW))
    assert prov["fires"]["n"] == 4
    assert prov["met"]["n"] == 1


# ------------------------------------------------ rollup mirror sync

class _FakeS3:
    def __init__(self, objects):
        self._objects = objects          # key -> bytes

    def get_paginator(self, _name):
        objs = self._objects

        class _Pager:
            def paginate(self, Bucket, Prefix):
                hits = [{"Key": k} for k in sorted(objs)
                        if k.startswith(Prefix)]
                yield {"Contents": hits} if hits else {}

        return _Pager()

    def get_object(self, Bucket, Key):
        import io

        class _Body:
            def __init__(self, data):
                self._data = data

            def read(self):
                return self._data

        return {"Body": _Body(self._objects[Key])}


def _fake_b3(objects):
    class _B3:
        def client(self, _svc):
            return _FakeS3(objects)

        class Session:
            @staticmethod
            def get_credentials():
                return object()

    return _B3()


def test_rollup_mirror_pulls_jobs_outputs(tmp_path, monkeypatch):
    objs = {
        "daily/2026-10-03.json": b'{"date":"2026-10-03"}',
        "validation/weekly-2026-W40.json": b'{"week":"2026-W40"}',
        "validation/2026-W40.json": b'{"week":"2026-W40"}',
        "validation/field_validation.md": b"# report\n",
        "field/2026/10/04/1043.json.gz": b'{"cells":{}}',  # not a rollup
        "daily/": b"",                                     # bare prefix
    }
    monkeypatch.setenv("ALIVE_AIR_BUCKET", "bkt")
    monkeypatch.setattr(ingest_worker, "_aws_ready",
                        lambda: (_fake_b3(objs), "ok"))
    res = ingest_worker.sync_rollup_outputs(str(tmp_path))
    assert res["ok"] and not res["skipped"]
    assert sorted(res["downloaded"]) == [
        "daily/2026-10-03.json",
        "validation/2026-W40.json",
        "validation/field_validation.md",
        "validation/weekly-2026-W40.json",
    ]
    assert (tmp_path / "field/daily/2026-10-03.json").exists()
    assert (tmp_path / "field/validation/weekly-2026-W40.json").exists()
    # the admin page checks the report at the DATA root, not under field/
    assert (tmp_path / "field_validation.md").read_text() == "# report\n"
    # snapshot keys under field/ must not be mirrored into rollup dirs
    assert not list((tmp_path / "field/daily").glob("*.gz"))
    # idempotent: second pull downloads nothing (same bytes on disk)
    res2 = ingest_worker.sync_rollup_outputs(str(tmp_path))
    assert res2["ok"] and res2["downloaded"] == []


def test_rollup_mirror_skips_without_aws(tmp_path, monkeypatch):
    monkeypatch.delenv("ALIVE_AIR_BUCKET", raising=False)
    res = ingest_worker.sync_rollup_outputs(str(tmp_path))
    assert not res["ok"] and res["skipped"] == "no ALIVE_AIR_BUCKET"
    monkeypatch.setenv("ALIVE_AIR_BUCKET", "bkt")
    monkeypatch.setattr(ingest_worker, "_aws_ready",
                        lambda: (None, "no credentials"))
    res = ingest_worker.sync_rollup_outputs(str(tmp_path))
    assert not res["ok"] and res["skipped"] == "no credentials"
