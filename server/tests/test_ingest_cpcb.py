"""Unit tests for the data.gov.in CPCB adapter — no network, recorded
fixtures shaped exactly like the live resource response (field schema
documented in docs/plan/cpcb-source.md and api.data.gov.in metadata).

Run from server/:   uv run --with 'pytest,h3,boto3,httpx' \\
                      pytest tests/test_ingest_cpcb.py -q
"""
import os
import sys

import httpx
import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(_HERE))          # server/ on sys.path

import airindex                    # noqa: E402 - real QC path
import ingest_cpcb                 # noqa: E402

KEY = "test-key-0000"
RID = ingest_cpcb.RESOURCE_ID


def _rec(station, pid, avg, ts="03-10-2026 09:00:00", lo="40", hi="90",
         state="Delhi", city="Delhi"):
    return {"id": "x", "country": "India", "state": state, "city": city,
            "station": station, "last_update": ts, "pollutant_id": pid,
            "pollutant_min": lo, "pollutant_max": hi, "pollutant_avg": avg,
            "pollutant_unit": "NA"}


def _page(records, total=None):
    return {"index_name": RID, "status": "ok", "message": "Resource detail",
            "total": total if total is not None else len(records),
            "count": len(records), "limit": "1000", "offset": "0",
            "records": records}


# Delhi page: the real "Name, City - AGENCY" naming this feed uses.
DELHI = _page([
    _rec("Income Tax Office, Delhi - CPCB", "PM2.5", "54",
         lo="31", hi="88"),                                     # good
    _rec("Income Tax Office, Delhi - CPCB", "PM10", "120",
         lo="80", hi="160"),                                    # folds in
    _rec("IHBAS, Dilshad Garden, Delhi - CPCB", "PM2.5", "41",
         lo="41", hi="41"),                                     # flatline
    _rec("Jawaharlal Nehru Stadium, Delhi - DPCC", "PM2.5", "66",
         ts="01-10-2026 09:00:00", lo="50", hi="70"),           # stale
    _rec("Fictional Test Nagar, Delhi - CPCB", "PM2.5", "60"),  # unresolv.
    _rec("Bad Value Nagar, Delhi - CPCB", "PM2.5", "NA"),       # bad_value
    _rec("Mundka, Delhi - DPCC", "PM2.5", "35",
         ts="not-a-date"),                                      # bad_ts
    _rec("Alipur, Delhi - DPCC", "PM2.5", "9999"),              # out_range
    _rec("CO-Only Nagar, Delhi - CPCB", "CO", "28"),            # no pm25
])
HARYANA = _page([
    _rec("Vikas Sadan, Gurugram - HSPCB", "PM2.5", "72",
         state="Haryana", city="Gurugram"),                     # in bbox
    _rec("Murthal, Sonipat - HSPCB", "PM2.5", "90",
         state="Haryana", city="Sonipat"),                      # out bbox
])
EMPTY = _page([])

NOW = ingest_cpcb._parse_ts("03-10-2026 09:00:00") + 1800  # 09:30 IST


class _Resp:
    def __init__(self, payload):
        self._p = payload
        self.status_code = 200

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("err", request=None, response=None)

    def json(self):
        return self._p


class FakeClient:
    """httpx.Client stand-in: maps filters[state] -> payload. A list of
    payloads means successive pages (one per call for that state); an
    exception class is raised each call."""

    def __init__(self, payloads):
        self.payloads = payloads
        self.calls = []
        self._seen = {}

    def get(self, url, params=None, headers=None, timeout=None):
        self.calls.append({"url": url, "params": dict(params or {})})
        state = (params or {}).get("filters[state]")
        p = self.payloads.get(state, EMPTY)
        if isinstance(p, type) and issubclass(p, BaseException):
            raise p("boom")
        pages = p if isinstance(p, list) else [p]
        i = self._seen.get(state, 0)
        self._seen[state] = i + 1
        return _Resp(pages[min(i, len(pages) - 1)])


def _delhi_client():
    return FakeClient({"Delhi": DELHI, "Haryana": HARYANA,
                       "Uttar_Pradesh": EMPTY, "Rajasthan": EMPTY})


# ------------------------------------------------------------- key handling

def test_no_key_returns_empty_honest(monkeypatch):
    monkeypatch.delenv("CPCB_API_KEY", raising=False)
    c = _delhi_client()
    res = ingest_cpcb.fetch(client=c)
    assert res["status"].startswith("unavailable: no key")
    assert res["stations"] == []
    assert res["source"] == "data.gov.in-cpcb"
    st = ingest_cpcb.status()
    assert st["status"] == "no key — owner blocker"
    assert st["key_present"] is False
    assert st["key_env"] == "CPCB_API_KEY"
    # no key -> never even tried the network
    assert c.calls == []


def test_explicit_key_param(monkeypatch):
    monkeypatch.delenv("CPCB_API_KEY", raising=False)
    res = ingest_cpcb.fetch(api_key=KEY, client=_delhi_client())
    assert res["status"] == "ok"


# ------------------------------------------------------------- parsing

def test_fixture_parses_to_station_obs_schema(monkeypatch):
    monkeypatch.setenv("CPCB_API_KEY", KEY)
    res = ingest_cpcb.fetch(client=_delhi_client())
    assert res["status"] == "ok"
    stns = {s["raw_station"]: s for s in res["stations"]}
    ito = stns["Income Tax Office, Delhi - CPCB"]
    # airindex qc_stations schema: name/lat/lon/pm25/ts/series
    for k in ("name", "lat", "lon", "pm25", "ts", "series"):
        assert k in ito
    assert ito["pm25"] == 54.0
    assert ito["lat"] == pytest.approx(28.6235, abs=1e-4)
    assert ito["lon"] == pytest.approx(77.2494, abs=1e-4)
    assert ito["name"] == "Income Tax Office, Delhi - CPCB-103"  # registry
    assert ito["series"] == [31.0, 54.0, 88.0]
    # PM10 row folded into the same station's pollutant map, not a 2nd obs
    assert ito["pollutants"]["PM10"] == 120.0
    assert sum(1 for s in res["stations"]
               if s["raw_station"].startswith("Income Tax")) == 1
    # IST timestamp: 09:00 IST = 03:30 UTC
    assert ito["ts"] == pytest.approx(
        ingest_cpcb._parse_ts("03-10-2026 09:00:00"))
    # Vikas Sadan Gurugram resolved + inside bbox
    vs = stns["Vikas Sadan, Gurugram - HSPCB"]
    assert vs["lat"] == pytest.approx(28.4501238, abs=1e-4)


def test_malformed_rows_skipped_and_counted(monkeypatch):
    monkeypatch.setenv("CPCB_API_KEY", KEY)
    res = ingest_cpcb.fetch(client=_delhi_client())
    rep = res["report"]
    sk = rep["skipped"]
    assert rep["rows_in"] == 11            # 9 Delhi + 2 Haryana
    assert rep["stations_out"] == 6        # + Murthal, clipped below
    assert len(res["stations"]) == 5       # ITO,IHBAS,JNS,Mundka,VikasSadan
    assert sk["bad_value"] == 1            # "NA" avg
    assert sk["out_of_range"] == 1         # 9999 µg/m³
    assert sk["bad_ts"] == 1               # "not-a-date"
    assert sk["unresolved_coords"] == 1    # Fictional Test Nagar
    assert rep["unresolved_names"] == ["Fictional Test Nagar, Delhi - CPCB"]
    assert rep["outside_bbox"] == 1        # Murthal, Sonipat (29.02 N)
    # stations that survived still carry honest fields
    by_raw = {s["raw_station"]: s for s in res["stations"]}
    assert by_raw["Mundka, Delhi - DPCC"]["ts"] is None  # kept; QC-stales
    assert "Alipur, Delhi - DPCC" not in by_raw          # out of range
    assert "CO-Only Nagar, Delhi - CPCB" not in by_raw   # no PM2.5 row


def test_fetch_params_hit_data_gov_surface(monkeypatch):
    monkeypatch.setenv("CPCB_API_KEY", KEY)
    c = _delhi_client()
    ingest_cpcb.fetch(client=c)
    states = {call["params"]["filters[state]"] for call in c.calls}
    assert states == set(ingest_cpcb.STATES)
    for call in c.calls:
        assert call["url"] == f"{ingest_cpcb.API_BASE}/resource/{RID}"
        assert call["params"]["api-key"] == KEY
        assert call["params"]["filters[pollutant_id]"] == "PM2.5"


# ------------------------------------------------------------- QC seam

def test_output_feeds_airindex_qc(monkeypatch):
    monkeypatch.setenv("CPCB_API_KEY", KEY)
    res = ingest_cpcb.fetch(client=_delhi_client())
    survivors, dropped = airindex.qc_stations(res["stations"], None, NOW)
    names = {s["name"] for s in survivors}
    assert dropped["flatline"] == ["IHBAS, Dilshad Garden, Delhi - CPCB-6359"]
    assert "Jawaharlal Nehru Stadium, Delhi - DPCC-5754" in dropped["stale"]
    assert "Mundka, Delhi - DPCC-10486" in dropped["stale"]   # ts None
    assert names == {"Income Tax Office, Delhi - CPCB-103",
                     "Vikas Sadan, Gurugram - HSPCB-301"}


# ------------------------------------------------------------- failures

def test_upstream_error_marks_unavailable(monkeypatch):
    monkeypatch.setenv("CPCB_API_KEY", KEY)
    c = FakeClient({"Delhi": httpx.ConnectError,
                    "Haryana": httpx.ConnectError,
                    "Uttar_Pradesh": httpx.ConnectError,
                    "Rajasthan": httpx.ConnectError})
    res = ingest_cpcb.fetch(client=c)
    assert res["status"].startswith("unavailable:")
    assert res["stations"] == []


def test_api_level_failure_marks_unavailable(monkeypatch):
    monkeypatch.setenv("CPCB_API_KEY", KEY)
    bad = {"status": "failed", "message": "invalid api-key"}
    c = FakeClient({"Delhi": bad, "Haryana": bad,
                    "Uttar_Pradesh": bad, "Rajasthan": bad})
    res = ingest_cpcb.fetch(client=c)
    assert res["status"].startswith("unavailable:")
    assert res["stations"] == []


def test_pagination_follows_total(monkeypatch):
    monkeypatch.setenv("CPCB_API_KEY", KEY)
    r1 = _rec("Income Tax Office, Delhi - CPCB", "PM2.5", "54")
    r2 = _rec("IHBAS, Dilshad Garden, Delhi - CPCB", "PM2.5", "41")
    r3 = _rec("Jawaharlal Nehru Stadium, Delhi - DPCC", "PM2.5", "66",
              ts="03-10-2026 08:00:00")
    p1 = _page([r1, r2], total=3)
    p1["count"] = 2
    p2 = _page([r3], total=3)
    p2["count"] = 1
    c = FakeClient({"Delhi": [p1, p2], "Haryana": EMPTY,
                    "Uttar_Pradesh": EMPTY, "Rajasthan": EMPTY})
    res = ingest_cpcb.fetch(client=c, limit=2)
    assert res["status"] == "ok"
    assert res["report"]["pages"] >= 2
    assert res["report"]["rows_in"] == 3
    assert res["report"]["stations_out"] == 3


def test_status_after_fetch(monkeypatch):
    monkeypatch.setenv("CPCB_API_KEY", KEY)
    st = ingest_cpcb.status()
    assert st["key_present"] is True
    ingest_cpcb.fetch(client=_delhi_client())
    st = ingest_cpcb.status()
    assert st["status"] == "ok"
    assert st["last_fetch"]["n_stations"] == 5
