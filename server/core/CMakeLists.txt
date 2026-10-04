cmake_minimum_required(VERSION 3.18)
project(alive_core LANGUAGES CXX)

if(NOT CMAKE_BUILD_TYPE)
  set(CMAKE_BUILD_TYPE Release CACHE STRING "" FORCE)
endif()

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

option(ALIVE_CORE_WITH_EIGEN "Enable Eigen kernels (Phase-5 kriging)" OFF)

find_package(Python3 REQUIRED COMPONENTS Interpreter Development.Module)

# pybind11 via FetchContent (pip is PEP-668-blocked on the build box)
include(FetchContent)
FetchContent_Declare(
  pybind11
  GIT_REPOSITORY https://github.com/pybind/pybind11.git
  GIT_TAG v2.13.6
  GIT_SHALLOW TRUE)
FetchContent_MakeAvailable(pybind11)

# ASCII-fold table generated with the same Python/unicodedata that runs the
# parity tests, so C++ normalization is bit-identical to alive_core_ref.py
set(GENERATED_DIR ${CMAKE_BINARY_DIR}/generated)
file(MAKE_DIRECTORY ${GENERATED_DIR})
execute_process(
  COMMAND ${Python3_EXECUTABLE} ${CMAKE_CURRENT_SOURCE_DIR}/tools/gen_fold_table.py
          ${GENERATED_DIR}/fold_table.inc
  RESULT_VARIABLE _gen_rc
  OUTPUT_VARIABLE _gen_out
  ERROR_VARIABLE _gen_err)
if(NOT _gen_rc EQUAL 0)
  message(FATAL_ERROR "fold-table generation failed: ${_gen_err}")
endif()
message(STATUS "${_gen_out}")

# Per-mode emission-factor table resolved through server/emissions.py's
# own chain (tools/gen_ef_table.py) — the C++ lookup can't drift from the
# production factors; parity tests assert the result to 1e-9.
execute_process(
  COMMAND ${Python3_EXECUTABLE} ${CMAKE_CURRENT_SOURCE_DIR}/tools/gen_ef_table.py
          ${GENERATED_DIR}/ef_table.inc
  RESULT_VARIABLE _ef_rc
  OUTPUT_VARIABLE _ef_out
  ERROR_VARIABLE _ef_err)
if(NOT _ef_rc EQUAL 0)
  message(FATAL_ERROR "ef-table generation failed: ${_ef_err}")
endif()
message(STATUS "${_ef_out}")

if(ALIVE_CORE_WITH_EIGEN)
  # Eigen (header-only) via FetchContent — same PEP-668 constraint as pybind11
  FetchContent_Declare(
    eigen
    GIT_REPOSITORY https://gitlab.com/libeigen/eigen.git
    GIT_TAG 3.4.0
    GIT_SHALLOW TRUE)
  FetchContent_GetProperties(eigen)
  if(NOT eigen_POPULATED)
    FetchContent_Populate(eigen)
  endif()
endif()

pybind11_add_module(alive_core
  bindings.cpp
  src/search.cpp
  src/field.cpp
  src/emission.cpp
  src/path.cpp
  $<$<BOOL:${ALIVE_CORE_WITH_EIGEN}>:src/krige.cpp>
  $<$<BOOL:${ALIVE_CORE_WITH_EIGEN}>:src/bindings_krige.cpp>)

target_include_directories(alive_core PRIVATE
  ${CMAKE_CURRENT_SOURCE_DIR}/include
  ${GENERATED_DIR}
  $<$<BOOL:${ALIVE_CORE_WITH_EIGEN}>:${eigen_SOURCE_DIR}>)

target_compile_definitions(alive_core PRIVATE
  $<$<BOOL:${ALIVE_CORE_WITH_EIGEN}>:ALIVE_CORE_WITH_EIGEN>)

# Release already carries -O3; make it explicit for non-default build types.
target_compile_options(alive_core PRIVATE
  $<$<CONFIG:Release>:-O3>
  -fno-fast-math   # parity oracle asserts exact-order/scores to 1e-9
  -Wall -Wextra)

set_target_properties(alive_core PROPERTIES
  LIBRARY_OUTPUT_DIRECTORY ${CMAKE_BINARY_DIR})
