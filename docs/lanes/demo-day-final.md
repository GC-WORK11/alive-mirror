# Lane: demo-day-final — runbook truth pass

## Why
docs/demo-day.md + docs/plan/demo-script.md are what the owner runs
on Oct 8 morning. Numbers drift; this pass re-derives every quoted
figure against the CURRENT live task and re-verifies every verbatim
command block so nothing fails at T-60.

## Scope
- Re-verify on live (http://65.2.28.40, GETs + /v2/plan only):
  breath figure + cigarettes, dose-gap pair (car vs walk on the demo
  OD — India Gate 28.6129,77.2295 → Huda City Centre 28.4594,77.0725),
  option-count RANGE (reprice swings 19-24 — script must say a
  range), reach km, why-history span, GRAP stage line, forecast
  blend claim wording ("beats persistence on today's air" — verify
  against /v2/archive pairs if the endpoint allows a quick check,
  else cite docs/plan/judge-qa-v2.md + forecast-skill report).
- Re-verify every verbatim block: T-60 on-demand flip, T-40
  warm_task.py (all /v2 surfaces), the verify script paths, the
  squash-baseline FIRST-step warning (scripts/public-repo.sh —
  read it, confirm flags/paths still match the repo), AWS-console
  shotlist pointer (docs/plan/aws-console-shotlist.md exists,
  80_aws.mov filename matches assemble.sh).
- Update stale numbers IN-PLACE in both docs; add a "last verified"
  timestamp line at the top of demo-day.md.
- Write the "judge's first 90 seconds" checklist for the demo phone:
  cold-open → consent (the owner's real choice on camera) → sparse
  hero → first real number ~3s → the 3 taps that land on the dose
  gap. Reference binary SHA 0b11123 explicitly.

## Deliverable
- Commits to base/v2 (pull --rebase). Report →
  docs/lanes/demo-day-final-report.md: every figure checked with
  live curl evidence, every block dry-verified, anything that
  could NOT be verified named honestly.

## Hard rules
- Never deploy. No server/app code changes — docs only.
- Live probes: GETs + /v2/plan + /v2/reroute ONLY.
