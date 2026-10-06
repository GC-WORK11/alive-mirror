# Lane: forecast-skill — make "beat persistence" true where it can be

## Why
judge-qa-v2's top finding: the forecast model loses to naive
persistence at EVERY horizon tonight — h+1 MAE 12.8 vs 5.4, h+5
48.6 vs 21.7 (measured on /v2/archive recorded cells). docs/05
names beat-persistence as the acceptance criterion. The honest
answer exists ("not yet — the model buys bands, horizon, spatial
structure") — but the engineering play is better: in a stationary
regime like tonight's fog, last-hour IS information; a forecast
that ignores persistence is handicapped for no reason.

## Scope — server/forecast only, no Mobile
1. Find the forecast code path (what feeds /v2/day `forecast`,
   /v2/outlook, the archive `model` cells). Understand its
   persistence-blindness: does the short-horizon forecast condition
   on the last observed field at all?
2. The honest fix: a persistence anchor at short horizons — e.g.
   blend the model forecast with last-observed-cell decay: weight
   persistence ~1.0 at h+0 decaying toward ~0 by h+24-48 (choose the
   decay from the archive data — fit it, don't guess; report the
   fitted form). This is standard in air-quality nowcasting — cite
   the method in code comment.
3. Validate on the SAME archive pairs judge-qa used (they're
   reproducible — see docs/plan/judge-qa-v2.md): report model-MAE vs
   persistence-MAE before AND after per horizon. The claim to earn:
   model+anchor ≥ persistence at h+1-4, and never worse than the
   pre-change model at any horizon (hard rule — no regression to
   the spatial/horizon value the model adds).
4. If the fitted blend can't honestly beat persistence at ANY
   horizon, STOP and report the data — do not ship a regression
   dressed as an improvement; the honest "not yet" answer stands.
5. Tests: a stationary-regime case (blend tracks observation),
   a step-change case (blend doesn't drag the model the wrong way
   beyond the anchor window), horizon-weight shape.

## Hard rules
- cd server && PYTHONPATH=core/build312:. .venv312/bin/python
  -m pytest -q tests — targeted first, FULL suite before push.
- Never fake skill: measured only on recorded-vs-forecast pairs.
- Live API GETs only. Commit to base/v2 (pull --rebase).
  Report → docs/lanes/forecast-skill-report.md: per-horizon
  before/after MAE table + fitted blend params + verdict
  (claim earned / honest "not yet" stands).
