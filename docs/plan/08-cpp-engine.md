# 08 · `alive_core` — the C++ engine

## Why C++, honestly
User-perceived speed today is dominated by network calls (Amazon/OSRM/Photon round trips), not our Python. C++ is used where the work is ours and CPU-bound, and where it unlocks something Python can't do in budget:
1. **Search index (T1)** — fuzzy prefix search over ~1M Delhi-NCR names within ~1 ms. Python can't do typo-tolerant search at this size at keystroke rate.
2. **Field engine** — sample the H3/grid field along routes (thousands of points per `/plan` × 8 options) and integrate dose with bands.
3. **Emission integrator** — speed-curve + idle + cold-start over route spans or trip traces.
4. **Air-index builder kernels** — kriging matrix solve and grid prediction (Eigen) every 15 min.
We publish before/after numbers and only claim measured speedups.

## Layout
```
server/core/
  CMakeLists.txt          # C++20, -O3, pybind11, Eigen (header-only)
  include/alive/*.hpp
  src/search.cpp          # index build + query
  src/field.cpp           # grid sampling, polyline densify, dose integral
  src/emission.cpp        # ef(v), idle, cold-start, integrate
  src/krige.cpp           # variogram fit + ordinary/regression kriging
  bindings.cpp            # pybind11 module `alive_core`
  bench/                  # google-benchmark-style microbenchmarks + Python comparison script
  tests/                  # Catch2 unit tests; parity tests vs Python reference
```
Built inside the Docker image (CodeBuild); Python fallback implementations stay in place and are used if the import fails, so a build problem can never take the API down.

## Search index design
- Corpus: OSM Delhi-NCR extract (Geofabrik/BBBike or Overpass) — POIs, named buildings, streets, `addr:*` blocks; + Amazon results cached by place id; + gazetteer. Each entry: id, display name, aliases, category, lat/lon, popularity.
- Normalization: lowercase, ASCII-fold, strip punctuation, Hinglish alias table, common abbreviations (cp, gk, ncr, sec → sector, ph → phase).
- Structures: sorted token array with prefix ranges (binary search) + trigram inverted index for fuzzy candidates; Damerau-Levenshtein ≤1 for tokens ≥4 chars, ≤2 for ≥8.
- Scoring: `prefix_quality · w1 + token_coverage · w2 + popularity · w3 − log(1 + distance_km) · w4`.
- Memory budget: <300 MB for 1M entries. Build at container start from a prebuilt binary blob in S3 (mmap-able).

## Benchmark protocol
- Fixed corpus + 10k recorded queries (prefixes of real Delhi place names, with typos).
- Report p50/p95/p99 per query, build time, RSS — C++ vs the best Python baseline (current gazetteer search; `rapidfuzz` for fuzzy).
- Field/dose: 10k random Delhi routes, 8 modes each — wall time C++ vs current `exposure.py`.
- Results committed to `docs/plan/bench-results.md` and shown in the video.

## Parity and safety
- Every C++ function has a Python reference; CI asserts equality (1e-9 relative) on random inputs.
- Fuzz the search parser with random UTF-8 (libFuzzer locally).
