# Lane: app-overhaul-v2 — component-level redesign (owner mandate)

## Owner's verdict (verbatim, governs everything)
"the ui ux of weather admin app, landing page and worse the mobile
app — look so cheap and also too much complex it's like a fucking
operating system… this app must be a daily driver… too dull yeah the
light theme i wanted but it is so dull there is too much going on…
so much mini words so much cringe… without removing a single feature
…minimalism and more functional and productive… we really need
individual designed components… colorful like components add little
liquid glassmorphism… easily navigable any user no technical must use
it flawless… the functionality we provide is so advanced but we
aren't able to express it nicely… don't even compromise over a
single feature or numbers we are showing."

## The reference register (what his Dribbble/Mobbin tabs show)
Chunky COLORFUL components on light backgrounds — saturated accent
cards (lime balance card, purple unlock tile, orange stat tiles),
big hero numerals owning their card, generous rounded corners +
pill buttons, near-zero prose, cards that carry meaning visually.
Color lives ON components, not painted over everything. Glass is a
tint, not a frosting layer.

## Scope — Mobile app, component by component
Every screen keeps 100% of its features and numbers. The expression
changes:

1. **Kill the mini-words.** Audit every screen for text density:
   labels >3 words, qualifier strings, prose lines. Replace with
   component grammar: the number + its unit + a band-colored
   accent/icon does the talking. Words only where a number alone
   can't mean anything.
2. **Component-level design** — each surface's components get
   individually designed, not one blanket card style: dose hero,
   day arc, the move, days strip, ledger rows, compare options,
   receipt stats — each is its own designed object (own accent,
   own shape language, own hierarchy).
3. **Colorful + glass, in the light theme.** Saturated band-colored
   accents on components (CPCB palette deepened/saturated for
   component surfaces), light glass tints where the map shows
   through (search bar, chips, HUD tiles — the existing glass
   rule stands), soft shadows on cards. NOT: repaint the whole
   app colored, NOT dark theme, NOT frosting everywhere.
4. **Hierarchy per screen** — one hero per screen, everything else
   visibly recedes. The dose number / the move / today's window
   owns its screen.
5. **Navigable blind** — a non-technical user reaches every feature
   in ≤2 obvious taps; if a feature needs a label to be found,
   the IA is wrong.

## Rules
- Zero features or numbers removed — the verification list is the
  apk-final 14/14 surface set (docs/lanes/apk-final-report.md).
- Light theme only. Fraunces/Plex Mono stay (they're bundled).
- No jest; gates: cd Mobile && npx tsc --noEmit && npx expo lint &&
  node src/store/test-runner.mjs && node src/nav/test-runner.mjs.
- Never deploy. Live API GETs only.
- Deliver before/after shots per screen in the report +
  what the APK rebuild must re-verify. Commit to base/v2
  (pull --rebase). Report → docs/lanes/app-overhaul-v2-report.md.
- This lane owns Mobile only — web surfaces have a sibling lane;
  share the design language via docs/lanes/register-card.md
  (update it, don't fork it).
