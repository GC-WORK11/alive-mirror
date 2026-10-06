"""Offline tests for segments.py — synthetic field functions only."""

from segments import (segment_doses, hotspots, summary, split_geometry,
                      conc_color)

GEO = {"type": "LineString",
       "coordinates": [[77.0, 28.0], [77.05, 28.0], [77.10, 28.0],
                       [77.15, 28.0]]}


def const_field(v):
    return lambda lat, lon: v


def test_split_covers_full_route():
    segs = split_geometry(GEO, 900, 90)
    assert segs, "non-empty split"
    assert abs(sum(s["seconds"] for s in segs) - 900) < 1e-6
    assert abs(segs[0]["start_frac"]) < 1e-9
    assert abs(segs[-1]["end_frac"] - 1.0) < 1e-9


def test_dose_sum_matches_exposure():
    import exposure
    segs = segment_doses(GEO, 900, "auto_rickshaw", const_field(150))
    seg_total = sum(s["dose_ug"] for s in segs)
    ref = exposure.dose(GEO, 900, "auto_rickshaw", const_field(150))
    # midpoint sampling vs 250m sampling: on a constant field they agree
    # exactly; the test pins the invariant, not the approximation
    assert abs(seg_total - ref["dose_ug"]) < 1.0


def test_hotspot_detects_spike():
    def spike(lat, lon):
        return 900.0 if 77.09 < lon < 77.11 else 50.0
    segs = segment_doses(GEO, 900, "walking", spike, seg_seconds=90)
    hot = hotspots(segs)
    assert hot and hot[0]["share_pct"] > 25
    mid = hot[0]["midpoint_coord"]
    assert 77.05 < mid[0] < 77.15


def test_none_field_degrades_honestly():
    segs = segment_doses(GEO, 600, "metro", lambda lat, lon: None)
    assert all(s["dose_ug"] is None for s in segs)
    assert summary(segs)["total_dose_ug"] is None


def test_conc_color_thresholds():
    assert conc_color(None) == "#64748b"
    assert conc_color(40) == "#64748b"
    assert conc_color(100) == "#c2415c"
    assert conc_color(500) == "#7f1d1d"
