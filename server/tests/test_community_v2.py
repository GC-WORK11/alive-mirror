"""Privacy contract tests for the legacy community module (docs/plan/07 §3).

/community and the admin feed may only ever publish aggregates: city
totals and ~500 m corridor cells that clear the k>=3 distinct-device
threshold inside a 72 h window — the same rule v2/store.py's
TripAggregates implements. Raw coordinates, raw device ids and
per-trip/per-device rows must appear NOWHERE in the output or at rest —
and since the aggregate-at-ingest rewrite, no per-trip row can even
EXIST in the module's stores (the retired _obs list was the leak).
Run from server/:
    .venv/bin/python -m pytest tests/test_community_v2.py -v
"""
import hashlib
import io
import json
import os
import sys
import time

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import community  # noqa: E402
from v2 import store as _v2store  # noqa: E402

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


def _mk_fold(ts, contributor, cells=None, vehicle="bus",
             duration_s=600.0, dose_ug=30.0, avoided_ug=0.0):
    """Aggregate-fold a traversal at a chosen time — the aggregate-era
    replacement for poking _obs rows (which no longer exist)."""
    community._fold(
        ts=ts, vehicle=vehicle, duration_s=duration_s, dose_ug=dose_ug,
        avoided_ug=avoided_ug, co2_kg=None, km=0.4,
        cells={tuple(c) for c in (cells or [[77.2090, 28.6300]])},
        tok_hash=_tok(contributor))


@pytest.fixture(autouse=True)
def clean(monkeypatch):
    """Empty in-memory stores; never touch disk or S3."""
    for d in (community._CELLS, community._DAYS, community._HOURS,
              community._reports, community._reviews):
        d.clear()
    community._loaded = True
    community._CELLS_CACHE = (0.0, -1, [])
    community._s3_unhydrated = False
    community._s3_next_retry = 0.0
    community._LAST_ERROR = None
    # totals() reads the shared donation ledger — reset the module-level
    # singletons too so each test starts empty (memory backend only;
    # the suite never runs against real DDB)
    for s in (_v2store.TRIPS, _v2store.LEDGER):
        if getattr(s, "backend", "memory") == "memory":
            s.reset()
    monkeypatch.setattr(community, "_save", lambda: None)
    yield
    for d in (community._CELLS, community._DAYS, community._HOURS,
              community._reports, community._reviews):
        d.clear()
    for s in (_v2store.TRIPS, _v2store.LEDGER):
        if getattr(s, "backend", "memory") == "memory":
            s.reset()
    community._s3_unhydrated = False
    community._s3_next_retry = 0.0
    community._LAST_ERROR = None
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
def test_observe_hashes_token_and_folds_to_aggregates():
    _donate("raw-device-42")
    # hashed id lands ONLY inside the device-count sets — the per-day
    # traversal rollup now (the all-time device set is gone: the shared
    # donation ledger's own device index counts contributors)
    today = time.strftime("%Y-%m-%d", time.gmtime())
    assert _tok("raw-device-42") in community._DAYS[today]["devices"]
    blob = json.dumps(community._snapshot())
    assert "raw-device-42" not in blob
    assert "77.209" not in blob, "raw 5dp coordinates must not persist"


def test_no_per_trip_rows_can_exist_at_rest():
    """The whole point of the refactor: after donations, every persisted
    structure is a counter/bucket — there is no list a reader could walk
    trip-by-trip or chain cell-by-cell."""
    for dev in ("a", "b", "c"):
        _donate(dev, coords=[[77.20, 28.60], [77.21, 28.61], [77.22, 28.62]])
    assert not hasattr(community, "_obs"), "per-trip store must not exist"
    snap = community._snapshot()
    assert set(snap) == {"v", "cells", "days", "hours",
                       "reports", "reviews"}
    # the snapshot cannot carry an ordered trip: cell aggregates store
    # unordered sets and scalar counters only
    for cell, v in snap["cells"].items():
        assert isinstance(v["trips"], int)
        assert isinstance(v["dev_all"], list)  # a device SET, serialized
        assert "coords" not in v and "chain" not in v and "order" not in v


def test_snapshot_round_trip_preserves_aggregates(tmp_path, monkeypatch):
    import pathlib
    monkeypatch.setattr(community, "_FILE",
                        pathlib.Path(tmp_path) / "community.json")
    monkeypatch.undo()          # let the real _save write the file
    for dev in ("a", "b", "c"):
        _donate(dev)
    community._save()
    # the snapshot persists the traversal projection (per-day/day rollups,
    # corridors) — NOT the public ledger, which lives in v2.store.TRIPS
    before = ([(r["day"], r["trips"], r["contributors"])
               for r in community.contributors_detail()],
              len(community.corridors()), len(community._HOURS))
    for d in (community._CELLS, community._DAYS, community._HOURS):
        d.clear()
    community._loaded = False
    community._load()
    after = ([(r["day"], r["trips"], r["contributors"])
              for r in community.contributors_detail()],
             len(community.corridors()), len(community._HOURS))
    assert before == after and before[0][0][1] == 3


def test_v1_snapshot_migrates_cells_rows_and_drops_points_rows():
    """Legacy snapshots fold once, then the rows are gone: 'cells' rows
    fold into aggregates; 'points' rows (pre-trim era) are dropped —
    folding endpoints that were never trimmed would preserve exactly
    what the trim exists to erase."""
    now = time.time()
    migrated = community._apply({"obs": [
        {"ts": now, "vehicle": "bus", "duration_s": 600.0,
         "dose_ug": 30.0, "avoided_ug": 0.0, "contributor": "dev-a",
         "km": 0.4, "cells": [[77.2090, 28.6300]]},
        {"ts": now, "vehicle": "bus", "duration_s": 600.0,
         "dose_ug": 30.0, "avoided_ug": 0.0, "contributor": "dev-b",
         "points": [[77.2090, 28.6300], [77.2091, 28.6301]]},
    ]})
    assert migrated is True
    day = time.strftime("%Y-%m-%d", time.gmtime(now))
    assert community._DAYS[day]["trips"] == 1   # only the cells row folded
    assert _tok("dev-a") in community._DAYS[day]["devices"]  # hashed in


def test_report_stores_no_contributor():
    community.report("dust", 28.63, 77.21, contributor="raw-device-9")
    assert "contributor" not in json.dumps(community._reports)


def test_report_snaps_to_street_granularity():
    """5 dp (~1 m) is a doorstep — 3 dp (~110 m) is a street warning."""
    community.report("dust", 28.63154, 77.21679, contributor=None)
    r = community._reports[-1]
    assert r["lat"] == 28.632 and r["lon"] == 77.217


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
        _mk_fold(old, dev)
    assert community.corridors() == []
    # a single fresh traversal refreshes the window but k still decides
    _mk_fold(time.time(), "device-d")
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


def test_field_samples_stale_traversals_dont_publish():
    """fresh-window semantics: >=3 devices each with a fresh traversal —
    devices that only ever donated >72 h ago don't count."""
    old = time.time() - 73 * 3600
    for dev in ("dev-old-a", "dev-old-b"):
        _mk_fold(old, dev)
    _donate("dev-fresh")
    assert community.corridor_field_samples() == []


# --- response shape (the /community page contract) -------------------------
def test_totals_reads_the_shared_ledger():
    """totals() answers from the SAME donation ledger /v2/city and
    /admin serve (v2.store TRIPS + LEDGER) — one source of truth, so
    the public surfaces can never diverge again. The traversal
    projection this module keeps (community.observe's fold) is a
    different dataset and must NOT inflate the ledger numbers."""
    for i, dev in enumerate(("a", "b", "c")):
        _v2store.TRIPS.record_trip(
            [f"cell{i % 2}"], {"mode": "bus", "distance_km": 1.7,
                               "dose_ug": 30.0, "avoided_ug": 5.0},
            _tok(dev))
        _v2store.LEDGER.record(_tok(dev), {"distance_km": 1.7})
    t = community.totals()
    expected = {"obs_total", "obs_today", "today", "contributors",
                "km_today", "dose_ug_today", "avoided_ug_today",
                "avoided_ug_all", "active_reports", "modes_today",
                "latest_obs_age_min"}
    assert expected <= set(t)
    assert t["obs_total"] == 3 and t["obs_today"] == 3
    assert t["contributors"] == 3
    assert t["km_today"] > 0 and t["modes_today"] == {"bus": 3}
    assert t["avoided_ug_all"] == 15.0 and t["avoided_ug_today"] == 15.0
    assert t["today"] == time.strftime("%Y-%m-%d", time.gmtime())
    assert t["latest_obs_age_min"] is not None
    assert "ledger" in t["basis"] and "no per-trip" in t["basis"]
    assert t["source"] == "trip_aggregates"
    # a traversal-only fold (no TRIPS write) is corridor projection
    # data, not a shared-trip count — the ledger must not move
    _donate("coord-only-donor")
    assert community.totals()["obs_total"] == 3


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
        _mk_fold(now, dev)
    for dev in ("dev-c", "dev-d", "dev-e"):        # prev hour: k=3 -> shown
        _mk_fold(now - 3700, dev)
    rows = community.recent_obs(20)
    assert len(rows) == 1
    assert rows[0]["trips"] == 3 and rows[0]["devices"] == 3


def test_recent_obs_counts_devices_not_trips():
    """Three donations from ONE device in the same hour is k=1, not
    k=3 — trips count alone must never publish the bucket."""
    now = time.time()
    for _ in range(3):
        _mk_fold(now, "same-dev")
    assert community.recent_obs(20) == []


# --- endpoint-hiding trim (doc 07 §3, enforced server-side) -------------------
def test_observe_untrimmed_caller_gets_endpoint_trim():
    """An untrimmed caller (e.g. a client posting its full planned
    polyline incl. home and destination) gets the same privacy pipeline
    /v2/trip runs: first+last ~300 m can never persist even at cell
    granularity."""
    # 2.0 km straight north, ~51 m spacing, through exact cell centers
    path = [[77.2100, 28.6300 + i * 0.00046] for i in range(40)]
    community.observe(vehicle="auto", coords=path, duration_s=480.0,
                      dose_ug=40.0, avoided_ug=None,
                      contributor="untrimmed-caller")
    lats = {round(c[1], 3) for c in community._CELLS}
    assert 28.630 not in lats, "origin cell persisted — trim missing"
    assert 28.650 not in lats, "destination cell persisted — trim missing"
    assert lats == {28.635, 28.640, 28.645}, lats
    km = sum(d["km"] for d in community._DAYS.values())
    assert 1.0 < km < 1.6, km


def test_observe_privacy_trimmed_skips_second_trim():
    """v2/trip donates already-trimmed `kept` points — observe() must not
    shave another 300 m off them (would silently shorten every real
    donation's stored km by ~0.6 km)."""
    _donate("pre-trimmed")  # helper passes privacy_trimmed=True
    assert community._CELLS, "pre-trimmed payload must keep its cells"
    assert sum(d["km"] for d in community._DAYS.values()) > 0


def test_corridor_rows_carry_est_basis():
    """avg_dose_ug is traversal-implied, not an instrument read — the
    claims audit requires the estimate basis on the wire."""
    for dev in ("device-a", "device-b", "device-c"):
        _donate(dev)
    out = community.corridors()
    assert out and out[0]["avg_dose_basis"] == "est. from donated trips"


def test_journeys_per_hour_reads_hour_buckets():
    now = time.time()
    for dev in ("a", "b"):
        _mk_fold(now, dev)
    _mk_fold(now - 3700, "c")
    out = community.journeys_per_hour(3)
    cur, prev = int(now // 3600), int((now - 3700) // 3600)
    expect = [0] * 3
    expect[2] = 2
    i = 2 - (cur - prev)
    if 0 <= i < 3:
        expect[i] += 1
    assert out == expect


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


def test_review_note_coords_redacted_at_ingest():
    """The one free-text write surface must not persist raw lat/lon a
    user types in ('my stop at 28.6315,77.2167 is dusty')."""
    community._reviews.clear(); community._loaded = True
    community.add_review(stars=5,
                         note="my stop at 28.6315,77.2167 is dusty",
                         build="a")
    r = community._reviews[-1]
    assert "28.6315" not in r["note"] and "77.2167" not in r["note"]
    assert "28.63" in r["note"] and "77.22" in r["note"]  # ~1 km survives
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


def test_feedback_rate_map_stays_bounded_under_flood():
    """_review_rate must evict least-recent hosts past the cap — a flood
    of distinct fresh IPs would otherwise grow it unboundedly (hostile
    read §7: the stale-only sweep removed nothing fresh)."""
    import time as _t
    from fastapi.testclient import TestClient
    from main import app, _review_rate
    _review_rate.clear()
    now = _t.time()
    for i in range(5050):                        # all fresh — none stale
        _review_rate[f"10.0.{i // 255}.{i % 255}"] = [now - i]
    c = TestClient(app)
    r = c.post("/v2/feedback", json={"stars": 4})
    assert r.status_code in (200, 429)
    assert len(_review_rate) <= 5000 + 1         # bounded, not cleared
    _review_rate.clear()


# --- junk donations never enter the ledger -------------------------------------
def test_observe_empty_or_garbage_coords_rejected():
    """A donation folding to zero usable cells is not a donation."""
    before = sum(d["trips"] for d in community._DAYS.values())
    for bad in ([], None, ["x"], [["x", "y"]]):
        out = community.observe(vehicle="car", coords=bad,
                                duration_s=600, dose_ug=10,
                                avoided_ug=None, contributor="junk",
                                privacy_trimmed=True)
        assert out["stored"] is False
    assert sum(d["trips"] for d in community._DAYS.values()) == before


def test_observe_negative_metrics_dropped_not_stored():
    _donate("neg-check", dose_ug=-5.0, avoided_ug=-1.0)
    # negative doses are physically impossible — they fold as unknown,
    # never as numbers that would drag the aggregates down
    day = time.strftime("%Y-%m-%d", time.gmtime())
    assert community._DAYS[day]["dose_sum"] == 0
    assert community._DAYS[day]["avoided_sum"] == 0
    assert community._DAYS[day]["trips"] == 1
    assert all(v["vals"] == [] for v in community._CELLS.values())


def test_report_bad_kind_rejected():
    out = community.report("hurricane", 28.63, 77.21, contributor=None)
    assert out["stored"] is False
    assert not community._reports


# --- snapshot durability — hydrate merges, a failed S3 hydrate can't clobber ---
def test_hydrate_merges_instead_of_replacing():
    """The old wholesale _hydrate overwrote live stores: a donation
    folded while the S3 warm-up was still running vanished silently
    (the DDB ledger kept it; the community projection lost it forever).
    Hydrate is now a UNION — live folds survive the snapshot."""
    _donate("live-dev")
    today = time.strftime("%Y-%m-%d", time.gmtime())
    before = community._DAYS[today]["trips"]
    community._hydrate({"v": 2, "days": {
        today: {"trips": 10, "km": 42.0,
                "devices": ["old-1", "old-2"]}}})
    d = community._DAYS[today]
    assert d["trips"] == before + 10
    assert d["km"] > 42.0                    # snapshot km + live km
    assert _tok("live-dev") in d["devices"]  # live donor kept
    assert {"old-1", "old-2"} <= d["devices"]


def test_failed_s3_hydrate_stays_retryable_and_never_puts(
        tmp_path, monkeypatch):
    """The prod clobber mechanism: _load() caught every S3 error and
    latched _loaded on an EMPTY store — each later _save() then PUT a
    near-empty snapshot over the durable one. Now a transient failure
    stays retryable on a gap, lands in _LAST_ERROR, and _save()
    refuses to PUT while unhydrated."""
    puts = []

    class BoomS3:
        def get_object(self, **kw):
            raise RuntimeError("network down")

        def put_object(self, **kw):
            puts.append(kw)

    monkeypatch.undo()                       # restore the real _save
    monkeypatch.setattr(community, "_FILE",
                        tmp_path / "community.json")
    monkeypatch.setattr(community, "_s3", lambda: BoomS3())
    monkeypatch.setattr(community, "_last_s3_put", 0.0)
    community._loaded = False

    community._load()                        # boot during an S3 outage
    assert community._loaded is True
    assert community._s3_unhydrated is True
    assert "RuntimeError" in (community._LAST_ERROR or "")

    community._save()                        # must NOT PUT the empty
    assert puts == []                        # store over the real one

    class GoodS3(BoomS3):
        def get_object(self, **kw):
            return {"Body": io.BytesIO(json.dumps(
                {"v": 2, "days": {"2026-10-01": {"trips": 7}},
                 "reports": []}).encode())}

    community._s3_next_retry = 0.0           # the gap elapses → retry
    monkeypatch.setattr(community, "_s3", lambda: GoodS3())
    community._load()
    assert community._s3_unhydrated is False
    assert community._DAYS["2026-10-01"]["trips"] == 7
    community._save()
    assert puts, "a landed hydrate reopens PUTs"
