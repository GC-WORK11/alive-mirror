"""Dose-engine audit tests — doc 06 science + doc 10 claims ledger.

Reference values are computed from the doc's own formula
    dose_µg = Σ C·ME·VE·Δt      (doc 06 §1)
on a constant field, so every assertion is the published math, not a fit.
"""

import pytest

import exposure
from exposure import (CIG_UG, MICROENV, MODE_ACTIVITY, ROAD_UPLIFT,
                      VENTILATION_LPM, cigs_band, compare, dose,
                      dose_to_cigs, mode_factors, segment_samples)

# ~1.95 km east-west through central Delhi (lon, lat per GeoJSON)
GEO = {"type": "LineString",
       "coordinates": [[77.200, 28.620], [77.210, 28.620], [77.220, 28.620]]}
F100 = lambda lat, lon: 100.0           # constant 100 µg/m³ field
FNONE = lambda lat, lon: None


# --- doc 06 §1 table audit -----------------------------------------------------

def test_microenv_canonical_values_match_doc():
    """Every mode row, at the published-anchor value (Oct-2026 re-audit:
    open/shared modes re-pinned to Goel 2015 fixed-arterial exceedances +
    Apte 2011 in-rickshaw ratio; prior values underdosed 12–40%)."""
    doc06 = {"metro": 0.45, "driving_car_ac": 0.55, "driving_car_open": 1.00,
             "bus": 0.90, "driving_two_wheeler": 1.20, "auto_rickshaw": 1.30,
             "cycling": 1.10, "walking": 1.30}
    for mode, me in doc06.items():
        assert MICROENV[mode] == me, mode


def test_microenv_aliases_resolve_to_doc_values():
    """Plain app names (the doc's own wording) must land on the same rows."""
    assert MICROENV["car"] == MICROENV["driving_car_ac"] == 0.55
    assert MICROENV["car_open"] == MICROENV["driving_car_open"] == 1.00
    assert MICROENV["bike"] == MICROENV["two_wheeler"] == 1.20
    assert MICROENV["auto"] == MICROENV["rickshaw"] == 1.30
    assert MICROENV["cycle"] == MICROENV["cycling"] == 1.10
    assert MICROENV["walk"] == MICROENV["walking"] == 1.30
    # cab/taxi are flagged conservative defaults (no doc row) — never below
    # the closed-car row, and equal to open-car:
    assert MICROENV["cab"] == MICROENV["taxi"] == MICROENV["driving_car_open"]
    # every alias shares its canonical ventilation too
    for alias, canon in (("car", "driving_car_ac"), ("bike", "driving_two_wheeler"),
                         ("auto", "auto_rickshaw"), ("cycle", "cycling"),
                         ("walk", "walking")):
        assert VENTILATION_LPM[alias] == VENTILATION_LPM[canon]


def test_ventilation_is_activity_adjusted():
    """Doc 06: VE differs sitting vs walking vs cycling; cycling ≈2.1×
    in-vehicle passengers (Zuurbier 2009 measured ~10–11 L/min seated →
    ~22 cycling). Oct-2026 audit: seated tier raised to the measured
    passenger band (~10) from the prior sedentary-rest tier (7.5–9)."""
    assert VENTILATION_LPM["driving_car_ac"] == 10.0  # seated tier
    assert 9.0 <= VENTILATION_LPM["bus"] <= 11.5
    assert 13.0 <= VENTILATION_LPM["walking"] <= 15.0
    assert 20.0 <= VENTILATION_LPM["cycling"] <= 25.0
    assert (VENTILATION_LPM["cycling"] >
            VENTILATION_LPM["walking"] > VENTILATION_LPM["metro"])
    assert VENTILATION_LPM["cycling"] == pytest.approx(2.1 * 10.0, rel=0.06)
    # activity labels differentiate, and aliases inherit correctly
    assert MODE_ACTIVITY["cycling"] == MODE_ACTIVITY["cycle"] == "cycling"
    assert MODE_ACTIVITY["walking"] == MODE_ACTIVITY["walk"] == "walking"
    assert MODE_ACTIVITY["driving_car_ac"] == MODE_ACTIVITY["auto"] == "seated"


def test_measured_delhi_ordering_holds():
    """Doc 06/[1]: auto-rickshaw & walking highest; AC-car & metro lowest.
    Per-unit-time dose on the same field must preserve that ordering."""
    t = 600.0
    doses = {m: dose(GEO, t, m, F100)["dose_ug"]
             for m in ("auto_rickshaw", "driving_two_wheeler", "walking",
                       "bus", "driving_car_open", "driving_car_ac", "metro")}
    assert doses["auto_rickshaw"] > doses["bus"] > doses["metro"]
    assert doses["driving_car_open"] > doses["driving_car_ac"] > doses["metro"]
    assert doses["walking"] > doses["metro"]


# --- doc 06 worked-example math (constant field → closed form) -----------------

@pytest.mark.parametrize("mode,me,ve_lpm", [
    ("walking",            1.30, 14.0),
    ("metro",              0.45, 10.0),
    ("auto_rickshaw",      1.30, 10.0),
    ("cycling",            1.10, 22.0),
    ("driving_car_ac",     0.55, 10.0),
    ("bus",                0.90, 10.0),
    ("driving_two_wheeler", 1.20, 10.5),
])
def test_dose_closed_form(mode, me, ve_lpm):
    """C=100 µg/m³, Δt=10 min → dose = 100·ME·VE·10 exactly (doc 06 §1)."""
    expected = 100.0 * me * (ve_lpm / 1000.0) * 10.0
    r = dose(GEO, 600.0, mode, F100)
    assert r["dose_ug"] == pytest.approx(expected, abs=0.15)
    assert r["avg_conc_ugm3"] == pytest.approx(100.0 * me, abs=0.15)
    assert r["peak_conc"] == pytest.approx(100.0 * me, abs=0.15)
    assert r["coverage"] == 1.0
    assert r["factors"]["microenv"] == me
    assert r["factors"]["ventilation_lpm"] == ve_lpm


def test_alias_dose_identical_to_canonical():
    assert dose(GEO, 600, "auto", F100)["dose_ug"] == \
           dose(GEO, 600, "auto_rickshaw", F100)["dose_ug"]
    assert dose(GEO, 600, "walk", F100)["dose_ug"] == \
           dose(GEO, 600, "walking", F100)["dose_ug"]
    assert dose(GEO, 600, "car", F100)["dose_ug"] == \
           dose(GEO, 600, "driving_car_ac", F100)["dose_ug"]


# --- band helpers + cigarettes (doc 10) ----------------------------------------

def test_band_is_conservative_linear_sum():
    """Doc 06 §1: band = sum of lo / sum of hi. σ=20 walking 10 min →
    sd_eff = 20·1.3·0.014·5 per half → ±3.64 total, linear not RSS."""
    r = dose(GEO, 600.0, "walking", F100,
             field_sigma=lambda lat, lon: 20.0)
    assert r["dose_ug"] == pytest.approx(18.2, abs=0.15)
    assert r["dose_ug_lo"] == pytest.approx(14.56, abs=0.15)
    assert r["dose_ug_hi"] == pytest.approx(21.84, abs=0.15)
    assert 0.0 <= r["dose_ug_lo"] <= r["dose_ug"] <= r["dose_ug_hi"]


def test_no_sigma_means_no_band_not_invented():
    r = dose(GEO, 600.0, "walking", F100)
    assert r["dose_ug_lo"] is None and r["dose_ug_hi"] is None
    assert r["dose_ug"] is not None


def test_huge_sigma_band_floors_at_zero():
    r = dose(GEO, 600.0, "metro", F100,
             field_sigma=lambda lat, lon: 500.0)
    assert r["dose_ug_lo"] == 0.0
    assert r["dose_ug_hi"] > r["dose_ug"]


def test_dose_to_cigs_doc10_example():
    """Doc 10's own claim: ~41 µg ≈ 0.13 cigarettes (316 µg/cig)."""
    assert CIG_UG == 316.0
    assert dose_to_cigs(41.0) == pytest.approx(0.13, abs=0.005)
    assert dose_to_cigs(316.0) == pytest.approx(1.0)
    assert dose_to_cigs(0.0) == 0.0
    assert dose_to_cigs(None) is None
    assert dose_to_cigs(float("nan")) is None


def test_cigs_band_shape_and_order():
    b = cigs_band(41.0, 32.0, 55.0)   # doc 10's example band
    assert b["lo"] < b["mid"] < b["hi"]
    assert b["mid"] == pytest.approx(0.13, abs=0.005)
    assert b["unit"] == "cigarettes"
    assert cigs_band(None)["mid"] is None


# --- edge hardening -------------------------------------------------------------

def test_nan_concentration_is_uncovered_not_nan():
    nan_field = lambda lat, lon: float("nan")
    r = dose(GEO, 600.0, "walking", nan_field)
    assert r["dose_ug"] is None
    assert r["coverage"] == 0.0 and r["sparse"] is True
    assert "field_no_coverage" in r["warnings"]
    # mixed NaN + valid: valid portion still scores, coverage drops
    # (samples land at segment ends lon 77.21/77.22)
    half_nan = lambda lat, lon: 100.0 if lon < 77.215 else float("nan")
    r2 = dose(GEO, 600.0, "walking", half_nan)
    assert r2["dose_ug"] is not None and r2["coverage"] < 1.0


def test_zero_length_and_degenerate_geometry():
    single = {"type": "LineString", "coordinates": [[77.2, 28.6]]}
    dup = {"type": "LineString", "coordinates": [[77.2, 28.6], [77.2, 28.6]]}
    for g in (single, dup, {}, None):
        r = dose(g, 600.0, "walking", F100)
        assert r["dose_ug"] is None and r["sparse"] is True
    assert segment_samples(single, 600.0) == []
    assert segment_samples(GEO, float("nan")) == []


def test_zero_and_negative_duration():
    r = dose(GEO, 0.0, "walking", F100)
    assert r["dose_ug"] == 0.0                    # no time → no dose, honestly
    assert dose(GEO, -60.0, "walking", F100)["dose_ug"] is None
    assert dose(GEO, float("nan"), "walking", F100)["dose_ug"] is None


def test_implausible_speed_flags_not_crashes():
    # ~1.95 km in 30 s ≈ 234 km/h — not a Delhi surface trip
    r = dose(GEO, 30.0, "driving_car_ac", F100)
    assert "speed_implausible" in r["warnings"]
    assert r["confidence"] == "low"
    assert r["implied_speed_kmh"] > exposure.PLAUSIBLE_MAX_KMH
    assert r["dose_ug"] is not None               # flagged, still computed


def test_route_leaving_field_coverage():
    # field exists only on the western half of the route
    patchy = lambda lat, lon: 120.0 if lon < 77.215 else None
    r = dose(GEO, 600.0, "walking", patchy)
    assert 0.0 < r["coverage"] < 1.0
    assert r["sparse"] is (r["coverage"] < 0.5)
    out = dose(GEO, 600.0, "walking", FNONE)
    assert out["dose_ug"] is None and out["confidence"] == "none"


def test_field_exception_and_negative_and_bad_sigma():
    boom = lambda lat, lon: (_ for _ in ()).throw(RuntimeError("boom"))
    r = dose(GEO, 600.0, "walking", boom)
    assert r["dose_ug"] is None and r["coverage"] == 0.0

    neg = dose(GEO, 600.0, "walking", lambda lat, lon: -40.0)
    assert neg["dose_ug"] == 0.0                  # PM can't be negative
    assert "negative_field_clamped" in neg["warnings"]

    bad_sig = dose(GEO, 600.0, "walking", F100,
                   field_sigma=lambda lat, lon: float("nan"))
    assert bad_sig["dose_ug_lo"] is None          # unusable σ → no band
    assert bad_sig["dose_ug"] is not None


def test_malformed_coords_dont_crash():
    bad = {"type": "LineString",
           "coordinates": [[77.2, 28.6], [float("nan"), None], ["x", "y"],
                           [77.22, 28.62]]}
    r = dose(bad, 600.0, "walking", F100)
    assert r is not None and "dose_ug" in r       # degrades, never raises


def test_unknown_mode_defaults_honestly():
    f = mode_factors("hovercraft")
    assert f["known_mode"] is False
    assert f["microenv"] == 1.0 and f["ventilation_lpm"] == 10.0
    r = dose(GEO, 600.0, "hovercraft", F100)
    assert "unknown_mode_defaulted" in r["warnings"]
    assert r["dose_ug"] is not None


def test_road_uplift_scales_and_arterial_alias():
    base = dose(GEO, 600.0, "walking", F100)["dose_ug"]
    prim = dose(GEO, 600.0, "walking", F100, road_class="primary")["dose_ug"]
    assert prim == pytest.approx(base * 1.20, rel=0.01)
    assert ROAD_UPLIFT["arterial"] == ROAD_UPLIFT["primary"]


def test_compare_ranks_and_survives_broken_option():
    opts = [{"mode": "walking", "geometry": GEO, "duration_s": 1800.0},
            {"mode": "metro", "geometry": GEO, "duration_s": 600.0},
            {"mode": "auto_rickshaw", "geometry": GEO, "duration_s": 540.0},
            {"mode": "walking", "geometry": None, "duration_s": 100.0}]
    out = compare(opts, F100)
    assert out[0]["mode"] == "metro"              # lowest dose first
    assert out[-1]["exposure"]["dose_ug"] is None  # broken → tail, no crash
    scored = [o for o in out if o["exposure"]["dose_ug"] is not None]
    assert all("ug_saved_vs_worst" in o["exposure"] for o in scored)
    assert all("dose_vs_best_pct" in o["exposure"] for o in scored)
