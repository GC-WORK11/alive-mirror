"""Priced = displayed, under dedupe — the proof the demo rests on.

Every engine row carries two dose surfaces by design:
  * engine_dose_ug — the µg the A* actually summed over priced edges
    (the exact quantity the path choice minimized; ranking keys on it);
  * dose.{lo,mid,hi} — the shared raster band through exposure.dose,
    the same dose model every other row on screen shows.

For the least-smoke claim to be honest the two must be the SAME
integrand measured two ways — same concentration raster the edges
were priced against (_ENG_PACK), same microenv ratio, same VE, same
total travel time — not two models that happen to disagree. These
tests pin that contract on the real shipped graph:

  * per-mode priced factors (routegraph.MODE_ME / MODE_VE) equal the
    display factors (exposure.MICROENV / VENTILATION_LPM via the
    option row's microenv key) for every ENGINE_MODES mode;
  * displayed dose.mid ≈ engine_dose_ug — exactly under a uniform
    field (the allocation difference cancels), within a documented
    residual under a gradient (per-edge len/speed timing vs the
    uniform-speed sample allocation, plus ~250 m sample-vs-edge
    raster reads — the integrand itself is identical);
  * a memo-hit repeat (dedupe 5805620: one A* per OD+pricing epoch)
    serves byte-identical dose fields — it returns the owner's prim
    map verbatim and re-derives the band on the same _ENG_PACK;
  * the fast paint (alts=False) and the full plan's engine arm
    (alts=True) show identical primary rows — same memo key, same
    prim dicts, same raster.

Known residual (measured live ~±2%, asserted <=10% here): priced
timing is per-edge (len_m / edge speed); display timing apportions
the same total duration by sampled length. Both sum to the path's
duration — only the correlation of concentration with per-segment
time differs. The displayed band is deliberately the shared model so
engine and router rows stay comparable; engine_dose_ug ships on the
row verbatim so nothing is hidden.
"""

import gzip
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "core", "build"))

import exposure            # noqa: E402
import routegraph          # noqa: E402

BLOB_PATH = os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "data", "route_graph.bin.gz")

OD = (28.6315, 77.2167, 28.5479, 77.2511)   # CP → Nehru Place

# the dose surfaces an engine row must agree on
_DOSE_FIELDS = ("lo", "mid", "hi", "avg_conc_ugm3", "coverage")


class _UniformField:
    """Live-only field shape (prod: no snapshot file) — constant conc."""
    _snap_fv = None

    def _serving_snapshot(self):
        return False

    def value(self, lat, lon, pollutant="pm2_5"):
        if not (28.1 <= lat <= 29.0 and 76.7 <= lon <= 78.0):
            return None
        return 100.0

    def sigma(self, lat, lon):
        return 5.0

    def nearest_sample_km(self, lat, lon):
        return 1.0


class _GradientField(_UniformField):
    """West→east gradient — nonzero conc-vs-speed correlation."""
    def value(self, lat, lon, pollutant="pm2_5"):
        if not (28.1 <= lat <= 29.0 and 76.7 <= lon <= 78.0):
            return None
        return 90.0 + 20.0 * (lon - 77.0)


@pytest.fixture(scope="module")
def graph_blob():
    if not os.path.exists(BLOB_PATH):
        pytest.skip("route_graph.bin.gz not shipped")
    with gzip.open(BLOB_PATH, "rb") as fh:
        return fh.read()


@pytest.fixture
def engine_env(monkeypatch, graph_blob):
    """Deterministic engine state: fresh PyPathEngine priced on the
    test field's own raster, clean memo, restored globals after."""
    del graph_blob  # blob needed only so the graph exists on disk
    from v2 import plan as v2plan
    eng = routegraph.PyPathEngine(routegraph.load_blob())
    monkeypatch.setattr(v2plan, "_engine", lambda: eng)
    old_t, old_pack = v2plan._ENG_T, v2plan._ENG_PACK
    old_solve = dict(v2plan._ENG_SOLVE)
    v2plan._ENG_T = 0.0
    v2plan._ENG_PACK = None
    v2plan._ENG_SOLVE.clear()
    yield v2plan, eng
    v2plan._ENG_T, v2plan._ENG_PACK = old_t, old_pack
    v2plan._ENG_SOLVE.clear()
    v2plan._ENG_SOLVE.update(old_solve)


def test_engine_factor_parity(graph_blob):
    """The priced me/ve tables are the display tables — a row whose
    factors drifted would silently under- or over-state the dose the
    path actually minimized."""
    from v2 import plan as v2plan
    del graph_blob
    for mode, _label in v2plan.ENGINE_MODES:
        microenv_key = v2plan._MODES[mode][2]
        me_disp = exposure.MICROENV[microenv_key]
        ve_disp = exposure.VENTILATION_LPM[microenv_key]
        assert routegraph.MODE_ME[mode] == me_disp, \
            f"{mode}: priced microenv {routegraph.MODE_ME[mode]} " \
            f"!= displayed {me_disp} ({microenv_key})"
        assert routegraph.MODE_VE[mode] == ve_disp, \
            f"{mode}: priced VE {routegraph.MODE_VE[mode]} " \
            f"!= displayed {ve_disp} ({microenv_key})"


def test_priced_equals_displayed_uniform(engine_env, monkeypatch):
    """Uniform field: concentration identical on every edge and every
    sample — the only honest answer is priced == displayed (up to
    float). Any wire bug (wrong raster, wrong VE, double-counted
    microenv) diverges immediately."""
    v2plan, _eng = engine_env
    monkeypatch.setattr(v2plan.deps, "field", lambda: _UniformField())
    opts = v2plan._engine_options(*OD, "car", None, alts=False)
    assert opts, "engine emitted no rows on a priced uniform field"
    for o in opts:
        ed = o["engine_dose_ug"]
        mid = o["dose"]["mid"]
        assert mid is not None
        assert abs(mid - ed) <= max(0.5, 0.02 * ed), (
            f"{o['mode']}: displayed {mid} vs priced {ed} under a "
            f"uniform field — the dose surfaces diverged")
        # the band is real: sigma raster exists, lo <= mid <= hi
        assert o["dose"]["lo"] <= mid <= o["dose"]["hi"]
        assert o["dose"]["coverage"] == 1.0


def test_priced_displayed_coupled_gradient(engine_env, monkeypatch):
    """Gradient field: the two surfaces differ only by time-allocation
    (per-edge speed vs uniform-speed) and sample positions on the same
    raster — coupled within a small documented residual, never a
    factor-level divergence."""
    v2plan, _eng = engine_env
    monkeypatch.setattr(v2plan.deps, "field", lambda: _GradientField())
    opts = v2plan._engine_options(*OD, "car", None, alts=True)
    assert opts
    for o in opts:
        ed = o["engine_dose_ug"]
        mid = o["dose"]["mid"]
        assert mid is not None
        assert abs(mid - ed) <= max(1.0, 0.10 * ed), (
            f"{o['label']}: displayed {mid} vs priced {ed} — "
            f"residual past the documented time-allocation band")


def test_memo_hit_serves_identical_rows(engine_env, monkeypatch):
    """Dedupe: a repeat call on the same OD+epoch must hit the memo —
    zero new A* solves, byte-identical dose surfaces. Serving a
    re-solved (different) path under a memo hit would break the
    one-solve-per-epoch contract."""
    v2plan, eng = engine_env
    monkeypatch.setattr(v2plan.deps, "field", lambda: _GradientField())
    calls = {"n": 0}
    real_query = eng.query

    def spy(*a, **kw):
        calls["n"] += 1
        return real_query(*a, **kw)
    monkeypatch.setattr(eng, "query", spy)

    first = v2plan._engine_options(*OD, "car", None, alts=False)
    owner_solves = calls["n"]
    assert first and owner_solves > 0
    second = v2plan._engine_options(*OD, "car", None, alts=False)
    assert calls["n"] == owner_solves, \
        "memo-hit re-solved the OD — dedupe is not sharing the prim map"
    assert len(second) == len(first)
    for o1, o2 in zip(first, second):
        for f in ("mode", "label", "geometry", "distance_km", "eta_s",
                  "engine_dose_ug", "duration_model"):
            assert o2.get(f) == o1.get(f), f"memo-hit changed {f}"
        for f in _DOSE_FIELDS:
            assert o2["dose"].get(f) == o1["dose"].get(f), \
                f"memo-hit changed displayed dose.{f}"


def test_fast_and_full_share_priced_primaries(engine_env, monkeypatch):
    """fast=True (alts=False, the early paint) and the full plan arm
    (alts=True) draw from the same ('prim', OD, epoch) memo — the
    fast row IS the priced primary the full response later shows."""
    v2plan, _eng = engine_env
    monkeypatch.setattr(v2plan.deps, "field", lambda: _GradientField())
    fast = v2plan._engine_options(*OD, "car", None, alts=False)
    full = v2plan._engine_options(*OD, "car", None, alts=True)
    assert fast and full
    fast_by_mode = {o["mode"]: o for o in fast}
    prim_by_mode = {o["mode"]: o for o in full
                    if not o.get("alternative_index")}
    assert set(fast_by_mode) == set(prim_by_mode)
    for mode, fo in fast_by_mode.items():
        po = prim_by_mode[mode]
        for f in ("geometry", "distance_km", "eta_s", "engine_dose_ug"):
            assert po.get(f) == fo.get(f), \
                f"{mode}: fast row diverged from full primary on {f}"
        for f in _DOSE_FIELDS:
            assert po["dose"].get(f) == fo["dose"].get(f)
