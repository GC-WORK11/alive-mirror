# Transit first-plan — where the first-plan Metro went, and what shipped

Lane: `docs/lanes/transit-firstplan.md`. Base: `base/v2` @ `b18ac4e`.
Evidence: fresh local boots (macOS box, `uvicorn main:app`), a default-
executor starvation harness reproducing the prod signature, and
`http://65.2.28.40` GETs + `/v2/plan` for OD coverage truth.

## The honest finding first

**The async gap is not inside the transit scan — it is where the scan
was asked to run.** The transit arm fired `asyncio.to_thread(
_transit_options)`, which lands on the loop's *shared default
executor* — `min(32, cpu+4)` ≈ 5 workers on a 1-vCPU task. For the
first minutes of a cold boot that pool is fully squatted by the warm
fleet (routegraph build ~36 s, reprice sweeps, krige grids, gazetteer/
history/community loads, ingest+archive threads). The transit callable
sat in the executor's FIFO queue, never started, and its
`wait_for(TRANSIT_BUDGET_S=12 s)` elapsed → arm counted as missing →
`degraded:["transit"]`, zero GTFS rows. On re-plan the pool had
drained, the callable ran in ~0.5–2 s, and "Metro + walk" appeared —
the exact apk-v4 wart: *"First cold plan painted 22 options without
'Metro + walk'; it appeared on re-plan."*

Why road rows survived on that same first plan: the motorized arm's
AWS `calculate_routes` path builds its `_option` rows **on the event
loop** (no `to_thread`), and the engine arm already owns a private
pool (`_ENG_EXEC`, plan.py — added earlier for the identical reason:
*"a busy moment could queue the engine arm inside its own 8 s
budget"*). Transit was the only high-value arm still on the shared
executor.

Local-boot caveat: on an idle M4 box the pool is not saturated, so a
clean boot serves transit on plan #1 (2.5 s, 23 rows incl. metro+walk)
— the wart only reproduces when the default executor is actually
busy, which is precisely the fresh-Fargate condition the judges hit.

## Reproduction (simulated boot-warm starvation)

Same harness before/after: `max_workers=2` default executor, both
workers held by sleeps longer than the plan window, then
`_options_bounded` on the canonical metro OD (India Gate → Huda City
Centre 28.6129,77.2295 → 28.4593,77.0724 — the 28.4595,77.0266
Gurugram point in the drive note has **zero metro stops inside the
2.5 km access radius**, so the OD was re-anchored to a genuinely
metro-served destination).

| run | first-plan options | modes present | transit? | missing |
|---|---|---|---|---|
| before (starved) | 20 | car×4, car_open, auto×4, bus, bike×4, cycle×3, walk×3 | **none — `plan_transit` never ran** | `["slow","transit"]` |
| after (starved) | 21 | same + **metro+walk×1** | yes — ran on `alive-transit_0` | `["slow"]` |
| fresh boot, fixed, idle box | 23 (4.3 s) | full set incl. **metro+walk** (GTFS, Patel Chowk→Huda City Centre) | yes | none |

The `["slow"]` remnant is honest: `_slow_mode_options`' row-dosing is
also a `to_thread` and starves the same way — real degradation the API
already flags in `degraded` rather than hiding (noted as a sibling
wart below, out of this lane's scope).

## What shipped

- `server/v2/plan.py` — `_TRANSIT_EXEC`: private
  `ThreadPoolExecutor(max_workers=2, prefix="alive-transit")`; the
  transit arm now `run_in_executor`s there under the same 12 s cap.
  Two workers so a plan + a reroute overlap without queueing, but GTFS
  scans can't stack CPU storms. Same fix shape as `_ENG_EXEC`.
- `server/main.py` — `_warm_static` now runs `_transit_options` once on
  the canonical metro OD on the transit pool: pre-pays the first CSA
  scan **and** the lazy `_Grid` rebuild on pickled feeds, so even the
  very first request skips that cold work. Runs the plan arm's real
  callable — nothing fabricated, just earlier.
- `tools/warm_task.py` — `_transit_rows()` counted per plan OD and
  printed beside `engine_rows`; final summary reports how many ODs
  carried GTFS rows and warns when zero do. Previously it only gated
  on engine rows — T-40 could print WARM while transit was silently
  dead.
- `server/tests/test_transit_first_plan.py` — 3 tests:
  `first_plan_transit_survives_executor_starvation` (recreates the
  wart: squatted default executor → asserts a GTFS transit row lands,
  `transit` not in `missing`, callable ran on `alive-transit_*`, and
  the starvation was real via `slow` still flagging);
  `first_plan_transit_option_is_not_fabricated` (empty scan → no row —
  the fix moves *when* the scan runs, never *what* it reports);
  `warm_static_prepays_transit_scan` (lifespan boots → the canonical
  OD scan fires exactly once, on the transit pool).

## warm_task OD coverage — verified

All 12 `WARM_ODS` fired against a local server with compiled feeds:
**8/12 produce ≥1 GTFS transit row** (metro+walk ×5, bus ×several).
The four without — CP→IndiaGate (2 km hop), NehruPlace→Kalkaji,
KarolBagh→Gurgaon(28.4595,77.0266 — no metro stop within 2.5 km
egress), DU→Ghaziabad — are honest geography, not arm failure.
Spot-checked prod (`65.2.28.40`, build `37e55668`): CP→NoidaSec18 and
KashGate→Nizamuddin → metro+walk+bus each; canonical IndiaGate→HudaCC
→ metro+walk, 23 rows, 8.4 s, `degraded:none`.

## Gate

- New tests: `3 passed in 7.57s`.
- Full suite `tests/` (plan.py + main.py changed): **1126 passed,
  5 skipped, 0 failed** in 489 s. First run had 13 pre-existing
  failures in `test_reach`/`test_path_parity`/`test_path_legality` —
  all `'alive_core.PathEngine' object has no attribute 'reach'`, i.e.
  the worktree's `.so` predated `ba63d03` (dose-budget reach).
  Rebuilt via `core/build_ext.sh`; the 41 engine/parity tests then
  passed and the re-run above is fully green.
- Live API used read-only (GETs + `/v2/plan`). **Nothing deployed.**

## Sibling wart, flagged for a later lane

`_motorized_options`' OSRM-fallback `_rows` and `_slow_mode_options`'
`_rows` ride the same shared executor — on a truly contended cold
task both can starve exactly like transit did (seen as `slow` in
`missing` in the starved harness). The AWS Location path shields
motorized in prod; slow rows degrade honestly. A small shared
row-assembly pool would close the shape for good — deliberately left
out of this lane's minimal fix.
