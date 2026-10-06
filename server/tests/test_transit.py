"""Offline tests for transit.py — embedded station data, constant field.

Run from server/:
    .venv312/bin/python -m unittest tests.test_transit -v
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import transit  # noqa: E402
import exposure  # noqa: E402

FIELD150 = lambda lat, lon: 150.0  # noqa: E731 — constant test field

CONNAUGHT_PLACE = (28.6315, 77.2167)
KAROL_BAGH = (28.6450, 77.1900)
NOIDA_SEC_18 = (28.5710, 77.3260)
FAR_GREATER_NOIDA = (28.4500, 77.6000)


class TestStationRegistry(unittest.TestCase):
    def test_registry_size(self):
        self.assertGreaterEqual(len(transit.STATIONS), 30)

    def test_stations_inside_ncr(self):
        for s in transit.STATIONS:
            self.assertTrue(28.20 <= s["lat"] <= 28.95, s["name"])
            self.assertTrue(76.80 <= s["lon"] <= 77.90, s["name"])
            self.assertTrue(s["name"])
            self.assertTrue(s["lines"])

    def test_unique_names(self):
        names = [s["name"] for s in transit.STATIONS]
        self.assertEqual(len(names), len(set(names)))


class TestNearestStation(unittest.TestCase):
    def test_connaught_place_rajiv_chowk(self):
        name, lat, lon, dist = transit.nearest_station(*CONNAUGHT_PLACE)
        self.assertEqual(name, "Rajiv Chowk")
        self.assertLess(dist, 1.0)

    def test_exact_station_coords(self):
        name, _, _, dist = transit.nearest_station(28.5443, 77.2067)
        self.assertEqual(name, "Hauz Khas")
        self.assertLess(dist, 0.2)


class TestMetroOption(unittest.TestCase):
    def test_karol_bagh_to_noida(self):
        opt = transit.metro_option(*KAROL_BAGH, *NOIDA_SEC_18, FIELD150)
        self.assertIsNotNone(opt)
        self.assertEqual(opt["vehicle"], "metro")
        self.assertEqual(opt["mode"], "metro")
        self.assertIn(opt["duration_model"], ("estimated", "gtfs"))

        legs = opt["legs"]
        self.assertEqual([l["type"] for l in legs], ["walk", "metro", "walk"])
        self.assertEqual(opt["stations"]["board"], "Karol Bagh")
        self.assertIn("Noida Sector", opt["stations"]["alight"])

        # durations/distances sum across legs
        self.assertAlmostEqual(opt["duration_s"],
                               sum(l["duration_s"] for l in legs), delta=1)
        self.assertAlmostEqual(opt["distance_km"],
                               sum(l["distance_km"] for l in legs), places=1)

        # dose: constant field -> closed-form check of the math —
        # me/ve read the canonical tables so a re-anchor can't drift them
        exp = 0.0
        for l in legs:
            mk = "walking" if l["type"] == "walk" else "metro"
            microenv = exposure.MICROENV[mk]
            ve_lpm = exposure.VENTILATION_LPM[mk]
            exp += 150.0 * microenv * (ve_lpm / 1000.0) * (l["duration_s"] / 60.0)
        # per-leg dose_ug is rounded to 0.1 upstream, so allow slack
        self.assertAlmostEqual(opt["exposure"]["dose_ug"], exp, delta=0.3)

        # metro leg distance is the detour-inflated inter-station distance
        self.assertGreater(legs[1]["distance_km"], 10.0)
        self.assertLess(legs[1]["distance_km"], 30.0)

    def test_metro_beats_walking_same_trip(self):
        opt = transit.metro_option(*KAROL_BAGH, *NOIDA_SEC_18, FIELD150)
        km = opt["distance_km"]
        walk_all_s = km / 5.0 * 3600
        walk_all_dose = (150.0 * exposure.MICROENV["walking"]
                         * (exposure.VENTILATION_LPM["walking"] / 1000.0)
                         * (walk_all_s / 60.0))
        self.assertLess(opt["exposure"]["dose_ug"], walk_all_dose)

    def test_far_endpoint_returns_none(self):
        self.assertIsNone(
            transit.metro_option(*FAR_GREATER_NOIDA, *NOIDA_SEC_18, FIELD150))
        self.assertIsNone(
            transit.metro_option(*KAROL_BAGH, *FAR_GREATER_NOIDA, FIELD150))

    def test_field_unavailable(self):
        opt = transit.metro_option(*KAROL_BAGH, *NOIDA_SEC_18,
                                   lambda lat, lon: None)
        self.assertIsNotNone(opt)
        self.assertIsNone(opt["exposure"]["dose_ug"])
        for l in opt["legs"]:
            self.assertIsNone(l["dose_ug"])


class TestRealGTFS(unittest.TestCase):
    """Exercises transit_real only when its cache is present — the module
    must degrade silently everywhere else."""

    def setUp(self):
        self.tr = getattr(transit, "transit_real", None)
        if self.tr is None:
            self.skipTest("transit_real unavailable")
        import time
        for _ in range(300):  # bg thread parses the feed once
            if self.tr._STATE.get("metro") is not None:
                break
            time.sleep(0.1)
        if self.tr._STATE.get("metro") is None:
            self.skipTest("GTFS cache not loaded")

    def test_real_metro_journey(self):
        j = self.tr.metro_journey(*CONNAUGHT_PLACE, *NOIDA_SEC_18)
        self.assertIsNotNone(j)
        self.assertEqual(j["board"], "Rajiv Chowk")
        self.assertEqual(j["alight"], "Noida Sector 18")
        self.assertIn("Blue", j["lines"])
        self.assertGreater(j["ride_s"], 300)
        self.assertGreater(len(j["geometry"]["coordinates"]), 2)

    def test_option_uses_real_names(self):
        opt = transit.metro_option(*CONNAUGHT_PLACE, *NOIDA_SEC_18, FIELD150)
        self.assertEqual(opt["duration_model"], "gtfs")
        self.assertEqual(opt["stations"]["board"], "Rajiv Chowk")

    def test_bus_hint_shape(self):
        if self.tr._STATE.get("bus") is None:
            self.skipTest("bus feed not loaded")
        h = self.tr.bus_hint(*CONNAUGHT_PLACE, *NOIDA_SEC_18)
        if h is not None:
            self.assertIn("board_stop", h)
            self.assertIn("direct_routes", h)


if __name__ == "__main__":
    unittest.main(verbosity=2)
