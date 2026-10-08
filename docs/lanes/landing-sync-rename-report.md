# Lane report — landing-sync-rename

Sync the `0c5f9cc` rebrand (server/landing.html, `ALive·108` → `Alive`) into the
Vercel-facing standalone `index.html` on `main` + `landing`.

## What landed

- `7df93a3` on `main` and `landing` (same commit): `index.html` rebased on
  `server/landing.html@0c5f9cc`.

## Method — transform set verified byte-exact first

`index.html@821b753` (old standalone) vs `server/landing.html@34568a0` (the
landing it was built from): the ONLY differences were the transformation list —
zero drift:

- `src="/app-choose-strip-848.png"` → `src="./app-choose-strip-848.png"`
- `src="/app-hero-708.png"` → `src="./app-hero-708.png"`
- every other `/`-leading ref (wordmark `/`, nav+close `/city` `/community`,
  19 api()/fetch()/in-template href URLs) → `http://65.2.28.40/…` absolute.

Same transform applied to `server/landing.html@0c5f9cc` → new `index.html`.
Old→new index diff = exactly: 6 rename sites (title, og:title, boot
aria-label, bt-top, wordmark, footer) + `05a3b4b` comment ("as admin" → "as
the console") + `a7814cb` freshness-fix code (TL.epoch/touched,
tlInvalidate/tlAged, windAge, DAY_HRS/dayBarsHtml/dayTick, 120s-beat
additions). Nothing else.

## Found + fixed: webp `<source>` never shipped to the branch

Both `<picture>` blocks carried `<source type="image/webp" srcset="/app-*.webp…">`.
The webp variants live in `server/static/` on base/v2 but were NEVER copied to
`main`/`landing` — Chrome picks the srcset, hits 404, and the `<img>` PNG
fallback is NOT used (spec) → film gate + hero shot rendered as broken-image
placeholders on Vercel AND in the old standalone. Reproduced on localhost:
server log showed `GET /app-hero-472.webp 404`, `GET /app-choose-strip-1360.webp
404`.

Fix in `7df93a3`: dropped both `<source>` elements — `<img>` renders the two
PNGs the standalone actually ships. (Alternative: copy the 5 webps, ~200KB, to
root — heavier than this lane's asset set; PNGs are lazy/decoded-async below
the fold.)

## Verified

- Zero `/`-leading refs in the file (Python enumeration over
  href/src/api()/fetch()).
- 22 `http://65.2.28.40/` absolute refs (all API fetches + geojson + page links).
- Zero brand `108` — only `Delhi-Air-108` repo-name URLs remain (infra naming,
  kept per rename scope rule).
- `python3 scripts/check_inline_scripts.py index.html` — OK, 1 inline script
  parses clean (1 prose-in-comment warning, same as server copy).
- Local drive, `python -m http.server 8109` + Chrome:
  - boots to 'Alive' title + `ALIVE` wordmark (no `·108`), nav GET THE APP /
    THE CITY / COMMUNITY.
  - live prod data through the absolute refs: PM2.5 51.8 µg/m³ painting,
    53 stations, 903K road segments priced, dose equation 51.8 × 14.4 = ≈744 µg
    = 2.4 cig, 29 district chips filled, footer `ALIVE — DELHI NCR` +
    `BUILD 05A3B48D` from `/health`.
  - `app-choose-strip-848.png` renders + film gate scroll-cranks through the
    3 real frames; `app-hero-708.png` renders in the mechanics section.
  - Both CTAs → `github.com/<owner>/Delhi-Air-108/releases`.

Shots: `docs/lanes/landing-sync-rename-shots/` (top live hero, film gate,
hero shot, footer/CTAs).

## base/v2 residue check (verify-only)

`server/landing.html@0c5f9cc` — grep `108` = 3 hits, all
`github.com/<owner>/Delhi-Air-108/…` repo URLs. Zero brand `108`.
Clean.
