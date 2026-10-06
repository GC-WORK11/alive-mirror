"""Engine-arm contention: the cold-task gaps the live probe exposed.

Measured on prod (two tasks behind the NLB, 2026-10-04 ~11:03 UTC):
a fresh task's first raster sweep crawled ~45 s through live-krige
field reads while _ENG_BUSY was held — every concurrent arm took the
'already in flight' branch, found edges_priced=0 (no last pricing
existed), and silently served plans with zero engine rows. Not a
timeout — silent absence.

These tests pin the two bounds now in place:
  * unpriced busy arms JOIN the in-flight sweep (bounded by
    ENG_BUSY_JOIN_S inside the 8 s arm budget) instead of instantly
    dropping — priced arms still serve last pricing immediately;
  * the lattice sweep is read-latency adaptive and hard-capped by
    ENGINE_RASTER_BUDGET_S — it can never crawl for 45 s again.
"""

import os
import sys
import threading
import time


sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "core", "build"))



class _SlowField:
    """Krige-slow live field — every read costs REAL_MS."""
    REAL_MS = 0.04
    _snap_fv = None

    def _serving_snapshot(self):
        return False

    def __init__(self):
        self.calls = 0

    def value(self, lat, lon, pollutant="pm2_5"):
        self.calls += 1
        time.sleep(self.REAL_MS)
        return 90.0 + 20.0 * (lon - 77.0)

    def sigma(self, lat, lon):
        return 3.0

    def nearest_sample_km(self, lat, lon):
        return 1.0


class _StubEngine:
    """Minimal edges_priced probe surface — PyPathEngine-shaped."""
    def __init__(self, priced):
        self.edges_priced = priced


def _rw_state(v2plan):
    return (v2plan._ENG_BUSY, v2plan._ENG_DONE.is_set(),
            dict(v2plan._ENG_SOLVE))


def _stale_pricing(v2plan):
    """Force the reweight TTL stale — the busy branch only runs when
    pricing is due; a fresh _ENG_T (left by another suite test) takes
    the legitimate early-return and skips this file's branch entirely."""
    old = v2plan._ENG_T
    v2plan._ENG_T = 0.0
    return old


def test_unpriced_busy_arm_joins_in_flight(monkeypatch):
    """A second arm with edges_priced=0 waits for the holder's sweep
    (bounded), then proceeds to price — instead of instantly serving
    nothing."""
    from v2 import plan as v2plan
    monkeypatch.setattr(v2plan.deps, "field", lambda: _SlowField())
    old_busy, _old_done, _old_solve = _rw_state(v2plan)
    old_t = _stale_pricing(v2plan)
    try:
        v2plan._ENG_BUSY = True          # holder mid-sweep
        v2plan._ENG_DONE.clear()
        eng = _StubEngine(0)

        def holder_finishes():
            time.sleep(0.3)
            with v2plan._ENG_BUSY_LOCK:
                v2plan._ENG_BUSY = False
                v2plan._ENG_DONE.set()
        t = threading.Thread(target=holder_finishes)
        t.start()
        t0 = time.time()
        v2plan._engine_reweight(eng)
        elapsed = time.time() - t0
        t.join()
        assert elapsed < 2.0, (
            f"unpriced arm did not join promptly ({elapsed:.2f}s) — "
            "it must wake when the holder finishes")
        assert elapsed >= 0.25, \
            "unpriced arm returned instantly — the join never waited"
    finally:
        v2plan._ENG_BUSY, _d, _s = _rw_state(v2plan)
        v2plan._ENG_BUSY = old_busy
        v2plan._ENG_T = old_t


def test_unpriced_busy_arm_times_out_honestly(monkeypatch):
    """A holder that overruns ENG_BUSY_JOIN_S leaves the arm honest:
    bounded wait, then return (the caller drops rows this call, never
    hangs past its budget)."""
    from v2 import plan as v2plan
    monkeypatch.setattr(v2plan.deps, "field", lambda: _SlowField())
    old_busy = v2plan._ENG_BUSY
    old_join = v2plan.ENG_BUSY_JOIN_S
    old_t = _stale_pricing(v2plan)
    try:
        v2plan.ENG_BUSY_JOIN_S = 0.4
        v2plan._ENG_BUSY = True          # holder never finishes
        v2plan._ENG_DONE.clear()
        t0 = time.time()
        v2plan._engine_reweight(_StubEngine(0))
        elapsed = time.time() - t0
        assert 0.3 <= elapsed <= 2.0, \
            f"busy wait was {elapsed:.2f}s — must bound at JOIN_S"
    finally:
        v2plan._ENG_BUSY = old_busy
        v2plan.ENG_BUSY_JOIN_S = old_join
        v2plan._ENG_T = old_t


def test_priced_busy_arm_serves_immediately(monkeypatch):
    """With edges already priced the busy branch keeps its old
    behaviour — serve last pricing, no wait."""
    from v2 import plan as v2plan
    monkeypatch.setattr(v2plan.deps, "field", lambda: _SlowField())
    old_busy = v2plan._ENG_BUSY
    old_t = _stale_pricing(v2plan)
    try:
        v2plan._ENG_BUSY = True
        t0 = time.time()
        v2plan._engine_reweight(_StubEngine(903058))
        assert time.time() - t0 < 0.5, \
            "priced arm waited on the in-flight sweep"
    finally:
        v2plan._ENG_BUSY = old_busy
        v2plan._ENG_T = old_t


def test_raster_sweep_bounded_on_slow_field(monkeypatch):
    """The 45 s crawl can't recur: read-latency adapts the lattice and
    the hard cap stops the sweep inside ENGINE_RASTER_BUDGET_S."""
    from v2 import plan as v2plan
    f = _SlowField()
    old_budget = v2plan.ENGINE_RASTER_BUDGET_S
    try:
        v2plan.ENGINE_RASTER_BUDGET_S = 0.6
        t0 = time.time()
        out = v2plan._engine_field_view(f)
        elapsed = time.time() - t0
        assert elapsed < 3.0, \
            f"sweep ran {elapsed:.1f}s past a 0.6 s budget"
        # 56^2 = 3136 reads unbounded; the cap must stop far earlier
        assert f.calls < 100, \
            f"sweep made {f.calls} field reads under a 0.6 s budget"
        assert out is not None and out[0] is not None, \
            "a partial lattice must still produce a usable raster"
    finally:
        v2plan.ENGINE_RASTER_BUDGET_S = old_budget


def test_raster_adapts_down_not_up(monkeypatch):
    """A fast field keeps the full lattice — the adaptivity only ever
    trades density for time, never invents finer detail."""
    from v2 import plan as v2plan
    f = _SlowField()
    f.REAL_MS = 0.0
    t0 = time.time()
    out = v2plan._engine_field_view(f)
    assert out is not None
    assert f.calls > 3000, (
        f"fast field swept only {f.calls} reads — lattice shrank "
        "without cause")
    assert time.time() - t0 < 30.0
