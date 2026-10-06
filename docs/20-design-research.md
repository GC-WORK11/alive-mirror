# 20 — Design research: what "AI slop" actually is, and our way out

Owner mandate (Oct 6): "Do the deepest research on UI/UX and typography.
What should be the SOTA? First learn what is AI vibe coded slop — then
don't do that." Plus: "not colorful — DIFFERENT; smoother; the slop is in
details like borders, how elements are put, icons."

## What the research says (sources at bottom)

### The deepest tell: a checklist is not a design
The anti-slop literature's core finding: slop isn't any specific color or
font — it's **no point of view**. "A recolored layout is still slop."
Every fix we've shipped for four days has been palette/grammar patches on
the SAME assembled layout. The owner keeps smelling it because the layout
never made one creative decision.

### Literal tells we commit (checked against the codebase)
- **Fraunces** — named verbatim as the overused AI-signature display
  serif (the Fraunces+body-sans pairing). Our hero numeral IS Fraunces.
- **Icon centered in a colored tile** — our door wells, compare options,
  ledger boxes, sidebar wells. The single most repeated slop pattern.
- **Eyebrow pill/chip** — "GOOD MORNING · TUESDAY" rendered as a chip.
- **Hairline borders on every card** — the `hairline` token on all cards
  = the "kit-assembled" look the owner called out ("the borders").
- **Uniform corner radius** — every card ~14–18px = catalog parts.
- **Uniform padded grid of same-shaped tiles** — the door row.

### What SOTA looks like for our category (data-feeling apps)
- **CARROT/iOS Weather — the condition IS the canvas.** The background
  is a two-color gradient that maps to the state being reported; "the
  app's appearance IS the report before you read a number." Giant
  numeral: ultra-LIGHT sans (~weight 200), huge, tight tracking.
- **Tonal layering** — premium apps kill 1px card borders: hierarchy via
  surface depth (paper → tonal field → floating white). Ambient shadow
  (blur 20px+, tinted, never black) only for true floats.
- **Material 3 Expressive (Google's own 2025 answer)** — emotional
  impact: spring physics for every touch (spatial + effects springs),
  shape VARIETY (35-shape library, mixed corner radii as expression),
  shape morphing, emphasized type roles.
- **Gentler Streak (Apple Design Award)** — warmth comes from translating
  stats into felt language + soft surprises, not from dashboards.

## The creative decision (the point of view we never made)

**The air is the canvas.** The hero is not a card — it's a window into
today's air: a full-bleed field whose gradient is today's live band
(deep muted wash, breathing slowly), with the dose numeral floating
inside it in light-weight sans. Everything below sits on tonal paper —
grouped-list grammar, no hairlines on heroes/primary cards.

## The new register (v3 — supersedes token-level v2 where they conflict)

1. **Typography**: Fraunces REMOVED from all screens. Display numerals =
   geometric grotesque at light/medium weight, 80–96px, tight tracking.
   Candidate faces (test on-device): Satoshi (ITF — Indian Type Foundry,
   fitting for a Delhi product), Manrope, Hanken Grotesk. Body stays a
   warm grotesque; mono only for provenance/mono numerals where tabular
   matters. Devanagari stays Noto Sans Devanagari.
2. **Edges**: hairlines only INSIDE lists (row separators, iOS grammar).
   Heroes/cards float on tonal fill or ambient tinted shadow — never a
   1px outline.
3. **Shape variety**: hero squircle (~28), doors ~18, chips pill,
   gauges circle — corners carry meaning, not catalog uniformity.
4. **Color**: unchanged psychology — one accent + band hues where color
   means air — but the hero FIELD owns the band, not a card fill.
5. **Icon grammar**: filled rounded, consistent weight — but doors stop
   being "icon in a colored tile": icon + label in a tonal well row, or
   larger free-standing glyph + label (test both on-device).
6. **Motion**: spring on every pressable (scale 0.96, damping ~12);
   the sky field drifts/breathes; depart strip is finger-scrubbable;
   day tiles expand inline on tap.
7. **Copy**: stats translated to felt language (Gentler Streak rule) —
   already our register; keep.

## What this does NOT change
Light theme; muted-expensive palette; every feature and number stays;
no neon/3D/decorative SVG/lime/chocolate; honesty rules intact.

## Sources
- pols.dev/slop.md (the canonical anti-slop catalogue)
- blakecrosley.com CARROT Weather design teardown
- developer.android.com — Material 3 Expressive (motion springs, 35-shape
  library, expressive type)
- developer.apple.com/news Gentler Streak interview + sketch.com/blog
- tonal layering pattern (surface depth over borders)
- Android Wear typography roles (Numeral tabular defaults)
