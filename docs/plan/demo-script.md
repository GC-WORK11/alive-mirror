# ALive-108 — demo-day stage script (≤3:00) — v3

*Re-synced to the **Oct-7 owner fix wave** (19 Mobile commits —
chooser-craft `2590598`, visible air field `677dc5d`+`e1e9d22`, search
t0 rewrite `c583cab`, home-truth `3088716`, delhi-today-truth `7a2cedd`,
jank-perf `4b8ac8a`, plan-flow `4fa85ea`, jargon `313ffe5`, nav-journey
`70d8de2`, map-perf `d8c7b41`, audit-fix `e1e9d22`/`6bc2b80`,
offline-verify `c06f478`/`edc4666`, sigbus-release `849fd4a`,
leftover-fixup `e147dbd`). Every beat below was re-read
against **code at HEAD `e147dbd`** + the lane reports + live prod
**`6bc2b808`** (`/health.build_sha`, deploy-7 — transit real names on
the wire) on **2026-10-07 ~21:00–21:10 UTC**. Prior stamps (Oct-5/6/7
rehearsal passes) are history — see the rehearsal log tail.*

**⚠️ The binary decides which script is real.** The pinned demo APK
`alive108-ef5d95f.apk` is baked at `ef5d95f` — **it predates this whole
wave** (19 Mobile commits). On that binary the new beats do not exist
(it carries the old v1 chooser, the invisible 0.12-alpha field, the
welcome film, the old search). The script below assumes a re-cut at
**`e147dbd` or later — and never in `d8c7b41..edc4666`**: the map-perf
tune alone crashes Android at launch (`edc4666` is its fix). If no
re-cut lands, the phone beats fall back to v2's wording (the old
chooser still plays — frame/act claims come out). See `demo-kit.md` §1.

`NLB = http://alive108-2699c171ddded465.elb.ap-south-1.amazonaws.com`

Every number below was read off the wire or the code — most twice.
Numbers marked ⟳ **drift** — the verbatim lines are phrased to survive
it ("about", "over", "under"); the T-45 `curl $NLB/health` re-read is
mandatory. Nothing here is seeded or faked.

---

## Beats (total ~2:50, 10 s of slack)

| # | time | what to tap / what the screen does | say this (verbatim) | verified number behind it |
|---|------|-----------|---------------------|---------------------------|
| 1 | 0:00–0:15 | **Phone, cold open.** The app lands straight on home — **no welcome film** (retired `4b8ac8a`; release cold start ~0.8–1 s `am start`, ~2.6 s to painted home on the iOS dev build). Hero: "the air around you · **67 µg/m³** · moderate" + "PM2.5 dust per m³ of air · same air = AQI **~157** on other apps" + "read at your location · nearest live monitor **~1.8 km** away" + "air reading: N min old". Under it, above the doors, the **incidents card**: "in Delhi's air right now — *16 fires in the Punjab–Haryana belt — the wind isn't carrying it this way right now · air barely mixing — ventilation 521 m²/s vs ~3,000 typical · measured, not reported*". | "No video, no splash — it opens on the number. Sixty-seven micrograms of fine dust per cubic metre of air outside right now — the same air other apps would call AQI one-fifty-seven. It says where it read it, how far the nearest real instrument sits, and how old the number is. And below it — what's actually happening in Delhi's air today: fires in the burn belt, and the wind checked, honestly." | `/aqi` @CP live `6bc2b808`: pm2.5 **72.4** breathing / **67.1** ambient · us_aqi **157** · nearest_sample_km **1.8** · field age ~4 min, 54 stations WAQI+DPCC ok · smoke ×1.08. Incidents line = `/v2/why.cause_note` verbatim — **flips with the wind** (N carrying ↔ refused), re-read T-45 ⟳ |
| 2 | 0:15–0:35 | **Tap "Air map".** Sheet exits in ~50–70 ms — the whole viewport is the field itself: band-coloured cells (CPCB colours — the one place colour means air), each cell edged in its own band ink so a band change reads as a **contour seam**; the cell's own µg/m³ number floats on it like an instrument readout; quiet rings mark the **54 live instruments**, names at neighbourhood zoom. Legend: "redder = worse air right now · 54 live stations · air reading: N min old". Pan south — real variance: red cells over INA/Sarojini, a cleaner pocket at Kidwai Nagar. | "This is not a styled map — this IS the air. Every cell is the kriged field, coloured by its own official band; the edges draw as contours where the air changes. The numbers on the cells are what the instruments are reading — fifty-four of them live across NCR — and the field between them is measured uncertainty, not wallpaper. Redder means worse; nothing else on this screen uses colour at all." | `AirFieldLayer.tsx` — CONF_A alphas .92/.60/.34 (same as the web hero) + `airfieldEdges` contours + `airfieldValues` per-cell reads (z≥10.5) + `airStationDots`/`airStationNames` (z≥14.5). Verified on-device `audit-fix-report.md` (`06-airmap-field.png`, `07-airmap-variation.png`) + union walk (`airmap-after-pan.png` — field stays painted through gestures) ⟳ |
| 3 | 0:35–0:55 | **Tap "Where to?"** — the sheet opens in ~200–250 ms (the 124k-entry gazetteer index was slice-built at boot, not in the sheet's mount). **Type it the way he types it:** `ashook nagar shadara gali no 4` — real gali-4 rows near Shahdara + a Photon row resolving the full address · or `pawan bakery near hanuman mandir` — real bakeries anchored on the nearest Hanuman Mandir. Then the demo pick: `huda city centre` → "HUDA City Centre Metro Station · 18 km". | "Search works the way you actually type. Misspelled, half-phonetic, a gali number, 'the bakery near the mandir' — it folds the spelling, understands gali and block and pocket, anchors 'near' to the real landmark, and never invents a pin. Watch: 'ashook nagar shadara gali no 4' — real streets, the locality it meant. Now the trip: H-U-D-A city centre — the metro station itself." | `search-report.md` — phonetic fold (ashok→xk), units, near-anchor, kind scan; t0 local + Photon t3 labelled `· OpenStreetMap`; drops-chars bug killed (`useDeferredValue` + memo rows, `6bc2b80`). Offline: bundled gazetteer answers sans network ⟳ |
| 4 | 0:55–1:35 | **Tap the HUDA row → the plan lands (~1 s warm; a fresh post-refresh OD can take ~6–9 s — it lands) → THE CHOOSER plays on the map, four acts:** **frame** — a ring breathes once on India Gate, then on HUDA (~640 ms, endpoints marked before any line); **ways** — up to three candidates trace on at ease-out, each ~¾ s, staggered ~540 ms, all at equal weight — real alternates the server priced; **hold** — a ~300 ms breath, all equals; **settle** — losers dip to hairline, the winner re-traces itself bold from→to, and the **verdict pill** pins mid-route ~260 ms later: "cleanest and fastest" / "cleanest · N% less than fastest" / the server's own `reason_line` — ~4 s on, then it fades so the route stays the object. **Whole beat ~4–6 s — let it play.** Then the compare sheet: ~20 options — Car (AC) **≈15 µg** · car-open ≈28 · bike ≈37 · bus ≈41 · auto ≈48 · bicycle ≈237 · **on foot ≈535 µg** — **~34×** · the route itself is painted by dose, segment by segment. **Leave-later row on the same sheet** (served only when `pct_less_vs_now` > 8): tonight reads "leave tomorrow 11:00 → breathe ~27% less". | "India Gate to Huda City Centre — watch the map think. Your from, your to — then the ways it found, drawn as equals. Then one settles and *says why* — in the engine's own words. Now look at the ladder: same roads, same twenty-five kilometres — on foot you inhale about five hundred micrograms; in a sealed AC car, about fifteen. That's more than a thirty-times spread the map you use today never tells you. And it prices *when* too — leave at eleven tomorrow, about a quarter less." | `RouteTint.tsx` beat constants (170/540/300/260 ms; ~4 s pill) + `chooser-craft-report.md` (on-device Release: frame/candidates/settle/pill shots; "cleanest · 53% less" on a real plan). Wire `6bc2b808` ~21:05 UTC: **23 opts**, car-AC mid **15.5** (6.3–24.8), walk **535.1** → **34.5×**, warm `took_ms` **118–326** (first hit 6.3 s). `reason_line` verbatim: "Within ~10% of the lightest dose and the lightest exhaust of those — a fair trade." **Metro+walk ABSENT at tonight's read** (~02:35 IST — GTFS service hours; it returns in service hours — T-45 decides if the "car beats metro" clause lives) ⟳ |
| 5 | 1:35–1:55 | **Home → tap the week strip** ("your lungs' calendar", chevron): the **WeekSheet** rises — 7 real day cells (weekday, serif date, dose bar washed in that day's severity), the picked day's own hour-arc + accumulators, **"the air ahead"** ghosted forecast row (band dots, least-bad marks, `confidence:"lo"` dimming), footer "only real readings land here — a blank day is a day the app wasn't with you, never a zero". Then **"Delhi today"**: city hero + species + the honest gate — a fresh phone shows "no trips yet — go live your day, we'll count it here" and *the streets/totals of strangers never masquerade as your trips*. | "Every trip lands in your lungs' calendar — seven real days, each cell washed in what that day cost. Blank means the app wasn't with you — never a fake zero. And Delhi today: the city's air is real for everyone — but your phone's trips are yours. Until you've taken one, this screen says so honestly instead of borrowing strangers'." | `WeekSheet.tsx` + `home-truth-report.md` (sheet shots, verdict row, thin-day honesty) · `delhi-today-truth-report.md` — `own===0` collapses corridors/"travellers"/CityMoves to the quiet well; filesystem proof (no ledger.json on fresh install). Outlook live: Oct-8 Moderate ~80 = best of 5 days → Oct-9…12 **Very Poor** ⟳ |
| 6 | 1:55–2:15 | **Laptop:** `/` landing (live raster + wind arrow + the shipped app's own hero + the chooser film-strip) → `/community` → `/v2/city` → `/admin` gate card → signed-in board (signed in at T-30). | "The same field serves the public surfaces — the landing page you're looking at is that exact field, live. Every donated trip becomes a live sensor: forty-seven real donations, twenty-five contributors, thirty-five kilometres today — and the privacy is in the math: a street only publishes after three different riders crossed it. The engine room sits behind a real sign-in." | `/community` live: **47 obs / 8 today / 25 contributors / 34.7 km** today · avoided **1,410.3 µg** all-time (444.3 today) · corridors 12/55 publishable (k≥3) · `/v2/city` mean **92.5** tonight (dirty evening), GRAP-indicative **stage 1** ⟳ |
| 7 | 2:15–2:35 | **AWS console** — ECS `alive108` service card: ACTIVE · 1/1 · Fargate Spot · rollout COMPLETED. Pan to Tasks if they linger. | "Real infrastructure, not a laptop demo: ECS Fargate in Mumbai behind a Network Load Balancer — one service, one task, healthy, Spot-priced. CodeBuild ships every deploy, DynamoDB holds only aggregates, S3 keeps the last good field. Net zero billed this week inside the event credits." | `describe-services` ACTIVE 1/1 FARGATE_SPOT; `/health.build_sha` `6bc2b808` == image tag (read task-def off the console, never a memorized revision); 3 alarms OK + SNS confirmed + $0.00 net/7d (ops-handover) ⟳ |
| 8 | 2:35–2:50 | **`/admin` field map — species pills** (signed in) → back to `/`. | "One rule: no fake precision. The uncertainty band is *measured* — ninety-five-point-two percent coverage at two-sigma over three and a half thousand held-out station-hours. Ten pollutants ride the same lattice — ammonia is honestly empty today — click NO₂, it's a different map, not a relabeled layer. Dose every two hundred and fifty metres for the rider; emissions per mode for the city. ALive-108 — the map that prices the air." | band coverage **95.2% @±2σ / 3,550 held-out h, 85 stations** (field_validation.md); 10 species live (ammonia param served, honestly empty); pm25↔no₂ cell corr drifts (was +0.14–0.55); edge band widens with distance; Mumbai → `outside_service_area`; `step_m: 250.0` live on `/v2/strip` ⟳ |

## The AWS console moment (required — no console, no score)

**Primary:** ECS console, already signed in, pinned tab —
`https://ap-south-1.console.aws.amazon.com/ecs/v2/clusters/alive108/services/alive108/health`
(service card: ACTIVE, running 1/1, Fargate). Pan to **Tasks** if they
linger. Read the task-def revision off the console — it rides deploys.

**CLI understudy (verified live 2026-10-05):**

```bash
AWS_DEFAULT_REGION=ap-south-1 \
aws ecs describe-services --cluster alive108 --service alive108 \
  --query 'services[0].{status:status,running:runningCount,taskDef:taskDefinition,capacity:capacityProviderStrategy}'
```

→ `ACTIVE · 1/1 · alive108:210 · FARGATE_SPOT`. Do **not** log in live
on stage.

## Contingency beats

| If this stalls | do this on stage |
|---|---|
| `/v2/plan` > ~4 s | Engine re-pricing after a field refresh — wait ~12 s once, never spam; rehearsed OD lands warm in ~0.1–1.2 s. Rehearse on the SAME OD you'll demo (fresh unseen ODs measured 2.3–9.2 s server-side; one 60-km cold call hit the 20 s planner budget → honest `options:[] + error:"planner timed out"`). `python3 tools/warm_task.py` at T-40 is load-bearing. |
| `degraded:["engine","transit"]` on the wire | Narrate it: "the API names which arm timed out — we'd rather show a missing arm than a fabricated answer." Router rows still render. |
| Chooser plays behind the vehicle wizard | Only on a profile that's never planned — the T-45 pre-warm burns this off. If it happens: close the sheet, the winner is already drawn; re-run the OD. |
| Pill text differs from the script | The pill quotes `chooserVerdict`/the server's `reason_line` verbatim — read whatever it says; it's the engine's own words. |
| Any endpoint > 8 s twice | Cut to pre-recorded ride video (docs/demo-day.md backups); keep narrating — numbers were live-verified today. |
| `/health` `field_stale:true` | Say it tells the truth; read the real age aloud. |
| Hall Wi-Fi dead | Phone hotspot (NLB is HTTP :80 only; captive portals break it). Bundled 124k-row gazetteer keeps search alive offline; the r2 pack (744 tiles) rides any APK ≥`54a296e`. |
| Numbers drifted since morning | They will — the field refreshes every 15 min. Quote the ranges ("about fifteen", "over five hundred", "thirty-something times"); never a stale constant. |
| **Demo binary is the old `ef5d95f`** | The new beats don't exist on it — narrate the v1 chooser (draw-as-equals → settle → pill still plays), skip the air-field/choos­er-4-act/raw-search claims, and say the fix wave lands in the next cut. Do NOT fake familiarity with beats that aren't on the glass. |

## Numbers sheet (re-pinned 2026-10-07 ~21:05 UTC on `6bc2b808`; ⟳ = drifts)

**Field & air**
- engine `alive_core` · routing **1,070,459 edges / 903,058 priced** · `osrm-local` router (~15 ms)
- field: **102** model samples · **54** instruments — WAQI + DPCC both `ok` (drift band 52–54; 24 if DPCC stalls >90 min) · age ~4 min · `stale:false` · history.stations_climatology **125**
- fires: **90** today (16 in-belt, 41.4 MW), FIRMS public CSV · smoke modifier **×1.08** at CP — **refused** (wind ~4 km/h NNE; NW quadrant = carrying; it flipped both ways today) · `cause_note` on `/v2/why` + `/v2/city.why` ⟳
- CP now: pm2.5 **72.4** breathing / **67.1** ambient · **US AQI 157** · LOO calibration MAE 8.8 / RMSE 12.7 / n=70 / bias +0.2 · nearest sample **1.8 km** ⟳
- city: pm25 mean **92.5** / median 91.6 / max 137.6 · GRAP-indicative **stage 1**, aqi 209 — a dirty evening (was mild all afternoon — the field moves; name the anchor) · breath day-inhaled **~1,329 µg mid ≈ 4.2 cigarettes** ⟳
- outlook @CP: **Oct-8 Moderate ~80 = the best of 5 days** → Oct-9…12 **Very Poor** (confidence "lo" past the anchor — say the shape, not the digits) ⟳

**Routing & dose**
- **demo OD India Gate→Huda City Centre (24.7 km), live `6bc2b808` ~21:05 UTC:** **23 options** · warm `took_ms` **118–326 ms** (first post-boot hit 6,324 ms) · Car (AC) **15.5** mid (lo 6.3 / hi 24.8) · car-open 28.2 · bike 37.0 · bus 40.7 (46 min) + slow bus 126.8 (125 min) · auto 47.8 · bicycle ~237–266 · **on foot 535.1 → ~34.5×** · **metro+walk ABSENT tonight** (02:35 IST — outside GTFS service hours; present in daytime reads 38.5–53.2 — the clause lives or dies at T-45) · `reason_line`: "Within ~10% of the lightest dose and the lightest exhaust of those — a fair trade." ⟳
- **the chooser's clock** (`RouteTint.tsx`): frame ~640 ms (rings 170 ms apart) → ways ≤3 × ~¾ s @540 ms stagger → hold 300 ms → settle ~300 ms + pill +260 ms → pill ~4 s hold → fade. Felt total **~4–6 s** (chooser-craft on-device). Tap-swap on the same set skips the acts: bold settle ~300 ms, demote ~450 ms. Reduce-motion collapses to final state.
- **the honest surprise**: when metro+walk is on the wire it doses ~2.5–7× car-AC (53.2 vs 7.4 this afternoon; 38.5 vs ~11 at the v6 read) — clean coach, dirty access walks. **Clause conditional on the row existing at T-45** — absent tonight.
- corridor alternates measured divergent: 96%/55%/19% of length (spec ≥15%) — real different routes
- emissions: car CO₂ 1.8–5.2 kg (mid 2.82) + PM2.5 tailpipe up to 3.18 g · metro+walk 0.42 kg CO₂, zero PM · receipt/nav counters render **grams** under 1 kg (nav-journey F1)
- per-street air (strip `step_m` 250): mint on the tagged *recommended* row on the day — least-smoke `rd` engine rows strip as 'unnamed road'
- other ODs (older fields — ratios hold, absolutes re-mint): IG→Noida 32.7×; KG→Faridabad 38.5× (first cold call timed out at 20 s → retry 6.7 s); CP→IG walk 47.5 µg/4.7 km — say "30–40×"

**The app's new truths (this wave — code-verified, HEAD `e147dbd`)**
- cold open: **no welcome film** (`WelcomeScreen` unmounted, `4b8ac8a`); release APK `am start -W` TotalTime **845 ms**; offline cold relaunch → honest home+map **938 ms** (offline-verify); iOS dev build ~2.6 s to painted home. Fresh-install order now: **ambient beat first** (4 s, 9 s fallback) → 3-page onboarding (consent p3) → location ask — **notification permission is lazy** (fires on first real air event post-consent, or on arming a reminder; `events.ts` + `notify.ts`)
- sheet opens: "Where to?" ~**200–250 ms** · "go somewhere" ~150–250 ms · Air map open ~**50–70 ms** (jank-perf, measured on iOS sim; gazetteer slice-builds at boot +900 ms)
- felt buttons: check-in pill fills same-frame (~80 ms echo, before the disk write lands); daylog sample no longer collapses MoveCard/DaysAhead (stale-keep re-assemble)
- air map: field cells CONF_A .92/.60/.34 + band-ink contour edges + per-cell µg values (z≥10.5) + station rings + names (z≥14.5) + legend "redder = worse air right now · N live stations · air reading: N min old"
- search: phonetic fold + gali/block/pocket units + near-anchor + kind scan; Photon t3 labelled `· OpenStreetMap`; dropped-chars bug dead (`useDeferredValue` + memoized rows)
- ambient hero: eyebrow names the source ("the air around you" / "near central Delhi" / "expected near you"), provenance line (nearest monitor km), freshness line ("air reading: N min old"), AQI bridge ("same air = AQI N on other apps")
- Delhi today: `own===0` → corridors/traveller-totals/CityMoves collapse to "no trips yet — go live your day, we'll count it here"; IncidentsCard on home = `cause_note` + "· measured, not reported"
- offline pack: `delhi-ncr-z9-13-r2` — **744 region_tiles / 297 resources** verified on Android KVM, airplane-mode cold relaunch renders the basemap ~4 viewports out; style_url `http://<api>/v2-light.json`; zero crashes across the whole offline walk
- transit on prod: real line names — `Bus 405`, `0AIRPORTEXP-4(NS) → 764EXT`; all-caps feed ids (`CGOCOMPLEX-2`) suppressed to plain "Bus" (`6bc2b80`, live since deploy-7 `6bc2b808`)
- gates at HEAD: `tsc`/`expo lint` clean · node:test 84+76+17+16 pass · routeTint self-test 55 OK (union-regression)

**Honesty**
- band coverage **95.2% @±2σ over 3,550 held-out station-hours, 85 stations** (`σ=√(krige_sd²+(0.12·µ)²) × SIGMA_CAL 3.2`; `server/data/field_validation.md`)
- LOO calibration: MAE **8.8 µg/m³**, bias **+0.2**, n=70 — live at `/aqi.calibration`
- edge /aqi 11.1 km from nearest sample: band widens 10.7–97.7 · Mumbai → `outside_service_area` · budget timeout → `options:[] + error:"planner timed out"`
- `/community`: **47 obs · 25 contributors · 34.7 km today · 1,410.3 µg avoided all-time (444.3 today)** · corridors publish only at k≥3 — suppression on the wire ⟳
- self-grade (`/v2/skill`): **~330 pairs** — h+0 band-hit ~90% → h+11 ~36% (error widens honestly with horizon; endpoint 5.2 s → 0.7 s on prod)
- why: **stagnation primary tonight** (VC 521 m²/s vs ~3,000; trend +11.0 µg/5.8 h climbing underneath); fires refused (`carrying:false`) ⟳
- archive: recorded hours grow daily; honest gaps stay gaps — check `/v2/archive` on the day
- admin: gate card → `POST /v2/admin/login` → HttpOnly cookie ~8 h (T-30 playbook `docs/plan/admin-login.md`)

**AWS**
- ECS `alive108` ACTIVE · 1/1 · FARGATE_SPOT (owner's standing call — no flip) · image `alive108-api:6bc2b808` == `/health.build_sha` · 3 alarms OK + SNS confirmed + **$0.00 net/7d** · rollback `deploy.sh rollback <sha>`

## Do-not-say list (failed verification — never on stage)

- ~~"the welcome film"~~ — gone (`4b8ac8a`). Fresh install: ambient beat → onboarding → location ask; the notif dialog is lazy now.
- ~~"the map is just a basemap / the field is invisible"~~ — dead since `e1e9d22`; the air map IS the field. (On the old `ef5d95f` APK it's still true — know which binary is on the phone.)
- ~~"candidates draw as equals, winner settles ~1.5 s"~~ — that's the v1 chooser. Now: **frame → ways → hold → settle → verdict pill**, ~4–6 s felt (`2590598`). The pill pins ONE line ~4 s, then fades — don't wait for a second pill (the two-pill cycle was the old build).
- ~~"search is hardcoded / types garbage"~~ — phonetic fold + units + near-anchors; try `ashook nagar shadara gali no 4` live.
- ~~"Delhi today shows trips you never took"~~ — aggregates gated on one real own trip (`7a2cedd`); a fresh phone says "no trips yet".
- ~~"Bus CGOCOMPLEX-2"~~ — feed-internal ids suppressed live (`6bc2b808`); receipts read "Bus 347A → Metro"-style.
- ~~"release iOS is proven clean"~~ — overstated until tonight: nav-journey caught **SIGBUS ×2 on a Release build** tapping "Where to?" in the first ~90 s of a post-reinstall cold launch. **Now root-caused and closed on sim** — `849fd4a` found the YG-scavenge fault class (JS thread faulting into a just-scavenged young-gen segment; every crash window is GC-Young-Gen), eliminated three false leads, then killed the mechanism itself with `withAllocInYoung(false)` on sim: **40/40 clean** under full repro (`sigbus-release-report.md`). Device builds unaffected (gates are `TARGET_OS_SIMULATOR`). Say "found it, root-caused it, fixed it — forty clean runs of the exact repro" — device hardware remains honestly unmeasured.
- ~~"plans answer in ~70 ms"~~ — warm ~0.1–1.2 s on the rehearsed OD; fresh ODs 2.3–9.2 s server; one cold 60-km call hit the 20 s budget → honest empty. Say "about a second or two on the rehearsed trip".
- ~~"metro is the clean option"~~ / ~~"car beats metro" as a constant~~ — metro+walk is GTFS-hours dependent (absent at tonight's 02:35 IST read, ~38–53 µg in service hours). **Only narrate it if the row is on the wire at T-45.**
- ~~"62-station DMRC registry"~~ — real GTFS (263 stations / 37 routes).
- ~~"97,452 corpus / 16,952 addresses"~~ — **97,447 / 16,949**.
- ~~"7,240 held-out station-hours"~~ — **3,550 over 85 stations**; 95.2% is the number that holds.
- ~~"11 live species"~~ — **10**; ammonia served but honestly empty.
- ~~"corridors diverge ≥15%"~~ as the quote — measured **19–96%**; quote the measured number.
- ~~fixed AQI/pm2.5/option-count values~~ — everything drifts with the 15-min field; say ranges and read the screen.
- ~~"all ODs answer ~1.8 s"~~ / ~~"24 ms reroute / 100+ concurrent"~~ — fresh ODs 2.3–9.2 s; single-user path only (~8–15 concurrent honest posture).
- ~~absolute "Delhi AQI is 150"~~ — that's a point read; name the place (city lattice mean ≠ CP point).
- ~~"/admin/api tiles"~~ — `/admin` sits behind the sign-in (`b563da2`): gate card; sign in at T-30, never paste the token on camera.
- ~~"Android mid-range feel is proven"~~ — every Android number so far is a **SwiftShader delta** (~500 ms/present floor); the tune shows up as *more presents per window* (follow-mode p50 501→153 ms), not lower p50. Honest line: "verified on the emulator; the phone tells the real story" — `map-perf-report.md`.

## Rehearsal logs

**Pass 1 (Oct-5 12:20 IST):** beats in stage order — landing 0.71 s ·
health 0.48 · aqi 0.48 · plan 1.80 · depart 0.48 · community 0.48 ·
city 0.69 · moves 0.52 · grid-40 1.47 · edge-aqi 0.49 · admin 0.94 ·
describe-services 1.61 → ~10 s network in a 170 s script.

**Pass 2 (Oct-5 12:55–13:15 IST, deep probes):** search battery 25/25,
p50 474 ms; plan warm p50 346 ms; unseen-OD plans 4.0/6.3 s; strip
`step_m` 250; corridor divergence 44–97%; species corr −0.05; refresh
countdown ticking.

**Pass 3 (Oct-5 16:05–16:50 IST, post-re-anchor `951eeb3c`):** demo OD
20 opts, walk 189.8–211.6 µg ≈ 33–35× car; fresh-OD plans 2.3–6.7 s;
KG→Faridabad cold call hit the 20 s planner budget → honest empty;
fires 70/16 ×1.27; species 10 (ammonia empty); 3,550 h / 85 stations;
search battery 172/174 (98.9%) p50 471 ms.

**Pass 4–6 (Oct-5 23:55 UTC → Oct-6 11:40 UTC, builds `37e55668` →
`f4139b24` → `4eb9e1e8`):** persistence blend live; plan demo OD
19–24 opts ~33–36×; metro+walk flickered present/absent (GTFS hours);
depart now ~29 → worst ~103; skill 34→131 pairs; fires flipped
carrying↔refused with the wind; admin became gated cookie auth. Full
tables: `demo-rehearse-v2-report.md`, `demo-day-final-report.md`,
`demo-reverify-v2-report.md`.

**Pass 7 — the owner fix wave (Oct-7, this rewrite):** re-beated
against code `e147dbd` + lane reports; live re-pin on `6bc2b808` ~21:05
UTC: plan demo OD 23 opts, car-AC 15.5 / walk 535.1 → **34.5×**, warm
118 ms, metro absent overnight; `/aqi` @CP 72.4/67.1/AQI 157, fires
90/16 ×1.08 refused; community 47/25/34.7 km/1,410.3 µg; city mean
92.5 (GRAP-1 evening); depart pct 27 (best +13 h 11:00); outlook
Oct-8 Moderate ~80 best-of-5 then 4× Very Poor. **The binary gap is
the day's standing caveat:** APK `ef5d95f` predates the wave — re-cut
≥`edc4666`/`e147dbd` or the phone beats narrate the old app.

**Cold-path observation (unchanged):** first plan calls after a task
swap can hit ~12 s arm timeouts → `degraded:["engine","transit"]` with
real rows still served; recovered once warm. `warm_task.py` + rehearsed
OD is the mitigation; `/v2/strip` route_ids are per-task — re-mint
plan→strip pairs after any task swap.

| check | verdict |
|---|---|
| every quoted number read off the wire | GO |
| all 8 beats inside budget (~2:50/3:00) | GO |
| plan latency on rehearsed OD | GO — warm only |
| fresh-OD latency | NOTE — 4–9 s; stick to rehearsed OD or accept the pause |
| drift safety of verbatim lines | GO — phrased in ranges, T-45 re-read mandated |
| AWS console / CLI proof | GO — verified |
| corrupt-data risk (public POSTs) | GO — GET-only probing + /v2/plan |
| demo binary carries the new beats | **BLOCKED on re-cut** — `ef5d95f` predates the wave; cut ≥`e147dbd` or fall back to v2 wording |
