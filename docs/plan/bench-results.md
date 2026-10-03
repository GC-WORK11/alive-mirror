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

Field: real snapshot `data/field/snapshots/2026/10/03/0202.json.gz` —
14,628 cells (`latlon-fallback` ~0.74 km² grid). 100k random lookups
(80% inside the NCR bbox, 20% outside → coverage-fallback path;
91,960 hits on both sides — identical). Dose: 1k generated NCR routes
(5–60 waypoints + jitter, duration 300–3600 s, random mode ME/VE from
`exposure.py`), per-call latency. Harness:
`server/core/bench/bench_field.py`, fresh subprocess per impl, seed 108/42.

| Build | Lookups/s | Dose p50 | Dose p95 | Dose p99 |
|---|---|---|---|---|
| C++ `alive_core` (g++ 13, -O3) | 174,618 | 46.0 µs | 94.3 µs | 3,065.7 µs |
| Python ref (`alive_core_ref.py`) | 25,849 | 607.3 µs | 4,890.2 µs | 10,742.3 µs |

Speedup (Python/C++): ~6.8x lookups, ~13.2x dose p50 (~3.5x p99 — long
routes amortise the pybind crossing). `FieldView` semantics: nearest cell
within 1.0 km on airindex's flat-earth km metric (110.6/99.4) — no
interpolation (cells are already the kriged product). Parity asserted
bit-exact (values `==`, dose bands to 1e-9 rel) by
`server/tests/test_parity_field.py` + `test_parity_dose.py`. Note:
bit-exactness required replicating CPython details — `x**2` is libm
`pow()` (not `x*x`) and 3.12 `sum()` is Neumaier-compensated.

## Kriging kernels

| Build | Stations | Grid | Wall time | vs Python |
|---|---|---|---|---|
| pending | | | | |

## Emission integrator

10k generated span sets (2–10 spans, mixed moving/idle) on a resolved
2010–16 diesel-car band, per-call latency:

| Build | p50 | p95 | p99 |
|---|---|---|---|
| C++ `alive_core` | 11.2 µs | 17.3 µs | 131.7 µs |
| Python ref | 37.3 µs | 235.5 µs | 1,244.0 µs |

~3.3x p50. Parity vs `alive_core_ref.integrate_emissions` and cross-checked
against production `emissions.integrate` (`test_parity_dose.py`).
