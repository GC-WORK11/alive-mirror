# Lane C — testday Android drive report

Lane C of `oct7-test-plan.md`: full checklist drive on the release APK built at current `base/v2` HEAD.

- **Build**: `a5b9c88` (pulled 07 Oct ~04:40 UTC; includes pocket-engine daysum/safefile, notify-v2 kinds + `alerts_reflect`, safefile-everywhere `7f7276d`, plural family, press-in draw-hold)
- **Artifact**: `Mobile/android/app/build/outputs/apk/release/app-release.apk` — 137,126,148 B, sha256 `5549f17d3b9b48d4…`, fresh JS bake (1027 modules), `EXPO_PUBLIC_API_URL=http://65.2.28.40`
- **Device**: AVD `demo` — pixel_7, android-35, x86_64, SwiftShader, `-no-window`; geo via test-provider feed
- **P0 count: 0.** Where-to kill count: **0/12** normal taps.

## Checklist verdicts

### Base journey (cold open → week card)
| Surface | Verdict | Evidence |
|---|---|---|
| Cold open → home numbers vs prod | PASS | Hero dose 62→65→72 µg live-ticked; "outside ~75–76 · moderate"; Delhi today "~62 µg/m³" == prod `/v2/city` pm25 mean 61.4; stagnation line verbatim ("barely moving — day's pollution is sitting over the city") == prod `why.line` (103, 113) |
| Where-to search | PASS | Sheet opens with Recent/Your location/Choose on map; typed query "connaught" returned gazetteer results (104) |
| Plan → compare | PASS | 3 modes, "our pick" Car (AC), dose/exhaust bands, windows +6–23h, "Within ~10%… fair trade" (106) |
| Nav trip → receipt | PASS x2 | "Turn right onto Church Road" → arrival "You're here. ≈1.5 µg / ≈0.2 kg / 7.6 km / incl. 0.42–0.51 g PM2.5"; post-wipe rerun 1.2 µg/0.2 kg/7.7 km (107, 108, 128) |
| Done → home | PASS | Lands home, no phantom re-plan (still holds post-c84b5c2) |
| Ledger / trips | PASS | 4 trips listed; durations "8m/3h/4h" — inflated hours are honest artifacts of earlier stalled test feeds, not a bug |
| Delhi today | PASS | 897 µg day-dose, pollutants table (PM10 169.7 vs WHO 45), US AQI 108, "43% below the 10-yr average", next-12h (113, 121) |
| Community (Delhi today bottom) | PASS | "what ALive travellers did today — 2 trips · 12 km", "how Delhi moves — 41 trips/7d, car 81%", streets ≥3-traveller privacy floor (129) |
| Sidebar | PASS | Today/This-week, saved places (empty adds), language, share row → real share sheet, Settings, Delete (115) |
| Day arc | PASS | Scrub → "≈4.8 µg · 2:00" single ≈; accumulation windows listed (119, 122) |
| Week card | PASS | "≈72 µg this week" == hero; sealed days zeroed (120) |

### a. Delete-my-data completeness — PASS (with notes)
Pre-wipe FS had daylog/ledger/daysum/settings/consent/outbox/places/vehicle/events/contributor/welcome_seen + 5 `.bak` companions (safefile-everywhere confirmed on FS).
Post-wipe FS: **all of the above gone. Zero `.tmp`/`.bak` residue of wiped stores.** Only system files (`profileInstalled`, `mbgl-offline.db` — OSM tile cache, deliberately out of scope) remained.
Re-created within seconds (all *new* writes, verified contents): `daysum.json`+`.bak` (all-zero empty rollup — **no wiped totals**), `alive-cache/` (2 fresh fetch payloads for current cell), `daylog.json`+`.bak` (new samples only — first contained exactly 1 post-wipe sample; 18 wiped samples never returned), `events.json` (fresh `bandIdx:2, grapStage:0` state), `welcome_seen_v1.json`, then `consent.json`/`contributor.txt`/`settings.json`/`places.json`/`outbox.json`/`ledger.json` after re-onboarding.
**Resurrection check**: moved geo fix → sample #2 logged; ledger holds exactly 1 post-wipe trip; search sheet recents empty. Nothing wiped came back. (123–126)
Consent re-arm proven end-to-end: welcome film replayed ("ALIVE — Every Delhi trip has an air price…"), Skip wrote `consent.json {"sharing":"on"}` (matches its copy "Skipping counts as sharing on"), vehicle wizard re-armed.

### b. Air alerts — PASS
Settings → "Air alerts" master + 4 kind rows all render, no truncation at 1080p: "smoke & fires", "air turning worse", "clean windows", "your day on the road" (the new `reflect` kind). Master-off disables all kind switches (enabled=false), settings.json wrote `alerts:false` instantly; each kind off/on wrote `alerts_fires/_band/_windows/_reflect` correctly; back-out + re-enter persisted all. `alerts_reflect` materialized on first write — key absent pre-toggle is fine (default true). (116, 117)
**A real banner fired live**: notification "the air is sitting over the city — barely mixing — 2× stiller than usual; expect the day's smoke to linger" on the air-events channel (stagnation event, ~05:09). (125)

### c. Week-strip daysum parity — PASS
daysum.json: sealed rollups Oct 1–6 all `totalUg/trip_ug/trips/stay_ug = 0, thin` (pre-install days), `dirty: ["2026-10-07"]`. Sidebar "4 trips · ≈4.6 µg / put out ≈0.5 kg" == ledger sum (0.3+1.7+1.1+1.5 = 4.6 µg; 0+0.1+0.2+0.2 = 0.5 kg) — **zero drift**. Home week card "≈72" == hero dose. No parity error.

### d. BandScale — PASS
6-seg strip under hero on home AND on Delhi today; segment 3 solid at ambient ~62–75 µg/m³ (moderate) on both. Correct positional anchor, zero new words. Absent only during an actual API outage window (correct gating on `airNowIdx != null`). (114, 113/121)

### e. "Where to?" 10+ single taps — PASS, kill count 0
12 normal `input tap` cycles on the hero CTA: search sheet opened every time, pid stable (3212), no crash, no wedge. Map-surface header pill single-tap also opens the sheet. (104)

### f. Consent-off pcap — PASS
601 KB capture during search+plan+nav+arrival with `share:false`: **only** `GET /health`, `GET /v2/day`, `GET /aqi`, `GET /grid`, `GET /v2/strip`, `GET /depart`, `GET /reports`, `GET /v2/city`-family + `POST /v2/plan` ×24 + `POST /v2/reroute` ×14. **Zero telemetry/donation POSTs.** Receipt read "kept on this phone only". Outbox stayed `{"items":[],"dropped":0}`.

### g. armed-skip + CTA taps + Hindi — PASS
- Choose-on-map armed hint: tap-to-disarm ✓, BACK-disarm ✓, re-arm ✓; armed map tap commits a real pick ("Bastion at…fort walls") → compare sheet (109–112)
- Vehicle wizard armed-skip: "skip — estimate for vehicles like yours" dismisses the wizard-mounted sheet correctly → compare shows "vehicles like yours", no vehicle.json written ✓ (the audit's dead-row fix holds)
- Footer + header CTAs single-tap: ✓ (12-tap run + map-header pill)
- Hindi flip: full UI localizes ("सुप्रभात · कहाँ जाना है?"), `lang:"hi"` written; flip back → English, `lang:"en"`. English remains install default. (118)

## New-code confirmations
- daysum sealed rollup file real + `.bak` companion; dirty-today recompute live.
- safefile `.bak` companions for daylog/daysum/ledger/places/settings/outbox on FS.
- `alerts_reflect` settings row + key present and functional.
- events engine live-fired a stagnation banner post-wipe with a fresh state file (no seeded baseline needed on a real day).
- press-in draw-hold: no dropped/wedged frames observed during sheet↔map↔nav transitions this drive.

## Errors / notes
| # | Severity | What | Where |
|---|---|---|---|
| 1 | medium | Soft keyboard stays open when a typed search resolves into the plan/compare sheet and the vehicle wizard — it covers the sheet's bottom rows (back/skip/years) and eats those taps until IME dismissed. Recents path unaffected. | Search → pick → wizard |
| 2 | low | Stale last-known position queried at boot: `/v2/day` + `/aqi` fired for `39.237,-123.150` (leftover US coords) before the feed overrode it. | net warmup |
| 3 | low | alive-cache + daysum re-materialize within ~1 s of wipe (fresh fetches/empty rollup — no wiped bytes; flagging the literal FS reading). | settings.ts clearAllData scope |
| 4 | obs | `GET /health` ~1/3 s cadence during drive (100 hits in ~5 min). | net.ts |
| 5 | obs | Post-wipe trip with consent ON: receipt said "saved — will send when back online"; outbox empty seconds later — flushed or dropped unverified. | outbox |
| 6 | carried | Basemap street labels still blank at every zoom — SwiftShader-suspect, unchanged; needs hardware check. | map |
| 7 | obs | Eaten taps persist on emulator (recents row, Start, Skip) — each recovered on retry; consistent with known rig quirk, not a new regression. | global |

**Verdict: PASS — no P0/P1.** Lane C checklist complete on `a5b9c88`.

## v3 verify — IME fix (b12c6b3)

Build: release APK @ `b12c6b3`, fresh bake (`rm -rf app/build/outputs app/build/generated` first — stale-bundle trap observed).
Artifact: `Mobile/android/app/build/outputs/apk/release/app-release.apk` (137,127,164 B) — sha256 `9db1159ccfbb9508fd4d2b9f97590dc1b71b720b32df400379373896715c6474`. **This is the demo-morning artifact.**

**P0 check: keyboard is GONE at every sheet mount — PASS.** `dumpsys input_method` → `mInputShown=false` at each transition; uiautomator dumps show no IME window anywhere below the sheets.

### Typed search → pick → sheet mounts keyboard-free — PASS
- "connaught" typed with IME up (`mInputShown=true`) → result tap → `mInputShown=false`, vehicle wizard mounted clean (130–132). Same for "jantar" (135) and "palika" (no-IME on compare).
- Result rows needed a retap twice — same eaten-tap rig quirk as before, NOT keyboard coverage (IME already confirmed down via dumpsys before the retap). Unchanged rig note.

### Single-tap rows under where the IME used to sit — PASS (one tap each, zero eaten)
- wizard bottom `skip — estimate for vehicles like yours` @y≈2247 → compare sheet (133)
- `car` → Fuel? step; `back` @y≈2248 → step 1; re-enter → `petrol` → year step `2010–2016` → PUC step → `save` @y≈2249 → wizard completes (135–138); `vehicle.json` = `{"cls":"car","fuel":"petrol","year":"y2010_2016","puc":null}` and compare labels the option "· your usual" (139)
- `close` chips + `Start` @y≈2248 → nav HUD in one tap each (140)

### Remind/depart-percent path — wire+code verified, UI row unreachable at drive hour
- Fix confirmed in source: `useShellFlow.remind` now serves `depart.pct_less_vs_now` verbatim to `scheduleDeparture` (was µg→percent recompute, ~2.5× overstate).
- Wire check (GETs only): `/depart` serves `ug_saved_vs_now` and `pct_less_vs_now` as the SAME percent value (e.g. 17/17 on a CP-internal car hop; 0–6 on all long routes at 05:45 IST).
- The `leaveAtBreatheLess` bell row renders only when served saving > 8%: probed 8 destinations × 5 vehicles live — max 6% at drive hour (now is already the cleanest slot ~05:45), so the row correctly did not render. Percent copy sanity: the values it would print are the served percents verbatim — the overstatement is gone at the API contract level.

### Lane C obs #4 recount (lead's question) — APP traffic, not a box artifact
Re-filtered `consent-off.pcap` by emulator src: all app traffic including /health shares `10.0.2.16` (this AVD's slirp guest IP — it took .16, not .15; the earlier zero-count on .15 was my red herring). Inside-guest Linux-cooked capture — host-side curls physically cannot appear on the guest interface, and no /health loop ran on this box (no cron/scripts; box restarted since). Corrected cadence: **49 GETs in 336 s ≈ 1/6.9 s** (not ~1/3 s — earlier count was inflated), timestamps show 15 s spacing with same-second bursts on mount/reconnect — consistent with the app's 15 s ping + offline probe.

### Errors status after this pass
- #1 (medium, IME over sheet rows): **FIXED** on-device at b12c6b3.
- #4 (obs, /health cadence): **revised — app traffic, ~1/6.9 s**, consistent with documented pollers.
- #2/#3/#5/#6/#7: unchanged.

**Verdict: PASS — fix holds.** Shots 130–140.
