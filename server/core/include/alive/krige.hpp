// ALive-108 — kriging field kernels (alive_core, Phase-5).
//
// Ordinary + universal (regression) kriging over station observations and
// covariates, with Eigen factorisation reused across estimates.
//
// Semantics mirror server/krige.py::KrigeField exactly in legacy mode so the
// C++ kernel is a drop-in replacement: sill = var(z) (population), nugget =
// nugget_frac*sill, covariance C(d) = nugget + sill*exp(-d/range), the
// (n+p)x(n+p) augmented system [K F; F^T 0][w; lam] = [k; f0], and the
// krige.py variance formula var = sill - w.k + lam.f0.
//
// KrigeParams::legacy_variance=false switches to the mathematically exact
// error variance var = C(0) - w.k - lam.f0 with C(0) = sill + nugget.
// krige.py's formula under-reports sigma ~20-30% away from stations (it
// drops the nugget from C(0) and flips the Lagrange-multiplier sign);
// quantified in docs/plan/bench-krige.md. mu is identical under both modes.
//
// Coordinates are projected to km (equirectangular at ~28.6N) exactly as
// krige.py does, so `range_km` lives in real distance.
#pragma once

#include <Eigen/Dense>
#include <cstddef>
#include <optional>
#include <utility>
#include <vector>

namespace alive {

struct KrigeParams {
  double ky = 110.6;              // km per degree latitude  (krige.py _KY)
  double kx = 99.4;               // km per degree longitude (krige.py _KX)
  double range_km = 15.0;         // exponential covariance range (_RANGE_KM)
  double nugget_frac = 0.15;      // nugget = frac*sill      (_NUGGET_FRAC)
  size_t min_samples = 20;        // krige.py fit() minimum sample count
  double sill_floor = 2.0;        // dead-flat guard (sill_est < 2.0 -> off)
  bool legacy_variance = true;    // true: sigma as krige.py (drop-in parity)
                                  // false: corrected C(0) - w.k - lam.f0
};

class KrigeField {
 public:
  KrigeField() = default;

  // Ordinary kriging (constant-mean drift). Returns false when the field
  // cannot be fit (too few samples, dead-flat, singular system) — callers
  // keep their IDW fallback, same contract as krige.py.
  bool fit(std::vector<double> lat, std::vector<double> lon,
           std::vector<double> z, const KrigeParams& params = {});

  // Universal (regression) kriging. drift[i] is the covariate row at
  // station i (e.g. {1.0, model_prior}); estimate() then takes the
  // covariate row at the target. The ordinary case is drift = ones(n,1).
  bool fit_universal(std::vector<double> lat, std::vector<double> lon,
                     std::vector<double> z,
                     std::vector<std::vector<double>> drift,
                     const KrigeParams& params = {});

  // -> (mu, sigma) or nullopt when unfitted or when a universal field is
  // queried without its drift row. mu is clamped >= 0 and sigma >= 1,
  // matching krige.py's output contract.
  std::optional<std::pair<double, double>> estimate(
      double lat, double lon, const std::vector<double>& drift = {}) const;

  // Solved weight vector [w (n) | lam (p)] at the target, or nullopt —
  // exposed for validation/parity tests.
  std::optional<std::vector<double>> weights(
      double lat, double lon, const std::vector<double>& drift = {}) const;

  bool fitted() const { return on_; }
  size_t n() const { return static_cast<size_t>(z_.size()); }
  size_t n_drift() const { return p_; }
  double sill() const { return sill_; }
  double nugget() const { return nugget_; }
  double range_km() const { return params_.range_km; }

 private:
  bool fit_impl(std::vector<double> lat, std::vector<double> lon,
                std::vector<double> z,
                std::vector<std::vector<double>> drift,
                const KrigeParams& params, bool universal);

  Eigen::Matrix<double, Eigen::Dynamic, 2> pts_;  // sample coords, km
  Eigen::VectorXd z_;                              // observations
  Eigen::MatrixXd drift_;                          // n x p drift design
  Eigen::FullPivLU<Eigen::MatrixXd> lu_;           // factorised system
  std::vector<double> f0_default_;                 // ones(p) when ordinary
  KrigeParams params_;
  double sill_ = 0.0;
  double nugget_ = 0.0;
  double psill_ = 0.0;   // structural sill = sill_ - nugget_
  size_t p_ = 0;                                   // drift width
  bool universal_ = false;
  bool on_ = false;
};

}  // namespace alive
