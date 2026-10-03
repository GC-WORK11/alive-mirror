"""Privacy contract tests for the legacy community module (docs/plan/07 §3).

/community and the admin feed may only ever publish aggregates: city
totals and ~500 m corridor cells that clear the k>=3 distinct-device
threshold inside a 72 h window — the same rule v2/store.py's
TripAggregates implements. Raw coordinates, raw device ids and
per-trip/per-device rows must appear NOWHERE in the output or at rest.
Run from server/:
    .venv/bin/python -m pytest tests/test_community_v2.py -v
"""
import hashlib
import json
import os
import sys
import time

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import community  # noqa: E402

# one ~500 m cell near Connaught Place, plus a far-away second cell
CELL_A = [[77.2090, 28.6300], [77.2091, 28.6301]]  # same _cell bucket
CELL_B = [[77.7500, 28.9500]]


def _tok(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def _donate(contributor, coords=CELL_A, vehicle="bus",
            duration_s=600.0, dose_ug=30.0, avoided_ug=12.0):
    return community.observe(vehicle=vehicle, coords=coords,
                             duration_s=duration_s, dose_ug=dose_ug,
                             avoided_ug=avoided_ug, contributor=contributor)


def _mk_obs(ts, contributor, cells=None, vehicle="bus",
            duration_s=600.0, dose_ug=30.0, avoided_ug=0.0):
    """Stored-form observation (cells, hashed token) at a chosen time."""
    return {
        "ts": ts, "vehicle": vehicle, "duration_s": duration_s,
        "dose_ug": dose_ug, "avoided_ug": avoided_ug,
        "contributor": _tok(contributor), "km": 0.4,
        "cells": cells or [[77.2090, 28.6300]],
    }


@pytest.fixture(autouse=True)
def clean(monkeypatch):
    """Empty in-memory stores; never touch disk or S3."""
    community._obs.clear()
    community._reports.clear()
    community._loaded = True
    monkeypatch.setattr(community, "_save", lambda: None)
    yield
    community._obs.clear()
    community._reports.clear()
    community._loaded = False


def _keys(obj):
    """Every dict key in a nested structure, recursively."""
    found = set()
    if isinstance(obj, dict):
        for k, v in obj.items():
            found.add(k)
            found |= _keys(v)
    elif isinstance(obj, list):
        for v in obj:
            found |= _keys(v)
    return found


ALL_OUTPUTS = lambda: [  # noqa: E731 — every public read surface
    community.totals(),
    community.corridors(50),
    community.contributors_detail(),
    community.recent_obs(50),
    community.live_reports(),
    community.reports_geojson(),
]


# --- at-rest privacy ----------------------------------------------------------
def test_observe_hashes_token_and_drops_raw_points():
    _donate("raw-device-42")
    obs = community._obs[-1]
    assert obs["contributor"] == _tok("raw-device-42")
    assert "points" not in obs, "raw trajectory must not persist"
    assert obs["cells"], "traversal must fold into ~500m cells at ingest"
    blob = json.dumps(community._obs)
    assert "raw-device-42" not in blob
    assert "77.209" not in blob, "raw 5dp coordinates must not persist"


def test_report_stores_no_contributor():
    community.report("dust", 28.63, 77.21, contributor="raw-device-9")
    assert "contributor" not in json.dumps(community._reports)


# --- k>=3 suppression ---------------------------------------------------------
def test_corridor_below_k_never_publishes():
    # two devices, many passes — the old code showed this as a 'corridor'
    for _ in range(5):
        _donate("device-a")
        _donate("device-b")
    assert community.corridors() == []
    assert community.totals()["top_corridors"] == []


def test_corridor_publishes_at_k3_counts_trip_once():
    for dev in ("device-a", "device-b", "device-c"):
        _donate(dev)  # two points, same ~500m cell
    out = community.corridors()
    assert len(out) == 1
    c = out[0]
    assert c["samples"] == 3, "a trip counts a cell once, not per point"
    assert c["devices"] == 3
    for k in ("lon", "lat", "samples", "avg_dose_ug", "top_mode"):
        assert k in c, f"mobile client expects key {k!r}"


def test_corridor_stale_beyond_72h_suppressed():
    old = time.time() - 73 * 3600
    for dev in ("device-a", "device-b", "device-c"):
        community._obs.append(_mk_obs(old, dev))
    assert community.corridors() == []
    # a single fresh traversal refreshes the window but k still decides
    community._obs.append(_mk_obs(time.time(), "device-d"))
    out = community.corridors()
    assert len(out) == 1 and out[0]["devices"] == 4


def test_field_samples_need_k_distinct_devices():
    # one device looping: 3+ traversals must NOT enter the air field
    for _ in range(4):
        _donate("looping-device")
    assert community.corridor_field_samples() == []
    for dev in ("device-b", "device-c", "device-d"):
        _donate(dev)
    out = community.corridor_field_samples()
    assert out, ">=3 distinct devices should publish a field sample"
    assert all(s[3]["pm2_5"] > 0 for s in out)


# --- response shape (mobile client compat) ------------------------------------
def test_totals_shape_matches_mobile_contract():
    span = [[77.2090, 28.6300], [77.2280, 28.6300]]  # ~1.7 km, 2 cells
    for dev in ("a", "b", "c"):
        _donate(dev, coords=span)
    t = community.totals()
    expected = {"obs_total", "obs_24h", "contributors", "km_24h",
                "dose_ug_24h", "avoided_ug_24h", "avoided_ug_all",
                "active_reports", "modes_24h"}
    assert expected <= set(t), "Mobile/src/community.ts CommunityTotals"
    assert t["obs_total"] == 3 and t["contributors"] == 3
    assert t["km_24h"] > 0 and t["modes_24h"] == {"bus": 3}
    assert "aggregate" in t["basis"] and "anonymized" in t["basis"]
    assert t["source"] == "donated_trip_aggregates"


# --- no per-device fields anywhere --------------------------------------------
def test_no_per_device_fields_anywhere():
    for dev in ("dev-a", "dev-b", "dev-c", "dev-d"):
        _donate(dev)
    community.report("smoke", 28.61, 77.20, contributor="dev-a")
    for out in ALL_OUTPUTS():
        keys = _keys(out)
        assert "contributor" not in keys, f"per-device key in {keys}"
        blob = json.dumps(out)
        for dev in ("dev-a", "dev-b", "dev-c", "dev-d", _tok("dev-a")):
            assert dev not in blob, "raw or hashed device id leaked"


def test_contributors_detail_is_day_rollup_not_devices():
    for dev in ("dev-a", "dev-b", "dev-c"):
        _donate(dev)
    rows = community.contributors_detail()
    assert len(rows) == 1  # one UTC day, not one row per device
    r = rows[0]
    assert r["day"] == time.strftime("%Y-%m-%d", time.gmtime())
    assert r["contributors"] == 3 and r["trips"] == 3
    assert "contributor" not in _keys(rows)
    assert "last_seen_min_ago" in r  # /admin/api live-activity check


def test_recent_obs_are_hour_buckets_not_trips():
    for dev in ("dev-a", "dev-b", "dev-c"):
        _donate(dev)
    rows = community.recent_obs(20)
    assert len(rows) == 1 and rows[0]["trips"] == 3
    assert "contributor" not in _keys(rows)
    assert {"hour", "age_min", "trips", "vehicle", "dose_ug",
            "avoided_ug", "km"} <= _keys(rows)
