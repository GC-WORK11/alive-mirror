# Lane: executor-audit — every shared-executor arm that can starve at boot

## Why
transit-firstplan found the class: arms scheduled via
`asyncio.to_thread(...)` (or `loop.run_in_executor(None, ...)`) queue
behind the boot-warm fleet on the shared default executor and silently
degrade. Transit is fixed (`_TRANSIT_EXEC`); the lane's report flags
`_slow_mode_options` and the motorized OSRM-fallback `_rows` as riding
the same starved pool. Audit EVERY such arm — a judge's first touch
must never hit a starved leg.

## Scope
- Grep server/v2/*.py + server/app for `to_thread` / `run_in_executor`
  / `ThreadPoolExecutor` / `await asyncio.gather` on executor work.
- For each arm: which executor, what deadline/cap, what it degrades to,
  whether boot-warm traffic can starve it (first ~60s of task life).
- Reproduce starvation locally the way transit-firstplan did (occupy
  the default executor with slow jobs, fire the arm, measure).
- Fix the smallest way consistent with `_TRANSIT_EXEC`/`_ENG_EXEC`:
  private bounded pools for user-facing arms; leave genuinely
  background work on the shared pool.
- Regression tests: starved-pool harness asserting each user-facing arm
  lands within its cap.

## Gate
Targeted tests + FULL suite if plan.py/reroute.py/directions.py touch
(PYTHONPATH=core/build312:. .venv312/bin/python -m pytest -q tests —
rebuild core via core/build_ext.sh if bindings look stale). Commit to
base/v2 (pull --rebase). Report → docs/lanes/executor-audit-report.md:
arm × executor × starved? × fix table. Never deploy.
