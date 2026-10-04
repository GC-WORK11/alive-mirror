// ALive-108 — least-inhalation path engine (alive_core.PathEngine).
//
// Query semantics kept bit-identical with server/routegraph.py
// PyPathEngine (the parity oracle). Any change must be mirrored there.
//
// Edge cost is inhaled PM2.5 dose for traversing the edge in the
// queried mode:  dose_ug/m = conc * me_mode * uplift_hw * (ve/1000)
// * (0.06/sp_kmh). Dose minimization physically penalizes detours —
// extra metres are extra breaths — so no distance penalty term is
// needed (and none is added: the cost is dose, nothing else).
//
// Binary input: ARG2 packed graph (tools/build_route_graph.py)
//   <4s4I header | <4i bbox | nodes <2i (lon,lat e6) | names | edges
//   <IIfIHBbBiBB 27B (+u8 access-deny) | bans <I count then <IIIB
//   triples (dir-in | via node | dir-out | u8 mode mask) | pts i32
//   stream: per edge 2 abs ints then one packed i16-pair int per
//   delta; pts_off indexes int32 slots. ARG1 (26B edges, no bans) is
//   still read — access degrades to the class-level deny lists.
//
// Search runs over directed-edge states (e<<1 | rev): turn bans key
// on the arrival edge, so a node-settled A* could strand legal
// continuations behind a cheap but banned incoming move.
//
// A* over the CSR adjacency built at init; heuristic =
// gc-distance * min_edge_conc * me * ve/1000 * 0.06/250 — a strict
// lower bound on achievable dose (admissible).

#pragma once

#include <cstdint>
#include <functional>
#include <optional>
#include <string>
#include <unordered_map>
#include <vector>

namespace alive {

// Called once per sample point; returns the live field concentration
// (µg/m³) or nullopt when the field has no value there.
using FieldSampler = std::function<std::optional<double>(double lat,
                                                         double lon)>;

struct PathResult {
  bool ok = false;
  std::string error;                    // set when !ok
  std::vector<double> coords;           // [lon,lat] flattened
  double distance_m = 0.0;
  double duration_s = 0.0;
  double dose_ug = 0.0;
  int edges = 0;
  std::vector<uint32_t> edge_ids;       // travelled edge ids (31-bit)
  std::vector<char> edge_reversed;      // 1 = traversed v->u
  std::vector<std::string> names;       // distinct road names, in order
  double snap_from_m = 0.0;
  double snap_to_m = 0.0;
};

struct PathRule {
  // highway classes this mode may not use (bitmask, bit i = hw code i)
  uint32_t deny_mask = 0;
  bool oneway = false;                  // respect OSM oneway
  double speed_cap_kmh = 0.0;           // <=0 means no cap
  double speed_const_kmh = 0.0;         // >0 overrides the stored speed
  uint8_t acc_mask = 0;                 // e_acc bits that deny this mode
  uint8_t turn_mask = 0;                // ban mode-mask bit that applies
};

class PathEngine {
 public:
  explicit PathEngine(const std::string& blob);

  // Price every in-field edge with the sampler's mean over <=5
  // evenly-spaced polyline points; out-of-field / unsampled edges get
  // the computed field mean (honest — never free).
  void reweight(const FieldSampler& sampler);
  double field_mean() const { return field_mean_; }
  int edges_priced() const { return edges_priced_; }

  // Least-dose path for `mode` (car/car_open/cab/auto/bike/cycle/walk).
  PathResult query(double olat, double olon, double dlat, double dlon,
                   const std::string& mode) const;

  // Optimum plus up to `max_alts` honest alternative corridors: each
  // next solve taxes every edge of every corridor found so far by
  // kAltTax (edge-penalty diversity pass); a candidate sharing >=
  // kAltMaxShared of its length with accepted corridors is rejected as
  // a variant. Parity oracle: routegraph.py PyPathEngine.alternatives.
  std::vector<PathResult> alternatives(double olat, double olon,
                                       double dlat, double dlon,
                                       const std::string& mode,
                                       int max_alts = 2) const;

  static constexpr double kAltTax = 1.5;
  static constexpr int kAltMaxAttempts = 4;
  static constexpr double kAltMaxShared = 0.85;

  size_t n_nodes() const { return node_lon_.size(); }
  size_t n_edges() const { return e_u_.size(); }

 private:
  // decoded arrays
  std::vector<int32_t> node_lon_, node_lat_;
  std::vector<std::string> names_;
  std::vector<uint32_t> e_u_, e_v_, e_pts_off_;
  std::vector<float> e_len_;
  std::vector<uint16_t> e_pts_n_;
  std::vector<uint8_t> e_hw_, e_sp_, e_field_;
  std::vector<int8_t> e_ow_;
  std::vector<int32_t> e_nm_;
  std::vector<uint8_t> e_acc_;          // per-edge access-deny bits
  std::vector<int32_t> pts_;            // delta-packed polyline stream
  int32_t bbox_[4] = {0, 0, 0, 0};

  // ARG2 turn bans: (in_dir_raw << 32 | via node) -> {out_dir_raw: mask}
  std::unordered_map<uint64_t, std::unordered_map<uint32_t, uint8_t>>
      bans_;

  // CSR adjacency: edge id | 0x80000000 = traverse v->u
  std::vector<uint32_t> adj_flat_;
  std::vector<uint32_t> adj_off_;       // size n_nodes+1

  // snap connectivity screen: radj = reverse CSR (dirs whose head is
  // the node), reach_[mi] = {pre, post} membership bitsets built
  // lazily per mode — routegraph.py _reach_sets is the oracle
  mutable std::vector<uint32_t> radj_flat_, radj_off_;
  mutable std::unordered_map<
      int, std::pair<std::vector<uint8_t>, std::vector<uint8_t>>>
      reach_;

  // reweight state
  std::vector<float> conc_;             // per-edge concentration
  std::vector<char> conc_set_;
  double field_mean_ = 0.0;
  double min_conc_ = 0.0;
  int edges_priced_ = 0;

  static const PathRule& rule(const std::string& mode);
  PathResult route(double olat, double olon, double dlat, double dlon,
                   int mi, const std::vector<double>* tax) const;
  std::vector<std::pair<double, double>> edge_pts(uint32_t i) const;
  double conc(uint32_t e) const;
  bool legal(uint32_t e, bool rev, const PathRule& r) const;
  // role 0 = origin (needs pre — can reach the main net),
  // role 1 = destination (needs post — reachable from it)
  int snap(double lat, double lon, int mi, int role,
           double* d_out) const;
  void build_radj() const;
  std::vector<uint8_t> flood(uint32_t seed, const PathRule& r,
                             bool reverse) const;
  const std::pair<std::vector<uint8_t>, std::vector<uint8_t>>&
      reach_sets(int mi, const PathRule& r) const;
  double mode_speed(uint32_t e, const PathRule& r) const;
};

}  // namespace alive
