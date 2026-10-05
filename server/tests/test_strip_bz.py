"""strip-bz lane — one concentration basis across stays, plans, strips.

Ledger-audit (docs/lanes/ledger-audit-report.md) found the app's
reconstructDay counting stays at `bz` (ambient × FIRES smoke_modifier,
what /aqi serves as `pm25`) while /v2/plan dose blocks and /v2/strip
samples integrated raw ambient — a ~+9% stay-vs-trip mismatch during
burn events on the same street+hour.

Decision (docs/lanes/strip-bz.md): the modifier is physically real —
FIRMS belt detections vs seasonal baseline, wind-gated — so the honest
fix is pricing it engine-side everywhere, NOT stripping it from stays.
These tests lock that basis:

  * _dose_band / _leg_dose / /v2/strip samples all read
    ambient × smoke_modifier when the fires feed reports one;
  * a stay-segment and a plan-segment over the same street+hour share
    the same concentration term — bz == strip.pm25 == dose-implied
    conc / microenv;
  * mod = 1.0 (feed down or no burn) is byte-identical to the old
    ambient basis — no hidden scale factor;
  * the multiplier surfaces on the wire (plan/strip responses) so a
    client can prove basis parity against /aqi.
"""
import os
import sys
import time

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.pop("ALIVE_LOCATION_KEY", None)

from fastapi.testclient import TestClient  # noqa: E402

import main  # noqa: E402
import fires  # noqa: E402
import exposure  # noqa: E402
from airfield import FIELD  # noqa: E402
from v2 import deps, store  # noqa: E402
from v2 import plan as v2plan  # noqa: E402
import transit_v2  # noqa: E402

client = TestClient(main.app)

LINE = {"type": "LineString",
        "coordinates": [[77.2090, 28.6139], [77.2150, 28.6300],
                        [77.1990, 28.6450]]}

MOD = 1.25          # a burn-night modifier well clear of rounding noise
C_STUB = 100.0      # flat-ish stub field


async def _noop(*a, **k):
    return None


async def fake_osrm(profile, flon, flat, tlon, tlat):
    rt = {"distance": 6200.0, "duration": 780.0, "geometry": LINE,
          "legs": [{"steps": [
              {"maneuver": {"type": "depart", "modifier": "north",
                            "location": [77.2090, 28.6139]},
               "name": "Rajpath", "distance": 3000.0, "duration": 400.0},
              {"maneuver": {"type": "arrive",
                            "location": [77.1990, 28.6450]},
               "name": "", "distance": 0.0, "duration": 0.0}]}]}
    rt["steps"] = deps.osrm_steps(rt)
    return rt


class DisabledLoc:
    enabled = False


@pytest.fixture(autouse=True)
def wired(monkeypatch):
    deps.set_location(DisabledLoc())
    FIELD._samples = [
        (28.6139, 77.2090, "test-station", {"pm2_5": C_STUB}),
        (28.6300, 77.2150, None, {"pm2_5": C_STUB}),
        (28.6450, 77.1990, None, {"pm2_5": C_STUB}),
    ]
    FIELD._fetched_at = time.time()
    monkeypatch.setattr(deps, "field_refresh", _noop)
    monkeypatch.setattr(deps, "osrm_route", fake_osrm)
    monkeypatch.setattr(transit_v2, "plan_transit", lambda *a, **k: [])
    monkeypatch.setattr(FIELD, "refresh", _noop)
    monkeypatch.setattr(main.FIRES, "refresh", _noop)
    # strip/plan read fires.FIRES lazily — pin the modifier there
    monkeypatch.setattr(fires.FIRES, "smoke_modifier", lambda: MOD)
    store.ROUTES._routes.clear()
    yield
    deps.set_location(None)
    FIELD._samples = []


@pytest.fixture
def ambient_only(monkeypatch):
    monkeypatch.setattr(fires.FIRES, "smoke_modifier", lambda: 1.0)


# --- helpers ---------------------------------------------------------------
def _ambient_dose(geometry, duration_s, microenv):
    """The pre-fix basis: whichever surface _dose_band resolves
    (engine raster > field snapshot > live krige), read RAW — the
    same fallback chain the old code ran before _bz_field existed."""
    F = deps.field()
    dval, dsig = v2plan._dose_surface(F)
    return exposure.dose(geometry, duration_s, microenv,
                         dval or F.value, F.nearest_sample_km,
                         field_sigma=dsig or F.sigma)


def _mk_route_id():
    resp = client.post("/v2/plan", json={
        "from": {"lat": 28.6139, "lon": 77.2090},
        "to": {"lat": 28.6450, "lon": 77.1990},
        "vehicle": "auto"})
    assert resp.status_code == 200
    body = resp.json()
    opts = body.get("options") or []
    assert opts, "plan must return options"
    return body, opts[0]["route_id"]


# --- the unit locks ---------------------------------------------------------
def test_dose_band_scales_by_smoke_modifier():
    d_amb = _ambient_dose(LINE, 780.0, "auto_rickshaw")
    d_bz = v2plan._dose_band(LINE, 780.0, "auto_rickshaw")
    # wire fields ship at 0.1 precision — rel≈1% absorbs the rounding
    assert d_bz["mid"] == pytest.approx(d_amb["dose_ug"] * MOD, rel=0.01)
    assert d_bz["avg_conc_ugm3"] == pytest.approx(
        d_amb["avg_conc_ugm3"] * MOD, rel=0.01)
    # band scales with the concentration it wraps
    if d_amb.get("dose_ug_lo") is not None and d_bz["lo"] is not None:
        assert d_bz["lo"] == pytest.approx(d_amb["dose_ug_lo"] * MOD,
                                         rel=0.01)
        assert d_bz["hi"] == pytest.approx(d_amb["dose_ug_hi"] * MOD,
                                         rel=0.01)


def test_dose_band_ambient_basis_when_modifier_one(ambient_only):
    d_amb = _ambient_dose(LINE, 780.0, "auto_rickshaw")
    d = v2plan._dose_band(LINE, 780.0, "auto_rickshaw")
    assert d["mid"] == pytest.approx(d_amb["dose_ug"], rel=0.01)


def test_leg_dose_on_bz_basis():
    legs = [{"type": "walk", "geometry": LINE, "duration_s": 780.0}]
    d_amb = _ambient_dose(LINE, 780.0, "walking")
    d = v2plan._leg_dose(legs)
    assert d["mid"] == pytest.approx(d_amb["dose_ug"] * MOD, rel=0.01)


def test_bz_field_none_passthrough():
    v, s = v2plan._bz_field(None, None)
    assert v is None and s is None        # fallback chain must survive


def test_smoke_mod_guards_garbage(monkeypatch):
    for bad in (None, "fire", float("nan"), -1.2):
        monkeypatch.setattr(fires.FIRES, "smoke_modifier", lambda b=bad: b)
        assert v2plan._smoke_mod() == 1.0


# --- the wire locks ----------------------------------------------------------
def test_strip_samples_on_bz_basis():
    _, rid = _mk_route_id()
    resp = client.get(f"/v2/strip?route_id={rid}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["smoke_modifier"] == pytest.approx(MOD)
    F = deps.field()
    vals = [(s["pm25"], F.value(s["lat"], s["lon"]))
            for s in body["samples"] if s["pm25"] is not None]
    assert vals, "strip must serve samples"
    for served, ambient in vals[:8]:
        assert served == pytest.approx(ambient * MOD, abs=0.15)


def test_plan_options_scale_with_modifier(monkeypatch):
    """Same OD planned twice — burn-night mod then mod=1.0 — every
    option's dose.mid scales by exactly MOD. The multiplier commutes
    through the dose integral, so this ratio IS the basis switch."""
    body, _ = _mk_route_id()
    assert body["smoke_modifier"] == pytest.approx(MOD)
    # label-keyed: alternative rows share a mode ("car", "auto", ...)
    first = {o.get("label") or o["mode"]: (o.get("dose") or {}).get("mid")
             for o in body["options"]}

    monkeypatch.setattr(fires.FIRES, "smoke_modifier", lambda: 1.0)
    resp2 = client.post("/v2/plan", json={
        "from": {"lat": 28.6139, "lon": 77.2090},
        "to": {"lat": 28.6450, "lon": 77.1990},
        "vehicle": "auto"})
    body2 = resp2.json()
    assert body2["smoke_modifier"] == 1.0
    second = {o.get("label") or o["mode"]: (o.get("dose") or {}).get("mid")
              for o in body2["options"]}

    common = [m for m in first if m in second
              and first[m] is not None and second[m] is not None]
    assert common, "the two plans must share dosed modes"
    for m in common:
        assert first[m] == pytest.approx(second[m] * MOD, rel=0.05)


def test_strip_ambient_basis_when_modifier_one(ambient_only):
    _, rid = _mk_route_id()
    body = client.get(f"/v2/strip?route_id={rid}").json()
    assert body["smoke_modifier"] == 1.0
    F = deps.field()
    for s in body["samples"]:
        if s["pm25"] is None:
            continue
        assert s["pm25"] == pytest.approx(F.value(s["lat"], s["lon"]),
                                        abs=0.15)


def test_stay_and_trip_share_one_conc_basis():
    """The mandate lock: same hour, same street — a stay-segment and a
    plan-segment must read the same concentration.

    stay µg   = strip.pm25        × VE_REST(0.6 m³/h) × h   (daylog bz)
    trip µg   = strip.pm25 × ME   × VE(mode)          × h   (counters)
    Both share strip.pm25 == ambient × mod == /aqi's pm25 — assert the
    strip's served value equals the bz the stays ledger would read.
    """
    _, rid = _mk_route_id()
    body = client.get(f"/v2/strip?route_id={rid}").json()
    s = next(x for x in body["samples"] if x["pm25"] is not None)
    aqi_resp = client.get(f"/aqi?lat={s['lat']}&lon={s['lon']}")
    assert aqi_resp.status_code == 200
    aqi = aqi_resp.json()
    # /aqi's pm25 IS the bz the stays ledger samples — the strip must
    # serve the identical basis at the identical point
    assert s["pm25"] == pytest.approx(aqi["pm25"], abs=0.2)
    assert s["pm25"] == pytest.approx(aqi["pm25_ambient"] * MOD, abs=0.2)
    # and the stay-segment arithmetic lands on it: 30 min at this point
    stay_ug = s["pm25"] * 0.6 * 0.5          # VE_REST 0.6 m³/h × 0.5 h
    ambient_stay_ug = (aqi["pm25_ambient"] or 0) * 0.6 * 0.5
    assert stay_ug > ambient_stay_ug * 1.1   # burn-night gap is real
