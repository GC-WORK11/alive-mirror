"""Sanity tests for the NCR climatology runtime module.

Run:  server/.venv312/bin/python -m pytest server/tests/test_history.py
or:   server/.venv312/bin/python server/tests/test_history.py
"""
import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import history

# Central Delhi (near ITO / Connaught Place)
CP = (28.6315, 77.2426)


def test_november_morning_elevated():
    """Winter morning PM2.5 must be in a sane elevated range."""
    v = history.typical(*CP, month=11, hour=8)
    assert v is not None, "no pm25 data for Nov 08:00"
    assert 50 <= v <= 600, f"Nov 8AM typical PM2.5 {v} outside 50-600 µg/m³"


def test_april_afternoon_lower():
    """April afternoon should be far lower than November morning."""
    nov = history.typical(*CP, month=11, hour=8)
    apr = history.typical(*CP, month=4, hour=14)
    assert apr is not None, "no pm25 data for Apr 14:00"
    assert apr < nov, f"April 2PM ({apr}) not below Nov 8AM ({nov})"


def test_diurnal_curve_finite():
    curve = history.diurnal_curve(*CP, date="2025-11-15")
    assert len(curve) == 24
    assert all(v is not None and math.isfinite(v) for v in curve), \
        f"non-finite values in diurnal curve: {curve}"


def test_typical_band_ordering():
    band = history.typical_band(*CP, month=12, hour=9)
    assert band["p25"] <= band["median"] <= band["p75"]


def test_station_meta_populated():
    meta = history.station_meta()
    assert len(meta) >= 8, f"only {len(meta)} stations in climatology"
    assert all(s["lat"] and s["lon"] for s in meta)


if __name__ == "__main__":
    test_november_morning_elevated()
    test_april_afternoon_lower()
    test_diurnal_curve_finite()
    test_typical_band_ordering()
    test_station_meta_populated()
    print("all history checks passed")
