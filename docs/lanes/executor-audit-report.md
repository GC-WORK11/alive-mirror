# Lane report — executor-audit

Every `asyncio.to_thread` / `run_in_executor(None)` arm in the request
path, audited against the boot-warm squat. Follows `fa08e96` (transit +
engine got `_TRANSIT_EXEC`/`_ENG_EXEC`); this lane closes the class.

## The class

`to_thread`/`run_in_executor(None)` land on the loop's **shared default
executor** (`min(32, cpu+4)` ≈ 5 workers on the 1-vCPU task). The cold-
boot warm fleet (routegraph build ~36 s, reprice sweeps, krige grids,
gazetteer/history/community loads, ingest + archive capture) squats
every worker for a fresh task's first minutes, so any arm on that pool
queues behind it. In `_options_bounded` the starvation is silent and
total: `asyncio.wait(..., PLAN_BUDGET_S - 2)` cancels the whole arm
coroutine, so rows it had already fetched are dropped and the arm
reports `degraded`. For uncapped GETs the same squat is a wall-clock
stall with no degraded flag — the judge-perceived version of the wart.

Second wart shape found this lane: work that never went near an
executor at all — sync CPU running **on the event loop** (motorized
AWS-path dose rows, `build_why`'s snapshot tail). Not queue-starved,
but it parks every other request behind it; the same fix (a private
bounded pool) retires both shapes.

## Arm × executor × starved? × fix

| arm | before | starved? | cap | after |
|---|---|---|---|---|
| plan `motor` OSRM-fallback `_rows` | shared default (`to_thread`) | **YES** — cancelled whole, `degraded:[motor]` | 18 s plan window | `_ROWS_EXEC` (4, `alive-rows`) |
| plan `motor` AWS-path `_option` dosing | **event loop** (no executor) | loop-blocker — cold-krige dosing parks all requests | same | `_ROWS_EXEC` |
| plan `slow` `_rows` | shared default (`to_thread`) | **YES** — `degraded:[slow]` | 18 s plan window | `_ROWS_EXEC` |
| plan `engine` | `_ENG_EXEC` | already fixed (fa08e96) | `ENGINE_BUDGET_S` 8 s | unchanged |
| plan `transit` | `_TRANSIT_EXEC` | already fixed (fa08e96) | `TRANSIT_BUDGET_S` 12 s | unchanged |
| `v2/search` `_t1` gazetteer tier | shared default (`to_thread`) | **YES** — uncapped stall (repro: 969 ms on `bootwarm`) | none | `_T1_EXEC` (2, `alive-t1`) |
| `/v2/skill` payload | shared default | **YES** — uncapped stall | none | `_SKILL_EXEC` (1) |
| `/v2/archive` day payload | shared default | **YES** — uncapped stall | none | `_ARCHIVE_EXEC` (1) |
| `/v2/reach` encode (`_json_bytes`) | shared default | **YES** — full warm window added post-solve | `REACH_BUDGET_S` 8 s covers solve only | `_ENCODE_EXEC` (1) — deliberately off `_ENG_EXEC` so a multi-MB serialize never holds an engine slot |
| `/v2/reach` `_solve` | `_ENG_EXEC` | already fixed | 8 s | unchanged |
| `/v2/why` read+score tail (`_snapshot_series` etc.) | **event loop** | loop-blocker — S3 enumeration + multi-MB deserializes on `MainThread` | none | `_WHY_EXEC` (2) — whole sync tail |
| `main._aws_suggest` / `get_place` fan-out / `_aws_reverse` (boto3) | shared default | **YES** — `/search` + `/reverse` first-touch surfaces | none | `_AWS_EXEC` (4, `alive-aws`) |
| `admin_agg /status` `archive.status` | shared default | **YES** — ops surface | none | `_ADMIN_EXEC` (1) |
| `main._warm_*` fleet, archive capture, ingest workers, `_s3_series` inner `ThreadPoolExecutor(8)` | shared / local pools | background work — correct as-is | n/a | unchanged |
| `v2/trip`, `city`, `day`, `outlook`, `strip`, `ledger` | sync on loop | cheap CPU only, no executor calls | n/a | unchanged |

## Reproduction (starved default executor, 2 squatters × 5 s)

Before:

    probe_ran_early: [('bootwarm_0', 5.01)]   (probe queued 5 s — squat real)
    plan: 4041 ms, options=2, modes=['car','metro'], missing=['motor','slow']
      _option threads: ['alive-transit_0']
    search _t1: 969 ms, threads=['bootwarm_0']
    skill/archive/aws_suggest/aws_reverse: threads bootwarm_*
    why: series_threads=['MainThread']        (loop-blocker, different shape)
    encode: threads=['bootwarm_0']

After:

    probe_ran_early: []                        (never got a worker — squat held)
    plan: 6 ms, options=9, modes=[auto bike bus car car_open cycle metro walk],
          missing=[]
      _option threads: ['alive-rows_0','alive-rows_1','alive-transit_0']
    search _t1: 0 ms ['alive-t1_0']; skill ['alive-skill_0'];
    archive ['alive-archive_0']; aws suggest+reverse ['alive-aws_0'];
    why ['alive-why_0']; encode ['alive-encode_0']

## Files

- `server/v2/plan.py` — `_ROWS_EXEC`; motorized AWS `_aws_rows` + OSRM
  `_rows` + slow `_rows` all dose on it.
- `server/v2/search.py` — `_T1_EXEC`.
- `server/v2/skill.py` — `_SKILL_EXEC`; `v2/archive.py` — `_ARCHIVE_EXEC`.
- `server/v2/reach.py` — `_ENCODE_EXEC`.
- `server/v2/why.py` — `_WHY_EXEC`; whole sync tail off the loop.
- `server/main.py` — `_AWS_EXEC` for the three boto3 call sites.
- `server/admin_agg.py` — `_ADMIN_EXEC`.
- `server/tests/test_executor_starvation.py` — 8 regressions, starved-
  pool harness + probe: each arm lands inside its window on its own
  `alive-*` pool.
- `server/tests/test_transit_first_plan.py` — starvation evidence moved
  from `assert "slow" in missing` (now fixed) to a timestamped probe;
  asserts `motor`/`slow` land beside transit.

## Gate

- `tests/test_executor_starvation.py`: **8/8 pass**.
- Full suite (`PYTHONPATH=core/build312:. .venv312/bin/python -m pytest
  -q tests`): **1118 passed**; 14 failures = 13 stale `alive_core`
  bindings (`'PathEngine' object has no attribute 'reach'` — rebuilt via
  `core/build_ext.sh`, re-verified green file-level) + 1 stale assertion
  in `test_transit_first_plan` (updated, green).
- Live API: not needed for this lane (all evidence is offline repro +
  suite); no writes performed.
