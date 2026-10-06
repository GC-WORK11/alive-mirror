# Lane report: search-crash-fix — kill the residual SIGSEGV for good

## Verdict
FIXED + PROVEN. Removed ALL programmatic focus from the search sheet —
the keyboard now rises only on the user's own tap (Apple/Google Maps
grammar: recents render on open, input focuses on tap). **0 crashes in
15/15** map→pan→pan→"Where to?" cycles post-fix, vs **1 SIGSEGV in 7
identical opens (~14%)** on the same loop pre-fix. Search itself is
unchanged once the keyboard is up (query → results verified live).

## The crash being fixed (from ios-journey-overnight)
- `runningboardd` exit: `signal(2) code:SIGSEGV(11)`, pid 9659, 14:02:55
  sim-time, ~2 s after opening "Where to?" over a map panned ~15 s prior.
- Death signature identical to docs/lanes/search-crash-report.md:
  `KeyboardArbiter: TX focusApplication (peekAppEvent) stealKB:Y` +
  UIEvent/gesture dispatch stream → dead. No `.ips` (sim-app SIGSEGV).
- The d791879 gate (`runAfterInteractions` → `inputRef.focus()` at +350 ms,
  +1400 ms retry latch) WAS in the checkout — and still fired the crash.
  Why it can't win: `runAfterInteractions` only waits on RN's interaction
  queue, which says nothing about MapLibre's native draw thread. A map
  still streaming tiles after a pan is invisible to the queue, so the
  responder handoff (`becomeFirstResponder` → `stealKB`) lands mid-draw →
  Hermes GC heap stomp. Any *timed* focus keeps this window open.

## Fix (Mobile/src/screens/SearchScreen.tsx)
- Deleted the `focusField`/`foc`/`refoc`/`kbShown` machinery entirely —
  no `focus()` call exists anywhere in the sheet.
- `autoFocus` remains absent; the `<TextInput>` gets the keyboard only via
  the native responder path on user tap — a tap is itself proof the
  scene settled.
- `closingRef` removed (dead once focus went); `bodyReady` two-frame mount
  split kept (that's the *mount-commit* mitigation, unrelated to the
  keyboard path); `dismissThen` keyboardDidHide close kept.
- `searchSpring.test.ts`: the old test *required* the gate — replaced with
  the stronger invariant: zero `inputRef.focus()` calls and zero
  `autoFocus` props in the sheet (regression guard).

## Baseline → after
| | opens on `map → 2 pans → "Where to?"` | SIGSEGV |
|---|---|---|
| pre-fix (this session, d791879 gate live) | 7 | 1 (14:02:55) |
| post-fix | 15 consecutive + 1 functional | 0 |

Post-fix extras verified in the same runs: sheet opens with NO keyboard
every time (bottom chips visible), keyboard raises on field tap, typing
"Connaught" streams real results (Connaught Place 2.2 km et al.), back
returns to map cleanly. `sim log show` over the whole verify window:
zero signal exits (the only process exit is my own `simctl terminate`
for the bundle reload — `code:force-quit`, expected).

## Gates
- `npx tsc --noEmit` clean; `npx expo lint` clean.
- `node --test` on `src/nav/searchSpring.test.ts`: 2/2 pass (spring stays
  JS-driver + no-programmatic-focus invariant).

## Caveat / honest limit
The class is a timing race: 15 clean opens at a ~14% pre-fix rate is good
evidence, not a proof of impossibility (~22% chance of a lucky streak at
that rate alone — hence the removal fix, which eliminates the trigger
entirely rather than narrowing the window). The stronger guarantee is
structural: no code path calls focus/becomeFirstResponder anymore, so the
responder handoff can only ever occur on a user-tapped, already-settled
field. The remaining mid-draw teardown class (compare/receipt closes) is
the app's existing documented mitigation set, untouched here.

Commit: base/v2 (pushed with this report). Prior art: d791879 (gate),
a85517f revert, docs/lanes/search-crash-report.md, ios-journey-overnight-report.md B1.
