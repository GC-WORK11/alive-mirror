"""Tests for the aggregate-only admin API (server/admin_agg.py).

The whole point of the surface is doc 07 §3: it must be structurally
incapable of showing a person. So beyond shape tests, every response is
recursively scanned for token/coordinate/identity field names, and the
k>=3 corridor rule is tested both as a passthrough (store enforces) and
as a tripwire (admin asserts).
"""
import asyncio
import time

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

import admin_agg
from v2.store import TRIPS

app = FastAPI()
app.include_router(admin_agg.router)
client = TestClient(app)

ENDPOINTS = [
    "/admin/api",
    "/admin/api/status",
    "/admin/api/sources",
    "/admin/api/corridors",
    "/admin/api/donations",
    "/admin/api/validation",
    "/admin/api/model",
    "/admin/api/timing",
    "/admin/api/global",
]

# Field names that must never appear anywhere in an admin response —
# at any depth. ("devices" is a COUNT, allowed; "near"/"station" are
# public place/station names, allowed.)
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
    """Every dict key in a nested JSON structure, any depth."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield str(k)
            yield from _keys(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _keys(v)


def _donate(cells, tokens, summary=None):
    """One trip per token — mirrors what /v2/trip does post-privacy."""
    summary = summary or {"mode": "metro", "distance_km": 4.0,
                          "dose_ug": 40.0, "switched": False}
    for tok in tokens:
        TRIPS.record_trip(cells, summary, token_hash=tok)


# --- shapes -----------------------------------------------------------------

def test_index_shape():
    r = client.get("/admin/api")
    assert r.status_code == 200
    d = r.json()
    assert set(ENDPOINTS[1:]) == set(d["endpoints"])
    assert "aggregate" in d["privacy"]


def test_status_shape():
    d = client.get("/admin/api/status").json()
    for k in ("ts", "ok", "build_sha", "version", "uptime_s",
              "field", "provenance", "empty"):
        assert k in d
    for k in ("source", "samples", "station_readings",
              "age_s", "kriging", "wind", "snapshot_age_s"):
        assert k in d["field"]


def test_sources_shape():
    d = client.get("/admin/api/sources").json()
    assert set(d["sources"]) == {"model", "met", "stations",
                               "fires", "location", "routing"}
    for s in d["sources"].values():
        assert s.get("up") in (True, False, None)  # tri-state, never guessed
        assert "detail" in s


def test_validation_shape_and_no_grid_cells():
    d = client.get("/admin/api/validation").json()
    assert d["status"] in ("ok", "no rollup outputs on disk yet")
    assert "weekly" in d and "daily" in d
    if d["weekly"]:
        assert "loso" in d["weekly"] and "archive_replay" in d["weekly"]
    if d["daily"]:
        # rollup cell maps embed grid coords in their keys — never surface them
        assert "cells" not in d["daily"]


def test_sources_fires_held_to_own_cadence(monkeypatch):
    """Drift-watch finding: FIRMS' public CSV refreshes on its 6 h cache
    TTL, so holding it to the field's 45-min alarm rule flapped it stale
    between on-spec refreshes. Each source is now held to its own
    stale_after_s — fires self-declares STALE_AFTER_S = CACHE_S + one
    fetch cycle."""
    import fires as fires_mod
    fires_age = {"v": 3600.0}
    monkeypatch.setattr(admin_agg._health, "collect_health",
                        lambda **k: {"sources": {
                            "stations": {"age_s": 3000}}})
    monkeypatch.setattr(admin_agg, "_field_status",
                        lambda: {"stale_after_s": 2700, "age_s": 60})
    monkeypatch.setattr(admin_agg, "_fires_status",
                        lambda: {"age_s": fires_age["v"], "fires": 3,
                                 "stale_after_s": fires_mod.STALE_AFTER_S})
    monkeypatch.setattr(admin_agg, "_snapshot_prov", lambda: {})
    monkeypatch.setattr(admin_agg, "_location_enabled", lambda: False)
    monkeypatch.setattr(admin_agg, "_routing_status", lambda: {})

    d = client.get("/admin/api/sources").json()
    src = d["sources"]
    # past the FIELD bar (3600 > 2700) but inside its own cadence
    assert src["fires"]["stale_after_s"] == fires_mod.STALE_AFTER_S
    assert src["fires"]["stale_after_s"] > d["stale_after_s"]
    assert src["fires"]["stale"] is False
    # stations stay on the 45-min field line: 3000 > 2700 -> stale
    assert src["stations"]["stale_after_s"] == 2700
    assert src["stations"]["stale"] is True
    # and a fires feed genuinely past its own bar still flags
    fires_age["v"] = fires_mod.STALE_AFTER_S + 60
    assert client.get("/admin/api/sources").json()[
        "sources"]["fires"]["stale"] is True


# --- corridors: k>=3 ---------------------------------------------------------

def test_corridors_empty_is_honest():
    d = client.get("/admin/api/corridors").json()
    assert d["rows"] == [] and d["empty"] is True
    assert d["k_min"] == 3 and d["window_s"] == 72 * 3600


def test_corridors_k_suppression_passthrough():
    # 2 distinct devices on cell A -> suppressed by the store
    _donate(["cellA"], ["t1", "t2"])
    # 3 distinct devices on cell B -> publishable
    _donate(["cellB"], ["t1", "t2", "t3"])
    d = client.get("/admin/api/corridors").json()
    cells = [r["cell"] for r in d["rows"]]
    assert "cellB" in cells and "cellA" not in cells
    assert all(r["devices"] >= 3 for r in d["rows"])
    # passthrough: endpoint shows exactly what the store publishes
    assert cells == [r["cell"] for r in TRIPS.corridors(limit=25)]
    row = d["rows"][0]
    assert set(row) == {"cell", "near", "trips", "devices", "avg_dose_ug",
                        "co2_g_per_100m", "co2_trips", "field_pm25"}


def test_corridors_k_floor_tripwire(monkeypatch):
    """If the store ever regresses and leaks a k<3 row, the endpoint must
    fail loud (a real exception → structured 500) — never render it, and
    never depend on `assert` surviving `python -O`."""
    class BrokenStore:
        def corridors(self, limit=20):
            return [{"cell": "x", "trips": 5, "devices": 2,
                     "avg_dose_ug": 10.0}]

        def city_aggregates(self):
            return {"days": {}, "cells_tracked": 0,
                    "corridors_publishable": 0}

    monkeypatch.setattr(admin_agg, "TRIPS", BrokenStore())
    with pytest.raises(HTTPException) as e:
        asyncio.run(admin_agg.corridors())
    assert e.value.status_code == 500
    r = client.get("/admin/api/corridors")
    assert r.status_code == 500 and "k>=3" in r.json()["detail"]


def test_global_k_floor_tripwire(monkeypatch):
    """Same tripwire on /global — a k<3 area or od_pair row fails the
    endpoint loud, never publishes."""
    class BrokenStore:
        def global_aggregates(self):
            return {"areas": [{"name": "x", "devices": 2}],
                    "od_pairs": []}

    monkeypatch.setattr(admin_agg, "TRIPS", BrokenStore())
    r = client.get("/admin/api/global")
    assert r.status_code == 500 and "k>=3" in r.json()["detail"]


# --- donations ----------------------------------------------------------------

def test_donations_empty_is_honest():
    d = client.get("/admin/api/donations").json()
    assert d["totals"]["trips"] == 0 and d["empty"] is True
    # no global device registry exists — reported as such, not guessed
    assert d["distinct_devices"] is None
    assert "devices_note" in d


def test_donations_totals_sum_days():
    _donate(["cellB"], ["t1"], {"mode": "metro", "distance_km": 4.0,
                              "dose_ug": 40.0, "switched": True})
    _donate(["cellC"], ["t2"], {"mode": "car", "distance_km": 6.0,
                              "dose_ug": 90.0})
    d = client.get("/admin/api/donations").json()
    t = d["totals"]
    assert t["trips"] == 2 and t["km"] == 10.0
    assert t["dose_ug"] == 130.0 and t["switched"] == 1
    assert t["modes"] == {"metro": 1, "car": 1}
    today = time.strftime("%Y-%m-%d", time.gmtime())
    assert today in d["days"] and d["n_days"] == 1
    assert d["empty"] is False


def test_donations_co2_split_only_counts_reporters():
    _donate(["cellB"], ["t1"], {"mode": "car", "distance_km": 9.0,
                               "co2_kg_mid": 1.9,
                               "co2_moving_g": 100.0, "co2_idle_g": 40.0,
                               "co2_cold_g": 60.0})
    # old-build donation: counts in headline totals, never in the split
    _donate(["cellC"], ["t2"], {"mode": "bike", "distance_km": 4.0,
                               "co2_kg_mid": 0.9})
    t = client.get("/admin/api/donations").json()["totals"]
    sp = t["co2_split"]
    assert sp["trips"] == 1 and sp["moving_g"] == 100.0
    assert sp["pct"] == {"moving": 50.0, "idle": 20.0, "cold": 30.0}
    assert t["co2_kg_mid"] == 2.8  # both trips in the headline total


def test_model_card_serves_real_constants():
    d = client.get("/admin/api/model").json()
    assert d["available"] is True
    # the panel's numbers are the model's own tables — spot-check two
    # canonical rows so a drifted constant can never ship silently
    assert d["microenv"]["auto_rickshaw"] == 1.30
    assert d["ventilation_lpm"]["cycling"] == 22.0
    # cigarette framing is off admin surfaces entirely — the constant and
    # its citation must not ship to the ops board
    assert "cig_equiv_ug" not in d and "cig" not in d["citations"]
    assert "walk" not in d["microenv"]  # canonical keys only


def test_donations_co2_split_absent_is_null():
    _donate(["cellB"], ["t1"])
    t = client.get("/admin/api/donations").json()["totals"]
    assert t["co2_split"] is None


def _donate_od(o, d, tokens, summary=None, **rec_kw):
    summary = summary or {"mode": "metro", "distance_km": 4.0,
                          "dose_ug": 40.0}
    for tok in tokens:
        TRIPS.record_trip(["cellX", "cellY"], summary, token_hash=tok,
                          origin_area=o, dest_area=d, **rec_kw)


def test_global_empty_is_honest():
    d = client.get("/admin/api/global").json()
    assert d["empty"] is True
    assert d["areas"] == [] and d["od_pairs"] == []
    assert d["dose_avoided"] is None and d["co2_avoided"] is None
    assert d["suppressed"] == {"areas": 0, "od_pairs": 0}


def test_global_areas_and_od_k_rule():
    _donate_od("Central Delhi", "Gurugram", ["t1", "t2"])
    _donate_od("Central Delhi", "Gurugram", ["t3"])
    d = client.get("/admin/api/global").json()
    a = [r for r in d["areas"] if r["area"] == "Central Delhi"]
    assert a and a[0]["devices"] == 3 and a[0]["trips"] == 3
    od = d["od_pairs"]
    assert od == [{"origin": "Central Delhi", "dest": "Gurugram",
                   "trips": 3, "devices": 3}]
    assert d["empty"] is False


def test_global_suppresses_below_k3_and_counts():
    _donate_od("Shahdara", "Faridabad", ["t1", "t2"])  # 2 devices < k
    d = client.get("/admin/api/global").json()
    assert d["areas"] == [] and d["od_pairs"] == []
    assert d["suppressed"] == {"areas": 1, "od_pairs": 1}
    assert d["areas_tracked"] == 1 and d["od_pairs_tracked"] == 1
    assert d["empty"] is True  # suppressed rows never mint data


def test_global_savings_only_count_reporters():
    _donate_od("A", "B", ["t1", "t2", "t3"])
    TRIPS.record_trip(["c"], {"mode": "car", "distance_km": 5.0,
                              "dose_ug": 60.0, "avoided_ug": 30.0,
                              "co2_avoided_kg": 0.8,
                              "puc_calibrated": True},
                      token_hash="t4", origin_area="A", dest_area="B")
    # a trip carrying co2_avoided_kg WITHOUT the PUC flag must not count
    TRIPS.record_trip(["c"], {"mode": "car", "distance_km": 5.0,
                              "dose_ug": 60.0, "co2_avoided_kg": 9.9},
                      token_hash="t5")
    d = client.get("/admin/api/global").json()
    assert d["dose_avoided"] == {"dose_ug": 30.0, "trips_reporting": 1}
    assert d["co2_avoided"] == {"co2_kg": 0.8, "puc_calibrated_trips": 1}


def test_global_no_origin_means_no_area_row():
    TRIPS.record_trip(["cellX"], {"mode": "metro", "distance_km": 3.0,
                                 "dose_ug": 10.0}, token_hash="t1")
    d = client.get("/admin/api/global").json()
    assert d["areas_tracked"] == 0 and d["od_pairs_tracked"] == 0


# --- privacy scan -------------------------------------------------------------

def test_no_identity_or_coordinate_fields_anywhere():
    """Recursive scan: no response from ANY admin endpoint may carry a
    token / coordinate / identity field name, at any depth."""
    _donate(["cellB"], ["t1", "t2", "t3"])  # populate so rows exist too
    for ep in ENDPOINTS:
        r = client.get(ep)
        assert r.status_code == 200, ep
        leaked = {k.lower() for k in _keys(r.json())} & BANNED_KEYS
        assert not leaked, f"{ep} leaks field(s): {leaked}"
