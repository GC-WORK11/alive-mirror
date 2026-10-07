"""Tests for emissions.py — the declared-vehicle → BS → EF → speed/idle/
cold-start inference chain.

Reference values are the published anchors in docs/29 §3 (ARAI/ICAP 2007
measured table, Guttikunda-2015 fleet ±SD, SIM Delhi PM2.5 set) and
docs/31 §3 (shared-mode per-passenger factors). The speed curve is
normalised to 1.0 at REF_SPEED_MPS so the tables are reproduced there.
"""
import pytest

import emissions
from emissions import REF_SPEED_MPS, COLD_KM

CAR_BS4 = {"class": "car", "fuel": "petrol", "year_bucket": "2010_2016"}
WARM = COLD_KM  # cold_km_done=COLD_KM → fully warm engine


def span(km, v=REF_SPEED_MPS):
    return {"dist_m": km * 1000.0, "speed_mps": v, "moving": True}


def idle_span(seconds):
    return {"dist_m": 0.0, "speed_mps": 0.0, "moving": False,
            "dur_s": float(seconds)}


def per_km_g(vehicle, pol, v=REF_SPEED_MPS):
    """Mid emission per km at speed v, warm engine."""
    r = emissions.integrate(vehicle, [span(1.0, v)], cold_km_done=WARM)
    key = {"co2": "co2_kg", "pm25": "pm25_g", "nox": "nox_g"}[pol]
    return r[key]["mid"] * (1000.0 if pol == "co2" else 1.0)


# --- 1. ARAI/published-table anchors (docs/29 §3) --------------------------

def test_arai_reference_values():
    # petrol car CO2: ARAI lab 95–143 + real-world uplift; WRI 100–270
    ef = emissions.emission_factors(CAR_BS4)
    assert 95 <= ef["co2"]["mid"] <= 270
    # petrol car PM2.5: ARAI lab 0.004–0.008 → Delhi fleet 0.05/0.101
    assert 0.004 <= ef["pm25"]["mid"] <= 0.101

    # diesel car BS-IV PM2.5: Guttikunda 0.162±1.186 / 0.333±1.365
    ef_d = emissions.emission_factors(
        {"class": "car", "fuel": "diesel", "year_bucket": "2010_2016"})
    assert 0.10 <= ef_d["pm25"]["mid"] <= 0.33
    # real-world diesel CO2 tail: Jaiprakash–Habib 556±261 → hi reaches it
    assert ef_d["co2"]["hi"] >= 400

    # 4-stroke 2W CO2: ARAI 23–46
    ef_2w = emissions.emission_factors(
        {"class": "scooter", "fuel": "petrol", "year_bucket": "2010_2016"})
    assert 23 <= ef_2w["co2"]["mid"] <= 46
    # 2W PM2.5: ARAI 0.010–0.035 lab, SIM/Guttikunda fleet ~0.05
    assert 0.010 <= ef_2w["pm25"]["mid"] <= 0.06

    # CNG auto PM: ARAI post-2005 auto 0.043 / SIM 3W-CNG 0.03
    ef_a = emissions.emission_factors(
        {"class": "auto", "fuel": "cng", "year_bucket": "2010_2016"})
    assert 0.02 <= ef_a["pm25"]["mid"] <= 0.06

    # CNG bus PM: ARAI 0.044 / SIM 0.02; CO2 807
    ef_b = emissions.emission_factors(
        {"class": "bus", "fuel": "cng", "year_bucket": "2010_2016"})
    assert 0.02 <= ef_b["pm25"]["mid"] <= 0.06
    assert 600 <= ef_b["co2"]["mid"] <= 950


def test_table_reproduced_at_reference_speed():
    # integrate 1 warm km at REF_SPEED == emission_factors mid (occupancy 1)
    ef = emissions.emission_factors(CAR_BS4)
    assert per_km_g(CAR_BS4, "pm25") == pytest.approx(ef["pm25"]["mid"])
    assert per_km_g(CAR_BS4, "co2") == pytest.approx(ef["co2"]["mid"])
    assert per_km_g(CAR_BS4, "nox") == pytest.approx(ef["nox"]["mid"])


# --- 2. BS bucketing --------------------------------------------------------

def test_bs_bucket_mapping():
    assert emissions.bs_bucket(CAR_BS4) == ("bs4", "high")
    # 2W cutovers lag cars: 2010–2016 → BS-III (docs/29 §2)
    assert emissions.bs_bucket(
        {"class": "bike", "fuel": "petrol",
         "year_bucket": "2010_2016"}) == ("bs3", "high")
    assert emissions.bs_bucket(
        {"class": "car", "fuel": "petrol",
         "year_bucket": "2020_plus"}) == ("bs6", "high")
    # 'not sure' → fleet prior (BS-IV dominant, docs/32), low confidence
    assert emissions.bs_bucket(
        {"class": "car", "fuel": "petrol",
         "year_bucket": "not_sure"}) == ("bs4", "low")
    assert emissions.bs_bucket({"class": "walk"}) == ("none", "high")


# --- 3. cold start ----------------------------------------------------------

def test_cold_start_first_4km_higher():
    s = [span(COLD_KM)]
    cold = emissions.integrate(CAR_BS4, s, cold_km_done=0.0)
    warm = emissions.integrate(CAR_BS4, s, cold_km_done=WARM)
    for k in ("pm25_g", "nox_g", "co2_kg"):
        for b in ("lo", "mid", "hi"):
            assert cold[k][b] > warm[k][b]


def test_cold_decays_over_first_4km():
    # km 0–1 is dirtier than km 5–6 of the same cold trip
    r = emissions.integrate(CAR_BS4, [span(1.0)], cold_km_done=0.0)
    first = r["pm25_g"]["mid"]
    r2 = emissions.integrate(CAR_BS4, [span(1.0)], cold_km_done=5.0)
    assert first > r2["pm25_g"]["mid"]
    # past COLD_KM the chain is exactly steady-state
    assert r2["pm25_g"]["mid"] == pytest.approx(
        emissions.emission_factors(CAR_BS4)["pm25"]["mid"])


# --- 4. idle ----------------------------------------------------------------

def test_idle_accrues_grams_per_second():
    r300 = emissions.integrate(CAR_BS4, [idle_span(300)], cold_km_done=WARM)
    r600 = emissions.integrate(CAR_BS4, [idle_span(600)], cold_km_done=WARM)
    # scales with seconds, not km — zero distance still emits
    assert r600["co2_kg"]["mid"] == pytest.approx(
        2.0 * r300["co2_kg"]["mid"])
    # ~0.4 g/s petrol-car idle → 300 s ≈ 0.12 kg CO2
    assert 0.06 < r300["co2_kg"]["mid"] < 0.25
    assert r300["pm25_g"]["mid"] > 0
    assert r300["distance_km"] == 0


def test_mixed_trip_idle_plus_driving():
    r = emissions.integrate(CAR_BS4, [span(2.0), idle_span(120)],
                            cold_km_done=WARM)
    assert r["breakdown"]["idle_mid"]["pm25"] > 0
    assert r["breakdown"]["moving_mid"]["pm25"] > 0


# --- 5. speed curve (COPERT U) ----------------------------------------------

def test_speed_curve_is_u_shaped():
    v10, v60, v110 = 10 / 3.6, 60 / 3.6, 110 / 3.6
    assert per_km_g(CAR_BS4, "pm25", v10) > per_km_g(CAR_BS4, "pm25")
    assert per_km_g(CAR_BS4, "pm25") > per_km_g(CAR_BS4, "pm25", v60)
    assert per_km_g(CAR_BS4, "pm25", v110) > per_km_g(CAR_BS4, "pm25", v60)


# --- 6. shared modes / per-passenger ----------------------------------------

def test_metro_per_pkm_band():
    r = emissions.integrate({"class": "metro"}, [span(10.0, 12.0)])
    lo = r["co2_kg"]["lo"] * 100  # g/pkm
    mid = r["co2_kg"]["mid"] * 100
    hi = r["co2_kg"]["hi"] * 100
    assert 11 <= lo <= mid <= hi <= 25
    assert r["pm25_g"]["mid"] == 0 and r["nox_g"]["mid"] == 0
    assert "electricity" in r["label"]


def test_shared_occupancy_division():
    auto = {"class": "auto", "fuel": "cng", "year_bucket": "2017_2019"}
    ef = emissions.emission_factors(auto)
    r = emissions.integrate(auto, [span(1.0)], cold_km_done=WARM)
    # per-passenger = vehicle ÷ 1.5 (docs/31 §3)
    assert r["co2_kg"]["mid"] * 1000 == pytest.approx(
        ef["co2"]["mid"] / 1.5)
    assert r["basis"] == "per_pax_km" and r["occupancy"] == 1.5


def test_bus_load_factor_per_pkm():
    bus = {"class": "bus", "fuel": "cng", "year_bucket": "2020_plus"}
    ef = emissions.emission_factors(bus)
    r = emissions.integrate(bus, [span(1.0)], cold_km_done=WARM)
    pax = emissions.BUS_CAPACITY * emissions.BUS_LOAD_FACTOR
    got = r["co2_kg"]["mid"] * 1000  # g/pkm
    assert got == pytest.approx(ef["co2"]["mid"] / pax)
    # docs/31 §3: CNG bus lands in the 20–60 g/pkm shared band
    assert 20 <= got <= 60


# --- 7. zero modes / honesty -------------------------------------------------

def test_walk_cycle_exactly_zero():
    for cls in ("walk", "cycle"):
        r = emissions.integrate({"class": cls}, [span(5.0)])
        for k in ("co2_kg", "pm25_g", "nox_g"):
            assert r[k] == {"lo": 0, "mid": 0, "hi": 0}
        assert r["label"] == "none"


def test_not_sure_year_widens_band():
    ns = emissions.emission_factors(
        {"class": "car", "fuel": "petrol", "year_bucket": "not_sure"})
    sp = emissions.emission_factors(CAR_BS4)
    for pol in ("co2", "pm25", "nox"):
        w_ns = ns[pol]["hi"] / ns[pol]["lo"]
        w_sp = sp[pol]["hi"] / sp[pol]["lo"]
        assert w_ns > w_sp, pol
    assert ns["confidence"] == "low"


def test_fuzzy_edge_widens_band():
    # before_2010 car spans BS-II..BS-III → strictly wider than clean BS-IV
    old = emissions.emission_factors(
        {"class": "car", "fuel": "diesel", "year_bucket": "before_2010"})
    assert old["bs_class"] == "bs3" and "bs2" in old["bs_options"]
    assert old["confidence"] == "low"


def test_every_quantity_is_a_band():
    for v in (CAR_BS4, {"class": "auto"},
              {"class": "car", "fuel": "diesel",
               "year_bucket": "not_sure"}):
        for k, band in emissions.emission_factors(v).items():
            if k in ("co2", "pm25", "nox"):
                assert band["lo"] <= band["mid"] <= band["hi"], (v, k)


# --- 8. integration invariants ----------------------------------------------

def test_monotonic_in_distance():
    route = [span(1.0), idle_span(60), span(2.0, 5.0), span(3.0, 15.0)]
    prev = {p: -1.0 for p in ("co2_kg", "pm25_g", "nox_g")}
    for i in range(1, len(route) + 1):
        r = emissions.integrate(CAR_BS4, route[:i], cold_km_done=WARM)
        for p in prev:
            assert r[p]["mid"] >= prev[p] >= -1.0
            assert r[p]["lo"] <= r[p]["mid"] <= r[p]["hi"]
        prev = {p: r[p]["mid"] for p in prev}


def test_distance_scales_linearly_when_warm():
    r1 = emissions.integrate(CAR_BS4, [span(5.0)], cold_km_done=WARM)
    r2 = emissions.integrate(CAR_BS4, [span(10.0)], cold_km_done=WARM)
    assert r2["pm25_g"]["mid"] == pytest.approx(2 * r1["pm25_g"]["mid"])


def test_non_exhaust_separate_band_not_in_headline():
    r = emissions.integrate(CAR_BS4, [span(10.0)], cold_km_done=WARM)
    nx = r["non_exhaust"]["pm10_g"]
    assert nx["mid"] > 0
    # resuspension is reported beside, never inside, the PM2.5 tailpipe band
    ef_pm = emissions.emission_factors(CAR_BS4)["pm25"]["mid"] * 10
    assert r["pm25_g"]["mid"] == pytest.approx(ef_pm)
    assert "resuspended" in r["non_exhaust"]["note"]


def test_ev_tailpipe_zero_but_grid_co2():
    r = emissions.integrate(
        {"class": "car", "fuel": "electric", "year_bucket": "2020_plus"},
        [span(10.0)], cold_km_done=WARM)
    assert r["pm25_g"]["mid"] == 0 and r["nox_g"]["mid"] == 0
    assert 0.8 < r["co2_kg"]["mid"] < 3.0     # ~0.17 kWh/km × 0.82 kg/kWh
    assert "grid" in r["label"] or "electric" in r["label"]


def test_label_shape():
    r = emissions.integrate(CAR_BS4, [span(5.0)], cold_km_done=WARM)
    assert r["label"].startswith("estimated for a ")
    assert "petrol car" in r["label"] and "BS-IV" in r["label"]


# --- trip_emissions: the /v2/plan preview bridge (doc 06 §3) ---------------

def test_trip_emissions_metro_band():
    r = emissions.trip_emissions("metro", distance_km=10.0, duration_s=1500)
    # 10 pkm x 11-25 g CO2e/pkm incl. electricity = 0.11-0.25 kg
    assert 0.11 <= r["co2_kg"]["lo"] <= r["co2_kg"]["mid"] <= r["co2_kg"]["hi"] <= 0.25 + 1e-9
    assert r["pm25_g"]["mid"] == 0


def test_trip_emissions_idle_surcharge():
    km, free, jam = 8.0, 900.0, 1500.0
    moving = emissions.trip_emissions("car", distance_km=km, duration_s=free,
                                      freeflow_s=free)
    stuck = emissions.trip_emissions("car", distance_km=km, duration_s=jam,
                                     freeflow_s=free)
    assert stuck["co2_kg"]["mid"] > moving["co2_kg"]["mid"]
    assert stuck["breakdown"]["idle_mid"]["co2"] > 0


def test_trip_emissions_walk_and_car_open():
    r = emissions.trip_emissions("walk", distance_km=2.0, duration_s=1400)
    assert r["co2_kg"]["mid"] == 0 and r["label"] == "none"
    r = emissions.trip_emissions("car_open", distance_km=5.0, duration_s=900)
    assert r["co2_kg"]["mid"] > 0 and r["class"] == "car"


def test_trip_emissions_unknown_mode_raises():
    with pytest.raises(ValueError):
        emissions.trip_emissions("helicopter", distance_km=1.0, duration_s=60)
