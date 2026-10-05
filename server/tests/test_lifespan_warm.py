"""Boot-time warming: the field must refresh at startup, not first request.

FIELD.refresh() is request-driven; on a cold task the engine reweight
loop logged "field serves no reads" until the first /aqi (~60 s dead
time measured on a fresh Fargate task, /ecs/alive108 2026-10-04). The
lifespan now kicks the same real fetch at boot. This test stubs every
network/CPU-heavy warm target and asserts the field refresh actually
fires inside _lifespan — the rest of the suite keeps ALIVE_INGEST_IN_APP
off so no real upstream is touched.
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import main  # noqa: E402


class _FakeEngine:
    edges_priced = 903058  # priced already: warm loop exits on first try


def test_lifespan_warms_field_at_boot(monkeypatch):
    calls = {"field": 0, "fires": 0, "forecast": 0, "community": 0,
             "gazetteer": 0, "history": 0, "gtfs_kick": 0, "gtfs_compile": 0}

    async def _field_refresh(client, force=False):
        calls["field"] += 1

    async def _fires_refresh(client):
        calls["fires"] += 1

    async def _forecast_refresh(client):
        calls["forecast"] += 1

    def _community_load():
        calls["community"] += 1

    def _gaz_load():
        calls["gazetteer"] += 1
        return []

    def _history_load():
        calls["history"] += 1
        return {}

    def _engine_reweight(eng):
        return None

    monkeypatch.setattr(main.FIELD, "refresh", _field_refresh)
    monkeypatch.setattr(main.FIRES, "refresh", _fires_refresh)
    monkeypatch.setattr(main.FORECAST, "refresh", _forecast_refresh)
    monkeypatch.setattr(main.community, "_load", _community_load)
    monkeypatch.setattr(main, "http", lambda: object())
    monkeypatch.setenv("ALIVE_INGEST_IN_APP", "0")

    import routegraph
    import transit_real
    import transit_v2
    import history
    from v2 import plan as _v2plan
    from v2.gazetteer import GAZ
    monkeypatch.setattr(routegraph, "path_engine", lambda: _FakeEngine())
    monkeypatch.setattr(_v2plan, "_engine_reweight", _engine_reweight)

    def _gtfs_compile():
        calls["gtfs_compile"] += 1
        return {"metro": object(), "bus": object()}
    monkeypatch.setattr(transit_v2, "default_feeds", _gtfs_compile)

    def _gtfs_kick():
        calls["gtfs_kick"] += 1
    # ensure_loaded must be stubbed — the real one spawns a download
    # thread against crates.io/GCS mirrors, a network hit inside a unit
    # test.
    monkeypatch.setattr(transit_real, "ensure_loaded", _gtfs_kick)
    monkeypatch.setattr(transit_real, "feeds_on_disk", lambda: True)
    monkeypatch.setattr(GAZ, "_load", _gaz_load)
    monkeypatch.setattr(history, "_load", _history_load)

    async def _run():
        async with main._lifespan(main.app):
            # let the create_task'd warmers run; transit/engine go through
            # asyncio.to_thread so give them a beat of real time
            for _ in range(10):
                await asyncio.sleep(0)
            await asyncio.sleep(0.5)

    asyncio.run(_run())

    assert calls["field"] >= 1, "FIELD.refresh was never kicked at boot"
    assert calls["fires"] >= 1 and calls["forecast"] >= 1
    assert calls["community"] >= 1, "community._load never kicked at boot"
    assert calls["gazetteer"] >= 1, "GAZ._load never kicked at boot"
    assert calls["history"] >= 1, "history._load never kicked at boot"
    # transit boot-warm: the fetch/parse kick fires at boot, and with
    # feeds on disk the v2 index compile finishes before healthy
    assert calls["gtfs_kick"] >= 1, "transit_real.ensure_loaded never kicked"
    assert calls["gtfs_compile"] >= 1, "default_feeds never compiled at boot"
