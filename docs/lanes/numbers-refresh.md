# Lane: numbers-refresh — re-verify every published number post strip-bz

## Why now
`80a1525` moved plan/strip/reroute onto the breathing-zone basis (ambient ×
smoke_modifier — the same field `/aqi` serves). During burn events every
published trip-dose number rises ~+9%. Stale figures a judge can falsify
live are worse than no figure — every published number must be re-derived
from the NEW live build.

## Scope
- Wait for the deploy: poll `GET http://65.2.28.40/health` until
  `build_sha != 268ed544` (deploy rolls ~9min; poll every 60s up to 25min).
- Then re-run `scripts/verify_numbers.sh` (read it first — it knows the
  endpoints + drift flags) and reconcile EVERY flag it raises.
- Re-derive + update the dose claims wherever they're published:
  - `docs/submission/writeup.md` — dose pair, cigarettes, corridor counts,
    reach km, community counters (use live GETs).
  - `docs/demo-day.md` — every beat's expected number (33×→new ratio,
    breath figure, reach km, warm figures).
  - `docs/lanes/video-v4-report.md` / video beats claims if the numbers
    quoted changed materially (flag >10% moves; don't rewrite for ±1µg).
  - `scripts/verify_numbers.sh` baselines if they're hard-coded.
- Check the dose-gap wording: with the modifier in plan, the car-vs-walk
  ratio may move (both sides scale but not identically — modes differ in
  ME·VE·t). Re-derive the ratio fresh, don't extrapolate.
- Commit corrections to base/v2 (pull --rebase first; lanes push often).
- Report: docs/lanes/numbers-refresh-report.md — a before/after table of
  every figure touched, the live curl evidence for each, anything left
  stale + why.

## Hard rules
- Real numbers only — every corrected figure cites the live curl that
  produced it. No rounding invention.
- GETs + /v2/plan + /v2/reroute only on live — NEVER POST feedback/
  observe/trip.
- Server tests unchanged by you; if a test asserts a stale number fix the
  number inside the test the same way (with the curl evidence).
- Do not deploy — lead deploys.
