"""Unit tests for ingest_openaq — fully synthetic, no network.

A FakeTransport stands in for httpx.Client: canned locations/latest
payloads in OpenAQ v3 shape (meta/results), plus scripted 429s to prove
the rate-limit backoff path. Covers the mission contract: fixture JSON
-> normalized obs, parameter/unit mapping, paging, 429 backoff, and the
absent-key path ("no key — owner blocker").

Run from server/:  python3 -m pytest tests/test_ingest_openaq.py
"""
import json
import os
import sys

import httpx
import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(_HERE))          # server/ on sys.path

import airindex          # noqa: E402  qc_stations consumes our stations[]
import ingest_openaq as io  # noqa: E402

NOW = 1_780_000_000.0          # fixed epoch; readings kept < 3 h old
KEY = "test-key-deadbeef"      # fake — asserted to stay in headers only


def _iso(epoch):
    from datetime import datetime, timezone
    return datetime.fromtimestamp(epoch, tz=timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ")


class FakeResp:
    """Minimal httpx.Response stand-in."""
    def __init__(self, status=200, payload=None, headers=None):
        self.status_code = status
        self._payload = payload if payload is not None else {}
        self.headers = headers or {}

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            req = httpx.Request("GET", "https://api.openaq.org/v3/x")
            raise httpx.HTTPStatusError(
                f"HTTP {self.status_code}", request=req,
                response=httpx.Response(self.status_code, request=req))


class FakeTransport:
    """httpx.Client duck type. `routes` maps url -> FakeResp | callable
    (params)->FakeResp | list popped front-to-back (for 429-then-200)."""
    def __init__(self, routes):
        self.routes = dict(routes)
        self.calls = []

    def get(self, url, headers=None, params=None, timeout=None):
        self.calls.append({"url": url, "params": dict(params or {}),
                           "headers": dict(headers or {})})
        entry = self.routes[url]
        if callable(entry):
            return entry(dict(params or {}))
        if isinstance(entry, list):
            if len(entry) > 1:
                return entry.pop(0)
            return entry[0]
        return entry

    def urls(self, path_suffix):
        return [c["url"] for c in self.calls
                if c["url"].endswith(path_suffix)]


def _sensor(sid, pname, units):
    ids = {"pm10": 1, "pm25": 2, "no2": 7, "o3": 10}
    return {"id": sid, "name": f"{pname} {units}",
            "parameter": {"id": ids.get(pname, 999), "name": pname,
                          "units": units, "displayName": pname.upper()}}


def _loc(lid, name, lat, lon, sensors):
    return {"id": lid, "name": name, "locality": "Delhi",
            "coordinates": {"latitude": lat, "longitude": lon},
            "provider": {"id": 1, "name": "CPCB"}, "sensors": sensors}


def _row(sid, loc_id, value, epoch, lat, lon):
    return {"datetime": {"utc": _iso(epoch), "local": _iso(epoch)},
            "value": value, "sensorsId": sid, "locationsId": loc_id,
            "coordinates": {"latitude": lat, "longitude": lon}}


# --- shared fixtures: 3 locations over 2 pages (meta.limit=2) ----------

LOCS_P1 = {"meta": {"name": "openaq-api", "page": 1, "limit": 2,
                    "found": 3},
           "results": [
               _loc(101, "ITO Delhi", 28.63, 77.24,
                    [_sensor(5001, "pm25", "µg/m³"),
                     _sensor(5002, "pm10", "µg/m³"),
                     _sensor(5003, "no2", "ppm")]),
               _loc(102, "RK Puram", 28.56, 77.18,
                    [_sensor(5004, "pm25", "µg/m³"),
                     _sensor(5005, "o3", "ppm"),
                     {"id": 5006, "name": "co ppm",
                      "parameter": {"id": 8, "name": "co",
                                    "units": "ppm",
                                    "displayName": "CO"}}])]}

LOCS_P2 = {"meta": {"name": "openaq-api", "page": 2, "limit": 2,
                    "found": 3},
           "results": [
               _loc(103, "Anand Vihar", 28.65, 77.31,
                    [_sensor(5007, "pm25", "count"),   # no conversion
                     _sensor(5008, "pm25", "µg/m³")])]}

LATEST = {
    101: {"meta": {"page": 1, "limit": 100, "found": 3},
          "results": [
              _row(5001, 101, 55.0, NOW - 300, 28.63, 77.24),
              _row(5002, 101, 120.0, NOW - 300, 28.63, 77.24),
              _row(5003, 101, 0.020, NOW - 300, 28.63, 77.24)]},
    102: {"meta": {"page": 1, "limit": 100, "found": 2},
          "results": [
              _row(5004, 102, 80.0, NOW - 60, 28.56, 77.18),
              _row(5005, 102, 0.030, NOW - 60, 28.56, 77.18)]},
    103: {"meta": {"page": 1, "limit": 100, "found": 3},
          "results": [
              _row(5007, 103, 300.0, NOW - 60, 28.65, 77.31),
              _row(5008, 103, None, NOW - 60, 28.65, 77.31),
              _row(5008, 103, 92.0, NOW - 200, 28.65, 77.31)]},
}

LOC_URL = f"{io.OPENAQ_V3}/locations"


def _locations_route(params):
    return FakeResp(200, LOCS_P1 if params.get("page") == 1 else LOCS_P2)


def _latest_url(lid):
    return f"{io.OPENAQ_V3}/locations/{lid}/latest"


def _transport(latest_overrides=None):
    routes = {LOC_URL: _locations_route}
    for lid, payload in LATEST.items():
        routes[_latest_url(lid)] = FakeResp(200, payload)
    routes.update(latest_overrides or {})
    return FakeTransport(routes)


# ---------------------------------------------------------------- tests

def test_no_key_status_and_empty_honest(monkeypatch):
    monkeypatch.delenv(io.ENV_KEY, raising=False)
    t = _transport()
    out = io.fetch(client=t, sleep=lambda s: None)
    assert out["status"] == "no key — owner blocker"
    assert out["obs"] == [] and out["stations"] == []
    assert out["skipped"]["unsupported_unit"] == 0
    assert out["requests"] == 0 and t.calls == []   # zero network traffic


def test_fixture_json_to_normalized_obs(monkeypatch):
    monkeypatch.delenv(io.ENV_KEY, raising=False)
    t = _transport()
    out = io.fetch(api_key=KEY, client=t, sleep=lambda s: None)
    assert out["status"] == "ok"
    assert out["requests"] == 5          # 2 location pages + 3 latest
    got = {(o["station_id"], o["parameter"]): o for o in out["obs"]}
    pm25 = got[(101, "pm25")]
    assert pm25["name"] == "ITO Delhi"
    assert pm25["lat"] == 28.63 and pm25["lon"] == 77.24
    assert pm25["value"] == 55.0 and pm25["unit"] == "µg/m³"
    assert pm25["src_unit"] == "µg/m³" and pm25["src_value"] == 55.0
    assert abs(pm25["ts"] - (NOW - 300)) < 2
    assert pm25["sensor_id"] == 5001
    assert got[(101, "pm10")]["value"] == 120.0
    # out-of-scope parameter (co) never appears
    assert all(o["parameter"] in io.PARAMS for o in out["obs"])


def test_unit_mapping_ppm_gases_and_skips(monkeypatch):
    monkeypatch.delenv(io.ENV_KEY, raising=False)
    out = io.fetch(api_key=KEY, client=_transport(), sleep=lambda s: None)
    got = {(o["station_id"], o["parameter"]): o for o in out["obs"]}
    no2, o3 = got[(101, "no2")], got[(102, "o3")]
    assert no2["value"] == pytest.approx(0.020 * 1881.9, abs=0.5)
    assert o3["value"] == pytest.approx(0.030 * 1963.0, abs=0.5)
    # unit conversions per sensor units — direct checks on the helper
    assert io.to_ugm3("pm25", "ug/m3", 10.0) == 10.0
    assert io.to_ugm3("pm10", "mg/m³", 0.5) == 500.0
    assert io.to_ugm3("no2", "ppb", 20.0) == pytest.approx(37.64, abs=0.1)
    assert io.to_ugm3("pm25", "ppm", 1.0) is None   # nonsense for PM
    assert io.to_ugm3("o3", "count", 1.0) is None
    # pm25@103 in "count" units -> skipped + counted; None value -> bad
    assert out["skipped"]["unsupported_unit"] == 1
    assert out["skipped"]["bad_value"] == 1
    assert (103, "pm25") not in [(o["station_id"], o["parameter"])
                                 for o in out["obs"] if
                                 o["sensor_id"] == 5007]
    assert any(o["sensor_id"] == 5008 and o["value"] == 92.0
               for o in out["obs"])   # the good sensor at 103 survives


def test_stations_subset_matches_airindex_schema(monkeypatch):
    monkeypatch.delenv(io.ENV_KEY, raising=False)
    out = io.fetch(api_key=KEY, client=_transport(), sleep=lambda s: None)
    stns = out["stations"]
    assert {s["name"] for s in stns} == {"ITO Delhi", "RK Puram",
                                       "Anand Vihar"}
    for s in stns:
        assert set(s) >= {"lat", "lon", "name", "pm25", "ts"}
        assert isinstance(s["pm25"], float) and s["pm25"] > 0
    survivors, dropped = airindex.qc_stations(stns, None, NOW)
    assert len(survivors) == 3 and not any(dropped.values())


def test_paging_pulls_every_location_page(monkeypatch):
    monkeypatch.delenv(io.ENV_KEY, raising=False)
    t = _transport()
    out = io.fetch(api_key=KEY, client=t, sleep=lambda s: None)
    loc_pages = [c["params"]["page"] for c in t.calls
                 if c["url"] == LOC_URL]
    assert loc_pages == [1, 2]           # meta.found=3, limit=2 -> 2 pages
    assert out["pages"] == 2
    assert {o["station_id"] for o in out["obs"]} == {101, 102, 103}


def test_backoff_on_429_then_success(monkeypatch):
    monkeypatch.delenv(io.ENV_KEY, raising=False)
    reset_hdr = {"x-ratelimit-reset": str(NOW + 30)}
    t = _transport({_latest_url(101): [
        FakeResp(429, {"message": "Too many requests"}, reset_hdr),
        FakeResp(200, LATEST[101])]})
    sleeps = []
    clock = lambda: NOW  # noqa: E731
    out = io.fetch(api_key=KEY, client=t, sleep=sleeps.append,
                   time_func=clock)
    assert out["status"] == "ok"
    assert out["retries_429"] == 1
    assert sleeps == [30.0]              # honored x-ratelimit-reset
    assert len(t.urls("/latest")) == 4   # 101 retried; 102, 103 once
    assert any(o["station_id"] == 101 for o in out["obs"])


def test_persistent_429_skips_location_others_survive(monkeypatch):
    monkeypatch.delenv(io.ENV_KEY, raising=False)
    t = _transport({_latest_url(102): FakeResp(429)})
    sleeps = []
    out = io.fetch(api_key=KEY, client=t, sleep=sleeps.append,
                   time_func=lambda: NOW)
    assert out["status"] == "ok"         # degraded, not fatal
    assert out["locations_rate_limited"] == 1
    assert len(sleeps) == io.MAX_ATTEMPTS - 1   # exponential, no header
    assert not any(o["station_id"] == 102 for o in out["obs"])
    assert any(o["station_id"] == 101 for o in out["obs"])
    for s in sleeps:                     # all within the backoff cap
        assert 0 < s <= io.BACKOFF_MAX_S


def test_429_on_locations_page_degrades_bundle(monkeypatch):
    monkeypatch.delenv(io.ENV_KEY, raising=False)
    t = FakeTransport({LOC_URL: FakeResp(429)})
    out = io.fetch(api_key=KEY, client=t, sleep=lambda s: None,
                   time_func=lambda: NOW)
    assert out["status"] == "unavailable: rate-limited (429)"
    assert out["obs"] == [] and out["stations"] == []
    assert out["requests"] == io.MAX_ATTEMPTS


def test_key_stays_in_headers_never_in_output(monkeypatch):
    monkeypatch.delenv(io.ENV_KEY, raising=False)
    t = _transport()
    out = io.fetch(api_key=KEY, client=t, sleep=lambda s: None)
    assert all(c["headers"].get("X-API-Key") == KEY for c in t.calls)
    assert KEY not in json.dumps(out)    # secret never echoed anywhere


def test_env_key_is_used(monkeypatch):
    monkeypatch.setenv(io.ENV_KEY, KEY)
    t = _transport()
    out = io.fetch(client=t, sleep=lambda s: None)
    assert out["status"] == "ok"
    assert t.calls[0]["headers"]["X-API-Key"] == KEY
