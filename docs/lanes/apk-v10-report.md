# Lane report: apk-v10 — design-v4 + fix-wave demo binary @ 70914c0

**Date:** 2026-10-07 · **Verdict: BUILT + emulator-verified end-to-end (all drive steps PASS, 0 crashes)**
Build host: macOS box (compile lane). Emulator drive: **Linux KVM child lane**
(this macOS box is a nested VM — `kern.hv_support=0`, no HVF; raw QEMU TCG ran but
could not keep `system_server` alive under watchdog — see "macOS rig notes").

## Binary — FINAL (the one the owner installs)

- **URL:** https://app.devin.ai/attachments/af6f554d-b7c2-4e4e-a24b-9c17b1738df4/alive108-70914c0.apk
- **SHA:** `70914c0` — base/v2 product tip at build time. Includes design-v4
  (8c7ad97/31dbfdb/823323e), events→notification engine (4d20990/8346460),
  fix-mobile i18n + outbox-wipe + Skip-disclosure (832e7fa/1afccd8/92d58a6),
  SIGSEGV fixes (d45a55c mount-vs-draw throttle + 3c24a5e cold-launch
  jsi-destruction defer + GC sizing + boot-watch), android-drive fixes
  (c84b5c2 phantom re-plan/≈≈/exhaust-no-GNSS, 344b4a9 'Where to?' pill yield,
  0a68601 search distKm guard, 8e21de2 basemap-labels classified upstream
  maplibre-native#3648), pentest batch (aea1c68 rate-limiter socket-peer +
  stored-XSS + release-log gate), stale-NCR fix (c0d200c), lazy gazetteer
  postings (822949b), admin /v2/usage (16d3764 etc.), deadcode drops.
- **Size:** 137,120,268 B (130.8 MiB)
- **sha256:** `bfceaf26ad8f410d3995c473e77d14efd950e7ee1b610a20f7fa66849f41e88f`
  (re-verified byte-identical on the drive lane's box)
- **Superseded:** `alive108-e925451.apk` (`3c0cc336…d0e1bf`) and
  `alive108-aee635e.apk` (`c6889e31…e57239a`) — both built this session before
  HEAD moved again; do not install. Earlier `alive108-c3bb731.apk` also superseded.
- **Badging:** `com.anonymous.app` · versionCode 1 · versionName 1.0.0 ·
  targetSdk 36 · launcher label `ALive·108` · `usesCleartextTraffic=true`.

## Prod endpoint baked in

`unzip -p app-release.apk assets/index.android.bundle | grep`:
`http://65.2.28.40` — **exactly 1 hit**, bare host, port 80.
`localhost:8000` / `10.0.2.2` / `:808x` — **0 hits**.
(`EXPO_PUBLIC_API_URL` must be in the environment when Metro bundles; first
rebuild silently folded it out → bundle had 0 ELB hits. Rebaked with
`env EXPO_PUBLIC_API_URL=http://65.2.28.40 ./gradlew assembleRelease` after
deleting `generated/assets/react/release/index.android.bundle` so the bundle
task re-ran. Watch for this on the next lane — Gradle doesn't track env as a
task input.)

## Gates

`npx tsc --noEmit` clean · `npx expo lint` clean — both at 70914c0.
No product code modified; local-only build config (`android/local.properties`
sdk.dir, `~/.gradle/init.d/mirror.gradle` Maven-Central 429 workaround,
foojay line stripped from `@react-native/gradle-plugin` settings.gradle.kts).

## Drive verdicts (Linux KVM lane, `demo` AVD pixel_7 android-35 google_apis x86_64)

| Step | Result | Evidence |
|---|---|---|
| install → cold open | **PASS** — `Displayed +631ms` first frame; interactive hero ~4–6 s | logcat |
| welcome film once | **PASS, ordering caveat** — film played once (live `/v2/city` field mean 55.0 µg/m³), auto-exit → onboarding → consent; `welcome_seen_v1.json` written; relaunch skips straight to populated home. **Caveat (new, low):** OS notification-permission dialog paints *before* film/consent on Android — film runs underneath it; iOS ordering differs | film-8, onb-3, relaunch-3 |
| home live prod numbers | **PASS** — ambient hero moved 47→50→59→63 µg/m³ across polls; Delhi today 744 µg, PM10 174.4, NO₂ 13, O₃ 126.2, CO 759.8, SO₂ 16.7, US AQI 111, "40% below 10-yr avg", "updated 4 min ago". OkHttp → `65.2.28.40` in logcat; alive-cache holds real `v2_daycurve`/`v2_outlook` | home-final, settings-1 |
| search sheet ×10 (SIGSEGV watch) | **PASS — 0 crashes.** 10 open/close on one PID + typed searches ("india gate", "lotus temple" → real geo-ranked gazetteer). 0 × SIGSEGV/FATAL in logcat. 3c24a5e exercised hard on Android — clean | search-results2, cycle-typed |
| consent-off spot check | **PASS** — `consent.json sharing:"off"`, `settings.json share:false`, toggles OFF in drawer+Settings; `outbox.json` never materialized (stronger than `{"items":[],"dropped":0}` — enqueue path never ran); zero forbidden POSTs | drawer, settings-2 |
| air-alerts settings rows | **PASS** — Air alerts ON + kind rows (smoke & fires, air turning worse, clean windows, your day on the road) all ON matching `settings.json`; `events.json` live `{beltFires:12, bandIdx:2, seen:{…}}` — the events engine runs | settings-alerts, settings-notif |

Full per-step evidence: child session's `emulator-verify-report.md` and
screenshots (attached to session devin-e8c52dd7).

## Residual flags

- **android-drive-report's two mediums → FIXED by c84b5c2** (phantom post-arrival
  re-plan + exhaust idle-only model): commit confirmed ancestor of 70914c0; the
  drive lane's prior v2 pass at 39bae99 verified the fix on-device. Not
  re-driven end-to-end this pass (scope was the a–f checklist, no full nav trip).
- **Basemap labels** — closed as upstream emulator-only bug maplibre-native#3648
  (8e21de2); needs a physical device to finally classify. SwiftShader still
  renders no labels.
- **NEW (low): film/consent ordering** — OS notif-permission dialog surfaces
  before the welcome film on this build; content still completes. Demo-day
  expectation note, not a bug fix request.
- **Eaten taps persist (low)** — occasional second tap/micro-drag needed (Where
  to? pill, sheet field focus); could be emulator flakiness or real; unchanged
  from prior lanes.
- **Emulator-vs-hardware caveats** — `Displayed +631ms` is framework first-draw
  not full interactive; no multi-touch; GNSS-speed channel absent on
  test-provider fixes (exhaust derived-speed path exercised instead).

## macOS rig notes (for the next lane stuck without KVM)

- This box is a nested VirtualMac2,1 VM: `kern.hv_support=0` → no HVF. The SDK
  GUI emulator refuses arm64 images without accel; x86_64 images are refused by
  qemu2 on aarch64. The only working rig is raw
  `qemu-system-aarch64-headless -accel off` (TCG) with
  `DYLD_FALLBACK_LIBRARY_PATH` exported *inside* the wrapper script (SIP strips
  it on exec of system binaries), google_apis arm64-v8a image, `-no-window
  -gpu swangle_indirect`. Boot ~6–8 min, display 320×480.
- `-cores N` makes it WORSE (vCPUs timeshare ~1 host thread in this fork —
  no `thread=multi` support; `-accel` accepts only on/off/auto). Keep 1 vCPU.
- `pm install` under TCG repeatedly kills `system_server` via the 60 s watchdog
  (commit does verify+parse of 137 MB on a monitored thread). Two recipes that
  worked: (1) `pm install-create`/`install-write`/`install-commit` split —
  commit survives only if PM stays up through it; (2) **`pm install-create
  --staged` + `install-write` + `install-commit` + reboot** — the staged session
  is applied during early boot before the watchdog arms. Recipe (2) is the
  reliable one; orphan sessions (`SecurityException: no access`) mean PM
  restarted mid-sequence — create a fresh session.
- Post-boot, disable GMS churners to let the guest settle: `pm disable-user
  com.android.vending com.google.android.apps.wellbeing
  com.google.android.apps.nexuslauncher com.google.android.googlequicksearchbox
  com.google.android.gm com.google.android.apps.photos`.
- The AVD's real userdata is `userdata-qemu.img.qcow2` — `userdata-qemu.img` is
  a 6 MB placeholder; deleting the wrong file does not wipe data.
- `service check package` + `service check mount` to gate PM/storage readiness;
  expect "Broken pipe (32)" transiently while system_server restarts.
- Even with all of the above the drive never reached a stable interactive state
  on this box — **use a Linux child lane for the emulator drive** (this report's
  evidence came from one: boot ~10 s under KVM vs ~8 min TCG).
