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

#include <optional>
#include <string>
#include <vector>

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

}  // namespace

PYBIND11_MODULE(alive_core, m) {
  m.doc() = "ALive-108 C++ engine — T1 fuzzy place search index";

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
}
