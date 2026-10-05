# Cold path — server-side latency for a judge's first touch (2026-10-05)

## The question

Tonight's live measure put a cold `/v2/plan` at **6650 ms** while warm
re-hits answer in ~120 ms. A judge's FIRST touch is exactly the cold
path. This lane: instrument every stage, fix what's cheap and safe,
and say honestly what stays cold and why it can't hurt the demo.

All live numbers below are `curl -w` on the ELB
(`alive108-…elb.ap-south-1.amazonaws.com`, build `033aa866`, task
long-running = the post-warm state). "Cold task" costs that only exist
inside the first ~2 min of a Fargate task are taken from in-code
measurements (2026-10-04 boot logs) since they can't be re-measured on
the running task; they're marked *(boot-log)*, not re-verified.

## Live measurements — GET surfaces

| surface | cold/first hit | warm | payload | what the time is |
|---|---|---|---|---|
| `GET /` (landing) | 0.45 s ttfb ×5 | 0.45 s | 75 KB | FileResponse — pure RTT to ap-south-1, no upstream in request path |
| `GET /city` | 0.44–0.47 s ×4, one 1.22 s | 0.45 s | 75 KB | FileResponse; the 1.22 s is a transient, not structural |
| `GET /admin` | 0.45 s ttfb ×5 | 0.45 s | 125 KB | FileResponse + ~0.7 s of body transfer on a US-side pipe |
| `GET /v2/day` | 0.48 s → 0.44 s | 0.44 s | 5.6 KB | 60 s epoch cache; RTT-bound |
| `GET /v2/why` | 0.45 s | 0.45 s | 1.3 KB | bounded field+fires refresh, both TTL-gated |
| `GET /v2/outlook` | 0.57 s → 0.44 s | 0.44 s | 4.2 KB | epoch cache |
| `GET /v2/skill` | 0.56 s | 0.55 s | 1.3 KB | static advisory fold |
| `GET /v2/archive` | 0.93 s | 0.92 s | 22 KB | S3 `list_objects_v2` + one `get_object`+gunzip per recorded hour, all off-loop |
| `GET /v2/city` | 1.93 s → 0.98 s | 0.98 s | 6.1 KB | awaits a bounded field refresh (≤10 s) + corridor naming; needs the field it renders |
| `GET /v2/search` | 0.46 s | 0.45 s | 3.3 KB | gazetteer pre-warmed in lifespan |

No page or GET endpoint exceeds 1 s ttfb when the task is warm; the
only first-hit outliers are `/v2/city` (real bounded refresh) and the
transient `/city` spike. **Nothing to fix on the pages.**

## Live measurements — engine surfaces

| surface | cold/first hit | warm | payload | what the time is |
|---|---|---|---|---|
| `POST /v2/plan` (CP→Saket) | 6650 ms *(tonight, fresh task)* → 2662 ms *(warm task, new OD)* | 121–131 ms repeat | ~200 KB | see stage decomposition below |
| `GET /v2/reach` walk@25 | 3.76 s ttfb | 0.45–0.52 s | 86 KB | Dijkstra solve + first byte-cache fill → byte hit |
| `GET /v2/reach` walk@50 | — | 0.49 s | 347 KB | settled 8 695 edges |
| `GET /v2/reach` car@25 | 1.89 s ttfb | 3.66 s total | **3.56 MB** (1.14 MB gzipped wire) | settled **866 102** edges, serves capped 90 000 |

## Cold `/v2/plan` — stage decomposition

Measured locally (`.venv312`, `core/build312`) plus the boot-logged
Fargate costs. A cold plan runs four arms under `PLAN_BUDGET_S=20 s`
(`asyncio.wait` at `PLAN_BUDGET-2 = 18 s`): motorized (local OSRM ~2 ms
on prod — `osrm-local` confirmed live), slow (2 parallel local OSRM),
engine (`_ENG_EXEC`, `ENGINE_BUDGET_S=8 s`), transit (`TRANSIT_BUDGET_S
=12 s`).

| stage | this box | fresh Fargate task | once-per-task? |
|---|---|---|---|
| route-graph load (`path_engine`) | 0.22 s | ~36 s *(boot-log)* | yes — warmed in `_lifespan._warm_engine` |
| field first refresh (upstream fetch) | 2.9 s | ~96 s to serving *(boot-log)* | yes — `_warm_field` starts it at boot; plan fires it best-effort |
| engine reprice: live-field raster + C++ sweep | 0.26 s *(snapshot FieldView)* | raster ≤12 s budget + sweep seconds | per epoch — `_warm_engine` retries until priced |
| first A* solve / mode (traversal structures) | ~80 ms/mode | ~9 s first *(boot-log)* | yes — `_warm_solve` burns all 5 modes at boot |
| transit GTFS connection scan | 0.42 s | compiled at boot (feeds baked in image) | per-OD scan |
| OSRM route query | 0.55 s public-demo first hit → 0.18 s warm | ~2 ms (`osrm-local` sidecar, verified live) | keep-alive after first |
| whole engine arm (5 primaries + alts) | 0.78 s | ~2–3 s per new OD | per-OD, cached in `_solve_join` |

**Where the 6650 ms went** *(inference — can't instrument prod; the
composition is what the code forces)*: a plan landing while the boot
raster sweep still runs gets (a) the engine arm's busy-join wait —
`ENG_BUSY_JOIN_S=3.5 s` — then likely no priced edges →
`degraded:["engine"]`; (b) motorized+slow rows dosing on the live
krige per segment — the priced raster doesn't exist yet, and honest
dose reads on one vCPU cost seconds; (c) the first transit CSA scan on
cold structures; all of it CPU-starved by the concurrent raster sweep
on the same core. The number is real; it is also exactly what the T-40
`warm_task.py` run eliminates.

## Fixes landed

**1. `/v2/reach` veil now paints the real region** (`v2/reach.py`)
Settle order is dose-ascending, so `ids[:90_000]` painted only the
cheapest ~10 % core around the anchor. Now a uniform stride across
settle order serves the same 90 000 edges spanning the full settled
extent — same wire size, same cap, `edge_partial` still honest.

| | before (`ids[:N]`) | after (strided) |
|---|---|---|
| served bbox (flat-120 field, car@25) | lon 77.11–77.35, lat 28.53–28.72 (~24×22 km blob at CP) | lon 76.96–77.52, lat 28.38–28.87 (**~56×56 km — all of reachable NCR**) |

`city.html`'s partial-veil caption updated to match ("a uniform
sample", was "the nearest"), `Bridge/contract.ts` comment updated.

**2. Raster sweep yields the core** (`v2/plan.py::_engine_field_view`)
`time.sleep(0)` every 64 lattice cells so a request landing mid-sweep
gets OS scheduling slots on the single vCPU instead of waiting out
whole quanta. ~µs per yield, budget cap unchanged — the once-per-task
reprice is exactly when a cold hit can land.

**3. `tools/warm_task.py` coverage** — was: health/aqi/grid/plan×12/
reports/city/grid?h=12/day/reach-walk@25/outlook/community/tiles.
Added: `reach walk@50` + `reach car@25` (the city page's mode×budget
pills; car@25 is a ~1.3 s solve + 3.5 MB encode on a fresh cache),
`/v2/why`, `/v2/skill`, `/v2/archive`. The `fast:true` engine-first
paint needs no separate warm — it shares `_solve_join`'s prim cache,
filled by the regular plan calls.

## What stays cold — and why it can't hurt the demo

| stays cold | cost | why it's honest | covered by |
|---|---|---|---|
| graph load ~36 s | once per task | a packed 1.07 M-edge graph must decode somewhere; the request path never loads it | `_lifespan._warm_engine` at boot |
| field first fetch ~96 s | once per task | real upstream data; can't fake freshness | `_warm_field` at boot |
| raster reprice ≤12 s/epoch | once per field epoch | bounded + now yields; CPU-bound repricing of 1.2 M edges on 0.5 vCPU is irreducible | `_warm_engine` retry loop + warm_task's plan arm |
| first-hit plan dose bands on live krige | seconds, only pre-first-pricing | honest dose needs real reads; serving raster-priced numbers before the raster exists would be a lie | ordering: warm_task plans land after the raster |
| `/v2/city` bounded refresh ≤10 s | cold only | the card IS the field; an instant empty card is worse | `_warm_field` + warm_task `/v2/city` |
| `/v2/archive` ~0.9–1.1 s | every hit | S3 list + per-hour reads, off-loop; a TTL cache would trade freshness a judge can't see for a second hit she won't notice | warm_task now covers it |
| car@25 veil 3.56 MB body | every uncached combo | capped at 90 k edges + gzip → 1.14 MB wire; client already chunk-paints across frames | reach warm calls in warm_task |

## Morning-of re-run items (owner)

1. T-40 (or immediately post-deploy): `python3 tools/warm_task.py` —
   must print `WARM: priced engine serving after Ns`.
2. Spot-check one `POST /v2/plan` on the demo OD: `took_ms` should be
   < 1 s, no `degraded` key.
3. `GET /health`: `edges_priced>0`, `transit.compiled`=[bus,metro],
   `field_stale:false`.
4. One `GET /v2/reach?…mode=car&budget_ug=25` on the demo anchor — the
   veil combo this lane just made worth showing.
5. If the task restarted < ~2 min before judging: re-run warm_task —
   the first plan may still serve `degraded:["engine"]` while the boot
   raster finishes; that's the 6.6 s path, and it self-heals.

## Test status

`PYTHONPATH=core/build312:. .venv312/bin/python -m pytest -q tests` —
**1110 passed, 5 skipped** on this branch after the reach/plan edits.
