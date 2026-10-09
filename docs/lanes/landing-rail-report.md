# landing-rail lane — report

Owner's brief (verbatim): "the sidebar isn't going well — it is looking very
cheap template of HTML, CSS. Work hard on that." Scope: `server/landing.html`
only — the rail nav + its CSS.

## What was wrong (evidence: `landing-rail-shots/before_*`)

- `.wm` plain 600-weight 15px, default tracking — read as stock sidebar text.
- Four grey 13px links in a stack with generic gaps — a template `<ul>`.
- `.cur` was a 2px green `border-left` bar on "home" — the cheapest possible
  active marker, and it never moved (page links, not section-aware).
- No relation to the page's own register (margin indices `0NN`, hairlines,
  mono labels). The rail is the page's spine at ≥1024px and looked bolted on.

## What it is now

The rail **is** the page's spine — a 1px hairline track with numbered stops:

- `alive▪` wordmark — 700/17px, tight -.02em; the 5px square paints
  `var(--bhex)` = the live band once data lands ("a → live", quietly).
- `#toplive` live read sits under the wordmark (unchanged element/JS).
- `the page` (mono 9px label) → 11 stops, each `0NN` + a plain word
  (right now, the home, the chooser, the stay, the hour, the sum, the map,
  the record, the districts, how it knows, the promise). The `0NN` equals
  the section's printed margin index — JS mirrors the css counter exactly
  (index of each section within displayed `.stack>section:not(.open):not(.noidx)`;
  getComputedStyle can't resolve counters — verified in Chrome, it returns
  the literal `counter(...)` string).
- The section crossing the reading line (IO `rootMargin -34%/-56%`) takes the
  mark: a 7px ink square that **slides** along the track
  (`translateY` on one `.mark`, `.32s cubic-bezier(.22,1,.36,1)`), plus
  `aria-current="location"`. Holds the last stop through section gaps.
- `elsewhere` group under a hairline: the field/delhi/community with quiet
  `→` exits (`home` hidden ≥1024 — the spine covers it).
- `scroll-behavior:smooth` added (RM block already resets to `auto`);
  `.mark`/arrow transitions killed under `prefers-reduced-motion`.
- New section ids: `secNow secHome secChooser secStay secHour secSum
  secField secRecord secDistricts secHow secPromise` (fieldSec untouched —
  `sparkGo` anchor intact).

## Mobile (≤1023px)

Spine hidden; identical top row as before — `alive▪ home the field delhi
community` — verified at 390px (`after_mobile.png`). `.top` stays
`position:absolute` (scrolls away); rail is `fixed` only ≥1024.

## Verification

- `landing-rail-shots/before_desktop_top.png` vs `after_desktop_top.png`
  (1440×900) — template stack → instrument index.
- `after_desktop_mid.png` — mark on `010 the record` with that section in
  view; `after_desktop_map.png` — mark on `007 the map` (superseded, kept
  as a second position proof).
- `after_mobile.png` — 390px row intact, band dot live.
- Script parse-checked (node Function); no dead selectors (`.top nav`,
  `a.cur` greps = 0).
- Served via local static+proxy rig (`/v2/city` → prod) — real data painted:
  `pm2.5 97.9`, band dot `b3` tone, margin indices match spine numbers.

## Files

- `server/landing.html` — rail CSS + markup + spine JS (+ids, smooth scroll).
- `docs/lanes/landing-rail-shots/` — before/after evidence.

## Notes for the next lane

- The `.rn` numbers mirror the css `sec` counter — adding a `<section>`
  automatically renumbers both sides; the JS reruns on `load`.
- `.mark` is a single element translated to `offsetTop+offsetHeight/2` of the
  current link — it lives inside `.spine` (position:relative).
- `#toplive .on` class is toggled by old scroll furniture but has no CSS —
  pre-existing dead class, left alone.
