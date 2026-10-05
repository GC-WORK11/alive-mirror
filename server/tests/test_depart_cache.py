"""/depart horizon cache: same OD inside one forecast fetch is served
from cache (identical numbers, explicit marker); a forecast refresh or
a different OD misses and re-solves.
"""
import asyncio

import main


def _run(coro):
    return asyncio.run(coro)


def _fake_env(monkeypatch, calls):
    async def fake_refresh():
        calls["refresh"] += 1
    monkeypatch.setattr(main, "_forecast_refresh_bounded", fake_refresh)

    async def fake_osrm(profile, lon0, lat0, lon1, lat1):
        calls["osrm"] += 1
        return {"geometry": [[77.2, 28.6], [77.0, 28.4]],
                "distance": 10000, "duration": 600}
    monkeypatch.setattr(main, "_osrm", fake_osrm)

    def fake_dose(geom, dur_s, mode, field_fn):
        calls["dose"] += 1
        return {"dose_ug": 12.0, "avg_conc_ugm3": 80.0}
    monkeypatch.setattr(main.exposure, "dose", fake_dose)

    class _F:
        _fetched_at = 1000.0
        def hour_index(self, h):
            return h if h < 24 else None
        def time_at(self, idx):
            return f"2026-10-04T{idx:02d}:00:00+05:30"
        def status(self):
            return {"hours": 24}
    monkeypatch.setattr(main, "FORECAST", _F())


OD = dict(from_lat=28.6315, from_lon=77.2167,
          to_lat=28.4595, to_lon=77.0266, vehicle="car", hours=24)


def test_depart_caches_per_forecast_epoch(monkeypatch):
    calls = {"refresh": 0, "osrm": 0, "dose": 0}
    _fake_env(monkeypatch, calls)
    main._DEPART_CACHE.clear()

    r1 = _run(main.depart(**OD))
    assert r1["now"]["dose_ug"] == 12.0
    assert "served_from_cache" not in r1
    assert calls["dose"] == 24                     # one solve per hour
    osrm_after_first = calls["osrm"]

    r2 = _run(main.depart(**OD))
    assert r2["served_from_cache"] is True
    assert r2["now"]["dose_ug"] == r1["now"]["dose_ug"]
    assert calls["osrm"] == osrm_after_first       # no re-solve
    assert calls["dose"] == 24                     # no re-eval


def test_depart_cache_invalidates_on_refresh(monkeypatch):
    calls = {"refresh": 0, "osrm": 0, "dose": 0}
    _fake_env(monkeypatch, calls)
    main._DEPART_CACHE.clear()

    _run(main.depart(**OD))
    main.FORECAST._fetched_at = 2000.0             # new forecast fetch

    r3 = _run(main.depart(**OD))
    assert "served_from_cache" not in r3
    assert calls["dose"] == 48                     # re-solved


def test_depart_cache_key_covers_od_vehicle_hours(monkeypatch):
    calls = {"refresh": 0, "osrm": 0, "dose": 0}
    _fake_env(monkeypatch, calls)
    main._DEPART_CACHE.clear()

    _run(main.depart(**OD))
    r = _run(main.depart(**{**OD, "vehicle": "bike"}))
    assert "served_from_cache" not in r            # different vehicle
    r = _run(main.depart(**{**OD, "hours": 12}))
    assert "served_from_cache" not in r            # different horizon
    r = _run(main.depart(**{**OD, "from_lat": 28.6129,
                            "from_lon": 77.2295}))
    assert "served_from_cache" not in r            # different OD
    r = _run(main.depart(**OD))
    assert r["served_from_cache"] is True          # original still warm


def test_depart_serves_field_freshness_on_hit_and_miss(monkeypatch):
    """The horizon anchors to the live field — its 'as of' rides the
    payload like /v2/day and /v2/outlook carry. A cache hit must still
    serve CURRENT stamps: a frozen age would lie."""
    calls = {"refresh": 0, "osrm": 0, "dose": 0}
    _fake_env(monkeypatch, calls)
    main._DEPART_CACHE.clear()

    r1 = _run(main.depart(**OD))
    assert "field" in r1 and "field_age_s" in r1

    # same forecast epoch -> cache hit; mutate the status surface and
    # the recomputed stamps must come through, not the cached body's
    main.FORECAST.status = lambda: {"hours": 24, "age_s": 4242}
    r2 = _run(main.depart(**OD))
    assert r2["served_from_cache"] is True
    assert r2["forecast"]["age_s"] == 4242       # recomputed at serve time
    assert "field" in r2 and "field_age_s" in r2
