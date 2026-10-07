# Community-ledger data sanity — pre-demo audit

**Lane:** community-ledger sanity · **Date:** 2026-10-07 ~13:40Z · **Repo head audited:** `0c13dd9` (base/v2)
**Surfaces audited:** `GET /community` JSON + `community.html` (the page a judge reads), `/v2/city` corridors, `/reports`, plus the two durable stores behind them — DynamoDB `alive108-agg` (full scan, 170 items) and S3 `alive108-build-185708268748/community/state.json` (the corridor/day/hour snapshot, 34 KB).

## Verdict (what a judge gets)

**Every number on the page is real product data.** `44 trips · 24 contributors · 1,278.9 µg all-time` reconciles exactly to the stores, every visible corridor row clears the k≥3/72 h gate, and the audit found **zero test-labelled devices, zero seeded trips, zero non-Delhi geometry**. Three honest caveats below — two data wrinkles, one wording nit — none of them fabrication.

## Method

1. Read the write path: `POST /v2/trip` → `v2/trip.py` (privacy pipeline → H3 cells + hashed token + bounded summary) → `TRIPS.record_trip` (`agg_ddb.DDBTripAggregates` on `alive108-agg`) + `LEDGER.record` (`DDBDeviceLedger`) + `community.observe()` (in-memory aggregates → S3 snapshot). Legacy `POST /observe` fed `community.observe` only — retired `ad9367d` 10-05 14:34Z.
2. Read the publish path: `community.totals()` reads DDB day items + `LEDGER.devices()`; `corridors()` reads the S3-backed `_CELLS` gated `len(dev_all)>=3 && last_ts<=72 h`.
3. Full-scan `alive108-agg` (170 items) + pull the S3 snapshot + dictionary-attack the hashed device tokens (~140 test-y candidate ids) + recompute every displayed figure from raw items.

## Reconciliation (page ↔ store, exact)

| page says | store truth | match |
|---|---|---|
| `obs_total` 44 trips | day#sum trips: 17+14+8+5 = **44** = 43 ledger rows + 1 tokenless summary-only donation | exact |
| `contributors` 24 | `ledger_meta` items = **24** distinct `device#<sha256[:16]>` | exact |
| `avoided_ug_all` 1,278.9 | Σ day `avoided_ug` = 0+303.7+662.3+312.9 = **1,278.9** (17 reporting trips) | exact |
| today: 5 trips / 31.4 km / 10.9 µg / bus×1·car×4 / 312.9 dodged | `day#2026-10-07` sum item identical | exact |
| last trip ~6.3 h ago | day last_ts 10-07 07:01Z (= ledger row `e66281ec` 07:01Z) | exact |
| 5 named corridors (Outer Circle 10/7, Tolstoy Marg 8/6, Radial Road 4 6/5, Swami Vivekanada 5/5, Shahjahan 5/4) | S3 `_CELLS`: same cells, trips/dev counts identical; all real CP-area street names from offline gazetteer | exact |
| `/v2/city` corridors | DDB `cell#` items publishable: 12 cells, all real names (hanuman lane, Atul Grove Road, Motilal Nehru Marg…); top cell 883da11409fffff 16 trips/12 dev | exact |

Per-day ledger↔day-item sums verified field-exact (e.g. 10-03: 17 rows, km 71.7, dose 87.2; 10-07: 5 rows, km 31.4, dose 10.9). `ledger_meta.trips` totals = 43 = ledger row count. No double-counting, no day-item inflation vs the per-device ledger.

## k≥3 — enforced, and visibly suppressing real rows

- **Corridor cells (page):** S3 has 91 cells; 9 publishable (`dev_all≥3` + fresh); top-5 shown all ≥4 devices. 29 suppressed cells carry trips but <3 devices — correctly invisible.
- **DDB cells (`/v2/city`):** 55 items; publishable = tokens≥3 AND last_ts ≤72 h → 12 publish now; Oct-3/4-morning cells correctly stale-excluded.
- **Hour feed (`recent()`):** every live hour bucket has 0–2 devices → **all suppressed**. No lone-device trip leaks.
- **Global areas/OD:** `area#New Delhi` (12 trips/9 dev) and `od#New Delhi#New Delhi` (10/7) publish; `od#New Delhi#Old Delhi` (2 dev) suppressed.
- Code check: gate lives at publish (`corridors()`, `_publishable_cells`, `recent()`, `global_aggregates`, `corridor_field_samples`) — a below-k cell cannot reach any response.

## Pollution hunt — what was looked for, what was found

- **Test-labelled devices:** dictionary-attacked all 24 device hashes + all cell token hashes against ~140 candidates (`test`, `dev`, `devin`, `lane*`, `sim*`, `emu`, `e2e`, `load*`, …). **Zero hits.**
- **Non-Delhi geometry:** all 55 DDB cells are Delhi H3 res-8 (`883da1*`); all 91 community cells inside NCR bbox (all in the CP cluster 77.20–77.235 / 28.605–28.65). **Zero out-of-area.**
- **Mode vocabulary:** only real app modes (car/bus/auto/metro/walk/cycle/unknown). Area names only real districts (`New Delhi`, `Old Delhi`).
- **Impossible values:** all doses 0–38.4 µg, km 0.4–12.9, inside bounds. No zero-km trips (floor refuses), no epoch/future timestamps.
- **Seeding paths:** `tools/load_v2.py` never POSTs trip/observe/feedback (GETs + `/v2/plan` only); `docs/plan/app-demo-seed.md` seeds on-device daylog only and forbids faking; no seed scripts write the ledger. Lane drive reports confirm real nav arrivals (consent-off drives verifiably posted **zero** telemetry).

## Caveats a judge should hear if asked

1. **Two community-only traversals from the retired `/observe`.** S3 snapshot holds 2 tokenless donations never in the shared ledger: 10-05 05:36Z (~car, dose 41.2 µg, implied C 499) and 06:20Z (walk, dose 61.0 µg, implied C 143.6) — both while `/observe` was still live (retired `ad9367d` 10-05 14:34Z). Real traversal data (Delhi coords, mode-consistent implied-C), not test junk — but they inflate two published corridor dose sums: Outer Circle avg 12.2 (≈8.1 without) and Radial Road 4 avg 11.5 (≈1.6 without). Their implied-C samples feed corridor field medians until they age out **10-08 ~06:20Z** (72 h window — lapses right at demo open). The "44 trips" headline is unaffected (it reads the DDB ledger, which never saw them).
2. **14 ledger rows carry impossible implied speed** (>140 km/h; worst 7.8 km in 42 s ≈ 667 km/h) — pre-bound admissions before `9f4533b`/`e483a96` (Oct-7) added `MAX_SPEED_KMH`. Real donations with broken duration telemetry (compressed-time drives): the traversals happened — km and dose are sane — but their durations can't feed implied-C (refused by the ≥30 s/≤900 µg/m³ gate anyway). They count honestly in trip totals.
3. **"24 contributors" counts device tokens, not humans** — a reinstall mints a new token. Real telemetry, stated so nobody oversells it on stage.

## Wording nit (not data)

Page basis says "corridor cells publish only with ≥3 distinct devices in 72 h". Implementation = ≥3 distinct devices **all-time** + ≥1 traversal inside 72 h (the device set never expires per-device; same semantics in both stores). 3 of 9 publishable cells have only 2 devices fresh in the window — none appear in the page's top-5. If a privacy-reading judge presses, the honest phrasing is "≥3 phones ever crossed it AND it saw a trip in the last 72 h".

## Housekeeping notes

- `/admin/api` is 401-gated; its suppressed hour/area feeds are judge-invisible anyway.
- Reviews store: 1–2 rows (a 5★ blank-note today, lane-verified `/v2/feedback` live) — admin-only, note bodies withheld below k=3 by design.
- `/reports` empty (6 h TTL, zero active flags) — honest.
- "Numbers shift" is expected: donations still arriving (latest 10-07 07:01Z).
- **No data was modified or deleted by this audit.** The two `/observe` traversals age out of the corridor window on their own ~10-08 06:20Z; deleting them from S3 would be an ops call, and nothing in the DDB ledger needs touching.

## Evidence

- Raw dumps this audit used: `~/comm_audit/ddb_items.json` (170 items), `~/comm_audit/community_state.json` (S3 snapshot) on this box — recomputed figures quoted above.
- Code anchors: `server/community.py` (`totals()` L908, `corridors()` L869, `_fold` L146, k-gate L119-120), `server/agg_ddb.py` (`_publishable_cells` L470, `recent` L268, ledger layout L568+), `server/v2/trip.py` (`_BOUNDS` L86, `MIN_TRIP_KM`/`MAX_SPEED_KMH` L124-125, dedupe L47-80), `server/v2/store.py` (memory-backend mirror of the same contract).
- `/observe` retirement: `ad9367d` (10-05 14:34Z) — diff shows it wrote `community.observe` only, never `TRIPS`/`LEDGER`.
