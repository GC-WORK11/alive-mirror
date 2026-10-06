# Lane: field-drift-watch — model sanity in the high-PM regime

## Why
Tonight is the highest-PM regime the field has served (monsoon→fog
transition; breath figure ~1165µg). Krige, QC, the fires modifier, and
/why's driver attribution all get stressed exactly now — drift
failures at 300+µg are the ones that embarrass on stage. Watch for
them BEFORE they become visible.

## Scope (a ~3h watch loop, ~25min cadence)
Each tick:
- `GET /aqi` at 6 spread points (CP, Anand Vihar, Gurugram, Noida,
  Rohini, Dwarka) — record pm25, freshness, band. Flag: identical
  values across points (field froze), pm25=0/null, age>30min.
- `GET /v2/why` — record trend n_snapshots/span/delta + which drivers
  claimed. Flag: history shrinking (should hold ~30-34 builds/6h),
  trend flipping sign tick-to-tick, drivers that contradict the
  field (fires claimed while wind is clearly not from the belt).
- `GET /v2/city` breath figure + `/v2/skill` — flag: skill pairs
  stopped accruing; breath number jumping >2× between ticks.
- `GET /fires` count + `GET /admin/api/sources` (token in
  ~/.alive_admin_token) — flag: a source dropping to 0, fires=0 for
  >1h in burning season.
- S3 spot-check: `aws s3 ls s3://alive108-air/field/YYYY/MM/DD/` —
  builds landing ~every 15min; flag a >30min gap.
- On any flag: reproduce once, then write the anomaly with evidence
  into the report. Don't fix — OBSERVE and document (fixes go through
  the lead loop). If an anomaly is a live-lying severity (fake numbers
  on surfaces), note LOUDLY at top of report.

## Hard rules
- Live API GETs + admin GETs only — zero POSTs, zero deploys.
- aws CLI: export AWS_DEFAULT_REGION=ap-south-1 first.
- Write docs/lanes/field-drift-watch-log.md incrementally each tick
  (timestamped entries, real numbers — no "looks fine" vibes).
  Final report → docs/lanes/field-drift-watch-report.md. Commit both
  to base/v2 (pull --rebase) when done or on any hard finding.
