"""Emissions inference engine — "vehicles like yours" bands, never points.

Chain (docs/plan/06 §2):
    declared {class, fuel, year_bucket}
      → BS bucket        (Delhi registration-year cutover table, docs/29 §2;
                          ±1-reg-year fuzzy edge at every cutover → widen band)
      → EF band/pollutant (ARAI/ICAP-2007 measured table + Guttikunda-2015
                          fleet ±SD + SIM/urbanemissions Delhi PM2.5 set;
                          real-world uplift per Jaiprakash–Habib / ICCT /
                          ICCT-TRUE remote sensing — docs/29 §3–4)
      → speed curve ef(v) (COPERT U-shape; normalised to 1.0 at REF_SPEED_MPS
                          so the published table is reproduced at ref speed)
      → idle floor (g/s) + cold-start penalty over first COLD_KM km
      → integrate over spans [{dist_m, speed_mps, moving, dur_s?}]

Every returned quantity is a band {lo, mid, hi}; we NEVER emit a per-vehicle
point value — docs/29 §5, docs/plan/10 (claims ledger).

Anchors used (all from repo docs):
  ARAI/ICAP 2007 measured, g/km, MIDC in-use fleet (docs/29 §3):
    2-stroke auto pre-2000 → post-2005  PM 0.110 → 0.043,  CO2 55 → 72
    4-stroke motorcycle/scooter          PM 0.010–0.035,    CO2 23–46
    petrol car <1400cc                   PM 0.004–0.008,    CO2 95–143
    diesel car                           PM 0.015–0.19/vtg, CO2 129–157
    CNG car retrofit                     PM 0.001–0.006,    CO2 131–150
    city bus diesel                      PM 0.30–2.01,      CO2 602–921
    CNG bus                              PM 0.044,          CO2 807
  Guttikunda-2015 Table 5 fleet ±SD (docs/26 §3.1):
    petrol car PM2.5 0.050±0.228 / 0.101±0.257, NOx 0.243/0.376
    diesel car PM2.5 0.162±1.186 / 0.333±1.365, NOx 0.657/1.162
    petrol 2W 0.025±0.051 / NOx 0.392; petrol 3W 0.024±0.174 / NOx 0.692
    diesel bus PM2.5 2.672±7.586 / NOx 21.38; CNG car 0.016±0.118 / NOx 0.198
  SIM/urbanemissions Delhi PM2.5 g/km (docs/29 §3): petrol car 0.05,
    diesel car 0.15, CNG car 0.03, diesel bus 0.34, CNG bus 0.02,
    3W petrol 0.08 / CNG 0.03, 2W 0.05.
  Real-world uplift (docs/29 §3–4): Jaiprakash & Habib on-road post-2010
    diesel cars CO2 556±261, NOx 3.1±2.9; ICCT BS-IV NOx 5–7×, CO 10–22×
    type-approval; TRUE Delhi 2024 — BS-VI taxi NOx 2.4× private, CNG BS-VI
    1.5–14× over limits ("CNG is not clean" → wide hi tails, not marketing).
  Shared modes (docs/31 §3): auto ÷1.5 pax, cab ÷1.3, bus ÷(50×40% load),
    metro 11–25 g CO2e/pkm incl. electricity (CEA grid OM/CM 0.71–0.92).
  Fleet prior for "not sure" year (docs/32 §0/§2): ~89% of measured on-road
    vehicles BS-IV+; diesel >10y / petrol >15y legally off Delhi roads.
  Non-exhaust (docs/26 §3.2): ~86% of Delhi traffic PM10 is non-exhaust
    (resuspension alone ~79%, Sahu et al. STOTEN 2020) — reported as a
    separate per-vkm band, NEVER folded into the headline numbers.
"""

# --- calibration ----------------------------------------------------------
REF_SPEED_MPS = 30.0 / 3.6      # ≈8.33 m/s — MIDC urban-average; ef(v)=1 here
V_OPT_MPS = 50.0 / 3.6          # curve minimum ≈50 km/h (COPERT structure)
V_FLOOR_MPS = 2.5               # ≈9 km/h — below this the curve is pinned;
                                # slower motion belongs in the idle bucket
COLD_KM = 4.0                   # cold-start penalty zone, linear decay to 0

# Shared-mode per-passenger accounting (docs/31 §3)
OCCUPANCY = {"auto": 1.5, "cab": 1.3}
BUS_CAPACITY = 50
BUS_LOAD_FACTOR = 0.40          # → 20 pax; docs/31: ÷15–40 onboard
METRO_CO2E_GPKM = (11.0, 17.0, 25.0)   # docs/31 §3, incl. electricity

# Well-to-wheel for electrics (docs/31 §3 boundary)
GRID_KG_PER_KWH = (0.71, 0.82, 0.92)   # CEA OM/CM, RE share credited in mid
EV_KWH_PER_KM = {                     # {ef_group: (lo, mid, hi)}
    "2w":   (0.025, 0.038, 0.055),
    "car":  (0.13, 0.17, 0.24),       # cab reuses car
    "auto": (0.050, 0.065, 0.090),    # e-rickshaw-class
    "bus":  (0.98, 1.15, 1.30),       # ITDP rollout guide (docs/31 §3)
}

ZERO = (0.0, 0.0, 0.0)

# --- vehicle taxonomy -----------------------------------------------------
_EF_GROUP = {"car": "car", "cab": "car", "scooter": "2w", "bike": "2w",
             "auto": "auto", "bus": "bus"}
_BS_GROUP = {"car": "4w", "cab": "4w", "scooter": "2w", "bike": "2w",
             "auto": "3w", "bus": "4w"}
_NON_MOTOR = ("walk", "cycle")

_DEFAULT_FUEL = {"car": "petrol", "cab": "cng", "scooter": "petrol",
                 "bike": "petrol", "auto": "cng", "bus": "cng"}
_VALID_FUELS = {
    "car":     {"petrol", "diesel", "cng", "electric"},
    "cab":     {"petrol", "diesel", "cng", "electric"},
    "scooter": {"petrol", "electric"},
    "bike":    {"petrol", "electric"},
    "auto":    {"cng", "petrol", "electric"},
    "bus":     {"cng", "diesel", "electric"},
}

# --- BS buckets: Delhi registration-year table (docs/29 §2) ----------------
# year_bucket → (dominant_bs, possible_bs_classes, confidence).
# possible > dominant at every ±1-reg-year fuzzy edge (dealer stock clearance
# at cutovers; early BS-VI 2018-19 Delhi regs; BS-IV grace to mid-2020).
# 2W/3W cutovers lag 4W: BS-III only Apr-2010, BS-IV sales Apr-2017, BS-VI
# Apr-2020 (docs/29 §2 caveat row). Pre-2001 BS-I tail is folded into bs2's hi.
_BS_BY_YEAR = {
    "4w": {"before_2010": ("bs3", ("bs2", "bs3"), "low"),
           "2010_2016":   ("bs4", ("bs3", "bs4"), "high"),
           "2017_2019":   ("bs4", ("bs4", "bs6"), "high"),
           "2020_plus":   ("bs6", ("bs4", "bs6"), "high")},
    "2w": {"before_2010": ("bs2", ("bs2", "bs3"), "medium"),
           "2010_2016":   ("bs3", ("bs3", "bs4"), "high"),
           "2017_2019":   ("bs4", ("bs4",), "high"),
           "2020_plus":   ("bs6", ("bs4", "bs6"), "high")},
    "3w": {"before_2010": ("bs2", ("bs2", "bs3"), "medium"),
           "2010_2016":   ("bs3", ("bs3", "bs4"), "high"),
           "2017_2019":   ("bs4", ("bs4",), "high"),
           "2020_plus":   ("bs6", ("bs4", "bs6"), "high")},
}

# Delhi fleet prior for 'not_sure' (docs/32 §2.1: ~89% BS-IV+ measured on-road;
# BS-IV single largest block). Diesel drops pre-BS-IV — >10y diesels are
# legally off Delhi roads (NGT/SC ban, enforced via ANPR fuel-denial).
_FLEET_PRIOR = {
    ("4w", "petrol"):  {"bs3": 0.08, "bs4": 0.52, "bs6": 0.40},
    ("4w", "diesel"):  {"bs4": 0.55, "bs6": 0.45},
    ("4w", "cng"):     {"bs3": 0.10, "bs4": 0.55, "bs6": 0.35},
    ("2w", "petrol"):  {"bs2": 0.03, "bs3": 0.12, "bs4": 0.55, "bs6": 0.30},
    ("3w", "cng"):     {"bs2": 0.02, "bs3": 0.18, "bs4": 0.50, "bs6": 0.30},
    ("3w", "petrol"):  {"bs2": 0.03, "bs3": 0.20, "bs4": 0.52, "bs6": 0.25},
    ("bus", "cng"):    {"bs3": 0.10, "bs4": 0.50, "bs6": 0.40},
    ("bus", "diesel"): {"bs3": 0.10, "bs4": 0.55, "bs6": 0.35},
}

# --- emission-factor table ------------------------------------------------
# g/km (lo, mid, hi) at REF_SPEED_MPS, warm engine, real-world Delhi band.
# lo ≈ clean/well-maintained of the class; mid ≈ class median; hi covers the
# published super-emitter tail (2–14× over limits — docs/29 §4), NOT a
# worst-case vehicle. cab = car × _TAXI_UPLIFT (TRUE: usage dominates class).
_EF = {
    "car": {
        "petrol": {
            # PM2.5: ARAI measured petrol cars 0.004–0.008 — petrol exhaust PM
            # is tiny; mid stays near ARAI (uplift is a diesel/high-use story,
            # docs/29 §5), hi carries the Guttikunda fleet 0.05 + GDI tail.
            "bs2": {"co2": (125, 180, 280), "pm25": (0.012, 0.035, 0.220),
                    "nox": (0.30, 0.65, 1.40)},
            "bs3": {"co2": (118, 168, 265), "pm25": (0.008, 0.025, 0.160),
                    "nox": (0.25, 0.52, 1.10)},
            "bs4": {"co2": (110, 155, 250), "pm25": (0.005, 0.012, 0.100),
                    "nox": (0.15, 0.40, 0.90)},
            "bs6": {"co2": (105, 148, 240), "pm25": (0.004, 0.010, 0.080),
                    "nox": (0.10, 0.30, 0.72)},
        },
        "diesel": {
            "bs2": {"co2": (135, 215, 480), "pm25": (0.100, 0.320, 0.950),
                    "nox": (0.80, 1.60, 4.50)},
            "bs3": {"co2": (132, 205, 460), "pm25": (0.080, 0.240, 0.720),
                    "nox": (0.70, 1.40, 4.00)},
            # CO2 hi: Jaiprakash–Habib real-world 556±261 g/km
            "bs4": {"co2": (130, 195, 560), "pm25": (0.050, 0.160, 0.550),
                    "nox": (0.60, 1.20, 6.00)},
            # BS-VI DPF floor 0.0045 g/km (type-approval, docs/29 §3)
            "bs6": {"co2": (125, 185, 500), "pm25": (0.003, 0.010, 0.060),
                    "nox": (0.15, 0.50, 1.60)},
        },
        "cng": {
            # hi tails: ICCT TRUE — high-use CNG 1.5–14× over type-approval
            "bs2": {"co2": (135, 175, 270), "pm25": (0.010, 0.030, 0.160),
                    "nox": (0.15, 0.35, 1.60)},
            "bs3": {"co2": (130, 168, 260), "pm25": (0.008, 0.025, 0.140),
                    "nox": (0.12, 0.30, 1.40)},
            "bs4": {"co2": (125, 160, 250), "pm25": (0.006, 0.016, 0.120),
                    "nox": (0.10, 0.20, 1.20)},
            "bs6": {"co2": (120, 152, 240), "pm25": (0.005, 0.014, 0.100),
                    "nox": (0.08, 0.18, 1.00)},
        },
    },
    "2w": {
        "petrol": {
            "bs2": {"co2": (24, 36, 52), "pm25": (0.025, 0.050, 0.130),
                    "nox": (0.15, 0.36, 0.85)},
            "bs3": {"co2": (23, 35, 50), "pm25": (0.020, 0.042, 0.110),
                    "nox": (0.12, 0.30, 0.68)},
            "bs4": {"co2": (22, 34, 48), "pm25": (0.015, 0.032, 0.090),
                    "nox": (0.10, 0.26, 0.55)},
            "bs6": {"co2": (21, 32, 46), "pm25": (0.010, 0.026, 0.075),
                    "nox": (0.08, 0.21, 0.45)},
        },
    },
    "auto": {
        "cng": {
            # ARAI: post-2005 auto PM 0.043; SIM 3W-CNG 0.03
            "bs2": {"co2": (62, 88, 125), "pm25": (0.022, 0.065, 0.170),
                    "nox": (0.20, 0.62, 1.90)},
            "bs3": {"co2": (58, 82, 118), "pm25": (0.016, 0.052, 0.145),
                    "nox": (0.18, 0.56, 1.70)},
            "bs4": {"co2": (55, 78, 112), "pm25": (0.012, 0.040, 0.120),
                    "nox": (0.15, 0.50, 1.45)},
            "bs6": {"co2": (52, 74, 106), "pm25": (0.010, 0.032, 0.100),
                    "nox": (0.12, 0.42, 1.20)},
        },
        "petrol": {
            # SIM 3W-petrol PM 0.08; Guttikunda petrol-3W NOx 0.692
            "bs2": {"co2": (65, 95, 135), "pm25": (0.040, 0.100, 0.240),
                    "nox": (0.25, 0.75, 2.00)},
            "bs3": {"co2": (62, 90, 128), "pm25": (0.030, 0.090, 0.220),
                    "nox": (0.22, 0.70, 1.90)},
            "bs4": {"co2": (58, 85, 120), "pm25": (0.025, 0.080, 0.200),
                    "nox": (0.18, 0.60, 1.70)},
            "bs6": {"co2": (55, 80, 115), "pm25": (0.020, 0.070, 0.180),
                    "nox": (0.15, 0.50, 1.40)},
        },
    },
    "bus": {
        "cng": {
            # ARAI CNG bus PM 0.044 / CO2 807; SIM CNG bus 0.02
            "bs2": {"co2": (640, 810, 970), "pm25": (0.020, 0.055, 0.130),
                    "nox": (3.5, 9.5, 22.0)},
            "bs3": {"co2": (620, 790, 950), "pm25": (0.015, 0.045, 0.110),
                    "nox": (3.0, 8.5, 20.0)},
            "bs4": {"co2": (600, 760, 930), "pm25": (0.010, 0.035, 0.095),
                    "nox": (2.5, 7.5, 18.0)},
            "bs6": {"co2": (560, 720, 900), "pm25": (0.006, 0.025, 0.075),
                    "nox": (2.0, 6.0, 15.0)},
        },
        "diesel": {
            # ARAI city-bus diesel PM 0.30–2.01 / CO2 602–921; Guttikunda
            # diesel bus PM2.5 2.672±7.586, NOx 21.38 → huge hi tails
            "bs2": {"co2": (660, 840, 980), "pm25": (0.60, 2.00, 8.00),
                    "nox": (11.0, 18.0, 32.0)},
            "bs3": {"co2": (640, 810, 960), "pm25": (0.40, 1.50, 6.00),
                    "nox": (10.0, 16.0, 30.0)},
            "bs4": {"co2": (620, 780, 940), "pm25": (0.30, 1.00, 4.50),
                    "nox": (8.0, 15.0, 28.0)},
            "bs6": {"co2": (600, 760, 920), "pm25": (0.010, 0.050, 0.300),
                    "nox": (3.0, 8.0, 18.0)},
        },
    },
}

# Taxi/cab high-use uplift on the car table — TRUE Delhi: BS-VI taxi NOx
# 2.4× private cars, same BS class ("same class, different life", docs/29 §4).
_TAXI_UPLIFT = {"co2": (1.05, 1.15, 1.60),
                "pm25": (1.10, 1.30, 2.00),
                "nox": (1.10, 1.50, 2.40)}

# --- idle floor, g/s ------------------------------------------------------
# ~0.5–0.8 L/hr fuel burn for a car at idle → ~0.3–0.5 g/s CO2. Scaled by
# engine size; pollutant rates keep the same honesty ratio as the g/km bands.
_IDLE = {
    ("car", "petrol"):  {"co2": (0.25, 0.40, 0.65), "pm25": (0.00008, 0.0003, 0.0012), "nox": (0.001, 0.0025, 0.007)},
    ("car", "diesel"):  {"co2": (0.22, 0.36, 0.60), "pm25": (0.00020, 0.0007, 0.0025), "nox": (0.0015, 0.0035, 0.010)},
    ("car", "cng"):     {"co2": (0.20, 0.33, 0.55), "pm25": (0.00005, 0.0002, 0.0009), "nox": (0.001, 0.0025, 0.009)},
    ("car", "electric"): {"co2": (0.03, 0.08, 0.16), "pm25": ZERO, "nox": ZERO},
    ("2w", "petrol"):   {"co2": (0.07, 0.12, 0.20), "pm25": (0.00008, 0.0002, 0.0006), "nox": (0.0004, 0.001, 0.003)},
    ("2w", "electric"): {"co2": (0.01, 0.03, 0.06), "pm25": ZERO, "nox": ZERO},
    ("auto", "cng"):    {"co2": (0.09, 0.15, 0.26), "pm25": (0.00008, 0.00025, 0.0009), "nox": (0.0006, 0.0015, 0.005)},
    ("auto", "petrol"): {"co2": (0.10, 0.17, 0.28), "pm25": (0.00020, 0.0005, 0.0015), "nox": (0.0007, 0.0018, 0.006)},
    ("auto", "electric"): {"co2": (0.01, 0.04, 0.08), "pm25": ZERO, "nox": ZERO},
    ("bus", "cng"):     {"co2": (0.55, 0.90, 1.45), "pm25": (0.0001, 0.0004, 0.0015), "nox": (0.008, 0.020, 0.055)},
    ("bus", "diesel"):  {"co2": (0.65, 1.00, 1.60), "pm25": (0.0008, 0.003, 0.012), "nox": (0.010, 0.028, 0.075)},
    ("bus", "electric"): {"co2": (0.15, 0.35, 0.60), "pm25": ZERO, "nox": ZERO},
}

# --- cold-start multiplier ------------------------------------------------
# Multiplier at km 0 of a cold trip, decaying linearly to 1.0 at COLD_KM.
# SI catalysts dominate the penalty (petrol > CNG > diesel). Band honesty:
# applied at 0.7 strength to lo, 1.3 to hi — cold engines widen the spread.
_COLD_MULT = {
    "petrol":   {"co2": 1.30, "pm25": 2.5, "nox": 1.6},
    "diesel":   {"co2": 1.15, "pm25": 1.6, "nox": 1.3},
    "cng":      {"co2": 1.25, "pm25": 2.0, "nox": 1.5},
    "electric": {"co2": 1.00, "pm25": 1.0, "nox": 1.0},
}

# --- non-exhaust (separate band, NEVER in headline) ------------------------
# g PM10 per vkm: resuspended road dust + brake/tyre wear. ~86% of Delhi
# traffic PM10 is non-exhaust, resuspension ~79% (Sahu et al. STOTEN 2020,
# docs/26 §3.2). Inventories allocate it per-VKT; scales with vehicle mass.
_NON_EXHAUST_PM10_GVKM = {
    "2w":   (0.02, 0.06, 0.15),
    "auto": (0.03, 0.08, 0.20),
    "car":  (0.05, 0.15, 0.40),   # cab reuses car
    "bus":  (0.20, 0.50, 1.30),
}

# --- speed curve ef(v) ----------------------------------------------------
# COPERT structure: U-curve, minimum near V_OPT, steep rise below V_OPT
# (stop-go: acceleration enrichment, idle creep) and quadratic rise above
# (aero/load). Normalised so ef(REF_SPEED)=1 → the published table is
# reproduced at the MIDC reference speed. (L, H) per pollutant.
_SPEED_PARAMS = {"co2": (1.2, 0.8), "pm25": (1.8, 1.2), "nox": (0.9, 1.4)}


def _g_curve(pol, v_mps):
    L, H = _SPEED_PARAMS[pol]
    v = max(v_mps, V_FLOOR_MPS)
    if v < V_OPT_MPS:
        return 1.0 + L * ((V_OPT_MPS - v) / V_OPT_MPS) ** 2 * (V_OPT_MPS / v)
    return 1.0 + H * ((v - V_OPT_MPS) / V_OPT_MPS) ** 2


_G_REF = {p: _g_curve(p, REF_SPEED_MPS) for p in _SPEED_PARAMS}


def speed_factor(pol, v_mps):
    """ef(v)/ef(v_ref) — COPERT U-curve, 1.0 at REF_SPEED_MPS by construction."""
    return _g_curve(pol, v_mps) / _G_REF[pol]


# --- resolution helpers ----------------------------------------------------
_BS_NAME = {"bs2": "BS-II", "bs3": "BS-III", "bs4": "BS-IV",
            "bs6": "BS-VI", "none": ""}
_YEAR_NAME = {"before_2010": "pre-2010", "2010_2016": "2010–2016",
              "2017_2019": "2017–2019", "2020_plus": "2020+"}
_CLASS_NAME = {"car": "car", "cab": "cab", "scooter": "scooter",
               "bike": "motorcycle", "auto": "auto-rickshaw", "bus": "bus",
               "walk": "walk", "cycle": "cycle", "metro": "metro"}
_FUEL_NAME = {"petrol": "petrol", "diesel": "diesel", "cng": "CNG",
             "electric": "electric"}


def _resolve(vehicle):
    """Normalise the declared vehicle dict → (vclass, fuel, year_bucket)."""
    vclass = (vehicle.get("class") or "").lower().strip()
    if vclass in _NON_MOTOR or vclass == "metro":
        return vclass, None, vehicle.get("year_bucket", "not_sure")
    if vclass not in _EF_GROUP:
        raise ValueError(f"unknown vehicle class: {vclass!r}")
    fuel = (vehicle.get("fuel") or _DEFAULT_FUEL[vclass]).lower().strip()
    if fuel not in _VALID_FUELS[vclass]:
        fuel = _DEFAULT_FUEL[vclass]    # e.g. "diesel scooter" → Delhi reality
    year = vehicle.get("year_bucket") or "not_sure"
    if year not in _YEAR_NAME and year != "not_sure":
        year = "not_sure"
    return vclass, fuel, year


def _bs_options(vclass, fuel, year):
    """→ (dominant_bs, tuple(possible_bs), confidence, prior_dict_or_None)."""
    if fuel == "electric" or vclass in _NON_MOTOR or vclass == "metro":
        return "none", ("none",), "high", None
    group = _BS_GROUP[vclass]
    if year == "not_sure":
        pgroup = {"car": "4w", "2w": "2w", "auto": "3w",
                  "bus": "bus"}[_EF_GROUP[vclass]]
        prior = _FLEET_PRIOR.get((pgroup, fuel)) or \
            _FLEET_PRIOR[(pgroup, "petrol" if pgroup != "bus" else "cng")]
        dom = max(prior, key=prior.get)
        return dom, tuple(prior), "low", prior
    dom, opts, conf = _BS_BY_YEAR[group][year]
    return dom, opts, conf, None


def _occupancy(vclass):
    if vclass == "bus":
        return BUS_CAPACITY * BUS_LOAD_FACTOR
    return OCCUPANCY.get(vclass, 1.0)


def _ev_ef(vclass):
    """WTW band for an EV: tailpipe PM/NOx zero, CO2 = kWh × grid EF."""
    e = EV_KWH_PER_KM[_EF_GROUP[vclass]]
    g = GRID_KG_PER_KWH
    return {"co2": tuple(round(e[i] * g[i] * 1000.0, 1) for i in range(3)),
            "pm25": ZERO, "nox": ZERO}


def _ice_ef(vclass, fuel, bs):
    """Vehicle-level g/km band for one (class, fuel, BS) — car→cab uplifted."""
    row = _EF[_EF_GROUP[vclass]][fuel][bs]
    if vclass == "cab":
        return {p: tuple(row[p][i] * _TAXI_UPLIFT[p][i] for i in range(3))
                for p in row}
    return row


def _merge_band(vclass, fuel, dom, opts, prior):
    """Union band over possible BS classes.
    mid = dominant-class mid, or the fleet-prior-weighted mean for 'not sure'."""
    rows = [(_ice_ef(vclass, fuel, b), (prior or {}).get(b)) for b in opts]
    out = {}
    for pol in ("co2", "pm25", "nox"):
        lo = min(r[pol][0] for r, _ in rows)
        hi = max(r[pol][2] for r, _ in rows)
        if prior:
            mid = sum(r[pol][1] * w for r, w in rows) / sum(prior.values())
        else:
            mid = _ice_ef(vclass, fuel, dom)[pol][1]
        out[pol] = (lo, mid, hi)
    return out


def _label(vclass, fuel, year, dom, opts):
    cname = _CLASS_NAME[vclass]
    if fuel == "electric":
        return (f"estimated for vehicles like yours (electric {cname}, "
                f"incl. grid electricity)")
    bs_txt = _BS_NAME[dom] if len(opts) == 1 else \
        "–".join((_BS_NAME[opts[0]], _BS_NAME[opts[-1]]))
    if year == "not_sure":
        return (f"estimated for vehicles like yours "
                f"({_FUEL_NAME[fuel]} {cname}, Delhi fleet mix — {bs_txt})")
    return (f"estimated for vehicles like yours "
            f"({_YEAR_NAME[year]} {_FUEL_NAME[fuel]} {cname}, {bs_txt})")


def _band(lo, mid, hi, nd=4):
    return {"lo": round(lo, nd), "mid": round(mid, nd), "hi": round(hi, nd)}


# --- public API ------------------------------------------------------------
def bs_bucket(vehicle):
    """declared vehicle → (bs_class, confidence).
    'none' for EV/non-motorized/metro; 'low' confidence for 'not_sure'."""
    vclass, fuel, year = _resolve(vehicle)
    dom, _opts, conf, _prior = _bs_options(vclass, fuel, year)
    return dom, conf


def emission_factors(vehicle):
    """Per-km pollutant bands at REF_SPEED_MPS, warm engine.

    Road vehicles → vehicle-level g/km (basis 'per_vkm', occupancy noted for
    shared modes — per-passenger division happens in integrate()).
    Metro → per-passenger-km CO2e incl. electricity. Walk/cycle → zeros.
    """
    vclass, fuel, year = _resolve(vehicle)
    if vclass in _NON_MOTOR:
        return {"co2": _band(*ZERO), "pm25": _band(*ZERO),
                "nox": _band(*ZERO), "units": "g/km", "basis": "none",
                "bs_class": "none", "confidence": "high", "label": "none"}
    if vclass == "metro":
        return {"co2": _band(*METRO_CO2E_GPKM), "pm25": _band(*ZERO),
                "nox": _band(*ZERO), "units": "g/pkm",
                "basis": "per_pax_km", "bs_class": "none",
                "confidence": "high",
                "label": "metro per passenger-km (incl. electricity)"}
    dom, opts, conf, prior = _bs_options(vclass, fuel, year)
    band = _ev_ef(vclass) if fuel == "electric" else \
        _merge_band(vclass, fuel, dom, opts, prior)
    return {"co2": _band(*band["co2"]), "pm25": _band(*band["pm25"]),
            "nox": _band(*band["nox"]), "units": "g/km",
            "basis": "per_vkm", "occupancy": _occupancy(vclass),
            "bs_class": dom, "bs_options": list(opts), "confidence": conf,
            "label": _label(vclass, fuel, year, dom, opts)}


def _idle_band(vclass, fuel):
    key = (_EF_GROUP[vclass], fuel)
    return _IDLE.get(key) or _IDLE[(_EF_GROUP[vclass],
                                    _DEFAULT_FUEL.get(vclass, "petrol"))]


def _cold_avg_mult(c, d_start, cold_len_km):
    """Mean of 1+(C-1)(1 - x/COLD_KM) over the cold overlap [d_start,
    d_start+cold_len_km] — closed form, not sampled."""
    x_avg = d_start + cold_len_km / 2.0
    return 1.0 + (c - 1.0) * (1.0 - x_avg / COLD_KM)


def integrate(vehicle, spans, cold_km_done=0.0):
    """Trip emissions as bands.

    spans: [{dist_m, speed_mps, moving, dur_s?}] — moving spans accrue
    g/km at ef(v); non-moving spans accrue g/s over dur_s (or dist/speed).
    cold_km_done: trip km already driven (multi-leg calls) — the cold-start
    penalty only applies to the first COLD_KM km of a cold trip.
    Returns {co2_kg, pm25_g, nox_g} each {lo,mid,hi} + label + provenance;
    shared modes are per-passenger, private modes per vehicle trip.
    """
    vclass, fuel, year = _resolve(vehicle)

    if vclass in _NON_MOTOR:
        return {"co2_kg": _band(*ZERO), "pm25_g": _band(*ZERO),
                "nox_g": _band(*ZERO), "label": "none", "basis": "none",
                "bs_class": "none", "confidence": "high",
                "non_exhaust": {"pm10_g": _band(*ZERO),
                                "note": "zero — non-motorized mode"},
                "breakdown": {}}

    if vclass == "metro":
        km = sum(s.get("dist_m", 0.0) for s in spans) / 1000.0
        g = METRO_CO2E_GPKM
        return {"co2_kg": _band(g[0] * km / 1000.0, g[1] * km / 1000.0,
                                g[2] * km / 1000.0),
                "pm25_g": _band(*ZERO), "nox_g": _band(*ZERO),
                "label": "metro per passenger-km, incl. electricity "
                         "(11–25 g CO2e/pkm — DMRC + CEA grid EF, docs/31 §3)",
                "basis": "per_pax_km", "bs_class": "none",
                "confidence": "high",
                "non_exhaust": {"pm10_g": _band(*ZERO),
                                "note": "rail — no road resuspension"},
                "breakdown": {}}

    dom, opts, conf, prior = _bs_options(vclass, fuel, year)
    occ = _occupancy(vclass)
    band = _ev_ef(vclass) if fuel == "electric" else \
        _merge_band(vclass, fuel, dom, opts, prior)
    idle = _idle_band(vclass, fuel)
    cold = _COLD_MULT[fuel]
    nx = _NON_EXHAUST_PM10_GVKM[_EF_GROUP[vclass]]

    acc = {p: [0.0, 0.0, 0.0] for p in ("co2", "pm25", "nox")}
    acc_nx = [0.0, 0.0, 0.0]
    moving_mid = {p: 0.0 for p in acc}
    idle_mid = {p: 0.0 for p in acc}
    cold_mid = {p: 0.0 for p in acc}
    d = max(0.0, float(cold_km_done or 0.0))   # km since cold start
    tot_km = 0.0

    for s in spans or []:
        dist_m = float(s.get("dist_m") or 0.0)
        v = float(s.get("speed_mps") or 0.0)
        moving = bool(s.get("moving", True))

        if moving and dist_m > 0.0:
            km = dist_m / 1000.0
            tot_km += km
            # cold-zone overlap [d, d+km] ∩ [0, COLD_KM]
            cold_len = min(d + km, COLD_KM) - d if d < COLD_KM else 0.0
            warm_len = km - max(0.0, cold_len)
            for p in acc:
                f = speed_factor(p, v)
                sw = 1.0 + 0.2 * abs(f - 1.0)      # speed-curve uncertainty
                lo, mid, hi = band[p]
                km_lo, km_mid, km_hi = lo * f / sw, mid * f, hi * f * sw
                if cold_len > 0.0:
                    c = cold[p]
                    ml = _cold_avg_mult(1.0 + (c - 1.0) * 0.7, d, cold_len)
                    mm = _cold_avg_mult(c, d, cold_len)
                    mh = _cold_avg_mult(1.0 + (c - 1.0) * 1.3, d, cold_len)
                    acc[p][0] += km_lo * (cold_len * ml + warm_len)
                    acc[p][1] += km_mid * (cold_len * mm + warm_len)
                    acc[p][2] += km_hi * (cold_len * mh + warm_len)
                    cold_mid[p] += km_mid * cold_len * (mm - 1.0)
                else:
                    acc[p][0] += km_lo * km
                    acc[p][1] += km_mid * km
                    acc[p][2] += km_hi * km
                moving_mid[p] += km_mid * km
            for i in range(3):
                acc_nx[i] += nx[i] * km
            d += km
        else:
            # idle bucket — accrue per second, never per km
            dur = s.get("dur_s")
            if dur is None:
                dur = dist_m / v if v > 0.3 else 0.0
            dur = max(0.0, float(dur))
            for p in acc:
                for i in range(3):
                    acc[p][i] += idle[p][i] * dur
                idle_mid[p] += idle[p][1] * dur

    # shared modes: everything above is vehicle-level → per passenger
    if occ > 1.0:
        for p in acc:
            for i in range(3):
                acc[p][i] /= occ
            idle_mid[p] /= occ
            moving_mid[p] /= occ
            cold_mid[p] /= occ
        for i in range(3):
            acc_nx[i] /= occ

    def _kg(t):
        return _band(t[0] / 1000.0, t[1] / 1000.0, t[2] / 1000.0, nd=4)

    label = _label(vclass, fuel, year, dom, opts)
    if fuel == "electric":
        label += " — tailpipe zero"
    if occ > 1.0:
        label += f", per passenger (÷{occ:g})"

    return {
        "co2_kg": _kg(acc["co2"]),
        "pm25_g": _band(*acc["pm25"]),
        "nox_g": _band(*acc["nox"]),
        "label": label,
        "basis": "per_pax_km" if occ > 1.0 else "per_vkm",
        "occupancy": occ,
        "bs_class": dom, "bs_options": list(opts), "confidence": conf,
        "fuel": fuel, "class": vclass,
        "non_exhaust": {
            "pm10_g": _band(*acc_nx),
            "per_vkm_g": _band(*nx),
            "note": ("non-exhaust (resuspended dust + brakes/tyres), "
                     "reported separately — ~86% of Delhi traffic PM10 is "
                     "non-exhaust (Sahu et al. 2020, docs/26); never folded "
                     "into tailpipe numbers"),
        },
        "breakdown": {
            "moving_mid": {p: round(moving_mid[p], 5) for p in acc},
            "idle_mid": {p: round(idle_mid[p], 5) for p in acc},
            "cold_extra_mid": {p: round(cold_mid[p], 5) for p in acc},
            "units_g_except_co2_g": True,
        },
        "distance_km": round(tot_km, 3),
    }
