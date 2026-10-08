# apk-final-v5 — release builds + full-script camera drive (Android)

Lane: apk-final-v5 · date: 2026-10-08 · rig: Linux KVM child for the film (`devin-cbdb2561…`), macOS box as builder/coordinator
Build: `base/v2` HEAD = **270be81** — post-gate: scorer `8b62cdc` + home-polish `52ee286` + stays+playtime `c5ba61c` + routes-delta `96df587` + deploy-24 `270be81` (all verified ancestors pre-build)
Wait-gate: all 4 lane commits landed before the 90 min timeout — no timeout fallback. Anchor baseline was `8973d86`; gate counted only commits after it.

## Artifacts
| what | value |
|---|---|
| APK (release candidate, real devices) | `alive-270be81-arm64.apk` · 108,702,319 B (~108.7 MB) — **arm64-v8a only** — https://app.devin.ai/attachments/d030782b-a478-4fe9-bb8f-0912888bab97/alive-270be81-arm64.apk |
| APK (universal fallback, incl. x86 emulators) | `alive-270be81-universal.apk` · 189,252,976 B (~189.3 MB) — 4 ABIs — https://app.devin.ai/attachments/bd4aa94a-ed39-4835-af53-02c5ac91a0f2/alive-270be81-universal.apk |
| arm64 sha256 | `dcf7a9e8b10ac6c5de1516bf92c6aaad8e95c27e9c10ebe8915b4d307a655957` |
| universal sha256 | `3ac840ac2b4c2c7548c1c0d6654e5fa201854db04fac4739e2723e65fe7e0aba` |
| video (main take) | `v5.mp4` · 898.5 s · 92.9 MB · h264 1080×2400, one continuous screenrecord — https://app.devin.ai/attachments/1653d8a8-c80d-4bb7-a266-52f0e780da3b/v5.mp4 |
| video (supplement) | `v5-o.mp4` · 28.8 s · 9.4 MB — exit-toast beat overflowed the 900 s screenrecord cap; same session continuity — https://app.devin.ai/attachments/5512c97e-3f05-4f1e-b3b2-f84ee2035750/v5-o.mp4 |
| logcat | `drive-v5.logcat` · 24,489 lines threadtime, pre-launch → end — https://app.devin.ai/attachments/32950f77-7cb7-47bd-af45-b2aee75ca4f7/drive-v5.logcat |

## Bake verification (bundle inside the shipped APKs — independently re-checked on the coordinator box)
- arm64 `unzip -p assets/index.android.bundle | grep -c 'http://65.2.28.40'` → **1** ✓ (prod API baked); universal → **1** ✓
- dev-URL grep `localhost|10.0.2.2|192.168.` → **1 hit, benign**: `…arathi HS SchoolocalhostNutan Pustak Bhandar…` — gazetteer POI-name concatenation (same documented false-friend class as v4's `moodCurewell Hospitalocalhost…`; corpus rows changed, pattern identical). Real dev URLs = 0.
- ABI check arm64: 18 `lib/arm64-v8a/` entries, 0 `lib/x86*`/`lib/armeabi*` — true arm64-only.
- ABI check universal: 18 libs × {arm64-v8a, x86_64, armeabi-v7a, x86}.
- Badging: `com.anonymous.app` v1.0.0 (code 1), minSdk 24, targetSdk/compileSdk 36, label `Alive`.
- `rm -rf app/build/generated/assets/react` pre-build (stale-bundle trap avoided). Build host: this macOS arm64 box, fresh SDK provision (cmdline-tools + platform-tools 37.0.1 + android-36 + build-tools 36.0.0 + NDK 27.1.12297006 + cmake 3.22.1). `npm ci` clean — 3 patch-package patches applied, t0 index rebuilt (210k rows, 62 chunks). arm64 `assembleRelease` **4m42s** (383 tasks), universal **+1m28s** (bundle up-to-date from arm64 pass; same tree, identical prod bake verified on both outputs).
- Server-side cross-check from coordinator: `/v2/search?q=chandni chowk` → real Chandni Chowk entities top-ranked; `q=atm near cp` → compound ATM rows near CP; `/v2/stays` + `/v2/playtime` live on prod (:231, build_sha `c5ba61c0`).

## Camera take — beat verdicts (video-relative timestamps; film ran **universal** on x86_64 KVM AVD — arm64 is the device twin)
Rig: AVD `demo` pixel_7, Android 15 google_apis x86_64, `-accel on` (KVM verified), headless SwiftShader.

| beat | ts | verdict | evidence |
|---|---|---|---|
| a) cold open → onboarding first, no home flash | 0:11–0:23 | **PASS** | onboarding card "You can't see it…" + live ~76 µg/m³ for delhi; no home chrome flash |
| b) consent/skip + permission dialogs | 0:41 | **PASS** | Skip → location granted 0:44; notif dialog queued to post-onboarding relaunch (1:48→granted 2:04); card "Skipping counts as sharing on" |
| c) coach tour once | 0:51–1:32 | **PASS** | 3 stops shown, skipped 1:32, never replays |
| d) force-stop relaunch → home | 1:38–2:04 | **PASS** | straight home, zero onboarding/tour replay |
| e) hero numeral live | 0:46→ | **PASS** | 76 µg/m³ · moderate · 5.0× WHO · "air reading 9→10→11 min old" ticking; honest "location is off or hasn't locked yet" pre-GPS-lock |
| f) air-map tap → readout | 3:15, 11:53 | **PASS** | "the air map · 54 live stations" → "75 µg/m³ — moderate · Sector 4", later "Unistar BNB"; staleness chip "18 min — reconnecting" → refreshed "5 min old" on camera |
| g) search 'chandni chowk' — scorer fix | 4:14–4:30 | **PASS** | canonical entities (road·Shahjahanabad, market·Chawri Bazaar, metro, Lok Sabha) all outrank partials; `chandnichowk` concat → literal-name POI then canonical — correct scorer |
| h) search 'atm near cp' — regression fix | 4:48 | **PASS** | SBI/Axis/ICICI/Citibank ATMs all "· Connaught Place" — compound parse resolved |
| i) where-to → chooser delta headline → band route | 5:02–7:27 | **PASS** | CP card "air there now ~75" → Directions → options with delta copy: "+1 µg more than car", "windows down +3", "bike ~2.1× more inhaled", "Within ~10% of the lightest dose", "tomorrow 6:00 am → ~17% less smoke — ping me"; air-by-hour ~2.5 µg; route painted |
| j) stays list ranked by least pollution (feature 2) | 9:50–10:33 | **PASS** | "hotels near karol bagh" → "air answers" → "stays" sheet: ranked hotels "~110 µg · 16 µg heavier" chips → row → map pin live read at Karol Bagh |
| k) playtime verdict + 24h curve (feature 3) | 10:54–11:23 | **PASS** | "when to play" → "when to go out": verdict "no clean stretch — lightest 62", 24-band curve w/ now marker, "24h avg ~97", "heaviest 19:30 ~156", "before ~19:30 IST" |
| l) nav counters + park honesty + resume | 7:45–9:18 | **PASS** | turn-by-turn + breathe/ride counters; 30s parked → "ride meters paused — still counting the air" (0→0.4 µg, 12→35 g); GPS relock + reroute 1.5 km; exit honesty "under 100m — nothing counted" |
| m) drawer → Trips → DelhiToday → week | 12:12–13:14 | **PASS** | drawer today ≈0.7 µg/0.2 kg + week strip; Trips "honest ranges" + "≈106 µg less than the smokiest way"; DelhiToday 1298 µg poor, pollutants vs WHO, "17% below 10-yr avg", 12h forecast |
| n) settings | 13:33 | **PASS** | Language EN\|हिंदी toggle, anonymous-share toggle, Settings row, How ALive works |
| o) back×2 → exit toast | take-2 ~7–10s | **PASS** | "press back again to exit" → launcher (`v5-o.mp4`; main take hit the 900 s cap before this beat) |
| p) airplane → offline render → restore | 14:05–14:52 | **PARTIAL** | airplane+wifi off → cold relaunch renders full home from store (dose + cached context, no fabricated outside line, ✈ status icon) → radios back → "outside ~75 µg/m³" restored on camera. The "can't reach the server" pill did not appear in captured frames — transient or below fold; offline honesty itself confirmed |
| q) idle soak / zero crash | whole take | **PASS** | 0 FATAL EXCEPTION / tombstone / SIGSEGV in 24,489 logcat lines (independently re-grepped on coordinator); `dumpsys activity lastanr` = none since boot |

## Anomalies / notes
1. Emulator fused GPS held ProviderRequest OFF until nav forced a fix — app honestly degraded "couldn't get your location — type a place", then locked + blue dot + rerouted on camera. Rig-side GNSS quirk, app behaved honestly.
2. `input text` drops spaces in RN fields → typed via KEYCODE_SPACE; the "chandnichowk" frame at 4:09 is that artifact (incidentally proves literal-name scoring).
3. Notification permission queued to post-onboarding relaunch rather than first dialog pass — one-time OS dialog ordering, matches v4 note.
4. SwiftShader → no basemap text labels (rig limitation, not app).
5. Beat o spilled past the 900 s screenrecord cap → `v5-o.mp4` supplement, same session continuity.
6. Drive facts: streamed install 1.68 s (189,252,976 B), cold launch T+11 s, onboarding painted ≈T+16–23 s.
