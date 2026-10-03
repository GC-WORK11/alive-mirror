# Claims audit — every number & claim that faces the user

Audit against `docs/plan/10-claims-ledger.md` (say/never-say) and
`docs/plan/02-consumer-ux.md` §3 (vocab: never AQI/PM2.5/µg/dose/BS on
surface screens; technical terms only behind "How we got this") and
`docs/26-honest-impact.md` (kill list + sanctioned claims).

Verdicts: **✓** compliant · **⚠** borderline/incomplete · **✗** violation.

---

## 1 · Consumer string table — `Mobile/src/i18n/strings.ts`

| location | claim / number | verdict | required fix |
|---|---|---|---|
| strings.ts L6–16, 18–19, 28–48, 51–63, 71–73, 80–91, 94–101, 104–109, 114, 119–123 (+hi mirrors) | Pure navigation/label copy, no numbers, no jargon ("Where to?", "Directions", "turn-by-turn", mode/fuel names, a11y) | ✓ | — |
| strings.ts:17 `outsideDelhi` | "outside Delhi — breath estimates not available" — uses "estimates" | ✓ | — |
| strings.ts:20–22 lightest* tags | "lightest on both / for you / for Delhi" — comparative, spec verbatim | ✓ | — |
| strings.ts:25–27 `youBreathed`/`ridePutOut`/`lessThanByAuto` | receipt vocabulary, comparison built in | ✓ | — |
| strings.ts:49 `vehicleDone` | "we'll estimate using vehicles like yours" — declares estimate | ✓ | — |
| strings.ts:65–66 `breathingHeavier/Lighter` | relative claim, no units; currently unwired (SEAM) | ✓ | — |
| strings.ts:68 `updatedMinAgo` | "updated {n} min ago" — **defined but never rendered anywhere** (no consumer of this key in the app) | ✗ | Wire it: ledger requires "Data is N minutes old — always visible" wherever air data renders |
| strings.ts:69 `dataFromModelOnly` | "from model + satellite data — live stations reconnecting" — defined, never rendered; "satellite" is loose (field = stations + CAMS model + traversals) | ⚠ | If used, say "stations + forecast model + trips" |
| strings.ts:74 `layerCorridors` | "measured streets" — corridor cells are traversal-*implied* estimates (dose ÷ mode factors), not instrument measurements. Doc 26 sanctions the per-cell phrasing "measured by N commutes; data is H hours old" — a bare "measured" reads as air-instrument truth | ⚠ | Reword to "commute-measured streets" or "N commutes · Hh old" per doc 26 verbatim claim |
| strings.ts:78–79 yesterday % | "{p}% less/more than yesterday" — real arithmetic over local ledger | ✓ | — (see ledger-integrity note §3) |
| strings.ts:87 `shareDataHint` | "anonymous — it builds Delhi's air map" — traversals do Bayesian-update the field (airfield.py:355-361 verified); but see privacy gap §7 — the /observe path stores full route incl. endpoints at 5 dp, so "anonymous" is overstated vs doc 07 | ⚠ | Privacy fix first, then the claim is honest |
| strings.ts:92 `howAliveBody` | "it **estimates** the smoke… also **estimates** what the ride puts out… honest bands, never fake precision" — exemplary honesty copy; "satellites" loose (see above) | ⚠ | s/satellites and trips people donated/satellites→model grid/ or keep — minor |
| strings.ts:102 `leaveAtBreatheLess` | "leave {time} → breathe ~{n}% less" — n IS a real percent (main.py:604 `round(100*(1-best/now))` despite the `ug_` name), "~" hedge present; **but** /depart is fetched with hardcoded `vehicle=auto` — the % is the auto-mode number regardless of the selected option | ⚠ | Pass the selected option's vehicle to /depart, or label "for auto" |
| strings.ts:110 `breathedSoFar` | "breathed ≈ {n} so far" — n is cigarette-eq, 🚬 icon adjacent, "≈" hedge; matches doc 02 §S6 counter spec | ✓ | — |
| strings.ts:113 `receiptSaved` | "the smokiest way would have added ≈ {n}" — n is a bare µg delta (model-vs-model), no unit, counterfactual phrased as fact | ⚠ | Attach unit context ("≈ {n} µg more smoke") or restate per doc 10 per-trip-band rule |
| strings.ts:116–117 intro | "every trip in delhi has an air price." / "rank every way there by what you'd **actually** breathe" — "actually" overstates a model estimate | ⚠ | "by what you'd breathe" (drop "actually") |
| strings.ts:147–149 (hi) youBreathed/ridePutOut/lessThanByAuto | Hindi mirrors — clean, colloquial | ✓ | — |
| strings.ts:208 (hi) `howAliveBody` | Hindi mirror — uses अनुमान (estimate) throughout | ✓ | — |

**Jargon scan — consumer strings:** zero AQI / PM2.5 / µg / dose / exposure /
BS / emission-factor tokens in strings.ts. ✓ clean. (One breach lives in
`notify.ts` — §2.)

## 2 · Push notifications — `Mobile/src/notify.ts`

| location | claim / number | verdict | required fix |
|---|---|---|---|
| notify.ts:42–43 `scheduleDailyBrief` | "delhi's cleanest window today — air runs {dropPct}% lighter" — computed from `/today`, which is **decade-median climatology** (main.py:662-670, source "openaq-s3-climatology"), presented as today's forecast; and `dropPct` is floored at `Math.max(5,…)` (useShellFlow.ts:208) — a fabricated minimum number when the curve is flat | ✗ | Say "usually lightest window" + name the basis (decade-typical), and remove the 5% floor (0% = don't send) |
| notify.ts:64 `scheduleDeparture` | "same trip now — {savedPct}% less PM2.5" — **"PM2.5" jargon on a consumer notification surface** (doc 02 §3 ban); value is a real percent (see §1 depart row) | ✗ | "…{n}% less smoke" |

## 3 · Rendered numbers — `Mobile/src/**/*.tsx`, `App.tsx`

| location | claim / number | verdict | required fix |
|---|---|---|---|
| App.tsx:231 receipt | `Math.round(doseUg*10)/10` — a **bare µg point value** next to a `CigStrip` whose unit is cigarettes (strip reads ~0.1 cig, number reads "41.2" — unit mismatch a user can misread as 41 cigarettes); no ≈, no est., no band, no comparison → violates "never a bare number" (doc 02 §5) and "always a band + est." (doc 10) | ✗ | Show cigEq ("≈ 0.13 🚬") or the lo–hi band with "est."; keep the comparison line |
| App.tsx:233–234 receipt saved | `savedUg` = worst−chosen model delta rendered via `receiptSaved` — see §1 | ⚠ | same fix |
| NavChrome.tsx:33–35 banner | ETA min / km / arrival — real routing data | ✓ | — |
| NavChrome.tsx:41–46 counter | "breathed ≈ n" 🚬 — n = cigEq of accumulated `pm25 × microenv × ve × dt` — a model estimate, "≈"-labeled (spec-sanctioned ticker); updates every 25 s from a fresh `/aqi` fetch, not a fake 1 s ticker | ✓ | — |
| CompareSheet.tsx:54–66 depart row | "leave {time} → breathe ~{n}% less" — real percent, "~"; wrong vehicle basis (auto hardcoded) | ⚠ | §1 depart fix |
| CompareSheet.tsx:67–80 ModeRow list | ETA/distance real; `inFrac` = dose_ug/worst — relative bar, no units (spec); tag `lightestForYou` on min-dose option ✓; **dose_lo/hi bands and `confidence` exist in the payload but are dropped — no provenance surface at all** | ⚠ | Long-press → "How we got this" per doc 02 §S4 (bands + sources); until then, bars are the whole honesty surface |
| CompareSheet.tsx:101–103 steps | real OSRM distances | ✓ | — |
| Sidebar.tsx:146–160 Today | `cigOf(todayUg)` as hero number — a summed **model estimate** shown as a bare 2-dp point ("0.04"); spec wants the number but doc 10 wants "≈"; yesterday-% comparison shown when data exists ✓ | ⚠ | Prefix "≈"; also see ledger-integrity note below |
| Sidebar.tsx:163–181 week bars | relative heights over logged trips | ✓ | — (data caveat below) |
| Sidebar.tsx:187–198 trips list | per-trip cigEq point number; `tr.label`/`tr.from`/`tr.to` are server/English strings ("Car (AC)", "current location", "central delhi") — i18n gap | ⚠ | ≈ + i18n fallback names |
| SearchScreen.tsx:43–48, 88, 158–160 | real haversine distance labels | ✓ | — |
| SearchScreen rows (server) | `kind`/`subtitle` strings ("metro station", "restaurant") rendered raw — English-only on a Hindi-UI surface | ⚠ | Translate the small fixed kind vocabulary |
| useShellFlow.ts:157–176 ledger donation | **`logTrip` + `observeTrip` fire on option-select in phase "compare" — a lookup, not a trip.** Every route browse mints a ledger "trip", an `avoided_ug` credit, and a donated "traversal" (the *planned* route geometry, not a GPS track). All downstream counts ("journeys", "contributors", "µg avoided", corridor cells) are inflated by non-trips | ✗ | Gate on actual nav/receipt (phase transitions or arrival), not selection |
| useShellFlow.ts:126–129 receipt | `navDose` accumulated from modeled field value — ≈-labeled downstream | ✓ | — |
| i18n coverage | Server-driven English renders unlocalized: mode labels ("Auto-rickshaw", "Metro + walk", "Car (AC) · quieter rd"), `decision_reasons`, `reason_line`, gazetteer `kind` — doc 02 §6 breach | ⚠ | Localize the fixed label/reason vocabulary client-side |

## 4 · Server payloads — basis / label fields

| location | claim / number | verdict | required fix |
|---|---|---|---|
| exposure.py:175–186 dose() | dose_ug point + `dose_ug_lo/hi` (σ-propagated band) + `confidence` + `factors` + `coverage` — full provenance; sources in header ([1] 28.2×/5.3× measured) | ✓ | — |
| main.py:418–486 /compare | per-option exposure bands + `field` status (incl. age) shipped | ✓ | — |
| main.py:529–541 `ug_saved_vs_worst` | model-vs-model delta, honest key name | ✓ | — |
| main.py:564–615 /depart | `ug_saved_vs_now` is a **percent** (L604), misnamed field — consumers guess wrong without reading the code (notify.ts savedPct shows the trap) | ⚠ | Rename `pct_less_vs_now` or add explicit units field |
| main.py:618–657 /aqi | pm25 + `pm25_lo/hi` + `nearest_sample_km` + `calibration` + `field.status` (age_s) + `typical` provenance | ✓ | — |
| main.py:660–671 /today | climatology labeled `"source": "openaq-s3-climatology"` | ✓ | — |
| main.py:759–805 /escape | `pct_less_than_here` + `data_km` confidence + `none_cleaner` honest-empty state | ✓ | — |
| main.py:825–882 /shift | `dose_ug`/`cig_equiv` **point values** (no band) + explanatory `note` | ⚠ | Add lo/hi band (field σ exists) before any UI surfaces it |
| decide.py:95–116 reasons | "the smokiest way to go", "you'd breathe the least smoke on this one" — hedged, jargon-free ✓; "the safest way to travel" — a coarse MoRTH tier model stated flat | ⚠ | "the safest pick of these" (relative scope) |
| v2/plan.py:60–76, 126–143 | `EMIT_GKM` bands + `EMIT_BASIS` "est. for vehicles like yours…" + dose `{lo,mid,hi}` + `"basis":"est."` — the reference implementation for labels | ✓ | — |
| v2/plan.py:323–341 reason_line | "Least smoke for you and lowest emissions" — comparative, scoped | ✓ | — |
| v2/strip.py:20–39 | emission curve bands + `"est. — vehicles like yours…"` basis | ✓ | — |
| v2/city.py:62–78 | `field_age_s` + per-source up/down + trip aggregates only | ✓ | — |
| v2/search.py:176–180 | `"t2"` key written twice — t2 result rows never reach the client (status string overwrites the list); `tiers`/`took_ms` honest | ⚠ | Fix duplicate key (bug, not a claim) |
| emissions.py (whole) | bands `{lo,mid,hi}` everywhere, `label` "estimated for vehicles like yours (…)", `basis` per_vkm/per_pax_km, BS classes confined to label strings, "CNG is not clean" honored, non-exhaust reported separately per docs/26 | ✓ | — |
| community.py:294–315 corridors | `avg_dose_ug` per cell — traversal-implied estimate; label "corridor cell · avg inhaled µg" on admin/city has no est. marker | ⚠ | Label "est. from N donated trips" |
| community.py:107–124 /observe | stores raw coords (5 dp ≈ 1 m) incl. endpoints — see §7 | ✗ | §7 fix |
| segments.py:117–118 hotspots | `"label": "hot zone"` — consumer-safe wording | ✓ | — |
| grid.py cells | `conf` per cell → FieldLayer dims thin areas | ✓ | — |
| airfield.py:354–361 | claims "krige + 12% instrument floor + Bayesian traversal update" — verified in code | ✓ | — |

## 5 · Public pages — `server/city.html`, `server/admin.html`

| location | claim / number | verdict | required fix |
|---|---|---|---|
| city.html:220–222 hero | "**measured by its own commuters**" — the killed claim's semantic equivalent (doc 10: "your phone measured"; doc 26 K5); field is kriged instruments+CAMS, traversals only nudge corridors | ✗ | "mapped street-by-street from instruments, model grid and donated trips" |
| city.html:229 f-tag | "pm2.5 · µg/m³ · kriged field" — jargon permitted on the dashboard surface (ledger sanctions MAE/field detail here) | ✓ | — |
| city.html:250–267 breath panel | point + **krige σ band drawn + labeled** ("the width of our honesty") + `typical` decade context | ✓ | — |
| city.html:277–279 breaths card | "**breaths measured today** … counting live" — a derived model number (`dose_ug_24h ÷ pm25 × 2000`), ticking up between 60 s fetches via `breathRate` — fake per-second liveness on a model sum; "measured" wording | ✗ | "litres of Delhi air modeled through today's donated trips — est."; drop the ticker or tick only on refresh |
| city.html:282–285 cigs card | "the city smoked today — N cigarettes" — summed modeled dose as flat fact, no est. | ⚠ | "≈ N (est. Σ modeled dose)" |
| city.html:290 contrib card | "km measured across N anonymous contributors" — km are real donated lengths (count = true) but inflated by lookup-trips (§3); "measured" wording | ⚠ | "km traveled" + fix the source metric |
| city.html:293–295 saved card | "**dose dodged** — µg avoided by choosing the cleaner route · N **cigarettes not smoked**" — aggregate counterfactual presented as achieved impact = the killed class ("we cut X") in cigarette units | ✗ | Kill the card, or restate per doc 10: per-trip band only ("Σ est. dose difference vs the smokiest option shown") |
| city.html:311 `nstations` | fallback literal "28" rendered if `/aqi` fails (live value normally overwrites) | ⚠ | Fallback "—" not a fabricated count |
| city.html:312–315 fieldmeta | `field age N min` + nearest sample km + `calibrated mae {file} µg` — freshness + self-reported error live on the page | ✓ | — |
| city.html:336–340 footer | "kriged over CPCB/DPCC/HSPCB instruments + CAMS, **Kalman-smoothed, Bayesian-updated by traversal-implied concentration**" — verified true (airfield.py:98–113, 355–361); but "**commuters become the sensor network the city doesn't have**" — phones are not sensors (doc 26 T3-15 honest frame: demand/exposure layer) | ⚠ | Keep the verified mechanism; reword sensor-network → "the demand map the city didn't have" |
| city.html:442,451–454 src/ticker | source · samples · stations · krige + "field age N min" + "+N% vs decade-typical (9M measured station-hours)" — provenance shown; "9M" consistent across docs (125-station product) though the raw count isn't recomputable from the committed quantile file | ✓ | — |
| city.html ticker "km measured" | same "measured" wording issue | ⚠ | "km traveled" |
| city.html:466 "updated HH:MM ist" | page-level freshness | ✓ | — |
| admin.html:178–181 statusline | samples · stations · source · krige · **age N min** · wind · fires | ✓ | — |
| admin.html:187 "µg avoided · all time" | cumulative model-vs-model counterfactual shown as an achievement metric — killed class in aggregate form | ✗ | Relabel "Σ est. dose delta vs worst option" or drop |
| admin.html:188 "cigarettes · 24h dose" | model sum, flat number | ⚠ | "≈ est." |
| admin.html:194–216 contributor/journey tables | counts exist and are real rows — but inflated by lookup-trips (§3); per-row `dose_ug`/`avoided_ug` are estimates shown bare | ⚠ | Fix source metric; est. labels |
| admin.html:202–205 corridors | `avg_dose_ug` per cell — traversal-implied estimate, no est. marker | ⚠ | "est." |
| admin.html footer | "anonymous ids only" — true at id level; see §7 coords caveat | ⚠ | §7 |

## 6 · `README.md` — claims vs current code (another lane rewrites it; audit of what exists now)

| location | claim / number | verdict | required fix |
|---|---|---|---|
| README:3 tagline | "ranked by **estimated** inhaled pollution dose, with honest uncertainty" — declares estimate | ✓ | — |
| README:17 | "walking ≈ 28×, auto-rickshaw ≈ 5× the metro" — matches exposure.py [1] (28.2×/5.3× measured) & ledger | ✓ | — |
| README:25–37 | "live, verified" public endpoints on AWS IP — unverifiable from repo | ⚠ | Re-hit each URL at integration; drop any dead |
| README:46–47 | "8-hr two-wheeler shift ≈ 1.1–1.5 cigarette-equivalents on heavy days" — static figure; endpoint returns a point value | ⚠ | Verify against /shift on a heavy day; keep band |
| README:50–51 | "MAE 46 µg/m³, bias +0.3, n=94" — real (`field_calibration.json`), **but that's the LOO-over-live-stations run; the independent archive replay (field_validation.md) shows MAE 47.1, bias +45.1 (+150%)** — serving the flattering variant next to "honest error" | ⚠ | Name the method ("leave-one-out") or cite both numbers — doc 26 claim #2 sanctions the honest version including bias |
| README:63 | "~105 in NCR" instruments vs calibration n=94 / live `station_readings` count | ⚠ | Use the live count or "~94–105" |
| README:70 | "CAMS under-reads Delhi 2–8× at hotspots; LOO proved it" — field_validation + calibrate support the direction ✓ | ✓ | — |
| README:72–79 feature list | "Lung Ledger, budget %, avoided total, sparkline, journeys drawer, streak, Ambient Mode, horizon scrubber, hazard reporting, dose-colored route" — **most no longer exist** in the v2 shell (delete-list applied; receipt/sidebar/week-bars/search do) | ✗ | Rewrite to shipped reality (the README lane owns this — flagged) |
| README:78 | "<10 ms answers, 26.5k gazetteer" — corpus size ✓ (26,545 in bench); latency measured for C++/Python server engines, not the on-device T0 index | ⚠ | Bench t0 on-device or drop the number |
| README:83–85 | "51 assertions" — ~52 `check()` calls counted; verify at integration | ⚠ | trivial |
| README:100 | "10 · Provenance … measured vs modelled" — the ledger idea, doc exists | ✓ | — |
| README:30 | "the city breathing in real time" (/admin link) — 10 s-refresh ops board; "real time" loose per ledger | ⚠ | "live ops board" suffices |

## 7 · Privacy claims vs implementation

| location | claim / number | verdict | required fix |
|---|---|---|---|
| docs/plan/07 §3 vs community.py:107–124 + useShellFlow.ts:167–174 | Doc claims: client drops first+last 300 m, ~100 m thinning, 4 dp rounding, no raw trajectories at rest. The live path posts **planned route geometry** (incl. exact endpoints = home/destination) to `/observe`, stored rounded to **5 dp (~1 m)** in `community.json` — the v2/trip pipeline implements the promised design but the app doesn't call it | ✗ | Route donations through `/v2/trip` (or replicate trim+thin+round in observeTrip) — until then "anonymous"/"endpoints hidden" is not fully true |

## 8 · `docs/plan/bench-results.md`

| location | claim / number | verdict | required fix |
|---|---|---|---|
| bench-results.md:8–21 | 26,545-entry corpus, 10k queries, p50 0.189/16.623 ms, speedups 88×/100×/102× — protocol documented, math checks (16.623/0.189=87.9), bit-exact parity asserted | ✓ | — |
| bench-results.md:23–39 | pending tables — honestly blank, not zero-filled | ✓ | — |

## 9 · Model outputs that look measured (subtlest class)

| location | claim / number | verdict | required fix |
|---|---|---|---|
| city.html breath counter | derived breaths ticking between fetches | ✗ | §5 |
| city.html "dose dodged" / admin "µg avoided all-time" | counterfactual delta as achievement | ✗ | §5 |
| app receipt µg point value | point precision + unit ambiguity | ✗ | §3 |
| `navDose` "breathed ≈ n" | modeled accumulation — ≈-labeled, sanctioned | ✓ | — |
| corridor `avg_dose_ug` cells | inverted-model estimate presented as "avg inhaled" | ⚠ | est. label |
| `dropPct` floor 5 in morning brief | fabricated minimum on climatology | ✗ | §2 |
| depart % for `vehicle=auto` regardless of selection | right number, wrong basis | ⚠ | §1 |
| `/shift` point dose/cig | no band | ⚠ | §4 |
| `savedUg` counterfactual in receipt | model-vs-model delta as fact | ⚠ | §1 |

## 10 · Data-freshness coverage ("data is N minutes old — always visible")

| surface | age shown? | verdict |
|---|---|---|
| App compare/nav/receipt/sidebar | **never rendered** (`updatedMinAgo` string exists, unused; `/compare` ships `field.age_s`, ignored) | ✗ |
| city.html fieldmeta + stamp | `field age N min` + `updated HH:MM ist` | ✓ |
| admin.html statusline | `age N min` | ✓ |
| /health, /aqi, /compare, /v2/city payloads | `age_s` shipped | ✓ |

---

## Violations summary (worst first)

1. **`useShellFlow.ts:157–176`** — trips/traversals logged on option-**view**, not travel: every aggregate claim (journeys, contributors, avoided µg, corridor cells) counts non-trips. Feeds violations 2–4.
2. **`server/city.html:220`** — "measured by its own commuters" (+ footer "sensor network"): the exact killed claim, semantic form.
3. **`server/city.html:293–295` + `admin.html:187`** — "dose dodged / cigarettes not smoked / µg avoided all time": aggregate counterfactual presented as achieved impact (the "we cut X tonnes" class).
4. **`server/city.html:277–279`** — "breaths measured today · counting live": modeled sum, "measured" wording, fake per-second ticking.
5. **`Mobile/App.tsx:231`** — receipt shows a bare µg point value beside a cigarette-strip (unit ambiguity + fake precision, violates "never a bare number" + "always a band").
6. **`Mobile/src/notify.ts:64`** — "N% less PM2.5": the only consumer-surface jargon breach.
7. **`Mobile/src/notify.ts:43` + `useShellFlow.ts:208`** — "delhi's cleanest window today" from decade-climatology + a fabricated 5% floor.
8. **Field age never rendered in-app** — `updatedMinAgo` dead string; ledger's "always visible" unmet.
9. **`/observe` privacy path** — endpoints+full routes stored at ~1 m despite doc 07's trim/thin/round claims.
10. **`README.md` feature list** — describes deleted v1 features; calibration bias number cites the flattering LOO method without saying so.

## Recommended fixes for the integrator

1. Gate `logTrip`/`observeTrip` on real trip lifecycle (nav start / arrival), not option select.
2. city.html: reword hero + footer to "instruments + model grid + donated trips"; restate "dose dodged"/"city smoked"/"breaths" as Σ **est.** or cut; drop the breath ticker or tick on refresh only.
3. admin.html: relabel "µg avoided" → "Σ est. dose delta"; corridors/avg-dose → "est. from N trips".
4. Receipt: replace bare µg with "≈ N 🚬" (or dose_lo–hi band + "est.") + the comparison line.
5. notify.ts: "PM2.5" → "smoke"; daily brief → "usually lightest window" + drop the 5% floor.
6. Wire `updatedMinAgo`/`dataFromModelOnly` wherever air data renders (compare sheet + Delhi-today view).
7. Pass selected mode to `/depart` (or label "for auto"); rename `ug_saved_vs_now` → `pct_less_vs_now`.
8. Point donations at `/v2/trip` privacy pipeline (or port its trim/thin/round to `observeTrip`).
9. Localize server-driven labels/reasons/kind-subtitles (fixed vocab, both languages).
10. README lane: rewrite feature list to shipped reality; label MAE "leave-one-out" or cite both 46.1/+0.3 (LOO) and 47.1/+45.1 (archive replay).
11. `v2/search.py`: dedupe the `"t2"` response key (rows unreachable).
12. Add lo/hi to `/shift` before surfacing it; "the safest way to travel" → "the safest pick of these".

Counts: **56 audited rows — ✓ 24 · ⚠ 22 · ✗ 10.**
