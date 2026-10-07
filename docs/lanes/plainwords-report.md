# plainwords — the user-visible copy pass

Lane ask: inventory every user-visible string, answer the band-language
question, rewrite what a judge's grandmother can't parse into felt Delhi
words, audit the jargon glosses, verify the notification strings, keep
numbers/colors/honesty exact. Report = this file. Pushed to `base/v2`.

## The copy surface (inventory)

Consumer copy lives in five places:

| surface | what it is |
|---|---|
| `Mobile/src/i18n/strings.ts` | **the** app copy table — `en` + `hi` with parity compiler-enforced. ~560 keys: nav, onboarding, consent, home/dosimeter, day/week, compare sheet, plan, receipts, moves, notifications, settings, welcome gate, band words, `kind_*` gazetteer labels. |
| `Mobile/src/components/shell/CompareSheet.tsx` | wire-verbatim maps (`REASON_KEY`, `NE_KEY`, `EMLBL_KEY`, `DOSE_NOTE_KEY`, `SLOWER_RE`) — the server ships fixed English templates; the app maps each to an i18n key, so the **i18n value is what en and hi both render**, and the wire string is the lookup key. |
| `Mobile/src/screens/HomeScreen.tsx` | `decisionLine()` rebuilds the served `decisions[].line` from structured fields for "outdoor exercise"/"today" in both languages; the wire line is only the fallback for unrecognized labels/shapes. |
| `server/v2/*.py` | wire English that can surface to en as-is: `day.py::_decisions` (fallback path only), `outlook.py` verdict, `plan.py` reason_lines + dose notes (mapped), `why.py::_line`/`_LINE_BITS`. |
| `server/{landing,city,community,admin}.html` | the web faces. landing is the showcase page; city/community are the public pages; admin is the operator console. |

## The band language — checked, kept

Pollution bands are shown to users as the CPCB words:
**good / satisfactory / moderate / poor / very poor / severe**
(`felt_*` and `band_*` keys, `feltKeyForBand`). This was a deliberate
design-v4 decision (commit 8c7ad97, `android-overhaul-report.md`):
Delhi residents already know these words from news and AQI boards —
"क्या आज ख़राब है?" is already the Delhi phrasing. Earlier felt words
(easy/fine/fair/heavy/rough/harsh) were *removed* for that reason, so
this lane does not reintroduce them. Honesty law holds: poor stays poor.

What the app adds so "is today bad?" doesn't need PM2.5 knowledge:
the hero shows the band word + band colour + the number, the reference
line translates it ("WHO की दैनिक सीमा का {x}×" / `refWhoOver`), and the
cigarette parity + dose strings teach the scale ("1 cigarette ≈ 316 µg
of PM2.5 breathed in" in `settingsHowNumbersBody`).

## Jargon audit — what's glossed where

Already glossed before this lane (verified in place, not added):
`PM2.5` → "fine smoke (PM2.5)" at first sight (`cityHeroUnitUg`,
`cityBasisPm25*`); `µg` → "µg (micrograms)" (`unitUg`); cigarette parity
("≈ 316 µg") in the numbers explainer; AQI → "the government air score
(AQI)" on city.html; µg → "micrograms" on community.html; PUC →
"pollution certificate"; GRAP → always carries the honesty rider "our
read, not the official call" (now phrased "our estimate").

`kind_*` gazetteer keys are the corpus's own place-type vocabulary —
left as the canonical strings per the brief (key structure untouched).

## String-by-string changes

### App (`Mobile/src/i18n/strings.ts`) — en values

| key | old | new | why |
|---|---|---|---|
| `wel_provAmbient` | live · the field here, this hour | live · the air here, this hour | "field" is geostat jargon; "air" is what it is |
| `wel_provCity` | live · field mean over the ncr lattice | live · the ncr-wide average | "field mean over the lattice" is pipeline-speak; the number IS the NCR-wide average |
| `plan_outside_body` | …this trip leaves the field, so its dose can't be priced honestly. | …this trip leaves the air map, so its smoke can't be counted honestly. | "field" + "priced" both out; the honesty ("can't be counted") kept |
| `plan_coverage_note` | smoke counted for the NCR span only | smoke counted only for the Delhi NCR part | "span" was vague; names what is/isn't counted |
| `compare_safest` | safest route | least smoky | "safest" overclaimed; the chip marks the least-dose option — same word the app already uses ("least smoky way") |
| `mode_approx` | (approx.) | (roughly) | abbreviation out |
| `howWe_conf` | confidence: {c} | how sure we are: {c} | the stat-word → the question a person asks |
| `ne_road` | non-exhaust (resuspended dust + brakes/tyres), reported separately — ~86% of Delhi traffic PM10 is non-exhaust (Sahu et al. 2020, docs/26); never folded into tailpipe numbers | road dust, brake and tyre wear — reports call this 'non-exhaust'; counted separately, never added to exhaust (about 86% of Delhi's traffic dust is this kind — Sahu et al. 2020) | names the thing first, then gives the report's own word; repo-path citation dropped, author-year kept |
| `ne_rail` | rail — no road resuspension | rail — no road dust kicked up | "resuspension" → what it means |
| `ne_zero` | zero — non-motorized mode | zero — no engine | mode-category jargon → the felt fact |
| `emit_metroShort` | metro per passenger-km (incl. electricity) | metro per km per passenger (incl. electricity) | unit spelled in words |
| `emit_metroLong` | metro per passenger-km, incl. electricity (11–25 g CO2e/pkm — DMRC + CEA grid EF, docs/31 §3) | metro per km per passenger, incl. electricity (11–25 g CO2e per passenger-km — DMRC + CEA grid factors, docs/31 §3) | `pkm`/`EF` shorthand expanded; citation kept — this is a provenance note, precision stays |
| `emit_basisPerVkm` | per vehicle-km | per km driven | |
| `emit_basisPerPaxKm` | per passenger-km | per km per passenger | |
| `emit_innerFleet` | {f} {c}, Delhi fleet mix — {b} | {f} {c}, Delhi average — {b} | "fleet mix" → what it measures |
| `emit_innerEv` | electric {c}, incl. grid electricity | electric {c}, includes grid electricity | abbreviation out |
| `receipt_pmBand` | incl. {lo}–{hi} g of fine dust (PM2.5) | includes {lo}–{hi} g of fine dust (PM2.5) | |
| `receipt_pmBandOne` | incl. {x} g … | includes {x} g … | |
| `receipt_pmBandTiny` | incl. <0.01 g … | includes <0.01 g … | |
| `weekDayThin` | not counted — no covered hours on the phone that day | not counted — no hours logged that day | "covered hours" is sampling jargon |
| `daySparseSamples` | {n} of {m} samples | {n} of {m} readings | "samples" → the app's own word ("air reading") |
| `dayMorningNoCell` | outside the air map — no hour curve here | outside the air map — no hour-by-hour read here | "curve" is chart-speak |
| `moveDec_short` | only ~{n}h of today left on the card — {b} throughout | only ~{n}h of today left — {b} throughout | "on the card" is component-speak (wire fallback keeps the old text — pinned by `test_short_day_honest`) |
| `movesSuppressed` | +{n} more trips under the {k}-trip rule | +{n} more trips stay private — fewer than {k} travellers crossed them | the privacy rule said as the rule itself, not its name |
| `movesCorridorN` | {n} {streetNoun} measured in {h} h | {n} {streetNoun} measured over {h} hours | bare `h` unit → word |
| `ledgerEstNote` | estimates, honestly ranged | estimates — honest ranges, never fake-exact | same claim in the app's own phrase |
| `cityTypicalLine` | running {pct}% of the 10-year average of {med} µg/m³ for this hour | {pct}% of this hour's 10-year average ({med} µg/m³) | grammar untangled; numbers identical |
| `dayOutlookVerdict` | {d} looks {w} — avg ~{c} vs ~{g} µg/m³ across the forecast | {d} looks {w} — average ~{c} vs ~{g} µg/m³ across the forecast | "avg" → word |
| `notifyStagBody` | barely mixing — {f}× stiller than usual; expect the day's smoke to linger | {f}× stiller than usual — the day's smoke will linger | "barely mixing" (met-speak) out; the felt figure leads |
| `notifySevereBody` | today's air maps to GRAP stage {s} (our read, not the official call) — a mask outside is worth it | today's air reads like GRAP stage {s} — our estimate, not the official call; a mask outside is worth it | "maps to" is schema-speak; "reads like" is the felt claim. GRAP itself kept — the Delhi-known word, with its honesty rider |
| `notifyGrapUpBody` | our read now maps to stage {s} (aqi ~{a}) — computed from today's air, not the official call | today's air reads like stage {s} (AQI ~{a}) — our estimate, not the official call | same fix; `aqi` → AQI (the casing used elsewhere) |
| `notifyGrapDownBody` | our read now maps to stage {s} (aqi ~{a}) — still our computed read | today's air reads like stage {s} (AQI ~{a}) — still our estimate | |
| `notifyGrapClearBody` | our read no longer maps to a stage (aqi ~{a}) — still our computed read | today's air no longer reads like a stage (AQI ~{a}) — still our estimate | |
| `notifyOutlookHeavyBody` | avg ~{b} µg/m³ vs ~{a} today{cause} | average ~{b} µg/m³ vs ~{a} today{cause} | |
| `notifyOutlookLightBody` | avg ~{b} µg/m³ vs ~{a} today{win} | average ~{b} µg/m³ vs ~{a} today{win} | |

### Same keys, `hi` values

20 keys updated in Devanagari for parity (`tsc` enforces the key set):
`ne_road`, `ne_zero` (गैर-मोटराइज़्ड मोड → इंजन नहीं), `mode_approx`
(अनुमानित → अंदाज़न), `howWe_conf` (भरोसा → हमें कितना भरोसा),
`movesSuppressed` (privacy spelled out: "उन सड़कों से {k} से कम यात्री गुज़रे"),
`movesCorridorN` (घंटे → घंटों में), `notifyStagBody`, `notifySevereBody`,
`notifyGrapUp/Down/ClearBody` (मैप होती है → जैसी है; `aqi` → AQI),
`ledgerEstNote`, `compare_safest` (सबसे सुरक्षित रास्ता → सबसे कम धुआँ),
`plan_outside_body` (फ़ील्ड → हवा-नक्शे), `daySparseSamples` (नमूने → रीडिंग),
`dayMorningNoCell` (कर्व → घंटे-दर-घंटे रीडिंग), `moveDec_short` (कार्ड पर
dropped), `emit_innerFleet` (फ़्लीट मिक्स → दिल्ली औसत),
`emit_basisPerVkm/PerPaxKm` (वाहन-किमी/यात्री-किमी → गाड़ी के प्रति किमी /
यात्री के प्रति किमी), `emit_metroShort/Long`, `wel_provCity`
(एनसीआर ग्रिड पर हवा का माध्य → पूरे एनसीआर का औसत).

### Wire English (`server/v2/`) — en display text on fallback paths

| file:line | old | new |
|---|---|---|
| `day.py:310` | %s window %s IST (avg %.0f µg/m³ vs day %.0f) | %s window %s IST (average %.0f µg/m³, %.0f across the day) |
| `day.py:323` | (~%.0f µg/m³ avg) | (~%.0f µg/m³ average) |
| `day.py:350` | no sustained window today — lightest reads %.0f µg/m³, heaviest %.0f | no steady window today — lightest reads %.0f µg/m³, heaviest %.0f |
| `outlook.py:157` | %s looks %s — avg ~%.0f vs ~%.0f µg/m³ across the %d-day forecast | %s looks %s — average ~%.0f vs ~%.0f µg/m³ across the %d-day forecast |

(These are the served fallback strings; the app rebuilds "outdoor
exercise"/"today" lines from structured fields via `moveDec_*` in both
languages, so wire/fallback and rendered text now say the same thing.)

### Web (`server/landing.html`)

The page keeps its coined register ("the field knows what Delhi
breathed" — lead, meta, boot-strip) — that's the showcase voice, not
jargon. Changed the *operational* uses where "field" stood in for the
data product:

| old | new |
|---|---|
| the field, live / the field, this hour / the field (labels, loading, empty states — 12 spots) | the air map / the map — e.g. `pm2.5 — the air map, this hour`, `reading the live air map…`, `map stale`, `map unreachable` |
| live · field mean over the ncr lattice (×2: hero basis + boot line) | live · the ncr-wide average |
| 22 µg/m³-day ≈ 1 cig | a day at 22 µg/m³ ≈ 1 cigarette |
| worst ≈N cig | worst ≈N cigarettes |
| now — live field +N% vs the typical hour | now — live air +N% vs the typical hour |
| hi/med/lo conf — dense sample coverage / moderate coverage / far from samples | high/medium/low confidence — many/some/no stations near here |
| lo conf (route line + ladder flag, ×2) | low confidence |
| N measured · N interpolated · N thin | N measured · N estimated between stations · N thin |
| cell fade = distance to nearest sample | cell fade = distance to the nearest station |
| typical = the archive's median for this hour | typical = the archive's middle value for this hour |
| median N µg/m³ (status strip) | usual N µg/m³ |
| the engine prices the corridor / pricing the corridor / too close to price a corridor / same corridor | …prices the route / pricing the route / …price a route / same route |
| outside the priced field / inside the field window / NCR field window | outside the map's reach / inside the map / the NCR map |
| no field data / outside the measured field / computing +12h field | no map data / outside the measured map / computing the +12h read |
| centroid read — N covered cells / mean of N covered cells | centre-point read — N covered cells / average of N covered cells |
| N driver(s) observed (why-tonight) | N cause(s) seen |
| the field rebuilds roughly every 15; AQI sub-indices are inverted back to µg/m³ | the map rebuilds roughly every 15; station readings are converted back to µg/m³ |
| Ordinary kriging draws the field — a surface, not a guess | Ordinary kriging — careful fill-in between stations — draws the map, a surface, not a guess | (method name kept, inline felt gloss added — the "krige" rule) |
| Concentration × ventilation × minutes | Concentration × breathing rate × minutes |
| edges priced / million edges | road segments priced / million road segments |
| joins a corridor only where three or more phones cross it | joins a shared street only where three or more phones cross it |

## Count

- **35 en keys** + **20 hi keys** in `strings.ts` (55 string values)
- **4 wire lines** in `server/v2/` (day.py ×3, outlook.py ×1)
- **~28 copy spots** in `landing.html`
- 3 comment-only touch-ups in `CompareSheet.tsx`/`types.ts` keeping the
  quoted labels accurate

## Notifications — verified consistent

All `notify_*` strings walked: fires ("{a} → {b} fires in the burn belt —
wind carrying it this way"), band ("the air just turned {word}" — felt
word via `feltKeyForBand`), window ("easiest hours ahead"), stagnation
("{f}× stiller than usual"), severe, trend, GRAP, outlook, reflect.
Felt throughout; the only slips were the "maps to GRAP stage" phrasing
and `avg`/`aqi` casing — fixed above. Baselines stay honest (never
claims an official call).

## Deliberately left

- **CPCB band names** (good…severe) — the Delhi-known felt words, per the
  recorded design-v4 decision; reverting would undo that lane.
- **`kind_*` gazetteer labels** — the corpus's own vocabulary; canonical
  strings kept, key structure untouched.
- **admin.html** — operator console, stays technical per the brief.
- **`SPECS` titles** on landing (`pm2.5`, `us aqi`, `pm10`) — layer names
  shown beside their glosses; renaming "us aqi" would lose which
  standard it is.
- **`emit_*` citation parentheticals** (DMRC + CEA, Sahu et al., docs/§)
  — provenance notes where precision matters; shorthand expanded but
  citations kept.
- **Served `reason_*`/`doseNote_*` wire English** — display text comes
  from the i18n values; changing the wire would break the verbatim maps
  that feed hi.
- **`day.py` "…left on the card"** — pinned by `test_short_day_honest`;
  it's a rebuild-fallback users don't normally see (i18n covers it).
- **k≥3 / devices** in privacy copy — the honest mechanism word (k is
  explained on the same surface: "a street appears only after this many
  different devices cross it").
- **"the field"** in landing's poetic register (lead line, meta, boot
  strip) — coined voice, not jargon; only its operational uses changed.
- **"the dosimeter"** — the product's own name.
- **`degraded` arm names, `/v2/districts`, build sha** — wire tokens
  shown raw on the showcase page; they name real things.
- **city.html, community.html** — audited; already felt with inline
  glosses (AQI → "the government air score", pm2.5 → "fine dust", µg →
  micrograms, cigarette → 316 µg). No changes needed.
- **server `why.py`** — `_line`/`_LINE_BITS` already felt ("stubble
  smoke drifting in on the {dir} wind"); the technical `evidence[]`
  strings surface only behind "the evidence ↗".

## Verification

- `npx tsc --noEmit` — clean (en/hi parity holds).
- `npx expo lint` — clean.
- `node src/{store,nav,api,offline}/test-runner.mjs` — all pass.
- `pytest tests/test_v2_day.py tests/test_v2_outlook.py` — 31/31 pass.
- Full server suite — 1137 passed; 3 unrelated env failures
  (`alive_core` native module not built on this box;
  `test_search_latency_compound_path` p95 timing flake).
