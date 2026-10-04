// ALive-108 — least-inhalation path engine. Parity oracle:
// server/routegraph.py PyPathEngine — keep semantics bit-identical.

#include "alive/path.hpp"

#include <algorithm>
#include <cmath>
#include <cstring>
#include <limits>
#include <numeric>
#include <queue>
#include <stdexcept>
#include <tuple>
#include <unordered_set>

namespace alive {
namespace {

constexpr double kRM = 6371000.0;
constexpr double kSnapRadiusM = 1500.0;
constexpr int kMaxSamplePts = 5;

// NOTE: the priced objective uses a FLAT uplift (1.0) — routegraph.py
// documents why: the display integrator (_dose_band) never sees
// road_class, so pricing near-road uplift made engine corridors
// systematically slower AND worse-displayed. Priced dose now equals
// the shown integrand.
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
// acc bits: 1 motor | 2 bicycle | 4 foot | 8 motorcar | 16 motorcycle.
// turn bits: 1 motorized | 2 cycle | 4 walk.
constexpr uint8_t kAccMotor = 1, kAccCycle = 2, kAccFoot = 4,
                  kAccCar = 8, kAccMoto = 16;
constexpr uint32_t kDenyFoot = deny({15, 16, 17, 18, 19, 20, 21});
constexpr uint32_t kDenyFootAndMotor =
    kDenyFoot | deny({0, 1});
const PathRule kRules[] = {
    {kDenyFoot, true, 0.0, 0.0, kAccMotor | kAccCar, 1},  // 0 car
    {kDenyFoot, true, 0.0, 0.0, kAccMotor | kAccCar, 1},  // 1 car_open
    {kDenyFoot, true, 0.0, 0.0, kAccMotor | kAccCar, 1},  // 2 cab
    {kDenyFootAndMotor, true, 40.0, 0.0, kAccMotor, 1},   // 3 auto
    {kDenyFoot, true, 50.0, 0.0, kAccMotor | kAccMoto, 1},// 4 bike
    {deny({0, 1}), false, 16.0, 0.0, kAccCycle, 2},       // 5 cycle
    {deny({0, 1}), false, 0.0, 5.0, kAccFoot, 4},         // 6 walk
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
  const uint32_t magic = r.take<uint32_t>();
  const bool arg2 = magic == 0x32475241u;   // "ARG2" little-endian
  if (!arg2 && magic != 0x31475241u)        // "ARG1"
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
  e_acc_.assign(ne, 0);
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
    if (arg2) e_acc_[i] = r.take<uint8_t>();
  }

  // ARG2 turn bans: (dir-in | via | dir-out | mode mask) — keyed
  // (in_dir << 32 | via) -> {out_dir: mask} for the A* transition check
  if (arg2) {
    const uint32_t nb = r.take<uint32_t>();
    for (uint32_t i = 0; i < nb; ++i) {
      const uint32_t din = r.take<uint32_t>();
      const uint32_t via = r.take<uint32_t>();
      const uint32_t dout = r.take<uint32_t>();
      const uint8_t mask = r.take<uint8_t>();
      bans_[(static_cast<uint64_t>(din) << 32) | via][dout] = mask;
    }
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
  // Price into a scratch table: queries hold conc_mtx_ shared for the
  // whole solve, so swapping under a brief unique hold is the only
  // moment writer and readers ever contend — a ~1.2M-edge sweep never
  // stalls A* and A* never reads a half-updated epoch.
  std::vector<float> conc(conc_.size(), 0.0f);
  std::vector<char> conc_set(conc_set_.size(), 0);
  double acc = 0.0;
  double mn = std::numeric_limits<double>::max();
  int got_e = 0;
  for (uint32_t i = 0; i < e_u_.size(); ++i) {
    if (!e_field_[i]) {
      conc_set[i] = 0;
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
      conc[i] = static_cast<float>(m);
      conc_set[i] = 1;
      acc += m;
      if (m < mn) mn = m;
      ++got_e;
    } else {
      conc_set[i] = 0;
    }
  }
  std::unique_lock<std::shared_mutex> lk(conc_mtx_);
  conc_.swap(conc);
  conc_set_.swap(conc_set);
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
  if (e_acc_[e] & r.acc_mask) return false;  // per-way access override
  if (r.oneway) {
    const int8_t ow = e_ow_[e];
    if (ow == 1 && rev) return false;
    if (ow == -1 && !rev) return false;
  }
  return mode_speed(e, r) > 0;
}

// ---- connectivity screen: per-mode main-net floods (lazy) ----------
// routegraph.py _rev_adj/_flood/_reach_sets is the parity oracle.
void PathEngine::build_radj() const {
  if (!radj_off_.empty()) return;
  const size_t nn = node_lon_.size(), ne = e_u_.size();
  radj_off_.assign(nn + 1, 0);
  for (uint32_t i = 0; i < ne; ++i) {
    if (e_ow_[i] >= 0) radj_off_[e_v_[i] + 1]++;   // fwd dir enters v
    if (e_ow_[i] <= 0) radj_off_[e_u_[i] + 1]++;   // rev dir enters u
  }
  for (size_t i = 1; i < radj_off_.size(); ++i)
    radj_off_[i] += radj_off_[i - 1];
  radj_flat_.resize(radj_off_[nn]);
  std::vector<uint32_t> cur(radj_off_.begin(), radj_off_.end() - 1);
  for (uint32_t i = 0; i < ne; ++i) {
    if (e_ow_[i] >= 0) radj_flat_[cur[e_v_[i]]++] = i;
    if (e_ow_[i] <= 0) radj_flat_[cur[e_u_[i]]++] = i | 0x80000000u;
  }
}

std::vector<uint8_t> PathEngine::flood(uint32_t seed, const PathRule& r,
                                       bool reverse) const {
  const auto& off = reverse ? radj_off_ : adj_off_;
  const auto& flat = reverse ? radj_flat_ : adj_flat_;
  std::vector<uint8_t> seen(node_lon_.size(), 0);
  seen[seed] = 1;
  std::vector<uint32_t> fr{seed};
  while (!fr.empty()) {
    const uint32_t n = fr.back();
    fr.pop_back();
    for (uint32_t a = off[n]; a < off[n + 1]; ++a) {
      const uint32_t ei = flat[a];
      const uint32_t e = ei & 0x7FFFFFFFu;
      const bool rev = (ei & 0x80000000u) != 0;
      if (!legal(e, rev, r)) continue;
      // forward: successor = head of the travelled dir; reverse:
      // predecessor = tail of the travelled dir
      const uint32_t w = reverse ? (rev ? e_v_[e] : e_u_[e])
                                 : (rev ? e_u_[e] : e_v_[e]);
      if (!seen[w]) { seen[w] = 1; fr.push_back(w); }
    }
  }
  return seen;
}

const std::pair<std::vector<uint8_t>, std::vector<uint8_t>>&
PathEngine::reach_sets(int mi, const PathRule& r) const {
  {
    std::shared_lock<std::shared_mutex> lk(reach_mtx_);
    auto it = reach_.find(mi);
    if (it != reach_.end()) return it->second;
  }
  std::unique_lock<std::shared_mutex> lk(reach_mtx_);
  {   // another builder may have won while we waited for the lock
    auto it = reach_.find(mi);
    if (it != reach_.end()) return it->second;
  }
  constexpr double kMainMinFrac = 0.30;   // routegraph.MAIN_MIN_FRAC
  constexpr int kSeedCandidates = 8;      // routegraph.SEED_CANDIDATES
  const size_t nn = node_lon_.size();
  // seeds: highest-degree nodes first (junctions sit on the main net
  // almost surely), deterministic (degree desc, id asc) like the oracle
  std::vector<uint32_t> seeds(nn);
  std::iota(seeds.begin(), seeds.end(), 0u);
  const auto mid = seeds.begin() +
      std::min<size_t>(kSeedCandidates, nn);
  std::partial_sort(seeds.begin(), mid, seeds.end(),
                    [&](uint32_t a, uint32_t b) {
    const uint32_t da = adj_off_[a + 1] - adj_off_[a];
    const uint32_t db = adj_off_[b + 1] - adj_off_[b];
    return da != db ? da > db : a < b;
  });
  std::vector<uint8_t> post;
  uint32_t seed = seeds[0];
  size_t best = 0;
  for (int k = 0; k < kSeedCandidates; ++k) {
    auto f = flood(seeds[k], r, false);
    const size_t c =
        static_cast<size_t>(std::count(f.begin(), f.end(), 1));
    if (c > best) { post = std::move(f); seed = seeds[k]; best = c; }
    if (static_cast<double>(c) >= nn * kMainMinFrac) break;
  }
  build_radj();
  auto pre = flood(seed, r, true);
  auto res = reach_.emplace(mi, std::make_pair(std::move(pre),
                                               std::move(post)));
  return res.first->second;
}

int PathEngine::snap(double lat, double lon, int mi, int role,
                     double* d_out) const {
  const PathRule& r = kRules[mi];
  const double dlat = kSnapRadiusM / 111320.0;
  const double dlon =
      dlat / std::max(0.2, std::cos(lat * M_PI / 180.0));
  std::vector<std::pair<double, uint32_t>> cands;
  for (size_t n = 0; n < node_lat_.size(); ++n) {
    const double y = node_lat_[n] / 1e6;
    if (y < lat - dlat || y > lat + dlat) continue;
    const double x = node_lon_[n] / 1e6;
    if (x < lon - dlon || x > lon + dlon) continue;
    const double d = hav_m(lon, lat, x, y);
    if (d >= kSnapRadiusM) continue;
    for (uint32_t a = adj_off_[n]; a < adj_off_[n + 1]; ++a) {
      const uint32_t ei = adj_flat_[a];
      if (legal(ei & 0x7FFFFFFFu, (ei & 0x80000000u) != 0, r)) {
        cands.emplace_back(d, static_cast<uint32_t>(n));
        break;
      }
    }
  }
  if (cands.empty()) {
    if (d_out) *d_out = 0.0;
    return -1;
  }
  std::sort(cands.begin(), cands.end());
  const auto& sets = reach_sets(mi, r);
  const auto& screen = role == 0 ? sets.first : sets.second;
  for (const auto& [d, n] : cands) {
    if (screen[n]) {
      if (d_out) *d_out = d;
      return static_cast<int>(n);
    }
  }
  // every in-radius node is pocketed — fall back to the nearest legal
  // one so intra-island trips still route (oracle: routegraph.snap)
  if (d_out) *d_out = cands.front().first;
  return static_cast<int>(cands.front().second);
}

PathResult PathEngine::query(double olat, double olon, double dlat,
                             double dlon, const std::string& mode) const {
  return route(olat, olon, dlat, dlon, mode_index(mode), nullptr);
}

std::vector<PathResult> PathEngine::alternatives(
    double olat, double olon, double dlat, double dlon,
    const std::string& mode, int max_alts) const {
  const int mi = mode_index(mode);
  PathResult first = route(olat, olon, dlat, dlon, mi, nullptr);
  std::vector<PathResult> out;
  out.push_back(std::move(first));
  if (!out[0].ok || max_alts <= 0) return out;

  std::unordered_set<uint32_t> accepted(out[0].edge_ids.begin(),
                                        out[0].edge_ids.end());
  std::unordered_set<uint32_t> taxed(accepted);
  std::vector<double> tax;
  for (int attempts = 0;
       static_cast<int>(out.size()) < 1 + max_alts &&
       attempts < kAltMaxAttempts;
       ++attempts) {
    if (tax.size() != e_u_.size()) tax.assign(e_u_.size(), 1.0);
    for (const uint32_t e : taxed) tax[e] = kAltTax;
    PathResult cand = route(olat, olon, dlat, dlon, mi, &tax);
    if (!cand.ok) break;
    const std::unordered_set<uint32_t> cids(cand.edge_ids.begin(),
                                          cand.edge_ids.end());
    bool all_taxed = !cids.empty();
    for (const uint32_t e : cids)
      if (!taxed.count(e)) { all_taxed = false; break; }
    if (all_taxed) break;        // penalty moved nothing — no alt exists
    double shared = 0.0;
    for (const uint32_t e : cids)
      if (accepted.count(e)) shared += e_len_[e];
    if (cand.distance_m > 0.0 &&
        shared / cand.distance_m < kAltMaxShared) {
      accepted.insert(cids.begin(), cids.end());
      out.push_back(std::move(cand));
    }
    taxed.insert(cids.begin(), cids.end());
  }
  return out;
}

PathResult PathEngine::route(double olat, double olon, double dlat,
                             double dlon, int mi,
                             const std::vector<double>* tax) const {
  // one shared hold for the whole solve: the conc table is stable for
  // the entire A* while a reprice swaps epochs only between solves
  std::shared_lock<std::shared_mutex> conc_lk(conc_mtx_);
  PathResult res;
  const PathRule& rl = kRules[mi];
  const double ve = kModeVE[mi], me = kModeME[mi];

  double sd = 0.0, td = 0.0;
  const int s = snap(olat, olon, mi, 0, &sd);
  const int t = snap(dlat, dlon, mi, 1, &td);
  res.snap_from_m = sd;
  res.snap_to_m = td;
  if (s < 0 || t < 0) {
    res.error = "no graph node near endpoint";
    return res;
  }

  // admissible h: gc dist * cheapest dose/m achievable — evaluated at
  // the state's head node, same bound as the node-state form
  const double h_rate = (field_mean_ > 0 && min_conc_ > 0)
                            ? min_conc_ * me * (ve / 1000.0) * (0.06 / 250.0)
                            : 0.0;
  auto h = [&](uint32_t n) {
    return hav_m(node_lon_[n] / 1e6, node_lat_[n] / 1e6, dlon, dlat) *
           h_rate;
  };
  auto head = [&](uint32_t sid) {  // node a directed-edge state ends on
    const uint32_t e = sid >> 1;
    return (sid & 1) ? e_u_[e] : e_v_[e];
  };

  // directed-edge-state A* — sid = (e << 1) | rev. Turn bans key on
  // the arrival edge; a node-settled search could strand a legal
  // continuation behind a cheap but banned incoming move. s == t
  // leaves the search empty → zero-edge path (same as the oracle).
  const size_t ns = e_u_.size() * 2;
  std::vector<double> gs(ns, std::numeric_limits<double>::infinity());
  std::vector<int32_t> par(ns, -1);
  std::vector<char> settled(ns, 0);
  using QI = std::tuple<double, double, uint32_t>;   // (f, g, sid)
  std::priority_queue<QI, std::vector<QI>, std::greater<QI>> pq;
  int64_t end_sid = -1;
  if (s != t) {
    for (uint32_t a = adj_off_[s]; a < adj_off_[s + 1]; ++a) {
      const uint32_t ei = adj_flat_[a];
      const bool rev = (ei & 0x80000000u) != 0;
      const uint32_t e = ei & 0x7FFFFFFFu;
      if (!legal(e, rev, rl)) continue;
      const double sp = mode_speed(e, rl);
      const double rate =
          conc(e) * me * (ve / 1000.0) * (0.06 / sp);
      const double t0 = tax ? (*tax)[e] : 1.0;
      const uint32_t sid = (e << 1) | (rev ? 1u : 0u);
      const double ng = rate * e_len_[e] * t0;
      gs[sid] = ng;
      pq.emplace(ng + h(head(sid)), ng, sid);
    }
  }
  while (!pq.empty()) {
    const auto [f, gc, sid] = pq.top();
    pq.pop();
    if (settled[sid]) continue;
    settled[sid] = 1;
    const uint32_t e = sid >> 1;
    const bool rev = (sid & 1) != 0;
    const uint32_t n = rev ? e_u_[e] : e_v_[e];
    if (static_cast<int>(n) == t) { end_sid = sid; break; }
    const uint32_t d_raw = rev ? (e | 0x80000000u) : e;
    const auto bit = bans_.find((static_cast<uint64_t>(d_raw) << 32) |
                                static_cast<uint64_t>(n));
    for (uint32_t a = adj_off_[n]; a < adj_off_[n + 1]; ++a) {
      const uint32_t ei = adj_flat_[a];
      const bool rev2 = (ei & 0x80000000u) != 0;
      const uint32_t e2 = ei & 0x7FFFFFFFu;
      if (bit != bans_.end()) {
        const auto oi = bit->second.find(ei);
        if (oi != bit->second.end() && (oi->second & rl.turn_mask))
          continue;                    // banned turn
      }
      if (!legal(e2, rev2, rl)) continue;
      const double sp = mode_speed(e2, rl);
      const double rate =
          conc(e2) * me * (ve / 1000.0) * (0.06 / sp);
      // diversity pass multiplier — raises real edge costs only;
      // admissibility of h is unaffected (tax >= 1 can never go below
      // the unconstrained optimum h estimates)
      const double tt = tax ? (*tax)[e2] : 1.0;
      const double ng = gc + rate * e_len_[e2] * tt;
      const uint32_t sid2 = (e2 << 1) | (rev2 ? 1u : 0u);
      if (ng < gs[sid2] - 1e-9) {
        gs[sid2] = ng;
        par[sid2] = static_cast<int32_t>(sid);
        pq.emplace(ng + h(head(sid2)), ng, sid2);
      }
    }
  }
  if (end_sid < 0 && s != t) {
    res.error = "no path in graph";
    return res;
  }

  // unwind the directed-edge chain
  std::vector<std::pair<uint32_t, bool>> chain;
  for (int64_t sid = end_sid; sid >= 0; sid = par[sid]) {
    chain.emplace_back(static_cast<uint32_t>(sid >> 1), (sid & 1) != 0);
  }
  std::reverse(chain.begin(), chain.end());

  res.ok = true;
  res.edges = static_cast<int>(chain.size());
  std::unordered_set<std::string> name_set;
  for (const auto& [e, rev] : chain) {
    res.edge_ids.push_back(e);
    res.edge_reversed.push_back(rev ? 1 : 0);
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
    res.dose_ug += conc(e) * me * (ve / 1000.0) * t_min;
    res.distance_m += ln;
    res.duration_s += t_min * 60.0;
    int32_t nm = e_nm_[e];
    if (nm) {
      nm -= 1;  // stored as idx+1
      // ordered-unique (parity oracle): first-appearance order,
      // leave/rejoin repeats skipped — the corridor list reads like
      // the turn sequence
      if (nm >= 0 && static_cast<size_t>(nm) < names_.size() &&
          !name_set.count(names_[nm])) {
        name_set.insert(names_[nm]);
        res.names.push_back(names_[nm]);
      }
    }
  }
  if (res.names.size() > 12) res.names.resize(12);
  return res;
}

}  // namespace alive
