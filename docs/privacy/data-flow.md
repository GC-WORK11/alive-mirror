# Data flow — what a donated trip becomes

One donation path exists: **`POST /v2/trip`**, the hardened pipeline the
privacy spec (docs/plan/07 §3) describes. (`POST /observe`, the older
raw-coords endpoint, is retired — it answers 410 Gone. Its store,
`community.observe()`, lives on as the citizen-corridor layer that
`/v2/trip` feeds *after* the pipeline — and since the privacy audit it
folds every donation straight into aggregates at ingest.)

## Path A — POST /v2/trip (the spec pipeline)

```
 phone                                  server (process memory only)
 ─────                                  ──────────────────────────
 trip ends / option picked
   │                                      POST /v2/trip
   │  {device_token,                       server/v2/trip.py:99
   │   summary{mode,km,s,dose,co2,pm25,
   │           switched},
   │   trajectory[[lon,lat]…]}  ────────►  1. parse ≤5000 pts        trip.py:54-65
   │                                       2. TRIM 300 m both ends   trip.py:28,82-85
   │                                       3. THIN ~100 m spacing    trip.py:29,87-91
   │                                       4. ROUND 4 dp (~11 m)     trip.py:30,90
   │                                       5. → H3 res-8 cell keys   trip.py:33-44,107
   │                                          (fallback grid:4dp)
   │                                       6. token → sha256[:16]    trip.py:109-110
   │                                       7. raw payload DISCARDED  trip.py:106-114
   │                                              │
   │                                              ▼
   │                                     TripAggregates              store.py:60
   │                                       _days["YYYY-MM-DD"]       store.py:75-87
   │                                         {trips, km, dose_ug,
   │                                          co2_kg_mid, pm25_g_mid,
   │                                          switched, modes{}}
   │                                       _cells[cell]              store.py:89-97
   │                                         {count, dose_sum,
   │                                          tokens:{hashed ids},
   │                                          last_ts}
   │                                              │
   │              GET /v2/city                     ▼                 city.py:45
   │   totals only ◄─────────── city_aggregates()  store.py:117-129
   │   (no cells,              days{} + cells_tracked +
   │    no tokens)             corridors_publishable count
   │
   │              corridor layer                   ▼
   │   only cells with          corridors()        store.py:111-115
   │   ≥3 distinct hashed       _publishable_cells store.py:99-109
   │   tokens AND fresh ≤72 h ─►  filter: len(tokens)>=3
   │   get published               && now-last_ts<=72h
   │
   │   response echoes the transform actually applied
   │   {trimmed_start_m, trimmed_end_m, thin_m,
   │    rounded_decimals, cell_scheme}             trip.py:119-127
```

Invariant: after step 7 there is no coordinate and no raw token anywhere
in the process. `_cells` holds H3 keys and hashed-token sets; `_days`
holds sums. In-memory → cleared on restart (no TTL coded).

## Path B — community.observe() (the citizen-corridor store, post-audit)

Fed **only** by /v2/trip's `kept` points — already trimmed, thinned,
rounded. `observe()` re-snaps them to ~500 m cells and folds them into
AGGREGATES at ingest; no per-trip row is ever created.

```
 /v2/trip `kept` pts  ──►  community.observe()        community.py
   (privacy_trimmed)        • pts → ~500 m cell SET (order dies)  _cell
                            • contributor → sha256[:16]           _token
                            • _fold():                            _fold
                                  _CELLS[cell] += {trips, dose_sum,
                                    km_sum, modes{}, dev_all{hash},
                                    dev_ts{hash:[ts]}, vals[[ts,C]]}
                                  _HOURS[utc-hour] += {trips, devices{},
                                    dose_ug, km, modes{}, last_ts}
                                  _DAYS[YYYY-MM-DD] += {trips, dose_sum,
                                    km, modes{}, devices{}, last_ts}
                                  _LIFE += {trips, km, dose_ug,
                                    avoided_ug, last_ts}
                                  _DEVICES.add(hash)   (count only)
                                   │
                _save() writes BOTH (aggregates only — _snapshot()):
                  • server/data/community.json
                  • s3://$COMMUNITY_BUCKET/community/state.json
                    (≥60 s apart, when bucket set)
                  • legacy v1 files fold once at load, then re-save
                    (points-era rows are DROPPED — never re-persisted)
                                   │
        GET /community (public)    ▼
   totals: obs_total, obs_24h,  totals() — _LIFE + _HOURS window sums
   contributors, km_24h, dose_ug_24h,
   avoided_*, modes_24h,
   top_corridors ◄── corridors() — _CELLS rows where
     ~500 m cells, k≥3:            len(dev_all)>=3 AND last_ts ≤72 h
                                   (below-k cells do not appear at all)
                                   │
        citizen field (feeds the model)     ▼
   corridor_field_samples() — per cell, median implied PM2.5 over
     fresh vals; publishes only with ≥3 fresh traversals AND
     ≥3 devices with a fresh traversal (dev_ts, 72 h windows)
                                   │
        GET /admin/api (Bearer token / loopback)   ▼
   contributors_detail() — UTC-DAY rollups + distinct-device count
   recent_obs(20)        — HOUR buckets, each published only at k≥3
                           distinct devices
   live_reports()        — hazard pins (no contributor field exists)
   corridors(10)         — same gated cells as /community
                                   │
   └─► device-side delete: clearAllData() wipes settings.json,
       ledger.json, contributor.txt, intro_seen.txt
       + DELETE /v2/ledger (X-Device-Token header) wipes the
       per-device ledger rows. Corridor aggregates are anonymous
       counters — not retractable, by design.
```

## Side stores (not trip data)

```
 /v2/plan ──► RouteStore.put({geometry, mode, duration_s, vehicle})
              route_id → record, TTL 1 h, cap 500   store.py:22-57
              consumed by GET /v2/strip             server/v2/strip.py:42-82
              ⚠ holds the requested origin→destination geometry in memory

 Hazard report: POST /report → _reports, snapped 3 dp (~110 m),
                6 h TTL, no contributor at rest     main.py, community.report()
                served publicly as GeoJSON points   GET /reports
                (no shipped client posts to it today)

 Reviews: POST /v2/feedback → _reviews {ts, stars, note, build} —
          no token/device id; note coord-patterns redacted to ~1 km
          at ingest; note bodies publish only at ≥3 reviews
          (main.py, community.add_review/_redact_note)
```

## What is never in this diagram

- no login, no account table, no PII fields anywhere in the payloads;
- `/v2/trip`: no raw trajectory at rest, no raw token at rest;
- the community store: no per-trip row exists — only cell/hour/day
  aggregates and the hashed-device sets the k≥3 gate needs.
