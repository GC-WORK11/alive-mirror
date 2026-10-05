# Lane: ingest-coldbuild — the ~25min first-build gap on a fresh task

## The observation (verified live, Oct 6 ~04:15 UTC)
After each ECS rollout, the ingest daemon thread's FIRST
`run_index_once()` takes ~25-30 min before its snapshot lands in
`s3://alive108-air/field/` — task 172 booted ~22:18 UTC, first key
`2243` landed 22:43 (the steady-state cadence after that is ~15min).
Every deploy punches a ~25-min hole in the recorded trail. Serving
stays fresh (the in-app FIELD.refresh path is independent), so this is
about the durable record + trend/history warmup, not live data.

## Questions to answer (profile, don't guess)
1. WHERE does the time go inside `run_index_once` on a cold task?
   - station/source fetches (serial? timeouts? retries?)
   - kalman smoother warmup
   - krige build over 784 cells (CPU?)
   - fire belt match
   - serialize + S3 put
   Add timing logs (or instrument with the existing log.* pattern —
   whatever the file already does) to attribute it. A quick local
   profile (time the same build path against recorded inputs, or a
   task-local `py-spy`/timer around the stages) is the evidence.
2. Is any stage needlessly cold-only? e.g. does the build re-download
   something the image or a snapshot could seed? Does the snapshot it
   just wrote skip local mirror (S3-only) forcing next-boot re-fetch
   anyway?
3. Options ranked by effort: (a) log stage timings so it's at least
   observable; (b) parallelize independent fetches if serial; (c) seed
   the cold build from the newest S3 snapshot's provenance where valid;
   (d) leave as-is with the finding documented. Implement (a) always;
   (b)/(c) only if clearly safe + small.
4. Do NOT change the cadence or the snapshot format — consumers
   (archive, /v2/why series, /v2/skill pairing) depend on it.

## Scope
- server/ingest_worker.py + whatever it calls for the build.
- Tests: any timing/logging change must not break
  `tests/test_ingest*.py` or the loop tests; run the full suite gate
  before pushing.
- Commit to base/v2 (pull --rebase first). Report →
  docs/lanes/ingest-coldbuild-report.md: the stage breakdown, what
  shipped, expected new first-build time (or why it can't improve).

## Hard rules
- Never deploy, never POST to live — CloudWatch logs are readable via
  `aws logs filter-log-events --log-group-name /ecs/alive108`
  (AWS_DEFAULT_REGION=ap-south-1).
- Honest finding over eager fix — if 25min is irreducible (real network
  + real compute), say so and ship just the observability.
