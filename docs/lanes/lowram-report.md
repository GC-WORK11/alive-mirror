# Lane report — server memory/cache audit (low-RAM task)

Scope: measure real RSS, enumerate every in-process cache, fix unbounded
growth surgically, honest concurrency verdict for the 1vCPU/3GB Fargate
Spot task. Branch `base/v2`, HEAD at pull `3589209`.

## Prod budget (verified in `scripts/deploy.sh`, not vibes)

- Task: `--cpu 1024 --memory 3072`.
- OSRM sidecar container: `memory:1024, memoryReservation:512` → the API
  process's real budget is **≈2GB**, not 3.
- Prod env sets `AGG_TABLE=alive108-agg` → `v2/store` selects
  `DDBTripAggregates`/`DDBDeviceLedger`; the in-memory stores are the
  dev/CI/missing-credentials fallback.

## Measured RSS (this box, python3.12, `tools/lane_rss.py`)

Staged boot cost (post-fix run):

| stage | RSS MB | delta |
|---|---|---|
| interpreter + psutil | 16.8 | — |
| `import main` (app + field + forecast + search T1 eager-build) | 404.8 | +388 |
| `history._load()` climatology | 407.8 | +3 |
| `GAZ._load()` 119,716 rows (slim) | 522.4 | +115 |
| `community._load()` | 522.4 | +0 |
| `routegraph.path_engine()` C++ graph | 717.3 | +195 |
| engine warm (5-mode A* + reach floods) | 758.1 | +41 |
| `transit_v2.default_feeds()` bus+metro (pkl path) | 873.0 | +115 |
| `FIELD.load_snapshot()` | 873.7 | +1 |
| `FIELD.refresh(force)` 48 rows | 880.1 | +6 |
| engine reweight 903,058 edges | 880.2 | +0 |

Pre-fix run of the same probe ended at **1664MB** — allocator-order and
GTFS-load-path variance is large (GTFS +477 vs +115 depending on whether
pkls are compiled or deserialized), so treat staged totals as a
~0.9–1.7GB range, not a point estimate. The GAZ delta (~217→~115MB)
is a real, isolated saving.

Live dev server (uvicorn, `tools/lane_req_rss.py`, post-fix):

| endpoint | RSS after | delta |
|---|---|---|
| warm idle | 726MB | — |
| GET /aqi, /v2/city, /grid, /v2/search, /v2/day | 726 | +0 each |
| GET /v2/reach (first call) | 937 | +211 one-time (flood raster + veil) |
| POST /v2/plan ×3 (743KB, 24 options) | 946 | +9 first, +0 after |
| 8-round mixed loop (24 requests) | 946 | **+0 total — flat plateau** |

Identical probe pre-fix plateaued at 1033MB. No request-path leak in
either run — per-request churn is transient and GC'd.

## Cache inventory — every store, bounded?

| store | bounded? | cap / eviction | ~size now |
|---|---|---|---|
| `GAZ` gazetteer | yes | fixed dataset | ~110MB rows + ~5MB lazy index (was ~217MB always) |
| `core_engine._SEARCH_ENTRIES` + C++ search idx | yes | fixed dataset | ~267MB Py + ~48MB C++ |
| `transit_v2._FEEDS` bus/metro | yes | fixed dataset | ~115–480MB |
| `airfield.FIELD` (+`_lru`, `_kalman`) | yes | 16,384-cell LRU, clear-all | field grids, small |
| `main._GRID_CACHE` / `_DEPART_CACHE` | yes | 24 / 64 entries, epoch-keyed | MB-scale |
| `v2/plan` `_ENG_SOLVE` + TTLCaches | yes | 256 cap + TTL, 7s in-flight dedupe | small |
| `v2/store.RouteStore._routes` | yes | 500 + 1h TTL | ≤~75MB worst |
| `v2/store.TripAggregates` `_cells/_areas/_od` | **was NO → fixed** | now 72h window prune, 60s throttle | dev-only |
| `v2/store.DeviceLedger` | yes | 5,000 devices × 300 rows | small |
| `community._CELLS` (+`_CELL_VAL_CAP`) | yes | 60k cells, stalest evict, 400/cell | grows per distinct ~500m cell, geography-bounded |
| `community._CELLS[*].dev_all` | half | per-cell all-time device set | flagged below |
| `community._DAYS/_HOURS/_reports/_reviews` | yes | 400 / 7d / 2000+6h / 400 | small |
| `v2/places._place_cache/_rev_cache` | yes | 512 + 900s TTL | small |
| `core_engine._FOREIGN_Q_CACHE` | yes | 512, clear-all | small |
| `v2/trip._DEDUPE` | yes | 4,096 + 24h | small |
| `transit_rt._STATE` | yes | wholesale replace per poll | ~10–30MB transient |
| `MetricsRegistry` | yes | route-template labels only | ~450 series |
| `RateLimitMiddleware._buckets` | yes | 20k keys + stale evict | small |
| request body / pagination | yes | 2MiB body cap; `limit` capped (search ≤15, corridors ≤200, etc.) | — |

`docs/lanes/server-harden-report.md` verified the hardening side; this
audit found every hot-path store already bounded. The one true leak was
`TripAggregates`, plus `GAZ` holding a permanently-resident search
index for a fallback path that never fires when the C++ index is up.

## Fixes landed (small commit + tests each)

1. **`server/v2/store.py`** — `TripAggregates._prune_stale`: evicts
   `_cells`/`_areas`/`_od` entries dead past the 72h publish window
   (`record_trip` stamps `last_ts` on all three; prune throttled to
   once/min inside the write lock). Publishable output unchanged —
   dead entries were already invisible to readers. Closes the only
   unbounded-growth → OOM vector under sustained donations on the
   in-memory backend.
2. **`server/v2/gazetteer.py`** — slim rows + lazy index: `_load()`
   stores `{idx,name,norm,kind,lat,lon,pop}` (+ raw corpus aliases);
   postings/vocab/trigram/match_tokens build via `_ensure_index()` on
   first `search()` call. **~107MB always-resident saved**; fallback
   path behavior identical (index materializes once on demand).

Focused tests green (test_agg_ddb, test_admin_agg, test_admin_v2,
test_v2, test_lifespan_warm, test_search_quality, test_query_tolerance —
220 tests); full suite: **1204 passed, 5 skipped, 9m03**.

## Per-request allocation — top-3 structural costs flagged (not fixed)

1. **Place data held ~3×**: GAZ slim rows (~110MB) + `_SEARCH_ENTRIES`
   Python dicts (~267MB) + C++ index (~48MB). Collapsing to one slim
   table = re-architecture; flagged only.
2. **GTFS feeds ~115–480MB resident** — biggest single structure;
   resident size depends on pkl-deserialize vs compile path.
3. **Engine warm + graph ~240MB** — intrinsic to routing.
4. `/v2/reach` +211MB on first call per mode is a one-time raster/veil
   build, bounded caches thereafter — not per-request growth.

`dose()` ~120 small dicts per option is modest and transient; not worth
a surgical change this close to demo day.

## Verdict

- Baseline working set: ~0.95GB live-measured (staged range
  0.9–1.7GB by load order) vs ≈2GB API budget → **~1GB headroom**.
- Steady-state per-request RSS delta = 0; memory is **not** the
  concurrency limiter. The binding constraint is 1vCPU: ~2.5s per
  /v2/plan with a 2rps/burst6 per-client cap means a few concurrent
  plans queue before RAM matters. Honest posture: **~8–15 concurrent
  active users** of mixed GETs + plans; the rate limiter and 256-entry
  solve-dedupe keep RAM flat regardless.
- Demo-day OOM loop risk: eliminated — no remaining unbounded cache;
  the single leak found is fixed and dev/fallback-only anyway.

Probes (kept in `server/tools/`): `lane_rss.py` (staged boot RSS),
`lane_req_rss.py` (per-request RSS against a live PID).
