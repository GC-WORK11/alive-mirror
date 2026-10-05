# Ingest cold-build — where the 25 min goes, and what shipped

Lane: `docs/lanes/ingest-coldbuild.md`. Base: `base/v2`. Evidence:
`/ecs/alive108` (ap-south-1) + `s3://alive108-air/field/` key timings +
a local profile of `run_index_once` with injected inputs.

## The honest finding first

**The first build after a deploy is usually NOT slow.** Sampling recent
task boots against S3 `LastModified` of the first `field/` key: cold
tasks landed their first snapshot **13–54 s** after start. The observed
22:18-boot → 22:43-key hole is real but it is not "build takes 25 min" —
it is *no completed iteration for 25 min*: the snapshot key is named by
build **start** minute (`built_epoch` is captured at `build_field`
entry), so key 2243 means a build *started* at 22:43. What happened in
the gap — and what keeps happening mid-flight (task f8537b2b's iteration
2 ran >20 min before the next rollout killed it) — is that an iteration
occasionally enters a **pathological serial-fetch path** and either
finishes absurdly late or dies with the task.

Why it was invisible until now: `log.info` never reaches
`/ecs/alive108` in this deployment (zero INFO-level events all week) —
only WARNING+ lines show. Every stage timer below is emitted at
`log.warning`, matching the existing "engine reweight done" pattern.

## Stage breakdown (where time can actually go)

`run_index_once` = `build_field` → `serialize` → `store_blob` →
`rotate_snapshots` → `_emit_metrics`.

| stage | measured / bounded cost | verdict |
|---|---|---|
| fetch: met | 1 open-meteo call | trivial |
| fetch: model | 1 CAMS call | trivial |
| fetch: fires | **4 global FIRMS CSVs, serial, 45 s timeout each, ×2 retry** | up to ~6 min pathological; whole 24 h global CSVs are multi-MB |
| fetch: stations → WAQI (live route) | **≤64 `/feed/@uid` serial × ≤3 attempts × 30 s timeout, +429 backoff 5→60 s, whole chain ×2** | the dominant tail — >100 min worst case |
| fetch: stations → OpenAQ fallback | **~50 `/locations/{id}/latest` serial × 30 s, ×2** | ~50 min worst case |
| fetch: stations → CPCB fallback | serial per-state pages | dead route in prod (api.data.gov.in TCP-refused from task egress) |
| prior + QC + Kalman + krige fit | ms-scale (fresh `AirField()` per build → Kalman `_smooth` is a first-call passthrough anyway) | not the hole |
| cell loop over the grid | **14,155 cells** (H3 res-8 NCR, not the brief's 784): ~40–70 ms locally, ~100 ms serialize | not the hole — even ×50 task contention it's seconds |
| serialize + S3 put | ~100 ms + one ~0.5 MB gz put | trivial — but a failed put degraded to local disk **silently** (`note` returned, never logged) |
| rotate + metrics | ms | trivial |

Cold-start amplifiers: on a fresh task every leg is cold (DNS, TCP+TLS,
no keep-alive reuse), and the ingest thread launches at the *top* of
`_lifespan` alongside the warm fleet (routegraph build, reweight loop,
transit) — CPU contention inflates everything a bit, but the math above
is dominated by serial network legs × timeouts × retries, not CPU.

## What shipped (all in `server/`)

**(a) Stage-timing observability — always.** Three WARNING lines per
iteration, CloudWatch-visible today:

```
alive.airindex ingest fetch wall=821ms met=410ms[ok] model=410ms[ok] fires=819ms[ok] stations=406ms[ok]
alive.airindex ingest build: fetch=0ms prior=0ms qc_kalman_krige=0ms cells=40ms total=41ms n_cells=14155 stations=1 grid=h3
alive.ingest   ingest run: build=41ms serialize=108ms store=402ms[s3] gc_metrics=1ms total=552ms -> s3://alive108-air/field/...
```

Plus `ingest store note: ...` whenever `store_blob` falls back to local
disk — a hole in the durable record that used to be completely silent.

**(b) Speed fix — bounded parallel fetch, the "clearly safe + small"
tier.** All three serial legs parallelized with `concurrent.futures`
and `executor.map`, which **preserves submission order** — bundles keep
byte-identical row/error ordering vs the serial loops, so every
`attempts`/`n`/`skipped`/`requests` assertion the tests make holds
unchanged:

- `fetch_inputs`: met/model/fires/stations run in a 4-wide pool
  (`FETCH_WORKERS`). `fires` still waits on `met` — `smoke_modifier`
  needs the real `wind_deg`; that's one cheap call, not the tail.
- WAQI `fetch()`: per-feed legs on an 8-wide pool (`FEED_PARALLEL`),
  deliberately under the already-shipped `FEED_SEM=12` precedent in
  `grab_async`. Per-call `stats`/`skipped` dicts merge as integer sums
  after the map — identical totals, deterministic regardless of
  completion order. 429/`_SourceDown` per-feed semantics unchanged.
- `_fetch_stations_once` (OpenAQ): per-location `/latest` reads on an
  8-wide pool (`LEG_WORKERS`); the all-failed → `_SourceDown` verdict is
  order-independent and unchanged.
- `_fetch_fires_once`: the 4 FIRMS CSVs on a 4-wide pool; one-CSV-
  missing tolerance and all-failed → `UpstreamError` unchanged.
- CPCB deliberately left serial — dead route in prod, and it sits
  behind WAQI anyway.

Nothing about cadence, snapshot shape, key naming, bundle statuses, or
the archive/`/v2/why`/`/v2/skill` wire contracts changed. The serving
path (`grab_async`, `FIELD.refresh`) is untouched.

## Expected new timing

- Healthy upstreams: fetch wall ≈ **max(source legs) instead of the
  sum** — locally ~0.8 s vs ~1.6 s on 400 ms/sourer fakes, and
  proportionally more on real cold connections (WAQI alone: 20 feeds at
  300 ms went 6.3 s → 1.3 s). First-build-after-rollout should land in
  the same 13–54 s envelope it already does on a clean task.
- Degraded upstream (the actual hole-maker): the >20 min serial tail —
  64 feeds × retries × 30 s timeouts run strictly one-at-a-time —
  collapses roughly 8× (WAQI) and the sources overlap each other, so a
  429-storming upstream now bounds an iteration near its *slowest* leg
  instead of stacking all four. Estimated ceiling ~2–3 min vs >20 min
  observed.
- Not changed, by design: an iteration killed mid-build still loses its
  snapshot (option (c), seed-from-last-provenance, would mask real
  staleness — noted, not shipped), and a task flapping before *any*
  build completes still punches a hole — the window is just much
  smaller now.

## What to watch in CloudWatch after the next rollout

`ingest fetch wall=` names the guilty source with per-source ms and the
bundle's own status (`unavailable: HTTP 429` etc. — verbatim reason
preserved); `ingest build:` splits compute; `ingest run:` splits
serialize/store. If a hole still appears, the first missing `ingest run`
line after a task boot now has a last-seen stage instead of silence.

## Gates

`cd server && PYTHONPATH=core/build312:. .venv312/bin/python -m pytest -q tests`
— all ingest/airindex tests green (92/92). The full suite shows 13
pre-existing failures in `tests/test_reach*.py` / `test_path_*` —
`alive_core.PathEngine` in `core/build312` was built 2026-10-04, before
`reach` landed in `core/src/path.cpp` (2026-10-05); the stale `.so` was
rebuilt via `core/build_ext.sh` so the lane gate runs against current
sources. No test in those files touches the ingest path.
