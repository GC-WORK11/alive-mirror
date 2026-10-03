// ALive-108 — emission span integrator. Bit-identical semantics with
// server/alive_core_ref.integrate_emissions (see include/alive/emission.hpp).

#include "alive/emission.hpp"

#include <algorithm>
#include <cctype>
#include <cmath>
#include <cstring>

namespace alive {
namespace {

// Generated per-mode EF table (tools/gen_ef_table.py -> ef_table.inc):
// kEmModeTable — resolved band at kEmRefSpeedMps per canonical class,
// kEmAliasTable — mode alias -> canonical name.
#include "ef_table.inc"

// emissions._resolve's (vehicle.get("class") or "").lower().strip().
std::string normalize_mode(const std::string& mode) {
  size_t a = 0, b = mode.size();
  while (a < b && std::isspace((unsigned char)mode[a])) ++a;
  while (b > a && std::isspace((unsigned char)mode[b - 1])) --b;
  std::string m = mode.substr(a, b - a);
  for (char& ch : m) ch = (char)std::tolower((unsigned char)ch);
  return m;
}

const EmModeRow* mode_row(const std::string& m) {
  for (const EmModeRow& r : kEmModeTable)
    if (m == r.name) return &r;
  for (const EmAliasRow& a : kEmAliasTable)
    if (m == a.alias)
      for (const EmModeRow& r : kEmModeTable)
        if (std::strcmp(a.canonical, r.name) == 0) return &r;
  return nullptr;
}

// (L, H) per pollutant, indexed by Pol — ref _EM_SPEED_PARAMS.
constexpr double kSpeedL[kPolCount] = {1.2, 1.8, 0.9};
constexpr double kSpeedH[kPolCount] = {0.8, 1.2, 1.4};

// Python's x**2 is libm pow(), not always bit-identical to x*x — the
// volatile exponent blocks GCC's constant-folding of pow(x, 2.0) -> x*x.
inline double py_sq(double x) {
  volatile double two = 2.0;
  return std::pow(x, two);
}

double g_curve(int pol, double v_mps) {
  const double L = kSpeedL[pol];
  const double H = kSpeedH[pol];
  const double v = std::max(v_mps, kEmVFloorMps);
  if (v < kEmVOptMps) {
    return 1.0 +
           L * py_sq((kEmVOptMps - v) / kEmVOptMps) * (kEmVOptMps / v);
  }
  return 1.0 + H * py_sq((v - kEmVOptMps) / kEmVOptMps);
}

double g_ref(int pol) { return g_curve(pol, kEmRefSpeedMps); }

// Mean of 1+(C-1)(1 - x/COLD_KM) over the cold overlap — closed form.
double cold_avg_mult(double c, double d_start, double cold_len_km) {
  const double x_avg = d_start + cold_len_km / 2.0;
  return 1.0 + (c - 1.0) * (1.0 - x_avg / kEmColdKm);
}

}  // namespace

double emission_speed_factor(int pol, double v_mps) {
  return g_curve(pol, v_mps) / g_ref(pol);
}

EmissionResult integrate_emissions(
    const std::vector<EmSpan>& spans, const std::array<Band3, 3>& ef_band,
    const std::array<Band3, 3>& idle_band,
    const std::array<double, 3>& cold_mult, const Band3& nx_band,
    double cold_km_done, double occupancy) {
  EmissionResult r;
  double acc[3][3] = {{0, 0, 0}, {0, 0, 0}, {0, 0, 0}};
  double acc_nx[3] = {0, 0, 0};
  double d = std::max(0.0, cold_km_done);
  double tot_km = 0.0;

  for (const EmSpan& s : spans) {
    const double dist_m = s.dist_m;
    const double v = s.speed_mps;
    if (s.moving && dist_m > 0.0) {
      const double km = dist_m / 1000.0;
      tot_km += km;
      const double cold_len =
          d < kEmColdKm ? std::min(d + km, kEmColdKm) - d : 0.0;
      const double warm_len = km - std::max(0.0, cold_len);
      for (int p = 0; p < 3; ++p) {
        const double f = emission_speed_factor(p, v);
        const double sw = 1.0 + 0.2 * std::abs(f - 1.0);
        const Band3& b = ef_band[p];
        const double km_lo = b.lo * f / sw;
        const double km_mid = b.mid * f;
        const double km_hi = b.hi * f * sw;
        if (cold_len > 0.0) {
          const double c = cold_mult[p];
          const double ml = cold_avg_mult(1.0 + (c - 1.0) * 0.7, d, cold_len);
          const double mm = cold_avg_mult(c, d, cold_len);
          const double mh = cold_avg_mult(1.0 + (c - 1.0) * 1.3, d, cold_len);
          acc[p][0] += km_lo * (cold_len * ml + warm_len);
          acc[p][1] += km_mid * (cold_len * mm + warm_len);
          acc[p][2] += km_hi * (cold_len * mh + warm_len);
          r.cold_extra_mid[p] += km_mid * cold_len * (mm - 1.0);
        } else {
          acc[p][0] += km_lo * km;
          acc[p][1] += km_mid * km;
          acc[p][2] += km_hi * km;
        }
        r.moving_mid[p] += km_mid * km;
      }
      const double nx[3] = {nx_band.lo, nx_band.mid, nx_band.hi};
      for (int i = 0; i < 3; ++i) acc_nx[i] += nx[i] * km;
      d += km;
    } else {
      double dur;
      if (s.has_dur) {
        dur = s.dur_s;
      } else {
        dur = v > 0.3 ? dist_m / v : 0.0;
      }
      dur = std::max(0.0, dur);
      for (int p = 0; p < 3; ++p) {
        const double idle[3] = {idle_band[p].lo, idle_band[p].mid,
                                idle_band[p].hi};
        for (int i = 0; i < 3; ++i) acc[p][i] += idle[i] * dur;
        r.idle_mid[p] += idle[1] * dur;
      }
    }
  }

  if (occupancy > 1.0) {
    for (int p = 0; p < 3; ++p) {
      for (int i = 0; i < 3; ++i) acc[p][i] /= occupancy;
      r.idle_mid[p] /= occupancy;
      r.moving_mid[p] /= occupancy;
      r.cold_extra_mid[p] /= occupancy;
    }
    for (int i = 0; i < 3; ++i) acc_nx[i] /= occupancy;
  }

  for (int p = 0; p < 3; ++p)
    r.pol[p] = Band3{acc[p][0], acc[p][1], acc[p][2]};
  r.nx_pm10 = Band3{acc_nx[0], acc_nx[1], acc_nx[2]};
  r.distance_km = tot_km;
  return r;
}

// ---------------------------------------------------------------------------
// emission_g_km — (mode, speed_kmh) -> g/km band (see emission.hpp).
// ---------------------------------------------------------------------------
bool emission_g_km(const std::string& mode, double speed_kmh,
                   EmCurveResult& out) {
  const EmModeRow* row = mode_row(normalize_mode(mode));
  if (row == nullptr) return false;
  out.mode = row->name;
  out.per_pkm = row->per_pkm;
  out.occupancy = row->occupancy;
  const double v_mps = speed_kmh / 3.6;
  for (int p = 0; p < kPolCount; ++p) {
    const Band3& b = row->band[p];
    if (row->per_pkm) {
      out.pol[p] = b;  // metro: per-passenger-km, speed-independent
      continue;
    }
    const double f = emission_speed_factor(p, v_mps);
    const double sw = 1.0 + 0.2 * std::abs(f - 1.0);
    out.pol[p] = Band3{b.lo * f / sw, b.mid * f, b.hi * f * sw};
  }
  return true;
}

}  // namespace alive
