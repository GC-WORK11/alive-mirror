"""Offline tests for GET /v2/why — the 'why is it like this' lane.

No network: field refresh is a no-op, fires/forecast/snapshot inputs are
stubbed straight onto the singletons and a tmp snapshot root. Run from
server/:
    PYTHONPATH=core/build312:. .venv312/bin/python -m pytest -q tests/test_v2_why.py
"""
import gzip
import json
import os
import sys
import time
from datetime import datetime, timezone

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient  # noqa: E402

import main  # noqa: E402
from v2 import deps  # noqa: E402
from v2 import why as v2why  # noqa: E402

client = TestClient(main.app)

NOW = time.time()


def _snap(path, built_epoch, mean_pm25, vc=None, belt=None, mod=None):
    doc = {
        "schema": "alive-field/1",
        "built_epoch": built_epoch,
        "built_at": "2026-10-05T00:00:00+00:00",
        "cells": {"g8:28.6:77.2": {"pm25": mean_pm25}},
        "stats": {"mean_pm25": mean_pm25},
        "met": {"vc_m2s": vc, "blh_m": 700.0, "wind_ms": 2.0,
                "wind_deg": 300.0},
        "provenance": {
            "met": {"vc_m2s": vc, "blh_m": 700.0, "wind_ms": 2.0,
                    "wind_deg": 300.0},
            "fires": {"n_fires": belt, "belt_fires": belt,
                      "modifier": mod},
            "stations": {"n_used": 12, "n_raw": 14},
        },
    }
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as fh:
        fh.write(gzip.compress(json.dumps(doc).encode()))


@pytest.fixture()
def snap_root(tmp_path, monkeypatch):
    root = tmp_path / "snaps"
    root.mkdir()
    monkeypatch.setenv("ALIVE_SNAPSHOT_DIR", str(root))
    return str(root)


def _write_series(root, specs):
    """specs: [(hours_ago, mean_pm25, vc_m2s, belt_fires, modifier)]"""
    for h_ago, pm, vc, belt, mod in specs:
        t = NOW - h_ago * 3600
        import datetime as _dt
        d = _dt.datetime.fromtimestamp(t, tz=_dt.timezone.utc)
        _snap(os.path.join(root, f"{d:%Y/%m/%d/%H%M}.json.gz"),
              t, pm, vc=vc, belt=belt, mod=mod)


class _NoFires:
    """fires feed with nothing to say."""
    _status = "cold"
    _fires = None
    _wind_deg = None
    _fetched_at = 0.0

    def status(self):
        return {"status": "cold", "source": None, "fires": 0,
                "belt_fires": 0, "belt_frp_mw": 0.0,
                "wind_deg": None, "modifier": 1.0, "age_s": None}


class _Fires:
    def __init__(self, belt=61, frp=412.3, modifier=1.8):
        self._status = "live"
        self._wind_deg = 315.0
        self._fetched_at = NOW - 900
        self._fires = [{"lat": 30.1, "lon": 75.5, "frp": frp, "belt": True}
                       for _ in range(belt)]
        self._modifier = modifier

    def status(self):
        return {"status": "live", "source": "firms-public-csv",
                "fires": 120, "belt_fires": len(self._fires),
                "belt_frp_mw": round(sum(f["frp"] for f in self._fires), 1),
                "wind_deg": self._wind_deg, "modifier": self._modifier,
                "age_s": 900}


@pytest.fixture(autouse=True)
def quiet(monkeypatch):
    """No upstream contact inside the endpoint."""
    async def _no_field():
        return None

    async def _no_fires():
        return None
    monkeypatch.setattr(deps, "field_refresh", _no_field)
    monkeypatch.setattr(v2why, "_refresh_fires_bounded", _no_fires)


@pytest.fixture()
def wind_nw(monkeypatch):
    """Field wind blowing FROM the burn belt (NW quadrant)."""
    class F:
        def wind(self):
            return {"speed_kmh": 9.0, "from_deg": 315.0}
        def _wind_expired(self):
            return False
    monkeypatch.setattr(deps, "field", lambda: F())


@pytest.fixture()
def wind_se(monkeypatch):
    """Wind FROM the south-east — smoke cannot reach Delhi."""
    class F:
        def wind(self):
            return {"speed_kmh": 9.0, "from_deg": 150.0}
        def _wind_expired(self):
            return False
    monkeypatch.setattr(deps, "field", lambda: F())


@pytest.fixture()
def wind_calm(monkeypatch):
    class F:
        def wind(self):
            return {"speed_kmh": 1.5, "from_deg": 315.0}
        def _wind_expired(self):
            return False
    monkeypatch.setattr(deps, "field", lambda: F())


@pytest.fixture()
def wind_unknown(monkeypatch):
    class F:
        def wind(self):
            return {"speed_kmh": 0.0, "from_deg": 0.0}
        def _wind_expired(self):
            return True
    monkeypatch.setattr(deps, "field", lambda: F())


@pytest.fixture(autouse=True)
def no_snapshot_prov(monkeypatch):
    """Keep health._field_probe honest-empty unless a test opts in."""
    import health as _h
    monkeypatch.setattr(_h, "_field_probe",
                        lambda *a, **k: {"payload": {}, "age_s": None})


@pytest.fixture()
def cold_forecast(monkeypatch):
    class FC:
        _met = []
        _aq = []
        _fetched_at = 0.0

        def hour_index(self, h):
            return None

        def stagnation_detail(self, lat, lon, idx):
            return None
    import forecast
    monkeypatch.setattr(forecast, "FORECAST", FC())
    monkeypatch.setattr(v2why, "_ventilation_read",
                        v2why._ventilation_read)  # keep real fn
    return FC()


# ------------------------------------------------------------------- gates

def test_carry_gate_quadrant():
    assert v2why._carries_toward_delhi(315.0, 9.0) is True   # NW
    assert v2why._carries_toward_delhi(270.0, 9.0) is True   # W edge
    assert v2why._carries_toward_delhi(360.0, 9.0) is True   # N edge
    assert v2why._carries_toward_delhi(150.0, 9.0) is False  # SE
    assert v2why._carries_toward_delhi(200.0, 9.0) is False  # S


def test_carry_gate_speed_floor_and_unknown():
    assert v2why._carries_toward_delhi(315.0, 1.0) is False  # too calm
    assert v2why._carries_toward_delhi(None, 9.0) is None    # can't judge
    assert v2why._carries_toward_delhi(315.0, None) is True  # dir only


def test_stagnation_threshold():
    vent = {"vc_m2s": 4000.0, "blh_m": 1500, "wind_ms": 2.7,
            "factor": 0.75, "source": "forecast", "age_s": 300}
    d, ev, ct = v2why._eval_stagnation(vent)
    assert d is None and ct is None          # mixing fine — not a driver
    vent2 = {"vc_m2s": 1500.0, "blh_m": 500, "wind_ms": 3.0,
             "factor": 2.0, "source": "forecast", "age_s": 300}
    d2, ev2, ct2 = v2why._eval_stagnation(vent2)
    assert d2 and d2["kind"] == "stagnation" and ct2 is None
    assert 0 < d2["score"] <= 1


def test_stagnation_missing_is_honest():
    d, ev, ct = v2why._eval_stagnation({"vc_m2s": None})
    assert d is None and ct and ct["kind"] == "stagnation"


def test_fires_below_bar_not_claimed(wind_nw):
    d, ev, ct = v2why._eval_fires(
        _Fires(belt=4).status() | {"belt_frp_mw": 10.0},
        {"speed_kmh": 9.0, "from_deg": 315.0})
    assert d is None and ct is None          # 4 fires = background


def test_fires_wrong_wind_not_claimed(wind_se):
    d, ev, ct = v2why._eval_fires(
        _Fires(belt=80).status(),
        {"speed_kmh": 9.0, "from_deg": 150.0})
    assert d is None and ct is None
    assert ev["carrying"] is False


def test_fires_unknown_wind_cannot_tell(wind_nw):
    d, ev, ct = v2why._eval_fires(
        _Fires(belt=80).status(),
        {"speed_kmh": None, "from_deg": None})
    assert d is None and ct and ct["kind"] == "stubble_smoke"
    assert ev["carrying"] is None


def test_fires_cold_feed_cannot_tell():
    d, ev, ct = v2why._eval_fires(_NoFires().status(),
                                  {"speed_kmh": 9.0, "from_deg": 315.0})
    assert d is None and ct and ct["kind"] == "stubble_smoke"


def test_fires_admitted_when_carrying(wind_nw):
    d, ev, ct = v2why._eval_fires(
        _Fires(belt=61, frp=7.0).status(),
        {"speed_kmh": 9.0, "from_deg": 315.0})
    assert d and d["kind"] == "stubble_smoke"
    assert "61 fires" in d["evidence"] and "NW" in d["evidence"]
    assert ev["carrying"] is True


# ------------------------------------------------------------------- trend

def test_trend_rising(snap_root):
    _write_series(snap_root, [(5.0, 60, 3000, 20, 1.1),
                            (4.0, 65, 3000, 20, 1.1),
                            (3.0, 80, 2800, 25, 1.2),
                            (1.0, 130, 2000, 40, 1.5),
                            (0.5, 140, 1800, 45, 1.6)])
    series, meta = v2why._snapshot_series()
    d, ev, ct = v2why._eval_trend(series, meta)
    assert d and d["kind"] == "trend" and d["direction"] == "rising"
    assert ev["delta_ug"] >= v2why.TREND_MIN_DELTA_UG
    # the record's own shape rides along — local listing saw all 5 slots
    assert ev["n_snapshots_available"] == 5
    assert ev["span_available_h"] == pytest.approx(4.5, abs=0.1)


def test_trend_flat_not_claimed(snap_root):
    _write_series(snap_root, [(5.0, 100, 3000, 20, 1.1),
                            (3.0, 102, 3000, 20, 1.1),
                            (1.0, 104, 3000, 20, 1.1),
                            (0.5, 101, 3000, 20, 1.1)])
    d, ev, ct = v2why._eval_trend(*v2why._snapshot_series())
    assert d is None and ct is None


def test_trend_too_few_cannot_tell(snap_root):
    _write_series(snap_root, [(2.0, 100, 3000, 5, 1.0),
                            (0.5, 130, 3000, 5, 1.0)])
    d, ev, ct = v2why._eval_trend(*v2why._snapshot_series())
    assert d is None and ct and ct["kind"] == "trend"


def test_trend_stale_newest_cannot_tell(snap_root):
    _write_series(snap_root, [(5.5, 60, 3000, 5, 1.0),
                            (4.5, 65, 3000, 5, 1.0),
                            (3.8, 120, 3000, 5, 1.0),
                            (3.5, 130, 3000, 5, 1.0)])
    # 4 builds inside the window but newest 3.5h old — beyond SNAP_MAX_AGE_S
    d, ev, ct = v2why._eval_trend(*v2why._snapshot_series())
    assert d is None and ct and "old" in ct["reason"]


def test_series_s3_fallback_merges_and_dedupes(snap_root, monkeypatch):
    """Production path: local dir thin -> bucket rows fill the window,
    deduped by build time. The bucket is stubbed, not contacted."""
    _write_series(snap_root, [(1.0, 70, 3000, 5, 1.0)])
    s3_rows = [{"t": NOW - 5.0 * 3600, "pm25": 60, "vc_m2s": 3000,
                "blh_m": None, "belt_fires": 5, "modifier": 1.0},
               {"t": NOW - 4.0 * 3600, "pm25": 62, "vc_m2s": 3000,
                "blh_m": None, "belt_fires": 5, "modifier": 1.0},
               {"t": NOW - 1.0 * 3600, "pm25": 999, "vc_m2s": 3000,
                "blh_m": None, "belt_fires": 5, "modifier": 1.0}]  # dup
    # listing-derived slots are minute-floored (they come from names);
    # the local file's slot collapses onto the dup build's
    def _slot(h_ago):
        return int(NOW - h_ago * 3600) // 60 * 60
    s3_meta = {"available_ts": [_slot(5.0), _slot(4.0), _slot(1.0)]}
    monkeypatch.setattr(v2why, "_s3_series", lambda w: (s3_rows, s3_meta))
    v2why._SERIES_CACHE.update({"at": 0.0, "key": None,
                                "rows": [], "meta": {}})
    rows, meta = v2why._snapshot_series()
    assert len(rows) == 3            # local row + 2 unique bucket rows
    assert rows[-1]["pm25"] == 70    # local newest wins over the dup key
    assert meta["n_available"] == 3  # merged slots, duped build collapses


def test_snap_slot_t_parses_build_names():
    t = v2why._snap_slot_t("field/2026/10/06/0540.json.gz")
    assert t == datetime(2026, 10, 6, 5, 40,
                         tzinfo=timezone.utc).timestamp()
    # same name under a local snapshot root parses identically
    assert v2why._snap_slot_t(
        "/tmp/snaps/2026/10/06/0540.json.gz") == t
    assert v2why._snap_slot_t("field/2026/10/06/latest.json.gz") is None
    assert v2why._snap_slot_t("random.bin") is None


class _FakeS3:
    """In-memory bucket for _s3_series — keys -> raw doc bytes."""

    def __init__(self, objs):
        self._objs = objs          # {key: (last_modified_ts, bytes)}
        self.fetched = []

    def list_objects_v2(self, Bucket=None, Prefix=""):
        return {"Contents": [
            {"Key": k, "LastModified": datetime.fromtimestamp(
                lm, tz=timezone.utc)}
            for k, (lm, _) in self._objs.items()
            if k.startswith(Prefix)]}

    def get_object(self, Bucket=None, Key=None):
        self.fetched.append(Key)
        body = self._objs[Key][1]

        class _B:
            def read(self):
                return body
        return {"Body": _B()}


def _snap_doc(t, pm):
    import gzip as _gz
    doc = {"schema": "alive-field/1", "built_epoch": t,
           "stats": {"mean_pm25": pm},
           "met": {"vc_m2s": 2000.0},
           "provenance": {"met": {"vc_m2s": 2000.0}}}
    return _gz.compress(json.dumps(doc).encode())


def test_s3_series_reads_whole_window(snap_root, monkeypatch):
    """Drift-watch finding: the 4 s result-iterator deadline discarded
    the OLDEST rows while the executor still waited for every fetch —
    under-count wobble 26-32 vs ~31. Now every listed in-window key is
    fetched and every result kept; the record's count/span come from
    the listing itself."""
    import datetime as _dt
    # Fresh clock, not the module-level NOW: in a full-suite run this test
    # executes minutes after import, and _s3_series uses its own
    # time.time() — fixture rows anchored to the stale NOW drift out of
    # the 6 h window (oldest row's margin is only ~11 min).
    now = time.time()
    base = _dt.datetime.fromtimestamp(now, tz=_dt.timezone.utc)
    objs = {}
    # 30 in-window builds, one every 12 min
    for i in range(30):
        t = now - i * 720 - 60
        d = _dt.datetime.fromtimestamp(t, tz=_dt.timezone.utc)
        objs[f"field/{d:%Y/%m/%d/%H%M}.json.gz"] = (t, _snap_doc(t, 50 + i))
    # out-of-window by slot AND by pad — must not even be fetched
    old = _dt.datetime.fromtimestamp(now - 7 * 3600, tz=_dt.timezone.utc)
    objs[f"field/{old:%Y/%m/%d/%H%M}.json.gz"] = (
        now - 7 * 3600, _snap_doc(now - 7 * 3600, 10))
    # inside the slot pad but out of window — fetched, row filtered
    edge = _dt.datetime.fromtimestamp(now - 6 * 3600 - 600,
                                    tz=_dt.timezone.utc)
    objs[f"field/{edge:%Y/%m/%d/%H%M}.json.gz"] = (
        now - 6 * 3600 - 600, _snap_doc(now - 6 * 3600 - 600, 15))
    # not a build name at all — never fetched, never counted
    objs[f"field/{base:%Y/%m/%d}/manifest.json.gz"] = (now, b"{}")
    # corrupted body — slot counts it, the row drops
    bad = _dt.datetime.fromtimestamp(now - 1800, tz=_dt.timezone.utc)
    objs[f"field/{bad:%Y/%m/%d/%H%M}.json.gz"] = (now - 1800,
                                                 b"not-a-build")

    fake = _FakeS3(objs)
    import boto3
    monkeypatch.setattr(boto3, "client", lambda *a, **k: fake)
    monkeypatch.setenv("ALIVE_AIR_BUCKET", "test-bucket")
    rows, meta = v2why._s3_series(v2why.TREND_WINDOW_S)
    # all 30 in-window docs read; corrupted body drops out of the rows
    # but NOT out of the record — its slot still counts
    assert len(rows) == 30
    assert rows == sorted(rows, key=lambda r: r["t"])   # oldest->newest
    assert len(meta["available_ts"]) == 31   # 30 good + corrupt slot
    # fetched: 30 in-window + pad-edge + corrupt; skipped: 7h slot,
    # manifest (not a build name)
    assert len(fake.fetched) == 32
    assert f"field/{old:%Y/%m/%d/%H%M}.json.gz" not in fake.fetched
    assert not any("manifest" in k for k in fake.fetched)


def test_eval_trend_discloses_truncation():
    """When the read set is smaller than the record, the payload says
    so — n_snapshots is what the delta used, n_snapshots_available the
    record's true count, span_available_h the record's true span."""
    series = [{"t": NOW - h * 3600, "pm25": p, "vc_m2s": 2000,
               "belt_fires": 5, "modifier": 1.0}
              for h, p in ((4.0, 60), (3.0, 70), (1.0, 120), (0.5, 140))]
    meta = {"n_available": 8, "span_available_s": 5.5 * 3600}
    d, ev, ct = v2why._eval_trend(series, meta)
    assert d and d["kind"] == "trend"
    assert ev["n_snapshots"] == 4               # bodies read
    assert ev["n_snapshots_available"] == 8     # the record's truth
    assert ev["span_available_h"] == 5.5
    assert ev["span_h"] == pytest.approx(3.5, abs=0.05)  # read coverage
    assert "4 of 8 recorded builds" in d["evidence"]


def test_eval_trend_too_few_discloses_record():
    """Truncation below the admission bar must not pretend the record
    itself is thin."""
    series = [{"t": NOW - h * 3600, "pm25": p}
              for h, p in ((1.0, 100), (0.5, 130))]
    meta = {"n_available": 30, "span_available_s": 5.8 * 3600}
    d, ev, ct = v2why._eval_trend(series, meta)
    assert d is None and ct
    assert "of 30" in ct["reason"]              # the record is not 2
    assert ev["n_snapshots"] == 2
    assert ev["n_snapshots_available"] == 30


# ---------------------------------------------------------------- endpoint

def test_endpoint_honest_empty(snap_root, wind_se, cold_forecast,
                               monkeypatch):
    """Nothing observable -> local background, drivers []."""
    import fires
    monkeypatch.setattr(fires, "FIRES", _NoFires())
    r = client.get("/v2/why?lat=28.63&lon=77.22")
    assert r.status_code == 200
    body = r.json()
    assert body["drivers"] == []
    assert body["line"] == "local background — no single driver stands out"
    assert any(c["kind"] == "stubble_smoke" for c in body["cannot_tell"])
    assert body["history"] is None


def test_endpoint_smoke_primary(snap_root, wind_nw, cold_forecast,
                                monkeypatch):
    import fires
    monkeypatch.setattr(fires, "FIRES", _Fires(belt=61, frp=6.5))
    _write_series(snap_root, [(5.0, 60, 3000, 20, 1.1),
                            (3.0, 80, 2800, 25, 1.2),
                            (1.0, 130, 2000, 40, 1.5),
                            (0.5, 140, 1800, 45, 1.6)])
    r = client.get("/v2/why")
    assert r.status_code == 200
    body = r.json()
    kinds = [d["kind"] for d in body["drivers"]]
    assert "stubble_smoke" in kinds
    assert body["drivers"][0]["weight"] == "primary"
    for d in body["drivers"]:
        assert d["evidence"] and d["score"] > 0
    assert body["history"]["points"]  # 4 builds spanning >3h
    assert "north-west" in body["line"]


def test_endpoint_wind_blocked(snap_root, wind_se, cold_forecast,
                               monkeypatch):
    """Fires burning but SE wind — no smoke claim (the live tonight)."""
    import fires
    monkeypatch.setattr(fires, "FIRES", _Fires(belt=80, frp=5.0))
    r = client.get("/v2/why")
    body = r.json()
    assert all(d["kind"] != "stubble_smoke" for d in body["drivers"])
    assert body["evaluated"]["fires"]["carrying"] is False


def test_endpoint_shape_keys(snap_root, wind_se, cold_forecast,
                             monkeypatch):
    import fires
    monkeypatch.setattr(fires, "FIRES", _NoFires())
    body = client.get("/v2/why").json()
    for k in ("generated_at", "lat", "lon", "scope", "line", "drivers",
              "evaluated", "cannot_tell", "wind", "history", "honesty"):
        assert k in body
    for k in ("fires", "ventilation", "trend"):
        assert k in body["evaluated"]


def test_why_block_in_city(snap_root, wind_se, cold_forecast,
                           monkeypatch):
    """/v2/city carries the one-liner block."""
    import fires
    monkeypatch.setattr(fires, "FIRES", _NoFires())
    from airfield import FIELD
    FIELD._samples = [(28.63, 77.21, "t", {"pm2_5": 90.0})]
    FIELD._fetched_at = time.time()
    r = client.get("/v2/city")
    assert r.status_code == 200
    why = r.json().get("why")
    assert why is not None and why["line"]
    assert why["why_url"] == "/v2/why"


def test_endpoint_marks_point_outside_service_area(snap_root, wind_se,
                                                   cold_forecast,
                                                   monkeypatch):
    """/aqi rejects the same coords outright; /v2/why keeps its
    city-scale answer (fires/stagnation/trend are city drivers) but
    must not read as a local one — the edge-honesty probe showed a
    far-out-of-area query silently clamping the ventilation read to
    an edge cell and returning the Delhi line with no marker."""
    import fires
    monkeypatch.setattr(fires, "FIRES", _NoFires())
    r = client.get("/v2/why?lat=51.5074&lon=-0.1278")
    assert r.status_code == 200
    got = r.json()
    assert got["point_in_area"] is False
    assert got["lat"] == 51.5074 and got["lon"] == -0.1278
    assert "outside" in got["note"]


def test_endpoint_marks_point_inside_service_area(snap_root, wind_se,
                                                  cold_forecast,
                                                  monkeypatch):
    import fires
    monkeypatch.setattr(fires, "FIRES", _NoFires())
    got = client.get("/v2/why?lat=28.6315&lon=77.2167").json()
    assert got["point_in_area"] is True
    assert "note" not in got


def test_endpoint_default_point_marks_in_area(snap_root, wind_se,
                                              cold_forecast,
                                              monkeypatch):
    import fires
    monkeypatch.setattr(fires, "FIRES", _NoFires())
    got = client.get("/v2/why").json()     # Delhi default
    assert got["point_in_area"] is True


# ----------------------------------------------------------------- surfaces

def test_city_html_has_why_line():
    html = open(os.path.join(os.path.dirname(__file__), "..",
                             "city.html")).read()
    assert 'id="whyline"' in html and "cy.why" in html


def test_admin_html_has_drivers_table():
    html = open(os.path.join(os.path.dirname(__file__), "..",
                             "admin.html")).read()
    assert 'id="whydrivers"' in html and "/v2/why" in html \
        and 'id="whyeval"' in html


# ------------------------------------------------------------- cause_note

def _ev(belt=44, frp=120.0, carrying=True, feed_status="live",
        factor=1.86, vc=1612.0, delta=-15.6):
    """A frozen evaluated{} — the fields _cause_note reads."""
    return {
        "fires": {"seen": feed_status == "live", "belt_fires": belt,
                  "belt_frp_mw": frp, "n_fires": belt * 3,
                  "modifier": 1.06, "feed": "firms-public-csv",
                  "feed_status": feed_status, "carrying": carrying},
        "ventilation": {"vc_m2s": vc, "factor": factor},
        "trend": {"delta_ug": delta, "from_pm25": 64.8, "to_pm25": 64.8 - delta,
                  "span_h": 6.0},
    }


def _wind(deg=315.0, kmh=9.0):
    return {"from_deg": deg, "speed_kmh": kmh}


def _series_belt(rows):
    """rows: [(hours_ago, belt_fires)]"""
    return [{"t": NOW - h * 3600, "pm25": 80.0, "vc_m2s": 2000.0,
             "belt_fires": b, "modifier": 1.0} for h, b in rows]


def test_belt_delta_gates():
    f_live = _ev()["fires"]
    f_cold = _ev(feed_status="cold")["fires"]
    series = _series_belt([(5.0, 20), (1.0, 40)])
    assert v2why._belt_delta(f_live, series) == (24, 4.0)
    # cold feed vs recorded builds compares the same number twice
    assert v2why._belt_delta(f_cold, series) is None
    # <2 belt rows / <3h span — nothing to compare against
    assert v2why._belt_delta(f_live, _series_belt([(1.0, 40)])) is None
    assert v2why._belt_delta(
        f_live, _series_belt([(1.5, 20), (0.5, 40)])) is None


def test_cause_note_full_carrying_inflow():
    """The parali build: belt count + jump + carry + stillness + trend,
    every figure a served field."""
    ev = _ev(belt=44, delta=-15.6)
    ev["trend"]["to_pm25"] = 49.2
    text, f = v2why._cause_note(ev, _wind(), _series_belt([(5.0, 20), (1.0, 40)]))
    assert "44 fires in the Punjab–Haryana belt" in text
    assert "up from 20 over ~4 h" in text
    assert "carrying it toward Delhi" in text
    assert "air barely mixing" in text and "1,612" in text
    assert "64.8 → 49.2" in text
    assert text.endswith("smoke inflow meeting still air")
    assert f["basis"] == "measured" and f["belt_delta"] == 24
    assert f["carrying"] is True and f["wind_from_deg"] == 315.0


def test_cause_note_blocked_wind_says_so():
    text, f = v2why._cause_note(
        _ev(carrying=False), _wind(deg=150.0), _series_belt([(5.0, 20), (1.0, 40)]))
    assert "isn't carrying it this way" in text
    assert "carrying it toward Delhi" not in text
    assert f["carrying"] is False


def test_cause_note_cold_feed_no_belt_jump():
    """Recorded fallback: belt count still reads, the 'jumped' claim
    drops — it would compare a recorded count against itself."""
    ev = _ev(feed_status="cold")
    ev["fires"]["seen"] = True
    text, f = v2why._cause_note(ev, _wind(), _series_belt([(5.0, 20), (1.0, 40)]))
    assert "44 fires" in text and "up from" not in text
    assert f["belt_delta"] is None


def test_cause_note_quiet_belt_and_background():
    text, _ = v2why._cause_note(
        _ev(belt=3, factor=1.0, delta=0.0), _wind(), [])
    assert text.startswith("a quiet belt — 3 fires")
    text2, _ = v2why._cause_note(
        _ev(belt=0, factor=1.0, delta=0.0), _wind(), [])
    assert "a quiet belt right now" in text2
    # nothing at all → the honest empty answer, not silence
    text3, _ = v2why._cause_note(
        {"fires": {}, "ventilation": {}, "trend": {}}, _wind(), [])
    assert text3 == "local background — no big driver in play right now"


def test_cause_note_floors_hold():
    """Below the explainers' own bars the note stays quiet: 3 fires is
    a quiet belt, factor 1.1 isn't 'barely mixing', ±6 µg isn't a move,
    and a belt delta under the re-count floor isn't a 'jump'."""
    ev = _ev(belt=9, factor=1.1, delta=6.0)
    text, f = v2why._cause_note(ev, _wind(), _series_belt([(5.0, 11), (1.0, 10)]))
    assert "9 fires" in text and "air barely mixing" not in text
    assert "city mean" not in text
    assert f["stag_factor"] is None and f["trend_to"] is None
    # |delta|=2 < _NOTE_DELTA_MIN — FIRMS re-count noise, not a move
    assert "up from" not in text and "down from" not in text
    assert f["belt_delta"] is None


def test_endpoint_serves_cause_note(snap_root, wind_nw, cold_forecast,
                                    monkeypatch):
    import fires
    monkeypatch.setattr(fires, "FIRES", _Fires(belt=61, frp=6.5))
    _write_series(snap_root, [(5.0, 60, 3000, 20, 1.1),
                            (3.0, 80, 2800, 25, 1.2),
                            (1.0, 130, 2000, 40, 1.5),
                            (0.5, 140, 1800, 45, 1.6)])
    body = client.get("/v2/why").json()
    note = body["cause_note"]
    assert "61 fires in the Punjab–Haryana belt" in note
    assert "carrying it toward Delhi" in note
    f = body["cause_note_fields"]
    assert f["basis"] == "measured" and f["belt_fires"] == 61


def test_city_html_has_parali_tile():
    html = open(os.path.join(os.path.dirname(__file__), "..",
                             "city.html")).read()
    assert 'id="noteline"' in html and "cause_note" in html
