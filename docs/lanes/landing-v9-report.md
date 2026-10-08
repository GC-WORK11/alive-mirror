# landing-v9 — a1mobile register

Lane: landing (v9 redesign). Branch `base/v2`, base `da8b18d`, prod GET only.

Owner verdict on v8 editorial: thin/stretched fonts, ugly spacing.
Owner copy law (same dispatch, tightened): plain purpose-driven words —
no "dosimeter", no edgy poetry, no "exposed system". Register: "Delhi's
air is the worst in the world, and nobody tells you how much of it you
actually breathe. Alive does…"

## Design Read (stated before build)

Consumer landing for Delhi residents + judges — redesign-overhaul into
the a1mobile register. `DESIGN_VARIANCE 6 / MOTION_INTENSITY 5 /
VISUAL_DENSITY 4`. One accent = forest sage `#3a6844`; CPCB band hues
only where colour means air quality. All four vendored taste skills
(`docs/design/taste-skill/*/SKILL.md`) read in full.

## What shipped

`server/landing.html` — `<head>`+`<body>` rebuilt; the ~1,550-line
live-data `<script>` preserved, patched in 7 places (globals, felt copy,
hnumS paint, sparkCard unhide, storyCard fill, film-gate removed).

- **Hero** — card on warm `#FBFBFA`; the day's live field paints behind
  a paper scrim; h1 "Delhi's air is the worst in the world." at 800
  weight, tight `-.038em`; the field mean as a massive band-ink numeral
  (`clamp(92px,24.5vw,190px)`); band chip `pm2.5 · <band>`; read line
  "read across delhi ncr · map N min fresh · worst ≈N cigarettes"
  (repaints on every `/health` poll + the 30 s ticker); felt line
  "a day outside in this air ≈ N cigarettes"; pill CTAs — black
  "get the app" → releases, outline "open the live field" → /city,
  ghost "community" → /community.
- **Cards** — thick 1.5px ink borders, soft tinted shadow, generous
  padding, one 24px card radius vs one 100px pill radius: the day's
  arithmetic (live eq + provenance statusline), the live field (same
  kriged raster, pill controls, scrub deck, demochip — all wiring kept),
  the story card (`whyBig` = the felt line from `/v2/why`, cause note +
  `updated N min ago` + evidence link — hidden unless data),
  forecast spark card (same curve, card hidden until filled),
  the city card (day archive bars + 29-district rail),
  the app card (4 iOS screens in slim 6px-bezel frames, scroll-snap
  rail on mobile), how-it-knows (measure/interpolate/keep +
  what-leaves-your-phone ledger), black get-app card
  ("the field knows what Delhi breathed — the app knows what you
  breathed"), /city + /community door cards.
- **Nav** — floating pill bar, `toplive` slides in the live read past
  the hero fold.
- **Footer** — black block, giant edge-to-edge ALIVE signature
  (`clamp(96px,30.5vw,430px)`, baseline-bled), minimal links, live
  build sha.
- **Type** — one system sans stack, weight 800 headlines / 700 felt /
  mono small-caps only for instrument labels. Zero serif, zero
  stretched/thin faces, zero `font-weight:250/300`.

## Kept

Every live fetch (`/grid` ×3, `/v2/city`, `/health`, `/v2/plan`,
`/depart`, `/today`, `/v2/skill`, `/v2/why`, `/v2/districts`,
`/v2/reverse`, both geojsons), freshness disclosures (map age on hero
line + statusline + toplive, refreshed-IST on field head, story age,
wind age), honesty fixes (hidden-until-data, no fake numbers,
"unreachable" states), 'get the app' → GitHub releases, zero admin
strings, `osm_admin_5` untouched on this branch.

## Copy changes

"dosimeter" removed everywhere (title, meta, eyebrow, capLeft, comment).
New register per copy law: h1/sub are the owner's words almost verbatim.
Test marker `dosimeter` → `public monitors` in
`server/tests/test_landing_serve.py` (the REQUIRED list guards the
page; the copy law outranks the old marker).

## Verification

- `pytest tests/test_landing_serve.py tests/test_inline_scripts.py` —
  **8/8 pass** (fresh `.venv312`, python fallback for alive_core).
- Headless Chrome (CDP, emulated): **0 console errors / exceptions**
  at 1440×900, 390×844, 360×780; stepped scroll pass reveals every
  card; no horizontal overflow at any width; numeral scales 190→95px;
  CTAs stack; phone rail scroll-snaps.
- Links resolve: /city, /community, /v2/why, /v2/districts, /today,
  /v2/skill, /health, both geojsons — all 200 through the local
  verify proxy (local html + server/static, rest proxied to prod).
- Live data confirmed painting: 61.5 µg/m³ mean, 2.8 cigarettes,
  53 stations, map 7–12 min fresh, wind 8 km/h, 903K segments priced,
  29 districts, story "the air is barely moving…" updated 56 min ago,
  forecast 61.9–90.0 µg/m³.

## v8-sync (main + landing)

Standalone `index.html` derived and pushed to both `main` and
`landing` at `a734ad0` — `./ios-*` bundled assets (all present on
branch), `http://65.2.28.40/` absolute for every api()/fetch()/href,
`osm_admin_5` → `'osm_\x61dmin_5'`, zero `admin` strings. Landing
required a force-with-lease (it carried its own parallel v8-sync
commit; trees differed only in index.html). Standalone render
verified vs prod — identical, zero console errors (v8-hero.png).

## Evidence

`landing-v9-shots/` — d1440: hero, proof, field, story, city, mech,
getapp, doors, foot; m390: hero, field; m360: app, full page; v8-hero:
standalone on prod data.
