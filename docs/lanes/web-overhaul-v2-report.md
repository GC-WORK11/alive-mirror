# web-overhaul-v2 — lane report

Mandate: `docs/lanes/web-overhaul-v2.md`. Register extended (not forked) in
`docs/lanes/register-card.md` § *Web component grammar*. All three server
templates redesigned component-by-component; **zero features or numbers
removed** — every id queried by JS, every emitted class, and every
test-mandated string survives.

## What changed, per surface

### landing (`server/landing.html`)
- `:root` now carries the full register: `--surf/--surf2/--surf3`, accent
  quartet, `--b0..5` plus washed `--bw0..5`, deeper `--bd0..5`, band-ink
  `--bi0..5`.
- Hero = eyebrow accent-chip + serif head + **one hero stat tile**
  (`.hnum`: accent-chip `LIVE` + 80px serif `4.7` + unit line + provenance
  caption). The two outbound links became `.door` tiles — 36px solid icon
  block + name + ≤3-word caption + arrow (`/city` accent, `/community`
  band-deep warm).
- `.statusline` spans → chip tiles; `.psel` segmented pill (surface2 track,
  white-card active); `.fwrap` rounded-16 framed map card; `.trow` control
  strip; `.routeline`/`.depart` tinted tiles; `.lrow` rows → tiles with
  `.rec` accent-bordered recommendation.
- `.daybars` 24-hour strip lives inside one rounded tile; `.dscroll`
  districts emit band-washed `.dchip` tiles (`--cw` per district via new
  `washHex(d.color, .82)`).
- `.steps` = three pastel step tiles (`s1` bd0, `s2` bd2, `s3` bd1) with
  numbered chips replacing the flat `.how` rows.
- Section labels get `.sec-tick` 6px squares (`.t-acc`, `.t-b2`, `.t-b3`).

### city (`server/city.html`)
- Same `:root` extension. `.eyebrow` → accent chip; `.whyline`/`#grapline`
  → tinted callout tiles; `.wtag` → solid accent chip.
- `.map-card` radius 16 + soft shadow; `.chip`/`.tl button`/`.m-src` all on
  chip grammar; reach arm + `.rch-pills` active = accent-wash selection.
- `.days` → five band-washed `.day` tiles (`--dw` = `washHex(bandCol, .78)`
  — pastel tile surface, true CPCB dot kept on `.dv i`); `.detail` popover →
  radius-12 card; `.ticker-in` items → surface chip tiles.
- `.ledger` stats → tile grid alternating accent-wash/surface2, `.k` chip
  labels, clamp(32–42px) serif numerals with small units, `.d` captions —
  provenance moved out of prose.
- `.sec-n` → accent chips; `.minimap`, `.card2`, `.dose-chip`, `.modep`,
  `.live-sq` on the same radius grammar.

### admin (`server/admin.html`) — look kept, comprehension layered
- Every headline/stat tile now emits `.kchip` (severity-tinted label chip
  ABOVE the numeral — `.accent`/`.brick`/`.wine` by health) + serif numeral
  + `.cap` caption (provenance as a 9px mono caption, not a paragraph).
  Same emit in `paintShared`, `paintArchive`, and the wide archive cards.
- `h2::before` = 6px accent square (sec-tick grammar); `.fmsel` buttons →
  chips with accent-wash selection; `.pipe` stages → surface2 `.st` tiles
  with numbered `.n` chips.
- `.priv-badge`, `.feed`, `.pill`, `.badge`, `.ah`, `.dt-aqi` radii tuned to
  the chip scale. Tables, `.prov` segments, `.fmpop` clip-path, `.kv`,
  `.whybig` — untouched, per the owner's "i like the way it looks".

## Gate

`cd server && PYTHONPATH=core/build312:. .venv312/bin/python -m pytest -q tests`
— **1136 passed, 7 skipped, 0 failed.**

Note: the first run showed 13 failures in `tests/test_reach.py` +
`tests/test_path_parity.py` — `alive_core.PathEngine` was missing the
`reach` binding because `core/build312/alive_core.*.so` (built Oct 4)
predated the binding. Rebuilt via `core/build_ext.sh`; all 41 affected
tests now pass. Unrelated to the HTML work — environment staleness only.

## Screenshots (1440px landing/city, 1200px admin full-page)

| surface | before | after |
|---|---|---|
| landing | [before](web-overhaul-v2-shots/before-landing.png) | [after](web-overhaul-v2-shots/after-landing.png) |
| city | [before](web-overhaul-v2-shots/before-city.png) | [after](web-overhaul-v2-shots/after-city.png) |
| admin | [before](web-overhaul-v2-shots/before-admin.png) | [after](web-overhaul-v2-shots/after-admin.png) |

## Anti-list audit

No neon/cyberpunk/glow, no 3D, no SVG noise, no lime/chocolaty/cheap-yellow,
no gratuitous animation — light `muted-expensive` only. All fills are solid
washes (blend toward white, never alpha). Not deployed — the lead deploys.
