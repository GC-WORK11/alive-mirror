You are the cold-path lane for ALive-108 — server-side latency hardening for the surfaces a judge hits COLD on stage. Measured tonight on live: `/v2/plan` took_ms 6650 on a cold hit (warm re-hits are fast, but a judge's FIRST touch of the app is exactly the cold path). Reach payloads, first-byte on landing//city/admin, and whatever lazy warm-up still hides in the request path are your territory. Deliver: a measured profile of every cold-path bottleneck + focused fixes where the fix is safe.

Repo: <owner>/Delhi-Air-108, branch base/v2 (pull latest — lanes push often). Server: server/ (FastAPI). Live: http://alive108-2699c171ddded465.elb.ap-south-1.amazonaws.com (GETs + /v2/plan + /v2/reroute only — NEVER POST /v2/feedback, /observe, /v2/trip). Suite: `cd server && PYTHONPATH=core/build312:. .venv312/bin/python -m pytest -q tests`.

HARD RULES
- Push code only — never deploy (the lead deploys). Full suite green before push.
- No new dependencies, no architectural rewrites — measure first, fix the cheapest real bottleneck, keep behavior identical.
- Honest: if a latency number can't be improved safely, document WHY (e.g. graph-load is once-per-task and warm_task.py covers it) — don't fake a fix.

MANDATE — measure, then fix what's cheap:
1. **Cold /v2/plan**: what eats the ~6.6s? Candidates to instrument LOCALLY (never on live): route-graph load on first request, OSRM sidecar first query, field/krige first paint, priced-edge cache fill. Time each stage in a local run (the repo has tools/ + core/build312 — use them). If it's once-per-task warmup, the honest fix may be extending `tools/warm_task.py` coverage — check what it already warms (demo-day T-40) and cover any gap (e.g. a plan call on the demo OD, a reach call, /v2/day).
2. **/v2/reach payload + paint**: measure response size + serialize time for walk@25/50, car@25 on the demo anchor (curl -w timings on live is fine). If the edge list is megabytes, check whether a simplification or gzip middle already exists — if the demo only needs the veil, is there a cheap `?detail=veil` option? (Only if trivially safe.)
3. **First-byte on the pages**: / (landing), /city, /admin — curl -w time_starttransfer on live ×5 each. If any is >1s, find why (template render? upstream fetch in request path?).
4. **Endpoint fan-out**: /v2/day, /v2/why, /v2/outlook, /v2/skill, /v2/archive — cold timings after a task restart vs warm. Document the post-deploy warm curve: what stays slow for how many requests.
5. Write `docs/plan/cold-path.md`: the measured table (endpoint → cold/warm ms → the bottleneck → fix or honest reason), plus whatever code/warm_task changes you made.

Report: the measurement table, fixes landed (with before/after ms on the same box), what stays cold + why it can't hurt the demo (warm_task coverage), anything the owner should re-run morning-of.
