# Lane: demo-rehearse-v2 — re-verify every beat on the current build

## Why
demo-script.md + verify_numbers.sh were last verified before these
landed: hero-sparse `dbbc76a`, nav-start-pick `59a7da8`, ledger
dedupe removal + donation floor `0fdd597`, ingest parallel fetch
`5ec1f2f`, why-series parallel fetch. The demo script's beats and
timings must hold on what judges will actually see Oct 8.

## Scope
1. Read docs/demo-script.md, docs/demo-day.md, tools/verify_numbers.sh.
2. Re-run verify_numbers.sh against live http://65.2.28.40 — capture
   EVERY drifted figure into a table (script-says vs live-says):
   dose ladder pair, breath cigarettes, reach km, depart slots,
   skill pairs/MAE, community counters, corridors.
3. Walk each scripted beat and verify the SURFACE matches: fresh
   install → sparse hero design (not gray bar), compare → pick
   metro → Start → metro nav (pick persists), receipt copy
   ("added anonymously" vs queued wording), days-ahead band tiles,
   why-line presence on /city + /admin.
4. Time the real timings on the live build (cold /v2/plan, warm
   /v2/plan, /v2/reach paint, /v2/why) — update the script where the
   line would lie ("~2s" claims must hold).
5. Fix demo-script.md/demo-day.md where any claim is now stale
   (numbers ranges, surface descriptions, known caveats).
6. Report → docs/lanes/demo-rehearse-v2-report.md: beat × verdict
   table + the updated figures.

## Hard rules
- Live API GETs + /v2/plan + /v2/reroute ONLY — never POST.
- Commit doc fixes to base/v2 (pull --rebase). Never deploy.
- Honest drift — if a scripted number now can't be said, rewrite the
  line, don't fudge the range.
