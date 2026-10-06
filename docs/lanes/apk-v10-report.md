# Lane report: apk-v10 — design-v3 demo binary @ c3bb731

**Date:** 2026-10-06 · **Verdict: BUILT + statically verified** ·
Build host: this macOS box (compile lane runs natively — no KVM child needed;
emulator runtime explicitly not required this round).

## Binary — FINAL (the one the owner installs)

- **URL:** https://app.devin.ai/attachments/2bca2e64-f9be-4dd5-ad4b-6b0da650c461/alive108-c3bb731.apk
- **SHA:** `c3bb731` — base/v2 product tip. Everything below PLUS
  `c3bb731` launcher label `app → ALive·108` (verified in-binary:
  `aapt` reports `application-label:'ALive·108'`).
- **Size:** 137,054,180 B (130.7 MiB)
- **sha256:** `ebe3d2c327b1837727993c3610021dd63154252e4094892195b7ee58bd91cc49`
- **Superseded:** `alive108-3d3df49.apk` (`22e18738…a3248`, label still `app`)
  and `alive108-419680f.apk` (`b44041ae…1fa49`, pre-search-verb). Do not install.
- **aapt badging:** `com.anonymous.app` · versionCode 1 · versionName 1.0.0 ·
  targetSdk 36 · `usesCleartextTraffic=true` (required — prod endpoint is http).

## Prod endpoint

`EXPO_PUBLIC_API_URL=http://alive108-2699c171ddded465.elb.ap-south-1.amazonaws.com`
baked at bundle time (per `client.ts`: release builds take the env var;
`localhost:8000`/`10.0.2.2:8000` only exist under `__DEV__`).

Bundle grep (`assets/index.android.bundle`):

| string | hits |
|---|---|
| `alive108-2699c171ddded465.elb.ap-south-1.amazonaws.com` | 1 |
| `localhost:8000` / `10.0.2.2:8000` | **0** (dev fallback tree-shaken) |

## Feature markers in bundle (grep counts)

| feature | marker | hits |
|---|---|---|
| welcome cinematic | `WelcomeScreen`, `welcome_seen_v1` | 1 + 1 |
| arc-scrub pressables | `arcScrub` | 1 |
| week card (`de01a11`) | `weekTitle`, `homeWeek`, `"your week"` | 1 + 2 + 1 |
| design-v3 soul pass | `BreathEdge`/`breath` | 7 |
| live provenance line (`419680f`) | `nearest` | 4 |

`alive_boot_v1` = landing-page (web) boot strip — correctly absent from the
Android bundle, present in web surfaces only.

## Build recipe (what ran)

```
cd Mobile && npm ci --prefer-offline          # 746 pkgs, 12s
# re-strip foojay resolver line 16 in
# node_modules/@react-native/gradle-plugin/settings.gradle.kts
# (npm ci RESTORES it — strip AFTER install, every build)
cd android
EXPO_PUBLIC_API_URL=http://alive108-2699c171ddded465.elb.ap-south-1.amazonaws.com \
  ./gradlew assembleRelease -x lint           # BUILD SUCCESSFUL 4m14s
```

Mirror init.gradle at `~/.gradle/init.d/mirror.gradle` already covers
repo.maven.apache.org + repo1.maven.org → googleapis mirror; no edits needed.

## Verification statement

Static verification only, per brief: APK unzipped, release bundle grepped for
baked endpoint + feature markers above, `aapt dump badging` for manifest
sanity, sha256 computed on the shipped artifact. No emulator install/run —
runtime evidence for this source stands on the iOS-sim-verified tree plus
the v9 Android drive of the same design chain.

## Flags (pre-existing, not touched)

- Launcher label was `app` → fixed by owner in `c3bb731`
  (`strings.xml` app_name → `ALive·108`), now baked into the FINAL binary.
- `package com.anonymous.app` remains the default Expo package id — fine for
  demo/internal installs; rename before any store presence.
