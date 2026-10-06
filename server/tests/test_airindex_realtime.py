"""r5 realtime-honesty tests — fully synthetic, no network.

Contract covered:
  * ingest_cpcb degrades cleanly when api.data.gov.in is TCP-refused
    (non-India egress): the status carries the verbatim upstream reason
    ('ConnectError: [Errno 111] Connection refused'), retries are
    bounded, and a partially-failed fetch reports its per-state errors.
  * forecast.pm25() is anchored to the live FIELD: exact at the current
    hour, decaying ~exp(-h/9h) toward raw CAMS, gated by field
    freshness — the live source is injectable per convention and the
    module never reads snapshot paths itself.
  * the provenance line /health renders — 'model: 48 pts, 42s old' —
    is computable from bundle fields alone.

Run from server/:   uv run pytest tests/test_airindex_realtime.py -q
"""
import inspect
import math
import os
import sys
import time
from datetime import datetime, timedelta, timezone

import httpx
import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(_HERE))          # server/ on sys.path

import airindex                                    # noqa: E402
import forecast                                    # noqa: E402
import ingest_cpcb                                 # noqa: E402

NOW = 1_780_000_000.0  # fixed epoch — deterministic ages
LODHI = (28.5918, 77.2277)


# ---------------------------------------------------------------- cpcb

class _RefusedClient:
    """api.data.gov.in TCP-refused — every GET raises ConnectError."""
    def __init__(self):
        self.calls = 0

    def get(self, url, params=None, **kw):
        self.calls += 1
        raise httpx.ConnectError("[Errno 111] Connection refused")


class _PartialClient:
    """Delhi page answers (one real row); every other state is refused."""
    def __init__(self):
        self.calls = 0

    def get(self, url, params=None, **kw):
        self.calls += 1
        if (params or {}).get("filters[state]") == "Delhi":
            return _CPResp({"status": "ok", "total": 1, "records": [
                {"station": "Income Tax Office, Delhi - CPCB",
                 "last_update": "03-10-2026 09:00:00",
                 "pollutant_id": "PM2.5", "pollutant_avg": "54",
                 "pollutant_min": "31", "pollutant_max": "88"}]})
        raise httpx.ConnectError("[Errno 111] Connection refused")


class _CPResp:
    def __init__(self, payload):
        self._p = payload
        self.status_code = 200

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("err", request=None, response=None)

    def json(self):
        return self._p


def test_cpcb_tcp_refused_verbatim_reason_bounded_retries():
    c = _RefusedClient()
    sleeps = []
    res = ingest_cpcb.fetch(api_key="k", client=c, sleep=sleeps.append)
    # the upstream reason rides the status verbatim — no 'Delhi@0' label
    assert res["status"].startswith("unavailable: ConnectError")
    assert "refused" in res["status"].lower()
    assert "@0" not in res["status"]
    # bounded: <= states x GET_ATTEMPTS calls, one sleep between tries
    assert c.calls == len(ingest_cpcb.STATES) * ingest_cpcb.GET_ATTEMPTS
    assert len(sleeps) == \
        len(ingest_cpcb.STATES) * (ingest_cpcb.GET_ATTEMPTS - 1)
    assert all(0 < s <= ingest_cpcb.BACKOFF_CAP_S for s in sleeps)
    rep = res["report"]
    assert rep["requests"] == c.calls          # real HTTP calls counted
    assert rep["attempts_per_page"] == ingest_cpcb.GET_ATTEMPTS
    assert all("ConnectError" in e for e in rep["errors"])
    assert res["stations"] == [] and res["fetched_at"]


def test_cpcb_attempts_override_tightens_bound():
    c = _RefusedClient()
    res = ingest_cpcb.fetch(api_key="k", client=c, attempts=1,
                            sleep=lambda s: None)
    assert c.calls == len(ingest_cpcb.STATES)  # one try per state, done
    assert res["status"].startswith("unavailable: ConnectError")


def test_cpcb_partial_failure_ok_but_errors_honest():
    res = ingest_cpcb.fetch(api_key="k", client=_PartialClient(),
                            sleep=lambda s: None)
    assert res["status"] == "ok"
    assert res["n"] == len(res["stations"]) == 1
    # refused states are counted verbatim next to their state@page tag
    errs = res["report"]["errors"]
    assert len(errs) == len(ingest_cpcb.STATES) - 1
    assert any("Haryana@0: ConnectError" in e for e in errs)
    assert res["report"]["requests"] > len(ingest_cpcb.STATES)


def test_cpcb_status_reflects_refused_last_fetch():
    """status() must surface the verbatim failure, not 'ok' or silence."""
    ingest_cpcb.fetch(api_key="k", client=_RefusedClient(),
                      sleep=lambda s: None)
    st = ingest_cpcb.status(api_key="k")
    assert "ConnectError" in st["status"]
    assert st["last_fetch"]["n_stations"] == 0


# ------------------------------------------------------------- forecast

def _forecast_field(live, const=40.0):
    """ForecastField holding a flat `const` µg/m³ CAMS horizon that
    starts today 00:00 UTC — hour_index resolves against real 'now',
    so the anchor math is exact (met empty -> stagnation factor 1.0)."""
    ff = forecast.ForecastField(live=live)
    t0 = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0,
                                            microsecond=0)
    times = [(t0 + timedelta(hours=i)).isoformat() for i in range(120)]
    ff._aq = [{"lat": LODHI[0], "lon": LODHI[1], "name": None, "t0": t0,
               "times": times, "vars": {"pm2_5": [const] * 120}}]
    return ff


def test_forecast_anchors_exactly_at_current_hour():
    """h=0 must report what the live field reports — not the model."""
    ff = _forecast_field(live=lambda la, lo: 100.0)
    assert ff.hour_index(0) is not None
    v = ff.pm25(*LODHI, 0)
    assert v == pytest.approx(100.0, abs=0.5)


def test_forecast_anchor_decays_toward_model():
    """Far-horizon slots converge on raw CAMS — the live correction is
    persistence, not a permanent bias. Two stages: the bias delta
    decays exp(-h/9); on top, the fitted blend pulls toward the live
    read with anchor_w(h) = 1 to h+2, linear to 0 by h+40."""
    ff = _forecast_field(live=lambda la, lo: 100.0)
    v24 = ff.pm25(*LODHI, 24)
    v48 = ff.pm25(*LODHI, 48)
    # h=24: corrected = 40+60·e^(-24/9) ~= 44.2; w = 16/38 ~= 0.421 ->
    # blend = 44.2 + 0.421·(100-44.2) ~= 67.7
    assert v24 == pytest.approx(67.7, abs=1.0)
    # h=48 is past the blend's reach: the bias delta alone remains,
    # 40 + 60·e^(-48/9) ~= 40.3
    assert v48 == pytest.approx(40.3, abs=0.8)
    assert v48 < v24


def test_forecast_no_live_source_is_raw_model():
    ff = _forecast_field(live=None)
    assert ff.pm25(*LODHI, 0) == pytest.approx(40.0)
    st = ff.status()["live_anchor"]
    assert st["enabled"] is False and st["source"] is None


def test_forecast_live_none_value_unanchored():
    """A live source with nothing to say must not bend the field."""
    ff = _forecast_field(live=lambda la, lo: None)
    assert ff.pm25(*LODHI, 0) == pytest.approx(40.0)


def test_forecast_pm25_live_kwarg_overrides_default():
    ff = _forecast_field(live=lambda la, lo: 100.0)
    assert ff.pm25(*LODHI, 0, live=None) == pytest.approx(40.0)
    assert ff.pm25(*LODHI, 0, live=lambda la, lo: 55.0) \
        == pytest.approx(55.0)


def test_forecast_anchor_cannot_push_negative():
    """A live value near zero decays a high model — but never below 0."""
    ff = _forecast_field(live=lambda la, lo: 0.0)
    assert ff.pm25(*LODHI, 0) == pytest.approx(0.0, abs=0.5)
    assert ff.pm25(*LODHI, 24) > 0.0


def test_default_live_anchor_is_airfield_field():
    ff = forecast.ForecastField()
    assert ff._live is forecast._live_field_pm25
    st = ff.status()["live_anchor"]
    assert st["enabled"] is True and st["source"] == "airfield.FIELD"
    assert st["bias_tau_h"] == forecast.ANCHOR_TAU_H
    assert st["max_age_s"] == forecast.ANCHOR_MAX_AGE_S
    # the fitted persistence blend reports its shape honestly
    bl = st["blend"]
    assert bl["hold_h"] == forecast.ANCHOR_BLEND_HOLD_H
    assert bl["end_h"] == forecast.ANCHOR_BLEND_END_H
    assert bl["w_h1"] == 1.0 and 0.0 < bl["w_h11"] < 1.0


def test_field_anchor_gated_by_serving_freshness(monkeypatch):
    """The FIELD anchor fires only while the served field is fresh —
    a >3 h old truth must not bend the horizon."""
    monkeypatch.setattr(forecast.FIELD, "status",
                        lambda: {"age_s": forecast.ANCHOR_MAX_AGE_S + 1})
    monkeypatch.setattr(forecast.FIELD, "value",
                        lambda la, lo, p="pm2_5": 77.0)
    assert forecast._live_field_pm25(*LODHI) is None
    monkeypatch.setattr(forecast.FIELD, "status",
                        lambda: {"age_s": 60})
    assert forecast._live_field_pm25(*LODHI) == 77.0


def test_field_anchor_empty_or_none_field_unanchored(monkeypatch):
    monkeypatch.setattr(forecast.FIELD, "status",
                        lambda: {"age_s": 60})
    monkeypatch.setattr(forecast.FIELD, "value",
                        lambda la, lo, p="pm2_5": None)
    assert forecast._live_field_pm25(*LODHI) is None


def test_departure_window_scores_anchored_now():
    """The 'leave later' optimizer inherits the anchor through pm25 —
    its 'worst' slot can honestly be *right now*."""
    ff = _forecast_field(live=lambda la, lo: 100.0)
    w = ff.best_departure_window(*LODHI, 0, 4)
    # the hold window (w=1 through h+2) serves the live read verbatim —
    # "right now" is tied-worst, not artificially safe
    assert w["worst"]["hours_ahead"] <= 2
    assert w["worst"]["pm25_ugm3"] == pytest.approx(100.0, abs=1.0)
    # best = furthest-out slot: h=3 sits just past the hold window, so
    # w ~ 0.974 — corrected 40+60·e^(-3/9) ~ 83.0, blended ~ 99.6
    assert w["best"][0]["hours_ahead"] == 3
    corr = 40.0 + 60.0 * math.exp(-3 / forecast.ANCHOR_TAU_H)
    assert w["best"][0]["pm25_ugm3"] == pytest.approx(
        corr + forecast.anchor_w(3) * (100.0 - corr), abs=1.0)


def test_forecast_reads_live_field_not_snapshot_paths():
    """forecast.py must not manage snapshot files itself — the live
    truth is FIELD's freshness-honest serving layer."""
    src = inspect.getsource(forecast)
    for pat in ("load_snapshot", "SNAPSHOT_DIR", "gzip", "open("):
        assert pat not in src, f"forecast.py touches stale path: {pat}"


# ----------------------------------------------------------- health row

def test_provenance_renders_health_line():
    """/health's 'model: 48 pts, 42s old' is computable from the
    provenance fields alone — n + age_s."""
    inputs = {
        "model": {"status": "ok", "source": "open-meteo/cams",
                  "fetched_at": NOW - 42,
                  "samples": [{"lat": 28.5, "lon": 77.2, "name": None,
                               "pm25": 60.0}] * 48},
        "stations": {"status": "ok", "source": "openaq-v3",
                     "fetched_at": NOW - 120, "stations": []},
        "fires": {"status": "ok", "source": "nasa-firms-public-csv",
                  "fetched_at": NOW - 900, "modifier": 1.0,
                  "n_fires": 4, "belt_fires": 1},
        "met": {"status": "ok", "source": "open-meteo",
                "fetched_at": NOW - 60, "wind_ms": 2.5, "wind_deg": 315,
                "blh_m": 800.0, "vc_m2s": 2000.0},
    }
    f = airindex.build_field(now=NOW, inputs=inputs)
    p = f["provenance"]["model"]
    assert f"model: {p['n']} pts, {p['age_s']}s old" == \
        "model: 48 pts, 42s old"
    # every source carries the same renderable triple
    for src, p in f["provenance"].items():
        assert p["n"] is not None, src
        assert p["fetched_at"], src
        assert p["age_s"] is not None, src
