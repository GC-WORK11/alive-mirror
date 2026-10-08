# landing-v8 — the air itself is the hero

Lane: landing-v8. Branch: base/v2 @ e3a1183+ (rebased over 3 newer lanes before push).
Scope: `server/landing.html` only (+373 / −119). No build/deploy changes, prod GET-only.

## Design Read (taste-skill §0.B, required)

> *Reading this as: a consumer landing for a live instrument judged by a
> hackathon panel, with an editorial-instrument "the air itself is alive"
> language, leaning toward native single-file canvas + scroll-driven
> choreography under the paper/ink + CPCB-band design law.*

Dials: `DESIGN_VARIANCE: 7` · `MOTION_INTENSITY: 8` · `VISUAL_DENSITY: 4`.
Minimalist-skill governs restraint (transform/opacity only, IO not scroll
listeners for reveals, reduced-motion fully honored, no emoji/gradients/glass).

## What changed, beat by beat

1. **Hero — the field IS the surface.** `#fieldair` canvas fills `.open`
   edge-to-edge under the statement: the same `/grid` features the
   instrument reads, cells breathing out of phase (confidence sets the
   ceiling), district borders at furniture weight, 56 motes drifting on
   the REAL wind vector from `/health` (`from_deg`/`speed_kmh`). Two
   veils: the day's band wash (`--hw`, colour = the data) + paper
   gradient protecting type. Numeral moved INTO the hero foot — the
   instrument reading its own mean over the field it just drew; basis
   line + `#heroLive` provenance strip (stations · map age · wind) under
   it. Before data: honest ink-dot skeleton, no fake surface.
2. **Chrome made sticky.** v7's `#toplive` was dead code — `.top` wasn't
   sticky, so the live read faded in inside chrome that had already
   scrolled off. `.top` is now `position:sticky` + paper blur; the mean +
   freshness genuinely follows you (µg opt-out so µg doesn't uppercase
   into "mg").
3. **Dose story.** `.proof` = lead "A day of breathing it." + felt line +
   the equation arriving term by term (`data-rv` + `--rvd` stagger, IO)
   + spark curve drawing itself (pathLength 1, dashoffset transition,
   `.dr` on IO) + provenance line. Also fixed a latent v7 bug:
   `.eq{display:flex}` silently overrode `hidden` — the equation rendered
   `—` placeholders before data. `.eq[hidden]{display:none}` added.
4. **Film gate.** `.choose` becomes a 235vh runway with a sticky gate
   (`min(330px,78vw)`): scroll cranks the 3 real app frames through the
   gate, caption beats light in sequence. No-JS / reduced-motion → the
   identical static strip (same markup, no transform).
5. **Numbers tick.** `countIn` → `countTo`: first count-in 950ms, then
   every 120s refresh ticks the numeral between real values.
6. **Age ticks.** `FIELD_AGE_S` + 30s interval keeps "map N min fresh"
   honest between `/health` polls across statusline, heroLive, toplive.
7. **Accrued motions.** daybars grow bar-by-bar on reveal (`scaleY`
   origin bottom, `--i` stagger); district chips mount staggered once
   (`chipin`); `.rv` gains `--rvd` delay var.
8. **Em-dash hygiene in new/edited visible copy** per skill 9.G (felt
   line, heroLive, captions use "·"/periods; untouched v7 strings kept
   their typography).

Ambient loop cost: one rAF gated by IO + `visibilitychange` — zero
painting off-screen or hidden-tab. ~300 lines of new JS, all stdlib-free.

## Verification (all local, prod GET-only)

- `python3 scripts/check_inline_scripts.py` → **OK** (4 blocks parse
  clean; 2 pre-existing prose warnings).
- Served `server/landing.html` via a same-origin test proxy
  (`/tmp/landing_proxy.py`, localhost:8791 → prod API; test-only, not
  committed). Every live surface verified against real prod data.
- **Perf**: `performance.getEntriesByType('paint')` → FCP 64ms,
  LCP 64ms (local). Wire = 131,343 B html (~128KB, v7 ~119KB) — inside
  the 250KB budget; prod FCP stays dominated by one HTML request + the
  deferred idle fetches (unchanged strategy).
- **Desktop drive** (Chrome, real browser, ~790px viewport): hero field
  breathes, numeral counts in, toplive appears past hero and ticks
  (10→15 min observed live), equation staggers, spark draws, gate
  cranks all 3 beats, inspector/district popovers work, day strip
  grows in, refresh caption honest mid-flight.
- **Mobile drive** (DevTools 400×867): statement/field/numeral/provenance
  all fit; eq column layout; gate 78vw; no overflow, no clipped text.
- `AIR_ON`/`AIR_RAF` verified: loop runs only while hero intersects.
- Console: zero JS errors across the full scroll.

## Evidence

- Scroll-through video (desktop, annotated):
  `/Users/devin/screencasts/rec-7f9916f2-c1ca-438b-8663-0cd5b84d0557/rec-7f9916f2-c1ca-438b-8663-0cd5b84d0557-edited.mp4`
- Screenshots: `/Users/devin/screenshots/ss_*.png` (hero, dose, field,
  gate beats 1–3, mech, day, close, mobile hero/dose/field).

## Caveats / honest notes

- The hero canvas needs ~300ms first paint after `/grid` lands (same
  dependency the instrument already had); skeleton dots show meanwhile.
- Boot strip unchanged (sessionStorage-gated, skip on revisit).
- The map still sits in a card — deliberately: ambient hero = canvas of
  air, instrument = the same surface operative. Removing the card frame
  was considered and rejected (inspector + TL deck + demo chip need a
  coordinate frame anyway).
- `figcaption` → `div.film-caps` (figcaption must be a direct child of
  figure; the gate needed it inside the sticky wrapper).
- `.hnum` margin restored for non-hero contexts; `.open .hnum` overrides.
