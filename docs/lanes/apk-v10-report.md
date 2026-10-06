# Lane report: apk-v10 — design-v3 demo binary @ 419680f

**Date:** 2026-10-06 · **Verdict: BUILT + statically verified** ·
Build host: this macOS box (compile lane runs natively — no KVM child needed;
emulator runtime explicitly not required this round).

## Binary

- **URL:** https://app.devin.ai/attachments/af468ab8-e317-45c9-be02-22bf8c1cca03/alive108-419680f.apk
- **SHA:** `419680f` — base/v2 HEAD ("meaning layer — live provenance line").
  Carries welcome cinematic (`16b9c2e`), week card (`de01a11`), arc-scrub
  pressables, footer-CTA fix (`4f60b28`), full design-v3/soul/one-accent
  chain, dead-code sweep (`64c122b` + `b7ce48f` + `3569a2e` + `f1454fa`).
- **Size:** 137,054,272 B (130.7 MiB)
- **sha256:** `b44041aee75217daca02893c195e2b6bf56b9e5e1c14efc8eb52f08dc411fa49`
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

- Launcher label is `app` (`android/.../strings.xml` app_name, committed in
  the original project generation `1101564`) — every shipped APK including
  v9 shows it. One-string fix, but it's a visible product name — flagged for
  owner call rather than changed in a build lane.
- `package com.anonymous.app` is the default Expo package id — same story,
  fine for demo/internal installs.
