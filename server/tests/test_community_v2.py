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
    # the synthetic CELL_A two-pointers are ~1.6 m long — far below the
    # 300 m endpoint trim observe() applies to untrimmed callers. They
    # model already-trimmed payloads (what /v2/trip sends), so flag them.
    return community.observe(vehicle=vehicle, coords=coords,
                             duration_s=duration_s, dose_ug=dose_ug,
                             avoided_ug=avoided_ug, contributor=contributor,
                             privacy_trimmed=True)


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


# --- banned-key invariant over every output -----------------------------------
# Coordinate leaves exist in exactly two sanctioned places: k>=3 corridor
# cell centres (the ~500 m cells the mobile CorridorLayer and the admin
# map draw — a corridor dict always carries {devices, samples, ...}) and
# volunteered public report pins (GeoJSON Point features). Any banned key
# elsewhere — or coordinates outside those two shapes — fails the build.
BANNED_KEYS = {
    "token", "tokens", "token_hash", "device_token",
    "latitude", "longitude", "coord", "coords",
    "trajectory", "points", "route", "contributor",
    "reporter", "identity", "user", "users", "uid",
    "uuid", "device_id", "ip",
}


def _walk_dicts(o):
    if isinstance(o, dict):
        yield o
        for v in o.values():
            yield from _walk_dicts(v)
    elif isinstance(o, list):
        for v in o:
            yield from _walk_dicts(v)


def test_outputs_never_leak_identity_or_foreign_coords():
    for dev in ("ka", "kb", "kc"):
        _donate(dev)
    community.report("smoke", 28.61, 77.20, contributor=None)
    for out in ALL_OUTPUTS():
        for d in _walk_dicts(out):
            ks = {str(k).lower() for k in d}
            assert not (ks & BANNED_KEYS), \
                f"banned key(s) {ks & BANNED_KEYS} in {sorted(d)}"
            if {"lat", "lon", "latitude", "longitude"} & ks:
                corridor = {"devices", "samples"} <= ks
                report_pin = {"kind", "age_min"} <= ks
                assert corridor or report_pin, \
                    f"coordinate leaf outside a k>=3 corridor cell or " \
                    f"volunteered report pin: {sorted(d)}"
            if "geometry" in ks or "coordinates" in ks:
                assert d.get("type") in ("Point", "Feature"), \
                    f"non-pin coordinate structure: {d}"


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


def test_recent_obs_suppresses_sub_k_hours():
    """An hour bucket of 1-2 devices is a thin slice of someone's trip
    (mode, summed dose/km, near-exact age) — the same k>=3
    distinct-device rule as corridor cells applies to recent_journeys."""
    now = time.time()
    for dev in ("dev-a", "dev-b"):                 # this hour: k=2 -> dark
        community._obs.append(_mk_obs(now, dev))
    for dev in ("dev-c", "dev-d", "dev-e"):        # prev hour: k=3 -> shown
        community._obs.append(_mk_obs(now - 3700, dev))
    rows = community.recent_obs(20)
    assert len(rows) == 1
    assert rows[0]["trips"] == 3 and rows[0]["devices"] == 3


def test_recent_obs_counts_devices_not_trips():
    """Three donations from ONE device in the same hour is k=1, not
    k=3 — trips count alone must never publish the bucket."""
    now = time.time()
    for _ in range(3):
        community._obs.append(_mk_obs(now, "same-dev"))
    assert community.recent_obs(20) == []


# --- endpoint-hiding trim (doc 07 §3, enforced server-side for /observe) ---
def test_observe_untrimmed_caller_gets_endpoint_trim():
    """The legacy /observe endpoint posts the full planned polyline —
    including home and destination. observe() must run the same privacy
    pipeline /v2/trip does before folding to cells, so the first and
    last ~300 m can never persist even at cell granularity."""
    # 2.0 km straight north, ~51 m spacing, through exact cell centers
    path = [[77.2100, 28.6300 + i * 0.00046] for i in range(40)]
    community.observe(vehicle="auto", coords=path, duration_s=480.0,
                      dose_ug=40.0, avoided_ug=None,
                      contributor="untrimmed-caller")
    obs = community._obs[-1]
    lats = {round(c[1], 3) for c in obs["cells"]}
    assert 28.630 not in lats, "origin cell persisted — trim missing"
    assert 28.650 not in lats, "destination cell persisted — trim missing"
    assert lats == {28.635, 28.640, 28.645}, lats
    assert 1.0 < obs["km"] < 1.6, obs["km"]  # ~1.4 km kept, not the 2.0 sent


def test_observe_privacy_trimmed_skips_second_trim():
    """v2/trip donates already-trimmed `kept` points — observe() must not
    shave another 300 m off them (would silently shorten every real
    donation's stored km by ~0.6 km)."""
    _donate("pre-trimmed")  # helper passes privacy_trimmed=True
    obs = community._obs[-1]
    assert obs["cells"], "pre-trimmed payload must keep its cells"
    assert obs["km"] > 0


def test_corridor_rows_carry_est_basis():
    """avg_dose_ug is traversal-implied, not an instrument read — the
    claims audit requires the estimate basis on the wire."""
    for dev in ("device-a", "device-b", "device-c"):
        _donate(dev)
    out = community.corridors()
    assert out and out[0]["avg_dose_basis"] == "est. from donated trips"


def test_corridors_tolerate_pre_km_snapshots():
    """Prod regression: snapshots written before obs carried km/cells
    (raw points only) crashed corridors() with KeyError 'km' -> /admin/api
    500. They must fold through _obs_km/_obs_cells like every other path."""
    now = time.time()
    for dev in ("a", "b", "c"):
        community._obs.append({
            "ts": now, "vehicle": "bus", "duration_s": 600.0,
            "dose_ug": 30.0, "avoided_ug": 0.0, "contributor": _tok(dev),
            "points": [[77.2090, 28.6300], [77.2091, 28.6301]],
        })
    out = community.corridors()
    assert len(out) == 1 and out[0]["devices"] == 3
    assert community.totals()["obs_total"] == 3


# ---------------------------------------------------------------- reviews
def _fresh_reviews(monkeypatch):
    community._reviews.clear()
    community._loaded = True
    monkeypatch.setattr(community, "_save", lambda: None)
    yield
    community._reviews.clear()
    community._loaded = False


def test_review_rejects_bad_stars():
    community._reviews.clear(); community._loaded = True
    assert community.add_review(stars=0, note="", build="x")["stored"] is False
    assert community.add_review(stars=6, note="", build="x")["stored"] is False
    assert community.add_review(stars="junk", note="", build="x")["stored"] is False
    community._reviews.clear(); community._loaded = False


def test_review_validates_and_caps():
    community._reviews.clear(); community._loaded = True
    assert community.add_review(stars=5, note="  x " * 200, build="abc123456789defg")["stored"]
    r = community._reviews[-1]
    assert r["stars"] == 5
    assert len(r["note"]) <= 240
    assert len(r["build"]) <= 16
    assert "contributor" not in r and "token" not in r  # nothing linkable at rest
    community._reviews.clear(); community._loaded = False


def test_reviews_notes_kgated():
    community._reviews.clear(); community._loaded = True
    community.add_review(stars=5, note="one", build="a")
    community.add_review(stars=4, note="two", build="a")
    s = community.reviews_summary()
    assert s["count"] == 2 and s["avg"] == 4.5
    assert s["notes"] == [] and s["notes_withheld"] is True
    community.add_review(stars=1, note="three", build="a")
    s = community.reviews_summary()
    assert s["count"] == 3 and s["notes_withheld"] is False
    assert {n["note"] for n in s["notes"]} == {"one", "two", "three"}
    assert all(n["ts_hour"] % 3600 == 0 for n in s["notes"])  # hour bucket
    community._reviews.clear(); community._loaded = False


def test_feedback_endpoint_round_trip():
    from fastapi.testclient import TestClient
    from main import app
    community._reviews.clear(); community._loaded = True
    c = TestClient(app)
    r = c.post("/v2/feedback", json={"stars": 4, "note": "smoke was honest"})
    assert r.status_code == 200 and r.json()["stored"] is True
    r = c.post("/v2/feedback", json={"stars": 9})
    assert r.status_code == 422
    s = c.get("/admin/api/reviews").json()
    assert s["count"] >= 1
    community._reviews.clear(); community._loaded = False


# --- junk donations never enter the ledger -------------------------------------
def test_observe_empty_or_garbage_coords_rejected():
    """A donation folding to zero usable cells is not a donation."""
    before = len(community._obs)
    for bad in ([], None, ["x"], [["x", "y"]]):
        out = community.observe(vehicle="car", coords=bad,
                                duration_s=600, dose_ug=10,
                                avoided_ug=None, contributor="junk",
                                privacy_trimmed=True)
        assert out["stored"] is False
    assert len(community._obs) == before


def test_observe_negative_metrics_dropped_not_stored():
    _donate("neg-check", dose_ug=-5.0, avoided_ug=-1.0)
    obs = community._obs[-1]
    # negative doses are physically impossible — stored as unknown,
    # never as numbers that would drag the aggregates down
    assert obs["dose_ug"] is None and obs["avoided_ug"] is None


def test_report_bad_kind_rejected():
    out = community.report("hurricane", 28.63, 77.21, contributor=None)
    assert out["stored"] is False
    assert not community._reports
