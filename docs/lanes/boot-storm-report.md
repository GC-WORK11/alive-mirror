# boot-storm-ios lane report — the ~2.5 min 100%-CPU cold-launch storm

Lane scope (dispatch): reproduce the lifecycle-catalogued cold-start
storm on the iOS sim (`100%-CPU ~2-2.5min EVERY launch, once FATAL —
main thread idle, worker-side spin`), capture who burns it, fix the
spinning component(s), verify 5 cold launches before/after, report +
push to `base/v2`. Android is the boot-burst lane's.

## Verdict

Root cause found and fixed: the storm is the **search-index `cap()`
sorts in `src/search/t0.ts`** — postings lists > `PREFIX_CAP`(80) are
sorted with a comparator that calls `weight()` → `typeBonus()`, a
9-branch regex gauntlet, **~2 regex-evaluating calls per compare**.
~2,589 lists / ~3 M capped ids → hundreds of millions of interpreted
regex evals in **one unyielding macrotask** (input-yield can't help
inside `Array.sort`). On interpreted Hermes that is the ~2 min 100%
wall; the once-seen FATAL fits the same window.

After the fix: **5/5 cold launches** go quiet at t≈111-122 s with a
~3 s cap spike instead of a ≥70 s wall; seconds ≥60% CPU dropped
79 → 18-27; no crash. Evidence `~/bootstorm/{cold1,fix1-5}/`.

## Repro + attribution (BEFORE, HEAD 1384a6c)

Rig: iPhone 17 sim `EDD9B083` + `E0224A22` (iOS 26.5), Release build
`~/dd-rel/…/Release-iphonesimulator/ALive108.app`. Harness
`~/bootstorm/probe2.sh <label> <dur> [reinstall] [udid]` — terminate,
launch, 1 Hz `ps %cpu`, `sample $PID` at t=12/35/60/90/120/150,
screenshots every 15 s.

`cold1/cpu.tsv`: peak 106%, ≥80% **t=4 → t=177.6 (still burning at
capture end)**, 79 s ≥60%, never quiet.

`cold1/sample_t150.txt` — the whole JS thread in one frame:

```
com.facebook.react.runtime.JavaScript
  TimerCallback::invoke → interpretFunction
    → arrayPrototypeSort → doQuickSort
    → StandardSortModel::compare
    → regExpPrototypeTest → regex::Context::backtrack
```

That stack is `ids.sort((a,b) => weight(entries[b]) - weight(entries[a]))`
inside `cap()` at the tail of `buildSlice()` — `weight` → `typeBonus`
→ `regExpPrototypeTest`. Earlier samples (t35-90) show the *other* CPU
phase: `HadesGC::EvacAcceptor::forwardCell` / `OldGen::search` /
`allocSlow` — `indexRow` allocation churn across the sliced warm build
(bounded, 20-70% duty — honest work, not the storm).

## Fix (Mobile/src/search/t0.ts)

1. **`typeBonus` memoized** — the kind vocabulary is ~720 strings; each
   kind now pays the regex gauntlet once, ever, instead of ~twice per
   sort compare.
2. **`Entry.wt` precomputed** in `indexRow` (`typeBonus + w*0.5 + k*2`)
   — same formula, computed once per row at index time.
3. **Numeric comparator** `entries[b].wt - entries[a].wt` in `cap()`;
   `weight()` now reads `e.wt` for the scoring call sites too (match
   ordering unchanged — same weights, same branch order).
4. **`cap()` sliced like the row build** — `capIdx` walks PREFIX →
   FPREFIX → FSKEL, one map per `buildSlice` call, so on a saturated
   rig the residual sorts park between macrotasks (input-yield +
   SIGBUS-window behavior preserved). `build()`/`query()` still drain
   slices synchronously — a mid-build query completes the index before
   returning, exactly as before.

`npx tsc --noEmit` clean, `npx expo lint` clean, `node src/search/
test-t0.mjs` green (karol bagh→8, india gate→2, ashok nagar→8, gali→0 —
no rank regressions).

## AFTER — 5 cold launches (fix1-5, same rig)

| run | peak %cpu | last ≥80% | quiet-to-end | secs ≥60% |
|-----|-----------|-----------|--------------|-----------|
| cold1 (before) | 106.3 | t=177.6 (never) | never | 79 |
| fix1 | 95.7 | t=110.6 | t=111.6 | 18 |
| fix2 | 100.6 | t=120.2 | t=122.3 | 23 |
| fix3 | 122.8 | t=118.1 | t=120.2 | 21 |
| fix4 | 100.3 | t=117.0 | t=119.1 | 26 |
| fix5 | 99.7 | t=114.9 | t=116.0 | 27 |

Post-cap samples (e.g. `fix1/sample_t150.txt`, `fix2/sample_t120.txt`):
JS thread parked in `mach_msg` — idle runloop, not a spin. Onboarding
screen is up by t=15 (`fix*/shot_t15.png`); worst JS macrotask during
boot is now ~1 s (one cap map) vs a ~70 s+ unyielding sort, so the
input-yield windows boot-burst added actually work. Fatal repro did
not recur — 5/5 processes alive at capture end.

## What still burns (honest remainder)

t≈20-115 s runs 20-70% CPU — the sliced 124,311-row `indexRow` build
over the 11.3 MB gazetteer plus pack prefetch. That's bounded honest
work at ~50-60% duty with yield gaps, not a spin, and it's what makes
first search instant. The real kill (per boot-burst's recommendation)
is a **bundle-time serialized index** — precompute PREFIX/FPREFIX/
FSKEL + entries into the shipped bundle and skip the build entirely.
Bigger change, flagged for a follow-up lane.

## Also fixed — the patch files were silently dead

All three `Mobile/patches/*.patch` were authored as `diff -ruN` output
with **package-relative** paths (`a/ios/…`) and mtime-suffixed
`---`/`+++` lines. patch-package expects app-root-relative git diffs
(`a/node_modules/<pkg>/…`); its parser also glued the timestamp into
the filename. Result: **`postinstall` reported "3 error(s)" and applied
NONE of the patches on every fresh clone** — the sigbus lane's
`withAllocInYoung(false)` / `makeThreadSafeHermesRuntime` / modulemap
fixes never shipped to a clean install. Rewrote all three as git-style
diffs (`node_modules/<pkg>/` prefixes, `new file mode` + `/dev/null`
for the generated modulemap). Verified on pristine
`npm pack` extracts in an isolated root: all 3 apply ✔ via
patch-package 8.0.1, and `withAllocInYoung(false)` lands in
`HermesInstance.cpp`. Every lane's next fresh `npm install` actually
gets the native fixes now.
