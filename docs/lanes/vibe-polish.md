You are the vibe-polish lane for ALive-108 — the craft layer, not the structure. The owner keeps saying the app "still looks a little odd — not giving vibe" even after the dosimeter rebuild landed the right skeleton. Deliver: a focused visual-quality pass on the home + journey surfaces that a real eye would call expensive, plus before/after proof on device.

Repo: <owner>/Delhi-Air-108, branch base/v2 (pull latest — OTHER LANES are live in Mobile/: hi-locale touches strings.ts, first-open touches the launch path — pull+rebase RIGHT before push, keep your diff scoped to styles/visual props so rebases stay trivial). App: Mobile/ (Expo RN SDK54). This macOS box can't emulate Android — build the iOS dev client on the iPhone-17 sim (see Mobile docs + prior lanes' sim-driving notes; `xcrun simctl location <UDID> set 28.6315,77.2167`) for screenshots, OR attach clear code-diff evidence if sim work is blocked.

HARD RULES
- Push code only — never deploy. NEVER POST /v2/feedback, /observe, /v2/trip to live.
- `npx tsc --noEmit && npx expo lint` before push. Never hand-edit android/ios/ generated dirs.
- STRUCTURE IS FROZEN: no new cards, no removed cards, no re-order, no new data calls — the dosimeter skeleton (dose hero / the move / your day / days ahead / how you felt / budget) is the owner's approved shape. You are tuning how it LOOKS, not what it shows.
- Register stays: serif display (Fraunces) + mono data (Plex) + hairlines + muted CPCB palette + paper. No new colors, no gradients, no shadows-for-shadows-sake, no emoji icons, no cards-within-cards.
- No string edits — hi-locale owns strings.ts this hour (use existing t() keys only).
- Nothing fake: every visual claim must still be backed by live data; if a polish hides a stale/empty state that was honest, revert it.

MANDATE — the craft problems to hunt (verify each visually, don't assume):
1. **Hierarchy contrast**: does the dose number visually OWN its card? Labels should recede (ink3, letterspaced, smaller), the hero figure should carry the serif weight. Check the actual rendered sizes vs design-refs.md intent.
2. **Spacing rhythm**: are section gaps/margins on a consistent scale (4/8-pt rhythm)? Cards that crowd or float = the "odd" feeling. Normalize to a rhythm.
3. **Elevation depth**: paper-on-paper needs a consistent elevation story — hairline + soft shadow on cards, not flat fill. Audit which surfaces have which depth treatment and unify the story.
4. **Press/hover states**: every tappable should visibly respond (opacity/scale/spring) — audit the home CTAs, "Where to?", check-in chips, budget picker, quiet links. Missing press feedback reads dead.
5. **The band-wash moments**: where does the app let air quality TINT the surface (hero numeral color exists — where else can the band whisper without new colors)? e.g. the day-arc bars should already carry band color — verify it renders.
6. **Type details**: letter-spacing on labels, mono tabular-nums on figures, line-height on serif multi-line — the register's fine print.
7. Measure: screenshot each surface BEFORE your change on the sim, then AFTER, same scroll position — attach the pairs. Report which changes moved which felt problem.

REPORT: the before/after pairs, each defect found + the fix, what you deliberately left alone, any place the register itself fails on-device (fonts rendering? hairlines invisible at 1px?) — report it honestly even if unfixable.
