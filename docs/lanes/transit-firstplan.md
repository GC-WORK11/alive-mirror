# Lane: transit-firstplan — first /v2/plan after boot must carry metro

## The wart (apk-v4 drive note, `bdc52a3`)
GTFS now compiles at boot (health.transit.compiled=['bus','metro']),
but the FIRST cold /v2/plan on a fresh task can still return no
Metro+walk option — the async transit-options path lands after the
road options resolve. On the demo phone the very first query a judge
makes could be India Gate→Gurugram (a metro OD) — metro silently
missing reads as a feature that doesn't exist.

## Questions
1. Reproduce: on a FRESH local server boot (transit compiled), time
   the first /v2/plan for a metro-suitable OD — count options by
   mode. Does the first response include the transit option? If not,
   where does the async gap live — the transit search inside plan,
   the station-access walk leg, or the option-assembly ordering?
2. Options ranked by risk:
   (a) await the transit leg before responding when it lands within
       a small budget (e.g. +800ms) — keeps first plan honest;
   (b) boot-warm a canonical metro OD inside _warm_static so the
       async path is populated before any user hits it (cheapest,
       matches warm_task pattern);
   (c) surface honestly "transit options still loading" — NOT
       acceptable for demo, only if (a)/(b) infeasible.
3. Ship the smallest safe fix + a regression test: simulate the
   first-plan path and assert a transit-bearing option appears for
   the metro OD (or assert the warm path exists).
4. Also verify tools/warm_task.py's plan ODs actually produce a
   transit option — if warm can't make metro appear post-deploy,
   the T-40 run doesn't cover this wart either.

## Scope
- server/v2/plan.py + transit option assembly + main warm path +
  tools/warm_task.py.
- Gate: targeted tests + full suite if plan.py changes.
- Commit to base/v2 (pull --rebase). Report →
  docs/lanes/transit-firstplan-report.md: repro numbers (first-plan
  option count before/after), what shipped.
- Live API http://65.2.28.40 — GETs + /v2/plan only. Never deploy.
