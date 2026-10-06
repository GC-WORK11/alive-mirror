"""First-plan transit: the cold-boot gap the apk-v4 drive exposed.

Measured live: the FIRST /v2/plan on a fresh task painted 22 options
with no 'Metro + walk'; it appeared on re-plan. GTFS was already
compiled at boot — the gap was where the arm RAN: asyncio.to_thread
lands on the shared default executor, which the boot-warm fleet
(graph load, reprice sweeps, krige grids, static/community loads)
saturates for the first minutes of a cold task. The transit callable
queued behind that fleet until its 12 s cap elapsed →
degraded:["transit"] on exactly the request a judge sees first.

The arm now runs on its own pool (_TRANSIT_EXEC — same fix shape as
_ENG_EXEC for the engine arm) and _warm_static pre-pays the first CSA
scan (+ lazy _Grid rebuild on pickled feeds) on a canonical metro OD.

These tests pin both halves — all offline: plan_transit is a stub,
the location client is a local fake, and boot-warm starvation is
simulated by squatting every default-executor worker with sleeps.

Run from server/:
    .venv/bin/python -m pytest tests/test_transit_first_plan.py -q
"""

import asyncio
import concurrent.futures
import os
import sys
import threading
import time


sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from v2 import deps          # noqa: E402
from v2 import plan as v2plan  # noqa: E402
import transit_v2            # noqa: E402

# Canonical metro OD (same one _warm_static pre-warms):
# India Gate -> Huda City Centre, Gurugram — Yellow line end-to-end.
FROM_IG = (28.6129, 77.2295)
TO_HUDA = (28.4593, 77.0724)

# A metro journey in the shape transit_v2.plan_transit emits.
METRO_JOURNEY = {
    "mode": "metro", "duration_s": 5400.0,
    "legs": [
        {"type": "walk", "duration_s": 1500.0, "distance_m": 2100,
         "geometry": {"type": "LineString", "coordinates":
                      [[77.2295, 28.6129], [77.2137, 28.6236]]},
         "from": {"name": "origin"},
         "to": {"name": "Patel Chowk"}},
        {"type": "metro", "duration_s": 3900.0, "distance_m": 29000,
         "wait_s": 60.0, "line": "Yellow",
         "geometry": {"type": "LineString", "coordinates":
                      [[77.2137, 28.6236], [77.1500, 28.5400],
                       [77.0724, 28.4593]]},
         "from": {"name": "Patel Chowk"},
         "to": {"name": "Huda City Centre"}},
        {"type": "walk", "duration_s": 300.0, "distance_m": 400,
         "geometry": {"type": "LineString", "coordinates":
                      [[77.0724, 28.4593], [77.0724, 28.4593]]},
         "from": {"name": "Huda City Centre"},
         "to": {"name": "destination"}},
    ],
    "lines": ["Yellow"], "walk_m": 2500, "transfers": 0,
    "duration_model": "gtfs",
}


class _FakeAwsLoc:
    """Prod-signature location client: the first cold plan got its road
    rows via AWS CalculateRoutes (on-loop) and the engine's own pool —
    while the to_thread arms starved."""
    enabled = True

    async def calculate_routes(self, flat, flon, tlat, tlon,
                               travel_mode=None, alternatives=0,
                               depart_at=None):
        return [{"distance_m": 29000.0, "duration_s": 2100.0,
                 "freeflow_s": 1900.0,
                 "geometry": {"type": "LineString",
                              "coordinates": [[77.2295, 28.6129],
                                              [77.1500, 28.5400],
                                              [77.0724, 28.4593]]},
                 "steps": []}]


class _FastField:
    _snap_fv = None

    def _serving_snapshot(self):
        return False

    def value(self, lat, lon, pollutant="pm2_5"):
        return 95.0

    def sigma(self, lat, lon):
        return 15.0

    def nearest_sample_km(self, lat, lon):
        return 2.0


OSRM_RT = {"distance": 29000.0, "duration": 2100.0,
           "geometry": {"type": "LineString",
                        "coordinates": [[77.2295, 28.6129],
                                        [77.1500, 28.5400],
                                        [77.0724, 28.4593]]},
           "legs": [{"steps": []}]}


def test_first_plan_transit_survives_executor_starvation(monkeypatch):
    """The wart, reproduced: every default-executor worker is held by a
    boot-warm-style sleeper for longer than the plan window — the exact
    condition that queued the transit callable past its 12 s cap. The
    arm must still run (on its own pool) and the plan must still carry
    a real GTFS option."""
    ran_on = []

    def spy(*a, **k):
        ran_on.append(threading.current_thread().name)
        return [dict(METRO_JOURNEY)]

    monkeypatch.setattr(transit_v2, "plan_transit", spy)
    monkeypatch.setattr(deps, "field", lambda: _FastField())
    deps.set_location(_FakeAwsLoc())

    async def fake_osrm(profile, flon, flat, tlon, tlat):
        return dict(OSRM_RT)
    monkeypatch.setattr(deps, "osrm_route", fake_osrm)

    # Keep the engine arm cheap and honest — this test is about transit.
    monkeypatch.setattr(v2plan, "_engine_options", lambda *a, **k: [])
    # Shrink the plan window so the starved arms cancel promptly; the
    # transit arm still must land inside it.
    monkeypatch.setattr(v2plan, "PLAN_BUDGET_S", 6.0)

    probe_ran = []

    async def starved_first_plan():
        loop = asyncio.get_running_loop()
        # Boot-warm fleet: both workers busy longer than the plan window.
        loop.set_default_executor(concurrent.futures.ThreadPoolExecutor(
            max_workers=2, thread_name_prefix="bootwarm"))
        for _ in range(2):
            loop.run_in_executor(None, time.sleep, 5.0)

        t0 = time.monotonic()

        def probe():
            probe_ran.append(round(time.monotonic() - t0, 2))
        loop.run_in_executor(None, probe)
        return await v2plan._options_bounded(
            FROM_IG[0], FROM_IG[1], TO_HUDA[0], TO_HUDA[1],
            "car", None, None)

    try:
        options, err, missing = asyncio.run(starved_first_plan())
    finally:
        deps.set_location(None)

    assert err is None
    assert ran_on, "plan_transit never ran — the transit arm starved"
    assert all(n.startswith("alive-transit") for n in ran_on), (
        f"transit ran on {ran_on} — must be its own pool, not the "
        "starved shared executor")
    transit_rows = [o for o in options
                    if o.get("steps_source") == "gtfs"]
    assert transit_rows, "first plan carries no GTFS transit option"
    assert any(o["mode"] in ("metro", "metro+walk", "bus")
               for o in transit_rows)
    assert all(o["stations"]["board"] == "Patel Chowk"
               for o in transit_rows if o.get("stations"))
    assert "transit" not in missing
    # The starvation was real — a probe job queued on the shared
    # executor couldn't get a worker while the sleepers held them
    # (hits at ~5 s are asyncio.run's shutdown drain, after the 4 s
    # plan window closed; any hit <4.5 s means the squat never held).
    # The executor-audit lane fixed the other arms, so motor/slow rows
    # land beside transit now — nothing may be left in `missing`
    # except the stubbed engine arm.
    assert not [t for t in probe_ran if t < 4.5], (
        f"probe got a worker at {probe_ran} — the executor wasn't "
        "actually starved during the plan window; the test isn't "
        "proving anything")
    assert "slow" not in missing and "motor" not in missing
    # ...and the road rows still paint (motorized path included).
    assert any(o["mode"] == "car" for o in options)


def test_first_plan_transit_option_is_not_fabricated(monkeypatch):
    """The empty path must stay honest: no GTFS journeys on an OD means
    no transit row — the fix moves WHEN the scan runs, never WHAT it
    reports."""
    monkeypatch.setattr(transit_v2, "plan_transit", lambda *a, **k: [])
    monkeypatch.setattr(deps, "field", lambda: _FastField())
    # no station model either — transit.metro_option declines
    import transit
    monkeypatch.setattr(transit, "metro_option",
                        lambda *a, **k: None)
    out = v2plan._transit_options(
        FROM_IG[0], FROM_IG[1], TO_HUDA[0], TO_HUDA[1],
        "car", None, None)
    assert out == []


def test_warm_static_prepays_transit_scan(monkeypatch):
    """_warm_static must fire the plan arm's real callable once on the
    canonical metro OD — on the transit pool, off the shared executor —
    so the first request doesn't pay the first CSA scan + _Grid build."""
    calls = []

    def spy(flat, flon, tlat, tlon, vehicle, profile, depart_at):
        calls.append({"args": (flat, flon, tlat, tlon),
                      "thread": threading.current_thread().name})
        return []
    monkeypatch.setattr(v2plan, "_transit_options", spy)

    import main
    import routegraph
    import transit_real
    import history
    import community
    from v2.gazetteer import GAZ

    async def _noop_async(*a, **k):
        return None

    def _noop(*a, **k):
        return None

    monkeypatch.setattr(main.FIELD, "refresh", _noop_async)
    monkeypatch.setattr(main.FIRES, "refresh", _noop_async)
    monkeypatch.setattr(main.FORECAST, "refresh", _noop_async)
    monkeypatch.setattr(main, "http", lambda: object())
    monkeypatch.setattr(main.FIELD, "_fetched_at", None)
    monkeypatch.setattr(community, "_load", _noop)
    monkeypatch.setattr(community, "_name_rows", _noop)
    monkeypatch.setattr(GAZ, "_load", _noop)
    monkeypatch.setattr(history, "_load", _noop)
    monkeypatch.setattr(transit_real, "ensure_loaded", _noop)
    monkeypatch.setattr(transit_real, "feeds_on_disk", lambda: True)
    monkeypatch.setattr(transit_v2, "default_feeds",
                        lambda: {"metro": object(), "bus": object()})

    class _Eng:
        edges_priced = 903058

        def query(self, *a, **k):
            return None

    monkeypatch.setattr(routegraph, "path_engine", lambda: _Eng())
    monkeypatch.setattr(v2plan, "_engine_reweight", _noop)
    monkeypatch.setenv("ALIVE_INGEST_IN_APP", "0")
    monkeypatch.setenv("ALIVE_ARCHIVE", "0")
    monkeypatch.setenv("ALIVE_ROLLUP_MIRROR", "0")

    async def _run():
        async with main._lifespan(main.app):
            for _ in range(10):
                await asyncio.sleep(0)
            # the transit warm runs on its pool — give it a real beat
            for _ in range(20):
                if calls:
                    break
                await asyncio.sleep(0.1)

    asyncio.run(_run())

    assert len(calls) == 1, (
        f"_warm_static ran _transit_options {len(calls)} times — "
        "the first request still pays the first scan")
    assert calls[0]["args"] == (FROM_IG[0], FROM_IG[1],
                                TO_HUDA[0], TO_HUDA[1])
    assert calls[0]["thread"].startswith("alive-transit"), (
        f"transit warm ran on {calls[0]['thread']} — must be the "
        "transit pool so it can't starve behind the to_thread fleet")
