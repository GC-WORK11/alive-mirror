# nav-start-pick — report

Lane: `Mobile/src/components/shell` compare-sheet selection → Start.
Branch `base/v2`. Flag from apk-drive-v3: pick a non-recommended option
(Metro) → Start launches the RECOMMENDED card (Car-AC).

## The bug's mechanism — two stacked state-read faults

**1. Pick preservation matched on `route_id`, which can never match.**
`show()` (useShellFlow) kept the user's pick across the engine-first →
full-plan swap by remembering `opts[sel].route_id` and finding it in the
new set. But `server/v2/plan.py` calls `ROUTES.put(...)` per option and
`server/v2/store.py` mints `route_id = uuid.uuid4().hex[:12]` **per
response** — every `/v2/plan` POST re-issues every id. The
engine-first paint (`planEngineFirst`, `fast:true`) and the full plan
(`planOptions`) are separate POSTs, so the lookup always missed →
`setSelected(0)`. Index 0 is the ranked-first row = the recommended
card. Any pick on the engine rows (bike/car, the only ones painted
early) was silently re-pointed at the recommendation when the full plan
landed — a beat later, while the sheet still showed a pick window.
Start then read `options[0]` and launched the recommended mode.

**2. The remembered pick could lag one commit.**
`pickRef` was mirrored from state in a `useEffect`; a card tap landing
between the state commit and the effect run was invisible to `show()`,
widening the same failure window.

Start itself read `options[selected]` correctly — the corruption was
upstream, in what `selected` held.

## The fix (minimal — state read, not a sheet redesign)

- `src/components/shell/types.ts`: `sameOption(a, b)` — identity across
  plan responses = `mode` + `alternative_index` + `stations.board`/`alight`
  + `via_names`. ETA/dose/`label`/`engine`/`tag` move between calls and
  are excluded. `preserveIdx(prev, opts)` — the same option's new index,
  else `0` (ranked first = the recommended default).
- `useShellFlow.ts`: `setOptions`/`setSelected` are now `useCallback`
  wrappers that update `pickRef` **synchronously** at the write, then
  call the real state setters; the mirror `useEffect` is gone. `show()`
  calls `preserveIdx(pickRef.current.opts[pickRef.current.sel], opts)`
  instead of the route_id lookup.
- No change to ranking, card rendering, `onSelect(i)` wiring, or
  `startNav` — it still reads `options[selected]`, now a value the pick
  actually survives into.
- `src/nav/test-runner.mjs`: define `globalThis.__DEV__ = true`
  (Metro injects it; Node doesn't). Pre-existing harness fault — async
  callbacks hitting a bare `__DEV__` threw after the suite ended,
  exiting 1 with all tests green. Now the full 68-test suite runs, exit 0.

## Evidence — both paths

Unit (`src/nav/pick.test.ts`, 7 tests under the nav runner):

- pick-bike on engine rows → full plan lands → `preserveIdx` = bike's
  new index (was: forced to 0 by the route_id miss). **pick→Start
  launches the picked mode.**
- no pick → `preserveIdx` = 0 = `recommended` row. **no-pick→Start
  launches recommended — unchanged default.**
- pick whose option vanished from the new set → 0 (recommended).
- re-plan swap keeps a transit pick (`stations` match across fresh
  route_ids).
- `sameOption` unit edges: corridor alternatives of one mode stay
  distinct via `alternative_index`/`via_names`; different alighting
  stations ≠ same option.

Receipt attribution — **already tracks the launched mode**; proof:
`App.tsx` passes `NavSession option={options[selected]}`; `NavSession`
derives `modeLabel`/`mode` from that `option` prop; worst/alt
comparisons exclude `o !== option` — the receipt compares exactly the
option Start launched, never the stale "usual".

## Gates

```
cd Mobile && npx tsc --noEmit      # clean
cd Mobile && npx expo lint         # clean (0 errors, 0 warnings)
cd Mobile && node src/store/test-runner.mjs   # 13 pass, 0 fail
cd Mobile && node src/nav/test-runner.mjs     # 68 pass, 0 fail, exit 0
```

Never deployed; no POSTs beyond the plan/reroute GETs the app already
makes.
