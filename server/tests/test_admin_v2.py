"""r5 ops-dashboard tests — the fields the rebuilt /admin page consumes.

Covers the additive surface on /admin/api/* (server/admin_agg.py):
field serving/stale/σ-band honesty, the `met` ingest source with
provenance extras, per-source stale flags, mode share + derived dose
means in /donations, publishable counts in /corridors — and re-asserts
the k>=3 + no-identity invariants against the enriched payloads.
"""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import admin_agg
from v2.store import TRIPS

app = FastAPI()
app.include_router(admin_agg.router)
app.include_router(admin_agg.usage_router)
client = TestClient(app)

ENDPOINTS = [
    "/admin/api",
    "/admin/api/status",
    "/admin/api/sources",
    "/admin/api/corridors",
    "/admin/api/donations",
    "/admin/api/validation",
    "/v2/usage",
]

# Same contract as test_admin_agg: no response may carry identity or
# coordinate field names, at any depth — the new fields must not either.
BANNED_KEYS = {
    "token", "tokens", "token_hash", "device_token",
    "lat", "lon", "latitude", "longitude",
    "coord", "coords", "coordinate", "coordinates",
    "trajectory", "points", "geometry", "route",
    "contributor", "reporter", "identity",
    "user", "users", "uid", "uuid", "device_id", "ip",
}


@pytest.fixture(autouse=True)
def clean_store():
    TRIPS.reset()
    yield
    TRIPS.reset()


def _keys(obj):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield str(k)
            yield from _keys(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _keys(v)


def _donate(cells, tokens, summary=None):
    summary = summary or {"mode": "metro", "distance_km": 4.0,
                          "dose_ug": 40.0, "switched": False}
    for tok in tokens:
        TRIPS.record_trip(cells, summary, token_hash=tok)


def _fake_field(**over):
    f = {"source": "openaq-stations+open-meteo/cams",
         "serving": "snapshot", "samples": 48, "station_readings": 42,
         "age_s": 300, "stale": False, "stale_after_s": 2700,
         "kriging": "on", "sigma_coverage": "full",
         "coverage": {"bbox": [76.8, 28.2, 77.5, 28.9],
                      "out_beyond_km": 12, "cells": 1200,
                      "sigma_cells": 1200},
         "wind": {"speed_kmh": 11.0, "from_deg": 290.0, "factor": 0.4}}
    f.update(over)
    return f


def _fake_health(sources=None, **over):
    h = {"ok": True, "ts": 1000.0, "build_sha": "abc123",
         "version": "0.0.0-test", "uptime_s": 60.0, "field_age_s": 400,
         "disk": {"free_pct": 61.0, "low": False},
         "trips_backend": "memory",
         "sources": sources or {}}
    h.update(over)
    return h


# --- /status: serving + stale + sigma honesty --------------------------------

def test_status_serving_stale_sigma_keys(monkeypatch):
    monkeypatch.setattr(admin_agg, "_field_status",
                        lambda: _fake_field())
    monkeypatch.setattr(admin_agg._health, "collect_health",
                        lambda: _fake_health())
    d = client.get("/admin/api/status").json()
    f = d["field"]
    for k in ("serving", "stale", "stale_after_s",
              "sigma_coverage", "coverage"):
        assert k in f
    assert f["serving"] == "snapshot"
    assert f["stale"] is False and f["stale_after_s"] == 2700
    assert f["sigma_coverage"] == "full"
    assert f["coverage"]["cells"] == 1200
    assert d["trips_backend"] == "memory"
    assert "disk" in d and d["disk"]["free_pct"] == 61.0


def test_status_stale_true_passthrough(monkeypatch):
    monkeypatch.setattr(admin_agg, "_field_status",
                        lambda: _fake_field(age_s=4000, stale=True))
    f = client.get("/admin/api/status").json()["field"]
    assert f["stale"] is True and f["age_s"] == 4000


# --- /sources: met, provenance extras, stale flags ----------------------------

def test_sources_met_present_with_prov_extras(monkeypatch):
    monkeypatch.setattr(admin_agg, "_field_status", lambda: _fake_field())
    monkeypatch.setattr(admin_agg, "_snapshot_prov", lambda: {
        "model": {"n_points": 48},
        "met": {"wind_ms": 3.2, "wind_deg": 285.0,
                "blh_m": 912.0, "vc_m2s": 2918.4},
        "stations": {"n_raw": 61, "n_used": 42},
        "fires": {"modifier": 1.21},
    })
    d = client.get("/admin/api/sources").json()
    s = d["sources"]
    assert "met" in s                       # fourth field input, now surfaced
    assert s["met"]["wind_ms"] == 3.2
    assert s["met"]["vc_m2s"] == 2918.4
    assert s["met"]["blh_m"] == 912.0
    assert s["model"]["n_points"] == 48
    assert s["stations"]["n_used"] == 42
    assert s["stations"]["n_raw"] == 61
    assert s["fires"]["modifier"] == 1.21
    assert d["stale_after_s"] == 2700


def test_sources_stale_flag_tristate(monkeypatch):
    monkeypatch.setattr(admin_agg, "_field_status",
                        lambda: _fake_field(stale_after_s=100))
    monkeypatch.setattr(admin_agg, "_snapshot_prov", lambda: {})
    monkeypatch.setattr(admin_agg, "_fires_status", lambda: {})
    monkeypatch.setattr(admin_agg._health, "collect_health",
                        lambda: _fake_health(sources={
                            "model": {"up": None, "detail": "m",
                                      "age_s": 500, "status": "ok"},
                            "met": {"up": None, "detail": "met",
                                    "age_s": 10, "status": "ok"},
                            "stations": {"up": None, "detail": "s",
                                         "age_s": None, "status": "x"},
                            "fires": {"up": None, "detail": "f",
                                      "age_s": 90, "status": "ok"},
                            "location": {"up": None, "detail": "l"},
                        }))
    s = client.get("/admin/api/sources").json()["sources"]
    assert s["model"]["stale"] is True      # 500s > 100s alarm rule
    assert s["met"]["stale"] is False       # fresh
    assert s["stations"]["stale"] is None   # no age -> 'no data', not 'late'
    assert s["location"]["stale"] is None
    assert s["fires"]["stale"] is False


def test_sources_live_null_never_erases_prov_age(monkeypatch):
    """A live module that has never fetched (age_s None) must not blank
    out the newest snapshot's provenance age — the honest age survives."""
    monkeypatch.setattr(admin_agg, "_field_status", lambda: _fake_field())
    monkeypatch.setattr(admin_agg, "_snapshot_prov", lambda: {})
    monkeypatch.setattr(admin_agg, "_fires_status",
                        lambda: {"fires": None, "belt_fires": None,
                                 "status": None, "age_s": None})
    monkeypatch.setattr(admin_agg._health, "collect_health",
                        lambda: _fake_health(sources={
                            "fires": {"up": None, "detail": "f",
                                      "age_s": 700, "status": "ok"},
                        }))
    s = client.get("/admin/api/sources").json()["sources"]
    assert s["fires"]["age_s"] == 700       # prov age kept, not erased
    assert s["fires"]["status"] == "ok"


def test_sources_live_values_win_over_prov(monkeypatch):
    monkeypatch.setattr(admin_agg, "_field_status", lambda: _fake_field())
    monkeypatch.setattr(admin_agg, "_snapshot_prov", lambda: {})
    monkeypatch.setattr(admin_agg, "_fires_status",
                        lambda: {"fires": 12, "belt_fires": 4,
                                 "status": "ok", "age_s": 55})
    monkeypatch.setattr(admin_agg._health, "collect_health",
                        lambda: _fake_health(sources={
                            "fires": {"up": None, "detail": "f",
                                      "age_s": 700, "status": "stale"},
                        }))
    s = client.get("/admin/api/sources").json()["sources"]
    assert s["fires"]["age_s"] == 55        # live fetch beats prov age
    assert s["fires"]["status"] == "ok"
    assert s["fires"]["fires"] == 12 and s["fires"]["belt_fires"] == 4


# --- /donations: mode share + derived means ------------------------------------

def test_donations_mode_share_sorted_and_sums_100():
    _donate(["cA"], ["t1"], {"mode": "car", "distance_km": 6.0,
                           "dose_ug": 90.0})
    _donate(["cB"], ["t2"], {"mode": "metro", "distance_km": 4.0,
                           "dose_ug": 40.0})
    _donate(["cC"], ["t3"], {"mode": "metro", "distance_km": 4.0,
                           "dose_ug": 40.0})
    _donate(["cD"], ["t4"], {"mode": "walk", "distance_km": 2.0,
                           "dose_ug": 10.0})
    d = client.get("/admin/api/donations").json()
    share = d["mode_share"]
    assert [r["mode"] for r in share] == ["metro", "car", "walk"]
    assert share[0]["trips"] == 2 and share[0]["pct"] == 50.0
    assert abs(sum(r["pct"] for r in share) - 100.0) < 0.3
    t = d["totals"]
    assert t["avg_dose_per_trip_ug"] == 45.0      # 180µg / 4 trips
    assert t["avg_km_per_trip"] == 4.0            # 16km / 4
    assert t["dose_ug_per_km"] == 11.2            # 180µg / 16km


def test_donations_derived_null_when_empty():
    """Zero trips -> null derived means, never a fake-zero average."""
    d = client.get("/admin/api/donations").json()
    assert d["mode_share"] == []
    t = d["totals"]
    assert t["avg_dose_per_trip_ug"] is None
    assert t["avg_km_per_trip"] is None
    assert t["dose_ug_per_km"] is None


# --- /corridors: publishable counts, k>=3 kept ---------------------------------

def test_corridors_publishable_counts():
    _donate(["cellA"], ["t1", "t2"])                 # k<3 -> suppressed
    _donate(["cellB"], ["t1", "t2", "t3"])           # publishable
    d = client.get("/admin/api/corridors").json()
    assert d["shown"] == len(d["rows"]) == 1
    assert d["publishable_cells"] == 1
    assert d["cells_tracked"] == 2
    assert all(r["devices"] >= 3 for r in d["rows"])
    assert d["k_min"] == 3


# --- privacy re-scan on the enriched payloads ----------------------------------

def test_enriched_payloads_still_leak_nothing(monkeypatch):
    monkeypatch.setattr(admin_agg, "_field_status", lambda: _fake_field())
    monkeypatch.setattr(admin_agg, "_snapshot_prov", lambda: {
        "met": {"wind_ms": 3.2, "wind_deg": 285.0,
                "blh_m": 912.0, "vc_m2s": 2918.4},
        "stations": {"n_raw": 61, "n_used": 42},
    })
    _donate(["cellB"], ["t1", "t2", "t3"])
    for ep in ENDPOINTS:
        r = client.get(ep)
        assert r.status_code == 200, ep
        leaked = {k.lower() for k in _keys(r.json())} & BANNED_KEYS
        assert not leaked, f"{ep} leaks field(s): {leaked}"
