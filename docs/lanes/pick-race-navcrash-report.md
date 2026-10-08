# pick-race + nav-crash lane report — base/v2

**Verdict: both bugs root-caused to code (no native crash anywhere); both fixed, all gates green.**
Evidence level: unit-tested state machines + source-grep invariants + iOS-sim drive of the shared JS pick path (the Android box with AVD `demo` and `alive-63b7ed4.apk` belongs to the demo-video lane; this macOS box has no `/dev/kvm` — iOS sim is the rig here, and both fixed classes live in shared JS).

## 1. PICK-RACE — the t104–105 s bounce to an empty Where-to

### What the drive showed
The tap landed exactly as results swapped stale→fresh rows; the app returned to an **empty** Where-to (chooser never mounted), and scripted BACK-press recovery then ejected to the launcher (~45 s trimmed).

### Mechanism — four compounding holes, all in JS

1. **Rows are index-keyed and gestures resolve at release.** `t0rows.map((p, i) => renderPlace(p, "t0-"+i))` / `srv-…` keys mean a stale→fresh swap reuses the same fibers with new props. A touch that lands on row *A* (touch-down) and releases after the swap fires **row B's** `onPress` closure — the pick commits a place the user never saw, or drops entirely if the pressable unmounted mid-gesture.
2. **The pick's confirm chain spans seconds of async work with no concurrency guard.** `useShellFlow.pick()`: `dismissThen` (≤500 ms keyboard wait) → `setTo(p)` → `await posNow()` (up to 9 s). During that window the sheet stays mounted and **still tappable** — a second tap started a second full pick on top of the first; whichever tail resolved last won `setPhase`, and a failed tail could steer a journey that no longer belonged to it.
3. **A stale tail could reopen the sheet EMPTY.** The failure path (`locPickFailed`) ended in `setPhase("search")` unconditionally. If anything had moved the phase meanwhile — back-press to idle, `choose_on_map`, a second pick already advancing to compare — the write **remounted** `SearchScreen` (`visible` flips false→true → `SearchSheetInner` remounts with `q=""`, empty recents). That *is* the empty Where-to on camera: not the user's failed pick in place, but a stale continuation reopening a fresh sheet over whatever surface had taken over.
4. **`setPhase` defers through `holdMapDrawThen`** (mount-vs-draw SIGSEGV class), so on emulator/sim the state write lands later — a tail reading `phase` state could see a surface that had already been superseded by a requested-but-not-yet-committed one.

### The fix

- `Mobile/src/components/shell/pickGate.ts` (new): `pickTailGate(surface, "stay"|"advance")` — pure predicate. `stay` writes (failed/too-close re-arm + notice) require `"search"`; `advance` tolerates `"search"`/`"compare"` (the journey already moved in this pick's own direction); every other surface denies the write.
- `useShellFlow.ts`:
  - `phaseRef` — mirror of the last **requested** phase, written inside `setPhase` *before* the deferred commit (the functional-update form is resolved eagerly so the ref stays true).
  - `pickSeq` — each `pick()` captures `++pickSeq.current`; after the `await posNow()` window a `seq !== pickSeq.current` bail kills superseded tails outright — they write **nothing** (not even the notice).
  - All post-await journey writes route through `pickTailGate(phaseRef.current, …)`: failed-fix re-arm only while search still owns the surface (else the tail just clears its notice and returns); the advance write only while the journey is still in this pick's lane.
  - `pickDone` counter bumps in `finally` on the *latest* pick — the sheet's latch signal that the confirm window ended.
  - `invalidatePicks()` — bumped by `openSearch`, `onPickPlace`, and `choose_on_map`/`placePickSlot` paths in `App.tsx`: any deliberate surface change makes an in-flight tail dead.
- `SearchScreen.tsx`:
  - `pickAtPress` — every tappable row captures its `PlaceResult` at **`onPressIn`** (the identity under the finger at touch-down); `pick()` commits the captured identity if it's <800 ms old — the release's fiber props are no longer trusted after a mid-gesture swap. A capture that never became a press ages out so `submit` and action-bar picks can't inherit it.
  - `committing` latch — a second row tap, long-press, or action-bar press during the confirm window is held, not raced; released by `pickDone` from the shell (new prop).
  - `App.tsx` `onSearchSelect` current-location failure path gates `setPhase("search")` on `phaseRef.current === "search"` too — same bounce class through a different door.

What the user now sees in the exact beat: tap lands mid-swap → the **tapped** row's place commits (press-in identity), sheet latches for the confirm → compare mounts with that destination, or — if the fix fails — the **same mounted sheet** keeps the query and shows the honest notice. There is no path back to an empty Where-to.

## 2. NAV-CRASH — the drawer→settings→Trips eject to launcher

### Root cause — not a crash, an OS-level exit

`App.tsx` BackHandler dispatcher closes overlays topmost-first (`vehicle→settings→ledger→delhi→layers→sidebar→mapPickArmed→compare→nav-guard→idle-home`) and then ended in a bare **`return false`**. On Android `false` defers to the OS, which **finishes the activity** — the app exits cleanly to the launcher. The report's "a back-press chain had already ejected the app" is exactly this: recovery BACK presses (after the pick bounce) walked past the root and the last one exited. On iOS `hardwareBackPress` never fires — consistent with this never appearing on iOS drives.

It is **not** the known SIGSEGV classes — those are iOS-sim-only mount-vs-draw/heap-stomp failures (`sigsegv-mount-fix-report.md`, `sigsegv-coldfix-report.md`), and this box's rig can't run the Android AVD anyway (no `/dev/kvm`). A native crash would also have left `FATAL EXCEPTION`/tombstone lines in logcat; the take instead shows the launcher with the app simply gone — a finish, not a kill.

### The fix — double-press-to-exit (the standard Android pattern)

At the dispatcher root (`App.tsx`), a first BACK now shows `ToastAndroid` `t("backToExit")` ("press back again to exit" / "बाहर निकलने के लिए फिर से back दबाएँ") and returns `true` (swallowed); only a second press within 2 s returns `false` and actually exits. A stray back in a scripted-fast demo can no longer kill the app; a real user still has an exit.

## Gates

| gate | result |
|------|--------|
| `npx tsc --noEmit` | **clean** |
| `npx expo lint` | **clean** |
| `node src/nav/test-runner.mjs` | **100/100** (incl. new `pickRace.test.ts`: gate predicate truth table, stale-tail/supersede/closed-surface simulations driven through the real `pickTailGate`, source-grep wiring checks for `phaseRef`/`pickSeq`/`pickAtPress`/`committing`/double-press-exit) |
| `node src/store/test-runner.mjs` | **16/16** |
| `node src/api/test-runner.mjs` | **37/37** |
| `node src/offline/test-runner.mjs` | **16/16** |
| `drawHold.test.ts` updated | regex now matches the resolved-variable commit (`setPhaseState(next)`) + asserts `phaseRef` is written before the deferred commit — same draw-hold invariant, strict superset |

## iOS-sim evidence (the rig that exists here)

Dev-client build of this branch on iPhone 17 sim (iOS 26.5, `expo run:ios`, `EXPO_PUBLIC_API_URL=http://65.2.28.40`), frames in `docs/lanes/pick-race-navcrash-shots/`:

| frame | what it proves |
|-------|----------------|
| `01-results.png` | "connaught" → 11 real rows (t0 + server tiers merged) |
| `02-pick-tooclose-same-sheet.png` | **the core fix**: a row pick committed and FAILED (`pickTooClose` — sim's fix landed ~10 m from Connaught Place) → the **same mounted sheet** keeps "connaught" in the field and the full list, with the honest notice row — not an empty Where-to |
| `03-pick-advanced-outside.png` | next row tap (after `pickDone` unlatched) committed **"Connaught Lane"** → advanced to compare → `/v2/plan`'s honest "outside Delhi NCR" sheet (sim's fix is SF). The latch releases for a follow-up pick; the journey advances exactly once |
| `04-reopen-recents.png` | re-opened search shows "Recent · Connaught Lane" — `addRecent` persisted the picked identity; recents rows carry the same press-in capture |
| `05-repick-compare-entering.png` | recents-row pick committed → "checking every way there…" compare entering — second full cycle works |
| `06-outside-answer.png` | second cycle resolved to the same honest outside answer — no empty-sheet bounce anywhere in the walk |

The BackHandler fix is Android-only code (`hardwareBackPress` cannot fire on iOS) — its evidence is the `pickRace.test.ts` wiring check + code review; **the on-device Android re-verify belongs to the next KVM-box lane**.

## Honest notes

- The pick-race fix is defense-in-depth across the whole tap→compare window; the exact frame-level sub-mechanism (which of row-swap / dropped-press fired first in t104) is inferred from the take + code, not re-recorded — the raw `t18.mp4`/`drive.py` live on the demo lane's box, not in git.
- Double-press-exit cannot prevent a determined 2-presses-in-2s exit — by design (the app still needs a real exit). It removes the *accidental* eject that scripted fast walks hit.
- `onPressIn` capture window is 800 ms — covers press-in→press release across any plausible list-swap latency; a press that never becomes a release can't poison the next pick.
