# Server-harden report — hot-path profile, dead-weight sweep, fixes

Lane: performance + correctness micro-audit of the three hot paths —
`/aqi` (kriged point eval), `/v2/plan`, `/v2/city` — on `base/v2`. Local
server on this box, 20 sequential requests per endpoint, both serving
modes exercised. Fixes kept small; no feature removal; seam-marked
dormant features left in place.

- **When:** 2026-10-06 late UTC, `build_sha=b869bd0` + this lane's diff.
- **Box limits:** this egress is rate-limited by open-meteo (every live
  fetch 429s), so the box reproduces prod's **upstream-down** mode
  exactly; prod's warm mode was profiled by seeding `FIELD._samples`
  with 81 real cells from the newest shipped snapshot (the same row
  shape a successful refresh produces) — `tools/lane_live_app.py`.
  OSRM public answers normally (~150–250 ms RTT), so `/v2/plan` numbers
  are fully realistic.
- **Harness:** `server/tools/lane_profile.py` — sequential requests,
  per-request wall ms + p50/p80/max + server-reported `took_ms`.
  Server run with `ALIVE_RATE_LIMIT=0` (documented knob) so the 20-call
  series isn't capped by the product rate limiter (/v2/plan is 2 rps /
  burst 6 by design).

## The slowest 20% and the cause

**`/aqi` and `/v2/city`: one root cause — failed-upstream retry storms.**

`AirField.refresh`, `FireField.refresh`, and `Forecast.refresh` each
stamped `_fetched_at` **only on success**. A dead upstream therefore
re-ran the entire fetch inside *every* request, on the request's
critical path (`/aqi` awaits field+fires refresh; `/v2/city` awaits
field refresh and, in `_next_hours`, the dual forecast bulk fetch).
The fetch itself is ~45 model-grid calls through a semaphore plus the
station chain plus wind (airfield), multi-satellite FIRMS CSVs (fires),
or two bulk requests (forecast). With open-meteo 429ing, every request
paid ~0.9–2.4 s doing work that could never succeed.

`/v2/plan` was **not** storm-bound: it fires the refresh as
`asyncio.ensure_future` (plan.py, off the critical path). Its critical
path is the racing-arm maximum, and the slowest arm is the external
OSRM public round trip — ~150–250 ms RTT is the floor, visible as
`took_ms ≈ 190`. Sporadic ~450 ms outliers trace to OSRM jitter and the
600 s engine-reweight boundary; the ~2.4 s first call is cold engine
pricing after boot. All bounded by design — nothing code-side to fix.

Inside `/v2/city`'s warm path the remaining real cost was
`_corridors → _name_corridor → _gaz_nearest`: a **linear scan over all
119,716 gazetteer rows per corridor cell** (~8.6 ms × up to 10 cells on
prod where the trips store is populated; empty locally). The gazetteer
has a text index but no spatial index.

## Timings — before → after

Wall ms p50, n=20 sequential each. "Degraded" = upstream-down mode
(every live fetch fails); "Live" = prod-realistic seeded field.

| endpoint | mode | before p50 (p80, max) | after p50 (p80, max) |
|---|---|---|---|
| GET /aqi | degraded, snapshot serving | 904 (910, 1444) | **1 (1, 11)** |
| GET /v2/city | degraded | 2380 (2953, 5195) | **20 (22, 51)** |
| POST /v2/plan | degraded | 227 (229, 2416) | 227 (229, 2416) — unchanged, external-bound |
| GET /aqi | live field (prod mode) | ~900 (same storm — mode-independent fetch) | **1 (1, 14)** |
| GET /v2/city | live field | ~2400 | **26 (29, 59)** |
| POST /v2/plan | live field | ~230 | 246 (249, 2127) — unchanged |
| POST /v2/plan (single-point warm) | | 10 | 10 — unchanged |

The surviving first-call tails (11 / 51 ms) are the single retry the
gate still allows per 60 s window — by design, it keeps checking for an
upstream recovery on a bounded cadence instead of every request.

## Fixes applied (diff: +60/−13 across 5 files)

1. **Failed-fetch retry gate** — `FETCH_RETRY_S=60` (airfield),
   `RETRY_S=60` (forecast, fires): on the non-force path a fetch
   attempt is allowed at most once per window, stamped inside the
   existing lock with the same double-check shape the TTL path uses.
   `force=True` (ingest worker, admin) bypasses it. Honesty untouched:
   `status()` still reports the field's real age and `upstream-error`
   — nothing is fabricated as fresh.
2. **Gazetteer spatial index** (`v2/city._gaz_geo`): 0.01° bucket grid
   built once per gazetteer load, keyed on the rows-list identity.
   `_gaz_nearest` now visits only the buckets touching the radius box —
   ~8.6 ms → ~µs per corridor cell (verified 0 parity mismatches vs the
   brute-force scan on ~120 sampled points).

## Dead-weight audit

Removed:
- `ingest_dpcc.py`: 4 unused imports (`base64`, `gzip`, `json`, `math`)
  — the registry read is delegated to `ingest_cpcb._registry()`.

Inspected and kept (with reasons):
- `route_geojson` on every plan option duplicates `geometry` verbatim —
  **~50% of the 452 KB response payload**. It is a documented wire
  contract (Bridge/contract.ts, Mobile routeTint/plan/reroute/nav,
  landing.html, tests assert equality). Seam-marked, stays; flagged as
  the candidate for a v3 slimming pass.
- `v2/plan._pt` vs `middleware.parse_point` — near-duplicate point
  parsers but intentionally different contracts (error wording, lat/lon
  range bounds vs service-area check). Kept.
- Per-module haversine/_km helpers (exposure, gazetteer, transit,
  transit_v2, alive_core_ref, airindex) — same ~15-line function behind
  five different seams; consolidating imports across seams is a bigger
  diff than the duplication costs. Kept.
- `ingest_dpcc` itself: flag-seamed dormant feed (`dpcc: skipped: flag
  off`), stays per the lane rule.
- No `if False` blocks, unreachable branches, or never-called helpers
  found (`ruff F401/F841` clean repo-wide after the fix above).

## Suite

- Affected tests after each fix: `test_airfield_v2`, `test_forecast`,
  `test_v2`, `test_v2_cache`, `test_ingest_dpcc` (85+5sk),
  `test_v2_city` (11), `test_v2_plan`, `test_v2_reroute`,
  `test_lifespan_warm`, `test_executor_starvation` (63) — all green.
- Full suite: **1164 passed, 10 skipped** in 448 s — identical to the
  pre-change baseline (1164/10).

## New files

- `server/tools/lane_profile.py` — the sequential timing harness.
- `server/tools/lane_live_app.py` — profiling-only app wrapper that
  seeds the live field from real snapshot cells (never imported by the
  app; marked as such).
