# Lane: hero-sparse — the empty dosimeter reads BROKEN, not honest

## The problem (verified on the shipped APK home screenshot)
On a fresh install — exactly what the owner's demo phone and every judge
sees — the home's centerpiece "YOU'VE BREATHED TODAY" renders as a thin
gray bar with "µg" and NO number, followed by small gray text "still
sparse — the phone has sampled today's air too little to count it yet".
It looks like a loading skeleton that failed, not a designed sparse
state. "0µg this week" + 7 empty dots reads the same way. This is the
biggest single contributor to the owner's "still looks a little odd" —
the app's most important card visibly doesn't work on first open.

## The honest fix (NOT fake data — designed sparse)
Honest-degrade means show the truth we HAVE, labeled — not blank the
hero. The field at your position IS known (the phone serves ~63 µg/m³
outside right now); what's missing is only the personal sampling.

- **Sparse hero**: render the day's ambient curve at the device's
  location faintly inside the hero zone with a clear designed label —
  e.g. "today's air where you are: ~63 µg/m³ — your count starts once
  the phone logs its first hours" + a subtle "counting" affordance
  (progress to first counted hour, e.g. "1 of 3 samples"). The skeleton-
  looking empty bar must go — either a real number or a designed
  illustration/arc, never a gray line.
- **Week strip**: same treatment — when <1 day counted, show the city's
  week arc (available from /v2/outlook) dimmed + "your week starts
  counting today", instead of "0µg" + empty dots.
- Keep the honesty: the label must make clear which part is ambient
  field vs personal dose. Never show a personal number that isn't real.
- **Copy nits on the same screen** (cheap, same pass):
  - "how sure the smoke number is: low" → "confidence: low" (or better:
    the band-colored dot + "thin forecast").
  - DAYS AHEAD tiles: five near-identical washed-mauve cards are hard to
    scan — differentiate by band color more strongly so worst/best reads
    at a glance (the data already has `band`).

## Scope
- Mobile/ only: the home hero component + week strip + the two copy nits.
- Sparse states are the deliverable — but do NOT regress the populated
  state (verify both: fresh install AND after samples accumulate — the
  store test-runner or manual state seeding).
- Gates: `cd Mobile && npx tsc --noEmit && npx expo lint`; keep
  src/store/test-runner.mjs green (add a sparse-state render test if the
  harness allows).
- Screenshots required: before/after for BOTH sparse and populated hero
  states — attach to the report.
- Commit to base/v2 (pull --rebase first). Report →
  docs/lanes/hero-sparse-report.md.

## Hard rules
- No fake personal dose EVER — sparse means "ambient truth + labeled
  missing personal part", not invented counts.
- Match the existing register (serif hero, mono labels, CPCB palette,
  hairlines) — extend it, don't invent a new look.
- Never deploy.
