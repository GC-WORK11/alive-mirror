# Lane report: grap-stage — honest GRAP-equivalent surface

**Date:** 2026-10-06 · **Commit:** `83d47de` on `base/v2` · **Verdict: shipped, gates green**

## Mandate → what shipped

October Delhi runs on GRAP; the product never names it. This lane adds the
honest GRAP-*equivalent* surface: the CAQM stage today's served air **maps
to**, computed from the codebase's one PM2.5→AQI formula — never a claim
about the legal stage, which is CAQM's declaration and which we do not
receive.

## Source (cited, not invented)

CAQM, **"Comprehensively revised GRAP Schedule" for NCR** — caqm.nic.in
(Dec 2024; further revised 21-Nov-2025 — that revision moved *measures*
between stages; the AQI triggers below were untouched). Stage triggers are
declared on **Delhi's CPCB national AQI**:

| Stage | Name | AQI trigger |
|---|---|---|
| I | 'Poor' | 201–300 |
| II | 'Very Poor' | 301–400 |
| III | 'Severe' | 401–450 |
| IV | 'Severe+' | >450 |

Cited in code at `districts.py` above `grap_stage`, in `Bridge/contract.ts`
on `V2Grap`, and in `tests/test_grap_stage.py`'s module docstring.

## Design decisions

- **One formula, total.** `districts.grap_stage(aqi)` + `grap_block(pm25,
  basis)` sit beside `cpcb_aqi`/`cpcb_band`; every surface flows through
  `grap_stage(cpcb_aqi(mean_pm25))`. Two surfaces can disagree on the *air*
  (point vs city mean) but never on the *mapping*.
- **`/aqi`'s pre-existing `grap_indicative` was a second formula** — a
  PM2.5-band approximation (I≈>90, II≈>120, III≈>250, IV≈>350 µg/m³). It now
  delegates to `districts.grap_stage(districts.cpcb_aqi(pm25))`. Wire keys
  (`indicative_stage`, `basis_pm25`) unchanged — the contract declares
  `grap?: Record<string, unknown>` and city.html's ticker was the only
  reader.
- **CPCB AQI, not US AQI.** `/aqi` also serves `us_aqi`; GRAP is legally
  defined on the CPCB national index, so `cpcb_aqi` is the basis.
- **Stage 0 is a real answer.** AQI ≤200 maps to `equivalent_stage: 0` —
  "below the Stage-I floor" is information, distinct from a cold field
  where the `grap` key is **absent** (not null). Honest degrade:
  `/v2/day` cold/error paths return before the block is built; `/v2/city`
  omits it when `pm25_stats.n == 0`.
- **Copy discipline everywhere:** "maps to GRAP stage N rules", "computed
  from today's air, not the official CAQM declaration" — never "in
  effect", never "official". The /city ticker's previous tooltip said
  "the official smog-emergency stage" — fixed in passing (it also now
  reads `cy.grap`, the city-field basis, instead of the point `/aqi` read,
  and shows `below stage i` instead of `—` for stage 0).

## Surface inventory

| Surface | Change |
|---|---|
| `server/districts.py` | `grap_stage` + `grap_block` (CAQM comment block with the schedule) |
| `server/airfield.py` | `grap_indicative` delegates to the shared stage map |
| `server/v2/day.py` | `grap` on the payload over `day_mean_pm25`; absent on cold/error/out-of-area |
| `server/v2/city.py` | `grap` over `pm25_stats.mean`; absent when `n == 0` |
| `server/city.html` | `#grapline` whyline under the hero ("today's air maps to *GRAP stage N* rules — aqi A on the city's live pm2.5 · computed here, not the official caqm call"); ticker `smog alert` row re-sourced + re-worded |
| `server/admin.html` | `/v2/city` added to the tick poll; `grap` row in the field panel (hidden when absent) |
| `Bridge/contract.ts` | `V2Grap` interface; `grap?` on `V2DayResponse` + `V2CityResponse` |
| `server/tests/test_contract_sync.py` | NESTED_OBJ entries for both `grap` keys |
| `server/tests/test_grap_stage.py` | NEW — 9 tests |

## Tests

`tests/test_grap_stage.py` — 9 tests, no network:

- `test_stage_boundaries_exact` — CAQM edges land exactly: 200→0, 201→I,
  300→I, 301→II, 400→II, 401→III, 450→III, 451→IV, None→None
  ("200.9→I? no — 201 exact boundary")
- `test_block_shape_note_and_formula` — `{equivalent_stage, aqi, basis,
  note}` at 12 PM2.5 values incl. band edges; `aqi == cpcb_aqi(pm25)`
  always (proves no second formula); `grap_block(None)` → None
- `test_aqi_indicative_shares_the_formula` — `/aqi`'s legacy block equals
  `grap_stage(cpcb_aqi(pm25))` across the old band edges
- `test_day_grap_present_and_consistent` — block consistent with served
  `day_mean_pm25`
- `test_day_grap_omitted_on_cold_forecast` — "forecast unavailable" →
  no `grap` key
- `test_day_grap_omitted_outside_area` — out-of-area → no `grap` key
- `test_city_grap_present_and_consistent` — block consistent with
  `pm25_stats.mean`
- `test_city_grap_omitted_on_cold_field` — `n:0` → no `grap` key
- `test_block_below_stage_one_is_real_answer` — stage 0 served as data,
  not absence

## Gates

- **Targeted:** `pytest -q tests/test_grap_stage.py tests/test_v2_day.py
  tests/test_v2_city.py` → **34 passed**; `tests/test_contract_sync.py` →
  **62 passed** (both directions of the contract check accept `V2Grap`).
- **Full suite:** `PYTHONPATH=core/build312:. .venv312/bin/python -m pytest
  -q tests` → **1141 passed, 7 skipped**.
  - *Caveat worth recording:* the first full run failed 13 tests in
    `test_reach`/`test_path_parity`/`test_path_legality` —
    `'alive_core.PathEngine' has no attribute 'reach'`. **Pre-existing and
    unrelated to this lane:** the gitignored `core/build312/*.so` on this
    box was built Oct 4, before `ba63d03` (Oct 5) added `reach` to the C++
    engine. Rebuilt via `server/core/build_ext.sh`; the three files then
    passed 41/41. Any session on a stale snapshot hits this — rebuild
    before trusting a red suite.
- **JS:** `node --check` on the extracted script bodies of `city.html` and
  `admin.html` — both parse.
- **Register kept:** hero line reuses the `.whyline` hairline-chip pattern
  (`grap` tag + plain-English `.wtxt`); muted palette untouched; lowercase
  `aqi`/`pm2.5` copy avoids the `µ`+`text-transform` gotcha; no emojis.

## Live API (GETs only — verified, not modified)

`http://65.2.28.40` runs `build_sha 9af96710` — **predates this lane**, so
live `/v2/city` and `/v2/day` currently serve no `grap` key (correct
honest-absent behavior on the old build). As-of-fetch numbers and what the
new code will compute once the box redeploys:

| Endpoint | Served basis | cpcb_aqi | equivalent_stage |
|---|---|---|---|
| `/v2/city` `pm25_stats.mean` | 89.7 | 199 | **0** — below Stage I (real answer) |
| `/v2/day` `day_mean_pm25` | 118.7 | 296 | **I** |
| `/aqi` point pm25 (smoke-modified) | 95.8 | 220 | indicative_stage **1** |

Note the live `/aqi` already shows the *old* formula agreeing here by
coincidence (95.8 > 90 → stage 1 either way); the unification matters at
the stage-IV boundary and band edges where the two formulas disagreed.

## Rules kept

- Never claims the official/in-effect stage — "maps to", "computed from
  today's air" throughout; CAQM declaration named as the legal source.
- No second AQI formula — the pre-existing one was *removed*, not added to.
- Key absent on cold field, not null.
- Server + web only — **zero `Mobile/` changes** (APK frozen).
- Live API: GETs only (`/v2/city`, `/v2/day`, `/aqi`, `/health`).
- `git pull --rebase` before push; direct to `base/v2`.
