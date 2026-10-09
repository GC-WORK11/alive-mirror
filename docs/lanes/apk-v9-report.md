# apk-v9 — FINAL release APKs on safe-area HEAD `ef758f9` (code tip `ea97dab`)

Lane: apk-v9 · date: 2026-10-09 · build host: this macOS arm64 box · smoke rig: same Linux KVM child as v8 ([devin-c0abb64cbdf848aaa31e2bdd9cf3e6c1](https://app.devin.ai/sessions/c0abb64cbdf848aaa31e2bdd9cf3e6c1))

Build: `base/v2` HEAD = **ef758f9** — repo tip; code tip = **ea97dab** safe-area fix (Sheet self-anchors below the status bar + caps detent at top inset; labelled '‹ back' BackChip exit on every sheet surface — the owner's complaint, verified PASS in `docs/lanes/safearea-e2e.md`). Rides everything v8 shipped: `aa724bb` splash, `c88bb0f` trip-flow, `98fd8ba` stays/playtime v2, `3f9245f` air-map restyle, `90bc055` air-gate.

## Artifacts

| what | value |
|---|---|
| APK (release candidate, real devices) | `alive-ef758f9-arm64.apk` · **108,333,863 B (~108.3 MB)** — arm64-v8a only — https://app.devin.ai/attachments/e41e41cc-21bb-4160-b1f2-3128c43c7529/alive-ef758f9-arm64.apk |
| APK (universal, incl. x86 emulators) | `alive-ef758f9-universal.apk` · **188,884,520 B (~188.9 MB)** — 4 ABIs — https://app.devin.ai/attachments/93fe1f16-b360-4428-887c-868dd2cce6bb/alive-ef758f9-universal.apk |
| arm64 sha256 | `ce95c33e5b555fe4c5c02480299b9bc670c193958e04ca4572ae4452d821d06a` |
| universal sha256 | `8bc5f57cea56e36ec0ffe6da4e73335af6549c115214e669a9561cb38fd35572` |

## Release config applied

Identical recipe to v8/v7: `npx expo prebuild --clean -p android` → `hermesFlags = ["-O", "-fstrip-function-names", "-g0"]` in `react{}` → `ndk { abiFilters(...) }` property-driven arm64-v8a default → `android:usesCleartextTraffic="true"` re-added (prebuild deletes it — the trap persists) → `local.properties` at `Mobile/android/` → `EXPO_PUBLIC_API_URL=http://65.2.28.40` + `-I ../../scripts/gradle-init-mirror.gradle`. All edits on the generated tree only; checked-in tree untouched, restored post-build.

## Bake verification

- `unzip -p assets/index.android.bundle | grep -c 'http://65.2.28.40'` → **1** each ✓
- dev-URL scan (`localhost:` / `10.0.2.2` / `192.168.` / `.local`) → **0** each ✓
- Commit markers (UTF-8+UTF-16LE byte scan): `'finding the purest route for you'`/`'start journey'`/`'where to stay'`/`'the air map'` all ≥1 (v8 chain) **plus `a11yBack` =1 and `BackChip` =1 — ea97dab safe-area code confirmed baked**. Bundles byte-identical: **66,719,644 B** (+700 B vs v8 = the safearea diff).
- ABI: arm64 = arm64-v8a only (18 libs); universal = 4 ABIs (72 libs) ✓
- `usesCleartextTraffic=0xffffffff` in both binary manifests ✓ · `com.anonymous.app` v1.0.0(1) minSdk24 targetSdk36 'Alive' · debug-keystore recipe, no secrets
- Builds: arm64 `assembleRelease` **1m25s** (warm daemon), universal **+38s** incremental (bundle UP-TO-DATE — same .hbc)

## Light boot smoke — `demo` AVD pixel_7 · Android 15 google_apis x86_64 · KVM + SwiftShader — **ALL PASS**

(Full-surface AVD walk already exists for this exact code: `docs/lanes/safearea-e2e.md` — PASS, 15 shots. This pass = binary sanity. sha256+size re-verified on the rig pre-install; shots `docs/lanes/apk-v9-shots/` pushed `fce72a8`, re-verified frame-by-frame here.)

| step | verdict | evidence |
|---|---|---|
| install → cold launch | **PASS** | `am start -W` TotalTime **1867 ms** (fresh-data first boot) |
| splash + consent | **PASS** | held 'alive' replay on fresh install; Skip → location while-in-use — `s01/s02` |
| home hero live | **PASS** | **99 µg/m³ poor** · "read near Connaught Place · nearest live monitor ~1.6 km · air reading 3 min old" — `s03` |
| safe-area on-device | **PASS** | where-to sheet top edge sits BELOW the status bar; stays sheet at bottom detent with **‹ back** BackChip + sibling door + ✕ — matches ea97dab exactly — `s04/s05` |
| logcat crash sweep | **PASS** | 0× FATAL/SIGSEGV/tombstone/ANR (3.6k lines, short run) |

## Verdict

Ship `alive-ef758f9-arm64.apk` as the FINAL install binary — **it supersedes the v8 pair** (identical base + the safe-area fix the owner flagged). `alive-ef758f9-universal.apk` is the emulator/fallback twin (byte-identical JS+config, 4 ABIs).
