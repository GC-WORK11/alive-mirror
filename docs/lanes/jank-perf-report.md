# jank-perf — the owner's six complaints, traced + fixed + measured

Owner verbatim, one root-cause trace each, then the fix and the measured
number on the iPhone 17 sim (iOS 26.5, dev client, base/v2 + this diff —
60 fps frame-diff timing, daylog.ts `ts` correlation for the write-path
claim). All timings are post-fix.

| # | Complaint (verbatim) | Root cause | Fix | Measured |
|---|---|---|---|---|
| a | "app updates every few minutes but the ENTIRE UI/UX reloads" | `useDayData` (`HomeScreen.tsx`): every landed ambient sample bumps `dayNonce` → the assemble effect re-ran → `setData` wrote `curve:null, outlook:null` → **MoveCard + DaysAheadCard unmounted for ~1 s** → ~600 px of scroll content collapsed → visible whole-surface reload, then remount on refetch | Re-assemble now preserves `prev.curve`/`prev.outlook`/`curveAgeS` while the refetch flies — cards stay mounted, numbers update in place | zero card unmount on re-assemble — a real poll-driven rebuild landed mid-test (daylog sample @10:37:57) with no visual artifact |
| b | "scroll below the days ahead → bug clutches hard, yanks me back up to the Move card" | Same unmount — DaysAhead lives *below* MoveCard; when it collapsed, the viewport clamped and the user landed on the move card | (1) stale-keep above kills the mount; (2) `maintainVisibleContentPosition={{minIndexForVisible:0}}` on the home ScrollView re-pins the first visible item whenever a card above grows — survives future height-jitter too (e.g. the new IncidentsCard arriving) | check-in press while scrolled to the bottom row: viewport pixel-identical across the press frames, no yank |
| c | "'how you felt' buttons are the MOST glitched — pressing one = piece of crap" | Two compounding bugs: (i) pill fill only derived from the `checkin` prop → press waited on the disk write + full day re-assemble (~100-500 ms dead read), and (ii) the (a) unmount teleported the row under the finger mid-press | `CheckinSheet` local echo — the picked pill fills the same frame; render-time reset yields to the prop the moment the record lands (no effect, lint-clean) | fill rendered at ~80 ms — **before** the daylog write timestamp (10:33:27.281); the echo precedes the disk roundtrip, not after |
| d | "'where are you going' took 10 SECONDS — screen glitched/hung/stuck" | `t0.ts` `build()`: 11.3 MB gazetteer `require` + 124k-entry prefix index ran as **one synchronous block inside the search sheet's mount effect** — the sheet's JS-driven enter spring froze mid-slide (Hermes parse+index ≈ multi-second JS-thread stall on a mid-range phone) | Index build is now sliced (~6k rows / ~20-30 ms per macrotask) and scheduled at boot-idle (+900 ms); both search doors also call `warm()` on press-in. `query()`/`nearestPlace` synchronously finish any remainder — correctness never waits on the scheduler | "Where to?" open ~200-250 ms; "go somewhere" ~150-250 ms; post-cold-relaunch open ~250 ms — zero mid-slide freeze |
| e | "Air Map took 5 seconds to load" | The map was never the slow part — it's mounted at boot under the home sheet; the open is just the sheet's 150 ms exit + unmount. The felt-5 s was boot-time tile streaming competing with the (d) JS stall | unmount commit only; verified path adds no work | tap→map fully visible ~50-70 ms (3-4 frame crossfade) |
| f | "the loading screen is slop I never asked for" | `WelcomeScreen` cinematic — once-per-install film the owner no longer wants | `<WelcomeScreen>` mount + state removed from `App.tsx`; `welcome_seen_v1.json` still writes once per install at boot (flag lifecycle identical for anything reading it); `WelcomeScreen.tsx` stays on disk unbundled | cold relaunch → home painted ~2.6 s — straight to consent, no film |

## Search-index equivalence (the risky one)

`t0.ts` was rewritten from one-shot `build()` to sliced `buildSlice()` —
verify it's not a subtle result change: compiled the HEAD version and
the new version side-by-side, ran **20 queries** ("connaught", "cp",
"karol bagh", "noida sec", "gk", "sarojini", "dwarka", "rajiv chowk",
"airport", "saket", "hauz khas", "lajpat", "chandni", "isbt", "tiwari",
"metro", "mandi house", "greater kailash", "okhla", "rohini") + **5
`nearestPlace` points** — byte-identical result lists, corpus still freed
after build (`raw.length=0`).

## Also fixed en route

- `setUserPos` every 60 s poll allocated a fresh `{lat,lon}` → deduped
  (same fix = `prev` object identity when the fix hasn't moved).

## Gates

`npx tsc --noEmit` clean · `npx expo lint` clean · `node src/{store,nav,api,offline}/test-runner.mjs` → 84+76+12+12 = 184 pass / 0 fail.

## Honest caveats

- **Sim ≠ device CPU.** The sliced index build lands at ~1-2 s post-boot
  on the sim; on the owner's phone the same slices run slower but stay
  ≤~30 ms each — the sheet mount itself can never block on the build now
  (mount calls async `warm()`, never sync `build()`). Only a *keystroke*
  inside the first ~seconds of a cold launch could still pay a
  synchronous finish — bounded, rare, and strictly better than before.
- **The literal 60 s-poll blink wasn't filmed** — ambient samples land at
  ~8-9 min cadence (the poll dedupes); the check-in write exercises the
  identical `setData` re-assemble path and was filmed clean, plus one
  real sample-driven re-assemble ran mid-recording with no artifact.
- `useHeldState`/draw-hold machinery on every overlay mount/unmount is
  sim-only (`Device.isDevice` no-ops) — kept, per its documented
  SIGSEGV class. Map 2 fps throttle during the first ~100 s on sim is
  that same shim, not a regression.
- `maintainVisibleContentPosition` requires RN ≥0.72 / new arch — we're
  on RN 0.86 (Expo SDK 57); on any engine that ignores it the prop is a
  no-op, no fallback needed.

## Evidence

- Key stills committed at `docs/lanes/jank-perf-shots/` —
  `t1-immediate-after-press.png` (pill filled ~600 ms post-press with
  every card still mounted), `t4-search-open.png` +
  `t4-connaught-results.png` (sheet open + real results),
  `t3-airmap-after.png` (map fully visible ~50-70 ms post-tap),
  `t6-home-after-relaunch.png` (cold relaunch straight to home).
- Full 60 fps recording + raw frame-diff source: on the testing box
  (`screencasts/alive108-jank/`, `testing-evidence/` incl. the
  test-plan.md and per-test frame montages).
