# Landing v7 — current-UI imagery + chooser beat

**Lane:** landing-v7 · **Date:** 2026-10-07 · **Branch:** base/v2
**Scope:** public `server/landing.html` only (admin untouched), plus static assets + routes.

## What changed

1. **Hero → current shipped home.** `/app-hero-*` now shows the dose-ledger
   home ("you've breathed 17 µg · good · 8% of your daily budget · least-bad
   hours strip") — the screen the shipped app actually opens on.
   Source: `docs/lanes/demo-rehearsal-v2-shots/02-home-hero.png`
   (real device capture, 1080×2400), copied to `landing-v7-shots/home-dose-src.png`.
   Served 236 CSS px wide via preloaded srcset: 472w (1×/2× phones, 19.2KB webp),
   708w (3×, 29.7KB), png fallback 198KB.

2. **New section — "The same field, asked to choose."** Between the field map
   and the mechanism section. A film-strip figure: three consecutive real frames
   from one chooser run on the shipped build —
   *every way, priced* → *the verdict pins itself* → *the cleanest goes bold*.
   Each frame cropped to the same map+sheet window (1560px tall), rounded,
   composited onto one canvas → `app-choose-strip-{848,1360,1520}.webp`
   (31.0/57.8/62.0KB) + 848w png fallback. `loading="lazy"` + `fetchpriority="low"`.
   Source: `chooser.mp4` screen recording from the freeze-dryrun child session
   (afbb89341aba489f936fa89ad7907460 attachment), frames extracted at t≈8.5s,
   10.5s, 14s; sources kept in `landing-v7-shots/`.

3. **Verdict pill echoed in page type.** The app's own pill — `∅ the cleanest
   way there` — sits as a real pull-quote next to the section's lead. Paper
   surface, ambient shadow, ink text: existing tokens only, no new color.
   (The ∅ mark renders via `<i>` + italic-override, matching the app's mark.)

4. **Caption grammar.** The strip's three-step captions reuse the page's
   mono/uppercase/tabular track style; hero caption text unchanged (still true).

## Weight audit (the page's own bytes: HTML + images it fetches)

| surface | html | hero tier | strip tier | total |
|---|---|---|---|---|
| phone 1×/2× | 118.6KB | 19.2KB (472w) | 31.0KB (848w) | **168.8KB** |
| phone 3× | 118.6KB | 29.7KB (708w) | 57.8KB (1360w) | 206.1KB |
| desktop 1× | 118.6KB | 19.2KB | 57.8KB | 195.6KB |
| desktop 2× | 118.6KB | 19.2KB | 62.0KB | 199.8KB |

vs v6: ~158.7KB. The delta buys the chooser sequence; every common case stays
inside the ~200KB line — only 3× phones grazing the 1520w+1360w picks land at
206KB. Hero itself got 30% lighter (43→29.7KB at the densest tier) because the
new capture compresses better than the old dark UI.

## Verification

- `pytest tests/test_landing_serve.py tests/test_inline_scripts.py` — **8 passed**
  (required markers incl. `/app-hero-708.webp`, `hero-grid`, dose lead all present;
  no forbidden strings — the only `admin` hits are `osm_admin_5` map internals).
- `scripts/check_inline_scripts.py` — **OK**, 4 blocks node --check-clean
  (2 pre-existing warnings, unchanged).
- Rendered headless Chrome 1280px + 390px against a static-first/prod-proxy
  preview (`render-wide.jpg`, `render-narrow.jpg`): hero paints new UI, strip
  renders three real frames with captions, pill echoes next to the lead, live
  number 38.0 µg/m³ painted from prod `/v2/city`, field map painted. Both widths
  correct.

## Not done / notes

- `delhi-today.png`, `settings.png` from the dryrun attachments were evaluated
  and skipped — the hero + chooser strip already carry the current UI story;
  more screenshots would cost wire without adding story.
- The 848w png strip fallback (302KB) only serves browsers without webp
  (effectively none of the demo audience); webp tier is what's fetched.
- Landing is English-only — i18n parity N/A. No admin changes. Deploy lane
  batches the push.
