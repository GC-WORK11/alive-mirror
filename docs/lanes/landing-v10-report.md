# landing-v10 — total theme replacement, all web surfaces

Lane: landing (v9 → v10 escalation). Branch `base/v2`, prod GET only.
Shots: `docs/lanes/landing-v10-shots/` (20 png, 1440 + 390).

## Escalation chain (owner verbatim governs)

1. v9 shipped → rejected: hero wanted *atmosphere* — "philosophical
   clouds, pollution".
2. v10 atmospheric pass → rejected harder: "eradicate EVERY design you
   created for landing AND admin — all-caps thin-track lettering =
   cheap." Scope grew to city + community + admin board.
3. Final escalation: "from the first letter of ALIVE to the footer —
   every component … ALL of it." → total CSS replacement ordered.
4. Register pivoted twice — dark-cinematic (Pollen/Aurora refs), then
   CORRECTED: "i hate … cyberpunkish, neonish, retro dark bluish or
   chocolaty … dont change the data or elements or maps or anything
   just the theme and hero and stuff."

**Governing brief:** theme + hero reskin ONLY; warm-neutral/cream or
moody-photograph — picked warm cream (zero cyberpunk risk); no
thick-thin long display fonts, no stretch/condensed, no serif gimmick;
alignment + generous consistent spacing is what he judges; Delhi-haze
art stays photographic muted warm-grey.

## Design law applied

- base `#FBFBFA`; one sans stack (system ui-sans); headlines 700–800,
  tight `-.03…-.04em`; body 400.
- ZERO letterspaced all-caps anywhere, including micro-labels — every
  old caps-track label is now small normal-case (mono stays for live
  data lines only).
- Cards: 1.5–2px solid ink borders + ONE soft shadow; no layered /
  translucent overlapping shadows; generous margins.
- ONE accent (forest `#3a6844`) + CPCB band hues only where colour
  means air quality. Pill CTAs. Black footer blocks.
- Copy law everywhere: plain purpose-driven; 'dosimeter' banned (test
  marker already moved to 'public monitors' in v9); no edgy poetry.

## What shipped (per surface)

- `server/landing.html` — hero now carries generated art
  `server/static/hero-haze.webp` (1536×724, 56 KB): photographic Delhi
  skyline (India Gate silhouette) dissolving into amber smog; warm-grey
  mute, no neon. Art bleeds the card edge (`inset:-7% -5%`), drifts
  34 s `hazedrift` (subtle parallax, `prefers-reduced-motion` gated),
  graded paper scrim keeps the 64.8-style numeral + copy legible
  (verified @1440/390/360). Live field canvas still paints inside it
  (`#fieldair`, opacity .55). Card system, footer ALIVE signature —
  kept from v9, caps-track residue purged.
- `server/city.html` — CSS wiped to the same tokens/cards; h1 "Delhi
  NCR air, right now." (em = soft ink, no italic). ALL live wiring
  kept: ncr.geojson SVG map, tl/rch/rc strips, hour-squares, ledger,
  ticker, corridors table, minimap, felt why-lines, disclosed ages.
- `server/community.html` — same wipe; "What Delhi breathed together —
  merged, never named."; 3-phones rule cards, shared-trips ledger,
  streets table, flags, black footer.
- `server/admin.html` — gate card restyled: warm base, heavy headline,
  solid ink pill button (green capsule + thin type gone); board labels
  normal-cased. `git diff` confirms `#gateform`/`#gatetok` and every
  auth handler byte-identical — pure look.

## Verified

- `pytest tests/test_landing_serve.py test_inline_scripts.py
  test_city_moves.py test_community_v2.py test_admin_auth.py
  test_admin_v2.py` → **84/84 pass**.
- Headless Chrome @1440 + @390 (and 360 earlier): 0 console errors on
  every surface; stepped scroll pass; no horizontal overflow; numeral
  scales (190 → ~95 px); cards stack; links 200.
- Admin gate: form markup unchanged (verified via `git diff` — only
  CSS values touched); the POST handler path untouched.
- Standalone `index.html` re-derived for `main` + `landing` (./ assets
  incl. `hero-haze.webp` at branch root, absolute prod API URLs, zero
  admin strings, `osm_\x61dmin_5` mangled).

## Shots → owner

16-frame set sent to the lead session for the owner's verdict
(awaiting visual verdict — pushed per deadline clause; iterate on any
rejection).
