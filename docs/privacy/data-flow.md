# Data flow — what a donated trip becomes

Two donation paths exist in the tree. **Path A** (`/v2/trip`) is the
hardened pipeline the privacy spec (docs/plan/07 §3) describes.
**Path B** (`/observe`) is the older community layer the app calls today.
Both are drawn so the gap is visible, not hidden.

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

## Path B — POST /observe (what the app calls today)

```
 phone                                                  server
 ─────                                                  ──────
 compare screen, option selected
 gate: shareEnabled (settings.share, default ON)
   Mobile/src/components/shell/useShellFlow.ts:168
   │                                    POST /observe   server/main.py:704
   │  geometry of the CHOSEN OPTION      community.observe()
   │  (planned route — NOT a GNSS trace,  server/community.py:107
   │   index-thinned to ~60 pts,           • points rounded 5 dp (~1 m) :119
   │   endpoints included —               • ≤400 points                 :120
   │   NO 300 m trim)                     • contributor stored raw ≤16c  :118
   │  + contributor "anon-XXXXXXXX"              │
   │  (generated once, never rotates,            ▼
   │   Mobile/src/community.ts:16)        _obs list (≤20 000 rows)      :39,57
   │                                        + _reports (6 h TTL)        :27,40
   │                                             │
   │                          _save() writes BOTH:                      :83-99
   │                            • server/data/community.json
   │                            • s3://$COMMUNITY_BUCKET/community/state.json
   │                              (≥60 s apart, when bucket set)
   │                                             │
   │        GET /community (public)             ▼
   │   totals: obs_total, obs_24h,        community.totals()            :318-346
   │   contributors, km_24h, dose_ug_24h,
   │   avoided_*, modes_24h,
   │   top_corridors ◄── corridors()      community.corridors()         :294-315
   │     ⚠ ~500 m snap cells ranked by
   │       sample count — NO k≥3 device threshold
   │
   │        citizen field (feeds the model)      ▼
   │   corridor_field_samples()           community.py:224-260
   │     per ~500 m cell: median implied  • needs ≥3 FRESH traversals    :255
   │     PM2.5, traversals ≤72 h only       (not ≥3 distinct devices)
   │     (_OBS_FRESH_S, :221)
   │
   │        GET /admin/api (NO AUTH)             ▼                      main.py:885
   │   contributors_detail()              per-id trips/km/dose/last_seen :149-177
   │   recent_obs(20)                     rows incl. contributor id      :180-187
   │   live_reports()                     kind+point+contributor         :190-197
   │   corridors(10)                      same unthresholded cells       :294
   │
   └─► device-side delete: clearAllData() wipes settings.json,
       ledger.json, contributor.txt, intro_seen.txt
       Mobile/src/components/shell/settings.ts:45-52
       (server rows are NOT touched — no delete-by-id endpoint exists)
```

## Side stores (not trip data)

```
 /v2/plan ──► RouteStore.put({geometry, mode, duration_s, vehicle})
              route_id → record, TTL 1 h, cap 500   store.py:22-57
              consumed by GET /v2/strip             server/v2/strip.py:42-82
              ⚠ holds the requested origin→destination geometry in memory

 Hazard report: POST /report → _reports, 6 h TTL   main.py:717, community.py:127-135
                served publicly as GeoJSON points   GET /reports, main.py:728
                (client wrapper exists; check current UI wiring —
                 Mobile/src/community.ts:44)
```

## What is never in this diagram

- no login, no account table, no PII fields anywhere in the payloads;
- `/v2/trip`: no raw trajectory at rest, no raw token at rest;
- `/observe` rows carry a pseudonymous contributor id — linkable within
  that store until it rolls off the 20 k cap or the file/bucket is wiped.
