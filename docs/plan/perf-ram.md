# perf-ram — memory audit + Metro config (lane r4-perfram)

**Owner demand:** "sleek and low on RAM." Scope audited: `Mobile/` — bundler
config, map module, nav engine, API cache, screens, bundled assets.
This lane owns `Mobile/metro.config.js` + this file; everything else is
reported as a recommendation for the owning lane.

## 1. Metro config — applied (`Mobile/metro.config.js`)

| Knob | Value | Rationale |
|---|---|---|
| `transformer.getTransformOptions → transform.inlineRequires` | `true` | Expo SDK 57 ships `inlineRequires: false` — every module body executes at bundle init. With it on, a module executes on first `require` instead: cold-start JS heap + TTI drop by the cost of code not yet touched (all of maplibre/svg/screens the boot path never runs). Metro-native, no deps added. |
| `transform.experimentalImportSupport` | `true` | preserved at Expo's default — `getTransformOptions` is replaced wholesale, so the flag must be restated. |
| minifier (`metro-minify-terser`), package exports, asset pipeline | **unchanged** | audit found no other metro-level knob with a demonstrable RAM win; asset plugins would only add build complexity for <500 KB of images. |

Not in scope for metro.config: Hermes is already the default JS engine in
RN 0.86/Expo 57 — no engine flag needed. Hermes compile flags live in the
native build (`expo-build-properties`, not installed), not in Metro.

## 2. Memory-risk audit (top findings first)

| # | File:line | Risk | Est. impact | Recommended fix (owning lane) |
|---|---|---|---|---|
| 1 | `src/search/t0.ts:101` + `assets/delhi-gazetteer.json` (2.7 MB) | `require()` returns the parsed 26,545-entry array from Metro's module registry — retained **forever** after first `warm()`, *in addition to* the `ENTRIES`/`PREFIX` index `build()` derives from it. Double retention: raw rows + normalized index. | ≈4–8 MB JS heap once search opens; +2.7 MB in the JS bundle either way | After `build()`, empty the shared array in place (`raw.length = 0`) — legal because `require` returns the same reference, so the registry keeps an empty shell. Longer-term: load the JSON via `expo-file-system` text+`JSON.parse` so the parse result is GC-able, or ship it gzipped / slimmed (drop `w`/`k` into fewer bytes). |
| 2 | `src/map/style.ts:97–133` | `v2StyleUrl()` does a full `JSON.parse(JSON.stringify(v2Style))` deep-clone **and** synchronous `File.exists` stat on every call — and the header comment (`src/map/index.ts:4`) advertises calling it inline in JSX. Each call returns a new object identity → passed to `<Map mapStyle>` it can trigger a native style diff/reload per render. | per-render clone + fs stat; worst case a full MapLibre `setStyle` per state change (multi-MB native alloc churn) | Resolve once per app lifetime: module-level `let resolved` cache in `v2StyleUrl()`, or `useMemo(() => v2StyleUrl(), [])` in the caller. `App.tsx:133` currently passes a constant URL, so this is latent — fix before the v2 style lands. |
| 3 | `src/screens/LedgerScreen.tsx:361` + `src/store/ledger.ts:59,67,146` | Ledger renders **every** trip via `sorted.map()` inside `ScrollView`; the store caps history at `slice(-500)` → up to 500 `TripRow` view hierarchies mounted at once on sheet open. | ~500 mounted rows when the ledger is full — several MB of view/state + a visibly slow sheet open | `FlatList` with `initialNumToRender`, or render latest 50 + "load more". The 500-entry disk cap is fine; the mount-all rendering is not. |
| 4 | `src/nav/engine.ts:363–371,375` | GNSS watcher (`BestForNavigation`, 1 s/5 m) + 1 Hz `setInterval` have no `AppState` gate — they keep running if the app is backgrounded mid-nav. Cleanup itself is correct (`subRef.remove()`/`clearInterval` at :150–157, unmount effect :383); `trajRef` is bounded at `MAX_TRAJ` 4,900 fixes ≈ ≤0.4 MB. | background GPS + JS wake = battery + RAM held while user thinks the app is asleep | subscribe to `AppState` in `start()`/cleanup: `remove()` the watcher + clear the interval on `background`, re-arm on `active` (navigation resumes honestly — counters measure `dt`, so no math breaks). |
| 5 | `App.tsx:153` | `<UserLocation animated accuracy>` mounts permanently once permission is granted — a continuous high-accuracy location subscription + native animation loop even in the idle/rest phase. | steady-state location callbacks + anim loop for the whole session | mount only during `phase === "nav"` (or when `flow.follow`), or drop `animated` outside nav. |

### Lower-severity notes (not top-5)

| File:line | Note |
|---|---|
| `src/api/cache.ts:90–100` | File-backed cache keeps **zero** in-memory index (good for RAM) but entries are never evicted — TTL is enforced at read only, and `cacheKeys.plan` mints one file per rounded O/D pair → slow unbounded *disk* growth. Fix: opportunistic eviction (delete a stale file on `cacheGet` miss, or sweep when `DIR.list().length` > N). |
| `App.tsx:88,91` | 15 s health + 60 s reports `setInterval`s — bounded payloads, both cleared on unmount (:105). Fine. |
| `src/nav/engine.ts:309–335` | `tick` fires 6 `setState`s at 1 Hz — render churn, not a leak. Optional: bail early when `pendMRef === 0` and no fix arrived. |
| `src/search/client.ts` / `SearchScreen.tsx` | Result sets bounded (T0 ≤6, recents ≤5, server limit 12); `ServerSearch` aborts in-flight work and `dispose()` runs on unmount (:120–124). Fine. |
| `src/offline/queue.ts` | Outbox bounded at `MAX_QUEUE = 50` with honest `dropped` count. Fine. |
| `src/components/shell/useShellFlow.ts:213–233` | `routeSegs`/`altSegs` GeoJSON correctly memoized — no per-render recreation. Fine. |
| `src/map/style.ts:29` | `v2-dark.json` (30 KB) parsed once at import — trivial. |

## 3. Bundled assets

| Asset | Size | Verdict |
|---|---|---|
| `assets/delhi-gazetteer.json` | **2.7 MB** | flagged — >1 MB bundled, parsed into the JS heap (see risk #1). Data is useful on-device; the fix is how it's held, not deleting it. |
| `assets/icon.png` | 388 KB | launcher icon — required by app.json, acceptable. |
| 6 embedded fonts (`@expo-google-fonts` Inter ×3, Noto Sans Devanagari ×3) | ≈336 KB each, ≈2 MB total | all weights ship in the packages but only the 6 imported `.ttf`s are bundled. Native font memory ≈2 MB — acceptable; subset further only if profiling demands it. |
| `src/map/v2-dark.json`, SVG pucks/pins, remaining PNGs | <35 KB each | fine. |

No other >1 MB bundled data found (`find assets -type f` scan; no `require()`d
JSON besides gazetteer + v2-dark).

## 4. Measurement recipe (verify on device)

```bash
# 0. Build/run a release or dev-client build (Expo Go skews numbers —
#    it carries the whole Go runtime).
cd Mobile && npx expo run:android --variant release   # or eas build

# 1. Cold start + idle baseline
adb shell am force-stop com.anonymous.app
adb shell am start -W -n com.anonymous.app/.MainActivity   # record TotalTime
sleep 5
adb shell dumpsys meminfo com.anonymous.app > mem_idle.txt
#    Watch "TOTAL PSS", "Native Heap" (MapLibre tiles), "Java Heap", "Code".

# 2. Gazetteer cost — open Search once, then:
adb shell dumpsys meminfo com.anonymous.app > mem_search.txt
diff mem_idle.txt mem_search.txt     # delta ≈ risk #1 (expect several MB)

# 3. Ledger — seed ~500 trips, open "Trip receipts" sheet, dumpsys again.

# 4. Nav — start navigation, background the app:
adb shell input keyevent KEYCODE_HOME
adb shell dumpsys location | grep -A2 com.anonymous.app   # is GNSS still on?
adb shell dumpsys meminfo com.anonymous.app               # heap still growing?

# 5. Metro flag A/B — set inlineRequires true/false in metro.config.js,
#    rebuild JS (npx expo export --platform android), compare step-1
#    "TOTAL PSS" at idle + `am start -W` TotalTime.

# 6. In-app: dev menu → Perf Monitor shows RAM live; Hermes stats via
#    HermesInternal.getInstrumentedStats() in a debug build if finer
#    JS-heap detail is needed. Android Studio: Profiler → app process →
#    Memory for a timeline + heap dump to hunt the gazetteer retention.
```

Acceptance suggestion: after risk #1's fix, step 2's delta should drop
to roughly the index size alone (entries+prefix ≈ half of today's delta);
after `inlineRequires`, step 1's idle `TOTAL PSS` + start time should be
measurably lower than the A/B control.
