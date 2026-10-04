"""Station-source chain tests — WAQI → CPCB → OpenAQ ordering and honest
degradation in BOTH live paths:

  * airindex._fetch_stations (15-min air-index worker, sync client)
  * airfield.AirField._grab_stations (serving field refresh, async)

Chain order verified by a Fargate probe inside the prod VPC
(2026-10-04): api.waqi.info is the only live route (reachable, fast);
api.data.gov.in is TCP-refused even from ap-south-1 — CPCB stays in the
chain as a keyed attempt for an India-reachable egress later; OpenAQ is
last (owner's key revoked, path kept for anyone else's).

Every test is offline: fake clients shaped exactly like each upstream's
real response surface (data.gov.in datastore pages, WAQI bounds/feed,
OpenAQ v3 /locations + /latest). Chain semantics under test:

  - WAQI is attempted FIRST when keyed;
  - a feed only wins when status 'ok' AND it yields stations;
  - the winner stamps bundle `source`; losers ride along as
    waqi_status / cpcb_status / openaq_status;
  - all-lost headline = first REAL upstream verdict, so a 'no key'
    placeholder never masks a refused/401 behind it — and with no keys
    at all the CPCB adapter's 'unavailable: no key — owner blocker'
    stands (the owner-facing blocker is the truth to show).
"""
import asyncio
import os
import sys
import time

import httpx
import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(_HERE))          # server/ on sys.path

import airfield                    # noqa: E402
import airindex                    # noqa: E402
import ingest_cpcb                 # noqa: E402
import ingest_waqi                 # noqa: E402

RID = ingest_cpcb.RESOURCE_ID
KEY = "test-key-0000"


def _clear_keys(monkeypatch):
    for k in ("CPCB_API_KEY", "WAQI_API_KEY", "OPENAQ_API_KEY"):
        monkeypatch.delenv(k, raising=False)


class _Resp:
    def __init__(self, payload, status=200):
        self._p = payload
        self.status_code = status

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError(
                f"HTTP {self.status_code}", request=None, response=None)

    def json(self):
        return self._p


def _cpcb_page(records):
    return {"status": "ok", "total": len(records), "count": len(records),
            "limit": "1000", "offset": "0", "records": records}


def _cpcb_rec(station, avg):
    return {"id": "x", "country": "India", "state": "Delhi",
            "city": "Delhi", "station": station,
            "last_update": "03-10-2026 09:00:00", "pollutant_id": "PM2.5",
            "pollutant_min": "30", "pollutant_max": "90",
            "pollutant_avg": avg, "pollutant_unit": "NA"}


# registry-resolvable names from data/delhi_climatology.json.gz
_CPCB_PAGE = _cpcb_page([
    _cpcb_rec("Income Tax Office, Delhi - CPCB", "54"),
    _cpcb_rec("Jawaharlal Nehru Stadium, Delhi - DPCC", "66"),
])


class _ChainClient:
    """One fake client serving every upstream at once — routes by URL
    host (data.gov.in pages by filters[state], waqi.info bounds/feed,
    api.openaq.org locations/latest), records every call so tests can
    assert which legs ran."""

    def __init__(self, cpcb=None, waqi_bounds=None, waqi_feeds=None,
                 oa_locations=None, oa_latest=None):
        self.cpcb = cpcb or {}
        self.waqi_bounds = waqi_bounds
        self.waqi_feeds = waqi_feeds or {}
        self.oa_locations = oa_locations
        self.oa_latest = oa_latest or {}
        self.calls = []

    def get(self, url, params=None, headers=None, timeout=None):
        self.calls.append(url)
        if url.startswith(ingest_cpcb.API_BASE):
            state = (params or {}).get("filters[state]")
            p = self.cpcb.get(state, _cpcb_page([]))
            if isinstance(p, type) and issubclass(p, BaseException):
                raise p("boom")
            return _Resp(p)
        if url.endswith("/map/bounds/"):
            if isinstance(self.waqi_bounds, type) and issubclass(
                    self.waqi_bounds, BaseException):
                raise self.waqi_bounds("boom")
            return _Resp(self.waqi_bounds or {"status": "ok", "data": []})
        if "/feed/@" in url:
            uid = int(url.rsplit("@", 1)[1].rstrip("/"))
            p = self.waqi_feeds.get(uid, {"status": "ok", "data": {}})
            return _Resp(p)
        if url.endswith("/locations"):
            if isinstance(self.oa_locations, type) and issubclass(
                    self.oa_locations, BaseException):
                raise self.oa_locations("boom")
            return _Resp(self.oa_locations or {"results": []})
        if "/latest" in url:
            lid = int(url.rsplit("/locations/", 1)[1].split("/")[0])
            return _Resp(self.oa_latest.get(lid, {"results": []}))
        raise AssertionError(f"unrouted url {url}")


def _waqi_client():
    now = time.time()
    bounds = {"status": "ok", "data": [
        {"uid": 11, "lat": 28.63, "lon": 77.24,
         "station": {"name": "waqi ITO", "geo": [28.63, 77.24]}},
    ]}
    feed = {"status": "ok", "data": {
        "time": {"v": now},
        "iaqi": {"pm25": {"v": 60.0}},
        "station": {"name": "waqi ITO"}}}
    return _ChainClient(waqi_bounds=bounds, waqi_feeds={11: feed})


def _oa_client(value=88.0):
    ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    locs = {"results": [
        {"id": 100, "name": "oa Loc",
         "coordinates": {"latitude": 28.5, "longitude": 77.1},
         "sensors": [{"id": 9000, "parameter": {"id": 2, "name": "pm25"}}]}]}
    latest = {100: {"results": [{"value": value, "sensorsId": 9000,
                                 "datetime": {"utc": ts}}]}}
    return _ChainClient(oa_locations=locs, oa_latest=latest)


def _cpcb_client():
    empty = _cpcb_page([])
    return _ChainClient(cpcb={"Delhi": _CPCB_PAGE, "Haryana": empty,
                              "Uttar_Pradesh": empty, "Rajasthan": empty})


# ------------------------------------------------ airindex._fetch_stations

def test_chain_waqi_first_and_wins(monkeypatch):
    """All keys present, WAQI healthy: WAQI wins and the later feeds are
    never even touched — primary is api.waqi.info."""
    _clear_keys(monkeypatch)
    monkeypatch.setenv("WAQI_API_KEY", KEY)
    monkeypatch.setenv("CPCB_API_KEY", KEY)
    monkeypatch.setenv("OPENAQ_API_KEY", KEY)
    c = _waqi_client()
    out = airindex._fetch_stations(c, sleep=lambda s: None)
    assert out["status"] == "ok"
    assert out["source"] == "waqi"
    assert len(out["stations"]) == 1 and out["n"] == 1
    # the primary won — CPCB + OpenAQ legs never touched the wire
    assert all("waqi.info" in u for u in c.calls)


def test_chain_waqi_first_then_cpcb_then_openaq_order(monkeypatch):
    """Attempt order is exactly WAQI → CPCB → OpenAQ."""
    _clear_keys(monkeypatch)
    monkeypatch.setenv("WAQI_API_KEY", KEY)
    monkeypatch.setenv("CPCB_API_KEY", KEY)
    monkeypatch.setenv("OPENAQ_API_KEY", KEY)
    c = _ChainClient(waqi_bounds=httpx.ConnectError,
                     cpcb={s: httpx.ConnectError for s in
                           ingest_cpcb.STATES},
                     oa_locations=httpx.ConnectError)
    out = airindex._fetch_stations(c, attempts=1, sleep=lambda s: None)
    hosts = [("waqi" if "waqi.info" in u else
              "cpcb" if "data.gov.in" in u else "openaq")
             for u in c.calls]
    # first call of each kind, in order
    firsts = []
    for h in hosts:
        if h not in firsts:
            firsts.append(h)
    assert firsts == ["waqi", "cpcb", "openaq"]
    assert out["status"].startswith("unavailable")


def test_chain_cpcb_wins_when_waqi_fails(monkeypatch):
    """WAQI keyed but refusing; CPCB keyed and serving — CPCB wins and
    OpenAQ never runs."""
    _clear_keys(monkeypatch)
    monkeypatch.setenv("WAQI_API_KEY", KEY)
    monkeypatch.setenv("CPCB_API_KEY", KEY)
    monkeypatch.setenv("OPENAQ_API_KEY", KEY)
    c = _cpcb_client()
    c.waqi_bounds = httpx.ConnectError
    out = airindex._fetch_stations(c, sleep=lambda s: None)
    assert out["status"] == "ok"
    assert out["source"] == "data.gov.in-cpcb"
    assert len(out["stations"]) == 2
    # losing primary's verdict rides along
    assert out["waqi_status"].startswith("unavailable")
    # OpenAQ leg never reached
    assert not any("openaq" in u for u in c.calls)


def test_chain_openaq_last_resort(monkeypatch):
    _clear_keys(monkeypatch)
    monkeypatch.setenv("OPENAQ_API_KEY", KEY)
    c = _oa_client()
    out = airindex._fetch_stations(c, sleep=lambda s: None)
    assert out["status"] == "ok"
    assert out["source"] == "openaq-v3"
    assert out["n"] == 1
    assert out["waqi_status"] == "skipped: no key"
    assert "no key" in out["cpcb_status"]


def test_chain_cpcb_refused_headlines_verbatim(monkeypatch):
    """CPCB keyed but TCP-refused (today's reality), others unkeyed: the
    status names the real failure — 'ConnectError' — and the skipped
    legs stay visible alongside."""
    _clear_keys(monkeypatch)
    monkeypatch.setenv("CPCB_API_KEY", KEY)
    c = _ChainClient(cpcb={
        "Delhi": httpx.ConnectError, "Haryana": httpx.ConnectError,
        "Uttar_Pradesh": httpx.ConnectError,
        "Rajasthan": httpx.ConnectError})
    out = airindex._fetch_stations(c, sleep=lambda s: None)
    assert out["status"].startswith("unavailable:")
    assert "ConnectError" in out["status"]
    assert out["source"] == "data.gov.in-cpcb"
    assert out["stations"] == [] and out["n"] == 0
    assert out["waqi_status"] == "skipped: no key"
    assert out["openaq_status"] == "unavailable: no key"


def test_chain_no_keys_is_owner_blocker_not_silent(monkeypatch):
    _clear_keys(monkeypatch)
    out = airindex._fetch_stations(
        _ChainClient(), sleep=lambda s: None)
    assert out["status"] == "unavailable: no key — owner blocker"
    assert out["stations"] == []
    assert out["waqi_status"] == "skipped: no key"
    assert out["openaq_status"] == "unavailable: no key"


def test_chain_waqi_placeholder_token_is_honest_no_key(monkeypatch):
    """The seeded alive108/waqi secret is '{"api_key":"REPLACE_ME"}' —
    the placeholder must degrade like a missing key (never burn a
    guaranteed-invalid call), and the upstream is never touched."""
    _clear_keys(monkeypatch)
    monkeypatch.setenv("WAQI_API_KEY", "REPLACE_ME")
    c = _waqi_client()
    out = airindex._fetch_stations(c, sleep=lambda s: None)
    assert out["stations"] == []
    assert not any("waqi.info" in u for u in c.calls)


def test_chain_real_verdict_beats_nokey_placeholder(monkeypatch):
    """OpenAQ leg actually raised (route down) while CPCB/WAQI were
    unconfigured: the degraded bundle still names the skipped legs."""
    _clear_keys(monkeypatch)
    monkeypatch.setenv("OPENAQ_API_KEY", KEY)
    c = _ChainClient(oa_locations=httpx.ConnectError)
    out = airindex._fetch_stations(c, sleep=lambda s: None)
    assert out["status"].startswith("unavailable")
    assert "ConnectError" in out["status"]
    assert "no key" in out["cpcb_status"]
    assert out["waqi_status"] == "skipped: no key"


# -------------------------------------------- airfield._grab_stations (async)

class _AsyncOA:
    """Async fake for the OpenAQ leg of _grab_stations."""

    def __init__(self, locations):
        self.locations = locations
        self.calls = []

    async def get(self, url, headers=None, params=None, **kw):
        self.calls.append(url)
        return _Resp(self.locations)


def _afield():
    return airfield.AirField()


def test_grab_stations_waqi_wins_first(monkeypatch):
    _clear_keys(monkeypatch)
    monkeypatch.setenv("WAQI_API_KEY", KEY)
    monkeypatch.setenv("CPCB_API_KEY", KEY)
    f = _afield()

    async def _fake_grab(client, api_key=None, bbox=None):
        return [(28.6, 77.2, "WAQI st", {"pm2_5": 60.0})]
    monkeypatch.setattr(ingest_waqi, "grab_async", _fake_grab)
    rows = asyncio.run(f._grab_stations(object()))
    assert f._stations_src == "waqi"
    assert f._stations_status["waqi"] == "ok"
    # primary won — CPCB/OpenAQ legs never ran
    assert "cpcb" not in f._stations_status
    assert "openaq" not in f._stations_status
    assert len(rows) == 1 and rows[0][3]["pm2_5"] == 60.0


def test_grab_stations_order_is_waqi_cpcb_openaq(monkeypatch):
    """Attempt order in the async chain is exactly WAQI → CPCB → OpenAQ."""
    _clear_keys(monkeypatch)
    monkeypatch.setenv("WAQI_API_KEY", KEY)
    monkeypatch.setenv("CPCB_API_KEY", KEY)
    monkeypatch.setenv("OPENAQ_API_KEY", KEY)
    order = []
    f = _afield()

    async def _waqi_fail(client, api_key=None, bbox=None):
        order.append("waqi")
        return []
    monkeypatch.setattr(ingest_waqi, "grab_async", _waqi_fail)

    def _cpcb_fail(**kw):
        order.append("cpcb")
        return {"status": "unavailable: ConnectError", "stations": []}
    monkeypatch.setattr(ingest_cpcb, "fetch", _cpcb_fail)

    class _OA(object):
        async def get(self, url, headers=None, params=None):
            order.append("openaq")
            return _Resp({"results": []})
    rows = asyncio.run(f._grab_stations(_OA()))
    assert order == ["waqi", "cpcb", "openaq"]
    assert rows == []
    assert f._stations_src is None
    assert f._stations_status["waqi"] == "unavailable"
    assert "ConnectError" in f._stations_status["cpcb"]
    assert f._stations_status["openaq"] == "unavailable"


def test_grab_stations_cpcb_wins_middle_leg(monkeypatch):
    _clear_keys(monkeypatch)
    monkeypatch.setenv("WAQI_API_KEY", KEY)
    monkeypatch.setenv("CPCB_API_KEY", KEY)
    f = _afield()

    async def _waqi_fail(client, api_key=None, bbox=None):
        return []
    monkeypatch.setattr(ingest_waqi, "grab_async", _waqi_fail)
    monkeypatch.setattr(ingest_cpcb, "fetch", lambda **kw: {
        "status": "ok", "source": "data.gov.in-cpcb",
        "stations": [{"lat": 28.63, "lon": 77.24,
                      "name": "ITO", "pm25": 54.0}]})
    rows = asyncio.run(f._grab_stations(object()))
    assert f._stations_src == "cpcb"
    assert f._stations_status["cpcb"] == "ok"
    assert f._stations_status["waqi"] == "unavailable"
    lat, lon, name, vals = rows[0]
    assert (lat, lon, name) == (28.63, 77.24, "ITO")
    assert vals["pm2_5"] == pytest.approx(54.0)


def test_grab_stations_all_dead_statuses_honest(monkeypatch):
    """No keys at all: empty rows, model field stands alone — but every
    leg's verdict is recorded verbatim for FIELD.status()."""
    _clear_keys(monkeypatch)
    f = _afield()
    rows = asyncio.run(f._grab_stations(object()))
    assert rows == []
    assert f._stations_src is None
    assert f._stations_status["waqi"] == "skipped: no key"
    assert "no key" in f._stations_status["cpcb"]
    assert f._stations_status["openaq"] == "skipped: no key"


def test_field_status_surfaces_station_chain(monkeypatch):
    f = _afield()
    f._stations_src = "waqi"
    f._stations_status = {"waqi": "ok", "cpcb": "skipped: no key"}
    st = f.status()
    assert st["stations_src"] == "waqi"
    assert st["stations_status"]["cpcb"] == "skipped: no key"


def test_grab_stations_src_resets_between_refreshes(monkeypatch):
    """A later refresh with no winning feed must not keep claiming the
    last winner — _stations_src is re-derived, not sticky."""
    _clear_keys(monkeypatch)
    monkeypatch.setenv("WAQI_API_KEY", KEY)
    f = _afield()

    state = {"rows": [(28.6, 77.2, "WAQI st", {"pm2_5": 40.0})]}

    async def _grab(client, api_key=None, bbox=None):
        return list(state["rows"])
    monkeypatch.setattr(ingest_waqi, "grab_async", _grab)
    asyncio.run(f._grab_stations(object()))
    assert f._stations_src == "waqi"
    state["rows"] = []
    rows = asyncio.run(f._grab_stations(object()))
    assert rows == [] and f._stations_src is None
    assert f._stations_status["waqi"] == "unavailable"
