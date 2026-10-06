# Lane: web-soul — carry the breathing-card register to the web surfaces

Context: the app just got its "soul pass" (owner mandate — the app read
AI-slop-beige; judges' published criterion is literally "clean and
obvious beats clever and confusing"). Mobile now has: hour-aware
greeting, band-wash deepened to 26% on hero cards, a `BreathEdge`
living-border (4.4s sine opacity loop on a 1.5px band-ink ring —
the dosimeter breathes), verdict-washed cards, clay ledger identity.
The web surfaces (static site in `web/` — landing `/`, `/city`,
`/admin`, `/community`) got the component overhaul earlier but NOT
this soul layer. Same owner, same bar: muted-expensive tones, color
with intent, NO neon/cyberpunk/retro/3D/decorative-SVG, no
lime/chocolaty-green/cheap-yellow. Every number/feature stays.

Your job — the same register, web grammar:

1. **/city hero** — the big day-AQI number's card deepens to the deep
   wash (match the app's 26%-band feel — you may need a slightly
   deeper `--band-wash` for the live band) + a CSS breathing edge:
   `@keyframes breath` animating border-color/box-shadow alpha over
   ~4.4s ease-in-out infinite, `prefers-reduced-motion: reduce` off.
   One breathing element per page max — it's the accent, not a habit.
2. **Landing** — the hero stat tile gets the same breath treatment in
   the day's band (the page already band-washes its stat tile; deepen
   the wash, add the edge). The door tiles below stay as-is.
3. **Warmth in moments** — landing's greeting line (if any clock/date
   copy exists) or the eyebrow above the hero stat can greet by
   part-of-day ("good evening —" en; the web is English-only, no hi
   needed). One line, warm, then the existing stamp.
4. **/community** — the ledger-ish collective surface: a warm clay-ish
   wash on the totals card if one exists (the app's ledger uses
   clay-wash as its identity). Keep the forest accent canon — the
   web-nits lane just made forest #3A6844 the one web accent; do NOT
   regress it (admin keeps its documented #2456D6 exception).
5. **/admin** — leave mostly alone (backstage), but the field-card /
   status hero may take the breathing edge IF it reads as aliveness,
   not decoration.

Verify: serve web/ locally (python -m http.server or the existing
static route), screenshot each page before/after at 1280px AND 390px
(CDP setDeviceMetricsOverride DSF 2 per the cold-eye report's
technique). The breath must be visible as a subtle edge glow — if you
can't perceive it in two frames 2s apart, it isn't there; if it's
garish, dial alpha down. Zero features/numbers removed. Light theme
stays light.

Report → docs/lanes/web-soul-report.md (what washed/breathed where +
capture links). Commit everything to base/v2.
