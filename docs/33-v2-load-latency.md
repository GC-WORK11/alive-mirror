# /v2 load & latency — demo-day numbers (Oct 5, measured live)

Measured against the running service on `c3d9c111` (ECS Fargate 1 vCPU,
single uvicorn worker) with `tools/load_v2.py` — bounded probing:
≤8 concurrent virtual clients (each its own `x-device-token`, matching
the server's per-client rate bucket), ≤25 s bursts, abort-on-5xx.
Zero 5xx/429 in any phase.

The probe box sits far from ap-south-1: ~220 ms keep-alive floor on every
number below (TCP connect ~230 ms). "srv" = the endpoint's own `took_ms`
where it reports one — the honest server-side figure; client numbers
include network.

## Baseline — sequential, one client

| endpoint | n | client p50 | client p95 | server side |
|---|---|---|---|---|
| `GET /v2/day` | 20 | 227 ms | 229 ms | ~10 ms |
| `GET /v2/outlook` | 20 | 290 ms | 292 ms | ~70 ms |
| `GET /v2/reach` walk≤50 µg | 15 | 675 ms | 1094 ms | solve 31–33 ms |
| `GET /v2/reach` car≤100 µg | 12 | 4614 ms | 4679 ms | solve 1133–1464 ms |
| `POST /v2/plan` CP→Gurugram | 15 | 1050 ms | 1477 ms | 532–960 ms |
| `GET /grid?h=0` | 20 | 252 ms | 254 ms | ~30 ms |
| `GET /aqi` | 20 | 224 ms | 234 ms | ~10 ms |
| `GET /city` | 12 | 226 ms | 228 ms | ~5 ms |
| `GET /admin` | 12 | 238 ms | 305 ms | ~80 ms |

`/v2/plan` had one 8.35 s cold-reprice outlier (first call pays the
raster price — expected, once per field refresh).

## Concurrency — what a judge pair actually does to it

| mix (25 s bursts) | result |
|---|---|
| 4×day + 4×outlook (622 req) | day p50 318 / p95 336; outlook p50 318 / p95 336 — **healthy** |
| 4×grid + 4×day (647 req) | grid p50 279 / p95 502; day p50 282 / p95 576 — **mild** |
| 4×reach-w50 + 4×plan | reach p50 3992 (srv 1263); plan p50 4174 (srv 3257) — the 3-worker engine executor queues |
| **2×reach-c100 + 4×day + 2×outlook** | reach srv p50 3967 / p95 8166 (hit the 8 s solve bound once → honest timeout); **day p50 896 / p95 2953; outlook p50 886 / p95 2961 — 13× starvation** |

## The actual bottleneck (not what it looks like)

The reach Dijkstra never blocked the loop — it runs on `plan._ENG_EXEC`
(3 workers) and the C++ engine releases the GIL. The starvation was the
**response machinery**: after a ~1.1 s solve, a car≤100 veil spent
~2.4–3.4 s on the single event-loop thread — `jsonable_encoder` +
`json.dumps` of ~90 000 edge lists (3.5 MB), then gzip level-9
(~0.8–0.9 s). While that ran, every day/outlook/grid request queued
behind it.

## What changed (commit `d6e6607`, `base/v2`)

1. **reach**: veil serialized off-loop (`run_in_executor` default pool —
   never the engine workers) and returned as pre-encoded `Response`
   bytes. New 60 s cache stores the *bytes* keyed by
   `(mode, budget, ~11 m anchor cell, field epoch)`: a repeat hit costs
   ~0 loop CPU, splices `took_ms` to real serve time, and marks
   `x-alive-cache: hit` (`miss` on a fresh solve — declared, never
   silent). Errors are never cached.
2. **day / outlook**: 60 s payload cache keyed `(cell, hour, data_epoch)`
   — the 24–120×`_hour_entry` fold was the recompute-per-request cost.
   `_refresh_both()` still runs on every request (refresh cadence
   untouched); the cache key carries the field/forecast epoch so a
   mid-TTL data refresh invalidates immediately.
3. **gzip**: `compresslevel` 9→4. On the real 3.56 MB veil: 878 ms→78 ms
   compress CPU for 1.14 MB vs 1.03 MB wire (+11 %). The wire was already
   ≥1 MB; the loop time was what starved judges.
4. `deps.TTLCache` + `deps.data_epoch()`; 8 new tests
   (`tests/test_v2_cache.py`) — 235 tests green across the touched
   suites.

## Projected post-fix (labeled: deployed only after next image build)

| endpoint | before | projected after |
|---|---|---|
| reach walk≤50 warm | ~675–1100 ms | ~250–400 ms; **cached ≈ RTT** |
| reach car≤100 warm | ~4600–4700 ms | ~1600–2600 ms (solve ~1.2 s + gz4 ~0.3 s loop + ~1.1 MB wire); **cached ≈ RTT** |
| day/outlook under 2×c100 mix | p95 ~2950 ms | ~400–700 ms (loop work per veil ~3.4 s → ~0.3–0.5 s) |

## Numbers the team can quote

- "reach walk≤50 µg: ~30 ms to solve on the server, under a second
  door-to-door" — and same-spot repeats are near-instant on the 60 s
  veil cache.
- "reach car≤100 µg is inherently multi-second — it's a settled-edge
  map of a whole metro area, ~1 MB gzipped. Narrate it as the heavy
  query, or demo it on `budget_ug=50`/walk."
- "/v2/day + /v2/outlook answer in tens of milliseconds server-side and
  hold up under an 8-way judge-pair burst (p95 ~340 ms incl. far-away
  RTT)."

## Residual risks — honest

- **car≤100 stays ~4.5 s pre-deploy / ~2 s post-deploy.** It is the
  heavy query by design (`edge_partial:true` — the veil is already
  capped at 90 k served edges of ~1.03 M settled). Decimation or
  `EDGE_SERVE_MAX` is a product call, not a perf bug.
- A fresh car≤100 *miss* during other heavy traffic still timeshares
  one vCPU — lighter endpoints degrade some, but ~5–10× less than the
  pre-fix starvation.
- `edges_e6`→e5 precision would save only ~10–16 % wire (measured),
  under the 30 % bar, and changes the wire contract — not done.
- `_ENG_EXEC` stays at 3 workers: on 1 vCPU more threads don't add CPU,
  they add queue shuffling. Engine mixes (reach+plan) queue honestly.
- Per-client rate limit (10 rps sustained / 30 burst, per
  `x-device-token`): a judge hammering refresh >10 rps sees honest 429s
  with `Retry-After` — by design, surfaced not hidden.
- Cold task (post-deploy): field + raster reprice ~45–60 s once —
  the runbook's T-60 rule already covers it; the caches only help warm.
