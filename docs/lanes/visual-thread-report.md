# Visual thread — every surface open + recorded (iOS sim + web + Android emu)

- Repo `<owner>/Delhi-Air-108`, branch `base/v2` @ `a09411b` (post plain-words pass).
- Lanes: iOS drive on this macOS box (iPhone 17 sim, iOS 26.5, `com.anonymous.app`, Debug build from source — contains the SIGSEGV cold-fix); web drive via headless-Chrome CDP rig at 390px + 1440px; Android drive on a Linux/KVM child session (devin-34e11ab2) with the release APK.
- Prod: `http://alive108-2699c171ddded465.elb.ap-south-1.amazonaws.com` (app uses baked `http://65.2.28.40`). GET-only discipline held everywhere; app's own `POST /v2/plan` is legitimate product traffic.
- Media index: iOS stills `ios-drive/NN-*.png` (33), web stills `drive-web/shots/<surface>-<390|desk>-NN.png` (~90 + innerText dumps), videos `ios-drive/seg*-*.mp4` + `web-video/<surface>-scroll.mp4`. Android lane media lives on the child session's attachments (filenames prefixed `android-`).

## Verdict

**iOS: full journey works end-to-end on live prod data — zero crashes, zero SIGSEGV.** The cold-fix holds. Home hero self-updates (55→57→61→64→63 µg/m³ across 15 min), dose counter transitions "count starts…" → real "8 µg · 12m counted" ledger mid-drive, search→compare→depart→settings→community all verified.

**Web: all 4 surfaces live.** Landing `/` was captured BROKEN mid-drive (unescaped `'` in `map's` at landing.html:1292, from `326e64e` → dead boot overlay); diagnosed and alerted in-chat, a sibling lane shipped `f9ea5ae` + deploy `adff31e` within the hour, and re-drive verifies the hero painting live (49.2 µg/m³, 53 stations, 903K segments). `/city`, `/community`, `/admin` (guest) all populate live numbers.

**Android: driven by Linux child `devin-34e11ab2`** — see "Android lane" below (report merged from child evidence).

## iOS beat-by-beat

| Beat | Result | Evidence |
|---|---|---|
| Cold open (timed) | Works — bundle served via Metro dev-client in ~10.9 s, first frame ~0.8 s after launch; relaunch after sim reboot straight to home (state persisted). | 01-launch, 26-relaunch |
| Welcome film | Works — cinematic: digit-rain "reading Delhi's air…" → live city reading "49.2 µg/m³ · PM2.5 · SATISFACTORY · live — the ncr-wide average" → "then — what you breathe"; Skip button present; ~4 s auto-exit. Replays only on first open (welcome_seen_v1.json gate — verified: deleting it replays the film). | 31–33, seg2-welcome.mp4 |
| Onboarding + consent | Works — 3 pages ("Every Delhi trip has an air price" → "Nothing personal is stored" → choice). Both consent buttons render; chose share-ON for the drive. | 02–04 |
| Home live numbers | Works — hero `the air around you` 55→64 µg/m³ drifting live, band flips satisfactory→moderate; "the move" least-bad-hours strip recomputes on location change; "air reading: N min old" freshness ticks. | 05, 23, 29 |
| Dose ledger | Works — after ~10 min at the injected fix, hero switches to `you've breathed today` 8 µg good / 4% of 216 µg budget with "where it accumulated" time windows (01:00–01:09 ≈5.5, 00:56–01:00 ≈2.5) and week ≈8 µg. Self-updating. | 26, 29 |
| Search sheet | Works — open/close clean; typed query geo-ranks 11–13 results with distances; Recent row persists + re-ranks against new fix ("Connaught Place 7.1 km" after relocate vs "50 m" stale origin). | 07, 08, 10 |
| Plan → compare | Works for real trips. India Gate at 50 m returned honest all-≈0 "what's live" fallback (degenerate but correct for a 50 m trip — not a bug, see errors). Connaught Place 7.1 km straight-line → 8.72 km road route: Car(AC) least-smoky ≈4 µg, 3 alternates via Mahatma Gandhi Marg → AIIMS Flyover, windows-down ≈7, bike ≈9, on-foot ≈39–47; Bus 894CL with real stop names (Baroda House→Scindia House). 22 option rows. | 09b, 14, 27 |
| Vehicle flow | Works — first-compare prompt "your pick sharpens the numbers — saved on this phone only" → mode (auto) → BS-era age (2021+ BS-VI) → optional PUC CO%/HC ppm — then "2021 or later auto" chip persists and "your usual" tag lands on auto rows. | 11–13 |
| Depart curve | Works — 24-bar dose-by-hour graph, marker readout "now·00:00 ≈1 µg" → "+12h·12:00 ≈2 µg" live on chip press; chips now..+23h. | 14, 15 |
| Settings | Works — vehicle row, EN/हिंदी radios, Voice on, cigarette-comparison off-by-default ("your dose stays in µg"), km metric-only. | 17 |
| Air alerts | Works — master "Air alerts" ON + kinds: morning air alert (off), smoke & fires, air turning worse, clean windows, your day on the road — each with real copy ("burn belt northwest of Delhi"). Leave-later reminders ON. | 18, 19 |
| Community / donate-off | Works + proven on disk — toggled Share-anonymous OFF → consent.json `{"seen":true,"sharing":"off"}` + settings.json `"share":false`; **no outbox/upload-queue file exists anywhere in the container**. Sub-copy flips to "off = nothing is uploaded; your own stats still work on this phone". | 20, 21 |
| Week strip | Works — "your week ≈2.5 µg" 7-chip strip (today highlighted) + "the days ahead" 5-day forecast (69/104/161/138/126, today least-bad, honest "(only its first ~11h fall inside the forecast)"). | 22 |
| Delhi today | Works — 709 µg city dose, pollutant table (PM10 170.8/WHO 45, NO₂ 13.8, O₃ 132, CO 724.1, SO₂ 16.5, US AQI 109) "measured every 15 min · updated 2 min ago", next-12h strip, **"streets travellers crossed"** = live community data (Hanuman Lane 16 trips heavier, Moti 11, Motilal Nehru Marg lighter…). | 24, 25 |
| Air map | Works — fullscreen Delhi map with real street labels (Nizamuddin, Hauz Khas, Safdarjung…), "your day so far ≈8 µg" live card, layers/locate FABs. | 28 |
| Your trips | Works — honest empty state "no trips yet — finish a trip and its smoke numbers land here · trips stay on your phone". | 30 |
| SIGSEGV oracle | **Zero crashes.** No DiagnosticReports entries for the app across the whole drive; process stayed one PID per session; sim log shows no SIGSEGV. Fix holds on RN-from-source Debug build. | — |

## iOS errors / honest flaws

| # | What | Severity |
|---|---|---|
| 1 | 50-m trip renders compare rows as "0 km · ≈0 µg" with "least smoky picks unavailable" — *technically correct* for a sub-block trip but reads like a broken plan; a "too close to need a ride" state would be kinder. | low |
| 2 | Offscreen-row presses get eaten while the sheet scrolls them into view ("go somewhere", "Delhi today" each needed 2 presses once). Consistent with the Android lane's eaten-taps note — likely RN touch flake, not app logic. | low |
| 3 | Compare sheet sits at one detent; no expand handle worked — full mode list reachable only by scrolling the inner list. | nit |
| 4 | `Recent` distances show the origin at query time and re-rank on the *next* query — a stale-distance blink is possible right after relocating. | nit |

## Web beat-by-beat (390px + 1440px, headless Chrome CDP)

| Surface | Result | Evidence |
|---|---|---|
| `/` landing | **Was BROKEN mid-drive → FIXED + re-verified live.** Dead-state capture: `Uncaught SyntaxError` at served 1292:52 (`map's` unescaped in single-quoted string, from `326e64e`) → boot overlay never dismissed, all landing JS dead. Fix `map\'s` shipped by sibling lane `f9ea5ae`/`adff31e`; re-drive at `?v=fix1` (cache-busted): script parses clean, page paints 3745 px — hero 49.2 µg/m³ SATISFACTORY · 2.2 cig · 53 stations · 12 min fresh · wind · 903K segments. | dead: landing-390-dead, landing-desk-dead + scroll videos; healed: landing-fixed-00..05 + text dump |
| `/city` | Works, live — "Delhi NCR air, right now": 51 µg/m³ SATISFACTORY AQI 86, across-map 28.3–72.1, 29 districts live, easiest Hapur 71 / heaviest North Delhi 121, WHY TONIGHT ("barely moving"), GRAP badge (below stage I, "computed here"), district choropleth with wind 4 km/h S. Renders identically at 390px (nav collapses correctly). | city-390-00..09, city-desk-00..05, both scroll mp4s |
| `/community` | Works, live — "What Delhi breathed together — merged, never named": **24 phones sharing, 44 trips all-time, 31.4 km today, 1,279 µg dodged, last shared 55 min ago**; three-rule proof cards (300 m on-device trim / merged-never-filed / 3-phones-to-appear); live rider flags + mode mix. | community-390-*, community-desk-*, scroll mp4s |
| `/admin` guest | Works, live — ops truth panel: 51.4 µg/m³ over 25 sampled cells (median 52.2, worst 67.4), "32% below typical oct day", wind 3.6 km/h/174°; map-is-live card (rebuilt 7 m ago, 53 govt feeds, 101 map points, **9,03,058 streets priced**, 44 fires / 12 in belt, next rebuild 8 m); health cards incl. 8.8 µg/m³ honesty score. Guest-locks operator internals. | admin-390-*, admin-desk-*, scroll mp4s |

## Android lane

Driven on Linux KVM child session `devin-34e11ab22363411586ce442b5970db8c` (Pixel 7 AVD, Android 35, swiftshader_indirect, geo test-provider). APK under test: `alive108-70914c0.apk` (sha256-verified @ 8dc2068). A HEAD rebuild (`app-release.apk` @ `a09411b`, 137 MB, debug-signed, bundle verified containing `http://65.2.28.40`) was built on this box and shipped to the child mid-drive — it arrived after beat 8 so the drive finished on 70914c0; the only delta between builds is the `326e64e` copy pass (strings.ts). Child's beat table + media merged below.

### Beat-by-beat (child drive, `alive108-70914c0.apk` @ 8dc2068 — pre-copy-pass build; the HEAD rebuild `a09411b` arrived mid-drive after beat 8 and was not swapped per instruction)

| # | Beat | Result | Evidence |
|---|---|---|---|
| 1 | install + cold open | ✅ ~2–3 s launch→interactive; live numbers painted by ~t3 s | 01-launch-t1s..t10s |
| 2 | welcome film | ✅ ≤4.4 s auto-exit; "51.4 µg/m³ PM2.5 SATISFACTORY · live · field mean over the ncr lattice" | 11-film-*, 12-film-*, 13 |
| 3 | onboarding/consent | ✅ 3 panes + consent card (OS notif dialog ordering captured honestly) | 03–08, 10 |
| 4 | home live numbers | ✅ hero 35 µg/m³ moderate 4.1×WHO → 66 over session; freshness chip ticks | 09, 19 |
| 5 | search | ✅ `india gate` + `lotus temple` geo-ranked w/ distances; sheet open/close smooth | 14–18, 20, 23 |
| 6 | plan + compare | ✅ IG→CP; vehicle picker; mode rail; "least smoky way" verdicts; two polylines | 24–29 |
| 7 | depart curve | ✅ +4h/+14h scrubs re-quoted ≈1 µg; hour arc live | 30–32 |
| 8 | nav trip → arrival | ✅ full trip — HUD live mid-drive, "Finding a new way…" reroute chip on off-path fixes, "You're here." receipt ≈1.2 µg breathed / ≈0.6 kg out / "kept on this phone only" | 33–37b, seg1.mp4 (170 s), seg2.mp4 (119 s) |
| 9 | settings + air alerts | ✅ vehicle row, EN→हिंदी full-home flip→restore, alerts master + 4 kinds all present and matching settings.json | 38–48 |
| 10 | week + forecast | ✅ "your week" 7-chip (today ≈15 µg), 5-day ahead (71→124), check-in | 49, 50 |
| 11 | consent-off | ✅ consent.json `sharing:"off"` on disk; `outbox.json` never created; receipt "kept on this phone only"; ledger "trips stay on your phone" | 35, 59 + adb cat |
| 12 | Delhi today | ✅ 707 µg city dose, PM10 172.1 / NO₂ 13.7 / O₃ 131 / CO 730.8 / SO₂ 16.3 / US AQI 109, next-12h, streets-crossed community list | 51–55 |
| + | sidebar / air map / trips ledger | ✅ bonus surfaces all rendered | 38, 39, 56–59 |

On-disk verification: `daylog.json` holds 7 breathing-zone samples along injected coords (amb 54.7→65.8); `ledger.json` `{vehicle:"car", dose_ug:1.2, avoided_ug:46, emit_kg:0.6, …, to:"Connaught Place"}`; settings.json matches every UI toggle 1:1. Zero FATAL/SIGSEGV/ANR lines in logcat across the session.

### Android honest flaws (child's own words)

1. OS notif-permission dialog interrupts the welcome film on first boot (~3–4 s, film plays under it); reproducible, film re-captured via welcome_seen_v1 reset.
2. That dialog ignores injected taps (separate window) — needed `pm grant POST_NOTIFICATIONS`; a real finger works fine (automation-only limitation).
3. Eaten taps throughout on the release build (2-px micro-swipe or retry needed) — same flake family as iOS #2.
4. "Finding a new way…" mid-nav re-plans when injected fixes stray off the snapped route — legitimate reroute behavior on camera.
5. fused provider dropped fixes mid-feed; gps provider held (re-injection cadence note).
6. Trip clock compressed (137 fixes in ~3 min → "3 min" durations) — feed artifact, arrival math correct.
7. Origin pin is sticky — first fix pins `from`; an IG→IG 0 km plan was correctly degenerate (same family as iOS #1).
8. `streets travellers crossed` counts real community trips from other devices even with own sharing off — correct, but worth noting for privacy review.
9. Settings list lazy-a11y drops offscreen rows from uiautomator — scripting note only.

Media: 76 screenshots + 2 screenrecord mp4s attached to child session `devin-34e11ab2` (all re-attached to the parent report message with `android-` context names).

## Cross-cutting notes

- Cold-open timing on iOS is Metro-bundle-bound (dev-client); a real installable .ipa cold open is comparable to the Android number — do not read the 10.9 s as shipped-app cold start.
- Map labels render on iOS sim; Android emulator still can't render them (SwiftShader SDF-glyph quirk — needs one physical-device check, unchanged from android-drive-report).
- Prod is honest under both apps: identical field (49–64 µg/m³ band moderate/satisfactory), same streets list, same forecast numbers as /city at the same minute — the apps and the site read one engine.
