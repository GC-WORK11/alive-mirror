# Lane: coldread-home — stranger comprehension on the dosimeter home

## Why
Owner's complaint has two halves — vibe (a lane is on it) and
COMPREHENSION. The dosimeter home uses field jargon a Delhi stranger
has 2 seconds to parse: "µg", "µg/m³", "breathing zone", "least-smoke",
"dose", "accounted", "band", "sensitive profile". Admin got a
comprehension pass for exactly this ("what is this / average of
where"); the consumer home never did. A judge who can't parse the hero
in 2s reads the whole app as confusing.

## Scope — Mobile surfaces only
1. Cold-read audit on the release build (iOS sim or KVM emulator):
   for EVERY surface a stranger sees (hero, THE MOVE, YOUR DAY, DAYS
   AHEAD, HOW YOU FELT, DAILY BUDGET, YOUR TRIPS, DayPeek, compare
   sheet, nav chrome, receipt, DelhiToday) — list every token a
   non-technical Delhiite cannot parse in ≤2s. Be the stranger, not
   the engineer: "breathing-zone price" means what to a person who
   skipped chemistry?
2. Rewrite ONLY the tokens that fail — Delhiite English, keep the
   measurement honest (never trade accuracy for simplicity — "µg" can
   get a one-line gloss where it first appears, not a fake unit).
   en + hi (hi-IN strings keep parity — check hi locale for the same
   jargon leaks).
3. Structure/layout stays — copy + inline micro-gloss only. If a card
   needs a caption to be parseable, add the caption line in the
   existing style.
4. After: second cold-read pass on the same surfaces — every flagged
   token either fixed or justified-in-report why it stays.

## Hard rules
- cd Mobile && npx tsc --noEmit && npx expo lint +
  node src/store/test-runner.mjs && node src/nav/test-runner.mjs green
  before push.
- en.json + hi.json parity — no English leaked into hi surfaces.
- Journey untouched. Live API GETs only.
- Commit to base/v2 (pull --rebase). Report →
  docs/lanes/coldread-home-report.md: token × verdict × fix table.
