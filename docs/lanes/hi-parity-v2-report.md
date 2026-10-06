# hi-parity-v2 — Hindi coverage report (post-d210492)

Scope: `app-overhaul-v2` `d210492` restyled every Mobile surface; verify
Hindi parity held — static en/hi key coverage, then a live Hindi sweep on
iOS sim (iPhone 17, iOS 26.5, UDID D0B64A8A…, local backend :8000 +
Metro :8081, location pinned at India Gate 28.6129,77.2295).

## Static verdict

- `Mobile/src/i18n/strings.ts` — `en`/`hi` are a paired object table:
  `hi` is `Record<StringKey, string>`, so coverage is compiler-enforced.
  **534 keys each, zero missing, zero extra** (was 529 pre-fix; +5 this
  lane: `agoNow/agoMin/agoHr/agoDay`, `unitsKg`).
- Every `hi` value carries Devanagari except deliberate Latin
  abbreviations (`BS-III/IV/VI`, `HC ppm`, `PUC` badge) and placeholder
  templates (`{y} {f} {c}, {b}`).
- Full-tree scan of every `<Text>` rendering `t(...)`: **0 sites** lack a
  `fam(lang)`/`famMonoText`/`famSerif` font override — the Devanagari
  fallback contract holds on all new chunky components.
- No hardcoded user-facing literals in d210492's diff (it added styles,
  not copy). `t()`/`modeLabel`/`placeNameLabel`/`localizeStep` call sites
  all pass `lang`.

## Leaks found + fixed this lane (all pre-existing, surfaced by audit)

| Site | Leak | Fix |
|---|---|---|
| `App.tsx` ×2 (share bodies) | literal `cigarettes` + `kg CO₂` interpolated into the Hindi `shareTripBody` | `t("nav_cigs")` / `t("nav_kg")` + `CO₂` — share text now "…ने ~0.1 किग्रा CO₂ छोड़ा" |
| `NavChrome` banner | `step0.instruction` rendered the server's raw English sentence while the nav engine armed (engine's `nextStep` was already localized) | `localizeStep(step0, lang)` — verified "सीधे चलते रहें" |
| `notify.ts` `fmtHr` | "7am–2pm" inside the Hindi morning-brief notification | `fmtHr(h, lang)` → hi "N बजे" (HomeScreen precedent). **Code-verified only — no notification fired during the run; APK must re-verify.** |
| `Sidebar` `timeAgo` | "now / Nm / Nh / Nd" Latin suffixes on Hindi trip rows | new keys `agoNow/agoMin/agoHr/agoDay` → "अभी / Nमि / Nघं / Nदिन" — verified "4मि" live-updating |
| `NavChrome` co2 band | `x–y kg` literal under the counter | `nav_kg` → "0.1–0.2 किग्रा" — verified |
| `LedgerScreen` ×3 | trip row `≈N kg`, hero ` kg`, week line `अंदाज़न N kg छोड़ा` | `nav_kg` (row, font widened to `famMonoText`), new `unitsKg` (hero split unit keeps its dim styling), `tripsOutDetail` hi value — verified किग्रा everywhere |
| `LedgerScreen` trip route + `SearchBar` label | place names clipped to ~2 chars + "…" ("Co…", "Kasturba…") on the new compact rows | `adjustsFontSizeToFit minimumFontScale` — verified full "Indira Gandhi International Airport, India" on one line |

## Dynamic sweep — every surface, Hindi (docs/assets/hi-parity-v2/)

| Surface | Shot | Verdict |
|---|---|---|
| Home — hero (dose ring, week dots, budget) | hi-home.png, **hi-home-v2.png** (post-`d3c4c06` paper doors) | PASS — आज आपने साँस में लिया · ≈39 µg · दैनिक में से · 1घं 3मि गिने |
| Home — DoorRow tiles | hi-home.png / hi-home-v2.png | PASS — हवा का नक्शा / आज की दिल्ली / आपकी यात्राएँ, full, no clip |
| The move card (sparkline, days-ahead) | hi-move.png | PASS — +3घं ticks, ठीक/बुरा pills fit |
| DelhiToday | hi-delhitoday.png, hi-delhitoday2.png | PASS — hero, chips, species, 12h outlook, CityMoves all Hindi |
| Compare sheet (options + detail + steps) | hi-compare.png, hi-compare2.png, hi-compare-steps.png | PASS — pills, शुरू करें, Hindi maneuvers w/ road names |
| Nav chrome (banner + counters + footer) | hi-navchrome.png, hi-navchrome-v2.png | PASS — सीधे चलते रहें, किग्रा counter + band, किमी बाकी |
| Receipt | hi-receipt.png | PASS — यात्रा ख़त्म हुई, both dose rows |
| Share sheet body | hi-share.png | PASS — किग्रा, no `cigarettes` |
| Ledger | hi-ledger.png, hi-ledger-v2.png | PASS — किग्रा uniform, पूर्वाह्न clock, recency suffixes |
| Settings | hi-settings.png, hi-settings2.png | PASS — भाषा/आवाज़ rows, delete-data, version |
| Onboarding (3 pages + consent) | hi-onboarding.png–3.png | PASS — गुमनाम साझा / फ़ोन पर रखें buttons |
| Vehicle wizard + PUC (bonus) | hi-vehicle.png, hi-vehicle-puc.png | PASS — 3-व्हीलर etc. |
| Sidebar | hi-sidebar.png, hi-sidebar-empty.png | PASS — अभी/Nमि rows, stat tiles |

**Global: zero tofu boxes, zero clipped Devanagari on the chunky tiles,
zero Latin am/pm or h/m/d suffixes inside Hindi text.**

## Deliberate exemptions (kept Latin)

- Units + chemical symbols everywhere: `µg`, `µg/m³`, `m`, `km` on
  distance tags, `CO₂`, `PM2.5/PM10`, `NO₂/O₃/SO₂/CO` — register rule
  (number+unit pairs; CPCB/SAFAR boards print the same).
- `US AQI` on the DelhiToday species row — distinguishes US-EPA AQI from
  the Indian standard; coldread precedent (regulatory symbols stay).
- `CNG`, `EV`, `BS-III/IV/VI`, `PUC` — fuel/certificate acronyms Delhiites
  use in English (hi-locale lane's register).
- `ALIVE-108`/`ALive·108` wordmark — brand.
- Place/road names + t0 gazetteer category subtitles ("salon",
  "hardware store") — third-party gazetteer vocabulary, same class as
  proper nouns. A localized `kindLabel` table is a possible follow-up,
  not a leak.
- `About this map` — native MapLibre attribution control, not app copy.
- Server-authored English lines kept verbatim by design (e.g. THE MOVE's
  en `decisionLine`) — hi path already rebuilds via `moveDec_*`.

## Flagged for the search lane (not fixed — their territory)

`SearchScreen.fmtDist` hardcodes `" m"` / `" km"` while `unitsKm`
(किमी) exists and nav chrome already localizes km — a one-line call-site
fix when that lane next touches the file. Not user-visible on the
surfaces this lane owns.

## APK rebuild must re-verify

1. `notify.ts` morning-brief window — "N बजे – N बजे" in the Hindi
   notification body (code-verified only here; arm the 06:45 brief on
   the device build and read the real notification).
2. `adjustsFontSizeToFit` on the ledger trip-route + search-bar label —
   confirm the shrink behaves on Android's text engine too.
3. The whole chunky-tile set under hi on the Android glyph stack —
   Devanagari on Noto here was clean; Android falls back differently.

## Gates (post-fix, on `a5b6292` + this diff)

`npx tsc --noEmit` ✔ · `npx expo lint` ✔ · `store/test-runner.mjs` 18/18 ✔ ·
`nav/test-runner.mjs` 68/68 ✔

Note: `npm install` was needed first — node_modules had gone stale vs
package.json (missing `@expo-google-fonts/fraunces`, `ibm-plex-mono`,
`expo-device`).

Recording of the sweep: testing-agent capture
(`screencasts/hi-parity-v2/`, `hi-parity-v2-delta/` on the box). 3 known
intermittent MapLibre SIGSEGVs hit mid-run (sheet-over-live-map race,
search-crash lane's book); state survived each relaunch.
