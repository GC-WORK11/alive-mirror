# apk-final-v6 — arm64 release build on e2e-residual HEAD

Lane: apk-final-v6 · date: 2026-10-08 · rig: macOS builder (SDK warm from v5)
Build: `base/v2` HEAD = **ec2ed08** — e2e-residual: P2-3 onboarding busy-latch, offline pill stall+z-order, IST clock everywhere, receipt expander, hi a11y (all iOS-sim verified by the lane, `docs/lanes/e2e-residual-shots/`). Rides on v5's full verified base (`270be81`: scorer + polish + stays/playtime + routes-delta).
Per brief: **no universal build** (v5's `alive-270be81-universal.apk` 189.3MB remains the x86 fallback), **no retake film** (v5.mp4 covers the feature paths — residual fixes carry their own sim evidence; the offline-pill fix here directly addresses v5 film's one PARTIAL beat).

## Artifact
| what | value |
|---|---|
| APK (release candidate, real devices) | `alive-ec2ed08-arm64.apk` · 108,705,019 B (~108.7 MB) — **arm64-v8a only** — https://app.devin.ai/attachments/a1c6257e-18fe-484f-806f-48736f7c8624/alive-ec2ed08-arm64.apk |
| sha256 | `95f467ca5ccca0fb4bdb4cb9955668c4caa84a77f637227a571399bfa8968d07` |

## Bake verification (bundle inside the shipped APK)
- `unzip -p assets/index.android.bundle | grep -c 'http://65.2.28.40'` → **1** ✓ (prod API baked)
- dev-URL grep → **1 hit, benign**: `…arathi HS SchoolocalhostNutan Pustak Bhandar…` — gazetteer POI-name concat, same documented false-friend class as v4/v5. Real dev URLs = 0.
- ABI check: 18 `lib/arm64-v8a/` entries, 0 `lib/x86*`/`lib/armeabi*` — true arm64-only.
- Badging: `com.anonymous.app` v1.0.0 (code 1), minSdk 24, targetSdk/compileSdk 36, label `Alive`.
- `rm -rf app/build/generated/assets/react` pre-build; `assembleRelease` **1m13s** incremental (359/383 up-to-date — JS bundle + native merge re-ran on the ec2ed08 diff). `npm ci` state carried from v5 (no package.json/android changes in ec2ed08 — verified via pull diff).

## Delta vs v5 (`270be81` → `ec2ed08`)
e2e-residual commit `ec2ed08` — 5 sweep leftovers fixed: post-wipe onboarding busy-latch (P2-3), offline pill stall + z-order (the v5-film partial), IST clock everywhere, receipt expander, hi a11y. No new features; v5.mp4 (898.5s, 16/17 PASS) remains the feature-film of record.

## Notes
- Size delta vs v5 arm64: +2,700 B (residual fixes only — code diff, no asset growth).
- x86/ emulator path: install v5's universal APK if an emulator smoke is needed; feature surfaces unchanged since.
