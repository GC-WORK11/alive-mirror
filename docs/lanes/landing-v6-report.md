# landing v6 — the "more advanced" pass

Lane: landing v6 · file `server/landing.html` · base `base/v2`
Rendered against live prod via a local proxy (`serve.mjs`: static
`/landing.html`, every other path forwarded — GET and the one
sanctioned POST `/v2/plan`). Owner verdict on v5: *"too simple — I
want it more advanced."*

## why v5 read flat

The v5 editorial bones were right (statement → proof → mechanics →
city → close) but the execution levelled everything:

1. **Live numbers described, never performed.** The hero read
   "49.2 µg/m³ ≈ 2.2 cigarettes" as static text — the aqi→µg
   translation the product IS was compressed into one felt line.
2. **The money shot was buried.** The a→b demo required reading the
   mode pill, picking two pins blind, and waiting — inside `.city`,
   third zone down. Nobody in a demo room ever saw the banded route
   arc around the dirty cells.
3. **The timelapse was furniture.** `.trow` sat under the map at
   caption weight — a real 12h CAMS+stagnation forecast presented
   like a footnote.
4. **No depth.** Flat paper, flat cards, uniform rhythm — v5 read as
   a well-typeset document, not a crafted instrument.

## what v6 does about it

### live numbers doing work — the proof zone, built out

- **`.eq` — the equation strip.** The dosimeter's arithmetic drawn as
  arithmetic, all terms live: `47.5 µg/m³` (the NCR mean) `×`
  `14.4 m³/day` (what a pair of lungs moves) `=` `≈682 µg` (the day's
  inhaled dose) `≈` `2.2 cigarettes` — every number from the same
  `/v2/city` payload, hidden until real. Desktop: one hairline-read
  row; ≤640px: stacked terms with `── × ──` op dividers.
- **`.spark` — the next-eleven-hours curve.** A hairline sparkline of
  `next_hours` (same payload — no extra fetch), band-tinted area,
  now-dot in the live band, cap line with the live range and a
  *watch it move on the map ↓* link that scrolls to the scrub deck.
- **The hero numeral counts in** — a 950ms eased sweep on first paint
  (the instrument waking up), instant on refresh, skipped under
  `prefers-reduced-motion`. A 1.1s `setTimeout` fallback guarantees
  the true value lands even if rAF stalls.
- **`#toplive` — the live read follows you.** Once the proof zone
  passes, `pm2.5 47.5 µg/m³ · map 5 min fresh` slides into the top
  bar — same mean the hero counted, same freshness `/health` reads.
  Filled by `paintToplive()` from whichever of `/v2/city` or
  `/health` answers second (the two arrive in either order — first
  version missed this and stayed empty).
- **A live dot everywhere the page speaks for the field** — eyebrow,
  field-head, toplive — all `--he` (band ink), the day's hue doing
  band duty again.

### the a→b route, made the demo it is

- **`.field` is now its own section, "The field, live."** — pulled
  out of `.city` into second place (proof → field → mech → city →
  close), on a `.col-wide` 1120px canvas. The money shot is inside
  the first scroll at 390 and the second viewport at 1440.
- **`.fglow`** — the day's band bleeding as a soft ambient glow
  behind the map card (`--gw` = band washed 55%, blurred 34px,
  sibling behind `.fwrap` so the card's own clip can't eat it).
- **`#demoChip` — "watch it work."** One tap on the map overlay fires
  a REAL `/v2/plan` for connaught place → i.g.i. — labelled as a live
  example, no canned path. It sets a→b mode, drops both pins, calls
  `planAB()`, and hides itself (also hides if the user goes a→b
  manually — they don't need the invite).
- **The route draws on, banded.** `drawSegRoute` renders the served
  `segments[]` — paper casing under each, then per-segment ink in the
  segment's own band hue pulled 26% toward ink — over a 1.1s eased
  rAF reveal with a pen-tip head dot; reduced-motion or missing
  segments falls back to the v5 mono dash-reveal. Clicking a ladder
  option redraws the same way (`drawOption` → `mkRoute` → `kickRoute`).
- **`#ladder` band dots** — each priced option wears a `.lbd` square
  in its own along-route air colour (distance-weighted mean of its
  served segments — `segAvgPM25`, all live, no invented values).

### the timelapse, featured

`.trow` is promoted to a featured control deck inside `.field`:
paper surface, ambient shadow, `▶ WATCH THE DAY` play verb, hour
readout at data weight, the scrub track + thumb filled in `--he`
(band ink). Verified live: `h+0 now → h+2 16:46 IST` advancing on
play, `‖ PAUSE` toggling.

### layered depth

- `.open` gets a faint engineering dot-grid wash behind the lede
  (masked gradient — texture, not pattern).
- The day-strip is a real timeline: every hour-bar washed in its own
  CPCB band (`--dbw` = hue → 74% white), the live hour in the band's
  ink register with a `now` flag — `washHex`/`inkHex`, the same rules
  the app applies.
- Scroll furniture: `.hero-copy` drifts up to −26px and `.shot`
  counters up to ±24px on scroll (rAF-gated, transform-only, skipped
  under reduced-motion); `#toplive` toggles at the proof zone's live
  bottom edge, measured per frame (eq/spark unhide late — a cached
  measurement lies).
- Type stepped up: `h1.lede` clamp(38→66px), `.lead` clamp(26→38px),
  equation terms at 24–34px 300-weight.

## contract, gates, verification

- **Live contract untouched** — every bound DOM id present once,
  every fetch path unchanged; `aqi.js`/loading patterns kept; one
  file, zero new deps.
- `python3 scripts/check_inline_scripts.py` → **OK, 4/4 inline
  blocks parse clean** (run after every edit batch).
- Forbidden strings scan → clean (no `/admin`, `TODO`, `FIXME`,
  `lorem`, `placeholder`, `aether`, `ROUTE_ODS`, `border-radius:999`).
- Required-strings scan → all present (`raster`, `bandCol`, `/grid`,
  `/health`, `/city`, `/community`, `app-hero.png`, `hero-grid`,
  `statusline`, `confSplit`, `fieldAge`, `buildTag`, `dosimeter`,
  `the app knows what you breathed`, `<title>`, `lungs`).
- **Browser-verified, not hoped** (headless Chrome via playwright,
  real prod data):
  - 390px: `docW=390` zero overflowers, `docH≈5.5k`; boot dismisses;
    `hnumV` lands on the live mean (49.2/47.5 across runs — the field
    moved between them); eq + spark painted; demo chip → 5 options
    priced, 5 ladder band dots, chip gone, routeline + departline
    live; toplive `.on` past the proof zone; 24 day-bars, 1 `now`;
    timelapse plays.
  - 1440px: `docW=1440` zero overflowers; same behaviours; toplive
    `.on`; banded route draw confirmed visually.
  - Paint to live numeral ≈300–500ms through the proxy.

## screenshots — `landing-v6-shots/`

| before (v5 live) | after (v6) |
| --- | --- |
| `v5-live-390-top.png` | `v6final-390-top.png` |
| `v5-live-1440-top.png` | `v6final-1440-top.png` |
| `v5-live-1440-f035.png`-era flat field | `v6final-390-f035.png` field zone |
| — | `v6-390-field.png` (map + demo chip + deck) |
| — | `v6-390-route.png`, `v6-1440-route.png` (banded draw) |
| — | `v6-390-eq.png` (equation strip, stacked) |
| — | `v6-390-spark.png` (forecast hairline) |
| — | `v6-390-day.png` (banded day timeline) |
| — | `v6-390-ladder.png` (priced options + band dots) |

## still true / known

- All numbers live; nothing invented — every new element renders only
  when its payload answers (`hidden` until then, same as v5's
  pattern).
- The demo chip is a genuine plan call, not a playback: its
  routeline/depart/ladder all come from the served response.
- Route band dots on a low-spread day all read the same hue — honest
  sameness, not a bug.
