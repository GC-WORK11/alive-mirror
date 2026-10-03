# test-report — hardening fuzz + contract sync (feat/r2-tests lane)

Additive-only test pass over `/v2` (and the v1 endpoints the contract
declares). Tests live in `server/tests/test_privacy_fuzz.py`,
`test_v2_hardening.py`, `test_contract_sync.py`. Source files were NOT
modified — failures below are filed as BUG entries for the integrator.

Run: `cd server && uv run --with 'pytest,h3,boto3,httpx' pytest tests/test_v2_hardening.py tests/test_privacy_fuzz.py tests/test_contract_sync.py -q`
Result: **87 tests — 75 pass, 7 fail (all on real bugs), 5 skip** (skips =
v1 endpoints on flaky upstream paths; contract drift can only be judged
on an object response).

## Bugs found (failing tests = repro)

| # | Endpoint | Bug | Repro | Failing test |
|---|----------|-----|-------|--------------|
| BUG-T1 | `GET /v2/search` | Duplicate `"t2"` key in the response dict (`search.py:176` rows, `:179` status) — the status string wins, so Amazon T2 rows are computed, timed, then silently dropped from the wire | FakeLoc enabled → `body["t2"] == "ok"`, rows nowhere | `test_v2_search_t2_rows_reachable` |
| BUG-S1 | `GET /v2/search` | `limit` has `le=15` but no `ge=0` → `limit=-3` executes `merged[:-3]` and returns **17** results (negative-slice leak). Same pattern in v1 `/search` (`main.py:315`) | `GET /v2/search?q=cp&limit=-3` → 200, 17 rows | `test_search_limit_zero_and_negative` |
| BUG-R1 | `rank_options` (`plan.py:316`) | Reset loop only clears `tag`/`recommended`/`reason_line` on **scored** options — an unscored option keeps stale flags from its builder → two `recommended: true` on the wire | unit fuzz, seeded trial 0: unscored option retains `recommended=True` alongside the real winner | `test_rank_options_randomized_property` |
| BUG-R2 | `rank_options` (`plan.py:322`) | All-`None` emissions → every `_co2_mid` is `inf` → `inf == inf` → winner tagged **"lightest on both"** — an honesty claim on zero emission data | unit: two options, `co2_kg.mid=None` both | `test_rank_all_none_emissions_claims_nothing` |
| BUG-T2 | `POST /v2/trip` | Non-iterable `trajectory` (e.g. `42`) → `for p in traj` raises `TypeError` outside the try → **500** | `{"trajectory": 42}` → 500 | `test_garbage_trajectory_shapes` |
| BUG-T3 | `POST /v2/trip` | Summary numbers unsanitized → `float("not-a-number")` inside `record_trip` (`store.py:80-88`) → `ValueError` → **500** | `summary.distance_km="not-a-number"` → 500 | `test_malformed_summary_values_do_not_crash` |
| BUG-T4 | `POST /v2/trip` | No coordinate range validation → `lat=999` H3-wraps to cell `88f2de558bfffff` (−81°,−81°, South Atlantic) and is **stored as a real traversal** | trajectory with `[999.0, 999.0]` → 200, wrapped cell in `snapshot_cells()` | `test_out_of_range_coords_not_silently_stored` |

## Privacy fuzz — what held (docs/plan/07 §3)

| Attack | Result |
|--------|--------|
| ~200 m and ~550 m trips (< 600 m of combined trim) | 0 cells, 0 tokens stored — nothing personal |
| Boundary straddle at 300 m | every kept point ≥ ~290 m along-path from both raw ends |
| Raw home/end coordinates | never in store dump, never in response |
| 6+ decimal input coords | kept points all 4-dp rounded |
| Per-point ×4 duplication | collapses via thinning; same kept count ±1 |
| 10 000-point flood | `MAX_POINTS=5000` cap + ~100 m thinning hold; pairwise kept distance ≥ ~84 m (4-dp shift) |
| Token handling | stored only as `sha256[:16]`; verbatim token absent from store + response |
| k≥3 | 2 distinct devices → `corridors()==[]`; 3rd device → publishable; published rows = `{cell, trips, devices, avg_dose_ug}` only |
| Same device re-post | counts as 2 traversals but still 1 device (no k-inflation) |
| PII stuffed into `summary` | whitelist (`_SUMMARY_FIELDS`) drops `name`/`phone`/`home` |
| `{}` / array / string bodies | `{}` → honest 200 w/ 0 cells; non-dict → 422, no 500 |
| Store keys | every key is a valid H3 res-8 cell (`h3:8` scheme) |

## Findings (documented, not asserted-fail)

- **F1 — fallback cell scheme**: when `h3` isn't importable, `_cell` emits
  `ll:<lat4dp>,<lon4dp>` — quasi-raw coordinates at rest, against the
  H3-only letter of doc-07. Mitigations: 4 dp ≈ 11 m; only when h3
  missing (h3 is in deploy reqs). Recommend: hash or grid-bucket the
  fallback key.
- **F2 — no GNSS outlier rejection**: a 43 km teleport spike contributes
  1 stored outlier cell. Data quality, not privacy.
- **F3 — no NCR geo-fence**: Delhi→outside-NCR trace stored 23/58 cells
  outside the bbox; corridors could surface non-NCR cells (k≥3 applies).
- **F4 — `limit>15`**: `/v2/search` returns 422 rather than clamping —
  honest, but callers may expect a clamp.
- **F5 — empty trip counted**: `{}` increments the day `trips` counter
  with 0 cells — visible in city totals.
- **F6 — flaky v1 500s**: `/depart`, `/route`, `/search`, `/reverse` can
  500 when upstream calls raise non-`httpx.HTTPError` (e.g. `TimeoutError`
  / event-loop teardown) — catches are too narrow; environmental flake
  observed in sandbox.

## Contract sync (Bridge/contract.ts)

Runtime checker (`test_contract_sync.py`) parses the TS interfaces and
diffs them against live responses both directions (required-fields ⊆
wire keys; wire keys ⊆ declared fields).

- **Was stale**: zero `/v2` types existed; `TodayResponse.lat/lon/station`
  and `ReverseResponse.lat/lon` were required but never emitted;
  `FieldStatus`, `HealthResponse`, `AqiResponse` missed many emitted
  fields; `RouteResponse.field`, `CompareResponse.best/field`, and all
  `DepartResponse` fields were required though absent on error paths.
- **Additive update applied**: those fields marked optional / added;
  new `V2*` block (`V2SearchResponse`, `V2PlanResponse`, `V2PlanOption`,
  `DoseBand`, `EmissionBand`, `V2StripResponse`, `V2StripSample`,
  `V2TripRequest`, `V2TripResponse`, `V2CityResponse`, `V2Place`) +
  `V2_ENDPOINTS`. `tsc --noEmit --strict` clean.
- **Post-fix drift**: zero missing-required and zero undeclared-emitted
  on every reachable path (`test_drift_summary_print` prints the table).
  `V2SearchResponse.t2` documents BUG-T1 inline (`Place[] | string`).
- **Remaining gap**: `DecideResponse`/`DepartResponse` happy paths are
  unverifiable offline (upstream-dependent); nested `exposure` inside
  `CompareOption` checked only on error-path shapes.
