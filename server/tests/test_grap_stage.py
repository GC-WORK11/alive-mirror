"""Offline tests for the GRAP-equivalent surface (lane grap-stage).

Delhi's legal air frame: CAQM's Graded Response Action Plan stages are
declared on Delhi's CPCB national AQI — I 'Poor' 201-300, II 'Very Poor'
301-400, III 'Severe' 401-450, IV 'Severe+' >450 (CAQM 'Comprehensively
revised GRAP Schedule' for NCR, caqm.nic.in). The product computes the
GRAP-EQUIVALENT of the served field — never the official declaration —
through the codebase's one PM2.5->CPCB-AQI formula (districts.cpcb_aqi),
so /v2/day, /v2/city and /aqi's indicative block can't disagree.

No network: deps.field_refresh is a no-op over injected field samples,
FORECAST is seeded with a synthetic CAMS horizon (same seeding style as
test_v2_day).

Run from server/:
    PYTHONPATH=core/build312:. .venv312/bin/python -m pytest \
        tests/test_grap_stage.py -q
"""
import os
import sys
import time
from datetime import datetime, timedelta, timezone

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient  # noqa: E402

import main  # noqa: E402
import districts  # noqa: E402
from airfield import FIELD, grap_indicative  # noqa: E402
from forecast import FORECAST  # noqa: E402
from v2 import deps, store  # noqa: E402

client = TestClient(main.app, raise_server_exceptions=False)

CP = (28.6315, 77.2167)
NOTE = "computed from today's air, not the official CAQM declaration"

SAMPLES = [
    (28.6315, 77.2167, "test-station", {"pm2_5": 150.0}),
    (28.6519, 77.1907, None, {"pm2_5": 185.0}),
    (28.5850, 77.2300, None, {"pm2_5": 120.0}),
    (28.7000, 77.2000, None, {"pm2_5": 210.0}),
]


def _seed_forecast(vals):
    t0 = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0,
                                            microsecond=0)
    times = [(t0 + timedelta(hours=i)).isoformat() for i in range(len(vals))]
    FORECAST._aq = [{"lat": CP[0], "lon": CP[1], "name": None, "t0": t0,
                     "times": times, "vars": {"pm2_5": list(vals)}}]
    FORECAST._met = []
    FORECAST._fetched_at = time.time()


def _clear_field():
    """Honest cold: no live samples AND no snapshot layer — the field
    can only answer None."""
    FIELD._samples = []
    FIELD._snap = None
    FIELD._snap_centers = []
    FIELD._snap_epoch = 0.0


@pytest.fixture(autouse=True)
def wired(monkeypatch):
    FIELD._samples = list(SAMPLES)
    FIELD._fetched_at = time.time()
    FIELD._station_count = 0
    FIELD._source = "test"
    FIELD._snap = None           # snapshot layer off — the seeded samples
    FIELD._snap_centers = []     # are what the field must serve
    FIELD._snap_epoch = 0.0
    _seed_forecast([150.0] * 120)

    async def _noop(*a, **k):
        return None
    monkeypatch.setattr(deps, "field_refresh", _noop)
    monkeypatch.setattr(FIELD, "refresh", _noop)
    monkeypatch.setattr(FORECAST, "refresh", _noop)
    store.TRIPS.reset()
    yield
    _clear_field()
    FORECAST._aq = []
    FORECAST._met = []
    FORECAST._fetched_at = 0.0


# ------------------------------------------------------------- boundaries
def test_stage_boundaries_exact():
    """CAQM edges land on the stage named in the schedule — 200.9->I is
    wrong; the floor is exactly AQI 201."""
    assert districts.grap_stage(0) == 0
    assert districts.grap_stage(50) == 0       # Good — no stage engages
    assert districts.grap_stage(200) == 0      # 'Moderate' tops out below I
    assert districts.grap_stage(201) == 1      # Stage I 'Poor' floor
    assert districts.grap_stage(300) == 1      # Stage I 'Poor' ceiling
    assert districts.grap_stage(301) == 2      # Stage II 'Very Poor'
    assert districts.grap_stage(400) == 2
    assert districts.grap_stage(401) == 3      # Stage III 'Severe'
    assert districts.grap_stage(450) == 3      # Stage III ceiling
    assert districts.grap_stage(451) == 4      # Stage IV 'Severe+'
    assert districts.grap_stage(500) == 4
    assert districts.grap_stage(None) is None  # no aqi -> no stage


def test_block_shape_note_and_formula():
    """The block is the CAQM stage OF the served cpcb aqi — the same
    formula /aqi and the district choropleth use, never a second one."""
    for pm25 in (0.0, 30.0, 90.0, 90.1, 120.0, 120.1, 200.0,
                 250.0, 250.1, 373.7, 400.0, 600.0):
        b = districts.grap_block(pm25, "test basis")
        assert set(b) == {"equivalent_stage", "aqi", "basis", "note"}
        assert b["aqi"] == districts.cpcb_aqi(pm25)
        assert b["equivalent_stage"] == \
            districts.grap_stage(districts.cpcb_aqi(pm25))
        assert b["note"] == NOTE
        assert b["basis"] == "test basis"
    assert districts.grap_block(None, "x") is None


def test_aqi_indicative_shares_the_formula():
    """/aqi's legacy block delegates to the same stage map — the point
    endpoint and the v2 surfaces can never disagree."""
    for pm25 in (0.0, 90.0, 90.1, 120.0, 250.0, 350.0, 373.8, 600.0):
        ind = grap_indicative(pm25)
        assert ind["indicative_stage"] == \
            districts.grap_stage(districts.cpcb_aqi(pm25))
        assert ind["basis_pm25"] == round(pm25, 1)
    assert grap_indicative(None)["indicative_stage"] is None


# ---------------------------------------------------------------- /v2/day
def test_day_grap_present_and_consistent():
    b = client.get("/v2/day", params={"lat": CP[0], "lon": CP[1]}).json()
    assert "error" not in b and b["hours"]
    g = b["grap"]
    assert g["aqi"] == districts.cpcb_aqi(b["day_mean_pm25"])
    assert g["equivalent_stage"] == districts.grap_stage(g["aqi"])
    assert 0 <= g["equivalent_stage"] <= 4
    assert g["note"] == NOTE


def test_day_grap_omitted_on_cold_forecast():
    """No served day -> no stage, not even a null block."""
    FORECAST._aq = []
    b = client.get("/v2/day", params={"lat": CP[0], "lon": CP[1]}).json()
    assert b["error"] == "forecast unavailable"
    assert "grap" not in b


def test_day_grap_omitted_outside_area():
    b = client.get("/v2/day", params={"lat": 51.5, "lon": -0.12}).json()
    assert "outside service area" in b["error"]
    assert "grap" not in b


# --------------------------------------------------------------- /v2/city
def test_city_grap_present_and_consistent():
    b = client.get("/v2/city").json()
    g = b["grap"]
    # the block maps the SAME field summary the hero reads
    assert g["aqi"] == districts.cpcb_aqi(b["pm25_stats"]["mean"])
    assert g["equivalent_stage"] == districts.grap_stage(g["aqi"])
    assert 0 <= g["equivalent_stage"] <= 4
    assert g["note"] == NOTE


def test_city_grap_omitted_on_cold_field():
    """Empty field -> pm25_stats {n:0} -> no grap key at all."""
    _clear_field()
    b = client.get("/v2/city").json()
    assert b["pm25_stats"]["n"] == 0
    assert "grap" not in b


# ------------------------------------------------------------- stage copy
def test_block_below_stage_one_is_real_answer():
    """AQI under 201 maps to stage 0 — honest 'no stage engages', which
    is different information from 'can't compute' (absent key)."""
    b = districts.grap_block(10.0, "test")
    assert b is not None and b["equivalent_stage"] == 0
    assert b["aqi"] == districts.cpcb_aqi(10.0)
