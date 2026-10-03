# Benchmark results — alive_core C++ vs Python reference

Protocol per docs/plan/08: fixed corpus, 10k recorded queries; p50/p95/p99,
build time, RSS. Only measured numbers go here — no estimates.

## Search index (T1)

Corpus: `Mobile/assets/delhi-gazetteer.json` — 26,545 real Delhi-NCR places.
Queries: 10k generated recorded-style (prefixes of gazetteer names + injected
typos, seed 108), geo bias at Connaught Place (28.6139, 77.2090), limit 10.
Each implementation benched in a fresh subprocess (`server/core/bench/bench_search.py`);
RSS = VmRSS delta at index build (peak process RSS in parentheses).

| Build | Corpus | Query | p50 | p95 | p99 | RSS |
|---|---|---|---|---|---|---|
| C++ `alive_core` (g++ 13, -O3) | 26,545 entries | 10k prefix+typo | 0.189 ms | 0.723 ms | 1.227 ms | +8.8 MB (peak 53.8 MB) |
| Python ref (`alive_core_ref.py`) | 26,545 entries | 10k prefix+typo | 16.623 ms | 72.249 ms | 125.168 ms | +1.9 MB (peak 45.0 MB) |

Index build time: C++ 45.2 ms vs Python 142.1 ms. Speedup (Python/C++):
~88x p50, ~100x p95, ~102x p99. Result parity asserted bit-exact (order +
scores to 1e-9) by `server/tests/test_core_parity.py`.

## Field / dose integration

| Build | Routes | Modes | Wall time | vs Python |
|---|---|---|---|---|
| pending | | | | |

## Kriging kernels

| Build | Stations | Grid | Wall time | vs Python |
|---|---|---|---|---|
| pending | | | | |

## Emission integrator

| Build | Spans | Wall time | vs Python |
|---|---|---|---|
| pending | | | | |
