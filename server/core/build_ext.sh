#!/usr/bin/env bash
# build_ext.sh — build the alive_core pybind extension without cmake.
#
# CMakeLists.txt is the canonical recipe (pybind11 via FetchContent, Eigen
# optional). Some build boxes (macOS VM snapshots) have no cmake; this
# mirrors the same sources/flags/includes through a direct compiler call.
#
#   usage: server/core/build_ext.sh [python]   (default: ../.venv312/bin/python)
#
# Layout produced (gitignored): build312/generated/*.inc +
# build312/alive_core.cpython-312-*.so
set -euo pipefail
cd "$(dirname "$0")"

PY="${1:-$(pwd)/../.venv312/bin/python}"
[ -x "$PY" ] || PY="python3"
PYVER=$("$PY" -c 'import sys; print(f"{sys.version_info.major}{sys.version_info.minor}")')
BUILD="build312"
GEN="$BUILD/generated"
mkdir -p "$GEN"

"$PY" -c 'import pybind11' 2>/dev/null || "$PY" -m pip install pybind11
PYBIND_INC=$("$PY" -c 'import pybind11; print(pybind11.get_include())')
PYINC=$("$PY" -c 'import sysconfig; print(sysconfig.get_paths()["include"])')

# generated tables — same generators CMakeLists invokes (bit-identical
# parity with alive_core_ref.py and server/emissions.py)
"$PY" tools/gen_fold_table.py "$GEN/fold_table.inc"
"$PY" tools/gen_ef_table.py "$GEN/ef_table.inc"

CXX="${CXX:-c++}"
SO="$BUILD/alive_core.cpython-${PYVER}-$(uname -s | tr 'A-Z' 'a-z').so"
case "$(uname -s)" in
  Darwin) LINK="-bundle -undefined dynamic_lookup" ;;
  *)      LINK="-shared -fPIC" ;;
esac

# ALIVE_CORE_WITH_EIGEN mirror: krige.cpp + bindings_krige.cpp compile when
# Eigen headers are locatable (env EIGEN_INC, or common include roots).
# Eigen is header-only — no linking, just the include path. CI builds with
# -DALIVE_CORE_WITH_EIGEN=ON; without these sources alive_core.KrigeField
# doesn't exist and test_parity_krige fails.
KRIGE_SRCS=""
for EIGEN_INC in "${EIGEN_INC:-}" /opt/homebrew/include/eigen3 /usr/local/include/eigen3 /usr/include/eigen3; do
  if [ -n "$EIGEN_INC" ] && [ -f "$EIGEN_INC/Eigen/Dense" ]; then
    KRIGE_SRCS="src/krige.cpp src/bindings_krige.cpp"
    EIGEN_FLAGS="-I$EIGEN_INC -DALIVE_CORE_WITH_EIGEN"
    break
  fi
done
if [ -z "$KRIGE_SRCS" ]; then
  EIGEN_FLAGS=""
  echo "note: Eigen headers not found — building without krige (set EIGEN_INC to enable)"
fi

$CXX -std=c++20 -O3 -fno-fast-math -fPIC -Wall -Wextra \
  -Iinclude -I"$GEN" -I"$PYINC" -I"$PYBIND_INC" \
  $EIGEN_FLAGS \
  $LINK \
  bindings.cpp src/search.cpp src/field.cpp src/emission.cpp src/path.cpp \
  $KRIGE_SRCS \
  -o "$SO"
echo "built $SO"
