# lane report — landing overhaul (the page that reads crafted, not assembled)

**scope** `server/landing.html` only (single file, served at `/`). no backend,
no endpoints touched, no PR — pushed to `base/v2`.

## diagnosis — why the old page read "cheap CSS template"

Studied reference landings before touching anything: Linear, Apple product
pages, Arc, Raycast. Their shared grammar: one dominant element per viewport,
colour only where it means something, numerals as instruments not stat cards,
and one action per screen. Then mapped the old page's tells against that
grammar and the repo's own anti-slop list (`docs/20-design-research.md`):

| tell in the old hero | why it read assembled |
|---|---|
| Fraunces-class serif italic headline ("A ledger for your *lungs*.") | literal AI-template signature; the app already retired serif for Satoshi (`Mobile/src/theme.ts`) |
| eyebrow text inside a tinted **pill chip** | named tell in docs/20 — chrome around a label |
| cigarettes as a **stat card** ("2.6 — cigarettes a day") | violates the owner's own rule: cigarettes are a qualifier, never the headline figure; also wrong measure to lead with |
| dense 5-line spec-sheet paragraph ("field-weighted over the ncr lattice…") | explains the machinery before the stranger knows what it is |
| two pastel **door tiles** with icon-in-a-well ("Open the live field", "Community") | named tell — icon-centered-in-colored-tile doors |
| phone screenshot floating in the hero grid | five competing elements in one viewport; no reference page does this |

Net: six small decorated components stacked — a component catalog, not a
page. The fix had to be subtraction + one idea, not another widget.

## the redesign — "the readout"

The hero is now the instrument itself: the zone **wears the day's live CPCB
band as a tonal wash** (`--hw` = band wash, set from `/v2/city` — colour =
the data, the v3 "the air is the canvas" exception), one question
("What did you breathe today?"), then the field mean set huge in a light
grotesque (weight 250, tabular, band-inked — the Satoshi-Light numeral
register the app uses), with `µg/m³` as a small mono unit.

- **cigarettes demoted to qualifier** — "a day of breathing today's field ≈
  2.6 cigarettes" under the numeral, never the figure itself.
- **basis line in mono** keeps honesty on the page: live · field mean over
  the ncr lattice · worst ≈6.5 cig · 22 µg/m³-day ≈ 1 cig (the Berkeley
  Earth conversion from `breath.basis`).
- a 1.5px baseline rule under the readout **breathes** (opacity .10→.30,
  ~4s, reduced-motion safe) — the welcome-film's "digit-field → live number"
  idea reduced to one honest pulse; it shows the number the page actually
  fetched, nothing is animated to fake anything.
- **actions are underlined mono text links** with an arrow, not door tiles.
- the phone artifact moved to "how it works" as proof furniture — the app
  shot earns its place beside the steps it illustrates.
- steps became **editorial numbered rows** (01 measure / 02 interpolate /
  03 dose) on an ink top-rule instead of uniform pastel cards.
- the proof line leads the how-section: "Dose-priced routing is the proof
  the field can decide — the engine priced 0.90 million of 1.07 million
  road edges under this hour's field."
- `em` in the h1 is styled `color:var(--ink2)` — the word *breathe* quiets,
  like a breath; no italic serif.
- `sub` rewritten as one breath of copy: "A personal dosimeter for Delhi —
  no hardware. The field below, rebuilt every 15 minutes from 54
  instruments, is the sensor, and the app knows what you breathed — a
  ledger kept on your phone, where only k≥3 aggregates ever leave."
- boot strip numeral switched to the same light sans so the film resolves
  into the same face the hero displays.

DOM/JS contract held per `docs/lanes/register-card.md`: every id queried,
every JS-emitted class, every test-mandated string survives. Changes are
wrapper markup + CSS + emit tweaks only; no element or fetch removed.

## live numbers — every one still real

Verified against prod (`alive108-…elb.ap-south-1.amazonaws.com`) while the
new page ran locally through a GET-only proxy (`/tmp/landing_proxy.py`):
page at `/`, all other GETs proxied — the rendered screenshots below show
real data, not fixtures.

| on the page | source | live value at verify |
|---|---|---|
| hero numeral | `/v2/city → breath.pm25_ugm3.mid` | 56.7 µg/m³ (band b1, satisfactory) |
| felt line | `breath.cigarettes.mid` | ≈2.6 cigarettes/day |
| worst | `breath.cigarettes.hi` | ≈6.5 cig |
| basis | `breath.basis` | "22 µg/m³-day ≈ 1 cigarette" (Berkeley Earth) |
| 54 instruments | `/health → sources.stations.count` | 54 |
| 0.90M / 1.07M edges | `/health → routing.edges_priced/edges` | 903,058 / 1,070,459 |
| field freshness | `/health → field_age_s` | ~8–11 min during shots |
| median / wind chips | `/v2/city → pm25_stats.median`, `/health → wind` | 50–53 µg/m³ · 7 km/h |
| −50% vs typical | `/v2/city → typical.vs_now_pct` | −48.6% |
| 95.2% ±2σ, 3,550 pairs | NUMBERS.md canonical, linked to field_validation.md | static claim, unchanged |
| map / day / districts | `/grid`, `/today`, `/v2/districts`, geojsons | all live, untouched |

Everything else on the page (raster map, watch-the-day timeline, typical
day strip, district chips, skill line, why-tonight line, footer build tag)
is unchanged machinery — still wired to `/grid`, `/v2/skill`, `/v2/why`,
`/v2/districts`, `/today`, `/health`.

## before / after

`landing-overhaul-shots/`: `before_*` = prod as it ships today;
`after_*` = new page locally against live prod data.

- `before_desktop.png` / `after_desktop.png` — 1440px, full page
- `before_mobile.png` / `after_mobile.png` — **true 390px** (CDP
  device-metrics; headless `--window-size=390` silently floors layout at
  500px — both old and new shots showed fake clipping until measured via
  `Emulation.setDeviceMetricsOverride`)

## test contract

`server/tests/test_landing_serve.py` markers: all 16 REQUIRED present
(`<canvas`, raster, paint, bandCol, `/grid`, `/health`, `/city`,
`/community`, `/app-hero.png`, hero-grid, statusline, confSplit, fieldAge,
buildTag, dosimeter, "the app knows what you breathed"); all FORBIDDEN
absent (lorem, TODO, placeholder, 999px radius, aether, ROUTE_ODS,
`/admin`); JS braces balanced, `setInterval` + `fetch(` intact.

## known residue / next lane

- `.fpop` place names + district aqi numerals still use `--serif` in tiny
  spots (field popover, district chips). Left as the "place label" voice;
  if a future lane wants full sans coherence, it's a 3-line change.
- the boot strip, popovers, timeline, district chips are untouched
  machinery — they already read crafted.
