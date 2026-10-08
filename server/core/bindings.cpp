// pybind11 module `alive_core` — T1 search index binding.
//
//   idx = alive_core.SearchIndex(entries, aliases, w1, w2, w3, w4)
//     entries: list[dict] with keys id, display, aliases, category, lat, lon,
//              popularity
//     aliases: dict[str, list[list[str]]] — normalized token -> alternatives
//     (use alive_core_ref.load_aliases() so C++ and the oracle share a table)
//   idx.query(q, lat, lon, limit) -> list[dict]
//     lat/lon may be None (no distance term)

#include <pybind11/pybind11.h>
#include <pybind11/stl.h>

#include <array>
#include <limits>
#include <optional>
#include <string>
#include <utility>
#include <vector>

#include "alive/emission.hpp"
#include "alive/field.hpp"
#include "alive/path.hpp"
#include "alive/search.hpp"

namespace py = pybind11;
using namespace alive;

namespace {

SearchIndex make_index(const py::list& entries, const py::dict& aliases,
                       double w1, double w2, double w3, double w4,
                       double w5) {
  std::vector<Entry> es;
  es.reserve(entries.size());
  for (const auto& item : entries) {
    const py::dict d = item.cast<py::dict>();
    Entry e;
    e.id = d["id"].cast<uint32_t>();
    e.display = d["display"].cast<std::string>();
    e.category = d["category"].cast<std::string>();
    e.lat = d["lat"].cast<double>();
    e.lon = d["lon"].cast<double>();
    e.popularity = d["popularity"].cast<double>();
    if (d.contains("aliases"))
      for (const auto& a : d["aliases"].cast<py::list>())
        e.aliases.push_back(a.cast<std::string>());
    es.push_back(std::move(e));
  }

  AliasMap am;
  for (const auto& kv : aliases) {
    const std::string key = kv.first.cast<std::string>();
    std::vector<std::vector<std::string>> alts;
    for (const auto& alt : kv.second.cast<py::list>()) {
      std::vector<std::string> toks;
      for (const auto& t : alt.cast<py::list>())
        toks.push_back(t.cast<std::string>());
      alts.push_back(std::move(toks));
    }
    am.emplace(key, std::move(alts));
  }

  Weights w{w1, w2, w3, w4, w5};
  return SearchIndex(std::move(es), std::move(am), w);
}

py::list index_query(const SearchIndex& idx, const std::string& q,
                     const py::object& lat, const py::object& lon,
                     size_t limit) {
  std::optional<double> blat, blon;
  if (!lat.is_none()) blat = lat.cast<double>();
  if (!lon.is_none()) blon = lon.cast<double>();
  std::vector<Hit> hits;
  {
    py::gil_scoped_release rel;   // fuzzy scan over the whole index
    hits = idx.query(q, blat, blon, limit);
  }
  py::list out;
  for (const Hit& h : hits) {
    const Entry& e = idx.entry(h.eidx);
    py::dict r;
    r["id"] = e.id;
    r["display"] = e.display;
    r["category"] = e.category;
    r["lat"] = e.lat;
    r["lon"] = e.lon;
    r["score"] = h.score;
    r["cov"] = h.cov;
    r["fuzzy"] = h.fuzzy;
    out.append(std::move(r));
  }
  return out;
}

// --------------------------------------------------------------------------
// Phase 3 — field view + dose/emission integrators
// --------------------------------------------------------------------------

// --------------------------------------------------------------------------
// Path engine — least-inhalation routing over the packed ARG1 graph.
// Mirrors routegraph.py PyPathEngine's dict contract exactly.
// --------------------------------------------------------------------------

std::unique_ptr<PathEngine> make_path_engine(const py::bytes& blob) {
  const std::string buf = blob;   // py bytes -> std::string needs the GIL
  py::gil_scoped_release rel;     // ARG1 parse is pure C++
  return std::make_unique<PathEngine>(buf);
}

// field may be a FieldView (fast path — direct C++ value() calls) or any
// Python callable f(lat, lon) -> float|None (parity with the oracle).
// Returns the oracle's dict {"edges_priced", "field_mean"}.
py::dict path_reweight(PathEngine& eng, const py::object& field) {
  if (py::isinstance<FieldView>(field)) {
    const FieldView* fv = field.cast<const FieldView*>();
    // pure C++ sweep over ~1.2M edges — release the GIL or the whole
    // asyncio loop stalls for the duration of a reprice.
    py::gil_scoped_release rel;
    eng.reweight([fv](double lat, double lon) {
      return fv->value(lat, lon);
    });
  } else {
    // same sweep, but each edge callback re-enters Python to sample the
    // field — release for the sweep, re-acquire per callback.
    py::gil_scoped_release rel;
    eng.reweight([&field](double lat, double lon) -> std::optional<double> {
      py::gil_scoped_acquire acq;
      const py::object r = field(lat, lon);
      if (r.is_none()) return std::nullopt;
      return r.cast<double>();
    });
  }
  py::dict out;
  out["edges_priced"] = eng.edges_priced();
  out["field_mean"] = eng.field_mean();
  return out;
}

py::dict path_result_dict(const PathResult& r) {
  py::dict out;
  if (!r.ok) {
    out["error"] = r.error;
    return out;
  }
  py::list coords;
  for (size_t i = 0; i + 1 < r.coords.size(); i += 2) {
    py::list pt;
    pt.append(r.coords[i]);
    pt.append(r.coords[i + 1]);
    coords.append(std::move(pt));
  }
  py::dict geom;
  geom["type"] = "LineString";
  geom["coordinates"] = std::move(coords);
  out["geometry"] = std::move(geom);
  out["distance_m"] = r.distance_m;
  out["duration_s"] = r.duration_s;
  out["dose_ug"] = r.dose_ug;
  out["edges"] = r.edges;
  py::list ids, revs;
  for (const uint32_t e : r.edge_ids) ids.append(e);
  for (const char rev : r.edge_reversed) revs.append(rev != 0);
  out["edge_ids"] = std::move(ids);
  out["edge_reversed"] = std::move(revs);
  py::list names;
  for (const auto& n : r.names) names.append(n);
  out["names"] = std::move(names);
  py::dict snap;
  snap["from_m"] = r.snap_from_m;
  snap["to_m"] = r.snap_to_m;
  out["snap"] = std::move(snap);
  out["engine"] = "alive_core-path";
  return out;
}

py::dict path_query(PathEngine& eng, double olat, double olon, double dlat,
                    double dlon, const std::string& mode) {
  PathResult r;
  {
    py::gil_scoped_release rel;   // A* is pure C++ — let the loop run
    r = eng.query(olat, olon, dlat, dlon, mode);
  }
  return path_result_dict(r);
}

py::list path_alternatives(PathEngine& eng, double olat, double olon,
                           double dlat, double dlon,
                           const std::string& mode, int max_alts) {
  std::vector<PathResult> rs;
  {
    py::gil_scoped_release rel;
    rs = eng.alternatives(olat, olon, dlat, dlon, mode, max_alts);
  }
  py::list out;
  for (const PathResult& r : rs)
    out.append(path_result_dict(r));
  return out;
}

py::dict path_reach(PathEngine& eng, double lat, double lon,
                    const std::string& mode, double budget_ug,
                    int64_t max_states) {
  ReachResult r;
  {
    py::gil_scoped_release rel;   // bounded Dijkstra is pure C++
    r = eng.reach(lat, lon, mode, budget_ug, max_states);
  }
  py::dict out;
  if (!r.ok) {
    out["error"] = r.error;
    return out;
  }
  py::list ids;
  for (const uint32_t e : r.edge_ids) ids.append(e);
  out["edge_ids"] = std::move(ids);
  out["expanded"] = r.expanded;
  out["nodes"] = r.nodes;
  out["frontier_ug"] = r.frontier_ug;
  out["distance_m"] = r.distance_m;
  out["snap_m"] = r.snap_m;
  out["truncated"] = r.truncated;
  return out;
}

FieldView make_field_view(const py::list& rows, double coverage_km) {
  std::vector<FieldCell> cells;
  cells.reserve(rows.size());
  for (const auto& item : rows) {
    const py::sequence t = item.cast<py::sequence>();
    FieldCell c;
    c.lat = t[0].cast<double>();
    c.lon = t[1].cast<double>();
    c.pm25 = t[2].cast<double>();
    c.lo = t[3].cast<double>();
    c.hi = t[4].cast<double>();
    c.sigma = t[5].cast<double>();
    cells.push_back(c);
  }
  return FieldView(std::move(cells), coverage_km);
}

py::object field_value(const FieldView& fv, double lat, double lon,
                       const std::string& pollutant) {
  // the snapshot field is pm2.5-only (mirrors ref PyFieldView.value)
  if (pollutant != "pm2_5" && pollutant != "pm25") return py::none();
  const auto v = fv.value(lat, lon);
  return v ? py::float_(*v) : py::object(py::none());
}

py::object field_sigma(const FieldView& fv, double lat, double lon) {
  const auto v = fv.sigma(lat, lon);
  return v ? py::float_(*v) : py::object(py::none());
}

py::object field_band(const FieldView& fv, double lat, double lon) {
  const auto b = fv.band(lat, lon);
  if (!b) return py::none();
  return py::make_tuple((*b)[0], (*b)[1], (*b)[2]);
}

py::object field_nearest_cell(const FieldView& fv, double lat, double lon) {
  const long i = fv.nearest(lat, lon);
  if (i < 0) return py::none();
  const FieldCell& c = fv.cell((size_t)i);
  py::dict d;
  d["lat"] = c.lat;
  d["lon"] = c.lon;
  d["pm25"] = c.pm25;
  d["lo"] = c.lo;
  d["hi"] = c.hi;
  d["sigma"] = c.sigma;
  d["dist_km"] = cell_km(lat, lon, c.lat, c.lon);
  return d;
}

std::vector<std::pair<double, double>> parse_coords(const py::object& src) {
  // accepts [[lon, lat], ...] or {"coordinates": [[lon, lat], ...]}
  py::object seq = src;
  if (py::isinstance<py::dict>(src)) {
    const py::dict d = src.cast<py::dict>();
    if (!d.contains("coordinates")) return {};
    seq = d["coordinates"];
  }
  std::vector<std::pair<double, double>> coords;
  for (const auto& item : seq.cast<py::sequence>()) {
    const py::sequence t = item.cast<py::sequence>();
    coords.emplace_back(t[0].cast<double>(), t[1].cast<double>());
  }
  return coords;
}

py::list seg_samples_py(const py::object& coords, double duration_s,
                        double step_m) {
  const auto cs = parse_coords(coords);   // py objects — needs the GIL
  std::vector<SegSample> ss;
  {
    py::gil_scoped_release rel;
    ss = segment_samples(cs, duration_s, step_m);
  }
  py::list out;
  for (const SegSample& s : ss)
    out.append(py::make_tuple(s.lat, s.lon, s.seconds, s.dist_m));
  return out;
}

py::dict dose_py(const py::object& coords, const FieldView& field, double me,
                 double ve, double duration_s, double step_m) {
  const auto cs = parse_coords(coords);
  DoseResult r;
  {
    py::gil_scoped_release rel;
    r = integrate_dose(cs, field, me, ve, duration_s, step_m);
  }
  py::dict out;
  out["lo"] = r.lo ? py::float_(*r.lo) : py::object(py::none());
  out["mid"] = r.mid ? py::float_(*r.mid) : py::object(py::none());
  out["hi"] = r.hi ? py::float_(*r.hi) : py::object(py::none());
  out["coverage"] = r.coverage;
  out["n_samples"] = r.n_samples;
  out["n_hit"] = r.n_hit;
  out["dist_km"] = r.dist_km;
  return out;
}

// r5/core-cpp — tick-level series kernels (docs/plan/04 §5 contract).
double to_double_nan_none(const py::handle& h) {
  return h.is_none() ? std::numeric_limits<double>::quiet_NaN()
                     : h.cast<double>();
}

double dose_series_py(const py::object& pm25_obj, const py::object& dt_obj,
                      double ve_lpm, double me) {
  std::vector<double> pm;
  const py::sequence pm25 = pm25_obj.cast<py::sequence>();
  pm.reserve(pm25.size());
  for (const py::handle h : pm25) pm.push_back(to_double_nan_none(h));

  std::vector<double> dts;
  if (dt_obj.is_none()) {
    // oracle broadcasts dt=None to every sample -> all skipped -> 0.0
    dts.assign(pm.size(), std::numeric_limits<double>::quiet_NaN());
  } else if (PySequence_Check(dt_obj.ptr()) &&
             !py::isinstance<py::str>(dt_obj) &&
             !py::isinstance<py::bytes>(dt_obj)) {
    const py::sequence ds = dt_obj.cast<py::sequence>();
    dts.reserve(ds.size());
    for (const py::handle h : ds) dts.push_back(to_double_nan_none(h));
  } else {
    dts.assign(pm.size(), dt_obj.cast<double>());
  }
  py::gil_scoped_release rel;
  return dose_series(pm, dts, ve_lpm, me);
}

py::dict emission_g_km_py(const std::string& mode, double speed_kmh) {
  EmCurveResult r;
  if (!emission_g_km(mode, speed_kmh, r))
    throw py::value_error("unknown vehicle class: '" + mode + "'");
  auto band_t = [](const Band3& b) { return py::make_tuple(b.lo, b.mid, b.hi); };
  py::dict out;
  out["mode"] = r.mode;
  out["units"] = r.per_pkm ? "g/pkm" : "g/km";
  out["co2"] = band_t(r.pol[kCO2]);
  out["pm25"] = band_t(r.pol[kPM25]);
  out["nox"] = band_t(r.pol[kNOx]);
  if (r.occupancy > 0.0) out["occupancy"] = r.occupancy;
  return out;
}

int pol_index(const std::string& pol) {
  if (pol == "co2") return kCO2;
  if (pol == "pm25") return kPM25;
  if (pol == "nox") return kNOx;
  throw py::value_error("unknown pollutant: " + pol);
}

Band3 parse_band3(const py::object& src) {
  if (py::isinstance<py::dict>(src)) {
    const py::dict d = src.cast<py::dict>();
    return Band3{d["lo"].cast<double>(), d["mid"].cast<double>(),
                 d["hi"].cast<double>()};
  }
  const py::sequence t = src.cast<py::sequence>();
  return Band3{t[0].cast<double>(), t[1].cast<double>(), t[2].cast<double>()};
}

std::array<Band3, 3> parse_band_dict(const py::dict& d) {
  std::array<Band3, 3> out;
  out[kCO2] = parse_band3(d["co2"]);
  out[kPM25] = parse_band3(d["pm25"]);
  out[kNOx] = parse_band3(d["nox"]);
  return out;
}

std::array<double, 3> parse_mult_dict(const py::dict& d) {
  return {d["co2"].cast<double>(), d["pm25"].cast<double>(),
          d["nox"].cast<double>()};
}

py::dict emissions_py(const py::list& spans, const py::dict& ef_band,
                      const py::dict& idle_band, const py::dict& cold_mult,
                      const py::object& nx_band, double cold_km_done,
                      double occupancy) {
  std::vector<EmSpan> es;
  es.reserve(spans.size());
  for (const auto& item : spans) {
    const py::dict d = item.cast<py::dict>();
    EmSpan s;
    if (d.contains("dist_m") && !d["dist_m"].is_none())
      s.dist_m = d["dist_m"].cast<double>();
    if (d.contains("speed_mps") && !d["speed_mps"].is_none())
      s.speed_mps = d["speed_mps"].cast<double>();
    if (d.contains("moving"))
      s.moving = PyObject_IsTrue(d["moving"].ptr()) == 1;  // bool() semantics
    if (d.contains("dur_s") && !d["dur_s"].is_none()) {
      s.dur_s = d["dur_s"].cast<double>();
      s.has_dur = true;
    }
    es.push_back(s);
  }

  Band3 nx{0, 0, 0};
  if (!nx_band.is_none()) nx = parse_band3(nx_band);

  const auto efb = parse_band_dict(ef_band);
  const auto ib = parse_band_dict(idle_band);
  const auto cm = parse_mult_dict(cold_mult);
  EmissionResult r;
  {
    py::gil_scoped_release rel;
    r = integrate_emissions(es, efb, ib, cm, nx, cold_km_done, occupancy);
  }

  auto band_t = [](const Band3& b) { return py::make_tuple(b.lo, b.mid, b.hi); };
  auto mid_d = [](const double v[3]) {
    py::dict d;
    d["co2"] = v[kCO2];
    d["pm25"] = v[kPM25];
    d["nox"] = v[kNOx];
    return d;
  };
  py::dict out;
  out["co2_g"] = band_t(r.pol[kCO2]);
  out["pm25_g"] = band_t(r.pol[kPM25]);
  out["nox_g"] = band_t(r.pol[kNOx]);
  out["non_exhaust_pm10_g"] = band_t(r.nx_pm10);
  out["distance_km"] = r.distance_km;
  out["moving_mid_g"] = mid_d(r.moving_mid);
  out["idle_mid_g"] = mid_d(r.idle_mid);
  out["cold_extra_mid_g"] = mid_d(r.cold_extra_mid);
  return out;
}

}  // namespace

#ifdef ALIVE_CORE_WITH_EIGEN
namespace alive { void register_krige(pybind11::module_& m); }
#endif

PYBIND11_MODULE(alive_core, m) {
  m.doc() = "Alive C++ engine — T1 fuzzy place search index";

#ifdef ALIVE_CORE_WITH_EIGEN
  alive::register_krige(m);
#endif

  py::class_<SearchIndex>(m, "SearchIndex")
      .def(py::init(&make_index), py::arg("entries"), py::arg("aliases"),
           py::arg("w1") = 1.0, py::arg("w2") = 1.0, py::arg("w3") = 0.5,
           py::arg("w4") = 0.15, py::arg("w5") = 0.5)
      .def("query", &index_query, py::arg("q"), py::arg("lat") = py::none(),
           py::arg("lon") = py::none(), py::arg("limit") = 8)
      .def("__len__", &SearchIndex::size)
      .def("size", &SearchIndex::size);

  m.def("normalize", &alive::normalize, py::arg("s"));
  m.def("dl_distance", &alive::dl_distance, py::arg("a"), py::arg("b"),
        py::arg("bound") = 8);
  m.def("haversine_km", &alive::haversine_km, py::arg("lat1"), py::arg("lon1"),
        py::arg("lat2"), py::arg("lon2"));

  // -- Phase 3: field view + dose/emission integrators ----------------------
  //   fv = alive_core.FieldView(rows, coverage_km=1.0)
  //     rows: [(lat, lon, pm25, lo, hi, sigma)] — from
  //           alive_core_ref.field_rows(snapshot)
  py::class_<FieldView>(m, "FieldView")
      .def(py::init(&make_field_view), py::arg("rows"),
           py::arg("coverage_km") = kFieldCoverageKm)
      .def("value", &field_value, py::arg("lat"), py::arg("lon"),
           py::arg("pollutant") = "pm2_5")
      .def("sigma", &field_sigma, py::arg("lat"), py::arg("lon"))
      .def("band", &field_band, py::arg("lat"), py::arg("lon"))
      .def("nearest_cell", &field_nearest_cell, py::arg("lat"), py::arg("lon"))
      .def("__len__", &FieldView::size)
      .def("size", &FieldView::size)
      .def_property_readonly("coverage_km", &FieldView::coverage_km);

  m.def("segment_samples", &seg_samples_py, py::arg("coords"),
        py::arg("duration_s"), py::arg("step_m") = 250.0);
  m.def("integrate_dose", &dose_py, py::arg("coords"), py::arg("field"),
        py::arg("me"), py::arg("ve"), py::arg("duration_s"),
        py::arg("step_m") = 250.0);
  // -- r5/core-cpp: series kernels -------------------------------------
  //   alive_core.dose_series(pm25, dt_s, ventilation_lpm, microenv) -> µg
  //     pm25: [float|None] µg/m³ ticks; dt_s: seconds scalar or per-sample.
  //     exposure.dose accumulation semantics (skip/clamp/order).
  //   alive_core.emission_g_km(mode, speed_kmh) ->
  //     {co2,pm25,nox:(lo,mid,hi), "units", "mode", "occupancy"?}
  //     emissions.emission_factors band x speed_factor curve + widening.
  m.def("dose_series", &dose_series_py, py::arg("pm25"), py::arg("dt_s"),
        py::arg("ventilation_lpm"), py::arg("microenv"));
  m.def("emission_g_km", &emission_g_km_py, py::arg("mode"),
        py::arg("speed_kmh"));
  m.def(
      "emission_speed_factor",
      [](const std::string& pol, double v) {
        return emission_speed_factor(pol_index(pol), v);
      },
      py::arg("pol"), py::arg("v_mps"));
  m.def("integrate_emissions", &emissions_py, py::arg("spans"),
        py::arg("ef_band"), py::arg("idle_band"), py::arg("cold_mult"),
        py::arg("nx_band") = py::none(), py::arg("cold_km_done") = 0.0,
        py::arg("occupancy") = 1.0);

  // -- least-inhalation path engine ------------------------------------
  //   pe = alive_core.PathEngine(blob_bytes)  # ARG1 packed graph
  //   pe.reweight(field_view_or_callable)     # price edges by live field
  //   pe.query(olat, olon, dlat, dlon, mode) -> dict (same shape as
  //       routegraph.PyPathEngine.query)
  py::class_<PathEngine>(m, "PathEngine")
      .def(py::init(&make_path_engine), py::arg("blob"))
      .def("reweight", &path_reweight, py::arg("field"))
      .def("query", &path_query, py::arg("olat"), py::arg("olon"),
           py::arg("dlat"), py::arg("dlon"), py::arg("mode") = "car")
      .def("reach", &path_reach, py::arg("lat"), py::arg("lon"),
           py::arg("mode") = "car", py::arg("budget_ug") = 0.0,
           py::arg("max_states") = PathEngine::kReachMaxStates)
      .def("alternatives", &path_alternatives, py::arg("olat"),
           py::arg("olon"), py::arg("dlat"), py::arg("dlon"),
           py::arg("mode") = "car", py::arg("max_alts") = 2)
      .def("n_nodes", &PathEngine::n_nodes)
      .def("n_edges", &PathEngine::n_edges)
      .def("edges_priced", &PathEngine::edges_priced)
      .def("field_mean", &PathEngine::field_mean);
}
