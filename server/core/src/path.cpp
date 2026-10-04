// ALive-108 — least-inhalation path engine. Parity oracle:
// server/routegraph.py PyPathEngine — keep semantics bit-identical.

#include "alive/path.hpp"

#include <algorithm>
#include <cmath>
#include <cstring>
#include <limits>
#include <queue>
#include <stdexcept>
#include <tuple>

namespace alive {
namespace {

constexpr double kRM = 6371000.0;
constexpr double kSnapRadiusM = 1500.0;
constexpr int kMaxSamplePts = 5;

// per-mode uplift keyed by hw code — exposure.py's published factors
double uplift(uint8_t hw) {
  switch (hw) {
    case 0: case 1: return 1.35;   // motorway(+link)
    case 2: case 3: return 1.30;   // trunk(+link)
    case 4: case 5: return 1.20;   // primary(+link)
    case 6: case 7: return 1.10;   // secondary(+link)
    case 8: case 9: return 1.05;   // tertiary(+link)
    default: return 1.0;
  }
}

double hav_m(double lon1, double lat1, double lon2, double lat2) {
  const double p1 = lat1 * M_PI / 180.0, p2 = lat2 * M_PI / 180.0;
  const double dp = p2 - p1, dl = (lon2 - lon1) * M_PI / 180.0;
  const double a = std::sin(dp / 2) * std::sin(dp / 2) +
                   std::cos(p1) * std::cos(p2) * std::sin(dl / 2) *
                       std::sin(dl / 2);
  return 2.0 * kRM * std::asin(std::sqrt(a));
}

struct Rd {
  const char* p;
  size_t off = 0;
  template <class T> T take() {
    T v;
    std::memcpy(&v, p + off, sizeof(T));
    off += sizeof(T);
    return v;
  }
  std::string take_str(uint16_t n) {
    std::string s(p + off, p + off + n);
    off += n;
    return s;
  }
};

// deny mask helper — bits for hw codes
constexpr uint32_t deny(std::initializer_list<int> codes) {
  uint32_t m = 0;
  for (int c : codes) m |= (1u << c);
  return m;
}

// Mode tables — same values as routegraph.py MODE_RULES/MODE_VE/MODE_ME.
// 15=cycleway 16=footway 17=pedestrian 18=path 19=steps 20=bridleway
// 21=corridor; 0/1=motorway(+link).
constexpr uint32_t kDenyFoot = deny({15, 16, 17, 18, 19, 20, 21});
constexpr uint32_t kDenyFootAndMotor =
    kDenyFoot | deny({0, 1});
const PathRule kRules[] = {
    {kDenyFoot, true, 0.0, 0.0},             // 0 car
    {kDenyFoot, true, 0.0, 0.0},             // 1 car_open
    {kDenyFoot, true, 0.0, 0.0},             // 2 cab
    {kDenyFootAndMotor, true, 40.0, 0.0},    // 3 auto
    {kDenyFoot, true, 30.0, 0.0},            // 4 bike
    {deny({0, 1}), false, 16.0, 0.0},        // 5 cycle
    {deny({0, 1}), false, 0.0, 5.0},         // 6 walk
};
constexpr int kModeCount = sizeof(kRules) / sizeof(kRules[0]);
const char* kModeNames[kModeCount] = {"car", "car_open", "cab", "auto",
                                      "bike", "cycle", "walk"};
constexpr double kModeVE[kModeCount] = {7.5, 7.5, 7.5, 8.5, 9.0, 22.0,
                                        14.0};
constexpr double kModeME[kModeCount] = {0.55, 0.80, 0.80, 1.15, 1.10,
                                        1.10, 1.00};

int mode_index(const std::string& mode) {
  for (int i = 0; i < kModeCount; ++i)
    if (mode == kModeNames[i]) return i;
  return 0;  // routegraph.py: unknown mode falls back to car
}

}  // namespace

const PathRule& PathEngine::rule(const std::string& mode) {
  return kRules[mode_index(mode)];
}

PathEngine::PathEngine(const std::string& blob) {
  Rd r{blob.data()};
  if (r.take<uint32_t>() != 0x31475241u)  // "ARG1" little-endian
    throw std::runtime_error("route_graph: bad magic");
  const uint32_t nn = r.take<uint32_t>();
  const uint32_t ne = r.take<uint32_t>();
  const uint32_t nname = r.take<uint32_t>();
  r.take<uint32_t>();  // n_pts informational
  for (int i = 0; i < 4; ++i) bbox_[i] = r.take<int32_t>();

  node_lon_.resize(nn);
  node_lat_.resize(nn);
  for (uint32_t i = 0; i < nn; ++i) {
    node_lon_[i] = r.take<int32_t>();
    node_lat_[i] = r.take<int32_t>();
  }

  names_.reserve(nname);
  for (uint32_t i = 0; i < nname; ++i) {
    const uint16_t ln = r.take<uint16_t>();
    names_.push_back(r.take_str(ln));
  }

  e_u_.resize(ne);
  e_v_.resize(ne);
  e_len_.resize(ne);
  e_pts_off_.resize(ne);
  e_pts_n_.resize(ne);
  e_hw_.resize(ne);
  e_ow_.resize(ne);
  e_sp_.resize(ne);
  e_nm_.resize(ne);
  e_field_.resize(ne);
  for (uint32_t i = 0; i < ne; ++i) {
    e_u_[i] = r.take<uint32_t>();
    e_v_[i] = r.take<uint32_t>();
    e_len_[i] = r.take<float>();
    e_pts_off_[i] = r.take<uint32_t>();
    e_pts_n_[i] = r.take<uint16_t>();
    e_hw_[i] = r.take<uint8_t>();
    e_ow_[i] = r.take<int8_t>();
    e_sp_[i] = r.take<uint8_t>();
    e_nm_[i] = r.take<int32_t>();
    e_field_[i] = r.take<uint8_t>();
  }

  const size_t n_ints = (blob.size() - r.off) / 4;
  pts_.resize(n_ints);
  std::memcpy(pts_.data(), blob.data() + r.off, n_ints * 4);

  // CSR adjacency — directed edges both ways unless oneway; high bit on
  // the stored id means traverse v->u (same marker as the oracle).
  adj_off_.assign(nn + 1, 0);
  for (uint32_t i = 0; i < ne; ++i) {
    if (e_ow_[i] >= 0) adj_off_[e_u_[i] + 1]++;
    if (e_ow_[i] <= 0) adj_off_[e_v_[i] + 1]++;
  }
  for (size_t i = 1; i < adj_off_.size(); ++i)
    adj_off_[i] += adj_off_[i - 1];
  adj_flat_.resize(adj_off_[nn]);
  {
    std::vector<uint32_t> cur(adj_off_.begin(), adj_off_.end() - 1);
    for (uint32_t i = 0; i < ne; ++i) {
      if (e_ow_[i] >= 0) adj_flat_[cur[e_u_[i]]++] = i;
      if (e_ow_[i] <= 0)
        adj_flat_[cur[e_v_[i]]++] = i | 0x80000000u;
    }
  }
  conc_.assign(ne, 0.0f);
  conc_set_.assign(ne, 0);
}

std::vector<std::pair<double, double>> PathEngine::edge_pts(
    uint32_t i) const {
  const uint32_t off = e_pts_off_[i];
  const int n = e_pts_n_[i];
  int32_t lon = pts_[off], lat = pts_[off + 1];
  std::vector<std::pair<double, double>> out;
  out.reserve(n);
  out.emplace_back(lon / 1e6, lat / 1e6);
  uint32_t k = off + 2;
  for (int j = 1; j < n; ++j) {
    const int32_t packed = pts_[k++];
    int16_t dl = static_cast<int16_t>(packed & 0xFFFF);
    int16_t dp = static_cast<int16_t>(packed >> 16);
    lon += dl;
    lat += dp;
    out.emplace_back(lon / 1e6, lat / 1e6);
  }
  return out;
}

void PathEngine::reweight(const FieldSampler& sampler) {
  double acc = 0.0;
  double mn = std::numeric_limits<double>::max();
  int got_e = 0;
  for (uint32_t i = 0; i < e_u_.size(); ++i) {
    if (!e_field_[i]) {
      conc_set_[i] = 0;
      continue;
    }
    const auto pts = edge_pts(i);
    int k = std::min<int>(kMaxSamplePts,
                          1 + static_cast<int>(std::ceil(e_len_[i] / 200.0)));
    double c_acc = 0.0;
    int got = 0;
    for (int s = 0; s < k; ++s) {
      const int idx =
          (k > 1) ? static_cast<int>(std::nearbyint(
                        static_cast<double>(s) * (pts.size() - 1) / (k - 1)))
                  : 0;
      // mirror oracle: dedupe repeated indices (sorted set); nearbyint
      // rounds half-to-even like Python's round()
      bool dup = false;
      for (int t = 0; t < s; ++t) {
        const int prev =
            (k > 1) ? static_cast<int>(std::nearbyint(
                          static_cast<double>(t) * (pts.size() - 1) / (k - 1)))
                    : 0;
        if (prev == idx) { dup = true; break; }
      }
      if (dup) continue;
      const auto c = sampler(pts[idx].second, pts[idx].first);
      if (c && std::isfinite(*c) && *c >= 0) {
        c_acc += *c;
        ++got;
      }
    }
    if (got) {
      const double m = c_acc / got;
      conc_[i] = static_cast<float>(m);
      conc_set_[i] = 1;
      acc += m;
      if (m < mn) mn = m;
      ++got_e;
    } else {
      conc_set_[i] = 0;
    }
  }
  edges_priced_ = got_e;
  field_mean_ = got_e ? acc / got_e : 0.0;
  min_conc_ = (mn == std::numeric_limits<double>::max()) ? 0.0 : mn;
}

double PathEngine::conc(uint32_t e) const {
  return conc_set_[e] ? static_cast<double>(conc_[e]) : field_mean_;
}

double PathEngine::mode_speed(uint32_t e, const PathRule& r) const {
  if (r.speed_const_kmh > 0) return r.speed_const_kmh;
  double sp = e_sp_[e];
  if (r.speed_cap_kmh > 0) sp = std::min(sp, r.speed_cap_kmh);
  return sp;
}

bool PathEngine::legal(uint32_t e, bool rev, const PathRule& r) const {
  if (r.deny_mask & (1u << e_hw_[e])) return false;
  if (r.oneway) {
    const int8_t ow = e_ow_[e];
    if (ow == 1 && rev) return false;
    if (ow == -1 && !rev) return false;
  }
  return mode_speed(e, r) > 0;
}

int PathEngine::snap(double lat, double lon, const PathRule& r,
                     double* d_out) const {
  const double dlat = kSnapRadiusM / 111320.0;
  const double dlon =
      dlat / std::max(0.2, std::cos(lat * M_PI / 180.0));
  int best = -1;
  double bd = kSnapRadiusM;
  for (size_t n = 0; n < node_lat_.size(); ++n) {
    const double y = node_lat_[n] / 1e6;
    if (y < lat - dlat || y > lat + dlat) continue;
    const double x = node_lon_[n] / 1e6;
    if (x < lon - dlon || x > lon + dlon) continue;
    const double d = hav_m(lon, lat, x, y);
    if (d >= bd) continue;
    for (uint32_t a = adj_off_[n]; a < adj_off_[n + 1]; ++a) {
      const uint32_t ei = adj_flat_[a];
      if (legal(ei & 0x7FFFFFFFu, (ei & 0x80000000u) != 0, r)) {
        best = static_cast<int>(n);
        bd = d;
        break;
      }
    }
  }
  if (d_out) *d_out = (best >= 0) ? bd : 0.0;
  return best;
}

PathResult PathEngine::query(double olat, double olon, double dlat,
                             double dlon, const std::string& mode) const {
  PathResult res;
  const int mi = mode_index(mode);
  const PathRule& rl = kRules[mi];
  const double ve = kModeVE[mi], me = kModeME[mi];

  double sd = 0.0, td = 0.0;
  const int s = snap(olat, olon, rl, &sd);
  const int t = snap(dlat, dlon, rl, &td);
  res.snap_from_m = sd;
  res.snap_to_m = td;
  if (s < 0 || t < 0) {
    res.error = "no graph node near endpoint";
    return res;
  }

  const size_t nn = node_lon_.size();
  std::vector<double> gs(nn, std::numeric_limits<double>::infinity());
  std::vector<int32_t> par_e(nn, -1);
  std::vector<int32_t> par_n(nn, -1);
  std::vector<char> par_rev(nn, 0), settled(nn, 0);

  // admissible h: gc dist * cheapest dose/m achievable
  const double h_rate = (field_mean_ > 0 && min_conc_ > 0)
                            ? min_conc_ * me * (ve / 1000.0) * (0.06 / 250.0)
                            : 0.0;
  auto h = [&](uint32_t n) {
    return hav_m(node_lon_[n] / 1e6, node_lat_[n] / 1e6, dlon, dlat) *
           h_rate;
  };

  // (f, gc, node) — same tuple order as the oracle's heapq entries so
  // tie-breaks resolve identically
  using QI = std::tuple<double, double, uint32_t>;
  std::priority_queue<QI, std::vector<QI>, std::greater<QI>> pq;
  gs[s] = 0.0;
  pq.emplace(h(s), 0.0, static_cast<uint32_t>(s));
  while (!pq.empty()) {
    const auto [f, gc, n] = pq.top();
    pq.pop();
    if (settled[n]) continue;
    settled[n] = 1;
    if (static_cast<int>(n) == t) break;
    for (uint32_t a = adj_off_[n]; a < adj_off_[n + 1]; ++a) {
      const uint32_t ei = adj_flat_[a];
      const bool rev = (ei & 0x80000000u) != 0;
      const uint32_t e = ei & 0x7FFFFFFFu;
      if (!legal(e, rev, rl)) continue;
      const double sp = mode_speed(e, rl);
      const double rate =
          conc(e) * me * uplift(e_hw_[e]) * (ve / 1000.0) * (0.06 / sp);
      const double ng = gc + rate * e_len_[e];
      const uint32_t to = rev ? e_u_[e] : e_v_[e];
      if (ng < gs[to] - 1e-9) {
        gs[to] = ng;
        par_n[to] = static_cast<int32_t>(n);
        par_e[to] = static_cast<int32_t>(e);
        par_rev[to] = rev ? 1 : 0;
        pq.emplace(ng + h(to), ng, to);
      }
    }
  }
  if (!std::isfinite(gs[t])) {
    res.error = "no path in graph";
    return res;
  }

  // unwind
  std::vector<std::pair<uint32_t, bool>> chain;
  for (int n = t; n != s;) {
    const int32_t e = par_e[n];
    if (e < 0) {  // defensive — shouldn't happen when gs[t] finite
      res.error = "no path in graph";
      return res;
    }
    chain.emplace_back(static_cast<uint32_t>(e), par_rev[n] != 0);
    n = par_n[n];
  }
  std::reverse(chain.begin(), chain.end());

  res.ok = true;
  res.edges = static_cast<int>(chain.size());
  std::string last_name;
  for (const auto& [e, rev] : chain) {
    auto pts = edge_pts(e);
    if (rev) std::reverse(pts.begin(), pts.end());
    const size_t skip = res.coords.empty() ? 0 : 1;
    for (size_t i = skip; i < pts.size(); ++i) {
      res.coords.push_back(pts[i].first);
      res.coords.push_back(pts[i].second);
    }
    const double ln = e_len_[e];
    const double sp = mode_speed(e, rl);
    const double t_min = ln / (sp * 1000.0 / 60.0);
    res.dose_ug += conc(e) * me * uplift(e_hw_[e]) * (ve / 1000.0) * t_min;
    res.distance_m += ln;
    res.duration_s += t_min * 60.0;
    int32_t nm = e_nm_[e];
    if (nm) {
      nm -= 1;  // stored as idx+1
      if (nm >= 0 && static_cast<size_t>(nm) < names_.size() &&
          names_[nm] != last_name) {
        last_name = names_[nm];
        res.names.push_back(last_name);
      }
    }
  }
  if (res.names.size() > 12) res.names.resize(12);
  return res;
}

}  // namespace alive
