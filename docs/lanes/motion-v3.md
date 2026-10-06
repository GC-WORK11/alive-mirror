# lane: motion-v3 — the "smoother" pass (press springs + scrub)

ALive-108. Repo <owner>/Delhi-Air-108, branch base/v2. Read
docs/20-design-research.md first — the new register you must not regress.

Owner's words: "something that is very smoother when as a user I'm
experiencing... more interactive things". Google's SOTA answer (Material
3 Expressive): every touch gets SPRING physics — no timing curves on
press feedback.

## Your files (yours alone — the lead owns HomeScreen/DelhiToday/Ledger)
- NEW `Mobile/src/components/PressSpring.tsx` — the shared primitive:
  wraps any child in an Animated.View; onPressIn → scale 0.96 via
  withSpring-like RN Animated.spring (damping ~12, stiffness ~180, mass
  ~1, useNativeDriver true); onPressOut → back to 1. Keep it tiny
  (RN Animated, no reanimated — not installed).
- `Mobile/src/components/shell/CompareSheet.tsx` — option tiles get
  PressSpring; selected-state transitions animated (opacity/spring).
- `Mobile/src/components/DepartGraph.tsx` — the depart strip becomes
  finger-scrubbable: on touch-drag over the strip, highlight the
  touched hour and live-update the "leave HH:MM" hint; on release the
  hint settles. If the component already exposes hour values per x
  position, wire pan gestures with RN's responder API (no new deps);
  else add a transparent scrub row of hour cells.
- `Mobile/src/components/shell/ReceiptSheet.tsx` — stat tiles land with
  a short stagger (spring up+fade ~80ms apart) on open.
- `Mobile/src/components/shell/CheckinSheet.tsx` — segment pills get
  PressSpring + selected fill animates.
- `Mobile/src/components/shell/TravelCta`-like CTAs in YOUR files only.

## Hard rules
- useReduceMotion() from src/a11y: every spring/stagger skipped when set.
- No new dependencies. RN Animated only (reanimated is NOT installed).
- No color/font/layout changes — the lead owns those in the same hours.
- npx tsc --noEmit + npx expo lint clean before committing.
- Keep feel subtle: scale ≥0.96, durations <300ms, no bounce overshoot
  >1.05 — springs should feel physical, not playful.
- Commit to base/v2 as "motion v3: <what>". Report →
  docs/lanes/motion-v3-report.md with what got springs, what didn't
  (and why), and the useReduceMotion coverage. Tell me when done.
