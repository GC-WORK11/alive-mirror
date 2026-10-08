# index-prebuild lane report — bundle-time chunked t0 index; early query() can't re-arm a build

Lane scope (dispatch): boot-burst found the freeze's second arming path —
first `query()` before the index is ready ran a synchronous UNBOUNDED
`build()` (~124k rows), re-arming the same burst an early typer is trying
to survive. Fix: a BUNDLE-TIME PREBUILT t0 index instead of building in
app; lazy-build fallback if the asset is bad; index kept fresh by the
same step that stamps the corpus; early `query()` must never
synchronously build. Verify on sim: cold-boot CPU before/after, "co"
typed at t+3s lands rows without a burst, identical result quality.

## Verdict

**Shipped, sim-verified — but the first design (one monolithic 32 MB
asset) made cold boot FATAL and had to be reworked mid-lane.**

- v1 (single `t0-index.json`, hydrate on first touch): the ~32 MB
  `require`+hydrate is ONE ~8 s ~100–150% CPU block on the sim. Fired at
  the deferred `warm()` point (t+15–20 s) it lands inside the
  boot-burst kill band → **app died 5/5 cold boots** (t+21/26/32 s, two
  with zero interaction; a `WARM_DEFER_MS=45000` diagnostic still killed
  at t+57 s). Baseline lazy build died **0/5** in the same windows.
- v2 (shipped, `assets/t0-index/` = 36 × ~0.9 MB chunks + generated
  `chunks.js` literal-require dispatch): per-chunk parse+merge is a
  bounded ~0.2–0.6 s step inside the same input-yielding quiet-window
  loop the old build survived → **0 deaths in 5 valid cold boots**,
  hydration completes ~t+28–40 s post-launch, no 8 s wall in any trace.
- Early typing: "co" at ~t+7 s → rows at ~t+8 s — the honest path
  working as designed (Photon/server tiers answer while t0 hydrates;
  `onIndexReady` replays when t0 lands). "karol bagh" typed
  MID-hydration returned instantly — input yields the scheduler.
- Result quality: parity test + sim screenshots — identical rows to the
  lazy build (name + kind·subtitle), `loadedFrom: "prebuilt"`.

## What ships (base/v2, commit 0c61ecf)

- `Mobile/assets/t0-index/` — generated, committed:
  `manifest.json` `{v, gaz_sha256, gaz_rows, chunks}`; `c0..c35.json`
  byte-balanced ~0.9 MB shards (every table — entries, prefix, fprefix,
  fskel, area, geo — split into contiguous byte-target slices);
  `chunks.js` — generated dispatch whose `load(i)` switch of literal
  `require()`s lets Metro bundle every chunk but only parse the asked
  one (~49 lines, regenerated, not hand-edited).
- `Mobile/scripts/build-t0-index.mjs` — builds THROUGH t0.ts's own
  indexing code (`__t0.buildAll()` + `__t0.serialize()`), so
  fold/tokens/caps are never re-implemented. Byte-balanced sharder,
  tmp-dir → atomic rename, `--check` sig gate, `--force`.
- `Mobile/src/search/t0.ts` — `ready()` only PROBES chunks.js (few KB,
  no chunk data → `prebuilt: "ok"|"failed"` once); `warm()` runs
  `hydrateNext()` — one chunk per scheduled macrotask, input-quiet
  gated, frees each merged shard (peak ≈ Maps + one chunk < old
  RAW-pinned peak). A bad/absent chunk or asset → `resetIndexState()` +
  the original sliced lazy build. `query()`/`nearestPlace()` return
  `[]`/`null` until `built` — no reader path ever calls `build()`.
  `onIndexReady(cb)` fires when the index lands.
- `Mobile/src/screens/SearchScreen.tsx` — subscribes once; on ready,
  replays `t0query(qRef.current, locRef.current)` so the queued query
  lands rows without another keystroke (refs, not render-bound state).
- `Mobile/src/search/test-runner.mjs` + `t0index.test.ts` — 5 pins:
  manifest sha vs gazetteer + dispatch integrity (`load(0)`, `load(N-1)`,
  `load(N)→null`); early query = honest `[]`, no sync build, no corpus
  parse, probe reads no chunk (`hchunk===0`); corrupt → lazy; missing →
  lazy; prebuilt-vs-lazy deep-equal on 15 queries + nearestPlace.
- `Mobile/package.json` — `build:t0`, `check:t0`, and `postinstall`
  regen (npm ci is the step every build path shares → a stale blob
  can't rot).
- `scripts/build_mobile_gaz.py --install` — emit + install gazetteer +
  index regen in ONE stamp step (the lane's freshness requirement).
- `.github/workflows/ci.yml` — `node src/search/test-runner.mjs` step.

## The numbers

| metric | BEFORE (lazy build) | v1 monolith (killed) | v2 chunked (shipped) |
|---|---|---|---|
| index ready, cold boot | ~2 min of sliced 100% CPU (or never under interaction) | — | ~t+28–40 s post-launch |
| biggest single JS block | ~11 MB corpus require (~1–2 s, survives) | ~8 s parse+hydrate | ~0.9 MB parse+merge (~0.2–0.6 s) |
| cold-boot survival (sim) | 0 deaths / control + all runs | **5/5 deaths** | **0 deaths / 5 launches** |
| first "co" rows | ~2 min (after freeze) | never (dead first) | ~1 s after keystroke (Photon until t0 lands ~t+30 s) |
| Node hydrate total | — | 160–220 ms | 83 ms (36 × ~0.9 MB, worst chunk parse 21 ms on this host) |
| hot query | ~31 ms | same | ~2 ms (Node host) |

## How to regenerate / verify

- After ANY gazetteer change: `cd Mobile && npm run build:t0` (or
  `scripts/build_mobile_gaz.py --install` for a full data stamp). Sig
  check only: `npm run check:t0`. `npm ci`/`npm install` re-stamps
  automatically when the corpus changed — the committed blob stays
  fresh because the freshness check lives in the step every build path
  runs.
- Tests: `cd Mobile && node src/search/test-runner.mjs` (also in CI,
  "Search index tests" step). Gates: `npx tsc --noEmit`, `npx expo lint`
  — all clean at 0c61ecf.

## Verification rig & evidence (iPhone 17 sim, EDD9B083, iOS 26.5)

- Dev client built from source (ruby@3.4 pod install + xcodebuild
  Debug iphonesimulator), Metro `EXPO_PUBLIC_API_URL=http://65.2.28.40`.
  BEFORE/AFTER toggled by `git show HEAD~1:` file redirects — same
  install, same bundle server.
- CPU: `pgrep -f ALiv[e]108` + `ps -o time=` deltas ~4.5 Hz to t+70–95 s.
- v1 traces `cpu_after{,2,3,45,45b}.txt` (deaths), `cpu_before{,_run1,
  2,3,_control}.txt` (survivals); v2 traces `cpu_c_s1..s4.txt`,
  `cpu_c_i1.txt` (interactive) — in the session's test-artifacts dir.
- Screenshots: `before_karol.png`, `before_rows_landed.png` (baseline);
  `after_death_springboard.png` (v1); `chunked_co_rows_t8.png`,
  `chunked_karol.png` (v2). Recording of the verified drive:
  `index-prebuild-chunked-edited.mp4`.

## Residual risk / notes

- Chunk files are generated assets committed to git (31 MB). They're
  regenerated by postinstall; a pull only changes them when the corpus
  did — matches the gazetteer convention (11 MB asset committed).
- `prebuilt` probe trusts `v`/`chunks`/`gaz_rows` + per-chunk array
  shapes at runtime; the sha256 sig is enforced at build/test time, not
  runtime (hashing 11 MB at boot is itself a burst).
- Hermes kill-band knowledge: empirically ~t+15–60 s on this rig — the
  window where ANY multi-second monolithic JS block risks jetsam/sigbus.
  v1's death wasn't the asset's size per se — it was ONE unbounded
  block; per-step bounds are the fix, not a bigger defer.
- SearchScreen replay subscribes per mount; unsubscribes on unmount.
  Photon rows can beat t0 rows to the sheet — merge/dedupe order is
  unchanged.
