# web-nits — lane report

Mandate: `docs/lanes/web-nits.md`. Folds web-cold-eye's three flagged nits
plus the accent-canon decision into `server/landing.html`, `server/city.html`,
`server/community.html`, `server/admin.html` on base/v2. Zero features
removed; every JS-queried `id`, emitted class and test-mandated string
preserved.

## Fixed

| Surface | Flag | Fix |
|---|---|---|
| `/`, `/city`, `/community` | **Accent drift.** Landing + /city ran sage `#4D7C0F`/`#3D610A`/wash `#EEF2E2`/tint `#E3E9D3` while the register canon (docs/lanes/register-card.md) is forest — "web siblings track the register, not a fork". | Canon swap on all three surfaces: `--acc/--sage → #3A6844`, ink `#2B4E32`, wash `#EAF0E4`, tint `#DCE7D1` — forest, not olive. Derivatives re-hued: `.door:hover` box-shadow → `rgba(43,78,50,.35)` (was sage-tinted); landing favicon dot + `/city` minimap self-dot → forest. `grep` over all three files: zero remaining sage hexes or `rgba(77|61,…)` literals. |
| `/admin` | Same drift, different direction — blue `#2456D6`. | **Kept, canonised.** Per the lead's decision this is the ONE documented backstage exception — now recorded in `register-card.md` ("a deliberate 'engine room' backstage hue … canon-by-exception, not drift") plus a new first row in the Web component-grammar table. File itself untouched. |
| `/` | **`.day-head`/`.dist-head` qualifier wrap.** At ≤640px the `<b>` qualifier (`a typical october, hour by hour`, `29 real boundaries, each filled live`) was a flex item inside `display:inline-flex` `.lbl` — it broke to a second line and sat right-shifted against the edge, reading like a stray column. | `@media(max-width:640px){ .day-head .lbl, .dist-head .lbl{ display:block; line-height:1.9 } }` — the qualifier flows as one continuous run wrapping left-aligned. Placed *below* the `.lbl` definitions in the stylesheet: first attempt sat earlier and `.dist-head .lbl`'s later equal-specificity `inline-flex` silently won — verified fixed only after the move. `.field-head .lbl` shares the pattern but its text is short and undisturbed at 390px (after/landing-390-fieldhead.png). |
| `/city` | **`.detail` popover dock.** Pinned `bottom:170px` against `.map-card`; measured at 390px the card spanned y 1811–1956 while the legend/days stack top sat at y 1820 — the popover painted *over* the day tiles on real content (before/city-390-popover-overlap.png). Root cause: `.map-card`'s height grew once the cold-eye fix moved controls/legend/days in-flow, so a bottom anchor floated far below the map it describes. | New `.map-view` wrapper (`position:relative`) around `svg#ncr` + `.m-wind` + `.detail`; mobile dock becomes `bottom:12px;left:12px;right:12px` — the card now sits inside the map's bottom edge and can never drift over the legend/days. Desktop unchanged (`top:66px` overlay; after/city-1280-popover.png). |

## Verification — 390px (CDP `Emulation.setDeviceMetricsOverride`, DSF 2, mobile:true) + 1280px

Captures committed under `docs/lanes/web-nits-shots/{before,after}/`.
Method per the cold-eye tooling note; `.rv` reveals forced `.in`; the
district popover opened via the page's own `highlight(name)` global.

| Capture | Result |
|---|---|
| `landing-390-hero` | Before: sage LIVE chip/eyebrow/door tile. After: forest `#3A6844` — deeper, muted; clay `community` door contrast preserved. |
| `landing-1280-hero` | Same swap at desktop width; no layout shift. |
| `landing-390-dayhead` | Before: qualifier right-shifted line 2. After: `the day, recorded — a typical october, hour by hour` flows as one run. |
| `landing-390-disthead` | Before: tick + `the districts —` squeezed into a narrow left column, qualifier floated right. After: single run `the districts — 29 real boundaries, each filled live`, `tap a boundary · worst first` hint clean. |
| `landing-390-fieldhead` | After-only: `pm2.5 — the field, this hour` unaffected at phone width (shares the inline-flex pattern, no squeeze — chip row takes the overflow). |
| `city-390-popover` | Before: popover bottom-anchored to `.map-card`. After: docked inside the svg's bottom edge; legend + day tiles fully clear below. |
| `city-390-popover-overlap` | Before-only evidence: popover painted over the day-tile peek strip (~140px card overlap, measured rects in notes). |
| `city-1280-popover` | Before/after identical: top-left overlay inside the map, legend and controls clear. |
| `community-390` | After-only: eyebrow tick + accents now forest; no sage left. |
| `admin-390`, `admin-1280` | After-only: blue accent unchanged by design — OPERATOR SIGN IN chip, links, status dot all still `#2456D6`. |

Page geometry: `scrollWidth=390` on all surfaces — no horizontal
overflow introduced. All four routes curl-clean: `/` `/city` `/admin`
`/community` → 200.

## Suite

`cd server && PYTHONPATH=core/build312:. .venv312/bin/python -m pytest tests`
→ **1136 passed**, 7 skipped, **13 failed — all pre-existing on base/v2**,
verified by running the same three files against a stash of this lane's
changes: `test_path_legality::test_priced_objective_matches_display_integrand`,
`test_path_parity` (2), `test_reach` (10). All are `alive_core.PathEngine`
C++-extension parity tests (missing `reach`, dose-integrand mismatch) — a
stale `core/build312` build on this box, untouched by this lane. Every
web-facing test (`test_landing_serve`, `test_city_moves`, community/admin
serves) is green, including `test_landing_script_wellformed`'s brace-balance
and `test_landing_machinery_intact`'s marker list.

## Files

`server/landing.html` — 5 edits (vars, favicon, hover shadow, media-block
`.lbl` fix, comment). `server/city.html` — 4 edits (vars, `.map-view`
wrapper + comment, minimap dot, mobile `.detail` dock).
`server/community.html` — 2 edits (favicon, `--sage`).
`docs/lanes/register-card.md` — admin blue recorded as the documented
backstage exception + grammar-table row. `docs/lanes/web-nits-shots/` —
17 before/after captures.
