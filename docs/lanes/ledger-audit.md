# Lane: ledger-math audit — does "≈N breathed" equal timeline × field?

The home hero ("YOU'VE BREATHED TODAY ≈N µg") is the product's most important number and
nobody has proved it end-to-end. If the on-device reconstruction is wrong, the hero is a
lie on the biggest surface. This lane makes it provable.

## The claim under test
The app reconstructs dose ON-DEVICE: position timeline × the served field → a personal µg
total + per-segment attribution ("WHERE IT ACCUMULATED"). A judge can ask "how do you know
that number is right?" — we should be able to answer with math, not vibes.

## Work
1. Read the reconstruction path in Mobile/ (ledger: timeline capture, field fetch,
   dose integration — find the actual files: likely src/ledger*, src/api/city.ts,
   nav/engine or a dose util). Document the formula precisely in the report.
2. **Fixture proof**: build a scripted timeline (e.g. stand at CP 08:00-08:30, ride to
   Saket 08:30-09:15, indoors 09:15-10:00), drive it through the same code path the app
   uses (unit harness or the sim), and compare the app's per-segment µg to a hand
   recomputation against the LIVE field values at those cells/hours (curl /v2/grid or
   the same endpoint the app fetches). Numbers must agree within a stated tolerance —
   if they don't, the bug is the finding; fix it.
3. **Edge cases the demo might hit**: fresh-install sparse state (verified "too little
   to count" — keep honest), location off (no timeline → what shows?), consent OFF
   (does reconstruction still run locally? it must — donation is separate), a segment
   crossing a field-epoch boundary (two different hourly fields inside one segment),
   gap hours where the field has no coverage.
4. **The wire shape**: does the app's fetch of the field match what it integrates?
   (cell resolution, units µg/m³ vs dose, ventilation factors by activity — check the
   same factors the engine uses or document why the app's differ.)

## Rules
- Mobile/ only for fixes (tsc + expo lint gate; never hand-edit android/ios). Pull
  --rebase before pushes; other lanes are live in the same files.
- Live API read-only (GETs + /v2/plan + /v2/reroute). Never POST trip/feedback/observe.
- Report: the formula found, fixture numbers app-vs-hand (the table a judge could
  reproduce), verdicts per edge case, fixes pushed, and the ONE sentence we'd say on
  stage if asked "prove the number".
