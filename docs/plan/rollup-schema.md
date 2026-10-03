# Rollup & validation output schema

Contracts for the two artifacts `server/rollup.py` writes. Both are
versioned; consumers should branch on `schema`. Units are µg/m³ for every
concentration field unless noted. Sources: doc 05 §2 (daily rollup,
weekly validation), doc 06 §accuracy (LOSO shown on `/city`).

## 1. `alive-rollup/2` — `daily/YYYY-MM-DD.json`

One per IST day, built from every readable field snapshot
(`field/YYYY/MM/DD/HHmm.json.gz`, local mirror or `ALIVE_AIR_BUCKET`).

| field | type | unit / meaning | provenance |
|---|---|---|---|
| `schema` | str | `"alive-rollup/2"` | this doc |
| `date` | str | `YYYY-MM-DD`, UTC snapshot day | snapshot path |
| `hours_tz` | str | timezone of `worst_hours` — `"IST"` | fixed |
| `n_snapshots` | int | snapshots that parsed into airindex fields | inputs |
| `snapshots` | [str] | labels (local path or `s3://`) of used snapshots, time order | inputs |
| `inputs.skipped` | [{snapshot, reason}] | every blob that failed read/parse — counted, never silently dropped or fabricated | inputs |
| `inputs.n_skipped` | int | `len(inputs.skipped)` | derived |
| `n_cells` | int | cells with ≥1 pm25 reading | cells |
| `thresholds.who_24h_pm25` | float | 15.0 — WHO 24-h guideline | doc 05 |
| `thresholds.cpcb_24h_pm25` | float | 60.0 — CPCB/NAAQS 24-h standard | doc 05 |
| `cells.<cid>.mean` | float | mean of the day's `pm25` readings | cell.pm25 across snapshots |
| `cells.<cid>.min` / `.max` | float | extremes of the day's readings | same |
| `cells.<cid>.p10` / `.p50` / `.p90` | float | **intra-day percentile band** — linear-interpolated percentiles of the day's pm25 values (temporal spread, not model σ) | same |
| `cells.<cid>.lo_mean` / `.hi_mean` | float\|null | mean of snapshot `lo`/`hi` band edges (average model uncertainty band) | cell.lo/hi |
| `cells.<cid>.worst_hours` | [int] | up to 6 IST hours ranked by mean pm25, worst first | built_epoch→IST |
| `cells.<cid>.n_snapshots` | int | snapshots contributing to this cell | count |
| `city.median_pm25` | float\|null | median of per-cell daily means (v1 semantics: `sorted[n//2]`) | cells.*.mean |
| `city.pct_cells_gt15_who` | float\|null | % of cell means above WHO 24 h | thresholds |
| `city.pct_cells_gt60_cpcb` | float\|null | % above CPCB 24 h | thresholds |
| `city.ventilation_m2s` | [{t, vc_m2s}] | per-snapshot ventilation coefficient BLH×wind (m²/s) | snapshot.met |
| `city.weighting` | str | `"uniform-cells"` (default) or `"per-cell-weights"` | see below |
| `city.weighting_note` | str | why this weighting | see below |
| `city.weighted_mean_pm25` | float\|null | weighted mean of cell daily means | cells.*.mean × w |
| `city.weighted_median_pm25` | float\|null | weighted median (cumulative-weight step) | same |
| `city.pm25_p10`/`p25`/`p75`/`p90` | float\|null | weighted city percentile curve points (feeds admin "city percentile curves", doc 07 §2) | same |
| `written_to`, `backend`, `note` | str | where the blob landed (`s3`/`local`) + degrade note | store_blob |

**Weighting:** doc 05 §2 specifies the city summary (median + % above
thresholds) but names **no population-density proxy**, so the default is
uniform — every grid cell one vote, `weighting: "uniform-cells"`.
`daily_rollup(..., cell_weights={cid: w})` switches the `city.weighted_*`
block to per-cell weights (e.g. population) without changing callers; the
unweighted median/% fields always stay alongside.

**v1→v2:** all `alive-rollup/1` fields (`mean`, `max`, `worst_hours`,
`n_snapshots`, `median_pm25`, `pct_*`, `ventilation_m2s`) are unchanged;
v2 adds `min`, `p10/p50/p90`, `lo_mean/hi_mean`, `inputs`, and the
`city.weighted_*` block.

## 2. `alive-validation/2` — `validation/weekly-{week}.json`

Weekly leave-one-station-out + archive replay. `{week}` is the ISO week
(`YYYY-Www`); snapshots are matched by UTC date inside Mon–Sun.
Canonical artifact is `weekly-{week}.json`; `{week}.json` is a byte
-identical compat copy of the pre-v2 name. `weekly-{week}.md` is the
human summary (same numbers, prose + worst-fold table).

| field | type | meaning | provenance |
|---|---|---|---|
| `schema` | str | `"alive-validation/2"` | this doc |
| `week` | str | ISO week `YYYY-Www` | arg / clock |
| `generated` | str | UTC ISO timestamp | clock |
| `snapshot` | str\|null | `built_at` of the snapshot scored | snapshot |
| `snapshot_used` | str\|null | label (path) of the scored snapshot | inputs |
| `snapshot_in_iso_week` | bool | false when no usable snapshot existed inside the week and the global latest was scored instead (flagged, not hidden) | inputs |
| `inputs.snapshots_scanned` | int | snapshot files seen inside the week | inputs |
| `inputs.skipped` / `.n_skipped` | list / int | corrupt/unreadable snapshots walked past, with reason | inputs |
| `loso.status` | str | `ok` / `insufficient stations` / `no pairs` / `no usable snapshot` | — |
| `loso.n` / `.n_folds` | int | folds evaluated — one per usable station | stations |
| `loso.mae_ugm3` / `.rmse_ugm3` / `.bias_ugm3` | float | held-out pred − obs errors | folds |
| `loso.coverage_pct` | float | % of held-out obs inside the rebuilt `lo_ugm3..hi_ugm3` band (~95% nominal) | folds |
| `loso.band` | str | band definition string | fixed |
| `loso.method` | str | `"krige+idw-fallback"` — krige.KrigeField when it fits (≥20 varying residuals + numpy), else IDW residual + distance-grown σ, same as build_field | krige.py / airindex.py |
| `loso.per_station[]` | obj | `{station, obs_ugm3, pred_ugm3, lo_ugm3, hi_ugm3, err_ugm3, in_band, method}` | each fold |
| `loso.skipped` / `.n_skipped` | list / int | stations excluded from folding (missing pm25/residual/location, or no estimate) — counted, never folded | stations |
| `archive_replay` | obj | `{status, pairs, mae_ugm3, rmse_ugm3, bias_ugm3, mean_obs}` vs OpenAQ archive via `validate_field.validate(168h)`; `unavailable: <reason>` when it can't run (incl. SystemExit) | validate_field.py |
| `written_to`, `backend`, `note`, `summary_md` | str | artifact locations + degrade notes | store_blob |

**Fold construction:** the model prior doesn't depend on stations, so a
fold rebuild = refit the station-residual interpolator on the N−1
remaining stations and evaluate it at the held-out location. `pred =
prior + residual_est` where `prior = obs − residual` (exact by
construction in `build_field`); the band uses build_field's own σ math
(krige σ + 12 % instrument floor, or IDW distance-grown spread). Held-out
error `pred − obs` is exactly the residual-space error — concentration
and residual space are identical here.

**v1→v2:** `schema`, `week`, `generated`, `snapshot`, `loso`,
`archive_replay` unchanged in name; v2 adds band coverage + per-station
bands, fold/skip accounting, `inputs`, `snapshot_used`,
`snapshot_in_iso_week`, `summary_md`, and the `weekly-` filename.
