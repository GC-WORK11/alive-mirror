# Lane: strip-bz — stays-vs-plan ambient basis mismatch during burn events

Found by ledger-audit (docs/lanes/ledger-audit-report.md): the app's `reconstructDay`
counts stays at `bz` (= ambient × fire smoke_modifier) while `/v2/plan` and the
`/v2/strip` counter integrate raw ambient — same street, same hour, ~+9% mismatch on
stay-vs-trip dose during burn events. A judge comparing "your stop at Saket cost N"
against "a trip on that street costs M" could catch the inconsistency on a smoky night.

## The question to answer correctly (don't just pick one)
- Read server/exposure.py + wherever `bz`/smoke_modifier is computed (grid field? fires
  feed? /aqi?). Understand what `bz` MEANS physically vs raw ambient.
- Decide the honest basis: should route/dose math price the modifier too (fires raise
  what you actually breathe on that edge), or is `bz` a display-only local bump?
- Whichever basis is right, make stays and plan/strip consistent — either apply the
  modifier inside the engine's edge pricing, or serve the modifier on the wire so the
  app applies one basis everywhere. Document WHY in the code comment + report.

## Work
1. Reproduce the mismatch live: pick a cell where bz ≠ ambient tonight, compute the
   two bases by hand, quote numbers.
2. Implement the consistency fix on the chosen basis (server/ if engine-side; the
   /v2/strip contract if wire-side — update Bridge/contract.ts + Mobile consumer if
   the wire shape changes).
3. Tests: extend the lane's runner or server tests to lock the chosen basis
   (a stays-segment and a plan-segment over the same hour+street must agree).
4. Report: numbers before/after, the basis decision + rationale, files touched,
   suite green.

## Rules
- server/ + Mobile/ + Bridge as needed; pytest gate for server, tsc+lint for Mobile.
- pull --rebase before pushes; never deploy (lead deploys after merge).
- Zero fake: if the modifier isn't physically justified in the field model, the fix is
  removing it from stays, not adding it to plan — say which honestly.
