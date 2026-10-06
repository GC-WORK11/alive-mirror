# coldread-home — stranger comprehension report

Cold-read of every consumer-home surface on the release build
(iPhone 17 sim, iOS 26.5) as a non-technical Delhiite with a 2-second
parse budget, in **en** and **hi**. Copy + micro-gloss only; layout,
structure, and the journey untouched. Live API GETs only.

## Token × verdict × fix

| Surface | Token (before) | Verdict | Fix / justification |
|---|---|---|---|
| hero / DayPeek | `µg` bare | **FAIL** — the one number on the screen had an unreadable unit | `unitUg` → `µg (micrograms)` / `µg (माइक्रोग्राम)` — one inline gloss at the two first-µg surfaces (hero, DayPeek). Same precedent as admin `community.html` ("µg is micrograms"). Real unit kept — no fake unit invented. |
| hero | `0h37m accounted` | **FAIL** — "accounted" is bookkeeping; "0h37m" packed | `dayCovered` → `{h}h {m}m counted` / `{h}घं {m}मि गिने` (spaces restored). Verified: "0h 45m counted". |
| hero gauge | `of ~216µg daily` | **FAIL** — number fused to unit | `homeOfBudget` → `of ~{b} µg daily` / `~{b} µg दैनिक में से`. |
| hero week dots | `35µg this week` | **FAIL** — same fused unit | `homeWeek` → `{n} µg this week` / `इस हफ़्ते {n} µg`. |
| YOUR DAY parts | `≈ 11µg` per row | **FAIL** — fused unit in trip rows | call-site fix: `{approx(doseUgRound(p.ug))} µg`. Verified: "≈ 11 µg". |
| THE MOVE sparkline | `+3h +6h …` ticks | FAIL in **hi only** — Latin "h" inside a Devanagari card | `hourTick` → `+{n}h` / `+{n}घं`; `hourTickTilde` → `~{n}h` / `~{n}घं`. Fixed at sparkline a11y, DAYS-AHEAD partial cell, DepartGraph ticks/caption, and DelhiToday "next 12h" strip (its own literal `+${x.h}h` was leaking). en keeps "+Nh" — parseable. |
| header | `DELHI` city tag | FAIL in **hi only** — "दिल्ली की हवा" card headed by Latin "DELHI" | `cityTag` → `DELHI` / `दिल्ली`, header reads `… · {cityTag}`. Verified: "सोमवार · 19:56 · दिल्ली". |
| trip rows (saved) | `… · least-smoke rd`, `… · least-smoke alt N` | **FAIL** — engine shorthand leaking through stored labels | display side: `mode_leastSmoke` → `· least smoky way`, `mode_leastSmokeAlt` → `· least smoky option {n}` (hi already `सबसे कम धुआँ वाला रास्ता`). `modeLabel()` now matches BOTH the wire form and the stored display form, so trips saved under either wording re-localize — verified live: "Car (AC) · least smoky way · 22m" and hi "कार (AC) · सबसे कम धुआँ वाला रास्ता · 27m". No migration needed. |
| FreshnessChip a11y | `live + open-meteo/cams`, `unavailable` | **FAIL** — raw wire tokens read aloud to screen readers | `sourceLabel()` maps tokens → `srcStations`/`srcModel`/`srcNone` (`live stations` / `satellite estimate` / `no source` · `लाइव स्टेशन` / `सैटेलाइट अंदाज़ा` / `कोई स्रोत नहीं`). Serving tokens (`live`/`snapshot`/`none`) filtered — they're *how* it was served, already covered by the age count — and duplicates deduped. Verified: "2 min — satellite estimate" / "2 मिनट — सैटेलाइट अंदाज़ा". |
| DAYS AHEAD | `faded days sit outside live reads — raw CAMS skill only` | **FAIL** — "CAMS skill" is pipeline jargon | `dayOutlookLoNote` → `faded days are past live readings — satellite estimate only` / `फीके दिन लाइव रीडिंग की पहुँच से बाहर — सिर्फ़ सैटेलाइट अंदाज़ा`. Verified on screen both locales. |
| compare sheet | `least-smoke roads first · adding metro, bus…` | **FAIL** — "least-smoke" compound | `compare_refining` → `least smoky roads first · adding metro, bus and more…` (hi already clean). |
| compare sheet | `least-smoke picks unavailable — showing what's live` | **FAIL** — same | `degradedEngine` → `least smoky picks unavailable right now — showing what's live` / `सबसे कम धुएँ वाले रास्ते अभी उपलब्ध नहीं — जो लाइव है वही दिखा रहे हैं`. |
| detail block | `the route leaves the field — only the {pct}% inside is counted, never spread thin` | **FAIL** — "the field" is engineer-speak for the smoke map | `howWe_coverage` → `the route leaves the smoke map — only the {pct}% inside it is counted, never stretched` / `रास्ता धुएँ-नक्शे से बाहर जाता है — सिर्फ़ ढके हुए {pct}% की गिनती हुई, अनुमान नहीं लगाया गया`. |
| dose-note fallbacks | `engine down` / `engine error` / `field down` | **FAIL** — "engine"/"field" internals named to users | `doseNote_engineDown` → `smoke estimate unavailable`, `doseNote_engineError` → `smoke estimate error`, `doseNote_fieldDown` → `air map unavailable` (hi parallels). |
| DelhiToday hero | `µg` bare under "आज की दिल्ली" | **FAIL** | `cityHeroUnitUg` → `µg of fine smoke (PM2.5) inhaled today` / `आज साँस में लिया बारीक धुआँ (PM2.5) — µg` — PM2.5 itself glossed as "fine smoke". |
| DelhiToday | `city species note`, `typical line`, `forecast note` raw values | **FAIL** in hi (English leaks) + awkward en | `citySpeciesNote` → `city average, µg/m³ — measured every 15 minutes` / `शहर का औसत, µg/m³ — हर 15 मिनट ताज़ा`; `cityTypicalLine` → `running {pct}% of the 10-year average of {med} µg/m³ for this hour` / `इस समय के 10-वर्ष औसत {med} µg/m³ की तुलना में {pct}%`; `cityForecastNote` → `satellite forecast matched to live readings, µg/m³` / `सैटेलाइट पूर्वानुमान, लाइव रीडिंग से जोड़ा, µg/m³`. Verified on screen. |
| DAY-PEEK partial cells | `first ~8h only` (en ok) / `पहले ~8घं` (hi) | PASS after fix | `dayOutlookPartial`/`dayOutlookTodayPartial`/`dayOutlookVerdictPartial` — hi ticks now use `घं` via hourTick. |
| move-card window labels | `7am/7pm` via `fmtHr` | FAIL in **hi only** — Latin "am/pm" when server labels are absent | `fmtHr(h, lang)` — hi renders `7 बजे`, en keeps `7pm`. Server-labeled path (the common one) was already localized. |
| receipt / ledger / share | `est.` prefix everywhere | **FAIL** — abbreviation-jargon; honesty is kept by "about"/"estimated" not by the token | en `est.` → `about` / `estimated —` (`tripsDoseBand`, `tripsDoseDetail`, `tripsOutDetail`, `receipt_estLike`, `receipt_estShort`, `receipt_doseUgBand`, `howWe_in`, `shareTripBody`). hi already native (`अंदाज़न/अनुमान`) — parity kept. DepartGraph caption now reads "about +6h · 16:30 ≈ 40 µg". |
| THE MOVE decision line | `cleanest window ~14:30-00:30 IST (avg 38 µg/m³ vs day 101)` | KEEP | server-authored en line served verbatim (`decisionLine` returns `d.line` for en). "IST" is how Delhiites read time; "avg" is standard. The client `moveDec_*` en templates mirror the server's phrasing and only run on the hi rebuild path (hi card verified: "सबसे साफ़ घड़ी ~14:30-00:30 (औसत 38 बनाम दिन 101 µg/m³)" — no IST). Server copy is out of this lane's scope. |
| DelhiToday species row | `PM10 · NO₂ · O₃ · CO · SO₂ · US AQI` | KEEP | regulatory symbols exactly as printed on every public AQI board in India (SAFAR/CPCB). Renaming invents non-standard words — worse for comprehension. Caption "शहर का औसत, µg/m³" now explains what they are. |
| DelhiToday | `11–25 g CO2e/pkm — DMRC + CEA grid EF, docs/31 §3` | KEEP | deliberately technical citation line in the emissions explainer (`emit_metroLong`) — the honesty footnote where the basis lives. By design: "jargon lives in details only". |
| `µg/m³` everywhere | concentration unit | KEEP | glossed in context (`citySpeciesNote`, `cityForecastNote` say "city average"/"satellite forecast"); CPCB's own boards print µg/m³ — it's the citizen-facing ambient unit. The *inhaled* µg got the microgram gloss; ambient µg/m³ reads as the same µg per cubic metre of air. |
| `mode_approx` | ` (approx.)` | KEEP | standard abbreviation on trip labels; hi uses ` (अनुमानित)`. |
| DAILY BUDGET | `general / sensitive / child` | KEEP | profile chips are self-labels; the caption under them already does the explaining — "a ceiling you set — not a medical line". |
| HOW YOU FELT | `breath · eyes · energy`, `meh` | KEEP | already plain; "meh" is colloquial Delhi English. |
| nav chrome / receipt | `{n}× less than by auto`, `incl. {lo}–{hi} g of fine dust (PM2.5)`, turn cues | KEEP | plain words already; PM2.5 glossed as "fine dust"; `incl.` and "×" are receipt conventions. |

## Notes

- **Second pass verified on device**: en hero/peek/day/budget/outlook all
  re-rendered with the new copy; hi run end-to-end (sidebar, map, home,
  DelhiToday) shows zero English leaks — दिल्ली header, +Nघं ticks,
  सैटेलाइट अंदाज़ा provenance, µg (माइक्रोग्राम) gloss.
- **Surfaces audited by strings, not live**: compare sheet, receipt,
  nav chrome (a live trip can't be triggered without touching the
  journey). Their copy was read in `strings.ts` + the components'
  render sites — every user-facing token in those paths went through
  the same 2s test.
- **Honesty kept**: no fake units, no rounded-away uncertainty — "≈",
  "about", lo–hi bands and confidence words all survive; only the
  unparseable wrapping changed.
- Gates after all edits: `npx tsc --noEmit` ✓, `npx expo lint` ✓,
  `node src/store/test-runner.mjs` 18/0 ✓, `node src/nav/test-runner.mjs` 68/0 ✓.
