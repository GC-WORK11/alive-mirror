"""Live-API tests for forecast.py — hits real Open-Meteo endpoints.

Run from server/:
    .venv312/bin/python -m unittest tests.test_forecast -v
or directly:
    .venv312/bin/python tests/test_forecast.py
"""
import os
import sys
import unittest
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import httpx  # noqa: E402

from forecast import ForecastField, FACTOR_MIN, FACTOR_MAX  # noqa: E402

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
        """When the anchor's correction pushes below the physical floor,
        pm25 serves the model's own number — never a clamped literal 0.0."""
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
        # (0.5 - ~199)·decay ≈ -142 → corrected << 0 → serve ~30 raw.
        v = f.pm25(*self.EAST, 3, live=live)
        self.assertIsNotNone(v)
        self.assertGreater(v, 0.0)
        self.assertAlmostEqual(v, 30.0, delta=10.0)

    def test_missing_met_degrades(self):
        """No met grid ⇒ undisplaced lookup — never None for a covered point."""
        f = _synthetic_field()
        f._met = []
        self.assertEqual(f._advected_origin(*self.EAST, 40), self.EAST)
        self.assertIsNotNone(f.pm25(*self.EAST, 3))


if __name__ == "__main__":
    unittest.main(verbosity=2)
