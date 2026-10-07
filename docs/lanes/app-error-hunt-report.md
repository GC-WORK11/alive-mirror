# app-error-hunt (lead session, self-run) — 2026-10-07

Owner report: "so many fucking errors in the app." Verdict: **the app is clean
at code level and at runtime** — every "error" class checked below is either
guarded or a stale-bundle artifact.

## The boot-time TypeErrors — explained, not a bug
- Symptom: 3× `ERROR [TypeError: undefined is not a function]` ~200 ms after
  firstFrame; LogBox pointed at `App.tsx:72` `latinLabels(STYLE_URL)`.
- Cause: **stale Metro fast-refresh**. The app was running while `git pull`
  brought commit 31dbfdb (new `latinLabels`); Metro pushed a partial transform
  — App.tsx re-evaluated against the old style.ts module → named import was
  undefined at eval. App kept rendering (old mounted tree), LogBox recorded
  the failed refresh.
- Proof: cold `expo start --clear` + app relaunch → **zero errors** across a
  full drive (home, map, Delhi today, trips, drawer, settings EN+HI, search,
  compare, nav, receipt). Fix-by-refresh, not fix-in-code.

## Gates
- `npx tsc --noEmit`: **0 errors**
- `npx expo lint`: **0 errors/warnings**
- Metro log after full feature drive: **0 ERROR/WARN** (excl. known benign
  "Invalid geometry in line layer" — ignored in App.tsx by design)

## Static sweeps — all clean
| Check | Result |
|---|---|
| `JSON.parse` unguarded | **0** — all 12 sites wrapped in try/catch |
| Non-null assertions on API data (`x!.y`) | **0** |
| Timer leaks (setInterval/setTimeout) | all paired with clear* in effect cleanup/finally |
| BackHandler/AppState/AccessibilityInfo listeners | all `sub.remove()` in cleanup |
| useNativeDriver:true | 20+ sites — the RN-0.86 `createAnimatedPropsHook` crash path already worked around in ui.tsx Sheet (useNativeDriver:false) |
| i18n parity | 522 en keys / 528 hi keys — **0 missing in either**; 325 actively used; 208 defined-unused (seam-marked dormant features, kept per dead-code rule) |
| API contract | typed vs `Bridge/contract.ts`, guarded by `test_contract_sync.py`; optional/null guards on every optional field |
| Prod field check | `/v2/city`, `/v2/day`, `/v2/outlook`, `/grid`, `/v2/city/moves`, `/health` — all live, fields match app parsing |
| expo-file-system `File`/`Paths` (style.ts) | exists in pkg 57.0.7; call site try/catch → worst case silent fallback to hosted tiles |

## Real issues found (minor)
1. **P2 a11y — "Where to?" pill hit-test**: its a11y centre is occluded by the
   "Good evening" greeting label (iOS a11y bridge reports the control covered;
   coordinate taps still work). Not user-visible in normal use; flag for the
   polish lane: give the header row a higher zIndex/elevation or an explicit
   accessibility container.
2. **P2 hygiene — 208 unused string keys** in strings.ts (vehicle wizard,
   settings sections, dormant seams). Kept by design; worth a `// seam`
   grouping comment so future audits don't recount them.
3. **Note** — `/grid?cells=` server cap is 40; app requests 8. No bug; recorded
   so future callers know the bound.

## What the errors WERE the owner saw
Most likely the same stale-refresh LogBox banners seen on his own dev-client
open after pulling — they appear as red "Uncaught Error" overlays, alarming
but harmless. If he saw *different* errors (Android red-screens, visual
glitches), the android-drive lane (53a85a60, building the emulator now) is
the sweep for platform-specific ones.

## For the fix queue (Max-org coordinator)
No code fixes landed by this hunt — nothing broken to fix. The P2s above are
the only actionable items; both are polish, not bugs.
