// Alive — field view + dose integrator (alive_core, Phase 3).
//
// Semantics kept bit-identical with server/alive_core_ref.py (the parity
// oracle — see its "Phase 3" block for the contract spec):
//
//   FieldView serves an airindex snapshot (schema alive-airindex/1) as a
//   nearest-cell view: value(lat,lon) is the pm25 of the nearest cell
//   center measured with airindex's flat-earth metric
//       km = hypot(dlat * 110.6, dlon * 99.4)
//   and only when that center is within coverage_km (default 1.0). No
//   interpolation — cells are already the kriged product. Ties break on
//   the smaller (lat, lon).
//
//   segment_samples / integrate_dose mirror exposure.py exactly:
//   haversine R=6371000 m on (lon,lat) pairs, ~step_m carry sampling,
//   seconds apportioned by segment length and renormalized to duration_s,
//   dose_ug = sum C*ME*VE*dt_min with lo/hi = conservative sums of the
//   per-cell band (docs/plan/06 section 1).
//
// Spatial index: uniform bins of 0.01 degrees; queries scan expanding
// Chebyshev rings until the ring's minimum possible distance exceeds the
// running best (initialized to coverage_km).

#pragma once

#include <array>
#include <cmath>
#include <cstdint>
#include <optional>
#include <unordered_map>
#include <utility>
#include <vector>

namespace alive {

constexpr double kFieldCoverageKm = 1.0;
constexpr double kFieldBinDeg = 0.01;
constexpr double kKmPerDegLat = 110.6;  // airindex._km scales
constexpr double kKmPerDegLon = 99.4;

// One field cell: center + pm2.5 band + krige sigma (airindex schema).
struct FieldCell {
  double lat = 0.0;
  double lon = 0.0;
  double pm25 = 0.0;
  double lo = 0.0;
  double hi = 0.0;
  double sigma = 0.0;
};

// airindex._km — flat-earth km between two (lat, lon) points.
inline double cell_km(double lat1, double lon1, double lat2, double lon2) {
  const double dy = (lat2 - lat1) * kKmPerDegLat;
  const double dx = (lon2 - lon1) * kKmPerDegLon;
  return std::hypot(dx, dy);
}

class FieldView {
 public:
  explicit FieldView(std::vector<FieldCell> cells,
                     double coverage_km = kFieldCoverageKm);

  // Index into cells() of the nearest center within coverage_km, else -1.
  long nearest(double lat, double lon) const;

  std::optional<double> value(double lat, double lon) const;
  std::optional<double> sigma(double lat, double lon) const;
  // (lo, pm25, hi) of the nearest cell.
  std::optional<std::array<double, 3>> band(double lat, double lon) const;

  size_t size() const { return cells_.size(); }
  const FieldCell& cell(size_t i) const { return cells_[i]; }
  double coverage_km() const { return coverage_km_; }

 private:
  std::vector<FieldCell> cells_;
  double coverage_km_;
  std::unordered_map<uint64_t, std::vector<uint32_t>> bins_;  // bin -> cells
};

struct SegSample {
  double lat = 0.0;
  double lon = 0.0;
  double seconds = 0.0;
  double dist_m = 0.0;
};

// exposure.segment_samples port; coords are (lon, lat) pairs.
std::vector<SegSample> segment_samples(
    const std::vector<std::pair<double, double>>& coords, double duration_s,
    double step_m = 250.0);

struct DoseResult {
  std::optional<double> lo;
  std::optional<double> mid;
  std::optional<double> hi;
  double coverage = 0.0;
  long n_samples = 0;
  long n_hit = 0;
  double dist_km = 0.0;
};

// dose_ug = sum over samples C*me*ve*dt_min; band = conservative cell
// lo/hi sums. me = microenvironment ratio, ve = m3/min.
DoseResult integrate_dose(
    const std::vector<std::pair<double, double>>& coords,
    const FieldView& field, double me, double ve, double duration_s,
    double step_m = 250.0);

// exposure.dose's accumulation loop in flat series form (the strip/tick
// contract, docs/plan/04 §5): dose_ug = sum over entries
//   c_eff * ve * (dt_s/60),  c_eff = c * microenv,  ve = ve_lpm/1000.
// Non-finite entries are skipped (exposure's 'uncovered field' branch;
// NaN is the C++-side missing marker), c < 0 clamps to 0 (krige can dip
// below 0; PM2.5 can't), dt < 0 or non-finite skips the sample. Road
// uplift folds into `microenv` (x*1.0 is bitwise x). Zip semantics on a
// length mismatch: iteration stops at the shorter series. Accumulation
// is a plain `+=` in input order — bit-identical to the Python loop.
double dose_series(const std::vector<double>& pm25,
                   const std::vector<double>& dt_s,
                   double ventilation_lpm, double microenv);

// Uniform-cadence convenience: one dt for every sample.
inline double dose_series(const std::vector<double>& pm25, double dt_s,
                          double ventilation_lpm, double microenv) {
  return dose_series(pm25, std::vector<double>(pm25.size(), dt_s),
                     ventilation_lpm, microenv);
}

}  // namespace alive
