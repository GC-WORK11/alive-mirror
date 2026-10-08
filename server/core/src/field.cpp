// ALive-108 — field view + dose integrator. Bit-identical semantics with
// server/alive_core_ref.py (see include/alive/field.hpp for the spec).

#include "alive/field.hpp"

#include <algorithm>
#include <cmath>
#include <cstdlib>

namespace alive {
namespace {

inline long bin_of(double deg) { return (long)std::floor(deg / kFieldBinDeg); }

inline uint64_t bin_key(long bi, long bj) {
  return ((uint64_t)(uint32_t)bi << 32) | (uint32_t)bj;
}

// Python's float ** 2 goes through libm pow(), which differs from x*x in
// the last ulp for some inputs. Keep the exponent non-constexpr so GCC
// cannot fold pow(x, 2.0) back into a multiplication.
inline double py_sq(double x) {
  volatile double two = 2.0;
  return std::pow(x, two);
}

// CPython 3.12's sum() over floats uses Neumaier compensated summation —
// replicated here so totals are bit-identical to exposure.py / the ref.
struct CSum {
  double hi = 0.0;
  double lo = 0.0;
  void add(double x) {
    const double t = hi + x;
    if (std::fabs(hi) >= std::fabs(x))
      lo += (hi - t) + x;
    else
      lo += (x - t) + hi;
    hi = t;
  }
  double total() const { return hi + lo; }
};

// exposure._haversine_m verbatim — a,b are (lon, lat) pairs.
inline double haversine_m(const std::pair<double, double>& a,
                          const std::pair<double, double>& b) {
  constexpr double R = 6371000.0;
  const double p1 = a.second * 0.017453292519943295;
  const double p2 = b.second * 0.017453292519943295;
  const double dp = (b.second - a.second) * 0.017453292519943295;
  const double dl = (b.first - a.first) * 0.017453292519943295;
  // mirror exposure's grouping: sin(dp/2)**2 + cos(p1)*cos(p2)*sin(dl/2)**2.
  // Python's x**2 calls libm pow(), which is NOT always bit-identical to
  // x*x on this platform — py_sq() forces a real pow() call (a literal 2.0
  // would be constant-folded back to x*x by GCC).
  const double sdp = std::sin(dp / 2);
  const double sdl = std::sin(dl / 2);
  const double h = py_sq(sdp) + std::cos(p1) * std::cos(p2) * py_sq(sdl);
  return 2 * R * std::asin(std::sqrt(h));
}

}  // namespace

// ---------------------------------------------------------------------------
// FieldView — nearest-cell view over an airindex snapshot.
// ---------------------------------------------------------------------------
FieldView::FieldView(std::vector<FieldCell> cells, double coverage_km)
    : cells_(std::move(cells)), coverage_km_(coverage_km) {
  for (uint32_t i = 0; i < cells_.size(); ++i)
    bins_[bin_key(bin_of(cells_[i].lat), bin_of(cells_[i].lon))].push_back(i);
}

long FieldView::nearest(double lat, double lon) const {
  if (cells_.empty()) return -1;
  const long bi = bin_of(lat);
  const long bj = bin_of(lon);
  double best = coverage_km_;
  long best_i = -1;
  double best_lat = 0.0, best_lon = 0.0;
  // ring-r bins hold cells no closer than (r-1)*bin degrees on the worst
  // axis; kKmPerDegLon < kKmPerDegLat is the conservative scale.
  for (long r = 0; (r - 1) * kFieldBinDeg * kKmPerDegLon <= best; ++r) {
    for (long di = -r; di <= r; ++di) {
      for (long dj = -r; dj <= r; ++dj) {
        if (std::max(std::labs(di), std::labs(dj)) != r) continue;
        auto it = bins_.find(bin_key(bi + di, bj + dj));
        if (it == bins_.end()) continue;
        for (uint32_t ci : it->second) {
          const FieldCell& c = cells_[ci];
          const double d = cell_km(lat, lon, c.lat, c.lon);
          if (d < best ||
              (d == best &&
               (best_i < 0 || c.lat < best_lat ||
                (c.lat == best_lat && c.lon < best_lon)))) {
            best = d;
            best_i = (long)ci;
            best_lat = c.lat;
            best_lon = c.lon;
          }
        }
      }
    }
  }
  return best_i;
}

std::optional<double> FieldView::value(double lat, double lon) const {
  const long i = nearest(lat, lon);
  if (i < 0) return std::nullopt;
  return cells_[i].pm25;
}

std::optional<double> FieldView::sigma(double lat, double lon) const {
  const long i = nearest(lat, lon);
  if (i < 0) return std::nullopt;
  return cells_[i].sigma;
}

std::optional<std::array<double, 3>> FieldView::band(double lat,
                                                     double lon) const {
  const long i = nearest(lat, lon);
  if (i < 0) return std::nullopt;
  const FieldCell& c = cells_[i];
  return std::array<double, 3>{c.lo, c.pm25, c.hi};
}

// ---------------------------------------------------------------------------
// segment_samples — exposure.segment_samples verbatim.
// ---------------------------------------------------------------------------
std::vector<SegSample> segment_samples(
    const std::vector<std::pair<double, double>>& coords, double duration_s,
    double step_m) {
  std::vector<SegSample> out;
  const size_t n = coords.size();
  if (n < 2) return out;
  CSum total_cs;
  for (size_t i = 1; i < n; ++i)
    total_cs.add(haversine_m(coords[i - 1], coords[i]));
  const double total = total_cs.total();
  if (total <= 0) return out;
  double carry = 0.0;
  for (size_t i = 1; i < n; ++i) {
    const auto& a = coords[i - 1];
    const auto& b = coords[i];
    const double seg = haversine_m(a, b);
    carry += seg;
    if (carry >= step_m || i == n - 1) {
      // carry, not seg — the sample stands for all meters since the last
      // emission (parity with exposure.segment_samples)
      const double frac = carry / total;
      out.push_back(SegSample{b.second, b.first, duration_s * frac, carry});
      carry = 0.0;
    }
  }
  CSum s_cs;
  for (const auto& x : out) s_cs.add(x.seconds);
  double s = s_cs.total();
  if (s == 0.0) s = 1.0;
  for (auto& x : out) x.seconds *= duration_s / s;
  return out;
}

// ---------------------------------------------------------------------------
// integrate_dose — dose_ug = sum C*me*ve*dt; band = conservative cell sums.
// ---------------------------------------------------------------------------
DoseResult integrate_dose(
    const std::vector<std::pair<double, double>>& coords,
    const FieldView& field, double me, double ve, double duration_s,
    double step_m) {
  const std::vector<SegSample> samples =
      segment_samples(coords, duration_s, step_m);
  DoseResult r;
  r.n_samples = (long)samples.size();
  if (samples.empty()) return r;
  double lo = 0.0, mid = 0.0, hi = 0.0;
  for (const SegSample& s : samples) {
    const auto b = field.band(s.lat, s.lon);
    r.dist_km += s.dist_m / 1000.0;
    if (!b) continue;
    ++r.n_hit;
    const double t_min = s.seconds / 60.0;
    lo += (*b)[0] * me * ve * t_min;
    mid += (*b)[1] * me * ve * t_min;
    hi += (*b)[2] * me * ve * t_min;
  }
  r.coverage = (double)r.n_hit / (double)samples.size();
  if (r.n_hit == 0) return r;
  r.lo = lo;
  r.mid = mid;
  r.hi = hi;
  return r;
}

// ---------------------------------------------------------------------------
// dose_series — exposure.dose's accumulation loop over a flat series
// (non-finite c skipped, c<0 clamped, zip-order += — see field.hpp).
// ---------------------------------------------------------------------------
double dose_series(const std::vector<double>& pm25,
                   const std::vector<double>& dt_s,
                   double ventilation_lpm, double microenv) {
  const double ve = ventilation_lpm / 1000.0;  // m3/min, exposure's order
  double total = 0.0;
  const size_t n = std::min(pm25.size(), dt_s.size());
  for (size_t i = 0; i < n; ++i) {
    double c = pm25[i];
    const double dt = dt_s[i];
    if (!std::isfinite(c)) continue;
    if (!std::isfinite(dt) || dt < 0.0) continue;
    if (c < 0.0) c = 0.0;
    const double c_eff = c * microenv;
    total += c_eff * ve * (dt / 60.0);
  }
  return total;
}

}  // namespace alive
