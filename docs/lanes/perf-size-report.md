# perf-size lane — boot→first-numeral + 169 MB APK

Date: 2026-10-08 · lane: perf-size · branch: base/v2 (HEAD ce22939 at write time)
Rig: iPhone 17 sim (iOS 26.5, UDID EDD9B083-…-0A6964CC2561), Metro dev client,
`PERF_ON=true`, prod API `http://65.2.28.40` (~470 ms /aqi roundtrip from this box).
All times are ms since bundle eval (`[perf]` marks ≈ `[PERF]` marks within ~10 ms;
dev StrictMode double-effects appear twice and are noted, both runs measured the same way).

## MOBILE PERF — boot → field fetch → numeral paint

### Measured timeline (returning-user boot; 3 launches each side)

Baseline (HEAD before this lane):

| mark | run 1 | run 2 | run 3 | what it is |
|---|---|---|---|---|
| app.mounted | 238 | 242 | 192 | AppInner mount |
| consent.read | 266 | 268 | 214 | consent.json → introSeen |
| loc.lastknown | 343 | 344 | 272 | getLastKnownPositionAsync — **serial ~100 ms before aqi:req** |
| aqi:req | 321 | 329 | 259 | `GET /aqi` fired |
| fonts.ready | 354 | 356 | 282 | useFonts resolves → splash hides + overlay gate opens |
| day.disk | 403 | 402 | 329 | allSamples+getCheckins (gated by afterFirstFrame by design) |
| day.week / day.lens | 447 / 448 | 418 / 419 | 346 / 347 | serial getDay ×7 + lens loop — **15–45 ms serial rollups** |
| daydata.first | 457 | 426 | 352 | first DayData setData → hero skeleton |
| grid:req → resp | 225 → 965 | 236 → 817 | 185 → 766 | the air-field GeoJSON — lands in the numeral window |
| aqi:resp | 959 | 966 | 904 | ambientUg set |
| daycurve:req → resp | 430 → 965 | 406 → 961 | 335 → 910 | forecast curve + outlook |
| day.curve | 1163 | 1047 | 943 | curve/outlook into DayData |
| **hero.num** | **2353** | **1168** | **1380** | **first commit with a real numeral** |

Baseline `hero.num` median ≈ **1380 ms** (run 1 is a first-launch outlier — cold
caches). The recurring serial stall: `aqi:resp` (~950) → `hero.num`, a
200–1400 ms gap where the JS thread was busy parsing the /grid GeoJSON,
building AirFieldLayer props, resolving curve+outlook and running
checkAirEvents — all in the same window the numeral commit needed.

### Fixes applied (safe deferrals only — every one lands before a human can reach for the surface)

1. **Boot fetch storm deferred** (`App.tsx`): `fieldBootRetry` (/grid),
   `fetchCity`, `fetchCityMoves` and the first `/reports` poll moved from
   effect-start to `afterFirstFrame() + 1200 ms`. None feed the first paint;
   the map sits under the home sheet until a tap; the field already tolerates
   7 s retry gaps, and report pins are map content. Same-file precedent:
   `warmSearchIndex`'s existing `afterFirstFrame + timeout` pattern.
2. **Search-index warm moved 900 → 2200 ms** (`App.tsx`): the ~0.9 MB
   t0-index chunk requires used to parse inside the numeral window; now they
   run after the field warm fires.
3. **`useDayData` rollups parallelized** (`src/screens/HomeScreen.tsx`):
   week strip (7× `getDay`) and symptom-lens days were serial `await` loops —
   now `Promise.all`. daysum seals are keyed per-day and disk writes chain on
   `writeTail`, so concurrent calls are safe (verified in daysum.ts: write
   path is a serialized single-file flush, per-day map mutation is
   single-threaded). Today's rec is still synchronous, not a `getDay` call
   (today is volatile by definition — same semantic as before).
4. **Measurement taps** (`src/startup/marks.ts`, `App.tsx`, `HomeScreen.tsx`):
   fetch tap extended to `/aqi`, `/grid`, `/v2/day`; seam marks added
   (`consent.read`, `loc.lastknown`, `day.disk/rec/week/lens/curve`,
   `hero.num`). Startup marks are dev-console only; `mark()` no-ops unless
   `PERF_ON` (left **false** in the commit).
5. **Font requires trimmed** (`App.tsx` — also an APK fix, below): barrel
   imports of `@expo-google-fonts/{inter,ibm-plex-mono,noto-sans-devanagari}`
   → 9 deep per-weight imports; dead `Fraunces_*` import removed (it was
   imported but never in `useFonts` — retired per docs/20). Fewer font
   requires at eval and fewer native font loads inside the `useFonts` gate.

### After (3 launches, same rig)

| mark | run 1 | run 2 | run 3 |
|---|---|---|---|
| aqi:req → aqi:resp | 254 → 734 | n/a → 787 | 358 → 838 |
| grid:req → resp | 1512 → 1836 | 1569 → 1899 | 1610 → 1931 |
| day.curve | 840 | 894 | 993 |
| **hero.num** | **945** | **1138** | **1467** |

- `hero.num` median **1380 → ~1138 ms (−240 ms, −17%)**; cold/worst case
  2353 → 1467 (−886 ms).
- `aqi:resp` itself lands ~150 ms earlier (904–966 → 734–838): the promise
  resolves on arrival now instead of queueing behind grid JSON.parse.
- The field still lands at ~1.8–1.9 s — well before any real map tap.
- `grid` parse+layer-build contention is what remains between `aqi:resp`
  and `hero.num` (~150–600 ms post-fix): the leftover gap is render work
  (overlay tree re-commit on `setAmbientUg` + StrictMode double render),
  not a deferrable stall — restructuring it is a bigger surgery than this
  lane's mandate.

### Measured-but-not-fixed stalls (reported, not hidden)

- `loc.lastknown` (~55–105 ms serial before `aqi:req`): kept. The await
  exists so the boot read can be taken **at the user's fix** rather than
  the centroid — honesty semantics, not a bug.
- `fonts.ready` (~280–355 ms gate): parallel with disk reads; trimmed the
  require set but the gate itself stays (fonts must precede text paint).
- Dev StrictMode double-runs `useDayData`; release doesn't. Numbers compare
  like-for-like on the same build mode.
- Sim CPU ≫ a mid-tier Delhi phone — the JS-contention win is expected to
  be *larger* on device; network numbers are real (prod ELB).

## APK SIZE — alive-06919ca.apk, 169,337,404 B

`unzip -v`, uncompressed sizes (source of truth for what fills the archive;
with `expo.useLegacyPackaging=false` .so files are stored uncompressed +
page-aligned, so uncompressed ≈ APK bytes there):

| payload | uncompressed MB | share | notes |
|---|---|---|---|
| `lib/` — 4 ABIs × 18 .so | 103.7 | ~61% | arm64-v8a 27.4 · x86 28.7 · x86_64 28.2 · armeabi-v7a 19.4; biggest per ABI: libmaplibre.so ~8–11 MB, libreactnative.so ~5–7.4 MB, libhermesvm, libappmodules, libexpo-modules-core |
| `assets/index.android.bundle` | 43.0 | ~25% | stored uncompressed (`android.enableBundleCompression` unset → RN adds `noCompress "bundle"`). Includes lazily-required gazetteer ~19.9 MB + t0-index shards — parsed on first query, NOT at boot (verified: `require` inside functions in src/search/t0.ts) |
| dex (3× classes*.dex) | 24.6 | ~8.9 compressed | minifyEnabled=false |
| `res/` incl. 46 .ttf | ~10 | ~5.6 compressed | fonts dominated it |
| resources.arsc + misc | ~1.4+ | | |

### Applied (zero-risk, verified by `expo export --platform android`)

- **Font trim** — 47 unused TTFs no longer required: Fraunces (18, dead
  import) + unused Inter/PlexMono/Noto weights (29). **−8.84 MB**
  uncompressed asset payload (~4–5 MB inside the APK); export shows 14 font
  assets (9 google + 5 Satoshi) ≈ 2.0 MB vs ~10 MB before. Also removes
  47 module requires from the Hermes bundle.

### Recommended, NOT applied (zero-feature-loss but not zero-risk)

- **`reactNativeArchitectures=arm64-v8a`** (one line in
  android/gradle.properties): −76 MB uncompressed → APK ≈ 95–100 MB.
  Biggest lever by far. Risk: the APK stops installing on x86 emulators —
  need a decision on how judges/demo machines run it. The clean fix is
  shipping AABs/splits per ABI.
- **`android.enableBundleCompression=true`**: ~−30 MB download, but trades
  stored-for-mmap → inflate-on-read: slower first eval (~100–300 ms on
  low-end). Directly conflicts with the boot-perf work above — needs a
  device-verified startup regression check before flipping.
- **`minifyEnabled=true` + `shrinkResources=true`**: dex 24.6 → est.
  8–15 MB + res pruning. Reflection/keep-rule risk — needs a full
  on-device regression pass, not a blind flip.

## Gates

- `npx tsc --noEmit` — clean (also re-run after pull-rebase onto ce22939)
- `npx expo lint` — clean
- `node src/store/test-runner.mjs` — 99 pass / 0 fail
- `node src/nav|api|offline/test-runner.mjs` — 0 fail each

## Env notes for the next lane

- `expo-build-properties` was in package.json but absent from node_modules —
  xcodebuild fails at `[CP-User] Generate app.config` until `npm install`.
- `PERF_ON=true` leaves a 20 s `setInterval` alive — the .mjs test runners
  never exit while it's on. Flip it back before running gates (it's false
  in this commit).
- Basemap/style, /reports, city warmers now start ~1.2 s post-first-frame —
  if a future lane needs them earlier for a new surface, gate on the
  surface's mount, not the boot effect.
