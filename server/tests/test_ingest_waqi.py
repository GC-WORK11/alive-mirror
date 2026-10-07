"""Unit tests for ingest_waqi + its wiring as the stations fallback —
fully synthetic, no network.

Covers: bounds->feed normalization into airindex's stations schema, the
in-body 'error' status path (Invalid key / Over quota), per-station feed
failures counted not hidden, all-failed -> unavailable verbatim, the
no-key owner blocker, and the airindex OpenAQ->WAQI chain.

Run from server/:  python3 -m pytest tests/test_ingest_waqi.py
"""
import os
import sys

import httpx
import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(_HERE))          # server/ on sys.path

import airindex  # noqa: E402
import ingest_waqi as iw  # noqa: E402

NOW = 1_780_000_000.0
KEY = "waqi-test-key"


class FakeResp:
    def __init__(self, status=200, payload=None):
        self.status_code = status
        self._payload = payload if payload is not None else {}

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            req = httpx.Request("GET", "https://api.waqi.info/x")
            raise httpx.HTTPStatusError(
                f"HTTP {self.status_code}", request=req,
                response=httpx.Response(self.status_code, request=req))


class FakeTransport:
    def __init__(self, routes):
        self.routes = dict(routes)
        self.calls = []

    def get(self, url, headers=None, params=None, timeout=None):
        self.calls.append({"url": url, "params": dict(params or {})})
        entry = self.routes[url]
        if callable(entry):
            return entry(dict(params or {}))
        if isinstance(entry, list):
            if len(entry) > 1:
                return entry.pop(0)
            return entry[0]
        return entry


BOUNDS = f"{iw.WAQI}/map/bounds/"


def _bounds_payload(uids):
    return {"status": "ok", "data": [
        {"lat": 28.63 + u, "lon": 77.21 + u, "uid": u,
         "aqi": str(150 + u),
         "station": {"name": f"Station-{u}", "time": "x",
                     "geo": [28.63 + u, 77.21 + u]}}
        for u in uids]}


def _feed_payload(name, pm25, ts_v=NOW - 60, extra=None):
    """`pm25` here is the WAQI Individual-AQI sub-index, NOT µg/m³ —
    iaqi.pm25.v on a real feed. The ingest must invert it to µg/m³."""
    iaqi = {"pm25": {"v": pm25}, "pm10": {"v": pm25 * 1.4}}
    if extra:
        iaqi.update(extra)
    return {"status": "ok", "data": {
        "aqi": 160, "time": {"s": "2026-10-03 07:00:00",
                             "tz": "+05:30", "v": ts_v},
        "city": {"name": "Delhi"}, "iaqi": iaqi,
        "station": {"name": name}}}


def _client(n_feeds=3, feed_map=None):
    routes = {BOUNDS: FakeResp(200, _bounds_payload(range(n_feeds)))}
    for u in range(n_feeds):
        url = f"{iw.WAQI}/feed/@{u}/"
        if feed_map and u in feed_map:
            routes[url] = feed_map[u]
        else:
            routes[url] = FakeResp(
                200, _feed_payload(f"Station-{u}", 80.0 + u))
    return FakeTransport(routes)


def test_fetch_normalizes_to_stations_schema():
    c = _client(3)
    out = iw.fetch(api_key=KEY, client=c, sleep=lambda s: None)
    assert out["status"] == "ok" and out["source"] == "waqi"
    assert len(out["stations"]) == 3
    row = out["stations"][0]
    assert set(row) >= {"lat", "lon", "name", "pm25", "ts", "station_id"}
    assert row["pm25"] > 0 and isinstance(row["ts"], float)
    # qc_stations must accept the shape it was designed for — it returns
    # (survivors, dropped_report); every fresh row survives.
    survivors, dropped = airindex.qc_stations(out["stations"], now=NOW)
    assert len(survivors) == 3
    assert all(not v for v in dropped.values())
    # token rode the query params, nowhere else
    assert all(c2["params"].get("token") == KEY for c2 in c.calls)


def test_no_key_is_owner_blocker(monkeypatch):
    # api_key=None falls through to $WAQI_API_KEY — a developer .env or
    # exported shell key would turn the 'no key' path into a real call
    # (and the fake client would answer 'ok'). Clear the env so the
    # owner-blocker branch is what runs.
    monkeypatch.delenv("WAQI_API_KEY", raising=False)
    out = iw.fetch(api_key=None, client=_client(1))
    assert out["status"] == "no key — owner blocker"
    assert out["stations"] == []


def test_inbody_error_status_surfaces_verbatim():
    c = FakeTransport({BOUNDS: FakeResp(
        200, {"status": "error", "data": "Invalid key"})})
    out = iw.fetch(api_key=KEY, client=c, sleep=lambda s: None)
    assert out["status"].startswith("unavailable:")
    assert "Invalid key" in out["status"]


def test_partial_feed_failure_counted_not_hidden():
    c = _client(3, feed_map={
        1: FakeResp(500, {})})
    out = iw.fetch(api_key=KEY, client=c, sleep=lambda s: None)
    assert out["status"] == "ok"
    assert out["skipped"]["http_error"] == 1
    assert out["feeds_failed"] == 1 and out["feed_errors"]
    assert len(out["stations"]) == 2


def test_all_feeds_failed_is_unavailable_not_zero_stations():
    c = _client(2, feed_map={
        0: FakeResp(500, {}), 1: FakeResp(500, {})})
    out = iw.fetch(api_key=KEY, client=c, sleep=lambda s: None)
    assert out["status"].startswith("unavailable:")
    assert "all 2 station feeds failed" in out["status"]
    assert out["stations"] == []


def test_station_without_pm25_counted_and_skipped():
    no_pm = FakeResp(200, {"status": "ok", "data": {
        "aqi": 40, "time": {"v": NOW - 60},
        "iaqi": {"o3": {"v": 88}}, "station": {"name": "O3-only"}}})
    c = _client(2, feed_map={1: no_pm})
    out = iw.fetch(api_key=KEY, client=c, sleep=lambda s: None)
    assert out["status"] == "ok"
    assert out["skipped"]["no_pm25"] == 1
    assert len(out["stations"]) == 1


def test_429_retry_then_succeed():
    sleeps = []
    c = FakeTransport({
        BOUNDS: [FakeResp(429, {}), FakeResp(200, _bounds_payload([0]))],
        f"{iw.WAQI}/feed/@0/": FakeResp(200, _feed_payload("S0", 42.0)),
    })
    out = iw.fetch(api_key=KEY, client=c, sleep=sleeps.append)
    assert out["status"] == "ok"
    assert out["retries_429"] == 1 and sleeps


# --- airindex chain: waqi primary --------------------------------------
def test_airindex_falls_back_to_waqi(monkeypatch):
    monkeypatch.setenv("WAQI_API_KEY", KEY)
    monkeypatch.delenv("CPCB_API_KEY", raising=False)
    monkeypatch.delenv("OPENAQ_API_KEY", raising=False)
    c = _client(2)
    bundle = airindex._fetch_stations(c, attempts=1, sleep=lambda s: None)
    assert bundle["status"] == "ok" and bundle["source"] == "waqi"
    # WAQI is the primary now — winning on leg 1 means the CPCB/OpenAQ
    # legs never ran, so they carry no status at all
    assert "cpcb_status" not in bundle
    assert "openaq_status" not in bundle
    assert len(bundle["stations"]) == 2


def test_airindex_no_keys_headlines_primary_blocker(monkeypatch):
    monkeypatch.delenv("CPCB_API_KEY", raising=False)
    monkeypatch.delenv("WAQI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAQ_API_KEY", raising=False)
    bundle = airindex._fetch_stations(
        _client(1), attempts=1, sleep=lambda s: None)
    assert bundle["source"] == "data.gov.in-cpcb"
    assert bundle["status"] == "unavailable: no key — owner blocker"
    # the skipped tails are still named alongside
    assert bundle["waqi_status"] == "skipped: no key"
    assert bundle["openaq_status"] == "unavailable: no key"


# --- grab_async (airfield path) -------------------------------------------
class AsyncFake:
    def __init__(self, routes):
        self.routes = dict(routes)

    async def get(self, url, headers=None, params=None, **kw):
        entry = self.routes[url]
        if isinstance(entry, list):
            if len(entry) > 1:
                return entry.pop(0)
            return entry[0]
        return entry


def test_grab_async_rows_shape(monkeypatch):
    monkeypatch.setenv("WAQI_API_KEY", KEY)
    c = AsyncFake({
        BOUNDS: FakeResp(200, _bounds_payload([0, 1])),
        f"{iw.WAQI}/feed/@0/": FakeResp(200, _feed_payload("S0", 61.5)),
        f"{iw.WAQI}/feed/@1/": FakeResp(200, _feed_payload("S1", 72.0)),
    })
    import asyncio
    rows = asyncio.run(iw.grab_async(c))
    assert len(rows) == 2
    lat, lon, name, vals = rows[0]
    assert vals["pm2_5"] > 0 and isinstance(name, str) and lat and lon


def test_grab_async_no_key_returns_empty(monkeypatch):
    monkeypatch.delenv("WAQI_API_KEY", raising=False)
    import asyncio
    assert asyncio.run(iw.grab_async(AsyncFake({}))) == []


# --- iaqi -> µg/m³ conversion (the 2026-10-04 unit bug) -------------------
# WAQI /feed iaqi.<p>.v is each pollutant's US-EPA Individual AQI
# sub-index — verified on a live Delhi feed where iaqi.pm25.v equalled the
# station's composite aqi (uid 10117: 154/154) and iaqi.co ~2-6 (µg/m³ CO
# would be ~3 orders low). Serving the index as µg/m³ inflated every
# blended station ~2-3x.

def test_iaqi_pm25_inversion_matches_epa_table():
    # US-EPA PM2.5 breakpoints: 35.5-55.4 µg/m³ <-> IAQI 101-150,
    # 55.5-150.4 <-> 151-200 — the two bands Delhi lives in.
    assert iw.iaqi_to_ugm3("pm25", 101) == pytest.approx(35.5, abs=0.05)
    assert iw.iaqi_to_ugm3("pm25", 150) == pytest.approx(55.4, abs=0.05)
    assert iw.iaqi_to_ugm3("pm25", 154) == pytest.approx(61.31, abs=0.05)
    assert iw.iaqi_to_ugm3("pm25", 0) == pytest.approx(0.0)
    assert iw.iaqi_to_ugm3("pm25", 500) == pytest.approx(500.4, abs=0.05)
    # past the table the top-band slope continues (never clamped silent)
    assert iw.iaqi_to_ugm3("pm25", 560) > 500.4


def test_iaqi_other_species_convert_with_units():
    # gas tables are ppb/ppm -> µg/m³ at 25 °C; sanity vs real Delhi
    # orders of magnitude (CAMS o3 ~160, co ~290, no2 ~6, so2 ~14 same day)
    assert 100 < iw.iaqi_to_ugm3("o3", 88) < 200        # 88 -> ~130 µg/m³
    assert 150 < iw.iaqi_to_ugm3("co", 2.3) < 400       # -> ~232 µg/m³
    assert 10 < iw.iaqi_to_ugm3("no2", 7.9) < 40        # -> ~16 µg/m³
    assert 5 < iw.iaqi_to_ugm3("so2", 6.8) < 30         # -> ~12 µg/m³
    assert iw.iaqi_to_ugm3("pm10", 134) == pytest.approx(221.67, abs=0.05)


def test_iaqi_bad_values_rejected():
    assert iw.iaqi_to_ugm3("pm25", -1) is None
    assert iw.iaqi_to_ugm3("pm25", "x") is None
    assert iw.iaqi_to_ugm3("pm25", float("nan")) is None


# --- us_aqi_sub_index (µg/m³ -> EPA sub-index, the inverse table) ----------

def test_us_aqi_sub_index_round_trips_iaqi_inversion():
    # every band edge must map back to its own index — the two functions
    # share one breakpoint table, so this is a consistency invariant, not
    # a tautology.
    for idx in (25, 75, 120, 160, 210, 260, 330):
        ugm3 = iw.iaqi_to_ugm3("pm25", idx)
        assert iw.us_aqi_sub_index("pm25", ugm3) == pytest.approx(idx, abs=0.6)
    # pm10 and gases ride their own bands + unit factors
    assert iw.us_aqi_sub_index("pm10", 120.0) == pytest.approx(
        51 + (120 - 55.0) / (154.0 - 55.0) * 49, rel=1e-3)
    o3_sub = iw.us_aqi_sub_index("o3", iw.iaqi_to_ugm3("o3", 88))
    assert o3_sub == pytest.approx(88, abs=0.6)


def test_us_aqi_sub_index_guards():
    assert iw.us_aqi_sub_index("pm25", -3) is None
    assert iw.us_aqi_sub_index("pm25", "x") is None
    assert iw.us_aqi_sub_index("pm25", float("nan")) is None
    assert iw.us_aqi_sub_index("plutonium", 10.0) is None
    # beyond the last band the top slope continues — never clamps low
    assert iw.us_aqi_sub_index("pm25", 700.0) > 500


def test_grab_async_emits_all_measured_params(monkeypatch):
    """A station's pm10/o3/no2 must reach the field — pm2_5-only emission
    left the coarse fraction raw-CAMS (public pm10 ~120 vs ours ~400)."""
    monkeypatch.setenv("WAQI_API_KEY", KEY)
    payload = _feed_payload("S0", 61.5)
    payload["data"]["iaqi"]["pm10"] = {"v": 134}
    payload["data"]["iaqi"]["no2"] = {"v": 7.9}
    c = AsyncFake({
        BOUNDS: FakeResp(200, _bounds_payload([0])),
        f"{iw.WAQI}/feed/@0/": FakeResp(200, payload),
    })
    import asyncio
    rows = asyncio.run(iw.grab_async(c))
    assert len(rows) == 1
    vals = rows[0][3]
    assert vals["pm2_5"] == pytest.approx(
        iw.iaqi_to_ugm3("pm25", 61.5), abs=0.1)
    assert vals["pm10"] == pytest.approx(iw.iaqi_to_ugm3("pm10", 134), abs=0.1)
    assert vals["nitrogen_dioxide"] == pytest.approx(
        iw.iaqi_to_ugm3("no2", 7.9), abs=0.1)
    assert iw.iaqi_to_ugm3("pm25", iw.IAQI_MAX + 1) is None
    assert iw.iaqi_to_ugm3("unlisted", 100) is None


def test_station_pm25_is_ugm3_not_iaqi():
    # the exact regression: IAQI 154 must land as ~61 µg/m³, not 154
    c = _client(1, feed_map={
        0: FakeResp(200, _feed_payload("Rohini-like", 154.0))})
    out = iw.fetch(api_key=KEY, client=c, sleep=lambda s: None)
    assert out["status"] == "ok"
    pm25 = out["stations"][0]["pm25"]
    assert pm25 == pytest.approx(61.31, abs=0.05)
    # obs keeps the raw index for provenance
    pm_obs = [o for o in out["obs"] if o["parameter"] == "pm25"][0]
    assert pm_obs["src_value"] == 154.0
    assert pm_obs["src_unit"] == "iaqi-us-epa"
    assert pm_obs["value"] == pytest.approx(61.31, abs=0.05)


def test_grab_async_rows_are_ugm3(monkeypatch):
    monkeypatch.setenv("WAQI_API_KEY", KEY)
    c = AsyncFake({
        BOUNDS: FakeResp(200, _bounds_payload([0])),
        f"{iw.WAQI}/feed/@0/": FakeResp(200, _feed_payload("S0", 154.0)),
    })
    import asyncio
    rows = asyncio.run(iw.grab_async(c))
    assert rows[0][3]["pm2_5"] == pytest.approx(61.3, abs=0.15)
