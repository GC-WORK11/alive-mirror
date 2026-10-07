# Jargon-sweep lane — report

Lane scope: every user-facing number/word on every NON-HOME surface of
`Mobile/src/` — does a Delhi street user instantly know what it is? Copy
fixes land in `i18n/strings.ts` (en+hi pairs); structural items are
flagged here, not redesigned. HOME components belong to the home-truth
lane — one exception noted below (en-wire leak fixed in place, 4-line
change, flagged for the sibling to keep or rework).

Gates at HEAD of lane work: `npx tsc --noEmit` (clean) + `npx expo lint`
(clean) + `node src/store/test-runner.mjs` (84/84). Surfaces swept:
DelhiToday (hero, species tiles, privacy line), CompareSheet (dose line,
meta, felt multiple, bands), NavChrome, DepartGraph, LedgerScreen,
VehicleSheet, SettingsScreen, LayersSheet, SearchScreen,
OnboardingScreen, WelcomeScreen, CheckinSheet, AirMapCard, CityMoves,
FreshnessChip, notify.ts + events-core cause-note grammar, offline pill,
plan-error strings, share-text composer (App.tsx), HomeScreen
IncidentsCard (en-wire leak — see fixed row).

Concurrent-lane note: the home-truth/plan-flow siblings landed their own
"vehicles like yours" de-mocking while this lane held the same strings —
the merge took THEIR copy (`a typical Delhi ride`, `your ride`,
`on that kind of ride`, `~{x}×` felt multiple) because it satisfies law #3
with warmer phrasing. My competing `this vehicle class` variants were
dropped; everything else in this report is what's actually at HEAD.

## Fixed — copy-level (en + hi pairs, strings.ts)

| Finding | Before | After | Why |
|---|---|---|---|
| `cause_note` en passthrough — the worst leak found, caught live on sim | `air barely mixing — ventilation 595 m²/s vs ~3,000 typical · city mean 38.9 → 80.1 µg/m³ over 5.7 h` | `air barely mixing — clearing at ~20% of its usual pace · the city's average 39 → 80 µg/m³ over ~6h` | The wire's English grammar carries an engineering unit (m²/s), a stats term ("city mean") and fake-exact decimals. `DelhiToday.tsx noteLine()` and `HomeScreen.tsx IncidentsCard` (sibling's file — 4-line reorder, flagged for them to keep) now rebuild from `cause_note_fields` in BOTH languages; `cause_note` stays the no-fields fallback. Verified on sim — see shots. |
| `noteStagVc` (superseded → `noteStagPct`) | `ventilation {vc} m²/s vs ~3,000 typical` | `air barely mixing — clearing at ~{p}% of its usual pace` (events-core.ts, derived from served `stag_factor`) | m²/s is an engineering unit nobody on the street reads. The number survives as a felt fraction, the unit goes. |
| `noteTrend` + notification trend span | `city mean 44.2 → 61.5 µg/m³ over 4.5h`; live banner showed `over 5.7h` | `the city's average 44 → 62 µg/m³ over ~5h`; banner `over ~6h` (`events.ts` `Math.round(spanH)`) | "city mean" = stats jargon; bare-decimal endpoints and a decimal hour are fake-exact on an estimate. Caught live on the sim banner (`before-banner-5-7h.png`). |
| `emit_metroLong` | `…DMRC + CEA grid factors, docs/31 §3)` | `…DMRC + CEA grid factors)` | Internal doc pointer leaked into a user string. Provenance stays in the code comment. |
| `whoRef` | `WHO 45` under every species tile | `WHO limit 45` | "WHO 45" read as a unit or a name; "limit" says what the number is. Verified live on all 5 tiles. |
| `US AQI` tile | `US AQI / 167 / —` | `US AQI / 167 / 0–500 scale` (`aqiScale` + `whoTxt` slot) | The index sat beside µg/m³ tiles with no scale — the owner's AQI-vs-µg law. Verified live. |
| `citySpeciesNote` | `city average, µg/m³ — measured every 15 minutes` | `dust & gases — city average in µg/m³ · measured every 15 minutes` | With the AQI tile in the grid, "city average in µg/m³" falsely claimed every value. |
| `cityHeroAirNow` (new) | `· ~36 µg/m³` trailing the inhaled-dose hero line | `· air now ~36 µg/m³` | A bare concentration beside "µg inhaled today" read as the same number twice. The ambient reference now names itself. Verified live: `6.0× the WHO daily limit · air now ~90 µg/m³`. |
| `movesCorridorNDays` (new) | `7 streets measured over 72 hours` | `7 streets measured over the last 3 days` | "72 hours" is server-speak. Whole-day windows render as days; ragged windows keep the honest hours form. |
| `cityBasisPrivacyDays` (new) | `…crossed it in 72 hours — …` | `…crossed it in 3 days — …` | Same fix on the privacy k≥3 line. Verified live in the "why this is an estimate" block. |
| `layerCorridors` | `commute-mapped streets` | `streets travellers crossed` | "commute-mapped" is our vocab; the row now says what the layer literally is. Verified live on the layers sheet. |
| `compare_vsLightest` | `+82 vs lightest` | `+82 µg vs lightest` | Bare signed number — µg led the line but +82 renders in its own text node. (Superseded in-place by the plan-flow lane's `compare_moreVs`/`compare_feltMore`, which landed the same fix with felt framing — kept.) |
| `chooser_lessVsFastest` | `cleanest · 42% less than fastest` | `cleanest · 42% less smoke than fastest` | "42% less" didn't say less-of-what. |
| `offlinePending` | `3 saved to send` | `3 waiting to send` | Terse server-ish; the number now reads as queued mail. |
| `fieldAgeCompact`/`fieldAgeNone` (new) | `12 min` or `—` on the compact freshness chip | `12 min old` / `no reading` | "12 min" alone reads as a duration; a dash says nothing. |
| CompareSheet dose band | `34–?` when an end is missing | `34+` / `up to 60` (`bandUpTo`) | A `?` inside a range is a wire token, not words. |
| CompareSheet meta | `? km · arrive 16:30` when `distance_km` null | `arrive 16:30` (segment dropped) | Same `?` leak on the option meta line — kept through the plan-flow merge. |
| CompareSheet felt multiple | `· 2.4×` | plan-flow lane landed `~{x}× more inhaled than {m}` (`compare_feltMore`, `.0` trimmed) | Bare decimal suffix — their landed copy adds the `~` approximation mark and a plain-words clause, better than my whole-number patch. Taken. |
| `shareTripBody` | `I breathed about — of smoke` when dose missing; `~34µg` (no space) | composed clauses: `I breathed about 34 µg of smoke · my ride put out ~2.1 kg CO₂` (`shareTripLine`/`shareClauseBreathe`/`shareClausePutOut`) | "—" inside a sentence is a wire token; missing estimates now compose honestly, or fall back to `shareAppBody` when nothing is estimable. Both App.tsx call sites updated. |
| `WelcomeScreen` numeral | `45.3` under the welcome hero | `46` | Fake-exact decimal on a city mean. |
| `nav_left_m` (new) | `0.35 km · 3 min left` for sub-km distances | `350 m · 3 min left` | A decimal km at walking distance is fake-exact; under 950 m the chrome switches to metres, rounded to 10. (Code in NavChrome; surfaced when `leftIsKm(m)` false.) |
| Superseded keys (`noteStagVc`, `noteStag`, `shareTripBody`, `movesCorridorN`) | — | kept in the table, marked superseded | Live keys stay for stale-surface compat; deadcode lane owns removal. |

## Flagged — structural (needs a design call, not a copy fix)

| Finding | Where | Issue | Suggested direction |
|---|---|---|---|
| Served species values carry 1 decimal | DelhiToday tiles: `285.2`, `36.9`, `1408.7`, `167` | These are server-served city means — `285.2 µg/m³` implies measurement precision a kriged city field doesn't have. | Round whole at render (`Math.round`) — 5-line change but it touches how served measurements display everywhere; left for a design call since instrument values were deliberately shown raw. |
| US AQI tile exists at all | DelhiToday species grid | Now self-labels `0–500 scale`, but its presence beside µg tiles still invites the AQI-vs-µg confusion the owner banned. | Keep with scale gloss (current fix) or move under "why this is an estimate" — design call. |
| `why.line` en passthrough | `DelhiToday.tsx whyLine()` — `lang === "en"` keeps the wire | Currently harmless: verified live it renders driver words only (`the air is barely moving — … sitting over the city + levels still climbing`). But the en path trusts server grammar blind — if `why.py` ever puts units/decimals in the line, en shows them raw (exactly the hole the cause_note leak came through). | Watch — or rebuild en from `drivers[]` the way hi already does (1-line change: drop the `lang === "en"` short-circuit). Flagged rather than changed: the wire reads well today. |
| `why.line`/`cause_note` server grammar | `server/v2/why.py`, `server/v2/day.py` | Client now rebuilds everywhere it matters, but the wire still serves engineering grammar (`m²/s`, `5.7 h`, `38.9 → 80.1`) — any future surface that touches it raw re-leaks. | Server lane: compose `_line`/`cause_note` from the same plain-words grammar (or stop serving the composed string once fields ship). Out of mobile lane scope. |
| GRAP "stage {s}" roman numerals | notifyGrap*/noteGrap* copy + severe titles | `GRAP स्टेज II` is real Delhi vocabulary (news uses it) but a stranger reads "stage II" as video-game. | Keep — verified phrasing already carries "our estimate, not official"; revisit only if owner wants `stage 2`. |
| 24h vs 12h clock split | Ledger shows `4:42 pm`; CompareSheet arrival, NavChrome ETA, DepartGraph ticks show `16:30` | Two clock languages across surfaces — not jargon, but inconsistent. | One `clockLabel(d, lang)` helper; DepartGraph axis ticks are 48 px-capped and may need hour-only forms. Bigger than copy. |
| `receipt_lessVs` `2.3× less than by walk` | ReceiptSheet | "× less" is colloquial India-math — readable but math-flavored. | `about a third of walking` (inverse framing) — needs the inverse computed; borderline copy. |
| `fmtCig` `<0.01 cigarettes` | Ledger + hero (showCig only) | Opt-in surface; `<` is a math glyph but no honest alternative fits in 5 chars. | Kept — `0` would be a lie; flag for owner review. |
| `emit_perPax` `, per passenger (÷{o})` | emit DetailBlock | `÷2` is math notation inside the permitted-detail zone. | `shared by {o} riders` — needs a key with {o}; flagged, DetailBlock is opt-in detail. |
| `0–237.5 µg/m³` estimate band edge | DelhiToday "why this is an estimate" block | Served hi-edge carries one decimal (`237.5`) on a kriged range. | `Math.round` both edges — trivial, flagged because it's a served range not a computed one. |
| Notification `~{win} IST` | notifyWindowBody | Window labels `06:00–09:00` are already 24h (no am/pm leak — verified `labelToMin` parses `HH:MM`); `IST` is the only Latin token in a hi string. | Keep IST — Delhi usage; or `IST`→`समय` if owner wants zero Latin. |

## Verified clean (no change needed)

- `notify.ts` event router — every body built from t() keys; `fmtHr` gives `7 बजे`/`7am` — hi never carries Latin letters.
- `events-core.ts` `causeNote` — hi rebuilds from `cause_note_fields`; now BOTH languages do (fix above).
- AirMapCard legend — `redder = worse air right now`, `band_*` words, `N live stations` — all plain. Layers sheet row verified live.
- SearchScreen — `350 m`/`1.2 km` distances, `localizeKind` subtitles.
- LedgerScreen — `≈34 µg`, `≈1.1 kg`, time labels with hi daypart; `fmtCig` opt-in (see flag).
- VehicleSheet — PUC fields (`CO %`, `HC`, `BS4`) are the certificate's own vocabulary; hint keys explain each.
- SettingsScreen — every toggle label + description plain.
- OnboardingScreen — `3+` numeral + `onb_kLabel` explains the k-gate in words.
- plan-error strings (`plan_outside_*`, `plan_failed_server`) — plain.
- `placeNameLabel`/`modeLabel` wire-English guards — in place and exercised.

## Verification (iOS sim, prod-GET build, `EXPO_PUBLIC_API_URL=http://65.2.28.40`)

Screens in `docs/lanes/jargon-sweep-shots/`:

- `before-banner-5-7h.png` — live notification: `39 → 80 µg/m³ over 5.7h`.
- `before-home-card-wire.png` — incident card rendering raw wire:
  `ventilation 595 m²/s vs ~3,000 typical · city mean 38.9 → 80.1 µg/m³ over 5.7 h`.
- `after-home-card.png` — same card after the en rebuild:
  `clearing at ~20% of its usual pace · the city's average 39 → 80 µg/m³ over ~6h`.
- `after-delhi-today-hero.png` — `6.0× the WHO daily limit · air now ~90 µg/m³`,
  `WHO limit N` on every tile, rebuilt cause line.
- `after-species-grid.png` — `US AQI 167 · 0–500 scale`, species note
  `dust & gases — city average in µg/m³ · measured every 15 minutes`.
- `after-privacy-days.png` — `crossed it in 3 days` (was 72 hours).
- `after-layers.png` — `streets travellers crossed` (was commute-mapped).
