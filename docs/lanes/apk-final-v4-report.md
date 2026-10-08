# apk-final-v4 — release build + full-script camera drive (Android/KVM)

Lane: apk-final-v4 · date: 2026-10-08 · rig: fresh Linux KVM child (8c/31GB, /dev/kvm), driven by macOS coordinator session
Build: `base/v2` HEAD = **06919ca** (pulled immediately pre-build; ≥0aad444 ✓)
Independent check: sha256 + both bundle greps re-verified on the coordinator box after download — all match.

## Artifacts
| what | value |
|---|---|
| APK | `alive-06919ca.apk` · 169,337,404 B (~169 MB) — https://app.devin.ai/attachments/e11a5066-d0c1-46fa-b20d-a15c8063d0dc/alive-06919ca.apk |
| APK sha256 | `bdadb36e8c86bacf6c1ddbbf0cdc61c86b1742f186c88c9f8799588170e2b3dc` |
| video | `alive-v4-take.mp4` · 812.5 s · 73.9 MB · h264 1080×2400 (one continuous screenrecord; no 180s cap on this build — single take, no concat) — https://app.devin.ai/attachments/aebb9507-37d0-451a-a61f-df9dab553603/alive-v4-take.mp4 |
| logcat | `drive-v4.logcat` (threadtime, from pre-launch through drive end) — https://app.devin.ai/attachments/3b56789d-51f9-431b-9a95-350412a26b1e/drive-v4.logcat |

## Bake verification (bundle inside the shipped APK)
- `unzip -p apk assets/index.android.bundle | grep -c 'http://65.2.28.40'` → **1** (prod API URL baked ✓)
- dev-URL grep `localhost|10.0.2.2|192.168.` → **1 hit, benign**: `moodCurewell HospitalocalhostRefocusTextInput` (Delhi POI-name concatenation, the documented false friend). Real dev URLs = 0.
- `rm -rf app/build/generated/assets/react` ran pre-build (stale-bundle trap avoided).

## Build
`Mobile`: `npm ci` → `android/local.properties` sdk.dir → `env EXPO_PUBLIC_API_URL=http://65.2.28.40 ./gradlew assembleRelease -x lint -I ../scripts/gradle-init-mirror.gradle` → **BUILD SUCCESSFUL 4m47s**, 395 tasks. Init-script mirrors covered all Maven-Central exposure — no node_modules seds needed this run. Fresh-box toolchain: node v20.19.5 tarball, cmdline-tools, platform-tools, android-36 platform, build-tools 36.0.0, NDK 27.1.12297006, cmake 3.22.1, api-35 google_apis x86_64 image, AVD `demo` (pixel_7). `/dev/kvm` needed `sudo chmod 666` (fresh box, ubuntu not in kvm group). Emulator flags: `-accel on` (37.x rejects `-accel kvm`), `-no-window -no-audio -gpu swiftshader_indirect`.

## Camera take — beat verdicts (video-relative timestamps)
| beat | ts | verdict |
|---|---|---|
| a) cold open → onboarding first, no home flash | 0:07–0:25 | **PASS** — video shows launcher→~3s bare mapTree gate (paper canvas + MapLibre attribution only, zero home sheet/chrome; this IS the designed `introSeen===null` state of the fix)→onboarding slide 1 with live `~65 µg/m³ moderate` already rendered |
| b) consent | 0:27 | **PASS** — Skip on onboarding = consent accept per the on-card disclaimer "Skipping counts as sharing on"; location + notification system dialogs granted |
| c) coach tour once | 1:05 | **PASS** — 5-stop overlay ("the air around you"), skipped; never reappeared |
| d) force-stop relaunch → straight home | 2:24 | **PASS** — home direct, no onboarding/tour replay |
| e) hero live numbers | 2:24+ | **PASS** — `68 µg/m³ moderate`, "read at your location · nearest live monitor ~1 km · air reading: 0 min old"; number ticked 65→67→68 across polls |
| f) air-map tap → readout | 2:47 | **PASS** — "the air map · 52 live stations"; tap → "air at Union Academy Senior Secondary School, New Delhi: 68 µg/m³ — moderate" + locality resolved |
| g) where-to → suggest → route | 4:49 | **PASS** — instant open; "connaught" → real suggestions (Connaught Place 950 m, t0 index live); chooser → Connaught Place fly-to + "air there now ~68"; Directions → vehicle-intro → metro saved → plan: Car(AC) card 2.11 km/≈1 µg/3 min, air-by-hour strip, "tomorrow 7:00 am → ~17% less smoke — ping me"; route painted on map in band amber (uniform moderate field today → honest single band) |
| h) nav counters + park honesty + resume | 5:38 | **PASS** — turn-by-turn ("70 m · Turn left onto Baba Kharak Singh Marg"); moving: breathe 0→≈0.5 µg, dist 2.1→1.6 km; **parked ~35 s → "ride meters paused — still counting the air"**: breathe kept accruing (0.2→0.5 µg), distance froze, ride-exhaust kept counting at ~idle rate (134→155 g ≈ +36 g/min ≈ 2.2 kg CO₂/h idle — plausible, honest); resume → "Bear left onto Outer Circle", counters live |
| i) drawer → Trips → DelhiToday → week | 7:15 | **PASS** — drawer: Today ≈0.7 µg/≈0.2 kg, FSSMTWT week strip (Thu lit), saved places, language toggle; Trips: "estimates — honest ranges, never fake-exact", today row w/ "≈32 µg less than the smokiest way"; DelhiToday: 961 µg city day, PM10 198/NO₂ 31/O₃ 70/CO 935 vs WHO limits, next-12h forecast strip, "last 7 days · 54 trips" mode split (car 80%/bike 6%/other 15%), k≥3 street aggregates |
| j) back×2 → exit toast | 11:07 | **PASS** — "press back again to exit" toast captured; second back → launcher |
| k) airplane mode → offline render | 12:15 | **PASS** — cold relaunch under airplane+wifi-off: home renders from local store (5.5 µg/22 m counted), "can't reach the server — trying again" pill mounted, live "outside" chip honestly absent, no fabricated data; restore → live "outside ~67" returns |
| l) idle soak / zero crash | full 13.5 min | **PASS** — 0 FATAL EXCEPTION, 0 tombstone/SIGSEGV/SIGABRT, `dumpsys activity lastanr` = none since boot |

## Anomalies / notes
1. **First-run OS dialogs split the onboarding arc**: location permission fires mid onboarding→consent; notification permission lands during coach tour. One-time dialogs, normal for fresh install — but on camera the intro sequence is interrupted twice.
2. **Plan option vs My vehicle**: picking "metro" in the vehicle sheet still defaults the plan card to "Car (AC) · least smoky" (ranked by dose). Trip logged as Car(AC). Metro stayed as saved vehicle. If the intent is "my vehicle pre-selects the plan option", this is a UX gap; if ranking-by-dose is the intent, it reads slightly off for a metro owner.
3. `adb uninstall` on never-installed package → DELETE_FAILED_INTERNAL_ERROR (cosmetic; install clean after).
4. Rig quirks hit as documented: `input text` needed EditText focus first (2nd tap); one empty uiautomator dump during tour (probe-level); SwiftShader → no basemap text labels (rig limitation, not app); geo fix needed Maps-launch GNSS wake then propagated to fused within ~60 s.
5. `AndroidRuntime` count 297 in logcat = RuntimeInit spawn noise from each `adb shell`, not crashes.
