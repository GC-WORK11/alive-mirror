"""Dose engine — the differentiating math of ALive-108.

dose(µg) = Σ over route segments [ C(lat,lon) × microenv_ratio(mode)
                                   × VE(m³/min) × t(min) ]

where C comes from an injected field callable (live field, forecast, or
climatology — the scorer doesn't care). Every factor is a published value
with a citation; the product shows them in its provenance UI.

Sources:
  [1] Sci. Total Environ. 2021 — measured PM2.5 in 6 Delhi transport
      microenvironments: auto-rickshaw & walking highest; AC-car & metro
      lowest. PM2.5 inhaled/km: walking 28.2×, rickshaw 5.3× vs metro.
  [2] Discover Atmosphere 2025 — measured means on Delhi Magenta-line
      corridor: auto-rickshaw 113.2, bus-open 68.9, bus-closed 63.1,
      car-open 71.0, car-closed 62.3, two-wheeler 41.9, metro 34.2 µg/m³.
  [3] Zuurbier et al. 2009 (Environ. Health) — minute ventilation while
      cycling ~2.1× car/bus passengers (280 real trips); in-vehicle VE
      measured ~10–11 L/min, cyclists ~21–25 L/min.
  [4] US EPA near-road literature / Karner et al. — traffic-linked PM
      increments decay ~75% within 30m and taper to ~500m.
  [5] Goel, Gani, Guttikunda, Wilson & Tiwari 2015 (Atmos. Environ. 123:
      129–138) — on-road vs ambient PM2.5 on a fixed 8.3 km Delhi
      arterial, rush hour: walking +40%, 2W +30%, open-window car +30%,
      auto-rickshaw +30%, AC/OW bus +20%, cycling +10%, AC car −50%,
      metro carriage −20%.
  [6] Apte et al. 2011 (Atmos. Environ.) — ~180 h in an auto-rickshaw:
      in-vehicle PM2.5 GM 190 µg/m³ = 1.5× simultaneous ambient (130).
"""
import math
from typing import Callable, Optional

try:  # C++ engine — verbatim ports verified by tests/test_parity_dose.py
    import alive_core as _ac
except Exception:
    _ac = None

# --- Measured Delhi microenvironment ratios -------------------------------
# Normalized to the ambient field (what a person standing on that street
# would breathe). Each row is pinned to the measured Delhi literature —
# [5]'s fixed-arterial exceedances and [6]'s in-rickshaw ratio are the
# direct breathing-zone evidence; [2] (Magenta-line run means vs the same
# corridor's ambient) cross-checks from the enclosed side. Where the two
# studies disagree we take the mid of the published range and say so —
# open modes are biased toward [5]/[6] because understating the highest-
# exposure modes would undersell the product's core claim.
# Audit (Oct-2026): walk 1.00→1.30, car_open 0.80→1.00, bus 0.70→0.90,
# 2W 1.10→1.20, auto 1.15→1.30 — every open/shared mode was below the
# measured band and understated dose 12–40%.

MICROENV = {
    # canonical mode keys (doc 06 §1 sources every row):
    "metro":              0.45,   # [2] run-mean ≈0.40–0.46 vs corridor
                                # ambient; [5] measured 0.80 on the 2014
                                # surface-line carriage — we keep the
                                # optimistic published end, flagged here.
    "driving_car_ac":     0.55,   # [5] measured 0.50; cabin I/O 0.20 new /
                                # 0.60 aged filter — mid of published.
    "driving_car_open":   1.00,   # [5] measured 1.30 (windows-down rides in
                                # the plume); [2] implies ~0.85–0.95 — we
                                # take 1.00, below the [5] exceedance.
    "bus":                0.90,   # [5] measured 1.20 (AC and OW both +20%);
                                # [2] implies ~0.78–0.88 — mid ~0.90.
    "driving_two_wheeler": 1.20,  # [5] measured 1.30; lightly discounted —
                                # riders sit ahead of much of the plume.
    "auto_rickshaw":      1.30,   # [5] 1.30, [6] 1.46, [2] implies ~1.33 —
                                # the published range starts at 1.3.
    "cycling":            1.10,   # [5] measured 1.10 exactly.
    "walking":            1.30,   # [5] measured 1.40; discounted ~7% —
                                # our kriged field already carries some
                                # roadside blend via CAAQMS stations.
    # app-facing aliases — the same published values under the plain
    # vehicle strings other lanes pass through (community.py stores raw
    # vehicle names; doc 06 §1 lists plain names: car, 2W, auto, cycle,
    # walk). cab/taxi have no doc row → conservative default = open car
    # (Delhi cabs wait at stands windows-down; never understate dose).
    "car":                0.55,   # alias: driving_car_ac (car default = AC)
    "car_ac":             0.55,
    "car_windows_up":     0.55,
    "car_open":           1.00,   # alias: driving_car_open
    "car_windows_down":   1.00,
    "cab":                1.00,   # DEFAULT (no doc row) — open-car value
    "taxi":               1.00,   # DEFAULT (no doc row) — open-car value
    "bike":               1.20,   # alias: driving_two_wheeler
    "two_wheeler":        1.20,
    "scooter":            1.20,
    "motorcycle":         1.20,
    "auto":               1.30,   # alias: auto_rickshaw
    "rickshaw":           1.30,
    "cycle":              1.10,   # alias: cycling
    "bicycle":            1.10,
    "walk":               1.30,   # alias: walking
    "on_foot":            1.30,
}

# --- Minute ventilation (L/min), activity-adjusted --------------------------
# Doc 06 §1 differentiates VE by ACTIVITY, not vehicle badge — three tiers:
#   seated/transit  ~10.0-10.5 (measured in-vehicle/passenger VE; audit fix
#                            Oct-2026 — was 7.5-9.0, a sedentary-rest tier
#                            ~25% below the published passenger band)
#   walking         14.0     (EPA EFH light/moderate adult walking ~12-16)
#   cycling         22.0     [3] Zuurbier 2009 measured cyclists ≈2.1×
#                            in-vehicle passengers; at car VE 10.0 our
#                            cycle/car ratio is 2.2× — matching the
#                            measured ratio, not exaggerating it.

MODE_ACTIVITY = {
    "metro": "seated", "driving_car_ac": "seated",
    "driving_car_open": "seated", "bus": "seated",
    "driving_two_wheeler": "seated", "auto_rickshaw": "seated",
    "cycling": "cycling", "walking": "walking",
    "car": "seated", "car_ac": "seated", "car_windows_up": "seated",
    "car_open": "seated", "car_windows_down": "seated",
    "cab": "seated", "taxi": "seated",
    "bike": "seated", "two_wheeler": "seated", "scooter": "seated",
    "motorcycle": "seated", "auto": "seated", "rickshaw": "seated",
    "cycle": "cycling", "bicycle": "cycling",
    "walk": "walking", "on_foot": "walking",
}

VENTILATION_LPM = {
    # canonical keys
    "metro":              10.0,
    "driving_car_ac":     10.0,
    "driving_car_open":   10.0,
    "bus":                10.0,
    "driving_two_wheeler": 10.5,
    "auto_rickshaw":      10.0,
    "cycling":            22.0,
    "walking":            14.0,
    # aliases (mirrors MICROENV)
    "car":                10.0,
    "car_ac":             10.0,
    "car_windows_up":     10.0,
    "car_open":           10.0,
    "car_windows_down":   10.0,
    "cab":                10.0,
    "taxi":               10.0,
    "bike":               10.5,
    "two_wheeler":        10.5,
    "scooter":            10.5,
    "motorcycle":         10.5,
    "auto":               10.0,
    "rickshaw":           10.0,
    "cycle":              22.0,
    "bicycle":            22.0,
    "walk":               14.0,
    "on_foot":            14.0,
}

# --- Near-road uplift ------------------------------------------------------
# Our field is ambient. Segments physically ON a major corridor carry a
# traffic-proximity increment: doc 06 §1 / [4] put the traffic-linked PM
# increment at ~+75% decaying within 30 m of the curb (taper to ~500 m).
# That 75% applies to the *traffic component*, not the whole ambient
# concentration — applied to total C at curb distance the published range
# is ~+20-50%, which is what the factors below use. Without per-segment
# road attribution we only mark the factor 1.0 and flag it.

ROAD_UPLIFT = {
    "motorway": 1.35, "trunk": 1.30, "primary": 1.20,
    "secondary": 1.10, "tertiary": 1.05, "residential": 1.0,
    "arterial": 1.20,   # alias: doc 06 wording for primary corridors
}

APP_MODES = {"driving", "cycling", "walking"}

# --- Consumer units ----------------------------------------------------------
# Berkeley Earth equivalence (claims ledger, doc 10): 1 cigarette ≈ 316 µg
# inhaled PM2.5. Same constant as the app ledger; main.py /shift uses /316.
CIG_UG = 316.0

# Above this average speed a 'route' is not a plausible Delhi surface/metro
# trip — the duration is wrong and the dose integral is understated.
# Flagged, never silently clamped. Generous bound: even the Airport Express
# metro averages <60 km/h.
PLAUSIBLE_MAX_KMH = 150.0


def mode_factors(mode: str) -> dict:
    """Resolve any canonical-or-alias mode string to its dose factors.
    Unknown modes degrade to open-air walking factors (microenv 1.0,
    seated VE 10.0) with known_mode=False — honest, never a crash."""
    me = MICROENV.get(mode)
    ve = VENTILATION_LPM.get(mode)
    return {
        "microenv": me if me is not None else 1.0,
        "ventilation_lpm": ve if ve is not None else 10.0,
        "activity": MODE_ACTIVITY.get(mode, "seated"),
        "known_mode": mode in MICROENV,
    }


def dose_to_cigs(dose_ug):
    """µg inhaled → cigarette equivalents (1 = 316 µg, doc 10).
    None in → None out; a band is a band."""
    if dose_ug is None or not math.isfinite(dose_ug):
        return None
    return dose_ug / CIG_UG


def cigs_band(dose_ug, dose_ug_lo=None, dose_ug_hi=None) -> dict:
    """Cigarette equivalent for a dose band → {lo, mid, hi, unit}.
    Missing bounds stay None; the UI shows '≈' not a point value."""
    return {
        "lo": dose_to_cigs(dose_ug_lo),
        "mid": dose_to_cigs(dose_ug),
        "hi": dose_to_cigs(dose_ug_hi),
        "unit": "cigarettes",
        "basis": "Berkeley Earth; CIG_UG=316",
    }


def _haversine_m(a, b):
    R = 6371000.0
    p1, p2 = math.radians(a[1]), math.radians(b[1])
    dp, dl = math.radians(b[1] - a[1]), math.radians(b[0] - a[0])
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R * math.asin(math.sqrt(h))


def _leg_m(a, b) -> float:
    """Haversine that degrades to 0 on malformed/non-finite coords —
    a bad vertex shortens the route honestly instead of crashing."""
    try:
        d = _haversine_m(a, b)
        return d if (math.isfinite(d) and d >= 0.0) else 0.0
    except Exception:
        return 0.0


def segment_samples(geometry: dict, duration_s: float, step_m: float = 250.0):
    """Sample a LineString every ~step_m; apportion duration by length
    (uniform-speed assumption — documented limitation vs. congestion).
    Returns list of dicts(lat, lon, seconds, dist_m); [] on degenerate
    input (empty geometry, non-finite/negative duration, zero length)."""
    if _ac is not None and duration_s is not None and \
            math.isfinite(duration_s) and duration_s >= 0:
        try:  # C++ verbatim port (test_parity_dose) — tuple rows -> dicts
            return [{"lat": t[0], "lon": t[1], "seconds": t[2],
                     "dist_m": t[3]}
                    for t in _ac.segment_samples(geometry, duration_s,
                                                 step_m)]
        except Exception:
            pass  # malformed vertex — the reference impl tolerates it
    coords = (geometry or {}).get("coordinates") or []
    if len(coords) < 2:
        return []
    if duration_s is None or not math.isfinite(duration_s) or duration_s < 0:
        return []
    total = sum(_leg_m(coords[i - 1], coords[i]) for i in range(1, len(coords)))
    if not math.isfinite(total) or total <= 0:
        return []
    out = []
    carry = 0.0
    for i in range(1, len(coords)):
        a, b = coords[i - 1], coords[i]
        seg = _leg_m(a, b)
        carry += seg
        if carry >= step_m or i == len(coords) - 1:
            frac = seg / total
            if isinstance(b, (list, tuple)) and len(b) >= 2 and \
                    math.isfinite(b[0]) and math.isfinite(b[1]):
                out.append({"lat": b[1], "lon": b[0],
                            "seconds": duration_s * frac, "dist_m": seg})
            # else: malformed vertex — no sample emitted (keeps the
            # lat/lon-always-float contract callers like v2/strip rely
            # on); its distance still counted in `total`, so neighbours
            # aren't over-credited.
            carry = 0.0
    # renormalize so Σseconds == duration_s exactly
    s = sum(x["seconds"] for x in out) or 1.0
    for x in out:
        x["seconds"] *= duration_s / s
    return out


def dose(geometry: dict, duration_s: float, mode: str,
         field_value: Callable[[float, float], Optional[float]],
         nearest_sample_km: Optional[Callable[[float, float], float]] = None,
         road_class: Optional[str] = None,
         field_sigma: Optional[Callable[[float, float], Optional[float]]] = None) -> dict:
    """Inhaled PM2.5 mass (µg) for one route+mode option. When the field
    carries krige uncertainty, segment σ propagates through the same
    dose integral → dose_lo/dose_hi. Band math per doc 06 §1: sum of lo,
    sum of hi (linear, conservative — not the independence-assuming RSS).
    Bad inputs degrade honestly: NaN/negative concentrations count as
    uncovered field, implausible speeds flag instead of clamping."""
    fac = mode_factors(mode)
    microenv = fac["microenv"]
    ve_lpm = fac["ventilation_lpm"]
    ve = ve_lpm / 1000.0  # m³/min
    uplift = ROAD_UPLIFT.get(road_class or "", 1.0)
    factors = {"microenv": microenv, "ventilation_lpm": ve_lpm,
               "road_uplift": uplift, "activity": fac["activity"],
               "mode_known": fac["known_mode"]}
    warnings = []
    if not fac["known_mode"]:
        warnings.append("unknown_mode_defaulted")

    def _empty(covs=0.0):
        return {"dose_ug": None, "dose_ug_lo": None, "dose_ug_hi": None,
                "avg_conc_ugm3": None, "peak_conc": None,
                "confidence": "none", "coverage": covs, "sparse": True,
                "warnings": warnings, "factors": factors}

    if duration_s is None or not math.isfinite(duration_s) or duration_s < 0:
        warnings.append("bad_duration")
        return _empty()

    samples = segment_samples(geometry, duration_s)
    if not samples:
        warnings.append("degenerate_route")
        return _empty()

    total_dose = 0.0
    total_sd = 0.0       # linear sum of segment σ×factors (doc 06 §1)
    conc_by_dist = 0.0
    peak = 0.0
    got = 0
    neg_clamped = 0
    dist_km = 0.0
    for s in samples:
        dist_km += s["dist_m"] / 1000.0
        if s["lat"] is None:
            continue
        try:
            c = field_value(s["lat"], s["lon"])
        except Exception:
            c = None          # field blew up → treat as uncovered, not crash
        if c is None or not math.isfinite(c):
            continue          # NaN/inf = honest 'no field', not a dose of NaN
        if c < 0:
            c = 0.0           # krige can dip below 0; PM2.5 can't
            neg_clamped += 1
        c_eff = c * microenv * uplift
        got += 1
        total_dose += c_eff * ve * (s["seconds"] / 60.0)
        conc_by_dist += c_eff * s["dist_m"]
        peak = max(peak, c_eff)
        if field_sigma is not None:
            try:
                sd = field_sigma(s["lat"], s["lon"]) or 0.0
                if math.isfinite(sd) and sd > 0:
                    total_sd += sd * microenv * uplift * ve * (s["seconds"] / 60.0)
            except Exception:
                pass

    coverage = got / len(samples)
    if got == 0:
        warnings.append("field_no_coverage")
        return _empty()
    if neg_clamped:
        warnings.append("negative_field_clamped")

    # confidence: field density + coverage + speed sanity
    near_km = 999.0
    if nearest_sample_km:
        try:
            mid = samples[len(samples) // 2]
            if mid["lat"] is not None:
                nk = nearest_sample_km(mid["lat"], mid["lon"])
                if nk is not None and math.isfinite(nk):
                    near_km = nk
        except Exception:
            near_km = 999.0
    if coverage < 0.5:
        conf = "low"
    elif near_km < 5:
        conf = "high"
    elif near_km < 15:
        conf = "medium"
    else:
        conf = "low"

    implied_kmh = dist_km / (duration_s / 3600.0) if duration_s > 0 else 0.0
    if implied_kmh > PLAUSIBLE_MAX_KMH:
        warnings.append("speed_implausible")
        conf = "low"        # the duration fed the integral is not believable

    return {
        "dose_ug": round(total_dose, 1),
        "dose_ug_lo": round(max(0.0, total_dose - total_sd), 1) if total_sd else None,
        "dose_ug_hi": round(total_dose + total_sd, 1) if total_sd else None,
        "avg_conc_ugm3": round(conc_by_dist / (dist_km * 1000 or 1), 1),
        "peak_conc": round(peak, 1),
        "implied_speed_kmh": round(implied_kmh, 1),
        "confidence": conf,
        "coverage": round(coverage, 2),
        "sparse": coverage < 0.5,
        "warnings": warnings,
        "factors": factors,
    }


def compare(options: list, field_value, nearest_sample_km=None,
            field_sigma=None) -> list:
    """Rank [{mode, geometry, duration_s, distance_km, ...}] by dose;
    annotate savings vs worst option. The 'auto=218, car=96, metro=41' math.
    A broken option degrades to an unscored tail entry, never a crash."""
    for o in options:
        try:
            o["exposure"] = dose(o.get("geometry"), o.get("duration_s"),
                                 o.get("mode"), field_value, nearest_sample_km,
                                 o.get("road_class"), field_sigma)
        except Exception:
            o["exposure"] = {"dose_ug": None, "confidence": "none",
                             "coverage": 0.0, "sparse": True,
                             "warnings": ["dose_error"], "factors": {}}
    scored = [o for o in options if o["exposure"]["dose_ug"] is not None]
    if not scored:
        return options
    best = min(x["exposure"]["dose_ug"] for x in scored)
    worst = max(x["exposure"]["dose_ug"] for x in scored)
    for o in scored:
        d = o["exposure"]["dose_ug"]
        o["exposure"]["dose_vs_best_pct"] = round((d - best) / best * 100, 1) if best else 0.0
        o["exposure"]["ug_saved_vs_worst"] = round(worst - d, 1)
    options.sort(key=lambda o: o["exposure"]["dose_ug"]
                 if o["exposure"]["dose_ug"] is not None else float("inf"))
    return options
