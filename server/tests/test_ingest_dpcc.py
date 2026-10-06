"""Unit tests for ingest_dpcc — fully synthetic except the three real
DPCC page fixtures under tests/fixtures/ (captured 2026-10-06, pinned
here so page churn can't flake the suite; a live-shape drift shows up
as fixture mismatch in review, not a red suite).

Covers: page parser (PM values are raw µg/m³ with unit tokens — NOT
index), gas/CO unit handling, staleness rejection (the months-dead
Supersite page), blank-cell handling, pm25>pm10 physical guard, flag
gating (ALIVE_DPCC_INGEST default off -> no fetch at all), the 15-min
fetch cache, unresolved coords counting, and grab_async's row shape.

Run from server/:  python3 -m pytest tests/test_ingest_dpcc.py
"""
import os
import sys

import httpx
import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(_HERE))          # server/ on sys.path

import ingest_dpcc as dp  # noqa: E402

FIX = os.path.join(_HERE, "fixtures")
NOW = 1_791_303_200.0          # ~2026-10-06 16:50 UTC (21:20-ish IST)


def _fixture(name):
    with open(os.path.join(FIX, name)) as f:
        return f.read()


VIVEK = "dpcc_vivek_vihar_live.html"     # pm25=69.0 pm10=226.0 @21:40 IST
ALIPUR = "dpcc_alipur_blank_pm.html"     # instrument flapping (3.0/3.0)
SUPER = "dpcc_supersite_stale.html"      # stuck at March 2025 -> all stale


def _mini_index(*pairs):
    """pairs: (b64, label); label must match dp.STATIONS keys for coords."""
    return "\n".join(
        f"<a href='AallStationView5MinData.php?stName={b}', "
        f"'../images/tree-active.png','{l}']" for b, l in pairs)


class FakeResp:
    def __init__(self, status=200, text=""):
        self.status_code = status
        self.text = text

    def raise_for_status(self):
        if self.status_code >= 400:
            req = httpx.Request("GET", "https://x/")
            raise httpx.HTTPStatusError(
                f"HTTP {self.status_code}", request=req,
                response=httpx.Response(self.status_code, request=req))


class FakeClient:
    def __init__(self, routes):
        self.routes = dict(routes)
        self.calls = []

    def get(self, url, params=None, timeout=None):
        self.calls.append(url)
        v = self.routes.get(url, FakeResp(404, "<html>404</html>"))
        if isinstance(v, Exception):
            raise v
        return v

    def close(self):
        pass


class FakeAsyncClient:
    def __init__(self, routes):
        self.routes = dict(routes)
        self.calls = []

    async def get(self, url, params=None, timeout=None):
        self.calls.append(url)
        v = self.routes.get(url, FakeResp(404, "<html>404</html>"))
        if isinstance(v, Exception):
            raise v
        return v


@pytest.fixture(autouse=True)
def _clean(monkeypatch):
    dp._reset_cache()
    monkeypatch.delenv("ALIVE_DPCC_INGEST", raising=False)
    yield
    dp._reset_cache()


# ---------- parser ----------


def test_parser_reads_raw_ugm3_not_index():
    r = dp.parse_station_page(_fixture(VIVEK), now=NOW)
    assert r["vals"]["pm25"][0] == pytest.approx(69.0)
    assert r["vals"]["pm10"][0] == pytest.approx(226.0)
    # units are µg/m3 in the page — a raw concentration, not an IAQI
    assert r["vals"]["pm25"][1] == "µg/m3"
    # gases ride along: no2/so2/o3 µg/m³, co mg/m³ -> µg/m³
    assert r["vals"]["no2"][0] == pytest.approx(31.0)
    assert r["vals"]["co"][0] == pytest.approx(500.0)   # 0.5 mg/m³ * 1000
    # row timestamp is the page's own IST stamp
    assert r["ts"] == pytest.approx(1_791_303_000.0)


def test_parser_stale_station_drops_everything():
    r = dp.parse_station_page(_fixture(SUPER), now=NOW)
    assert r["vals"] == {}
    assert r["ts"] is None
    assert r["skipped"]["stale"] >= 4    # pm25+pm10+gases all stale


def test_parser_blank_cells_do_not_crash():
    r = dp.parse_station_page(_fixture(ALIPUR), now=NOW)
    # whatever the page currently shows parses without exception; the
    # only requirement is a dict of unit-checked values
    assert isinstance(r["vals"], dict)
    for k, (v, unit, _s) in r["vals"].items():
        assert unit in ("µg/m3", "mg/m3")
        assert v >= 0


def test_parser_unit_mismatch_rejects():
    html = """<table><tr><td>Particulate Matter < 2.5 &micro;g</td>
    <td>Tuesday, October 06, 2026</td><td>21:40:00</td>
    <td>69.0 AQI</td><td>60 µg/m3</td></tr></table>"""
    r = dp.parse_station_page(html, now=NOW)
    assert "pm25" not in r["vals"]
    assert r["skipped"]["unit_mismatch"] == 1


def test_parser_pm25_gt_pm10_dropped():
    html = """<table>
    <tr><td>Particulate Matter < 2.5 &micro;g</td><td>Tuesday, October 06,
    2026</td><td>21:40:00</td><td>300.0 &micro;g/m3</td></tr>
    <tr><td>Particulate Matter < 10 &micro;g</td><td>Tuesday, October 06,
    2026</td><td>21:40:00</td><td>100.0 &micro;g/m3</td></tr></table>"""
    r = dp.parse_station_page(html, now=NOW)
    assert "pm25" not in r["vals"] and r["vals"]["pm10"][0] == 100.0
    assert r["skipped"]["bad_value"] == 1


def test_parser_bad_ts_counts():
    html = """<table><tr><td>Particulate Matter < 2.5 &micro;g</td>
    <td>garbage</td><td>zz</td><td>69.0 &micro;g/m3</td></tr></table>"""
    r = dp.parse_station_page(html, now=NOW)
    assert r["skipped"]["bad_ts"] == 1 and "pm25" not in r["vals"]


# ---------- link discovery ----------


def test_station_links_tree():
    idx = ("<a href='AallStationView5MinData.php?stName=QUJD', "
           "'../images/tree-active.png','Alipur']"
           "<a href='AallStationView5MinData.php?stName=REVG', "
           "'../images/tree-active.png','Wazirpur']")
    links = dp.station_links(idx)
    assert links == [("QUJD", "Alipur"), ("REVG", "Wazirpur")]


def test_nav_links_find_tree_omitted_stations():
    page = _fixture(VIVEK)
    nav = dp.nav_links(page)
    b64s = {b for b, _l in nav}
    # nav includes the nav-only stations the index tree omits
    for label in ("IGNOU", "JNU", "SBV Delhi Cantt",
                  "SPM-SPC Talkatora Garden", "NSUT(West Campus)",
                  "CWG Sports Complex,Akshardham"):
        assert any(l == label for _b, l in nav), label
    assert len(nav) >= 30


# ---------- coords ----------


def test_static_map_covers_index_labels():
    # every label seen live on 2026-10-06 must resolve with coords
    for label in ("Vivek Vihar", "Mundka", "IGNOU", "JNU",
                  "CWG Sports Complex,Akshardham", "NSUT(West Campus)",
                  "SPM-SPC Talkatora Garden", "SBV Delhi Cantt"):
        assert dp._resolve(label, {}) is not None, label


def test_unknown_label_unresolved_not_guessed():
    assert dp._resolve("Totally Invented Nagar", {}) is None


# ---------- fetch() end to end (fake transport) ----------


def _routes(vivek_b64="Vml2ZWtWaWhhcg=="):
    return {
        dp.INDEX: FakeResp(200, _mini_index((vivek_b64, "Vivek Vihar"))),
        dp.PAGE.format(vivek_b64): FakeResp(200, _fixture(VIVEK)),
    }


def test_flag_off_disables_and_fetches_nothing(monkeypatch):
    c = FakeClient(_routes())
    out = dp.fetch(client=c, now=NOW)
    assert out["status"] == "disabled"
    assert c.calls == []


def test_fetch_ok_shape(monkeypatch):
    monkeypatch.setenv("ALIVE_DPCC_INGEST", "1")
    c = FakeClient(_routes())
    out = dp.fetch(client=c, now=NOW)
    assert out["status"] == "ok"
    st = out["stations"]
    assert len(st) == 1
    s = st[0]
    assert s["pm25"] == pytest.approx(69.0)
    assert s["lat"] == pytest.approx(28.6723)
    obs = {o["parameter"]: o for o in out["obs"]}
    assert obs["pm25"]["unit"] == "µg/m³"
    assert obs["pm25"]["src_unit"] == "µg/m3"
    assert obs["pm25"]["value"] == pytest.approx(69.0)


def test_fetch_caches_15min(monkeypatch):
    monkeypatch.setenv("ALIVE_DPCC_INGEST", "1")
    c = FakeClient(_routes())
    out1 = dp.fetch(client=c, now=NOW)
    calls1 = len(c.calls)
    out2 = dp.fetch(client=c, now=NOW + 60)      # inside TTL
    assert out2 is out1 and len(c.calls) == calls1
    dp._cache["at"] = 0.0                         # force expiry
    out3 = dp.fetch(client=c, now=NOW + 1000)
    assert out3 is not out1 and len(c.calls) > calls1


def test_fetch_index_down_unavailable(monkeypatch):
    monkeypatch.setenv("ALIVE_DPCC_INGEST", "1")
    c = FakeClient({dp.INDEX: httpx.ConnectError("refused")})
    out = dp.fetch(client=c, now=NOW)
    assert out["status"].startswith("unavailable:")
    assert out["stations"] == []


def test_fetch_all_stale_unavailable(monkeypatch):
    monkeypatch.setenv("ALIVE_DPCC_INGEST", "1")
    b64 = "U3VwZXJzaXRl"
    c = FakeClient({dp.INDEX: FakeResp(200, _mini_index((b64, "Supersite(Rouse Avenue)"))),
                    dp.PAGE.format(b64): FakeResp(200, _fixture(SUPER))})
    out = dp.fetch(client=c, now=NOW)
    assert out["status"].startswith("unavailable:")
    assert out["skipped"]["stale"] > 0


# ---------- grab_async ----------


def test_grab_async_flag_off(monkeypatch):
    import asyncio
    c = FakeAsyncClient(_routes())
    rows = asyncio.run(dp.grab_async(c))
    assert rows == [] and c.calls == []


def test_grab_async_rows(monkeypatch):
    import asyncio
    monkeypatch.setenv("ALIVE_DPCC_INGEST", "1")
    c = FakeAsyncClient(_routes())
    rows = asyncio.run(dp.grab_async(c, now=NOW))
    assert len(rows) == 1
    lat, lon, name, vals = rows[0]
    assert (lat, lon) == pytest.approx((28.6723, 77.3153), abs=1e-3)
    assert name == "Vivek Vihar"
    assert vals["pm2_5"] == pytest.approx(69.0)
    assert vals["pm10"] == pytest.approx(226.0)
    assert "nitrogen_dioxide" in vals


def test_grab_async_failure_returns_empty(monkeypatch):
    import asyncio
    monkeypatch.setenv("ALIVE_DPCC_INGEST", "1")
    c = FakeAsyncClient({dp.INDEX: httpx.ConnectError("refused")})
    assert asyncio.run(dp.grab_async(c)) == []
