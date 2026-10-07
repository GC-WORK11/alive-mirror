# Component audit — every defect found driving the app

**Lane:** component-audit (find-everything, no fixes)
**Rig:** iPhone 17 sim (iOS 26.5, UDID EDD9B083-…), fresh Release install of `base/v2` @ HEAD, `EXPO_PUBLIC_API_URL=http://65.2.28.40` baked into the bundle (verified in `main.jsbundle`). Location pinned at 28.6139,77.2090 (Connaught Place). Driven with real taps/swipes for ~60 min.
**Evidence:** `docs/lanes/component-audit-shots/` (26 shots, device + framed captures).

## Verified honest (checked, not guessed)

| Claim | How verified |
|---|---|
| Hero ambient ~62–63 µg/m³ moderate, "4.2× WHO daily limit" | Live `/aqi` field; 63/15 = 4.2 ✓ |
| DelhiToday "1291 µg inhaled today · 6.0× WHO · ~90 µg/m³" | City-mean dose; 90/15 = 6.0 ✓ |
| US AQI 173 | Consistent with ~90 µg/m³ PM2.5 (unhealthy band) ✓ |
| "12% below the 10-year average (102 µg/m³)" | 90 vs 102 ≈ 12% ✓ |
| Budget pill recompute 216→72→"33% of your daily budget" on 24 µg | 24/72 = 33% ✓ live |
| Days-ahead 62/84/162/132/139 | `/v2/day` outlook; each cell expands to real per-day data ✓ |
| Incidents line ("16 fires… ventilation 595 m²/s… city mean 38.9→80.1 over 5.7h") | `/v2/why` `evaluated` fields verbatim, labeled "measured, not reported" ✓ |
| Plan flow: 12 options, dose 2.4 (car AC) → 77.2 (walk alt) | `POST /v2/plan` replayed — same spread, alt routes drawn on map ✓ |
| Trip receipt dose ≈0.4 µg, "0 km / 0 kg" | Sim never moved; zero is the measured truth, labeled correctly ✓ |
| "kept on this phone only" on receipt | `engine.ts:326` — 0-point trajectory → nothing donated; honest ✓ |
| Notification engine | `events.json` dedupe: `stagnation` + `trend_up` fired once each, per-day dedupe works; banners arrive ~5–15 s after launch ✓ |
| Fires (90) / blackspots (104) / community corridors endpoints | Real GeoJSON from prod ✓ (see map findings — they return data but render nothing) |
| Hindi switch | Full UI re-strings incl. incidents card; no Latin leakage spotted ✓ |
| Feedback (rate) | 5★ + note → `POST /v2/feedback` → "thanks — that helps" ✓ |
| Privacy copy | "300 m end-trim / ~11 m rounding / 3-device threshold" matches `engine.ts:104-110` + DelhiToday footnote ✓ |
| `welcome_seen_v1` cinematic | Replays on flag delete; labels "live · the ncr-wide average" (89.9 vs local 62 — correctly scoped, not the same number) ✓ |

## Defects

Severity: **blocks-demo** (a demo judge hits it) · **ugly** (visible defect) · **nit** (polish).
Owner lane tag in the last column.

| # | Component | What it does now | Defect (class) | Severity | Pointer | Shot | Owner |
|---|---|---|---|---|---|---|---|
| 1 | Home — fixed "Where to?" pill | Ink pill pinned under the greeting; content scrolls underneath it | **jank**: AX-verified blocked taps — an outlook day cell press was refused "centre is covered by button 'go somewhere'"; ~52 px of content slides under an opaque fixed bar and stays untappable until scrolled clear. `contentContainerStyle` pads only 12 px against a ~62 px overlay | ugly | `HomeScreen.tsx:1356–1360` | `home-pinned-pill-content-under.png` | jank |
| 2 | Onboarding page 1 | 3-page consent flow; "skip" = sharing ON | **jank**: the skip-disclosure line ("Skipping counts as sharing on…") renders half-clipped at the bottom edge on iPhone 17 — legally-important consent text is cropped on first run | ugly | `OnboardingScreen.tsx:381–390` | `onboarding-banner-over-p1.png` | new-lane-needed (onboarding) |
| 3 | Notifications | Local banners fire inside the 60 s `/aqi` poll, first at app mount | **jank**: a trend banner ("the city's air is climbing 35 → 70 µg/m³") slides over onboarding page 1 during the very first run — interrupts consent UX before the user has seen anything | ugly | `App.tsx` `aqiPoll` at mount; `store/events.ts` | `onboarding-banner-over-p1.png` | new-lane-needed (onboarding) |
| 4 | Map — layers | fires / crash spots / commute-mapped streets toggles, lazy-fetch `/fires` `/blackspots` `/community` | **dead-looking**: all three ON → zero visible marks over central Delhi. Fires are real but far NW (off-viewport, fine); but 22 blackspots exist in this viewport (`blackspotsDot` minzoom 11.5, 3–6 px dots) and a corridor sits dead-center at 77.22,28.63 (`corridorGlow` opacity 0.12 — designed "faint veil" reads as invisible). No legend, no "loading", no count — toggles feel broken | ugly | `HazardLayers.tsx:16–82`, `CorridorLayer.tsx:31–53` | `map-all-layers-on-empty.png` | airmap |
| 5 | Map — idle surface | basemap + freshness chip + DayPeek | **lie-adjacent**: a screen reached via a door literally labeled "Air map" (`homeLinkMap`, strings.ts:714) renders zero air data by default — no field tint, no contours. Air only appears once a route is planned | ugly | `App.tsx:201–204` (only hazard/route layers exist) | `map-all-layers-on-empty.png` | airmap |
| 6 | Map — OSM attribution | MapLibre ⓘ "About this map" button | **dead**: positioned `bottom: insets.bottom+72` — exactly inside the DayPeek card (`peekWrap` same offset). AX press refused: "centre is covered by label 'your day so far'". OSM attribution unreachable/invisible — license nit too | ugly | `App.tsx:661–662` vs `880` | `map-all-layers-on-empty.png` | airmap |
| 7 | Map — freshness chip | "N min" pill under the search bar | **jargon**: bare "13 min" sits where a route ETA would sit; it is field-data age (AX name resolves "… live stations + satellite estimate"). Next to an active route it reads as travel time | nit | `FreshnessChip.tsx:139` (compact label) | `map-all-layers-on-empty.png` | airmap |
| 8 | Map — DayPeek card | "your day so far · now ~62 · ≈18 µg" card | **dead-ish**: looks tappable, but press only routes back to Home — no expand, no day detail on the map | nit | `HomeScreen.tsx:890–961`, `App.tsx:881` | — | hometruth |
| 9 | Home — "days ahead" cell | tap expands a day | **jargon**: expanded header renders raw ISO — "friday · 2026-10-09" (`{open.date_ist}` verbatim) on a consumer surface | nit | `HomeScreen.tsx:703` | `outlook-iso-date.png` | hometruth |
| 10 | Home — "the move" | decision card from `/v2/day` | **jargon**: "only ~2h of today left — moderate throughout" at 10:56 AM — the unexplained window makes it read like a lie (server picks `moveDec_short`); sparse state also renders near-empty card (two ticks + clipped sparkline) | ugly | `strings.ts:628` (`moveDec_short`), `MoveCard` `:433+` | `home-sparse-hero.png` | hometruth |
| 11 | Home — pull-to-refresh | down-swipe at top triggers refresh | **jank**: coexists with scroll — a downward pull mid-scroll fires refresh (freshness jumped 4→10→11 min), fights gesture expectations; no complaint if intentional, but it surprised mid-walk | nit | `HomeScreen.tsx` scrollview | — | jank |
| 12 | Home — header clock | "Delhi · Wednesday 11:16" under greeting | **nit**: updates on a 30 s interval — can sit a minute behind the status bar (observed 11:16 vs 11:17) | nit | `HomeScreen.tsx:971–973` | `home-pinned-pill-content-under.png` | hometruth |
| 13 | Home — week strip | 7 day cells, tap expands | **lie (a11y)**: uncounted days expose AX name "T 0" — claims a zero the code itself refuses to show (`WeekStrip.tsx:14` "never a claimed zero", `:113` `${letter} ${doseUgRound(w.ug)}`). Expand correctly says "not counted — no hours logged" | nit | `WeekStrip.tsx:113` | `weekstrip-blank-days.png` | hometruth |
| 14 | Home — incidents card | "in Delhi's air right now" feed | ✓ honest, but card + outlook card both print separate "air reading: N min old" captions — duplicated freshness lines on one screen | nit | `HomeScreen.tsx` (both cards) | `home-pinned-pill-content-under.png` | hometruth |
| 15 | DelhiToday — species table | PM10/NO₂/O₃/CO/SO₂ vs WHO rows | **jargon**: values colored by severity but WHO cells read "WHO 45" with no unit; multiples not shown (295.2 vs 45 = 6.6× is user-math); "+" used mid-sentence in prose ("…over the city + levels still climbing") | nit | `DelhiToday.tsx:447–505` | `delhitoday-hero-species.png` | delhitoday |
| 16 | DelhiToday vs Home hero | 90 µg/m³ city mean vs 62 local field | **jargon**: two different "the air" numbers across screens; reconciliation only in DelhiToday's fine print ("~90 µg/m³") — a casual user sees the app contradicting itself | nit | `DelhiToday.tsx` hero vs `HomeScreen.tsx` hero | `delhitoday-hero-species.png` | delhitoday |
| 17 | Search — input | typing in "Where to?" | **jank**: fast typing dropped characters — "india gate" rendered "indiate" and returned a junk POI ("INDIATECH247 computer shop"); second clean attempt returned full ranked results (11 rows incl. monument) | ugly | `SearchScreen.tsx` field/debounce | `search-chars-dropped-indiate.png`, `search-india-gate-results.png` | search |
| 18 | Search — recents | recent row label | **nit**: verbose official name truncates mid-word — "India Gate Entry Kashturba Gand…" | nit | `search/recents` row | `search-india-gate-results.png` | search |
| 19 | Search — bottom bar | "Your location" / "Choose on map" | **dead-ish**: "Your location" as a destination pick is a no-op (you are already there) — no toast, no state change, silent ignore | nit | `SearchScreen.tsx` action bar | — | search |
| 20 | Choose-on-map | hint "tap the map to drop a pin there" → pin → reverse geocode | ✓ works ("Institute of Urban Designers — India"), but a 0.05 km pin runs the FULL compare + depart graph as if a trip matters — no "too close to count" guard | nit | `App.tsx` mapPick flow | `pindrop-50m-compare.png` | planflow |
| 21 | Compare — band text | emissions band under each option | **slop**: `0–0 kg CO2 · 0–0 g PM2.5` — a zero-to-zero "range" for non-motorized modes; row dose can also show "≈0 µg (0–0)". `bandTxt` prints `{lo}–{hi}` with no equal/collapse rule (ReceiptSheet has the collapse rule; this one doesn't) | ugly | `CompareSheet.tsx:143–146` | `compare-zero-zero-bands.png` | planflow |
| 22 | Compare — route labels | "least-smoke alt N" wire suffix on rows | **lie/jargon**: alternates labeled "least-smoke" can be smokier than the primary — bicycle base 26.0 vs "least-smoke alt 1" 34.4 / "alt 2" 29.9 (prod payload). The wire name reaches the UI and misleads; truncation compounds it ("Bus CGOCOM…") | ugly | `api/plan.ts` labels; `CompareSheet.tsx:366–373` | `compare-bus-cgocom.png` | planflow |
| 23 | Compare — depart graph | "leave tomorrow 02:00 → breathe ~25% less" + 8 bars | ✓ real values; **nit**: for a 50 m trip the graph still renders a full 8-bar day curve as if the choice matters | nit | `DepartGraph.tsx` | `pindrop-50m-compare.png` | planflow |
| 24 | Compare — offline pill | "offline — showing last known air · updated 1 min ago" | **jank/lie**: pill declared OFFLINE on a working connection — `useNetStatus` flips to `offline` on a single failed fetch (no NetInfo, no debounce; `status.ts:61–63`). Cleared on next render. One dropped request = scary banner | ugly | `offline/status.ts:61–63` | `offline-pill-while-online.png` | new-lane-needed (offline) |
| 25 | Turn-by-turn | "460 m Turn left" banner + live "≈0.1 µg" card | ✓ real instruction + accumulating dose; card's bottom "0 µg" scale tick sits cramped against "arrive 11:19" meta | nit | `nav/engine.ts`, NavChrome | `turnbyturn-started.png` | planflow |
| 26 | Receipt | "Trip ended · ≈0.4 µg · smokiest way +≈72 µg" | ✓ honest; **nit**: "≈ 0.4 µg about" — the "about" qualifier renders after the number, dangling; "kept on this phone only" is honest here but a real short trip with a 1-point trajectory would say the same while sharing is armed | nit | `ReceiptSheet.tsx:392–396`, `engine.ts:326` | `receipt-ended.png` | hometruth |
| 27 | Sidebar — trip row | "your location… Bicycle · 10m ≈ 0.4 µg" | **jargon**: "10m" is time-ago (`timeAgo`) but sits where a duration reads ("Bicycle · 10 min"). Grows by minutes after end — correct for "ago", reads wrong | nit | `Sidebar.tsx:339–340` | — | hometruth |
| 28 | Sidebar — How ALive works | inline expander | **jank**: long paragraph lands at the drawer's scroll end — opens showing only the first lines mid-word-clipped ("satellites a…"); fine after a manual scroll, but the expansion itself isn't brought into view | nit | `Sidebar.tsx` expander | `sidebar-howalive-clipped.png`, `sidebar-howalive-full.png` | jank |
| 29 | Sidebar — share toggle | "Share anonymous trip data" row | **slop**: two explainer lines stacked under one toggle say near-identical things (`settingsShareExplain` "share trips anonymously so Delhi sees its roads…" + `shareDataHint` "anonymous — it builds Delhi's air map; one tap to stop") | nit | `SettingsScreen.tsx:361–369`, `strings.ts:196,403` | `settings-notif-top.png` | hometruth |
| 30 | Settings — notifications | parent "Air alerts" + 3 sub-toggles | **jargon**: parent hint lists exactly the events the sub-toggles own ("smoke building, air turning worse, clean windows") — the group/member relationship is never stated; "morning air alert" is all-lowercase while siblings are capitalized | nit | `strings.ts:160–167,402` | `settings-notif-toggles.png` | new-lane-needed (notifications) |
| 31 | Settings — units row | "km / metric only" | **dead-looking**: a plain row that isn't a toggle; honest, but reads like a disabled control | nit | `SettingsScreen.tsx` units row | `settings-notif-top.png` | new-lane-needed (settings) |
| 32 | Settings — delete | "delete my data?" → cancel/delete | ✓ proper confirm, honest scope ("removed from this phone") | — | — | — | — |
| 33 | Home ↔ Trips naming | door "Your trips" → screen titled "Trips" | **nit**: label mismatch (`homeLinkTrips` vs `ledgerTitle`) | nit | `strings.ts` | — | hometruth |
| 34 | Vehicle wizard | own car/auto/bike → fuel → year → PUC | ✓ clean 4-step, honest "not sure — we'll use the Delhi average", BS-era framing; PUC optional with skip | ✓ good | `VehicleSheet.tsx` | — | — |
| 35 | Welcome cinematic | dark "first breath" count-up | ✓ honest provenance; **nit (design-law)**: pure black stage on an app whose palette is warm-neutral — deliberate smoke-dark? | nit | `WelcomeScreen.tsx` | `welcome-cinematic.png` | hometruth |

## Hardcode hunt

Numbers/strings that do NOT trace to live data (all carry code comments, none are user-visible slop except where noted):

| Constant | Where | Verdict |
|---|---|---|
| `WHO_DAILY_UG = 15` duplicated | `HomeScreen.tsx:1013` + `DelhiToday.tsx:760` | correct value, duplicated — drift risk, hoist |
| `PROFILE_BUDGET_UG {216,72,130}` | `components/shell/settings.ts:58` (+ `HomeScreen.tsx:890` default param `budgetUg=216` repeats the general value) | deliberate product constants — fine, but the DayPeek default re-hardcodes 216 |
| NCR bbox in three files with DIFFERENT bounds | `search/t0.ts:35` (76.75–77.95/28.15–28.98), `net.ts:16–17` (same), `map/tileWarm.ts:41` (76.8–77.9/28.2–28.95) | divergent duplicates — "outside NCR" verdicts differ at edges; single-source it |
| `CIG_UG` (1 cig ≈ 316 µg) | `theme.ts` + `strings.ts:171` ("Berkeley Earth rule") | documented constant — ok |
| `TRAJ_TRIM_M = 300` | `nav/engine.ts:111` | documented privacy constant, mirrors server — ok |
| breathing 10 L/min → 0.6 m³/h | `store/daylog.ts:51` | documented physiology constant — ok |
| "3 travellers / 72 h" privacy threshold | `strings.ts:286` `{k}/{h}` params | server-fed — ok |
| `stale ≥30 min` chip vs server `STALE_AFTER_S=45` | `FreshnessChip.tsx:64–66` | deliberate stricter client — ok |

**No fake data found.** Every number I could chase — ambient, dose, WHO multiples, AQI, climatology delta, trip stats, donate/private state, window forecasts — traced to prod or honest local state.

## Top of the pile (demo-blocking order)

1. **#4 + #5 airmap** — the product's namesake screen shows no air. Layers on → nothing visible; no field tint. For a demo this is the biggest gap.
2. **#24 offline lie** — "offline — showing last known air" on a live connection (single failed fetch).
3. **#21 + #22 compare slop** — `0–0` zero-ranges and "least-smoke" labels on smokier routes land on the hero surface.
4. **#1 pinned pill** — real content is untappable while scrolled under the CTA.
5. **#2 + #3 first-run** — clipped consent line + a notification firing over onboarding on a judge's first open.
6. **#10 move card** — "only ~2h of today left" at 10:56 AM reads wrong.

## Not tested / limits

- True offline drive (sim can't toggle radio cleanly) — the pill path was observed via a real flap (#24), not a forced offline session.
- Android APK — this run is iOS sim only; the Android rig needs the KVM child lane.
- Multi-day behavior (morning alert, reflect pings) — dedupe verified in `events.json`, delivery windows not waited out.
- "Home/Work add" saved-place slot flow verified reachable (search pick → settings patch path in `App.tsx:702–711`), not walked end-to-end.
