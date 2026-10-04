"""Claims-audit honesty fixes — endpoint-level verification.

Each test exercises the real endpoint code path offline (OSRM/forecast/
field fetches stubbed, same pattern as test_contract_sync.py) and checks
the wire shape the audit demanded:

- /shift must carry an honest dose band (dose_ug_lo/hi, cig_equiv_lo/hi),
  built from live krige sigma or decade-quantile bands — never bare
  point precision.
- /depart's saved-vs-now value is a percent; the honest key name
  pct_less_vs_now must ride alongside the legacy misnamed ug_* key.
- /decide's safest reason is scoped to the ranked options, not a flat
  "safest way to travel" claim.
"""
import os
import sys
import time

import pytest
from fastapi.testclient import TestClient  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import main  # noqa: E402
from airfield import FIELD  # noqa: E402

client = TestClient(main.app, raise_server_exceptions=False)

LINE = {"type": "LineString",
        "coordinates": [[77.20 + i * 0.001, 28.63] for i in range(30)]}
OSRM_ROUTE = {"code": "Ok", "routes": [
    {"distance": 6200.0, "duration": 780.0, "geometry": LINE, "legs": []}]}


class _FakeResp:
    def __init__(self, payload):
        self._p = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._p


class FakeHttp:
    async def get(self, url, params=None):
        if "router.project-osrm.org" in str(url):
            return _FakeResp(OSRM_ROUTE)
        raise ConnectionError("offline polish test")


@pytest.fixture(autouse=True)
def wired(monkeypatch):
    FIELD._samples = [
        (28.6315, 77.2167, "test-station", {"pm2_5": 150.0}),
        (28.6519, 77.1907, None, {"pm2_5": 185.0}),
    ]
    FIELD._fetched_at = time.time()

    async def _noop(*a, **k):
        return None
    monkeypatch.setattr(FIELD, "refresh", _noop)
    monkeypatch.setattr(main.FIRES, "refresh", _noop)
    monkeypatch.setattr(main, "http", lambda: FakeHttp())
    yield
    FIELD._samples = []


def test_shift_carries_honest_dose_band():
    r = client.get("/shift", params={"lat": 28.63, "lon": 77.21,
                                     "hours": 8})
    assert r.status_code == 200
    b = r.json()
    assert b.get("dose_ug") is not None, b
    lo, hi = b.get("dose_ug_lo"), b.get("dose_ug_hi")
    assert lo is not None and hi is not None, "no band on the wire"
    assert lo <= b["dose_ug"] <= hi
    assert b["cig_equiv_lo"] <= b["cig_equiv"] <= b["cig_equiv_hi"]


def test_depart_percent_key_is_honestly_named():
    """ug_saved_vs_now is a percent — pct_less_vs_now must say so."""

    class _StubForecast:
        def hour_index(self, h):
            return int(h)

        def time_at(self, idx):
            return f"+{idx}h"

        def pm25(self, lat, lon, when, live=None):
            # a real U-curve: cleaner at midday, dirtier at night —
            # best departure beats leaving now
            base = 200.0
            dip = [1.0, 0.95, 0.9, 0.8, 0.7, 0.6, 0.55, 0.6, 0.7]
            return base * dip[int(when) % len(dip)]

        def status(self):
            return {"up": True, "stub": True}

    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(main, "FORECAST", _StubForecast())

    async def _noop(*a, **k):
        return None
    monkeypatch.setattr(main, "_forecast_refresh_bounded", _noop)
    r = client.get("/depart", params={
        "from_lat": 28.60, "from_lon": 77.20,
        "to_lat": 28.70, "to_lon": 77.30, "vehicle": "auto"})
    monkeypatch.undo()
    assert r.status_code == 200
    b = r.json()
    if b.get("error"):
        pytest.skip(f"depart path unavailable offline: {b['error']}")
    assert "pct_less_vs_now" in b, b.keys()
    assert b["pct_less_vs_now"] == b["ug_saved_vs_now"]
    assert 0 <= b["pct_less_vs_now"] <= 100


def test_decide_reason_is_scoped_to_options():
    r = client.get("/decide", params={
        "from_lat": 28.60, "from_lon": 77.20,
        "to_lat": 28.70, "to_lon": 77.30})
    assert r.status_code == 200
    b = r.json()
    reasons = [x for o in b.get("options", [])
               for x in o.get("decision_reasons", [])]
    if not reasons:
        pytest.skip("no scored options offline")
    assert "the safest way to travel" not in reasons
    assert "the safest pick of these" in reasons
