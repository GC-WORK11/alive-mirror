"""Adversarial privacy fuzz for POST /v2/trip (docs/plan/07 §3).

The contract being defended: the client is assumed hostile or buggy, so
the SERVER must enforce 300 m end-trim, ~100 m thinning, 4-dp rounding,
H3-cell-only persistence, k>=3 suppression, and never let a raw
coordinate or raw device token reach the store. These tests attack that
pipeline with sub-300 m trips, duplicated points, GPS teleports,
out-of-NCR traces, 10 k-point floods and boundary-straddling geometry.

Offline: no field/network needed — /v2/trip never touches the airfield.
Run from server/:
    .venv/bin/python -m pytest tests/test_privacy_fuzz.py -v
"""
import hashlib
import math
import os
import re
import sys
import time

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient  # noqa: E402

import main  # noqa: E402
from v2 import store  # noqa: E402
from v2 import trip as v2trip  # noqa: E402

try:
    import h3 as _h3
    HAS_H3 = True
except Exception:
    _h3 = None
    HAS_H3 = False

# raise_server_exceptions=False so we can *observe* 500s instead of
# crashing the test — a 500 on hostile input is itself a finding.
client = TestClient(main.app, raise_server_exceptions=False)

H3_CELL = re.compile(r"^[0-9a-f]{15}$")
CP = (28.6315, 77.2167)


@pytest.fixture(autouse=True)
def clean_store():
    store.TRIPS.reset()
    store.ROUTES._routes.clear()
    yield
    store.TRIPS.reset()


# --- trace builders -----------------------------------------------------------
def _line(n_pts, start=(28.63, 77.20), dlat=0.0, dlon=0.0011):
    """[lon,lat]-order points (GeoJSON order, like a phone sends)."""
    return [[start[1] + i * dlon, start[0] + i * dlat] for i in range(n_pts)]


def _path_len_m(traj):
    """along-path metres of a [lon,lat] trace."""
    tot = 0.0
    for a, b in zip(traj, traj[1:]):
        tot += v2trip._hav_m(a[1], a[0], b[1], b[0])
    return tot


def _store_dump() -> str:
    """Everything the aggregates hold — the leak surface, as text."""
    return repr(store.TRIPS.__dict__)


def _cells_of_last_trip(resp):
    return resp.json()["cells_traversed"], resp.json()["points_used"]


def _post(traj, token="fuzz-device", **kw):
    body = {"device_token": token, "trajectory": traj,
            "summary": {"mode": "car", "distance_km": 5.0, "dose_ug": 42.0}}
    body.update(kw)
    return client.post("/v2/trip", json=body)


# --- endpoint hiding ----------------------------------------------------------
def test_sub_300m_trip_contributes_no_cells():
    """A ~200 m trip must deposit ZERO cells and ZERO tokens — there is
    no 'middle' once both 300 m ends are dropped."""
    traj = _line(8, dlon=0.0003)  # ~8 × ~29 m ≈ 200 m
    assert _path_len_m(traj) < 300
    r = _post(traj, token="short-trip-tok")
    assert r.status_code == 200
    cells, used = _cells_of_last_trip(r)
    assert used == 0 and cells == 0
    assert store.TRIPS.snapshot_cells() == {}, \
        "sub-300m trip leaked a cell into the store"


def test_trip_shorter_than_two_trims_keeps_nothing():
    """~500 m total < 600 m of combined trim → still nothing personal."""
    traj = _line(20, dlon=0.0003)  # ~550 m
    total = _path_len_m(traj)
    assert 300 < total < 600
    r = _post(traj, token="mid-trip-tok")
    assert r.status_code == 200
    assert r.json()["points_used"] == 0
    assert store.TRIPS.snapshot_cells() == {}


def test_trim_boundary_straddle():
    """Points just inside 300 m are dropped; just outside are kept —
    boundary discipline at both ends of the path."""
    # ~28.9 m per step; cum distances: 0, 28.9, ..., 867 m total (31 pts)
    traj = _line(31, dlon=0.000296)
    kept, ta, tb = v2trip.privacy_pipeline(traj)
    assert kept, "expected a kept middle on a ~870 m trace"
    # no kept point may sit <300 m along-path from either raw end
    cum = 0.0
    for a, b in zip(traj, traj[1:]):
        cum += v2trip._hav_m(a[1], a[0], b[1], b[0])
        la, lo = b[1], b[0]
        if (round(la, 4), round(lo, 4)) in kept:
            assert cum >= 290, f"kept point only {cum:.0f} m from start"
            assert _path_len_m(traj) - cum >= 290, \
                f"kept point only {_path_len_m(traj)-cum:.0f} m from end"
    assert ta >= 290 and tb >= 290


def test_first_and_last_points_never_persisted():
    """The raw endpoints (home/office — the identifying bits) must not
    survive into the store even at 4-dp precision."""
    home = [77.2167, 28.6315]          # exact raw start, 4 dp
    traj = [home] + _line(30, start=(28.6315, 77.2167), dlon=0.0011)
    r = _post(traj)
    assert r.status_code == 200
    dump = _store_dump()
    assert "28.6315" not in dump and "77.2167" not in dump
    last = traj[-1]
    assert f"{last[1]:.4f}" not in dump and f"{last[0]:.4f}" not in dump


# --- thinning / shape attacks ---------------------------------------------------
def test_duplicate_points_collapse():
    """Every point sent 4× must not inflate cells or defeat thinning."""
    single = _line(40, dlon=0.0008)
    dup = [p for p in single for _ in range(4)]
    kept1, _, _ = v2trip.privacy_pipeline(single)
    kept2, _, _ = v2trip.privacy_pipeline(dup)
    assert len(kept2) <= len(kept1) + 1  # boundary effect only
    r = _post(dup, token="dup-tok")
    assert r.status_code == 200
    assert r.json()["points_used"] <= len(kept1) + 1


def test_10k_point_trace_thins_and_caps():
    """10 000-point flood: parse cap + ~100 m thinning must hold — the
    store sees a handful of cells, never the flood."""
    traj = _line(10_000, dlon=0.00011)   # ~10 m steps, ~100 km path
    r = _post(traj, token="flood-tok")
    assert r.status_code == 200
    body = r.json()
    assert body["points_used"] <= v2trip.MAX_POINTS
    kept, _, _ = v2trip.privacy_pipeline(traj[: v2trip.MAX_POINTS])
    assert body["points_used"] == len(kept)
    # thinning: consecutive kept points >= ~84 m apart (100 m minus the
    # worst-case 4-dp rounding shift of ~8 m per endpoint)
    for a, b in zip(kept, kept[1:]):
        d = v2trip._hav_m(a[0], a[1], b[0], b[1])
        assert d >= 80, f"thinning broke: kept pair {d:.0f} m apart"
    # …and nothing raw persisted
    assert "77.20" not in _store_dump()


def test_gps_teleport_noise_cells_are_h3_only():
    """A GNSS jump 40 km out-and-back mid-trace: the spike points become
    cells like any other. Assert (a) nothing raw persists, (b) cells are
    valid H3 — and record whether outlier cells are filtered at all."""
    traj = _line(40, dlon=0.0011)
    spike = [traj[20][0] + 0.45, traj[20][1]]       # ~43 km east
    traj = traj[:21] + [spike] + traj[21:]
    r = _post(traj, token="noise-tok")
    assert r.status_code == 200
    snap = store.TRIPS.snapshot_cells()
    assert snap
    for key in snap:
        if HAS_H3:
            assert _h3.is_valid_cell(key), f"non-H3 store key {key!r}"
        assert "28." not in key and "77." not in key
    if HAS_H3:
        far = [k for k in snap
               if v2trip._hav_m(28.63, 77.20,
                                *_h3.cell_to_latlng(k)) > 20_000]
        # FINDING (not a privacy break): no outlier rejection — teleport
        # cells land in the aggregate. Tracked in test-report.md.
        print(f"\n[info] {len(far)} outlier cell(s) stored from GNSS "
              f"spike: {far[:3]}")


def test_trace_crossing_outside_ncr():
    """Delhi → well outside the NCR bbox. Cells still become H3 (global
    scheme) — but document that nothing geo-fences the aggregation."""
    traj = _line(60, start=(28.63, 77.20), dlat=-0.012, dlon=-0.008)
    r = _post(traj, token="ncr-crosser")
    assert r.status_code == 200
    snap = store.TRIPS.snapshot_cells()
    assert snap
    if HAS_H3:
        outside = [k for k in snap
                   if not (28.20 <= _h3.cell_to_latlng(k)[0] <= 28.95 and
                           76.80 <= _h3.cell_to_latlng(k)[1] <= 77.90)]
        print(f"\n[info] {len(outside)}/{len(snap)} cells lie outside "
              f"NCR bbox — stored unfiltered (see test-report.md)")


def test_every_kept_point_is_4dp_rounded():
    """Precision ceiling: kept points carry at most 4 decimals (~11 m)."""
    # jitter every point at 6+ decimals — finer than the contract allows
    traj = [[77.20 + i * 0.0008 + 0.0000007 * (i % 7),
             28.63 + 0.0000003 * (i % 5)] for i in range(50)]
    kept, _, _ = v2trip.privacy_pipeline(traj)
    assert kept
    for la, lo in kept:
        assert la == round(la, 4) and lo == round(lo, 4)


# --- store purity ---------------------------------------------------------------
def test_raw_coordinates_never_reach_store():
    """Deep-scan the aggregate object: no submitted coordinate string —
    at any precision — may appear anywhere in it."""
    pts = [[77.2013 + i * 0.0009, 28.6301 + i * 0.00001]
           for i in range(60)]
    raw_strings = {s for p in pts[::9] for s in
                   (f"{p[1]}", f"{p[0]}", f"{p[1]:.6f}", f"{p[0]:.6f}",
                    f"{p[1]:.4f}", f"{p[0]:.4f}")}
    r = _post(pts, token="scan-me")
    assert r.status_code == 200
    dump = _store_dump()
    leaked = [s for s in raw_strings if s in dump]
    assert not leaked, f"raw coordinate strings in store: {leaked[:4]}"


def test_cell_scheme_is_h3_and_keys_are_cells():
    """H3-only at rest (doc 07 §3): every persisted key is a res-8 cell,
    not a coordinate-ish string."""
    r = _post(_line(40, dlon=0.0009))
    assert r.status_code == 200
    assert r.json()["privacy"]["cell_scheme"] == "h3:8"
    for key in store.TRIPS.snapshot_cells():
        assert H3_CELL.match(key), f"store key {key!r} is not an H3 cell"
        if HAS_H3:
            assert _h3.is_valid_cell(key)


def test_token_never_stored_verbatim():
    """The device token is hashed before it can touch a store or a log."""
    token = "verbatim-device-token-should-never-appear"
    r = _post(_line(40, dlon=0.0009), token=token)
    assert r.status_code == 200
    dump = _store_dump()
    assert token not in dump
    # and the hash IS what k-counting uses (1 device, not N)
    hashed = hashlib.sha256(token.encode()).hexdigest()[:16]
    assert hashed in dump  # tokens held as hashes — that's the design
    snap = store.TRIPS.snapshot_cells()
    assert all(c["devices"] == 1 for c in snap.values())


def test_k3_suppression_threshold():
    """Corridors publish only with >=3 DISTINCT device tokens (72 h)."""
    traj = _line(40, dlon=0.0009)
    for i, tok in enumerate(("dev-a", "dev-a", "dev-b")):  # 2 distinct
        r = _post(traj, token=tok)
        assert r.status_code == 200
    snap = store.TRIPS.snapshot_cells()
    assert snap and all(c["devices"] == 2 for c in snap.values())
    assert store.TRIPS.corridors() == [], "k<3 cell became publishable"
    r = _post(traj, token="dev-c")
    assert r.status_code == 200
    pubs = store.TRIPS.corridors()
    assert pubs, "k>=3 cell stayed suppressed"
    assert all(p["devices"] >= 3 for p in pubs)
    # published rows expose aggregates only — never a token, never a coord
    for p in pubs:
        assert set(p) == {"cell", "trips", "devices", "avg_dose_ug"}
        assert H3_CELL.match(p["cell"])


def test_repeat_trip_same_token_counts_once_per_cell_per_trip():
    """Same device re-posting must not inflate 'devices' (k is distinct
    devices) but still counts as a second traversal."""
    traj = _line(40, dlon=0.0009)
    _post(traj, token="repeat-dev")
    _post(traj, token="repeat-dev")
    snap = store.TRIPS.snapshot_cells()
    assert all(c["devices"] == 1 for c in snap.values())
    assert all(c["count"] == 2 for c in snap.values())
    assert store.TRIPS.corridors() == []  # still suppressed


# --- hostile bodies ---------------------------------------------------------------
def test_malformed_summary_values_do_not_crash():
    """summary fields are floats-summed into day counters — garbage must
    be sanitized, not detonate a 500 inside the store."""
    r = client.post("/v2/trip", json={
        "device_token": "bad-summary",
        "summary": {"mode": "car", "distance_km": "not-a-number",
                    "dose_ug": {"nested": 1}},
        "trajectory": _line(40, dlon=0.0009)})
    assert r.status_code in (200, 400, 422), \
        f"malformed summary → {r.status_code} (should sanitize or 4xx)"


def test_out_of_range_coords_not_silently_stored():
    """lat=999 parses as a float and h3 wraps it onto a South-Atlantic
    cell — no range check, so garbage geo lands in the aggregates as a
    'real' traversal. Assert it is dropped or the request 4xx'd."""
    if not HAS_H3:
        pytest.skip("h3 not installed")
    traj = _line(40, dlon=0.0009)
    traj[20] = [999.0, 999.0]
    r = _post(traj, token="bad-geo")
    assert r.status_code in (200, 400, 422)
    if r.status_code != 200:
        return
    wrapped = _h3.latlng_to_cell(999.0, 999.0, 8)   # (-81,-81) South Atlantic
    snap = store.TRIPS.snapshot_cells()
    assert wrapped not in snap, (
        f"out-of-range coordinate became stored cell {wrapped} "
        f"({_h3.cell_to_latlng(wrapped)}) — no geo validation in _parse")


def test_garbage_trajectory_shapes():
    """None / string / mixed-garbage trajectories must not crash and
    must not write cells."""
    for bad in (None, "not-a-traj", 42, [{"x": 1}, ["a", "b"], []]):
        r = _post(bad, token="garbage")
        assert r.status_code in (200, 400, 422), \
            f"trajectory={bad!r} → {r.status_code}"
    assert store.TRIPS.snapshot_cells() == {}


def test_summary_extra_fields_dropped():
    """A hostile client stuffing PII into summary: only the whitelisted
    counters may persist — 'name'/'phone' die at the sanitizer."""
    r = client.post("/v2/trip", json={
        "device_token": "pii-stuffer",
        "summary": {"mode": "car", "distance_km": 3.0,
                    "name": "Alice Sharma", "phone": "9810098100",
                    "home": "C-42 Defence Colony"},
        "trajectory": _line(40, dlon=0.0009)})
    assert r.status_code == 200
    dump = _store_dump()
    for leak in ("Alice", "9810098100", "Defence", "name", "phone", "home"):
        assert leak not in dump, f"summary field leaked into store: {leak}"


def test_non_dict_body_rejected_honestly():
    """A JSON array / string body gets a validation 4xx, not a 500."""
    for bad in ([1, 2, 3], "hello", 42):
        r = client.post("/v2/trip", json=bad)
        assert r.status_code in (400, 422), \
            f"body={bad!r} → {r.status_code}, expected honest 4xx"


def test_empty_body_is_harmless():
    """{} records an empty trip: 0 cells, nothing personal, honest 200."""
    r = client.post("/v2/trip", json={})
    assert r.status_code == 200
    assert r.json()["cells_traversed"] == 0
    assert store.TRIPS.snapshot_cells() == {}


def test_response_echoes_no_raw_data():
    """The response itself must reflect only privacy-safe numbers."""
    traj = _line(40, dlon=0.0009)
    token = "echo-check-token"
    r = _post(traj, token=token)
    assert r.status_code == 200
    text = r.text
    assert token not in text
    for p in traj:
        assert f"{p[1]}" not in text and f"{p[0]}" not in text
