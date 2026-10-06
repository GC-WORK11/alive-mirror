# Lane: grap-stage — Delhi's legal air frame on the surfaces

## Why
October Delhi runs on GRAP (Graded Response Action Plan — CAQM's
legally binding stages every Delhiite knows: Stage I AQI 201-300,
II 301-400, III 401-450, IV >450). Nothing in the product names it.
A judge in Delhi sees "129 µg/m³" and mentally asks "what stage is
this" — answer it honestly. The stage RULES are public and
deterministic: we compute the GRAP-EQUIVALENT of the served field
("this air maps to Stage III under GRAP rules") — never claim the
official stage (CAQM declares that; we don't have that feed and
honest-degrade forbids pretending).

## Scope — server + web only (NO Mobile changes — APK is frozen)
1. `/v2/day`: add `grap` block — `{equivalent_stage: 1-4|0, aqi:
   <field AQI basis used>, note: "computed from today's air, not the
   official CAQM declaration"}` using the day_mean_pm25→AQI conversion
   already in the codebase (find how /aqi computes AQI; reuse it —
   no second formula).
2. `/v2/city` (or wherever today's field summary lives): same block.
3. Web: one honest line where today's number is already shown —
   /city hero and /admin. Copy discipline: "maps to GRAP Stage N
   rules" NEVER "GRAP Stage N is in effect". If the computation
   can't run (field cold), omit the line entirely (honest degrade).
4. Tests: stage boundaries (200.9→I? no — 201 exact boundary),
   omitted-on-cold-field, note text present.
5. Copy reference for the rules: CAQM's GRAP schedule — stage
   thresholds are AQI-based; document the source in code comment +
   report (cite the schedule, don't invent numbers).

## Hard rules
- Server: `cd server && PYTHONPATH=core/build312:. .venv312/bin/python
  -m pytest -q tests` green (targeted first, full suite before push).
- NO Mobile/ changes. Web edits in the same register (hairlines,
  muted palette, plain-English comprehension lines).
- Live API http://65.2.28.40 — GETs only.
- Commit to base/v2 (pull --rebase). Report →
  docs/lanes/grap-stage-report.md.
