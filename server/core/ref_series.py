"""ALive-108 — tick-level dose/emission kernels, Python reference.

Parity oracle for the alive_core series kernels added on r5/core-cpp —
the per-tick math the strip contract hands to clients (docs/plan/04 §5):

    dose_ug  += C * ME(mode) * VE(mode) * dt        (exposure.dose inner loop)
    ef_g_km   = ef_band(vehicle) * speed_factor(v)  (emissions.integrate's
                                                    km_lo/km_mid/km_hi)

`alive_core_ref.py` (server level, another lane's file) covers the
route-level walk; this module covers the flat series forms. Semantics
are verbatim from the production modules — the only composition is the
loop itself:

  dose_series      — server/exposure.py::dose accumulation:
                     non-finite/None concentrations are skipped (the
                     'uncovered field' branch), c < 0 clamps to 0 (krige
                     can dip below 0; PM2.5 can't), c_eff = c*microenv,
                     dose += c_eff * (ve_lpm/1000) * (dt_s/60). Road
                     uplift is 1.0 here — callers fold it into `microenv`
                     when they want it (exposure.dose multiplies the same
                     product by uplift, and x*1.0 is bitwise x).
  emission_g_km    — server/emissions.py: emission_factors({"class": cls})
                     fleet-prior band at REF_SPEED_MPS x speed_factor(p, v)
                     with the speed-uncertainty widening
                     (lo*f/sw, mid*f, hi*f*sw, sw = 1+0.2|f-1|). Metro is
                     per-passenger-km and speed-independent, walk/cycle
                     are zero — mirroring integrate()'s early returns.

Signatures mirror the C++ bindings one-for-one:
  dose_series(pm25, dt_s, ventilation_lpm, microenv) -> float µg
  emission_g_km(mode, speed_kmh) -> dict {co2,pm25,nox:(lo,mid,hi),
                                          units, mode, occupancy?}

Server-side wiring status: both kernels are built and parity-verified
but deliberately unwired — the server has no tick-level consumer (live
dose/emission accumulation is client-side in Mobile/src/nav/
counters.ts) and /v2/strip's emission contract needs the declared
vehicle profile that emission_g_km's mode-only signature can't express
(see v2/strip.py::_emission_curve). They stay available for any future
server-side tick accumulator.
"""

from __future__ import annotations

import math
from typing import Optional, Sequence

# ---------------------------------------------------------------------------
# dose_series — exposure.dose's accumulation, flat series form
# ---------------------------------------------------------------------------


def dose_series(pm25: Sequence[Optional[float]], dt_s,
                ventilation_lpm: float, microenv: float) -> float:
    """Cumulative inhaled PM2.5 (µg) over a concentration series.

    pm25:             µg/m³ per tick; None or non-finite entries are
                      skipped (exposure's uncovered-field semantics).
    dt_s:             seconds per tick — scalar (uniform cadence) or a
                      per-sample sequence; zip() truncation on a length
                      mismatch, like Python's own zip. Entries that are
                      None/non-finite/negative skip their sample.
    ventilation_lpm:  minute ventilation, L/min (exposure.VE table value
                      — divided by 1000 like dose()'s `ve = ve_lpm/1000`).
    microenv:         microenvironment ratio (exposure.MICROENV value);
                      road uplift folds in here when wanted.

    Accumulation is a plain `+=` in input order — identical association
    to exposure.dose's `total_dose += c_eff * ve * t_min`, so results are
    bit-identical to the same products summed in Python.
    """
    try:
        dts = list(dt_s)          # sequence → per-sample dt
    except TypeError:
        dts = [dt_s] * len(pm25)  # scalar → uniform cadence
    ve = ventilation_lpm / 1000.0  # m³/min, exposure.py line order
    total = 0.0
    for c, dt in zip(pm25, dts):
        if c is None or not math.isfinite(c):
            continue
        if dt is None or not math.isfinite(dt) or dt < 0:
            continue
        if c < 0:
            c = 0.0
        c_eff = c * microenv
        total += c_eff * ve * (dt / 60.0)
    return total


# ---------------------------------------------------------------------------
# emission_g_km — (mode, speed_kmh) -> g/km band lookup
# ---------------------------------------------------------------------------
# Canonical emissions classes (emissions._EF_GROUP keys + metro/walk/
# cycle). Each resolves through emission_factors({"class": cls}) — the
# declared vehicle defaults (class-default fuel, year "not_sure" → the
# Delhi fleet prior), i.e. "vehicles like yours" per doc 06 §2.
EMISSION_CLASSES = ("car", "cab", "scooter", "bike", "auto", "bus",
                    "metro", "walk", "cycle")

# Mode aliases -> canonical class. Union of v2/plan.py's tables
# (_EMIT_CLASS/_PREVIEW_CLASS for route modes, _PROFILE_CLASS/
# _VEHICLE_ALIASES for declared vehicles — emissions-class mapping, so
# taxi keeps its cab uplift and scooter stays scooter) plus exposure.py's
# motorized microenv keys, so plan-mode and dose-mode strings both work.
EMISSION_MODE_ALIASES = {
    # plan route modes
    "car_open": "car",
    "metro+walk": "metro",
    # declared-vehicle strings (plan.py _VEHICLE_ALIASES/_PROFILE_CLASS)
    "car_ac": "car",
    "four_wheeler": "car",
    "taxi": "cab",
    "rickshaw": "auto",
    "autorickshaw": "auto",
    "auto_rickshaw": "auto",
    "two_wheeler": "bike",
    "twowheeler": "bike",
    "motorcycle": "bike",
    "moped": "bike",
    "driving_two_wheeler": "bike",
    "dtc": "bus",
    "train": "metro",
    "subway": "metro",
    "dmrc": "metro",
    "cycling": "cycle",
    "bicycle": "cycle",
    "bike_cycle": "cycle",
    "walking": "walk",
    "on_foot": "walk",
    "foot": "walk",
    # exposure.py microenv keys for motorized modes
    "driving_car_ac": "car",
    "driving_car_open": "car",
    "car_windows_up": "car",
    "car_windows_down": "car",
}


def emission_g_km(mode: str, speed_kmh: float) -> dict:
    """g/km band for a mode at a speed — ef_g_km(vehicle, v) of the
    strip contract (docs/plan/04 §5), resolved for the mode's default
    fleet-prior vehicle.

    Returns {"co2", "pm25", "nox": (lo, mid, hi), "units": "g/km" or
    "g/pkm", "mode": canonical class, "occupancy": float when the source
    factor set reports one}. Raises ValueError on an unknown mode —
    emission_factors' own "unknown vehicle class" error path.
    """
    import emissions  # local tables, stdlib-only (lazy like alive_core_ref)

    m = str(mode).lower().strip()
    cls = EMISSION_MODE_ALIASES.get(m, m)
    ef = emissions.emission_factors({"class": cls})
    per_pkm = ef.get("units") == "g/pkm"
    v_mps = speed_kmh / 3.6
    out = {"mode": cls, "units": ef.get("units", "g/km")}
    for pol in ("co2", "pm25", "nox"):
        b = ef[pol]
        lo, mid, hi = b["lo"], b["mid"], b["hi"]
        if per_pkm:
            out[pol] = (lo, mid, hi)      # metro: flat per-pax-km band
        else:
            f = emissions.speed_factor(pol, v_mps)
            sw = 1.0 + 0.2 * abs(f - 1.0)
            out[pol] = (lo * f / sw, mid * f, hi * f * sw)
    if ef.get("occupancy"):
        out["occupancy"] = ef["occupancy"]
    return out


def emission_mode_table() -> dict:
    """{canonical_mode: {"per_pkm": bool, "occupancy": float|0,
    "bands": {pol: (lo, mid, hi)}}} — the resolved factor set the C++
    table is generated from (tools/gen_ef_table.py emits exactly this,
    hexfloat-encoded, so the C++ constants are bit-identical).
    """
    import emissions

    table = {}
    for cls in EMISSION_CLASSES:
        ef = emissions.emission_factors({"class": cls})
        table[cls] = {
            "per_pkm": ef.get("units") == "g/pkm",
            "occupancy": ef.get("occupancy") or 0.0,
            "bands": {p: (ef[p]["lo"], ef[p]["mid"], ef[p]["hi"])
                      for p in ("co2", "pm25", "nox")},
        }
    return table
