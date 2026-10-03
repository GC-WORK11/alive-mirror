// pybind11 registration TU for the Phase-5 kriging kernels.
//
// This file deliberately has no PYBIND11_MODULE of its own — bindings.cpp is
// owned by another lane. The integrator wires it in with two additions:
//
//   1) in bindings.cpp, above PYBIND11_MODULE:
//        namespace alive { void register_krige(pybind11::module_& m); }
//   2) inside PYBIND11_MODULE(alive_core, m), after the existing defs:
//        alive::register_krige(m);
//
// and adds `src/krige.cpp src/bindings_krige.cpp` plus the Eigen include dir
// to the pybind11_add_module() call in CMakeLists.txt (see
// ALIVE_CORE_WITH_EIGEN there).
//
// Python surface (mirrors server/krige.py semantics + universal extension):
//
//   p = alive_core.KrigeParams()            # defaults == krige.py constants
//   p.legacy_variance = True                # False -> corrected sigma
//   kf = alive_core.KrigeField()
//   ok = kf.fit(lats, lons, vals)           # ordinary, params optional
//   ok = kf.fit_universal(lats, lons, vals, drift_rows)   # n x p drift
//   mu, sd = kf.estimate(lat, lon)          # None when unfitted
//   mu, sd = kf.estimate(lat, lon, f0)      # universal: drift at target
//   w = kf.weights(lat, lon, f0)            # solved [w|lam] for tests

#include <pybind11/pybind11.h>
#include <pybind11/stl.h>

#include <optional>
#include <utility>
#include <vector>

#include "alive/krige.hpp"

namespace py = pybind11;

namespace alive {

void register_krige(py::module_& m) {
  py::class_<KrigeParams>(m, "KrigeParams")
      .def(py::init<>())
      .def_readwrite("ky", &KrigeParams::ky)
      .def_readwrite("kx", &KrigeParams::kx)
      .def_readwrite("range_km", &KrigeParams::range_km)
      .def_readwrite("nugget_frac", &KrigeParams::nugget_frac)
      .def_readwrite("min_samples", &KrigeParams::min_samples)
      .def_readwrite("sill_floor", &KrigeParams::sill_floor)
      .def_readwrite("legacy_variance", &KrigeParams::legacy_variance);

  py::class_<KrigeField>(m, "KrigeField")
      .def(py::init<>())
      .def("fit", &KrigeField::fit, py::arg("lat"), py::arg("lon"),
           py::arg("z"), py::arg("params") = KrigeParams{})
      .def("fit_universal", &KrigeField::fit_universal, py::arg("lat"),
           py::arg("lon"), py::arg("z"), py::arg("drift"),
           py::arg("params") = KrigeParams{})
      .def("estimate", &KrigeField::estimate, py::arg("lat"), py::arg("lon"),
           py::arg("drift") = std::vector<double>{})
      .def("weights", &KrigeField::weights, py::arg("lat"), py::arg("lon"),
           py::arg("drift") = std::vector<double>{})
      .def("fitted", &KrigeField::fitted)
      .def("n", &KrigeField::n)
      .def("n_drift", &KrigeField::n_drift)
      .def("sill", &KrigeField::sill)
      .def("nugget", &KrigeField::nugget)
      .def("range_km", &KrigeField::range_km);
}

}  // namespace alive
