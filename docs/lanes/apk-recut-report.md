# Lane report: apk-recut — canonical demo binary re-cut at base/v2 HEAD

**Date:** 2026-10-07 · **Verdict: SHIPPED — all gates PASS, offline pack verified on Android for the first time**
**Binary:** `alive108-ef5d95f.apk` — replaces `alive108-c3f7e9e.apk` (sha256 `4faa08ed…`) as the canonical demo binary.

- **URL:** https://app.devin.ai/attachments/0febc48c-996a-420e-9d84-a426a05d163a/alive108-ef5d95f.apk
- **sha256:** `de15ae62e5a3a886a7410148c214535ca9cf0829904499f00eb9c40ff401705a`
  — re-verified byte-identical on the aggregating macOS box after download
  (independent of the builder's claim).
- **Size:** 137,140,424 B (130.8 MiB)
- **Commit baked:** `ef5d95f` — base/v2 HEAD at build time. HEAD moved past
  pinned `1d39687` mid-lane (judge-answers doc push); all later commits through
  `2607ce0` are docs-only — **no product code shipped after the binary**.
- **Badging:** `com.anonymous.app` · `usesCleartextTraffic=true` · stock debug
  keystore wired into release (known gap since Oct-3 — installs fine, not
  Play-grade).

## Why

`alive108-c3f7e9e.apk` predates offline-pack fix `54a296e`. `EXPO_PUBLIC_API_URL`
and all app code are baked at bundle/build time, so the old APK's pack stays
dead forever — r1 created the region row with an unparsable `file://` style_url
and sat at `region_tiles=0` (docs/lanes/offline-walk-report.md). This binary is
the first that can actually download `delhi-ncr-z9-13-r2` on Android.

## Mobile delta riding along (`git log c3f7e9e..ef5d95f -- Mobile/`)

| commit | what ships in the app |
|---|---|
| `54a296e` | THE FIX — tileWarm passes `${API_BASE}/v2-light.json` (http) as the pack's mapStyle instead of a `file://` dump; pack renamed r1→r2, dead r1 rows deleted on sight; warms only on the bundled style + http(s) API_BASE; silent-degrade preserved |
| `795ff3b` | news-layer `cause_note` — app air-card + en/hi i18n + `{note}` on air-event pings |
| `47d7bff` | landing-perf — `Mobile/src/api/city.ts` `cached_s` disclosure + `Bridge/contract.ts` (in-flight GET dedupe) |

Mobile tree was final at build: last Mobile-touching commit on the branch is
`54a296e` itself — nothing Mobile landed mid-build.

## Build

- **Host:** Linux KVM child session (`devin-42e39709`) — the requesting lane's
  macOS box has no Android SDK and `kern.hv_support=0`; the Linux box carried
  JDK 17 + full SDK/AVD.
- **Recipe:** `npm ci` → foojay-resolver plugin line stripped
  (`node_modules/@react-native/gradle-plugin/settings.gradle.kts`, maven-429
  egress) → mavenCentral→googleapis sed mirror in node_modules gradle files +
  `scripts/gradle-init-mirror.gradle` → `~/.gradle/init.d/` →
  `rm -rf app/build/generated/assets/react` (Gradle does NOT track env as a
  task input — stale bundle silently folds out `EXPO_PUBLIC_API_URL`, v10
  lesson) → `env EXPO_PUBLIC_API_URL=http://65.2.28.40 ./gradlew
  assembleRelease -x lint`. **BUILD SUCCESSFUL 3m58s, zero 429s.**
- No product code modified; local-only build files.

## Bake-verify (on the shipped binary)

| check | expected | got |
|---|---|---|
| `http://65.2.28.40` in `assets/index.android.bundle` | exactly 1 | **1** |
| URL-form dev hosts (`https?://…localhost`/`127.0.0.1`/`10.0.2.2`/`:8081`) | 0 | **0** |
| literal `localhost` substring | n/a | 1 — benign: inside minified data token `…HospitalocalhostRefontWeight`, not a URL |

## KVM smoke — AVD `demo` (pixel_7, android-35 google_apis x86_64, SwiftShader)

Oracle: `logcat | grep -cE 'FATAL EXCEPTION|SIGSEGV|SIGABRT'` = **0**.

| beat | verdict |
|---|---|
| install + cold open | PASS — `am start -W` WaitTime 801 ms |
| notif dialog → onboarding → consent → location | PASS (known Android ordering quirk: dialog precedes onboarding) |
| home live numbers | PASS — hero "the air around you 59 satisfactory, 3.9× WHO"; OkHttp/tcp sockets to 65.2.28.40:80 in logcat |
| geo fix | PASS — `adb emu geo fix 77.2167 28.6315`; suggestions show real km |
| chooser | PASS — 3 candidate polylines drew, winner settled bold, **pill caught: "cleanest · 51% less than fastest"** + compare ladder (first pill state missed between captures; vehicle wizard F1 reproduced on first plan, completed, persists) |
| settings | PASS — toggles render |
| consent persistence | PASS — `consent.json {"seen":true,"sharing":"on"}` after force-stop |

## THE PACK — `delhi-ncr-z9-13-r2`: LANDED FULLY (first Android evidence)

`mbgl-offline.db` after first map render (adb root pull, sqlite3 on host):

- `regions` — 1 row: `style_url http://65.2.28.40/v2-light.json`, z9–13,
  NCR bounds `[28.2,76.8]–[28.95,77.9]`, name `delhi-ncr-z9-13-r2`; no r1 row
- **`region_tiles` = 744** — the full target (climbed and completed during
  the smoke drive; sibling lane 2607ce0 independently measured the same
  744/297/1 shape, z9=6 z10=16 z11=48 z12=154 z13=520)
- `region_resources` = **297** (glyphs + sprites + style + tilejson)
- logcat `Mbgl-HttpRequest: Unable to parse` / `file://` errors: **0**
- **Airplane-mode: PASS** — radios off → force-stop → cold relaunch 527 ms →
  honest stale pill ("offline — showing last known air"), panned ~4 viewports
  around Connaught Place → **full basemap renders from the pack** (streets,
  rail, parks, water). Pre-fix this went near-blank ~2 pans out.

## Prod dependencies (verified at build time)

- `GET http://65.2.28.40/v2-light.json` → 200, 94,254 B, sha256
  `295be2fdc8d7af8d68ea5d7850ac11e93aece3ac9c3f1fa4e3ebe4025e8e0be3` —
  byte-identical to `Mobile/src/map/v2-light.json`; live on build_sha
  `7c68c8bc`.
- `/health` → `engine=alive_core`, `field_stale=false`; `/aqi` + `/v2/city`
  serving real values (incl. `cause_note` from 795ff3b).

## Residuals / honest limits

- **SwiftShader renders no basemap text labels** (emulator quirk, closed as
  upstream maplibre-native#3648 on prior lanes; offline check relies on
  geometry which renders fully). Needs a physical device to finally classify.
- **Eaten taps under ~500 ms/frame emulator rendering** — drove with
  micro-swipes; unchanged from prior lanes.
- Pill first state ("cleanest and fastest") not captured — second state
  caught; both verified verbatim on the prior rehearsal lane.
- Release build emits no `Displayed:` line — cold launch timed via
  `am start -W` WaitTime instead.
- The literal `localhost` grep of the bundle returns 1 (glyph-data substring,
  not a URL) — stated honestly rather than zeroed.

## Evidence

- Child session: `devin-42e39709` (build + drive + pack check) — full
  `emulator-verify-report.md` attached there.
- Key shots (child attachments): home live numbers
  https://app.devin.ai/attachments/973f8660-cc58-4569-baaf-7c343c9aeb79/10-home.png ·
  chooser pill https://app.devin.ai/attachments/edf9b5e3-b7b6-4603-b78a-47ad9a41135a/chooser-05.png ·
  plan landed https://app.devin.ai/attachments/99890257-7cf3-4214-9cd4-97ba617e28e4/21-plan-landed.png ·
  settings https://app.devin.ai/attachments/11357414-9de4-415b-a3c6-c6623154d22f/24-settings.png ·
  airplane-mode map from pack https://app.devin.ai/attachments/b3175be4-b9e8-410c-a4fd-8da841c3137b/33-offline-map2.png
- Sibling corroboration: docs/lanes/offline-pack-android-verify.md (`2607ce0`)
  — independent KVM run, same 744/297/1 numbers.
