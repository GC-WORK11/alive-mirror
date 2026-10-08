# Lane report — plain-words copy sweep

Branch `base/v2`. Owner verdict this lane answers to: "language is complex,
slop of words too technical; but when it makes simple it makes cheap. The
way it tells the news in delhi-air-right-now is so complex you'd have to
kill your eyes to understand it."

Bar used: felt-words, short clauses, no lab jargon, no adjectives doing the
work numbers do. Every number stays live data — words changed, numbers
didn't.

## 1 · the /city story block (`server/v2/why.py`)

The "delhi air right now" narrative is three lines under the hero
(why-line, grap, parali-watch note). All variables verified live:
belt_fires, belt_delta, wind direction/speed, carry gate, stagnation
factor, trend endpoints all trace to `cause_note_fields` / `evaluated` —
nothing hardcoded was found pretending to be live.

`_cause_note` (the news line) — before → after, same live values:

- `"44 fires in the Punjab–Haryana belt, up from 20 over ~4 h — a NW wind
  at 9 km/h is carrying it toward Delhi"`
  → `"44 fires in the Punjab–Haryana belt, up from 20 4 hours back — a
  north-west wind at 9 km/h is carrying it our way"`
- `"air barely mixing — ventilation 1,612 m²/s vs ~3,000 typical"`
  → `"the air is barely moving — clearing at ~54% of its usual pace"`
  (same factor, said as the clearing pace a reader can feel)
- `"city mean 64.8 → 49.2 µg/m³ over 6 h"`
  → `"the city's average eased 64.8 → 49.2 µg/m³ in ~6 h"`
- `"smoke inflow meeting still air"` → `"smoke coming in while the air
  sits still"`
- `carrying=false`: `"the wind isn't carrying it this way right now"`
  → `"the wind is carrying it away from us"` (the verdict, in words)
- wind unknown: `"wind unknown, can't tell if it's coming"`
  → `"wind unread, can't tell if it's coming our way"`
- quiet belt: `"a quiet belt — 3 fires"` → `"the belt is quiet — 3 fires"`
- empty answer: `"local background — no big driver in play right now"`
  → `"the usual local air — no big driver in play right now"`

`_line` joins drivers `"a + b"` → `"a and b"` (prose, not math); fallback
`"local background"` → `"the usual local air"`. Compass initials (NW) now
expand to words ("north-west") inside the note, same as the line already
did.

`drivers[].evidence` keeps its engineering register (FRP MW, m²/s) — it's
the raw-evidence surface behind "the evidence ↗", the engine-room read.

### freshness

New payload field `story_age_s` on `/v2/why` + `/v2/city` `why` block:
the worst staleness of the note's ingredient reads (fires feed, wind,
mixing, newest recorded build). Surfaces as "updated N min ago" — the
freshest claim the story can honestly make, matching the existing
disclosed-age pattern (`map rebuilt N min ago`).

## 2 · /city statics (`server/city.html`)

- tag `"why tonight"` → `"why now"` (the line isn't time-of-day bound)
- dek: `"government air score"` → `"official air score"`, `"driven by"` →
  `"mostly"` — same facts, fewer syllables
- map tag: `"each district averages the map squares inside it"` →
  `"each is the average of the air inside it"`
- grap line: `"today's air maps to GRAP stage II rules — aqi N on the
  city's live pm2.5 · computed here, not the official caqm call"` →
  `"this air reads like GRAP stage II — aqi N on the live city map · our
  read, not the official caqm call"`
- source line: `"open-meteo/cams · 14155 points fitted · 0 live stations
  · gap-filling on"` → `"the satellite model · 0 live stations · 14155
  map squares · the gaps estimated between them"` (source token mapped
  to words; `stations`/`points fitted` stay real)
- fieldmeta: `"nearest map square 0.4 km away · typical error ±8.2
  µg/m³"` → `"nearest read ~0.4 km away · usually within ±8.2 µg/m³"`;
  `"not yet calibrated"` → `"error band not yet measured"`
- provenance: `"each live reading counts triple next to the European
  satellite model (CAMS)"` → `"each one outweighing the satellite
  model's guess three to one"` (the 3× weighting, in words)
- corridor table: `"pm2.5 per trip"` → `"fine dust per trip"` (unit still
  on the cell value)
- the note line now ends `· updated N min ago · measured, not reported`

## 3 · landing (`server/landing.html`)

- meta desc: `"Dose-priced routing is one proof"` → `"The map even picks
  the cleaner route"`
- og desc: `"only k≥3 aggregates ever leave your phone"` → `"nothing
  leaves your phone that isn't already a group count"`
- hero sub: same k≥3 clause → `"the only thing that ever leaves is a
  count of three or more"`
- step 01: `"report on their own cadences … converted back to µg/m³
  before anything touches them"` → `"report on their own clocks … and
  every reading lands in the same unit (µg/m³) before anything touches it"`
- step 02: `"Ordinary kriging … 95.2% of 3,550 held-out station-hours
  landed inside ±2σ"` → `"Careful fill-in between stations — kriging —
  … We hid 3,550 real station readings and asked the map to guess them —
  95.2% landed inside that band."` (kriging still named once; the test
  is now a story a reader can hold)
- step 03: `"Concentration × breathing rate × minutes, summed along the
  road"` → `"The dust in the air × how hard you're breathing × the
  minutes you're out — added up along the road"`
- `"Dose-priced routing is the proof the map can decide"` → `"Routing by
  breath is the proof the map can decide"`
- footer/links: `"k≥3 aggregates only"` → `"group counts only"` /
  `"never one person"`
- `whyLine` now carries the story's age: `"why now — … · updated N min
  ago · the evidence ↗"` off the same `story_age_s`

## 4 · app strings (`Mobile/src/i18n/strings.ts` en + hi)

The app rebuilds the note from `cause_note_fields` (`causeNote()` in
events-core) — changed in parallel, same register:

- `noteBeltUp/Down`: `", up from {a} over ~{h}h"` → `", up from {a} {h}h
  ago"`
- `noteCarryYes/NoKmh`: `"…carrying it toward Delhi"` → `"…carrying it
  our way"` (hi already says "दिल्ली की ओर" — kept)
- `noteCarryNo`: `"isn't carrying it this way right now"` → `"the wind is
  carrying it away from us"` · hi `"हवा इसे हमसे दूर ले जा रही है"`
- `noteCarryUnknown`: `"wind unknown"` → `"wind unread … our way"`
- `noteBeltQuiet/0`: `"a quiet belt"` → `"the belt is quiet"` (hi
  "बेल्ट शांत" already parallel)
- `noteStag`, `noteStagPct`: `"air barely mixing"` → `"the air is barely
  moving"` (hi "हवा ज़रा भी नहीं घूम रही" already said this)
- `noteTrend` → `noteTrendUp`/`noteTrendDown`: direction is a verb now —
  `"climbed {a} → {b} µg/m³ in ~{h}h"` / `"eased …"` · hi `"चढ़ा …" /
  "घटा …"`
- `noteTailInflow`: `"smoke inflow meeting still air"` → `"smoke coming
  in while the air sits still"` (hi "आता धुआँ ठहरी हवा में फँसा" kept —
  already natural)
- `noteBackground`, `whyNoDriver`: `"local background"` → `"the usual
  local air"` (hi "यहाँ का सामान्य" kept)
- `cityBasisModel`: dropped the "(CAMS/Open-Meteo)" name-drop —
  `"estimated from satellite + weather over Delhi, refreshed about every
  15 min"` · hi parallel

`noteStagVc` kept as the stale-surface fallback (its comment already says
superseded). Notification bodies, onboarding, receipts were already
plain-register from the earlier jargon sweep — no changes needed there.

## 5 · /community + admin

- community table headers `"pm2.5 / trip"` → `"fine dust / trip"`,
  `"co₂ per 100 m"` → `"exhaust per 100 m"`, `"main mode"` → `"mostly"`;
  the tnote explains the same terms in words now; `"est. from shared
  trips"` → `"built from shared trips"`.
- admin left technical (it's the engine room) — the σ/kriging tiles
  already carry plain glosses ("σ shows how honest each fill is").

## Em-dash note

The vendored taste-skill bans "—" in rendered copy, but the product's
established register — en + hi strings, both HTML surfaces — uses "—" as
its clause separator, and the lane brief's own model sentence uses it.
Kept the codebase convention; flagging for the owner to rule on.

## Verify

- `cd server && PYTHONPATH=core/build312:. .venv312/bin/python -m pytest
  -q tests/test_v2_why.py tests/test_v2_city.py` → 50 passed (test
  expectations updated to the new wording)
- `npx tsc --noEmit` clean; `node src/store|nav|api|offline
  /test-runner.mjs` + `npx tsx --test src/store/events.test.ts` → all
  pass (43 events tests incl. updated causeNote + hi-render test)
- `python3 scripts/check_inline_scripts.py` → OK, 4 scripts parse clean
- server booted (`uvicorn main:app :8108`), live reads:
  - `GET /v2/why` → line `"stubble smoke drifting in on the north-west
    wind"`, note `"15 fires in the Punjab–Haryana belt — a north-west
    wind at 8.8 km/h is carrying it our way"`, `story_age_s: 33`
  - `GET /v2/city` → `why.story_age_s` ships through (37 s)
  - /city, /, /community(html-accept) all 200

## Watch-outs for other lanes

- `cause_note` grammar changed; anything pattern-matching the old phrases
  ("carrying it toward Delhi", "local background") needs re-pinning —
  known consumers (city.html, landing.html, app causeNote) are updated.
- `story_age_s` is additive; older clients ignore it.
- `noteTrend` key is gone → `noteTrendUp`/`noteTrendDown` (events-core
  picks by direction).
