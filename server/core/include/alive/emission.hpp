// Alive — emission span integrator (alive_core, Phase 3).
//
// Bit-identical port of the span walk in server/emissions.py::integrate
// (the Python contract is alive_core_ref.integrate_emissions):
//
//   moving spans   accrue ef_band[p] * speed_factor(p, v) per km, with the
//                  COPERT U-curve normalised to 1.0 at 30/3.6 m/s and a
//                  speed-curve uncertainty widening (sw = 1+0.2|f-1|)
//   idle spans     accrue idle_band[p] g/s over dur_s (or dist_m/v when
//                  v > 0.3 m/s and no dur_s)
//   cold start     multiplier decaying linearly to 1.0 at 4 km, applied
//                  at 0.7 strength to lo and 1.3 to hi
//   non-exhaust    PM10 g/vkm accumulated separately, never folded in
//   occupancy      divides everything for shared modes
//
// Vehicle resolution (declared class/fuel/year -> BS bucket -> EF band)
// stays in emissions.py — this kernel takes the RESOLVED bands.

#pragma once

#include <array>
#include <string>
#include <vector>

namespace alive {

// Pollutant indexes — order matches ref's ("co2", "pm25", "nox").
enum Pol : int { kCO2 = 0, kPM25 = 1, kNOx = 2, kPolCount = 3 };

struct Band3 {
  double lo = 0.0;
  double mid = 0.0;
  double hi = 0.0;
};

struct EmSpan {
  double dist_m = 0.0;
  double speed_mps = 0.0;
  bool moving = true;
  double dur_s = 0.0;
  bool has_dur = false;
};

struct EmissionResult {
  Band3 pol[3];        // co2_g, pm25_g, nox_g
  Band3 nx_pm10;       // non-exhaust PM10 g, separate band
  double distance_km = 0.0;
  double moving_mid[3] = {0, 0, 0};      // mid g accrued while moving
  double idle_mid[3] = {0, 0, 0};        // mid g accrued at idle
  double cold_extra_mid[3] = {0, 0, 0};  // mid g of cold-start surplus
};

constexpr double kEmRefSpeedMps = 30.0 / 3.6;
constexpr double kEmVOptMps = 50.0 / 3.6;
constexpr double kEmVFloorMps = 2.5;
constexpr double kEmColdKm = 4.0;

// ef(v)/ef(v_ref) — COPERT U-curve, 1.0 at kEmRefSpeedMps.
double emission_speed_factor(int pol, double v_mps);

EmissionResult integrate_emissions(
    const std::vector<EmSpan>& spans, const std::array<Band3, 3>& ef_band,
    const std::array<Band3, 3>& idle_band,
    const std::array<double, 3>& cold_mult, const Band3& nx_band,
    double cold_km_done = 0.0, double occupancy = 1.0);

// ---------------------------------------------------------------------------
// Emission-curve lookup — ef_g_km(vehicle, v) of the strip contract
// (docs/plan/04 §5): a mode's resolved fleet-prior band at kEmRefSpeedMps
// evaluated at speed_kmh through the same curve + spread-widening
// integrate() applies per span:
//   f = ef(v)/ef(v_ref),  sw = 1 + 0.2|f-1|,
//   (lo*f/sw, mid*f, hi*f*sw)      v = max(kmh/3.6, kEmVFloorMps)
// Per-pkm modes (metro) are speed-independent; non-motorized modes carry
// zero bands — mirroring emission_factors()/integrate()'s early returns.
// The mode table itself is generated from emissions.py at configure time
// (tools/gen_ef_table.py -> ef_table.inc) so it cannot drift.
// ---------------------------------------------------------------------------

struct EmModeRow {
  const char* name;             // canonical emissions class
  bool per_pkm;                 // metro: band is per passenger-km
  double occupancy;             // shared-mode pax (0 when not reported)
  Band3 band[kPolCount];        // resolved band at kEmRefSpeedMps
};

struct EmAliasRow {
  const char* alias;            // plan/exposure/declared-vehicle string
  const char* canonical;        // -> EmModeRow.name
};

struct EmCurveResult {
  const char* mode = nullptr;   // canonical class that answered
  bool per_pkm = false;
  double occupancy = 0.0;       // 0 -> factor set reports none
  Band3 pol[kPolCount] = {};    // g/km (or g/pkm) at the query speed
};

// (mode, speed_kmh) -> banded g/km. mode is lower-cased + trimmed like
// emissions._resolve's `.lower().strip()`; aliases resolve first.
// false -> unknown mode (Python raises ValueError there).
bool emission_g_km(const std::string& mode, double speed_kmh,
                   EmCurveResult& out);

}  // namespace alive
