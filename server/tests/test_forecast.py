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


if __name__ == "__main__":
    unittest.main(verbosity=2)
