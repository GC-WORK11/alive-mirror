# landing-v13 — cognition.com × devin.ai register

Owner spec (verbatim): "same fonts same no navbar dude same blogging style same
to the last line or border dude to the same font size texture." Structure =
cognition.com, product sections = devin.ai. Final face — launch morning.

## Design read

Extracted tokens live in `docs/design/web-register.md`. The short version:
warm off-white `#F7F6F5`, ink `#16181d`, grotesque headings (proprietary
nbInternational → system sans stack, 500/600 weight, tight tracking), serif
prose (stkBureauSerif → Georgia stack), 10px mono micro-labels + margin
indices `001/002/…` in the left gutter, 1px hairlines instead of boxes,
small bordered buttons, column rhythm ~640px measure inside a 1180px frame.
Zero cards, zero capsules, zero shadows, zero download/github links.

## What shipped

`server/landing.html` — full CSS wipe + restructure:

- **Top**: tiny `alive` mark + four text links (home · the field · delhi ·
  community) + live `pm2.5 N µg/m³ · map N min fresh` mono readout. No navbar,
  no pill, no bar at all — absolute-positioned text only.
- **Hero**: generated mist-over-ridge photograph (`server/static/
  hero-nature.webp`, 2048×1365, 53.5KB, `<link preload>` + 190-byte inline
  LQIP under it). Headline "Delhi's air, counted." at clamp(26→44px), one
  serif sub-line, mono `delhi ncr` corner label. The numeral/chip/captions
  are GONE from hero chrome; their ids keep painting inside a hidden
  `hero-data` block so the script needs zero changes.
- **Unboxed data**: "right now, over delhi ncr" — the live figure as plain
  96px type + µg/m³ + small band chip + felt line + two mono provenance
  rows, all on hairlines. No card.
- **Feature story**: exactly 4 numbered sections — 001 the home (ios-dose)
  · 002 the chooser (ios-choose-priced) · 003 the ledger (ios-feat-trips)
  · 004 the week (ios-feat-week) — alternating phone frame ↔ one serif
  purpose line. Real sim captures only.
- **Field/story/forecast/record/how-it-knows**: same wiring, reskinned —
  kriged raster with mono pill toggles, day bars band-colored, district
  chips hairline-bordered, route ladder unboxed rows.
- **"the field, honestly"** — ruled journal rows (cognition's
  recently-shipped pattern): the map / the fires / the routes / the record,
  each `live`/`kept`.
- **Doors**: two hairline-ruled text links → /city, /community.
- **Footer**: ghost ALIVE at ~7% ink, three small link columns, mono
  foot-line with live build sha.
- **Section indices**: `counter-increment` margin numerals 001–012 in the
  left rail at ≥860px, stacked at mobile.

## Wiring kept

`hnumV/hnumB/hnumW/hnumS/hnumT/heroLive/stnHero/fieldair/eyebrow/liveDot/
toplive/status` all still in the DOM — the script's innerHTML writes land
either in the unboxed "right now" section or the hidden hero-data home.
One markup change: the duplicate `id="status"` statusline in the
arithmetic block was removed (the live-number section's is the real one).
`<noscript>` hide-list still covers every dynamic id.

## Admin gate/console

`/admin` does not share landing's css — it carries its own v10 warm-cream
register (heavy sans headline, ink pill, bordered card), which reads as the
same family (warm base + grotesque). Verified visually — shot in the bundle.
Auth markup/handlers untouched.

## Verification

- `pytest tests/test_landing_serve.py tests/test_inline_scripts.py` → 8/8;
  `check_inline_scripts.py` clean. Markers updated to v13 copy
  ("Delhi's air, counted.", "priced in lungs").
- Headless-Chrome CDP shots @1440 (hero/live-number/001/004/field/record/
  journal/footer) + @390 (hero/feat): **0 console errors**, no overflow,
  reveals paint, phone frames hold.
- FORBIDDEN list still guards: no `github.com`, no `get the app`, no
  `border-radius:999px`, no `/admin` links on the page.
- Standalone transform asserts: every `src/srcset/url()` ref local `./`,
  API+nav prod-absolute, `osm_\x61dmin_5` mangled.

## Pushes

- `base/v2` `0c1559f` — v13 rebuild + hero-nature.webp + ios-feat-{trips,week}.webp
  + web-register.md + this report + shots. Rebased on 6 upstream lane
  commits (all non-landing) cleanly.
- `main` `e18f11e`, `landing` `58ae339` — standalone `index.html` + asset
  files at root.

## Shots

`docs/lanes/landing-v13-shots/` — d1440: hero, live-number, feat-001,
feat-004, field, record, journal, footer, admin-gate; m390: hero, feat.

## Outstanding

Owner's visual verdict on v13. If he vetos: the knobs are in
`docs/design/web-register.md` (type scale, cream tone, rail indices).

---

# v14 addendum — owner's verdict applied

Owner rejected v13 verbatim: image doesn't suit pollution, phone bezels
aren't devin.ai product shots, page too sparse for cognition. Same
register, three fixes:

## Changes

- **Hero image → Delhi smog**: `server/static/hero-delhi-smog.webp`
  (2048px, 56.6KB) — India Gate dissolved in golden-amber volumetric
  haze; the pollution IS the subject. New 192B LQIP, preload kept.
- **Product shots raw**: `.phone` bezel removed via override — shots sit
  flat on the cream with 4px radius + 1px hairline + faint shadow,
  devin.ai style. iOS sim chrome visible inside captures.
- **Cognition density**: fixed left rail ≥1024px (alive mark, vertical
  links, blue-bar `.cur` on home, mono live readout beneath);
  content column `margin-left:216px`. Mobile keeps top stack.
- **Intro**: sans headline "Alive reads the air over Delhi — and counts
  what it does to you." + serif prose + `.btn` pair (/city solid,
  /community) + unboxed live number in the same section.
- **Headlines sans, prose serif** throughout (`.lead`→sans 500 −.018em,
  `.prose` serif Georgia stack).
- **Districts → ruled leaderboard**: `.dscroll` becomes vertical
  `counter-increment:dr` numbered rows — rank · district shape · serif
  name + mono state · band-colored aqi chip right. CSS-only override;
  JS markup + popover untouched.
- Duplicate `id="status"` removed (arithmetic copy dropped; live-number
  keeps it).

## Verify

- `pytest tests/test_landing_serve.py tests/test_inline_scripts.py`
  → 8/8 pass; `check_inline_scripts.py` clean.
- CDP shots @1440 (hero/mid/mid2/bottom/fix/dist) + @390 (hero/mid):
  rail paints, readout live (81.4 µg/m³ · map N min fresh), leaderboard
  rows numbered, 0 console errors, no overflow.
- Wired ids all still painted (visible live-number block + hidden
  `.hero-data`); zero JS edits; zero download/github/admin strings.

## Push

- `base/v2` — landing.html + hero-delhi-smog.webp + this report.
- `main` + `landing` — standalone index.html + hero-delhi-smog.webp.
