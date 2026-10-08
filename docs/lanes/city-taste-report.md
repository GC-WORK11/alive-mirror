# Lane report — city-taste (server/city.html, server/community.html)

HEAD at start: `286f0f3` on `base/v2`. Scope: light-touch register pass on
the two public pages behind the v8 landing; structure, sections and every
live element kept.

## Design Read (stated before touching pixels)

Two public instrument surfaces for demo viewers — /city is the live
choropleth, /community the shared-trips ledger — in the product's
warm-neutral register, being tightened one generation to the v8 landing
standard: light sans numerals over serif, ambient shadow over hairlines,
tonal controls over chip soup, band color only where it means air. Light
touch: same sections, same live elements, same honesty copy.

## What changed

**Number hierarchy (both pages).** The hero mean, stat-tile values,
district-detail aqi and ledger values moved from `--serif` 400 to
`--sans` 300 — the landing's numeral register. Mono units/captions
unchanged; serif still carries headlines where it already did.

**Ambient shadow.** `.htoday`, `.map-card`, `.stat`, `.minimap`,
`.card2`, `.day`, `.pt` traded the 1px/-3px micro-shadow (and the
inset-ring look on chips) for a soft `0 2px … -8px` ambient spread;
frame borders on enclosed cards softened to `--line2`. Hairlines that
are grammar (section index rule, ledger rows, ticker rules, table rows)
stayed.

**Chip discipline.** Legend `.chip`s, `.m-src`, ticker spans and the
`.wtag`s are now flat tonal `--surface2` pills (r999, no inset ring, no
white-on-ink). `.sec-n` and the pipe-tile `.n`s lost their chip frames
entirely — plain mono numbers, matching the landing's quiet section
register. `.tl button`s keep the surface2 grammar with a lighter shadow.

**Bugs fixed in passing (all visible on prod before this):**

- `.whyline[hidden]` — `display:flex` on the class was beating the
  `hidden` attribute, so the three callout tiles rendered empty with
  floating tags on first paint. Now `.whyline[hidden]{display:none}`,
  same pattern `.tl` and `.days` already used.
- `across the map: … ΜG/M³` — the uppercase `<i>` gloss was uppercasing
  `µg` → `ΜG`. The unit now sits in a `text-transform:none` span; same
  fix on /community's statusline `µg breathed`.
- **Freshness F1 / F8** — landed by `a7814cb` mid-flight; rebase kept
  upstream's epoch+900s `tlInvalidate()`/`tlAged()` and the `Math.min`
  600 s poll clamp (functionally the same fix this lane had written —
  horizon cache expires on field rebuild or one field cadence, and the
  "next rebuild in N min" disclosure can't outlive the field TTL).

## Band-color discipline

Unchanged — band wash still only on the today card, day tiles, legend
swatches, district fills and the dose chips. The `.wtag` chips went from
ink-dark to neutral; no new band or accent color introduced anywhere.

## Rename-lane note

No `108` strings touched. `ALIVE·108` masthead mark left for the rename
lane.

## Verification

- Server booted locally (`uvicorn main:app :8108`, fresh field build,
  0 stations → honest "no live instruments" states verified).
- Before/after shots: `docs/lanes/city-taste-shots/` —
  `city-before-desktop-top.png`, `city-before-desktop-bottom.png`,
  `city-before-390-top.png`, `community-before-desktop-top.png`,
  `city-after-desktop-top.png`, `city-after-desktop-mid.png`,
  `city-after-390-top.png`, `community-after-desktop-ledger.png`.
- Live elements confirmed rendering post-change: today card + band
  wash + breathing ring, why/grap/parali tiles, band legend, forecast
  scrubber row, recorded-hours strip, days-ahead tiles, wind tag,
  ticker, ledger stats, corridors table, statusline, community ledger
  grid + pipe tiles.
- Inline `<script>` blocks pass `node --check` on both files.

## Deferred (not this lane)

- Wind tag carries no age of its own; the fieldmeta line
  ("map rebuilt N min ago") is the page's disclosed-age carrier —
  adding a separate wind age would be a copy change, not a taste one.
- Em-dashes in body copy kept — they're the house voice and the v8
  landing uses them; the vendored skill's em-dash ban doesn't override
  the product register.
