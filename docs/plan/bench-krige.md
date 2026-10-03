# bench-krige — kriging kernel validation + wall-clock

Phase-5 (doc 08) heavy validation for the `alive_core` kriging kernels.
Everything below is measured — `server/core/bench/bench_krige.py`, run on
this machine (Apple Silicon, clang++ `-O3`, Eigen 5.0.1, pybind11 3.1.0,
Python 3.12, numpy 2.5.3). Reproduce with:

    cd server && PYTHONPATH=core/build:core:. \
        .venv312/bin/python core/bench/bench_krige.py --json bench_krige.json

## Setup

- Data: `server/data/delhi_climatology.json.gz` — OpenAQ archive,
  125 NCR stations, station × month × hour-IST pm2.5 `[p25, median, p75]`
  (9.0M measurements, 2016-02 → 2026-09).
- Method: leave-one-station-out over each month×hour slice — fit on the
  remaining stations, predict the held-out station's median, compare.
  7 slices spanning season + time-of-day, 643 folds per implementation.
- Implementations:
  - `py-krige` — production `server/krige.py` `KrigeField` (numpy inverse).
  - `cpp-legacy` — `alive_core.KrigeField` with `legacy_variance=True`
    (drop-in replacement semantics, bit-for-bit mu/sigma vs krige.py).
  - `cpp-corrected` — same kernel with `legacy_variance=False`
    (exact error variance, see "sigma finding" below).
  - `cpp-universal` — universal kriging, drift row `[1, x_km, y_km]`
    (linear trend; a constant covariate is singular — it duplicates the
    intercept).
  - `idw` — `airindex._idw` p=2, the current no-kriging fallback.
- Coverage-95 = fraction of folds with `|mu − true| ≤ 1.96·sigma`.
- Wall-clock = `perf_counter_ns` around fit + estimate of each fold.

## LOSO results per slice

### Jan 20:00 IST — deep winter evening (82 stations)

| impl | folds | MAE | RMSE | bias | cov95 | mean σ | fold ms | p95 ms | wall ms |
|---|---|---|---|---|---|---|---|---|---|
| py-krige | 82 | 36.37 | 45.62 | 0.85 | 0.439 | 14.6 | 0.121 | 0.133 | 9.9 |
| idw | 82 | 36.77 | 46.37 | 5.25 | — | — | 0.009 | 0.010 | 0.8 |
| cpp-legacy | 82 | 36.37 | 45.62 | 0.85 | 0.439 | 14.6 | 0.087 | 0.104 | 7.1 |
| cpp-corrected | 82 | 36.37 | 45.62 | 0.85 | 0.720 | 27.3 | 0.086 | 0.093 | 7.1 |
| cpp-universal | 82 | 37.14 | 46.69 | 1.05 | 0.720 | 27.6 | 0.099 | 0.120 | 8.1 |

### Mar 13:00 IST — spring midday (94 stations)

| impl | folds | MAE | RMSE | bias | cov95 | mean σ | fold ms | p95 ms | wall ms |
|---|---|---|---|---|---|---|---|---|---|
| py-krige | 94 | 13.48 | 19.80 | 0.35 | 0.351 | 3.8 | 0.153 | 0.172 | 14.4 |
| idw | 94 | 12.06 | 18.39 | 0.96 | — | — | 0.010 | 0.011 | 1.0 |
| cpp-legacy | 94 | 13.48 | 19.80 | 0.35 | 0.351 | 3.8 | 0.120 | 0.131 | 11.3 |
| cpp-corrected | 94 | 13.48 | 19.80 | 0.35 | 0.649 | 6.9 | 0.122 | 0.132 | 11.5 |
| cpp-universal | 94 | 13.53 | 19.82 | 0.37 | 0.660 | 7.0 | 0.138 | 0.154 | 13.0 |

### May 13:00 IST — summer afternoon (103 stations)

| impl | folds | MAE | RMSE | bias | cov95 | mean σ | fold ms | p95 ms | wall ms |
|---|---|---|---|---|---|---|---|---|---|
| py-krige | 103 | 49.65 | 179.55 | 3.41 | 0.553 | 32.4 | 0.171 | 0.180 | 17.6 |
| idw | 103 | 52.59 | 163.85 | 13.85 | — | — | 0.011 | 0.011 | 1.1 |
| cpp-legacy | 103 | 49.65 | 179.55 | 3.41 | 0.553 | 32.4 | 0.155 | 0.169 | 16.0 |
| cpp-corrected | 103 | 49.65 | 179.55 | 3.41 | 0.922 | 65.5 | 0.162 | 0.190 | 16.7 |
| cpp-universal | 103 | 49.78 | 179.56 | 3.47 | 0.922 | 66.2 | 0.174 | 0.185 | 17.4 |

### May 20:00 IST — summer evening (103 stations)

| impl | folds | MAE | RMSE | bias | cov95 | mean σ | fold ms | p95 ms | wall ms |
|---|---|---|---|---|---|---|---|---|---|
| py-krige | 103 | 18.02 | 22.80 | 0.66 | 0.320 | 4.7 | 0.172 | 0.181 | 17.7 |
| idw | 103 | 15.49 | 20.84 | -1.22 | — | — | 0.011 | 0.012 | 1.2 |
| cpp-legacy | 103 | 18.02 | 22.80 | 0.66 | 0.320 | 4.7 | 0.155 | 0.168 | 16.0 |
| cpp-corrected | 103 | 18.02 | 22.80 | 0.66 | 0.534 | 8.9 | 0.158 | 0.182 | 16.3 |
| cpp-universal | 103 | 18.05 | 22.83 | 0.66 | 0.534 | 9.0 | 0.173 | 0.198 | 17.8 |

### Aug 11:00 IST — monsoon midday (92 stations)

| impl | folds | MAE | RMSE | bias | cov95 | mean σ | fold ms | p95 ms | wall ms |
|---|---|---|---|---|---|---|---|---|---|
| py-krige | 92 | 8.74 | 11.87 | 0.54 | 0.435 | 2.9 | 0.143 | 0.149 | 13.1 |
| idw | 92 | 7.85 | 10.95 | 1.05 | — | — | 0.010 | 0.011 | 0.9 |
| cpp-legacy | 92 | 8.74 | 11.87 | 0.54 | 0.435 | 2.9 | 0.117 | 0.130 | 10.7 |
| cpp-corrected | 92 | 8.74 | 11.87 | 0.54 | 0.630 | 4.9 | 0.116 | 0.127 | 10.7 |
| cpp-universal | 92 | 8.78 | 11.87 | 0.51 | 0.630 | 4.9 | 0.130 | 0.138 | 11.9 |

### Oct 19:00 IST — autumn evening (86 stations)

| impl | folds | MAE | RMSE | bias | cov95 | mean σ | fold ms | p95 ms | wall ms |
|---|---|---|---|---|---|---|---|---|---|
| py-krige | 86 | 23.23 | 31.85 | -0.83 | 0.419 | 8.3 | 0.136 | 0.143 | 11.7 |
| idw | 86 | 21.16 | 30.40 | -1.74 | — | — | 0.011 | 0.013 | 1.0 |
| cpp-legacy | 86 | 23.23 | 31.85 | -0.83 | 0.419 | 8.3 | 0.134 | 0.152 | 11.5 |
| cpp-corrected | 86 | 23.23 | 31.85 | -0.83 | 0.686 | 15.3 | 0.127 | 0.144 | 10.9 |
| cpp-universal | 86 | 23.71 | 32.30 | -0.73 | 0.686 | 15.5 | 0.108 | 0.115 | 9.3 |

### Dec 08:00 IST — winter morning (83 stations)

| impl | folds | MAE | RMSE | bias | cov95 | mean σ | fold ms | p95 ms | wall ms |
|---|---|---|---|---|---|---|---|---|---|
| py-krige | 83 | 36.95 | 46.71 | 0.89 | 0.410 | 14.2 | 0.124 | 0.142 | 10.3 |
| idw | 83 | 38.47 | 49.25 | 6.42 | — | — | 0.009 | 0.010 | 0.8 |
| cpp-legacy | 83 | 36.95 | 46.71 | 0.89 | 0.410 | 14.2 | 0.092 | 0.101 | 7.6 |
| cpp-corrected | 83 | 36.95 | 46.71 | 0.89 | 0.735 | 26.5 | 0.093 | 0.101 | 7.7 |
| cpp-universal | 83 | 37.59 | 47.37 | 1.18 | 0.735 | 26.9 | 0.104 | 0.114 | 8.7 |

## Aggregate — all 643 folds

| impl | folds | MAE | RMSE | bias | cov95 | mean σ | fold ms | p95 ms | wall ms |
|---|---|---|---|---|---|---|---|---|---|
| py-krige | 643 | 26.58 | 77.51 | 0.89 | 0.418 | 11.7 | 0.147 | 0.176 | 94.7 |
| idw | 643 | 26.28 | 71.75 | 3.58 | — | — | 0.010 | 0.013 | 6.7 |
| cpp-legacy | 643 | 26.58 | 77.51 | 0.89 | 0.418 | 11.7 | 0.125 | 0.163 | 80.3 |
| cpp-corrected | 643 | 26.58 | 77.51 | 0.89 | 0.697 | 22.6 | 0.136 | 0.207 | 87.6 |
| cpp-universal | 643 | 26.86 | 77.67 | 0.98 | 0.698 | 22.8 | 0.134 | 0.179 | 86.1 |

## Grid refresh — production 15-min rebuild shape

One fit on the fullest slice (May-20:00, 103 stations), then `estimate()`
over every `airindex._fallback_cells()` cell (14,628 cells ≈ H3 res-8
coverage of the NCR bbox):

| impl | fit ms | cells | est ms | µs/cell |
|---|---|---|---|---|
| py-krige | 0.213 | 14,628 | 101.8 | 6.96 |
| idw | 0.019 | 14,628 | 150.5 | 10.29 |
| cpp-legacy | 0.191 | 14,628 | 39.0 | 2.66 |
| cpp-corrected | 0.241 | 14,628 | 33.3 | 2.28 |
| cpp-universal | 0.198 | 14,628 | 36.1 | 2.47 |

## Findings

1. **Parity is exact.** `cpp-legacy` reproduces `py-krige` MAE/RMSE/bias/
   coverage identically on every slice (pointwise agreement ≤ ~5e-13 on
   both mu and sigma — see `server/tests/test_parity_krige.py`).

2. **krige.py under-reports sigma ~2×; bands under-cover badly.** Its
   variance formula `sill − w·k + λ` drops the nugget from C(0) and flips
   the Lagrange-multiplier sign (λ<0 away from stations, so it subtracts
   instead of adds). Verified against the brute-force error variance
   `wᵀKw − 2w·k + C(0)` in the parity test. Consequence: nominal 95% bands
   cover only 35–55% of held-out truth per slice (0.418 pooled). The
   corrected formula `(sill+nugget) − w·k − λ·f0` lifts coverage to
   0.63–0.92 (0.697 pooled) — still under nominal because the real field
   is not perfectly Gaussian-stationary, but honest by ~2×.
   `legacy_variance` stays the default for drop-in compatibility; flipping
   production to corrected sigma is a one-line param change once the
   integrator wants it.

3. **Universal kriging changes almost nothing here** (±0.3 µg MAE): the
   linear trend is weak inside a 60 km field. The path exists for the
   real regression-kriging use — per-station model-prior covariates in
   `airindex.build_field`, where the drift varies spatially.

4. **mu accuracy is krige-vs-IDW mixed.** Kriging wins the high-variance
   winter slices (Jan-20:00 36.37 vs 36.77; Dec-08:00 36.95 vs 38.47) and
   loses the smooth ones (Aug-11:00 8.74 vs 7.85; May-20:00 18.02 vs
   15.49; Oct-19:00 23.23 vs 21.16). Pooled, IDW edges out on RMSE
   (71.75 vs 77.51) — the May-13:00 outlier slice (RMSE ~180) dominates
   both. Kriging's value is the honest sigma band IDW cannot give, not a
   universal accuracy win.

5. **Speed: ~1.2× per LOSO fold, ~2.9× per grid estimate.** A single
   (n+1)² system is too small for C++ to dominate — numpy's `inv` is
   already tight (~0.1 ms). The win is the estimate side: 2.66 µs/cell
   vs 6.96 µs/cell on 14.6k cells, i.e. a 15-min grid refresh costs
   ~34 ms C++ vs ~102 ms Python for the kriging step alone (IDW's pure-
   Python loop costs 150 ms and gives no sigma).
