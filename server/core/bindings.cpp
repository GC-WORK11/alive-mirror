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
#include <optional>
#include <string>
#include <utility>
#include <vector>

#include "alive/emission.hpp"
#include "alive/field.hpp"
#include "alive/search.hpp"

namespace py = pybind11;
using namespace alive;

namespace {

SearchIndex make_index(const py::list& entries, const py::dict& aliases,
                       double w1, double w2, double w3, double w4) {
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

  Weights w{w1, w2, w3, w4};
  return SearchIndex(std::move(es), std::move(am), w);
}

py::list index_query(const SearchIndex& idx, const std::string& q,
                     const py::object& lat, const py::object& lon,
                     size_t limit) {
  std::optional<double> blat, blon;
  if (!lat.is_none()) blat = lat.cast<double>();
  if (!lon.is_none()) blon = lon.cast<double>();
  py::list out;
  for (const Hit& h : idx.query(q, blat, blon, limit)) {
    const Entry& e = idx.entry(h.eidx);
    py::dict r;
    r["id"] = e.id;
    r["display"] = e.display;
    r["category"] = e.category;
    r["lat"] = e.lat;
    r["lon"] = e.lon;
    r["score"] = h.score;
    out.append(std::move(r));
  }
  return out;
}

// --------------------------------------------------------------------------
// Phase 3 — field view + dose/emission integrators
// --------------------------------------------------------------------------

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
  py::list out;
  for (const SegSample& s :
       segment_samples(parse_coords(coords), duration_s, step_m))
    out.append(py::make_tuple(s.lat, s.lon, s.seconds, s.dist_m));
  return out;
}

py::dict dose_py(const py::object& coords, const FieldView& field, double me,
                 double ve, double duration_s, double step_m) {
  const DoseResult r =
      integrate_dose(parse_coords(coords), field, me, ve, duration_s, step_m);
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

  const EmissionResult r =
      integrate_emissions(es, parse_band_dict(ef_band),
                          parse_band_dict(idle_band),
                          parse_mult_dict(cold_mult), nx, cold_km_done,
                          occupancy);

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
  m.doc() = "ALive-108 C++ engine — T1 fuzzy place search index";

#ifdef ALIVE_CORE_WITH_EIGEN
  alive::register_krige(m);
#endif

  py::class_<SearchIndex>(m, "SearchIndex")
      .def(py::init(&make_index), py::arg("entries"), py::arg("aliases"),
           py::arg("w1") = 1.0, py::arg("w2") = 1.0, py::arg("w3") = 0.5,
           py::arg("w4") = 0.15)
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
}
