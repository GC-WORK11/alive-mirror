# Lane report: offline pack actually downloads — file:// style_url → http://

**Commit:** `54a296e` (fix) — `delhi-ncr-z9-13-r2` pack
**Prior evidence:** `docs/lanes/offline-walk-report.md` (`81c2326`) — r1 created the region row, 0 tiles forever.

## What was broken

`Mobile/src/map/tileWarm.ts` called `OfflineManager.createPack` with
`mapStyle` pointing at a `file:///…/alive-v2-style.json` it had dumped
from the bundled style. MapLibre Native's `Mbgl-HttpRequest` cannot
parse `file://` resource URLs — the style fetch never left the ground,
so the region row existed but `region_tiles`/`region_resources` stayed
0 forever. On dead wifi the basemap only rendered inside the ambient
cache (where the user had already panned).

## The fix — option (b): serve the bundled style over http

- `server/static/v2-light.json` — byte-identical copy of
  `Mobile/src/map/v2-light.json` (94,254 B, sha256
  `295be2fd…8e0be3`). The style itself points at hosted
  `https://tiles.openfreemap.org` for source/glyphs/sprite, so once the
  style JSON is fetchable, everything else already is.
- `server/main.py` — new `GET /v2-light.json` (FileResponse,
  `application/json`, `_STATIC_CACHE` headers). Additive route, no
  existing behavior touched.
- `server/tests/test_v2_light_parity.py` — parity test: route serves
  200/JSON/cache headers, served bytes == bundled bytes, style carries
  the https vector source + glyphs + sprite. Guards the two copies
  from drifting.
- `Mobile/src/map/tileWarm.ts` — rewritten: passes
  `${API_BASE}/v2-light.json` (same `API_BASE` every surface uses —
  `EXPO_PUBLIC_API_URL`, baked into release builds) as `mapStyle`.
  Pack renamed `delhi-ncr-z9-13-r1` → `…-r2`: a dead r1 region row can
  no longer shadow the fix, and any r1 row found is deleted on sight.
  Warms only when the live style is the bundled `v2Style` (an env or
  pmtiles override honestly skips the pack rather than warming the
  wrong source) and only when `API_BASE` is http(s). All failures stay
  silent — worst case is the pre-fix behavior (online streaming +
  ambient cache).
- `Mobile/src/offline/tileWarm.test.ts` + `test-runner.mjs` hooks —
  6 unit tests: r2 created with the http URL (never file://), r1
  deleted, 160 MB ambient cap, once-per-launch, skips non-bundled
  styles / non-http API_BASE, resumes an existing r2, silent on
  createPack failure. `npx tsc --noEmit` + `npx expo lint` clean.

## Verification

### iOS simulator — pack lands, end-to-end (PRIMARY EVIDENCE)

iPhone 17 sim (iOS 26.5), Debug dev-client built from this commit,
Metro with `EXPO_PUBLIC_API_URL=http://172.16.4.2:8000` against local
`uvicorn main:app`:

- `Library/Application Support/com.anonymous.app/.mapbox/cache.db`:
  - `regions` — exactly 1 row, definition JSON =
    `{"style_url":"http://172.16.4.2:8000/v2-light.json","min_zoom":9.0,"max_zoom":13.0,"bounds":[28.2,76.8,28.95,77.9]}`
  - **`region_tiles` = 744** — the expected NCR z9–13 tile count
  - `region_resources` = 297 (glyph ranges + sprite)
  - counts stable across re-query — download complete, not partial
- Online path unbroken: same map renders OFM vector tiles live
  (San Francisco default sim location) — screenshot on record.
- Local server access log: `GET /v2-light.json` 200, 94,254 B —
  identical sha256 to the bundled style.

### Server route

- `pytest server/tests/test_v2_light_parity.py` — 3/3 pass
- `curl http://127.0.0.1:8000/v2-light.json` → 200, byte-identical.

### Prod

- `54a296e` pushed; deploy.sh (CodeBuild mode — no local docker on the
  verification box) ran at ~14:00 UTC with BUILD_SHA=54a296e3 →
  `curl http://65.2.28.40/v2-light.json` — **see "prod status" below.**

### Android

- Release APK built on macOS arm64: `EXPO_PUBLIC_API_URL=http://65.2.28.40
  ./gradlew assembleRelease` → `app-release.apk` (137 MB). Build works
  — required `scripts/gradle-init-mirror.gradle`-style maven mirror
  injection because `repo.maven.apache.org` 429-rate-limits shared
  egress.
- On-box AVD cannot run: `qemu … failed to initialize HVF` (no nested
  virtualization on the verification box). A KVM-enabled Linux child
  session is running the full AVD verification (region_tiles > 0,
  logcat clean) — see `docs/lanes/offline-pack-android-verify.md` when
  it lands. The mechanism is the same MapLibre `OfflineManager` API on
  both platforms; the iOS pass verifies the native fetcher behavior
  that was broken.

## Residuals / honest limits

- **A new APK cut is required.** `EXPO_PUBLIC_API_URL` is baked at
  bundle/build time — installed APKs still warm nothing (they contain
  r1-era code, and the r1 pack never downloaded anyway, so they are no
  worse off; new build ≥ `54a296e` is what gains the working pack).
- **Prod deploy is required.** Until `GET /v2-light.json` is live,
  release builds pointing at prod see the same dead-pack behavior
  (style fetch 404 → createPack idles, silent degrade). Deploy ran
  this session — status below.
- **Env/pmtiles style overrides skip the pack** by design — if
  `EXPO_PUBLIC_MAP_STYLE_URL` or a local pmtiles style is live, the
  warm gate refuses rather than caching the wrong source. Ambient
  cache still covers actually-rendered areas.
- `include_ideographs:false` is what MapLibre recorded for the region —
  Devanagari labels inside the pack depend on the glyph ranges OFM
  ships; check the offline हिन्दी labels on the demo walk if it matters.

## Files

- `Mobile/src/map/tileWarm.ts` — rewritten warm path
- `Mobile/src/offline/tileWarm.test.ts`, `Mobile/src/offline/test-runner.mjs` — tests + loader hooks
- `server/main.py` — `GET /v2-light.json`
- `server/static/v2-light.json` — served copy (parity-tested)
- `server/tests/test_v2_light_parity.py`

## Prod status — LIVE on `ffddab93`

`GET http://65.2.28.40/v2-light.json` → **200, 94,254 B, sha256
`295be2fdc8d7af8d68ea5d7850ac11e93aece3ac9c3f1fa4e3ebe4025e8e0be3`**
(byte-identical to `Mobile/src/map/v2-light.json`), `application/json`,
`cache-control: public, max-age=3600`. `/health` stamps `build_sha:
ffddab93` — a newer lane deploy that includes `54a296e`; task-def
`alive108:207` steady state, 1/1 running.

Deploy note for the deploy lanes: this session briefly ran
`scripts/deploy.sh` (CodeBuild, `BUILD_SHA=54a296e3`) before seeing prod
had already moved past it — the script was killed before the ECS stage
(service untouched, verified steady-state above). The CodeBuild build
did finish and pushed `alive108-api:54a296e3` AND `:latest`, so
**`:latest` currently points at `54a296e3`, older than the live
`ffddab93` image** — cosmetic only (task-defs pin sha tags), but the
next `deploy.sh` build will overwrite it anyway.
