"""Offline tests for GET /v2/why — the 'why is it like this' lane.

No network: field refresh is a no-op, fires/forecast/snapshot inputs are
stubbed straight onto the singletons and a tmp snapshot root. Run from
server/:
    PYTHONPATH=core/build312:. .venv312/bin/python -m pytest -q tests/test_v2_why.py
"""
import gzip
import json
import os
import sys
import time

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient  # noqa: E402

import main  # noqa: E402
from v2 import deps  # noqa: E402
from v2 import why as v2why  # noqa: E402

client = TestClient(main.app)

NOW = time.time()


def _snap(path, built_epoch, mean_pm25, vc=None, belt=None, mod=None):
    doc = {
        "schema": "alive-field/1",
        "built_epoch": built_epoch,
        "built_at": "2026-10-05T00:00:00+00:00",
        "cells": {"g8:28.6:77.2": {"pm25": mean_pm25}},
        "stats": {"mean_pm25": mean_pm25},
        "met": {"vc_m2s": vc, "blh_m": 700.0, "wind_ms": 2.0,
                "wind_deg": 300.0},
        "provenance": {
            "met": {"vc_m2s": vc, "blh_m": 700.0, "wind_ms": 2.0,
                    "wind_deg": 300.0},
            "fires": {"n_fires": belt, "belt_fires": belt,
                      "modifier": mod},
            "stations": {"n_used": 12, "n_raw": 14},
        },
    }
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as fh:
        fh.write(gzip.compress(json.dumps(doc).encode()))


@pytest.fixture()
def snap_root(tmp_path, monkeypatch):
    root = tmp_path / "snaps"
    root.mkdir()
    monkeypatch.setenv("ALIVE_SNAPSHOT_DIR", str(root))
    return str(root)


def _write_series(root, specs):
    """specs: [(hours_ago, mean_pm25, vc_m2s, belt_fires, modifier)]"""
    for h_ago, pm, vc, belt, mod in specs:
        t = NOW - h_ago * 3600
        import datetime as _dt
        d = _dt.datetime.fromtimestamp(t, tz=_dt.timezone.utc)
        _snap(os.path.join(root, f"{d:%Y/%m/%d/%H%M}.json.gz"),
              t, pm, vc=vc, belt=belt, mod=mod)


class _NoFires:
    """fires feed with nothing to say."""
    _status = "cold"
    _fires = None
    _wind_deg = None
    _fetched_at = 0.0

    def status(self):
        return {"status": "cold", "source": None, "fires": 0,
                "belt_fires": 0, "belt_frp_mw": 0.0,
                "wind_deg": None, "modifier": 1.0, "age_s": None}


class _Fires:
    def __init__(self, belt=61, frp=412.3, modifier=1.8):
        self._status = "live"
        self._wind_deg = 315.0
        self._fetched_at = NOW - 900
        self._fires = [{"lat": 30.1, "lon": 75.5, "frp": frp, "belt": True}
                       for _ in range(belt)]
        self._modifier = modifier

    def status(self):
        return {"status": "live", "source": "firms-public-csv",
                "fires": 120, "belt_fires": len(self._fires),
                "belt_frp_mw": round(sum(f["frp"] for f in self._fires), 1),
                "wind_deg": self._wind_deg, "modifier": self._modifier,
                "age_s": 900}


@pytest.fixture(autouse=True)
def quiet(monkeypatch):
    """No upstream contact inside the endpoint."""
    async def _no_field():
        return None

    async def _no_fires():
        return None
    monkeypatch.setattr(deps, "field_refresh", _no_field)
    monkeypatch.setattr(v2why, "_refresh_fires_bounded", _no_fires)


@pytest.fixture()
def wind_nw(monkeypatch):
    """Field wind blowing FROM the burn belt (NW quadrant)."""
    class F:
        def wind(self):
            return {"speed_kmh": 9.0, "from_deg": 315.0}
        def _wind_expired(self):
            return False
    monkeypatch.setattr(deps, "field", lambda: F())


@pytest.fixture()
def wind_se(monkeypatch):
    """Wind FROM the south-east — smoke cannot reach Delhi."""
    class F:
        def wind(self):
            return {"speed_kmh": 9.0, "from_deg": 150.0}
        def _wind_expired(self):
            return False
    monkeypatch.setattr(deps, "field", lambda: F())


@pytest.fixture()
def wind_calm(monkeypatch):
    class F:
        def wind(self):
            return {"speed_kmh": 1.5, "from_deg": 315.0}
        def _wind_expired(self):
            return False
    monkeypatch.setattr(deps, "field", lambda: F())


@pytest.fixture()
def wind_unknown(monkeypatch):
    class F:
        def wind(self):
            return {"speed_kmh": 0.0, "from_deg": 0.0}
        def _wind_expired(self):
            return True
    monkeypatch.setattr(deps, "field", lambda: F())


@pytest.fixture(autouse=True)
def no_snapshot_prov(monkeypatch):
    """Keep health._field_probe honest-empty unless a test opts in."""
    import health as _h
    monkeypatch.setattr(_h, "_field_probe",
                        lambda *a, **k: {"payload": {}, "age_s": None})


@pytest.fixture()
def cold_forecast(monkeypatch):
    class FC:
        _met = []
        _aq = []
        _fetched_at = 0.0

        def hour_index(self, h):
            return None

        def stagnation_detail(self, lat, lon, idx):
            return None
    import forecast
    monkeypatch.setattr(forecast, "FORECAST", FC())
    monkeypatch.setattr(v2why, "_ventilation_read",
                        v2why._ventilation_read)  # keep real fn
    return FC()


# ------------------------------------------------------------------- gates

def test_carry_gate_quadrant():
    assert v2why._carries_toward_delhi(315.0, 9.0) is True   # NW
    assert v2why._carries_toward_delhi(270.0, 9.0) is True   # W edge
    assert v2why._carries_toward_delhi(360.0, 9.0) is True   # N edge
    assert v2why._carries_toward_delhi(150.0, 9.0) is False  # SE
    assert v2why._carries_toward_delhi(200.0, 9.0) is False  # S


def test_carry_gate_speed_floor_and_unknown():
    assert v2why._carries_toward_delhi(315.0, 1.0) is False  # too calm
    assert v2why._carries_toward_delhi(None, 9.0) is None    # can't judge
    assert v2why._carries_toward_delhi(315.0, None) is True  # dir only


def test_stagnation_threshold():
    vent = {"vc_m2s": 4000.0, "blh_m": 1500, "wind_ms": 2.7,
            "factor": 0.75, "source": "forecast", "age_s": 300}
    d, ev, ct = v2why._eval_stagnation(vent)
    assert d is None and ct is None          # mixing fine — not a driver
    vent2 = {"vc_m2s": 1500.0, "blh_m": 500, "wind_ms": 3.0,
             "factor": 2.0, "source": "forecast", "age_s": 300}
    d2, ev2, ct2 = v2why._eval_stagnation(vent2)
    assert d2 and d2["kind"] == "stagnation" and ct2 is None
    assert 0 < d2["score"] <= 1


def test_stagnation_missing_is_honest():
    d, ev, ct = v2why._eval_stagnation({"vc_m2s": None})
    assert d is None and ct and ct["kind"] == "stagnation"


def test_fires_below_bar_not_claimed(wind_nw):
    d, ev, ct = v2why._eval_fires(
        _Fires(belt=4).status() | {"belt_frp_mw": 10.0},
        {"speed_kmh": 9.0, "from_deg": 315.0})
    assert d is None and ct is None          # 4 fires = background


def test_fires_wrong_wind_not_claimed(wind_se):
    d, ev, ct = v2why._eval_fires(
        _Fires(belt=80).status(),
        {"speed_kmh": 9.0, "from_deg": 150.0})
    assert d is None and ct is None
    assert ev["carrying"] is False


def test_fires_unknown_wind_cannot_tell(wind_nw):
    d, ev, ct = v2why._eval_fires(
        _Fires(belt=80).status(),
        {"speed_kmh": None, "from_deg": None})
    assert d is None and ct and ct["kind"] == "stubble_smoke"
    assert ev["carrying"] is None


def test_fires_cold_feed_cannot_tell():
    d, ev, ct = v2why._eval_fires(_NoFires().status(),
                                  {"speed_kmh": 9.0, "from_deg": 315.0})
    assert d is None and ct and ct["kind"] == "stubble_smoke"


def test_fires_admitted_when_carrying(wind_nw):
    d, ev, ct = v2why._eval_fires(
        _Fires(belt=61, frp=7.0).status(),
        {"speed_kmh": 9.0, "from_deg": 315.0})
    assert d and d["kind"] == "stubble_smoke"
    assert "61 fires" in d["evidence"] and "NW" in d["evidence"]
    assert ev["carrying"] is True


# ------------------------------------------------------------------- trend

def test_trend_rising(snap_root):
    _write_series(snap_root, [(5.0, 60, 3000, 20, 1.1),
                            (4.0, 65, 3000, 20, 1.1),
                            (3.0, 80, 2800, 25, 1.2),
                            (1.0, 130, 2000, 40, 1.5),
                            (0.5, 140, 1800, 45, 1.6)])
    series = v2why._snapshot_series()
    d, ev, ct = v2why._eval_trend(series)
    assert d and d["kind"] == "trend" and d["direction"] == "rising"
    assert ev["delta_ug"] >= v2why.TREND_MIN_DELTA_UG


def test_trend_flat_not_claimed(snap_root):
    _write_series(snap_root, [(5.0, 100, 3000, 20, 1.1),
                            (3.0, 102, 3000, 20, 1.1),
                            (1.0, 104, 3000, 20, 1.1),
                            (0.5, 101, 3000, 20, 1.1)])
    d, ev, ct = v2why._eval_trend(v2why._snapshot_series())
    assert d is None and ct is None


def test_trend_too_few_cannot_tell(snap_root):
    _write_series(snap_root, [(2.0, 100, 3000, 5, 1.0),
                            (0.5, 130, 3000, 5, 1.0)])
    d, ev, ct = v2why._eval_trend(v2why._snapshot_series())
    assert d is None and ct and ct["kind"] == "trend"


def test_trend_stale_newest_cannot_tell(snap_root):
    _write_series(snap_root, [(5.5, 60, 3000, 5, 1.0),
                            (4.5, 65, 3000, 5, 1.0),
                            (3.8, 120, 3000, 5, 1.0),
                            (3.5, 130, 3000, 5, 1.0)])
    # 4 builds inside the window but newest 3.5h old — beyond SNAP_MAX_AGE_S
    d, ev, ct = v2why._eval_trend(v2why._snapshot_series())
    assert d is None and ct and "old" in ct["reason"]


def test_series_s3_fallback_merges_and_dedupes(snap_root, monkeypatch):
    """Production path: local dir thin -> bucket rows fill the window,
    deduped by build time. The bucket is stubbed, not contacted."""
    _write_series(snap_root, [(1.0, 70, 3000, 5, 1.0)])
    s3_rows = [{"t": NOW - 5.0 * 3600, "pm25": 60, "vc_m2s": 3000,
                "blh_m": None, "belt_fires": 5, "modifier": 1.0},
               {"t": NOW - 4.0 * 3600, "pm25": 62, "vc_m2s": 3000,
                "blh_m": None, "belt_fires": 5, "modifier": 1.0},
               {"t": NOW - 1.0 * 3600, "pm25": 999, "vc_m2s": 3000,
                "blh_m": None, "belt_fires": 5, "modifier": 1.0}]  # dup
    monkeypatch.setattr(v2why, "_s3_series", lambda w: s3_rows)
    v2why._SERIES_CACHE.update({"at": 0.0, "key": None, "rows": []})
    rows = v2why._snapshot_series()
    assert len(rows) == 3            # local row + 2 unique bucket rows
    assert rows[-1]["pm25"] == 70    # local newest wins over the dup key


# ---------------------------------------------------------------- endpoint

def test_endpoint_honest_empty(snap_root, wind_se, cold_forecast,
                               monkeypatch):
    """Nothing observable -> local background, drivers []."""
    import fires
    monkeypatch.setattr(fires, "FIRES", _NoFires())
    r = client.get("/v2/why?lat=28.63&lon=77.22")
    assert r.status_code == 200
    body = r.json()
    assert body["drivers"] == []
    assert body["line"] == "local background — no single driver stands out"
    assert any(c["kind"] == "stubble_smoke" for c in body["cannot_tell"])
    assert body["history"] is None


def test_endpoint_smoke_primary(snap_root, wind_nw, cold_forecast,
                                monkeypatch):
    import fires
    monkeypatch.setattr(fires, "FIRES", _Fires(belt=61, frp=6.5))
    _write_series(snap_root, [(5.0, 60, 3000, 20, 1.1),
                            (3.0, 80, 2800, 25, 1.2),
                            (1.0, 130, 2000, 40, 1.5),
                            (0.5, 140, 1800, 45, 1.6)])
    r = client.get("/v2/why")
    assert r.status_code == 200
    body = r.json()
    kinds = [d["kind"] for d in body["drivers"]]
    assert "stubble_smoke" in kinds
    assert body["drivers"][0]["weight"] == "primary"
    for d in body["drivers"]:
        assert d["evidence"] and d["score"] > 0
    assert body["history"]["points"]  # 4 builds spanning >3h
    assert "north-west" in body["line"]


def test_endpoint_wind_blocked(snap_root, wind_se, cold_forecast,
                               monkeypatch):
    """Fires burning but SE wind — no smoke claim (the live tonight)."""
    import fires
    monkeypatch.setattr(fires, "FIRES", _Fires(belt=80, frp=5.0))
    r = client.get("/v2/why")
    body = r.json()
    assert all(d["kind"] != "stubble_smoke" for d in body["drivers"])
    assert body["evaluated"]["fires"]["carrying"] is False


def test_endpoint_shape_keys(snap_root, wind_se, cold_forecast,
                             monkeypatch):
    import fires
    monkeypatch.setattr(fires, "FIRES", _NoFires())
    body = client.get("/v2/why").json()
    for k in ("generated_at", "lat", "lon", "scope", "line", "drivers",
              "evaluated", "cannot_tell", "wind", "history", "honesty"):
        assert k in body
    for k in ("fires", "ventilation", "trend"):
        assert k in body["evaluated"]


def test_why_block_in_city(snap_root, wind_se, cold_forecast,
                           monkeypatch):
    """/v2/city carries the one-liner block."""
    import fires
    monkeypatch.setattr(fires, "FIRES", _NoFires())
    from airfield import FIELD
    FIELD._samples = [(28.63, 77.21, "t", {"pm2_5": 90.0})]
    FIELD._fetched_at = time.time()
    r = client.get("/v2/city")
    assert r.status_code == 200
    why = r.json().get("why")
    assert why is not None and why["line"]
    assert why["why_url"] == "/v2/why"


# ----------------------------------------------------------------- surfaces

def test_city_html_has_why_line():
    html = open(os.path.join(os.path.dirname(__file__), "..",
                             "city.html")).read()
    assert 'id="whyline"' in html and "cy.why" in html


def test_admin_html_has_drivers_table():
    html = open(os.path.join(os.path.dirname(__file__), "..",
                             "admin.html")).read()
    assert 'id="whydrivers"' in html and "/v2/why" in html \
        and 'id="whyeval"' in html
