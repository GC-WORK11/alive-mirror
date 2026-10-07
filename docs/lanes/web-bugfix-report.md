# web-bugfix — verify + fix pass over docs/lanes/web-audit.md

**All three flagged bugs were real and are fixed.** The audit's own numbers were re-verified against live prod (GET only), each fix was run locally through a real `uvicorn` server + `curl` before/after, and the related pytest files pass (111 + 94 = 205 tests). Direct push to `base/v2`.

## Verdict table

| claim | verdict | fix | evidence |
|-------|---------|-----|----------|
| `/city` today-ledger serves a stale day-key | **real** — live on prod right now | `city.html` keys the served `trips.days` on the real UTC date (`days[todayKey]`), not `days[lastKey]`; "last 3 days" contrib counter now sums the trailing-3-UTC-day window | prod `/v2/city` days keys = `{10-03, 10-04, 10-05}` while today = `10-07` → the page was showing Oct-5's `trips:8 / km:37.79 / dose:9.3` under "today" labels. Node re-run of old vs new expression on that field: **OLD → 8, NEW → 0** (+ the honest-empty copy "no shared trips today…" finally triggers) |
| donation/contributor stores diverge (22 vs 39) | **real** — both answers served simultaneously | `community.totals()` repointed to the **same** ledger `/v2/city` and `/admin` read (`v2.store.TRIPS.city_aggregates().days` + `LEDGER.devices()`); the module's duplicate all-time counters `_LIFE`/`_DEVICES` deleted outright | prod `/community` said `obs_total:22, contributors:14` while prod `/v2/city` ledger held **39 trips / 3 days** — same minute, two answers. Local before/after: after 3 probe `POST /v2/trip`s, **both** endpoints report `3 trips · 3 contributors · 5.4 km` byte-identical |
| 28 hardcoded station dots on the web map | **real** — static array painted as "the live instruments" | `AirField` now retains the live instrument set it already fetches each refresh (`_stations_live`, same `pm2_5 is not None` predicate as `station_readings`) and serves it on `status().stations`; `city.html` deleted the `STATIONS` constant and paints the served list — no list, no dots | prod field serves `station_readings: 53` but the map painted 28 baked dots beside copy claiming those dots ARE the instruments. Local `/aqi.field` after fix → `stations: []` (no keys on this box) → map draws zero dots; on prod it will serve the real ~53 coordinates |

## Claim 1 — stale day-key (detail)

- **Root cause:** `city.html:1603` read `days[dayKeys[dayKeys.length-1]]` — the *newest populated* key — and painted it under "the ledger, today", "shared trips today"/"km shared today" ticker items, the breaths divider, and "exhaust from shared trips, today". After UTC midnight (or any donation gap — prod currently has none since Oct 5) the card silently serves an older day.
- **Fix:** `const latest = days[todayKey] || {}` where `todayKey = new Date().toISOString().slice(0,10)` — the same `gmtime` basis `store.py` writes the keys with. `contrib` ("trips shared in the last 3 days") now sums days within the trailing-3-UTC-day window instead of `Σ all days`.
- **Not touched:** the page's "counted since utc midnight" copy was already the *claim*; the bug was the lookup. It is now true.

## Claim 2 — divergent donation stores (detail)

- **Root cause:** `v2/trip.py` dual-writes every donation: `TRIPS.record_trip`/`LEDGER.record` (DynamoDB on prod) *and* a best-effort `community.observe(...)` hop under `except Exception: pass` (S3 `community/state.json` on prod). Different persistence, silent failures, different contents (community folds only coord-bearing trips) — the two "shared trips" totals were structurally guaranteed to drift. `/community` quoted its own `_LIFE`/`_DEVICES` counters; `/city` + `/admin` quoted `TRIPS`.
- **Fix:** `community.totals()` now reads `TRIPS.city_aggregates().days` + `LEDGER.devices()` — literally the same fields the other surfaces serve, so they *cannot* disagree. `_LIFE`/`_DEVICES` deleted (a second all-time ledger that no longer exists can't be re-quoted by accident).
  - Wire fields renamed to what they now honestly are: `obs_24h`→`obs_today`, `km_24h`→`km_today`, `dose_ug_24h`→`dose_ug_today`, `avoided_ug_24h`→`avoided_ug_today`, `modes_24h`→`modes_today`, plus a served `today` day-key. Labels on `community.html` changed `· last 24 h` → `· today` ("same day-key as the /city ledger" in the explainer).
  - `latest_obs_age_min` needed a real newest-donation stamp → day buckets now carry `last_ts` on **both** backends (`v2/store.py` memory literal, `agg_ddb.py` `SET last_ts = :ts` on the `day#…`/`sum` item only; rounded to ms on both so the existing DDB↔memory parity test still holds).
  - `contributors` now comes from `LEDGER.devices()` — the device index `/v2/ledger` already maintains (token-bearing donations only; a tokenless trip counts trips but has no device to count — same semantics as before).
- **What stayed different on purpose:** corridor cells / `top_corridors` / `corridor_field_samples` keep reading this module's *traversal* projection — a legitimately different dataset (only donations carrying usable coordinates). `contributors_detail`/`recent_obs`/`journeys_per_hour` likewise stay on the traversal rollups; they're only consumed by the legacy monolithic `/admin/api` (admin.html uses the granular `admin_agg` endpoints, which already read TRIPS). Comments + docstrings now state the subset relationship so an operator can't misread it.
- **Local evidence (memory backend):**
  - before: `/community` `{"obs_total":0,"obs_24h":0,"contributors":0,…}` from its own store while `data/community.json` held 4-device corridor traversals — a dead giveaway the two stores counted different things.
  - after 3× `POST /v2/trip` (local, allowed): `/community` → `obs_total:3, obs_today:3, contributors:3, km_today:5.4, dose_ug_today:120.0, avoided_ug_today:45.0, modes_today:{"auto":3}, latest_obs_age_min:0, today:"2026-10-07"` — and `/v2/city` `trips.days["2026-10-07"]` carries `trips:3, km:5.4, dose_ug:120.0, avoided_ug:45.0, modes:{auto:3}, last_ts:1791337278.22`. Identical source, identical numbers.
  - a traversal-only `community.observe` (no TRIPS write) no longer inflates `obs_total` — tested (`test_totals_reads_the_shared_ledger`).

## Claim 3 — hardcoded station dots (detail)

- **Root cause:** `city.html` held `const STATIONS = [28 fixed lon/lat]` and painted them as green squares beside "the green squares on it" copy referring to the live instrument feed — while `station_readings` showed the live *count* (53 on prod at verify time, and it drops to ~24 in the known DPCC stall window).
- **Fix:** `airfield.py` keeps the pm2_5-carrying rows from `_grab_stations` on `self._stations_live` (set in the same refresh that sets `_station_count`, so the list and the count never disagree) and `status()` serves `"stations": [{lat, lon, name}]`. `city.html` paints `cy.field.stations` each load; absent list → zero dots (matches the "no live instruments" text it already prints at count 0).
- **Local evidence:** `/aqi` (no station keys on this box) → `{"serving":"live","station_readings":0,"stations":[],"stations_src":null}` → the minimap draws no dots — honest, never painted-in.

## Test runs

- `tests/test_community_v2.py` — rewritten fixture resets `TRIPS`/`LEDGER` singletons; new `test_totals_reads_the_shared_ledger`; `_LIFE`/`_DEVICES`-asserting tests repointed at the `_DAYS` rollups they actually exercise; snapshot key-set assertion updated (`life`/`devices` keys removed). **All 28 pass.**
- `tests/test_agg_ddb.py` — DDB↔memory `city_aggregates` parity incl. the new `last_ts` (explicit-ts seeds → equal). **All pass.**
- Also green: `test_v2.py`, `test_v2_city.py`, `test_landing_serve.py`, `test_admin_agg.py`, `test_airfield_v2.py`, `test_privacy_fuzz.py`, `test_health_detail.py`, `test_admin_v2.py`, `test_ledger_ddb.py`, `test_security.py` — **205 total, 0 failures.**

## Follow-ups / residuals (documented, not fixed)

- `Mobile/src/community.ts` `CommunityTotals` type declares the renamed `*_24h` fields — the app only reads `top_corridors` from the payload (App.tsx:757), so nothing breaks at runtime; a mobile-lane cleanup should re-sync the type when it touches the file.
- Prod DDB `day#` items pick up `last_ts` on the next donation; `latest_obs_age_min` reads `null` until then — the honest empty state.
- If the owner wants a *rolling* 24h panel back on `/community`, that's an additive `hour#`-window accessor on both TRIPS backends — deliberately not bundled here (minimal diff).
- Audit nits deliberately out of scope for this lane (belong to the nits lane): `/community` JSON unfurling, og: meta, 15-min vs 5-min copy, landing pre-filled numbers, <11px type floor, hairline borders, green-wash tiles.
