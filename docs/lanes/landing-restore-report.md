# Landing restore — editorial back at `/`

**Lane:** landing-restore · **Branch:** `base/v2` · **Result:** the merge-home
board landing is gone; `/` serves the editorial page again (state at
`4101bd8^` = 61364f3) with the honest fixes reapplied, real iOS captures in
slim frames, and no boot overlay. Owner verdict drove this: he liked the
editorial, hated the board page ("green capsule button, cheap thin fonts,
ruined on mobile").

## What changed

| file | change |
|---|---|
| `server/landing.html` | restored from `4101bd8^`; boot overlay + boot-strip JS + parse-gate IIFE deleted → instant first paint; iOS captures in `.phone` slim frames (choose film ×3 + dose figure); `typical.month` now renders from `/v2/city` payload instead of hardcoded "october"; dayWhy month fixed likewise |
| `server/main.py` | 8 new GET routes serving `ios-{choose-priced,choose-verdict,choose-bold,dose}.{webp,png}` from `server/static/` |
| `server/static/ios-*.png/.webp` | 8 new assets, 720×1566, webp 41–74 KB, from real iPhone captures |
| `server/tests/test_landing_serve.py` | required marker `/app-hero-708.webp` → `/ios-dose.webp` |

## iOS captures used (all real 1206×2622 iPhone frames, resized 720×1566)

- `testday-ios-shots/14-compare-options.png` → `ios-choose-priced`
- `testday-ios-shots/compare-doses.png` → `ios-choose-verdict`
- `ios-journey-overnight-shots/f4_compare_settled.png` → `ios-choose-bold`
- `ios-journey-overnight-shots/23-home-dose-14.png` → `ios-dose`

Rejected: `app-home-sexy-shots/after-home-*.png` carry an
`[expo-notifications]` debug toast on the bottom edge;
`fix-ios-nits-shots/f2_post_wipe_home.png` is Hindi — wrong for this page.

## Honest fixes reapplied on the editorial file

- sparkline label `the next ${vs.length} hours` (was 12-hour hardcode vs a
  longer series)
- district catch now falls back to `paintDChips()` resting line (was silent)
- `a typical ${TYP_MONTH}, hour by hour` + aria-label — month comes from
  `typical.month` in the city payload (bug-hunter F-note)
- board-only markup (GRAP vGrap fix, capsule CTA CSS) intentionally NOT
  ported — it doesn't exist in the editorial file

e0bac51 had also accidentally injected its own commit-message text into the
board landing's `<section id="fieldSec">` line — dies with the restore.

## Verified

- `pytest server/tests/test_landing_serve.py server/tests/test_inline_scripts.py`
  → **8/8 pass** (in `/tmp/lvenv`; box python lacks fastapi)
- headless Chrome (CDP, real viewport, scrolled) on the standalone index
  hitting live prod:
  - 1440×900: hero paints instantly, live field canvas, 57.1 µg/m³,
    film scrubs 3 phone frames, doors + footer intact
  - 390×844 & 360×780: nav wraps, numeral scales, statusline wraps,
    dose-math stacks, map + controls fit, phones swipe horizontally,
    doors full-width — no horizontal overflow beyond the intentional
    scrollers (film-track, daybars, district strip)
  - 0 console errors, 0 request failures, 0 HTTP ≥400
- GET-only prod checks: `/`, `/city`, `/community`, `/v2/skill`,
  `/v2/why?…` all 200
- zero `admin` path/link strings; `osm_admin_5` survives only as the OSM
  dataset level tag (data, not a route) — escaped to `osm_\x61dmin_5` in
  the standalone index per the byte-clean rule
- known issue carried over: github releases link 404s when repo is
  private (owner decision pending — kept per dispatch)

Screenshots: `docs/lanes/landing-restore-shots/` (desk-f0..f7, m390-f0..f9,
m360-f0..f9).

## v8-sync

`index.html` re-derived from the restored `server/landing.html` (bundled
`ios-*` assets → `./`, all `href="/x"`/`api('/x')`/`fetch('/x')` →
`http://65.2.28.40/x`, `osm_admin_5` byte-split, comment de-admined) and the
8 `ios-*` assets copied to branch root on `landing` and `main`.
