# web-cold-eye — lane report

Mandate: `docs/lanes/web-cold-eye.md`. Hostile stranger-comprehension pass
on `/` (landing), `/city`, `/admin` at desktop ~1280px and phone ~390px.
Surfaces audited on repo source — **live HTML verified byte-identical** to
`server/landing.html`, `server/city.html`, `server/admin.html` at HEAD
`84649bd` (curl + diff, all three). Live targets read-only; no POSTs, no
deploys. Admin audited as the public shell — `~/.alive_admin_token` is
absent on this box, so gated panels were read through their honest-empty
states exactly as a stranger sees them.

Method: full-page captures via headless Chrome + CDP device-metrics
override (DSF 2, mobile flag). **Tooling note for future lanes:** plain
`--window-size=390` headless shots are unreliable for this site — the page
renders at a ~500px layout and clips, which looks like breakage but is an
artifact. Real phone emulation needs `Emulation.setDeviceMetricsOverride`
(probe confirmed `scrollWidth=390`, no page overflow, on both / and /city).
The `.rv` reveal-on-scroll sections on /city stay `opacity:0` in
full-page captures unless `.in` is added — a capture artifact, not a bug.

## Fixed (commits on base/v2)

| Commit | Surface | Bug | Fix |
|---|---|---|---|
| `b5b5a60` | `/city` | **Phone breakage, real.** At ≤640px the absolute `.m-tag` ("districts coloured by the govt air score · each district averages the map squares inside it · tap a district for its number") was capped at 60% width → ~6 lines of 10px mono painted *over* the top-left quarter of the district map — illegible over green fills and it hid district labels. | Inside the ≤640 media block the tag drops off the map: `position:static` + hairline + padding, rendering as an in-flow caption row between the svg and the control rows — the same register `.tl` already uses, matching the codebase's own "in-flow … so it can never cover geography" rule (city.html:133). Desktop (>640px) unchanged: still a 2-line top-left overlay. Verified on the local file render. |
| `e5b35d6` | `/admin` | **Boot blocker.** `tick()` fired `window.prompt()` ("paste the operator token") *before first paint* on every load — a phone judge lands on a modal, and headless captures froze outright (the prompt blocks the event loop; `Page.navigate` never settled). | Boot prompt deleted. Public feeds + `gated — operator token required` honest-empties paint immediately (the "8 GATED — NO OPERATOR TOKEN" feed chip and "public view" statusline already say what is missing). New `.tokbtn` chip in the masthead: `operator sign in` → prompts on demand (the operator's own tap, so blocking is honest) → `sign out` once a token is stored. `#whyline2` also joined the all-failed placeholder rewrite list — it could sit on "connecting…" forever during a total outage. Verified at 390px on the local file: full page paints, zero modals. |
| `69b3b4c` | `/city`, `/admin` | **µg → "mg" unit corruption.** The register uppercases captions/pills/headers; a bare `µ` inside renders as `Μ` — visually "mg", a 1000× unit error. The codebase already carries the `text-transform:none` opt-out convention; four spots leaked: reach budget pills ("≤50 µg" → "≤50 ΜG"), reach arm note ("≈316 µg" → "≈316 ΜG"), replay delta note ("±N µg … µg/m³"), admin scorecard thead ("mae µg/m³" → "MAE ΜG/M³"). | Each unit wrapped in `text-transform:none` spans. `rchNote` + the delta note now write `innerHTML` so the span can opt out — all callers pass static strings + numbers, nothing user-derived. |
| `e360bdd` | `/` | Same class: the skill line wrote ASCII `ug/m3` inside `.day-note` (uppercase) → rendered `39.8 UG/M3` while the rest of the site writes `µg/m³`. | `µg/m³` with the opt-out span. |
| `c25428c` | `/admin` | Archive strip printed `1 GAPS` when exactly one hour was missing. | `1 gap / N gaps`. |

## 3-second test — per surface

| Surface | 1280px | 390px |
|---|---|---|
| `/` hero | PASS — "1.8" + "cigarettes a day — what breathing today's field adds up to" + LIVE chip + provenance line under the numeral; a Delhi reader gets dose-as-cigarettes instantly. | PASS — same stack, doors go full-width, app shot follows. |
| `/` field/day/districts | PASS — raster card + caption "1,156 cells, 20.5–70.1 µg/m³ · cell fade = distance to nearest sample" + "349 measured · 735 interpolated · 72 thin" confidence counts; recorded-day strip + "RECORDED HISTORY, NOT A FORECAST"; district chips band-washed with aqi numerals, worst-first. | PASS — chips scroll horizontally *by design* (verified: page `scrollWidth=390`, only the chip strips scroll internally). |
| `/city` hero + map | PASS — "Delhi NCR air, right now." + dek explains AQI/pm2.5/µg-m³ plainly; district fills + legend "under 100 is fine for most people · 200+ sensitive lungs feel it · 300+ everyone does". | PASS after fix — the caption no longer covers the map. |
| `/city` controls (tl/rch/rc) | PASS — three honest control rows; every caption carries real counts ("N km of roads reachable · N road segments drawn", "N hours saved today"). | PASS — pills wrap, rc-strip scrolls internally (intended). |
| `/city` ledger/prov/corridors | PASS — 5 stat tiles with honest sub-text ("totals only; no per-person data exists"); provenance card with minimap + "typical error ±46.1 µg/m³"; corridors table with k≥3 explanation. | PASS — grid collapses to 1 column; corridors rows stay legible. |
| `/admin` shell | PASS — "engine room" + statusline carries build/field/age + "public view — operator token unlocks internals". 6 of 9 KPI tiles show "insufficient data" — honest, and the reason is stated on-page. | PASS after fix — no modal; everything stacks. |

## Provenance-line honesty (check 2)

Verified live strings — every caption names its source:

- `/`: "median of 24 live stations" chips, "field-weighted over the ncr
  lattice · ~14.4 m³ breathed a day · 22 µg/m³-day ≈ 1 cigarette",
  "the archive's median for this hour — october · ist · connaught place ·
  recorded history, not a forecast", "only k≥3 aggregates ever leave it".
- `/city`: "waqi-stations+open-meteo/cams · 68 points fitted · 24 live
  stations · gap-filling on", "map rebuilt N min ago · nearest map square
  N km away · typical error ±N µg/m³", district tile "mean of N covered
  cells / centroid read", GRAP "computed here, not the official caqm call".
- `/admin`: per-feed table literally labels live/dormant/down with the
  *reason* ("data.gov.in keyed adapter — dormant while waqi wins the
  chain", "key unset"), fire feed "firms-public-csv · fetched 3h ago",
  scorecard "122 pairs over 18 recorded hours · bias +37.9 (we
  over-called)".

No hand-waving found. The failed-placeholder chain was extended, not
rewritten (whyline2).

## Mini-words ration (check 3)

No systemic violations — the register is already disciplined (number +
unit + ≤3-word labels on all stat/chip grammar). Sentence-length copy
survives only where it's *provenance* (dek, footer paragraphs, method
captions) — allowed. Borderline: the hero basis line packs 5 clauses of
mono caps (~40 words) under the numeral — dense but every clause is a
source, kept.

## Phone-viewport breakage (check 4)

- **Fixed:** `/city` m-tag (above), `/admin` boot prompt (above).
- **Nit, flagged not fixed:** `.day-head` / `.dist-head` labels on `/`
  squeeze their `<b>` qualifier into a right-shifted second line at
  390px ("THE DAY, RECORDED — / A TYPICAL OCTOBER, HOUR BY HOUR").
  Legible, mildly awkward.
- **Nit:** the `.detail` district popover docks `bottom:170px` over the
  map — with the caption now in-flow it can briefly overlap the m-tag row
  when open on phones. Opaque card over a caption — acceptable; watch it.
- Horizontal scrolls that exist (`.dscroll`, `.dayrow`, `.rc-strip`,
  `.chips`, `.scrollx`) are intended and carry scroll-shadow hints.
- False positive recorded so nobody re-chases it: `--window-size=390`
  headless captures clip at ~500px — CDP emulation showed no real page
  overflow anywhere.

## Anti-list sweep (check 5)

No violations — no neon, no cyberpunk, no 3D, no decorative SVG.
**Flagged as data, not decoration:** raw CPCB hues appear on (a) the
recorded-hours squares on /city and /admin archive strips (yellow
squares = recorded band), (b) the day-ahead tiles (each washed from its
own day's band — the pastel-yellow "today" is Moderate's hue at ~78%
wash, not a palette choice), (c) district fills. All are official-band
color carrying meaning; the register's muted washes soften everything
around them.

## Register consistency (check 6)

- **Flag — accent:** `/admin` runs blue `--accent:#2456D6`; the app
  register is forest `#3A6844` and register-card.md says web siblings
  track it, "not a fork". Reads as a deliberate "engine room" backstage
  hue — decide whether to document the exception or align.
- **Flag — drift:** `/` + `/city` use sage `#4D7C0F` — a third hue, close
  to but not the register's forest. One accent source of truth would
  settle it.
- Typography/geometry otherwise hold everywhere: Fraunces display,
  Inter body, mono numerals, 14–16px radii, hairline borders, tinted
  chips, honest empties.

## Figures touched — for the deploy check to curl

- `GET /` → `server/landing.html`: skill line now emits
  `µg/m³</span></b> on average` (grep `text-transform:none` inside the
  skillLine innerHTML at ~:1449).
- `GET /city` → `server/city.html`: m-tag CSS (`position:static` inside
  the ≤640 block), budget pills emit `≤N <span
  style="text-transform:none">µg</span>` (~:1218), replay-delta note
  writes `innerHTML` with unit spans (~:993), reach arm note (~:1231).
- `GET /admin` → `server/admin.html`: masthead now contains
  `id="tokbtn"` / "operator sign in"; the boot `prompt('…paste the
  operator token, or cancel…')` is gone (only the on-demand prompt
  remains); `#whyline2` in the placeholder list (~:610); scorecard
  thead `mae <span style="text-transform:none">µg/m³</span>` (~:1847);
  archive `gap${cov.gaps.length===1?'':'s'}` (~:1883).

**Deploy-side watch:** after these statics deploy, the demo flow for
`/admin` changes — first paint is the public board; click "operator
sign in" to get the token prompt (was: automatic modal on load). The
demo-recording notes describe the old auto-prompt.
