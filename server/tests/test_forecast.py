"""Live-API tests for forecast.py — hits real Open-Meteo endpoints.

Run from server/:
    .venv312/bin/python -m unittest tests.test_forecast -v
or directly:
    .venv312/bin/python tests/test_forecast.py
"""
import math
import os
import sys
import unittest
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import httpx  # noqa: E402

from forecast import (ForecastField, FACTOR_MIN, FACTOR_MAX, anchor_w,
                      ANCHOR_BLEND_HOLD_H, ANCHOR_BLEND_END_H)  # noqa: E402

LODHI_RD = (28.5918, 77.2277)  # central Delhi CPCB station


class TestForecastField(unittest.IsolatedAsyncioTestCase):
    field = None

    @classmethod
    def setUpClass(cls):
        cls.field = ForecastField()

    async def asyncSetUp(self):
        if not self.field._aq:
            async with httpx.AsyncClient(timeout=httpx.Timeout(30.0, connect=10.0)) as c:
                await self.field.refresh(c)
        if not self.field._aq:
            self.skipTest("Open-Meteo unreachable")

    def test_stagnation_factor_in_range(self):
        idx = self.field.hour_index(6)
        self.assertIsNotNone(idx)
        d = self.field.stagnation_detail(*LODHI_RD, idx)
        self.assertIsNotNone(d)
        if not d["estimated"]:  # BLH present
            self.assertIsInstance(d["factor"], float)
            self.assertGreaterEqual(d["factor"], FACTOR_MIN)
            self.assertLessEqual(d["factor"], FACTOR_MAX)

    def test_pm25_plus_24h_plausible(self):
        v = self.field.pm25(*LODHI_RD, 24)
        self.assertIsNotNone(v)
        self.assertGreater(v, 0)
        self.assertLess(v, 1000)

    def test_best_departure_window(self):
        w = self.field.best_departure_window(*LODHI_RD, 0, 24)
        self.assertIsNotNone(w)
        best, worst = w["best"], w["worst"]
        self.assertGreaterEqual(len(best), 1)
        self.assertLessEqual(len(best), 3)
        vals = [s["pm25_ugm3"] for s in best]
        self.assertEqual(vals, sorted(vals))
        # typical Delhi day has real hourly variation
        self.assertLess(best[0]["pm25_ugm3"], worst["pm25_ugm3"])
        for s in best + [worst]:
            self.assertIn("start", s)
            self.assertIn("pm25_ugm3", s)

    def test_outside_horizon_is_none(self):
        self.assertIsNone(self.field.pm25(*LODHI_RD, 200))
        self.assertIsNone(self.field.pm25(*LODHI_RD, -5))

    def test_datetime_input(self):
        v = self.field.pm25(*LODHI_RD,
                            datetime.now(timezone.utc) + timedelta(hours=12))
        self.assertIsNotNone(v)


def _synthetic_field(wind_ms=10.0, wind_dir=270.0):
    """Two-point grid: dirty west cell (200 µg), clean east cell (20 µg),
    steady wind (FROM `wind_dir`; 270 → parcels move EAST). No live
    anchor — deterministic, no network."""
    f = ForecastField(live=None)
    t0 = datetime.now(timezone.utc).replace(hour=0, minute=0,
                                            second=0, microsecond=0)
    times = [(t0 + timedelta(hours=i)).strftime("%Y-%m-%dT%H:%M")
             for i in range(120)]
    f._aq = [
        {"lat": 28.6, "lon": 77.0, "name": "", "t0": t0, "times": times,
         "vars": {"pm2_5": [200.0] * 120}},
        {"lat": 28.6, "lon": 77.4, "name": "", "t0": t0, "times": times,
         "vars": {"pm2_5": [20.0] * 120}},
    ]
    f._met = [
        {"lat": 28.6, "lon": 77.0, "name": "", "t0": t0, "times": times,
         "vars": {"wind_speed_10m": [wind_ms] * 120,
                  "wind_direction_10m": [wind_dir] * 120}},
        {"lat": 28.6, "lon": 77.4, "name": "", "t0": t0, "times": times,
         "vars": {"wind_speed_10m": [wind_ms] * 120,
                  "wind_direction_10m": [wind_dir] * 120}},
    ]
    return f


class TestAdvection(unittest.TestCase):
    """Semi-Lagrangian back-trajectory lookups on the synthetic grid."""

    EAST = (28.6, 77.4)

    def test_plume_advects_east(self):
        """At +1-3h the air arriving at the clean east cell left from the
        dirty west cell (10 m/s × hours ≈ 36-108 km, capped at 45 km) —
        the displaced sample must read ~west values, not local 20."""
        f = _synthetic_field()
        v = f.pm25(*self.EAST, 3)
        self.assertIsNotNone(v)
        self.assertGreater(v, 120)   # ~200 upwind vs 20 undisplaced
        undisplaced = f._idw(f._aq, *self.EAST, "pm2_5", 0)
        self.assertLessEqual(undisplaced, 20.0)

    def test_calm_degrades_to_undisplaced(self):
        """~calm wind ⇒ no displacement — same answer the old path gave."""
        f = _synthetic_field(wind_ms=0.1)
        self.assertEqual(f._advected_origin(*self.EAST, 40), self.EAST)
        v = f.pm25(*self.EAST, 3)
        self.assertIsNotNone(v)
        self.assertLess(v, 40)  # undisplaced blend, not the plume

    def test_displacement_capped(self):
        """Far-horizon + strong wind can't look up outside the grid —
        the cap holds the origin within ADV_MAX_M (~0.45° here)."""
        f = _synthetic_field(wind_ms=25.0)
        alat, alon = f._advected_origin(*self.EAST, 119)
        self.assertAlmostEqual(alat, self.EAST[0], places=6)
        self.assertLess(abs(alon - self.EAST[1]), 0.5)
        self.assertGreater(alon, 76.9)

    def test_anchor_evaluates_at_the_parcel_origin(self):
        """Regression — the live-anchor delta used to be computed at the
        query point but applied to the displaced base: a model over-read
        AT the destination could crush an upwind parcel to a clamped 0.0
        (seen live: CP h+2..6 read 0.0 under a westerly). The correction
        must follow the parcel — evaluate at the advected origin."""
        f = _synthetic_field(wind_dir=90.0)   # parcels move WEST
        # live truth: the model massively over-reads the west cell
        # (200 vs live 60) and slightly under-reads the east (20 vs 55).
        def live(lat, lon):
            return 60.0 if lon < 77.2 else 55.0
        v = f.pm25(28.6, 77.0, 3, live=live)   # query the WEST cell
        self.assertIsNotNone(v)
        # base at the displaced (east) origin ≈ 20; the parcel's own
        # bias is (55-20)·decay ≈ +24 → ~44. The old query-point delta
        # (60-200)·decay ≈ -98 would have clamped this to 0.0.
        self.assertGreater(v, 30.0)

    def test_overshooting_anchor_degrades_to_the_model(self):
        """When the bias delta pushes below the physical floor, that
        stage falls back to the model's own number — never a clamped
        literal 0.0. The persistence blend (a separate, convex stage)
        still applies on top — here it pulls the raw 30 base toward
        the query cell's live read of 180 at w(+3h)~0.97."""
        f = _synthetic_field()
        # the west cell declines over the horizon so a displaced base
        # sits far below that cell's hour-0 model value
        # decline starts one slot past the current hour, wherever that
        # lands (idx0 is hours-since-midnight — run-hour independent)
        idx0 = f.hour_index(0) or 0
        f._aq[0]["vars"]["pm2_5"] = (
            [200.0] * (idx0 + 1) + [30.0] * (120 - idx0 - 1))
        def live(lat, lon):
            return 0.5 if lon < 77.2 else 180.0
        # query EAST at +3h: westerly displaces the origin ~36 km west →
        # base ≈ 30 (the declined west cell); hour-0 bias there is
        # (0.5 - ~199)·decay ≈ -142 → corrected << 0 → base stands raw;
        # blend then gives 30 + w(3)·(180-30) ≈ 176.
        v = f.pm25(*self.EAST, 3, live=live)
        self.assertIsNotNone(v)
        self.assertGreater(v, 0.0)
        self.assertAlmostEqual(v, 30.0 + anchor_w(3) * 150.0, delta=8.0)

    def test_missing_met_degrades(self):
        """No met grid ⇒ undisplaced lookup — never None for a covered point."""
        f = _synthetic_field()
        f._met = []
        self.assertEqual(f._advected_origin(*self.EAST, 40), self.EAST)
        self.assertIsNotNone(f.pm25(*self.EAST, 3))

    def test_hour_zero_is_the_live_field_exactly(self):
        """Nowcast anchor contract: at the current-hour slot the served
        value IS the live read — the model value plus a delta of exactly
        (live − model)·exp(0). This is the forecast's only hard claim."""
        f = _synthetic_field(wind_ms=0.1)   # calm ⇒ undisplaced
        v = f.pm25(*self.EAST, 0, live=lambda lat, lon: 137.0)
        self.assertIsNotNone(v)
        self.assertAlmostEqual(v, 137.0, places=6)

    def test_anchor_fitted_blend_never_overshoots_horizon(self):
        """The fitted persistence weight — full hold to +2 h, linear to
        0 by +40 h — bounds the live pull: inside the window the served
        value sits between corrected-model and live (convex), and past
        +40 h nothing but the ~9-h bias delta remains — the anchor can
        never reach past the CAMS horizon it's anchored to."""
        f = _synthetic_field(wind_ms=0.1)
        live_v = 500.0                       # model says 20 at the cell
        def live(lat, lon):
            return live_v
        d0 = f.pm25(*self.EAST, 0, live=live) - f._idw(
            f._aq, *self.EAST, "pm2_5", f.hour_index(0))
        self.assertGreater(d0, 400)          # sanity: live >> model
        for h, lo_r, hi_r in ((3, 0.9, 1.01), (9, 0.75, 0.95),
                              (24, 0.30, 0.55), (39, 0.02, 0.20),
                              (48, 0.0, 0.03), (96, 0.0, 0.01)):
            idx = f.hour_index(h)
            if idx is None:
                continue
            model_h = f._idw(f._aq, *self.EAST, "pm2_5", idx)
            corr = f.pm25(*self.EAST, h, live=live)
            self.assertIsNotNone(corr)
            resid = abs(corr - model_h)
            self.assertLessEqual(
                resid, hi_r * abs(d0) + 1e-9,
                f"h+{h}: residual {resid:.1f} not decayed vs {d0:.1f}")
            # the blend still carries real signal deep in the window
            self.assertGreaterEqual(
                resid, lo_r * abs(d0) - 1e-9,
                f"h+{h}: residual {resid:.1f} lost the anchor entirely")


class TestPersistenceBlend(unittest.TestCase):
    """The fitted nowcast blend — served = corrected + w·(live −
    corrected) — on the synthetic two-cell field (calm ⇒ undisplaced,
    so the query cell IS the parcel origin)."""

    EAST = (28.6, 77.4)

    def test_stationary_regime_serves_persistence_then_model(self):
        """Steady state (live == the regime that persists): inside the
        hold window the read IS the live value; through the fade it
        sits strictly between corrected-model and live; past the end
        it is the model's own (bias delta only)."""
        f = _synthetic_field(wind_ms=0.1)
        live = lambda lat, lon: 500.0        # east cell model = 20
        # hold window: live verbatim
        for h in (0, 1, 2):
            self.assertAlmostEqual(
                f.pm25(*self.EAST, h, live=live), 500.0, places=6)
        # fade: strictly between the bias-corrected model and live
        idx9 = f.hour_index(9)
        m9 = f._idw(f._aq, *self.EAST, "pm2_5", idx9)
        corr9 = m9 + (500.0 - m9) * math.exp(-(idx9 - f.hour_index(0)) / 9.0)
        v9 = f.pm25(*self.EAST, 9, live=live)
        self.assertLess(corr9, v9)
        self.assertLess(v9, 500.0)
        # past the end: the blend contributes exactly nothing — what
        # remains is model + bias delta, identical to the step-change
        # case below (not live=None: the delta is its own stage)
        idx48 = f.hour_index(48)
        m48 = f._idw(f._aq, *self.EAST, "pm2_5", idx48)
        v48 = f.pm25(*self.EAST, 48, live=live)
        self.assertAlmostEqual(
            v48, m48 + (500.0 - m48) * math.exp(-(idx48 - f.hour_index(0)) / 9.0),
            places=9)

    def test_step_change_does_not_drag_past_window(self):
        """A regime break: the live field steps to a level the model
        never saw. Beyond +40 h the blend must contribute exactly
        nothing — the served value is model + bias-delta only, never
        dragged toward the stale step. Inside the window (control) it
        must pull — proves the field is wired and the step is seen."""
        f = _synthetic_field(wind_ms=0.1)
        live = lambda lat, lon: 999.0        # east cell model = 20
        idx0 = f.hour_index(0)
        for h in (40, 41, 60, 96, 119):
            idx = f.hour_index(h)
            if idx is None:
                continue
            model_h = f._idw(f._aq, *self.EAST, "pm2_5", idx)
            no_blend = model_h + (999.0 - model_h) * math.exp(
                -(idx - idx0) / 9.0)
            with_anchor = f.pm25(*self.EAST, h, live=live)
            self.assertIsNotNone(with_anchor)
            self.assertAlmostEqual(
                with_anchor, no_blend, places=9,
                msg=f"h+{h}: blend reached past its window")
        # control: at +3 h the same step IS pulled toward live
        v3 = f.pm25(*self.EAST, 3, live=live)
        model3 = f._idw(f._aq, *self.EAST, "pm2_5", f.hour_index(3))
        self.assertGreater(v3, model3 + 500.0)

    def test_weight_shape_is_the_fitted_form(self):
        """anchor_w is the fitted hold-then-linear-fade: flat 1.0
        through HOLD_H, strictly decreasing to 0 at END_H, never
        negative, never above 1."""
        self.assertEqual(anchor_w(0.0), 1.0)
        self.assertEqual(anchor_w(ANCHOR_BLEND_HOLD_H), 1.0)
        prev = 1.0
        h = ANCHOR_BLEND_HOLD_H + 1.0
        while h < ANCHOR_BLEND_END_H:
            w = anchor_w(h)
            self.assertLess(w, prev)
            self.assertGreater(w, 0.0)
            prev = w
            h += 1.0
        self.assertEqual(anchor_w(ANCHOR_BLEND_END_H), 0.0)
        self.assertEqual(anchor_w(ANCHOR_BLEND_END_H + 50), 0.0)
        self.assertEqual(anchor_w(-3), 1.0)   # a past-hour slot is 'now'


if __name__ == "__main__":
    unittest.main(verbosity=2)
