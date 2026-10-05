# Design references — the lifestyle-dosimeter rebuild

Owner's verdict on the last pass: *"still shit — it's not the direction. The
travelling maps is now a feature not a main app — it's more than the maps app,
a real lifestyle app."* This doc is the brief the rebuild is built from: every
pattern adopted below cites the shipped product it was stolen from (Mobbin's
latest iOS flows + the Dribbble mobile-app board were walked first; the
specific instruments below are the patterns that survived scrutiny).

## 1. The home is a health instrument's "your day", not a map

**Reference — Oura app redesign (Oct 2024).** Oura collapsed five tabs into
three (Today / Vitals / My Health). The *Today* tab puts "Shortcuts to Scores"
at the very top, then the activity goal, then a timeline — the home answers
"where am I right now" in one glance before any feature is offered.
(thepulseblog: *Introducing the New Oura App Design*, ouraring.com/blog/new-oura-app-experience)

**Reference — Apple Health, Insights tab (iOS 26).** Health reorders its home
by time of day — morning opens on sleep + readiness and a one-line "what to
do now" summary; the day is the unit, not the metric catalogue. Highlights
uses on-device selection to surface *the one thing that matters* first.
(apple.com/health; PCMag *I Tested Apple's Redesigned Health App*)

**Adopted:** the app's resting surface is the day ledger — your inhaled dose,
the day's arc, the one decision — rendered on paper, not on the basemap.
The old "map + peek card" home is inverted: the day is the app; the map is a
room you walk into.

## 2. Travel as a feature inside a lifestyle home

**Reference — Uber homescreen (Feb 2023 redesign).** Uber cut eight service
tiles to a single "Where to?" field; the entire ride journey — search,
compare, trip — lives behind that one affordance, and home stays a lifestyle
hub (saved places, suggestions, Activity). Travel is invoked, never resident.
(uber.com newsroom *We're redesigning the Uber App*; TechCrunch 2023-02-22)

**Reference — Arc Search (Browser Company, 2024).** Extreme restraint: a
minimized bottom toolbar, keyboard already up on open, one input that is the
whole journey. Does less, does the basics better.
(MacStories review, 2024-01-29)

**Adopted:** the journey (search → compare → nav → receipt) stays exactly the
approved flow — but it is entered via one search-shaped "where to?" bar on
home, and on the map surface the day-ledger card is the door back home
(tap → home; hardware BACK on idle map → home). Search opens with the
keyboard already up.

## 3. Score-first hero — one number, felt

**Reference — WHOOP home (Bureau Oberhaeuser system).** WHOOP compresses
dozens of biometric streams into *one* score (Recovery 0–100) because the
6 AM question is a single decision: how should I train today? Three-tier
progressive disclosure: glanceable score → trend views → deep graphs.
(925studios.co *WHOOP Design Breakdown*; the5krunner.com 2023-03-28)

**Reference — Oura score circles / Apple Watch rings.** The ring is the
cheapest completeness glyph ever shipped: fraction filled, colour does the
rest, no axes.

**Adopted:** home's hero is `≈N µg` — Fraunces at display scale (~88 pt),
coloured by fraction of the day's personal budget. A single arc ring beside
it fills toward the budget ceiling (dose gauge — band ink, never an alarm
red). Everything else on home is a tier below; the number counts up on mount
(Oura's ring-tick) and morphs from skeleton to value — no pops.

## 4. Type that owns the screen — the CRED register

**Reference — CRED Topaz / NeoPOP.** CRED's design goal: "simple typography
built specifically to highlight numbers"; serif display headings paired with
a restrained sans body is the Indian-premium register that reads expensive
without ornament. (cred.club/design; UX Planet *Thoughts on CRED's UI revamp*)

**Reference — Linear-class density.** Dense information still feels expensive
when rows are hairline-separated, metadata is mono, and cards earn their
corners — instead of card-soup SaaS where every row is a panel.

**Adopted:** the existing register is the right one and is kept verbatim —
Fraunces display, Inter body, Plex Mono for every number and every eyebrow.
New rules for home: mono micro eyebrows ("YOU'VE BREATHED · TUESDAY"),
serif for the *one* decision line (felt), hairlines over card frames wherever
the content doesn't need elevation. Tabular-nums everywhere.

## 5. Micro-FOMO that is felt, not tabulated

**Reference — WHOOP coaching + Uber "ways to plan/save".** Both products put
the decision *attached to the score*, phrased as cost: strain today vs
recovery, the cheaper way to go. A delta phrased as a multiplier in a
sentence ("leaving at 6pm costs 3×") lands harder than any table.

**Adopted:** the morning card becomes **the move** — the server's own
decision line (or the derived `same plan at {f} breathes ~{x}× lighter than
at {g}`) promoted to serif display-size text above the sparkline; heavy/
clean windows stay as mono evidence rows underneath. On the compare sheet,
the dose gap keeps the 27e914b improvements; the "vs lightest" line stays a
felt number, never a table.

## 6. Material presence, no fake anything

**Reference — paper→ink editorial surfaces (Oura/CRED).** Elevation is a
ladder of flat fills, hairlines are ~10% ink, and the muted CPCB palette is
the only colour that means data — a severe day should *feel* severe through
wash + ink, not through neon.

**Adopted:** keep 27e914b's depth pass (V2Elev ladder, band washes/edges/inks,
press physics). Home is paper; cards sit on it with hairline + `V2Elev.card`;
the hero carries the day's band wash as a feeling. No emoji chrome, no
gradients, no glass on text.

## 7. The verb layer — live / go out / travel / stay

The four things a Delhiite actually decides daily, each answered by real
endpoints or hidden:

- **live** — the hero: what today has already cost (daylog reconstruction).
- **go out** — the move card: the day's heavy/light windows + decision
  (`GET /v2/day`, grid fallback). Outside NCR or a dead endpoint → the card
  itself says so or hides.
- **travel** — the "where to?" CTA → the approved journey.
- **stay** — the days-ahead strip (`GET /v2/outlook`, ≤5 cells, ghosted past
  the live anchor) + the symptom check-in that stays on the phone.

## What is explicitly NOT adopted

- Mobbin's current crop of onboarding/paywall carousels — irrelevant here.
- Dribbble's gradient-blob / glass-morphism fashion — violates the paper
  register and the "nothing fake" rule.
- Dashboard-style metric grids (the "vitals" tier) — the instrument shows a
  day, not a panel of numbers; the tile row was cut for duplicating the hero.
