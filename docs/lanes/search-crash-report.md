# Lane report: search-crash — the stage-risk segfault

## Verdict
ROOT CAUSE FOUND + FIXED + PROVEN. The search sheet's autofocus — a
`focus()`/`becomeFirstResponder` responder handoff fired inside the
mount-commit window — is the segfault trigger. Reopening the sheet
while a map/camera/compare transition is still live made that handoff
land on a mutating Hermes heap → GC stomp → SIGSEGV (matches the
day-in-life lane's lldb diagnosis: Hermes GC heap stomp, 'Where to?'
sheet). Second contributor: a85517f's `useNativeDriver:true` flip on
the sheet's enter spring — same crash class the file's own comment
warns about — reverted to the JS driver. Fix: gate every `focus()`
behind `InteractionManager.runAfterInteractions` so the handoff only
lands after the enter spring + commit queue drain. Post-fix proof:
36/36 clean opens on the crash path (24 warm relaunch + 12 cold
install) vs ~1 crash per 2–4 opens pre-fix on the identical loop.

## Repro
Plain open-loop (~40 opens, relaunches, wipes) never reproduced — the
shoot's "6× consecutive" needed the real gesture: reopen 'Where to?'
while the previous close's compare-mount + camera transition is still
in flight. Drive loop (simctl taps + probe screenshot discriminator):

    tap 'Where to?' pill → sheet → paste 'india' → tap first result
    → compare mounts, camera transition starts
    → tap 'Where to?' again at +700 ms (during transition)

Pre-fix result on this loop: crash within 2–4 iterations, every run —
4 logged kills (23:22:04, 23:52:38, 23:53:22, 23:54:07), plus earlier
repros. Consistent with 6/6 once the shoot did search → pick → search.

## Log evidence
- `xcrun simctl spawn log show` forensics per pid: every dead process's
  last lines are UIKit `EventDispatch`/`KeyboardArbiter` rows
  (`TX focusApplication (peekAppEvent) stealKB:Y`) — death lands right
  where the responder/keyboard handoff happens.
- No .ips is ever written for sim-app SIGSEGV; `launch --console-pty`
  drops the fault text; lldb attach masks the race entirely (40/40
  clean under attach — timing-sensitive, consistent with a GC race);
  MallocScribble+MallocGuardEdges makes it fire in ~2 iters (deterministic
  heap-stomp shape: corruption survives until the next GC pass touches it).
- Bisect, same hot loop:
    autofocus disabled (focus() calls stubbed) → 20/20 opens clean
    autofocus enabled, ungated (350 ms/1400 ms timers) → crash in ≤4
  → the responder handoff is the trigger; mount churn alone is clean.

## Root cause
`SearchScreen` mount effect fired `inputRef.current?.focus()` on a
350 ms timer (+1400 ms kbShown-latch retry). On a reopen during a live
map/compare transition, Fabric is still committing the sheet and the
previous close's responder/keyboard teardown is still settling; the
native `becomeFirstResponder` handoff into that window mutates
JS-managed objects off the JS thread while Hermes GC is moving them →
heap stomp → SIGSEGV. The sheet's own comment already documented the
same class for `autoFocus` at mount; the timer only moved the race.

Companion fix (same crash class, reverted): a85517f flipped the sheet's
enter spring to `useNativeDriver:true`; the file explicitly warns
native-driven springs segfault this stack (native anim-driver node
graphs mutate JS-managed state from the render thread). Back to `false`.

## Fix
`Mobile/src/screens/SearchScreen.tsx`:
- enter spring `useNativeDriver:false` (revert of a85517f's flip here).
- all `inputRef.current?.focus()` calls now run inside
  `InteractionManager.runAfterInteractions` via a `focusField()`
  helper — the responder handoff lands only after the enter spring and
  the commit queue drain. Timers (350 ms + 1400 ms kbShown latch) and
  the closingRef guard unchanged; autofocus still fires — verified:
  field is first responder on open (paste lands, keyboard engages).
Regression: `Mobile/src/nav/searchSpring.test.ts` asserts both the JS
driver flag AND that no `focus()` call exists outside the gate — the
perf A/B or a redesign can't silently re-open the race.

## Proof
Post-fix, same drive loop, zero crashes:
- warm relaunch: 24/24 opens (12 hot iterations)
- cold install (uninstall + install + launch): 12/12 opens
- total 36/36 ≥ the required 20, all on the crash path (reopen during
  live transition), autofocus fully enabled. Intermittency: none seen.

Gates: `npx tsc --noEmit` clean · `npx expo lint` clean ·
`node src/store/test-runner.mjs` 18/18 · `node src/nav/test-runner.mjs`
70/70 (incl. the new regression test).

## Flags
- **Demo APK needs one rebuild** — this lands after binary 0b11123;
  the demo phone carries the old binary until respun.
- app-overhaul-v2 lane: the diff is ~20 lines inside
  SearchScreen.tsx's mount effect + import + one spring arg — no
  visual/structure change, so a redesign can land over it; any
  replacement of the mount/effect region MUST keep both invariants the
  regression test enforces (JS-driver spring, gated focus).
- Sim-only: same class could exist on device; the interaction queue
  drain guarantee is stack-wide, so the gate is the right fix either
  way — but device smoke before the shoot is still worth 5 minutes.
