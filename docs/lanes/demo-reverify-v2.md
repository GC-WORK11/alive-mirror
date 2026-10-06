# demo-reverify-v2 — runbook truth pass on live 4eb9e1e8

You are the demo-reverify lane for ALive-108 (exposure-aware Delhi product,
AWS×WeMakeDevs Air track, Oct 8–11). Repo: <owner>/Delhi-Air-108,
work on base/v2, pull first. A sibling lane verified the deploy; YOUR job is
re-running the owner's demo runbook against the NEW live build and fixing
drift — the admin surface changed shape since the last pass.

## Live endpoints (verify these, don't mock)
- NLB: http://alive108-2699c171ddded465.elb.ap-south-1.amazonaws.com
- /health must show build_sha 4eb9e1e8
- Admin token in ~/.alive_admin_token if it exists; ask lead if absent

## Tasks
1. Read docs/demo-day.md (the owner's runbook) + docs/plan/aws-console-shotlist.md.
   Walk EVERY beat with live curls: /v2/plan dose gap, /v2/why, /v2/day GRAP,
   /city, /admin, /escape, /directions. Record real numbers.
2. ADMIN DEMO FLOW CHANGED: admin is now a public board + "operator sign in"
   chip that triggers the token prompt — update demo-day.md if it still says
   "paste token on load" or shows the old flow.
3. FIRE STATE: 60 belt fires on the wire with NW wind (~315°) — check /v2/why:
   fires may now be CLAIMED (they were evaluated-not-claimed all night). If
   claimed, verify the modifier math and update any doc that says "fires
   honestly not claimed tonight" — that's stale now.
4. Verify every number in docs/repo-readme.md + docs/demo-day.md against live.
   Fix drift; suite must stay green (cd server && PYTHONPATH=core/build312:.
   .venv312/bin/python -m pytest -q tests).
5. NEVER POST /v2/feedback, /observe, /v2/trip — GETs + /v2/plan + /v2/reroute only.
6. Commit; write docs/lanes/demo-reverify-v2-report.md — table: beat | doc
   claim | live value | verdict.
