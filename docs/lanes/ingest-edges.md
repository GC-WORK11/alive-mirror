# Lane: ingest-edges — the two honesty-edge findings

## Why
field-drift-watch (clean watch, `d14815f`) documented two latent
issues — neither fake numbers, both polish-level honesty edges a
judge could notice on /admin/api/sources + /v2/why:

1. **FIRMS stale-flap** — the public-CSV feed's `stale_after_s=2700`
   (45min) is SHORTER than its real refresh cadence (45min+), so it
   spends real time flagged stale between refreshes. A judge watching
   the sources table sees a feed flapping stale→live→stale. Fix by
   aligning the marker to the true cadence (raise stale_after to
   ~2× observed refresh interval) OR shortening refresh — whichever
   is honest about how fresh FIRMS data actually can be (public CSV
   updates on its own lag; do NOT lower stale_after to hide it —
   the marker must reflect reality).
2. **why-snapshot under-count** — /v2/why's S3 read has a ~4s serial-
   budget ceiling (8 workers exist) that truncates OLDEST rows under
   CPU contention: count oscillates 26-32 vs ~30-31 actual, and the
   SPAN shrinks by losing the window's tail. Fix so count+span are
   stable: raise/parallelize further, cheap HEAD-count first, or
   make truncation explicitly reported in the payload
   (e.g. `n_snapshots_scanned` vs `n_snapshots_available`) — pick the
   honest mechanism that fits the code.

## Scope
- Read the watch report docs/lanes/field-drift-watch-report.md +
  the FIRMS ingest + /v2/why S3-read code paths.
- Land the minimal fix(es) + tests. Suite:
  cd server && PYTHONPATH=core/build312:. .venv312/bin/python -m pytest -q tests
- Verify live after I deploy (you don't deploy): /admin/api/sources
  stale_after sanity + /v2/why n_snapshots/span stability across
  repeated calls.

## Deliverable
- Commits to base/v2 (pull --rebase). Report →
  docs/lanes/ingest-edges-report.md with before/after numbers.
- Never deploy. Live probes GETs only.
