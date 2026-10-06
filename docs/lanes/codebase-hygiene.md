# lane: codebase-hygiene — the 100k-LOC deepest clean

Owner directive (verbatim, abridged): "~100,000 lines… international hackathon…
make the most maintainable code, no dead code, end to end, no fake, any to end
connected, no broken APIs, no dummy code, no wrong functions… modern syntaxing,
structured directories… a very light codebase but NOT A SINGLE FEATURE is
removed… more efficient and faster… server, admin, bridge and mobile."

## Phase 1 — AUDIT FIRST (your deliverable #1)

Read the WHOLE repo (server/, Bridge/, Mobile/, docs/, scripts/, web surfaces
landing.html/city.html/community.html/admin.html). Produce
`docs/lanes/codebase-audit-report.md` — a findings table, every item classified:

- `dead` — unreachable code/files/routes nobody calls (prove it: grep all call
  sites, check router mounts, check imports)
- `dummy` — stub/hardcoded/fake data that violates the zero-fake-data rule
- `broken` — endpoints/UI wired to nothing, or wrong response shapes consumed
- `dup` — duplicated logic worth extracting (only if extraction is safe)
- `stale` — outdated deps, dead config, commented-out blocks, orphan files
- `perf` — obvious hot-path waste (N+1 queries, per-request recompute,
  unbounded loops, oversized payloads)
- `structure` — misplaced files, naming violations of the repo's conventions
- `risk` — correct-looking but fragile (silent excepts, unguarded parses)

Each row: file:line, evidence, severity, safe-fix? (yes/needs-review).
Sort by severity. This report is reviewed by lead before mass fixes.

## Phase 2 — SAFE FIXES ONLY (same lane, after the report)

Apply fixes that are MECHANICALLY SAFE and locally verifiable:
- dead files/functions with zero references → delete
- unused imports/vars → remove
- obvious `except: pass` → narrow + log (never silently swallow)
- duplicated constants → single source
- dummy/stub returns of REAL endpoints → fix or delete the path (report each)

NEVER remove: a feature, a user-visible string, an API route that any client
could call, or a documented behavior. When in doubt → report, don't touch.

## Verify
- `cd server && PYTHONPATH=core/build312:. .venv312/bin/python -m pytest -q tests`
  must stay green (1151+ tests; if build312 is stale run `bash core/build_ext.sh` first)
- `cd Mobile && npx tsc --noEmit && npx expo lint` clean
- `cd Bridge && tsc` clean (check its package.json for the exact gate)
- Commit to base/v2 in small themed commits (dead-code pass, unused-import pass, …)

## Scope split with the lead
You own: server/, Bridge/, scripts/, web HTML surfaces' SCRIPT hygiene.
Do NOT touch: Mobile/src (lead + design lanes live there), docs/plan/handoff.md.
If a Mobile finding is big, write it into the report — lead fixes it.

## Non-goals
No reformatting storms (no mass prettier), no dependency upgrades unless a
known-broken one blocks tests, no architectural rewrites without lead sign-off.
