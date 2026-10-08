# Lane report — perf-budget (perf-regression-guard)

Honest latency numbers for the things a user feels, measured on-device. Bars
from the dispatch: **<300 ms** touch-feel, **<16 ms** frame budget (60 fps).
Evidence lives in `~/perfprobe/*/perf_log.jsonl` on the measurement box —
every number below is a `mark`/`jank` pair from `src/perf.ts`, not a stopwatch.

## Method

- iPhone 17 sim (UDID EDD9B083-…), iOS 26.5, **Release** build of HEAD
  (db3d275 + this lane's probes), `EXPO_PUBLIC_API_URL=http://65.2.28.40`
  (prod ap-south-1 — ELB hostname doesn't resolve on sim DNS).
- `PERF_ON=true` locally for the build (reverted to false before commit —
  all probes are no-ops when off). New marks added this lane: `search.tap`,
  `search.key`, `search.rows`, `search.open`, `search.idxReady`,
  `plan:req`/`plan:resp`/`plan:fail` (in `src/api/plan.ts` — the fetch tap in
  `startup/marks.ts` never fires: something re-wraps `globalThis.fetch`
  after module eval, so the plan call was instrumented at source instead),
  `plan.chooser`, `gest.will`/`gest.did`, `labels.hide`/`labels.show`,
  `settings.save`/`settings.write`, `dose.tick` + `jank("dose.tick")`,
  `jank("scroll.home")` on the home ScrollView drag.
- Time base: `t` = ms since `src/startup/marks.ts` eval (≈ JS bundle eval).
  Native process launch → bundle eval is **not** in these numbers — boot-film
  owns the true cold-open film; this table starts at first JS.
- Interactions driven through the iOS AX bridge (pixel taps get eaten during
  settle), dest = Saket metro, origin = Connaught Place fix.

## The budget table

| Latency a user feels | Measured | Bar | Verdict |
|---|---|---|---|
| app eval → `app.mounted` | 12.7–77.5 ms (5 boots: 12.7, 14.9, 17.8, 35.8 fresh-install, 77.5) | — | ✅ sub-80 ms; the 77.5 outlier is boot-to-boot variance, watch it |
| → live numbers painted (`daydata.first`) | 152–281 ms | — | ✅ live value on screen inside ~¼ s |
| → map rendered (first idle) | 314–910 ms warm tile cache; 1946 ms first-ever install | — | ✅ warm; cold-install tile fetch is network-bound |
| → tap lands | `search.tap`→`search.open` **70 ms** at t+12.3 s; sheets are tappable well under 1 s | <300 ms | ✅ |
| "where are you going" tap → sheet open | **70–71 ms** | <300 ms | ✅ |
| typed char → first row, index-warm | **6.4–11.1 ms** (two probes) | <300 ms | ✅ instant |
| typed char → first row, index-cold (typed t+16.1 s, `search.idxReady` t+17.7 s) | **1586 ms** — rows land 6 ms after the index finishes hydrating | <300 ms | ⚠️ honest wait — "Searching…" covers it; no server-tier row painted first in this sample |
| plan request → chooser visible | engine-first rows: **1788 ms** (`plan:req`→`plan:resp`→`plan.chooser` +12 ms); full ranked set (metro/bus): **7652 ms** | <300 ms | ⚠️ network+server-bound; progressive paint covers it, but "In progress · adding metro, bus…" sits ~6 s |
| home scroll jank (gfxinfo-equivalent) | **0 dropped / 292 rAF ticks**, maxGap 20 ms, 4 full-list drags | <16 ms | ✅ holds 60 fps |
| sheet-open frame drops | `enter.sheet` 0–1/73, `enter.search` 0/73, `enter.settings` 0/73, `drawer.open/close` 0–1/73 | <16 ms | ✅ |
| map gesture → labels hidden | `gest.will`→`labels.hide` **~9.7 ms**; rest → `labels.show` **~8.9 ms** | — | ✅ the d8c7b41 gap = the drag itself (1.19 s, 1.24 s); programmatic camera moves do NOT drop labels (userInteraction gate confirmed — `gest.did` without `gest.will` changes nothing) |
| covered-FPS delta | `preferredFramesPerSecond` 8 while covered (App.tsx:866) — can't be read from JS on sim; no jank probe dropped during gesture windows | — | ✅ semantically covered; see caveat below |
| data refresh tick → reload flash | `dose.tick` at t+180.5 s: jank **2 dropped / 66 ticks, maxGap 123 ms** | no flash | ⚠️ **no visual reload** (surface stays mounted — the fix holds) but ONE ~123 ms hitch during the re-assemble — borderline-perceptible stutter ≈7 frame-gaps |
| settings toggle → persisted | `settings.save`→`settings.write` **4.8 ms** (atomic write + .bak) | <300 ms | ✅ |
| app memory RSS | boot ~570–590 MB → settled post-hydration ~690–730 MB → after full nav tour ~1015 MB | — | ⚠️ trend climbs ~60% boot→nav; fine on modern devices, watch on low-RAM |
| CPU | idle <3 %, interaction bursts 20–38 % | — | ✅ |

## Bad-vs-bar callouts (owner candidates)

1. **`dose.tick` 123 ms frame gap** — the only real "glitchy" datapoint on
   this run. One hitch when a new ambient sample lands (~8 min cadence,
   dedupe-gated). Chain: `App.tsx:~598` `recordSample()` → `setDayNonce` →
   `useDayData` re-assemble (ledger/daylog re-derivation on the JS thread).
   Fix owner: whoever owns `src/store/daylog.ts` / the HomeScreen day-data
   derivation — move the re-derivation off the tick or memoize harder.
2. **index-cold typing 1.59 s to first row** — `src/search/t0.ts`
   `hydrateNext` chunk schedule reaches ready ~17.7 s post-eval; typing in
   the tail waits it out (the replay is correct, just slow for an early
   typer). Owner: search-index lane — either shrink hydration further or
   let the Photon/server tier actually paint first (it produced no row in
   this sample — worth checking why).
3. **Full-plan 7.65 s** — `plan:req`→`plan:resp` for the ranked set with
   metro/bus. Server-side `server/v2/plan.py` rank time, not client; the
   engine-first paint at 1.79 s already gives the user a real chooser.
4. **`app.mounted` 77.5 ms variance** — one boot took ~5× the median.
   Unknown cause; flag for repeat measurement, not a fix yet.

## Found & fixed on this lane (shipped regression)

`src/search/t0.ts` `hydrateNext` dropped the `wt` field when deserializing
the chunked index (regression from fda1083's chunked hydrate; `wt` has been
required since 9a0799a). Effect: hydrated entries scored `NaN`, `cap()`/`matchStage`
ranked temples above districts, `tsc` red at HEAD, search test-runner 4/5.
Fix: recompute `wt = typeBonus(c) + w*0.5 + k*2` per row (same formula as
`indexRow`). Verified: `tsc` clean, search runner **5/5**.

## BEFORE vs now (anchors from boot-film-report)

| anchor | boot-film | now | delta |
|---|---|---|---|
| `app.mounted` | 14–18 ms | 12.7–17.8 (one 77.5) | flat |
| `daydata.first` | 147–170 ms | 152–281 ms | flat, slightly wider spread |
| `map.rendered` | ~450–500 ms | 314–910 ms | tile-cache variance dominates |
| `enter.home` rAF settle | ~1.3 s | 0–2 dropped / 73 ticks | comparable (settle ≈1.2 s probe window) |
| tap→search-open | <2 s | 70 ms | different definition — earlier measured full settle incl. anim; both healthy |

## Caveats

- Sim ≠ device: rAF on sim is vsync-timed but Metal/driver cost is lower;
  absolute gaps transfer directionally, not exactly.
- Covered-FPS (8 fps while the sheet covers the map) can't be observed from
  JS — verified by code path only (App.tsx:866); no gesture-window jank was
  recorded, consistent with the cap doing its job.
- `plan:*` marks are now in `src/api/plan.ts` (gated by `PERF_ON`); the
  `startup/marks.ts` global-fetch tap stays but never observed a plan call
  (fetch gets re-wrapped post-eval).
- `npx tsc --noEmit` clean on this tree; `npx expo lint` + test runners
  run at commit time.
