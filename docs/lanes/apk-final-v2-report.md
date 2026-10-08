# Lane report — apk-final-v2 (canonical demo binary recut)

## Binary

- **`alive108-b1421d0.apk`** — 166,577,860 B
- **sha256** `935aec32cc06d76400391af6f62dd0ca6c2562572e877361139358be63beac73`
- **link** https://app.devin.ai/attachments/72b4a650-90be-497b-b5c9-7458ecc00a82/alive108-b1421d0.apk
- built from `base/v2` @ `b1421d0` (HEAD at build time == origin). HEAD drifted to `34568a0` during the drive — diff is docs + 2 lines of `server/landing.html`, zero `Mobile/` changes, so the binary is app-identical to current HEAD.
- `BUILD SUCCESSFUL` in 4m58s, `./gradlew assembleRelease -x lint`, `EXPO_PUBLIC_API_URL=http://65.2.28.40`
- bake verified: bundle contains `http://65.2.28.40` ×1; the single `localhost` hit is a `SchoolocalhostRefocus` data substring, benign
- patch-package applied all 3 patches cleanly this run (verified `targetEnvironment(simulator)` / `TARGET_OS_SIMULATOR` / `deferJsi` markers in node_modules — no manual `patch -p1` needed)
- maven armor all applied: foojay-resolver stripped, `mavenCentral()` → googleapis mirror in 19 node_modules gradle files, `scripts/gradle-init-mirror.gradle` in `~/.gradle/init.d/`, expo-module-gradle-plugin settings.gradle.kts written. Zero 429s.

## Rig

linux box, /dev/kvm present, AVD `demo` (pixel_7, android-35, google_apis, x86_64), `-no-window -gpu swiftshader_indirect -no-snapshot-load -memory 1536`. package `com.anonymous.app`, 1080×2400. GNSS recipe per scroll-hammer report (adb root → grant Maps fine location → launch Maps once → `emu geo fix`).

## Drive verdicts

| check | verdict | evidence |
|---|---|---|
| cold open TTI | PASS — ~643–864 ms cold (post `pm clear`), 376–494 ms warm | `am start` + window-focus timing |
| home live numbers + caption | PASS — live field numbers, caption "read near New Delhi" after GNSS kick | drive-02 screenshot |
| onboarding fresh install (5 beats) | PASS — all 5 beats render + advance, consent persisted | drive-03..07 screenshots, consent.json `{"seen":true,"sharing":"on"}` |
| search raw phrases | PASS — `connaught`, `ashok nagar`, `bakery near mandir` all resolve to real NCR places | drive-08..10 screenshots, places.json recents w/ lat/lon |
| plan → chooser settle | PASS — CP→India Gate 23 options; CP→Karol Bagh chooser w/ "least smoky · lightest for you" | drive-11..14, drive-33/34 screenshots; prod POST /v2/plan 200 |
| settings toggles persist | PASS — settings.json round-trips all keys; `show_cig` visibly changes nav copy to "a trace of a cigarette" | settings.json, drive-35/36 nav screenshots |
| scroll home 30s | PASS — no yank | earlier scroll pass this session |
| nav-gap honesty #1 (park→auto-arrive) | PASS — parked ~90 s mid-trip → receipt billed 2 min drive / 0.6 km / 227 g (+4 g only across parked window) | drive-20 receipt screenshot, ledger.json |
| nav-gap honesty #2 (mid-route park) | PASS — ride emissions 276→282 g (+6 g) across ~2 min parked, UI shows "paused ~2 min", distance-left unchanged 2.8 km. Parked time NOT billed as driven | drive-35 vs drive-36 screenshots |
| offline pack → airplane map | PASS — region `delhi-ncr-z9-13-r2` self-downloaded (744 region tiles, 758 total, 297 resources); airplane-mode cold relaunch renders full basemap + honest "offline — showing last known air" copy | sqlite query of pulled mbgl-offline.db, drive-31/32 screenshots |
| zero crashes | PASS — logcat crash buffer empty, no tombstones, through full drive incl. airplane toggles | logcat -b crash, /data/tombstones |

## Notes for future rigs

- **`from`-poisoning trap**: `posNow()` (`src/components/shell/net.ts`) takes an unguarded fresh fix; on an emulator whose default location is outside NCR, the first fix becomes `from` verbatim and `closeCompareToHome` never clears it — every plan then fails `outside_service_area` even with an in-NCR destination. Real phones can't teleport MV→Delhi, so this is a rig artifact, not a user-facing bug. Workaround: `emu geo fix` into NCR BEFORE the first plan; if stuck, `pm clear`/force-stop resets `from`.
- uiautomator dumps go stale on the live nav screen (constant animation → no idle state) and can wedge entirely; screenshots are ground truth during nav.
- `Finding a new way…` toast + "paused ~N min" status are the honest-degrade surfaces doing their job.

## Deliverable

Canonical demo binary for this wave: **alive108-b1421d0.apk**, sha256 `935aec32cc06d76400391af6f62dd0ca6c2562572e877361139358be63beac73`, link above. Supersedes `alive108-c9a298c.apk` (pre-onboarding/nav-gap/android-taste).
