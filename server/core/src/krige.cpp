// ALive-108 — kriging field kernels. See include/alive/krige.hpp for the
// contract and the legacy/corrected variance notes.

#include "alive/krige.hpp"

#include <cmath>

namespace alive {
namespace {

// Structural covariance C(d) = psill * exp(-d / range_km). The nugget is
// observation noise — it enters K only on the diagonal and never the
// query rhs (krige.py's correct nugget-effect model).
inline double covar(double d, double psill, double range) {
  return psill * std::exp(-d / range);
}

}  // namespace

bool KrigeField::fit(std::vector<double> lat, std::vector<double> lon,
                     std::vector<double> z, const KrigeParams& params) {
  const size_t n = z.size();  // captured before z is moved
  return fit_impl(std::move(lat), std::move(lon), std::move(z),
                  std::vector<std::vector<double>>(n, {1.0}), params, false);
}

bool KrigeField::fit_universal(std::vector<double> lat, std::vector<double> lon,
                               std::vector<double> z,
                               std::vector<std::vector<double>> drift,
                               const KrigeParams& params) {
  return fit_impl(std::move(lat), std::move(lon), std::move(z),
                  std::move(drift), params, true);
}

bool KrigeField::fit_impl(std::vector<double> lat, std::vector<double> lon,
                          std::vector<double> z,
                          std::vector<std::vector<double>> drift,
                          const KrigeParams& params, bool universal) {
  on_ = false;
  universal_ = universal;
  params_ = params;
  const size_t n = z.size();
  if (n != lat.size() || n != lon.size() || n != drift.size()) return false;
  if (n < params.min_samples) return false;
  if (drift.empty()) return false;
  p_ = drift[0].size();
  if (p_ == 0) return false;
  for (const auto& row : drift)
    if (row.size() != p_) return false;

  // sill = population variance of z (krige.py np.var); dead-flat -> off
  Eigen::VectorXd zv = Eigen::Map<const Eigen::VectorXd>(z.data(), n);
  const double mean = zv.mean();
  sill_ = (zv.array() - mean).square().sum() / static_cast<double>(n);
  if (!(sill_ >= params.sill_floor)) return false;
  nugget_ = params.nugget_frac * sill_;
  psill_ = sill_ - nugget_;

  pts_.resize(n, 2);
  drift_.resize(n, p_);
  for (size_t i = 0; i < n; ++i) {
    pts_(i, 0) = lat[i] * params.ky;
    pts_(i, 1) = lon[i] * params.kx;
    for (size_t a = 0; a < p_; ++a) drift_(i, a) = drift[i][a];
  }
  z_ = std::move(zv);

  // Default target drift for ordinary fields so estimate(lat, lon) works
  // bare, exactly like krige.py. Universal queries must pass their row.
  f0_default_ = universal_ ? std::vector<double>()
                           : std::vector<double>(p_, 1.0);

  // Augmented system A [w; lam] = [k; f0]:
  //   A = [ K  F ]   K(i,j) = psill*exp(-d_ij/range) + nugget*delta_ij
  //       [ F^T 0 ]
  const size_t m = n + p_;
  Eigen::MatrixXd A(m, m);
  for (size_t i = 0; i < n; ++i) {
    for (size_t j = 0; j < n; ++j) {
      const double dx = pts_(i, 0) - pts_(j, 0);
      const double dy = pts_(i, 1) - pts_(j, 1);
      A(i, j) = covar(std::sqrt(dx * dx + dy * dy), psill_,
                      params.range_km)
              + (i == j ? nugget_ : 0.0);
    }
    for (size_t a = 0; a < p_; ++a) {
      A(i, n + a) = drift_(i, a);
      A(n + a, i) = drift_(i, a);
    }
  }
  A.bottomRightCorner(p_, p_).setZero();

  lu_.compute(A);
  // Singularity check: a probe solve must reproduce the rhs within float
  // noise (LU on a singular system returns garbage instead of throwing).
  const Eigen::VectorXd probe_b = Eigen::VectorXd::Ones(m);
  const Eigen::VectorXd probe_x = lu_.solve(probe_b);
  const double resid = (A * probe_x - probe_b).norm();
  if (!std::isfinite(resid) || resid > 1e-6 * m) return false;
  on_ = true;
  return true;
}

std::optional<std::vector<double>> KrigeField::weights(
    double lat, double lon, const std::vector<double>& drift) const {
  if (!on_) return std::nullopt;
  const std::vector<double>& f0 = drift.empty() ? f0_default_ : drift;
  if (f0.size() != p_) return std::nullopt;
  const size_t n = static_cast<size_t>(z_.size());

  const double x = lat * params_.ky;
  const double y = lon * params_.kx;
  Eigen::VectorXd rhs(n + p_);
  for (size_t i = 0; i < n; ++i) {
    const double dx = pts_(i, 0) - x;
    const double dy = pts_(i, 1) - y;
    rhs(i) = covar(std::sqrt(dx * dx + dy * dy), psill_,
                   params_.range_km);
  }
  for (size_t a = 0; a < p_; ++a) rhs(n + a) = f0[a];

  Eigen::VectorXd w = lu_.solve(rhs);
  if (!w.allFinite()) return std::nullopt;
  return std::vector<double>(w.data(), w.data() + w.size());
}

std::optional<std::pair<double, double>> KrigeField::estimate(
    double lat, double lon, const std::vector<double>& drift) const {
  if (!on_) return std::nullopt;
  const std::vector<double>& f0v = drift.empty() ? f0_default_ : drift;
  if (f0v.size() != p_) return std::nullopt;
  const size_t n = static_cast<size_t>(z_.size());

  const double x = lat * params_.ky;
  const double y = lon * params_.kx;
  Eigen::VectorXd rhs(n + p_);
  for (size_t i = 0; i < n; ++i) {
    const double dx = pts_(i, 0) - x;
    const double dy = pts_(i, 1) - y;
    rhs(i) = covar(std::sqrt(dx * dx + dy * dy), psill_,
                   params_.range_km);
  }
  for (size_t a = 0; a < p_; ++a) rhs(n + a) = f0v[a];

  const Eigen::VectorXd w = lu_.solve(rhs);
  if (!w.allFinite()) return std::nullopt;
  const Eigen::VectorXd k = rhs.head(n);
  const Eigen::VectorXd wv = w.head(n);
  const Eigen::VectorXd f0 =
      Eigen::Map<const Eigen::VectorXd>(f0v.data(), p_);

  const double mu = wv.dot(z_);
  const double wk = wv.dot(k);
  const double lam_f = w.tail(p_).dot(f0);
  // sigma^2 = C_Z(0) - w.k - lam.f0 with C_Z(0) = psill (smooth-field
  // variance). Under the nugget-on-diagonal kernel that IS the true error
  // variance w^TKw - 2w.k + C(0) — legacy/corrected coincide; the flag
  // remains for API stability. mu is NOT clamped — airindex relies on
  // signed residuals (krige.py contract).
  const double var = psill_ - wk - lam_f;
  const double sigma = std::sqrt(std::max(1.0, var));
  return std::pair<double, double>{mu, sigma};
}

}  // namespace alive
