# apk-final-v3 lane report — `alive-63b7ed4.apk` on KVM emulator

- **Build sha:** `63b7ed4` (base/v2 HEAD after rename-alive landed via `0c5f9cc`)
- **APK:** `alive-63b7ed4.apk` — **169,315,792 bytes**, sha256 `4fe61126c9f4af4413aad1beaf620f12d023686a1ab2a03f71098282abed36f0`
- **Rig:** AVD `demo` (pixel_7, android-35 google_apis x86_64, 1080×2400) on `/dev/kvm`, `swiftshader_indirect`, `-no-snapshot -no-audio`. Package `com.anonymous.app`.
- **Method:** exact recipe from `apk-recut-report.md` (npm ci → strip foojay-resolver → maven mirrors + `Mobile/scripts/gradle-init-mirror.gradle` → `rm -rf app/build/generated/assets/react` → `EXPO_PUBLIC_API_URL=http://65.2.28.40 ./gradlew assembleRelease -x lint`).
- **Bake-verify:** prod API `http://65.2.28.40` ×1 in `assets/index.android.bundle`; zero `localhost`/`10.0.2.2` matches except the benign minified token `HospitalocalhostRefocusTextInput` ×1.

## Per-beat results — all 14 PASS

| # | Beat | Result | Evidence (video seg@time / shot) |
|---|------|--------|----------------------------------|
| 1 | Cold open timing | PASS — WaitTime **743ms** fresh install; warm relaunch 636ms | seg1@0:00 / `01-cold.png` |
| 2 | 5-beat onboarding | PASS — all 5 beats render + advance | seg1@0:40 / `02-onb-2.png`, `02-onb-5.png` |
| 3 | Coach tour once, skip persists | PASS — spotlights at real components (home dose card, Where-to); skip → never re-shows (verified across relaunch + pm-clear-free navigation; `coach_tour_seen_v1.json` written) | seg1@1:10 / `07-tour-2.png`, `08-tour-3.png` |
| 4 | Home live numbers + locality + honest ambient | PASS — `7.7 good`, `4% of your daily limit`, `11m counted`, `outside ~59 µg/m³ · satisfactory`, "in Delhi's air right now" + Connaught Place caption | seg1@1:40 / `11-home-final.png` |
| 5 | Branding 'Alive', zero visible '108' | PASS — OS dialogs ("Allow Alive to send you notifications?", "…access this device's location?"), drawer wordmark `ALIVE`, share text — no '108' anywhere driven | seg1@0:55 / `05-loc-dialog.png`, `27-drawer-2.png` |
| 6 | Air-map tap → band pin + `N µg/m³ — band · locality` | PASS | seg3@2:05 / `13-airmap-tap.png` |
| 7 | Raw-phrase search ×3 | PASS — `ashook nagar shadara gali no 4`, `pawan bakery near hanuman mandir`, `nandanagri a block` all resolve to results | seg4@0:30–1:30 / `15/16/17-search-*.png` |
| 8 | Chooser settle | PASS — chooser animation settles to selection | seg4@1:45 / `19-chooser-settled.png` |
| 9 | Parked-time honesty | PASS — "ride meters paused ~5 min — the air count kept going"; receipt `3.2µg / 704g / 3.1km / 8min` | seg2@0:35 / `21-parked.png`, `23-receipt.png` |
| 10 | Drawer + settings | PASS — hamburger retap needed once (known gotcha), drawer + settings render | seg5@0:20 / `27-drawer-2.png`, `28-settings.png`, `39-settings-v2.png` |
| 11 | Trips empty on fresh install | PASS — honest empty state | seg5@1:00 / `32-trips-empty.png` |
| 12 | DelhiToday honest-empty | PASS | seg5@1:10 / `33-dt-empty.png` |
| 13 | Offline pack → airplane → cold relaunch full basemap | PASS — `region_tiles=744, regions=1, region_resources=297` for `delhi-ncr-z9-13-r2` (verified in `mbgl-offline.db` twice, incl. post-`pm clear` re-download); airplane relaunch renders full basemap + honest "offline — showing last known air" + "can't reach the server — trying again" pill | seg3@0:40 / `34/35/36-offline-*.png` |
| 14 | 6-min soak | PASS — `FATAL EXCEPTION|SIGSEGV|SIGABRT|ANR` grep = **0**, crash buffer empty, `lastanr` none | seg3 (full) |

## Honest degradations

- None crash-level. Noted nits: drawer hamburger occasionally eats first tap (retap works — known emulator gotcha); eaten taps required coordinate taps in a few spots; no basemap text labels under SwiftShader (emulator rendering limit, not an app bug).

## Evidence inventory

- Video: `seg1.mp4` (169s — cold open/onboarding/tour/home), `seg2.mp4` (174s — nav/parked/receipt), `seg3.mp4` (173s — soak + air-map + offline), `seg4.mp4` (175s — searches + chooser re-drive), `seg5.mp4` (132s — drawer/settings re-drive).
- 39 screencaps `01-cold.png` … `39-settings-v2.png` + `emulator.log`.
