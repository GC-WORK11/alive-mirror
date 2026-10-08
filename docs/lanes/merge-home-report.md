# Merge-home — `/` rebuilt as the public air board — 8 October 2026

## Design Read

Reading this as: a public **instrument board** for Delhi's air, for a
cold visitor or a judge, in the admin console's **engine-room** register —
warm paper, mono micro-labels, serif numerals, muted CPCB colour only
where it means air. Dials: VISUAL_DENSITY 8 / VARIANCE 5 / MOTION 3.

Owner direction implemented verbatim-sense: "the main admin site is
itself the landing page — the main home screen should be the number,
very sexy." There is no landing page any more; `/` **is** the board.

## What changed

`server/landing.html` rewritten (133,863 → 95,536 bytes, −29%). The
editorial v8 structure — digit-flip boot overlay, essay blocks, film-strip
chooser, scroll-gated reveals — is retired. Replaced by a board:

- **mast** — sticky rail: `ALIVE · DELHI NCR` wordmark with live band dot,
  the live pm2.5 read (band-coloured dot + value + map age), doors
  (`/city`, `/community`, get-the-app).
- **hero** (`hero-grid`) — the field mean off `/v2/city` `pm25_stats.mean`
  as a serif instrument numeral in the band's ink register; band chip;
  `read at <gazetteer anchor> · nearest live monitor ~N km · map N min`
  disclosure; felt line "≈ N cigarettes a day"; a **vitals rail**
  (stations live / map age / wind / segments priced / grap stage /
  next 12h) fed by `/health` + `/v2/city`; door buttons under.
- **the field** — full-width panel: the kriged raster kept whole
  (param pills, inspect / a→b modes, demo chip, inspector card,
  boundaries+wind layer, legend + confSplit, skillLine + whyLine).
- **the strips** — three live cards: the air's story (`why.line` +
  `cause_note` + driver evidence + `story_age_s`), the next twelve hours
  (served `next_hours` spark), a typical October day (`/today` daybars +
  `vs_now_pct`).
- **the districts** — `/v2/districts` chip rail, worst-first, silhouette
  per boundary, +12h trend on tap (unchanged machinery).
- **the app** — lede "the field knows what Delhi breathed — the app
  knows what you breathed" + three real captures in **CSS device
  frames** (bezel, side keys, camera pinhole, rounded screen — no baked
  PNG borders, no captions) + CTAs.
- **footer** — `alive — delhi ncr · a dosimeter for your lungs` ·
  `buildTag` · group-counts honesty line.

### Field palette refinement (the "make it more improved" bit)

Not more colour — finer steps. Cell fills no longer snap band-to-band:
`rampCol()` lerps between per-band anchor values (`SPECS.*.ramp`), so the
surface shades like a field, not a choropleth. Official hues, legend,
band words, and confidence alpha (`hi .92 / med .6 / lo .34`) unchanged.
Band ink (`--bi*`) drives the numeral and band chip.

### App shots

Committed real captures, resized to 708×1573 (same density as
`app-hero-708`): `app-choose-settle.{png,webp}` from
`docs/lanes/demo-rehearsal-shots/13-compare-top.png`,
`app-airmap.{png,webp}` from `docs/lanes/android-verify-shots/04-airmap.png`.
Four routes added in `server/main.py` following the existing static
pattern (`_STATIC_CACHE`).

## Boundaries kept

- Every figure on the page is served data — `/v2/city`, `/health`,
  `/v2/districts`, `/today`, `/v2/skill`, `/v2/why`, `/grid`, `/aqi`,
  `/v2/reverse`, `/depart`, `/v2/plan` — with disclosed ages; no usage
  counters, no admin-only data, no token fields, no placeholder text.
- Every new fetch is a GET; `/v2/plan` remains the page's own POST and
  fires only on user taps — unchanged behaviour.
- Boot stays instant: no splash, no overlay; the numeral paints on the
  first `/v2/city` answer; below-fold feeds wait for `requestIdleCallback`.

## Verified

- `pytest server/tests/test_landing_serve.py` — **5/5 pass**
  (`/` ≡ `/landing`, required markers incl. `hero-grid`, `statusline`,
  `confSplit`, `fieldAge`, `buildTag`, `/app-hero-708.webp`; forbidden
  strings absent — `/admin`, `border-radius:999px`, `aether`,
  `ROUTE_ODS`, `placeholder text`, `TODO`).
- `pytest test_security.py test_admin_auth.py test_inline_scripts.py`
  (40 + script gate) — **all pass**.
- TestClient route sweep: `/`, `/landing`, all four new image routes
  (+ existing `app-hero-708` pair) → **200**, correct media types.
- Visual verify rig: local proxy served the edited html/statics and
  GET-proxied everything else to prod (POSTs refused — lane is prod
  GET-only). Chrome headless captures at 1440×3600 and 390px: hero,
  vitals, statusline, live raster + wind arrow, strips, district rail,
  device frames — all live values present (59.2 µg/m³ satisfactory,
  52 stations, 903k priced, fires/wind story, spark 68–103.9,
  build 61364f31 in footer).
- Screenshots: `/tmp/land-full.png` (desktop full), `/tmp/mob-hero.png`
  (390px) — not committed (verification artifacts).

## Honestly untested

- The a→b click path (POST `/v2/plan`) was not exercised — lane is prod
  GET-only; the code is ported near-verbatim from v8 which shipped it
  working, and the POST contract is unchanged.
- District popover + keyboard crosshair exercised by code review only,
  same provenance.
- Bug-hunter F3 stands: `get the app` → github releases still 404s for
  anonymous visitors (repo private). Kept per lane brief ("keep get the
  app → github releases") — making the release public is an owner call.
