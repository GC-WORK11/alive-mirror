# Lane: vibe-depth-2 — surgical second-order polish

## Why
Owner's last read (on pre-vibe shots): "still looks a little odd, not
giving vibe". vibe-polish `9b3abe4` fixed the physical defect (glass
panes ghosting the map). This lane is the SECOND-ORDER pass: the
felt-quality of the shipped surface — spacing rhythm, tonal warmth,
type contrast — against the Mobbin/Uber-class references in
docs/plan/design-refs.md.

## Scope — SURGICAL ONLY
- Audit the apk-final screenshots (docs/lanes/apk-final-report.md has
  ~20 attachment URLs: 05-hero-sparse, 45-en-home, 35-hero-rows,
  21-compare, 39-ledger, 42-hi-hero, 07-delhitoday) next to
  design-refs.md. Name EVERY felt-quality gap with a one-line fix.
- Allowed changes ONLY: spacing/padding/rhythm constants, font-size/
  weight/tracking within the existing type scale, color/alpha tweaks
  within the existing palette, border/hairline weights. Micro-
  adjustments that make the same structure feel expensive.
- FORBIDDEN: new components, layout restructuring, new surfaces, new
  copy, new tokens, removing anything. "In greed I ruin things" —
  the structure is frozen. If the audit finds only risk, report
  that honestly instead of inventing changes.
- Every change needs a before/after screenshot pair in the report.
- Suite gates: npx tsc --noEmit && npx expo lint && both test-runners
  (store 18, nav 68) — all green before commit.

## Deliverable
- If changes land: commit to base/v2 (pull --rebase), report →
  docs/lanes/vibe-depth-2-report.md with the before/after grid +
  a "what a rebuild must re-verify" list (the apk-final 14/14 set).
- If nothing safe: report says so with the audit — no forced diffs.

## Hard rules
- Never deploy. Live API GETs only. No PRs.
