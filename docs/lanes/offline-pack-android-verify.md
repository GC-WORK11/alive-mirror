# Lane report: offline-pack verify — Android emulator

**Fix under test:** `54a296e` — `OfflineManager.createPack` gets `mapStyle = http://65.2.28.40/v2-light.json` instead of a `file://` dump. Pack `delhi-ncr-z9-13-r2` (dead `r1` row deleted on sight).
**Goal:** `region_tiles > 0` (expect ~744) in `mbgl-offline.db` on Android + no `Mbgl-HttpRequest: Unable to parse resourceUrl` in logcat.

## Verdict: PARTIAL — device run blocked by environment, everything verifiable without a device checks out

The only step that could not run on the originating machine is the emulator
itself: the box is a **virtualized Mac** (`VirtualMac2,1`, `kern.hv_support=0`)
— no KVM/HVF equivalent exists, and Google's darwin-arm64 emulator ships no TCG
fallback (arm64 guests require HVF, full stop). A Linux/KVM lane was dispatched
to finish the on-device half; this file is updated when it lands.

## Environment details (the blocker)

| Item | Value |
|---|---|
| Host | macOS 26.6.2, arm64 (`Apple M4 Pro (Virtual)`, `VirtualMac2,1`) |
| Virtualization | `kern.hv_support: 0` — guest VM, no nested virt |
| Emulator | Android emulator 37.2.12.0; valid `-accel` = `on|off|auto` |
| `emulator -accel-check` | reports `Hypervisor.Framework OS X Version 26.6` |
| Attempt 1 (`-accel` auto) | `HVF error: HV_UNSUPPORTED` → `failed to initialize HVF: Invalid argument` |
| Attempt 2 (`-accel off`) | same — `off` is parsed but ignored: qemu is launched with HVF anyway (no TCG build shipped for darwin-arm64) |
| Attempt 3 (`-accel tcg`) | rejected: `Invalid '-accel tcg' parameter, valid values are: on off auto` |
| Attempt 4 (`-engine classic`) | `Missing emulator engine program for 'arm64' CPU` (classic engine removed) |

## What was verified on this box (no device needed)

- **Step 0 — prod route live:** `GET http://65.2.28.40/v2-light.json` → `200`,
  94,254 bytes, sha256 `295be2fdc8d7af8d68ea5d7850ac11e93aece3ac9c3f1fa4e3ebe4025e8e0be3`
  (matches the expected hash exactly — deploy `54a296e3` already landed).
- **Fix in tree:** `git merge-base --is-ancestor 54a296e HEAD` → yes
  (HEAD was `7c68c8b` at run time).
- **Style parity:** `server/static/v2-light.json` byte-identical to
  `Mobile/src/map/v2-light.json` (`cmp` clean, same sha256 as the live route —
  prod serves exactly the bundled style).
- **Unit suite:** `node src/offline/test-runner.mjs` → **12/12 pass**, incl. all
  six `tileWarm — fetchable pack style` tests (r2 created over http(s), r1 row
  deleted, bundled-style + http-only gates, once-per-launch, silent failure).
- **Release build:** `EXPO_PUBLIC_API_URL=http://65.2.28.40
  ./gradlew -I ../../scripts/gradle-init-mirror.gradle assembleRelease` →
  BUILD SUCCESSFUL in 3m34s (init script needed — plain run 429'd on the
  foojay plugin). APK `app-release.apk` = 137,140,420 B,
  sha256 `538b19138df9f8a17d9cada5705ec82b838e07520c458a18e3eb4dd5cc300d2a`.
- **Fix baked into the bundle:** `assets/index.android.bundle` strings contain
  `/v2-light.json` (×1), `delhi-ncr-z9-13-r2` (×1), `delhi-ncr-z9-13-r1` (×1 —
  the delete-on-sight constant); `alive-v2-style.json` (the old file:// style
  dump) is **absent** — the r1 code path is gone from the shipped JS.
- **AVD ready (unused):** `demo`, `system-images;android-35;google_apis;arm64-v8a`,
  `pixel_7` — created successfully; never booted (no accelerator).

## What's NOT verified here

- Booted-Android run: `region_tiles > 0` in `mbgl-offline.db`, single region
  row with `"style_url":"http://65.2.28.40/v2-light.json"`, and a clean
  `Mbgl-HttpRequest` logcat. Requires a machine with KVM (Linux) or HVF
  (bare-metal Mac). Prior iOS-sim evidence for the same fix:
  `docs/lanes/offline-pack-fix-report.md` — 744 tiles, 297 resources, 1 region.
