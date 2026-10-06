# Lane report: motion-v3 — the FEEL pass

**Date:** 2026-10-06 · **Lane:** `docs/lanes/motion-v3.md` · **Commit:** `5add56a` on `base/v2` (rebased over the lead's design-v3 sweep `004d616` — one HomeScreen conflict, resolved as below)

**Scope:** FEEL only — springs, a scrub gesture, one stagger. Zero colour/font/radius/layout edits; where the lead's sweep changed the paint underneath me (tonal cards, `surface2` pills), the extracted copies follow the new register.

## The primitive: `src/components/PressSpring.tsx` (new)

Wraps any child in an `Animated.View`: `onTouchStart` springs scale → 0.96, `onTouchEnd`/`onTouchCancel` spring home (`damping 12, stiffness 180, mass 1, useNativeDriver: true`). The handlers sit on the wrapper's bubble phase, so wrapped children keep their own `Pressable`s, haptics, hitSlop and a11y — no prop surgery at call sites. `style` lands on the scaling surface so margins/flex live where they belong. Under Reduce Motion the spring never fires — the wrapper is visually inert. `scale` prop defaults 0.96, usable for subtler dips.

Native-driver note: every value here is a single `Animated.Value` on `transform`/`opacity` — clean native graphs, no `Animated.add` mixing, so `useNativeDriver: true` holds everywhere (unlike Sheet's drag translate, which stays JS by design).

## What got motion

| Surface | Change |
|---|---|
| **CompareSheet — option cards** | Card dips 0.96 on press. Selection is now an `Animated.View` absolute-fill overlay (the old `cardSel` paint: accentWash + accent edge) crossfading on a spring (damp 18, stiff 260, mass 0.7) — a pick *arrives* instead of snapping; the accent border fades in rather than re-sizing, which fits the new "hairlines = selection" register. |
| **CompareSheet — CTAs** | vehicle chip, leave-later row, turn-by-turn ghost, Start, and both retry buttons each wrapped in `PressSpring` (chip hugs its content via `alignSelf`). `pressFx` retired inside the sheet. |
| **DepartGraph — the scrub** | The whole bars row is now the scrub surface: `onMoveShouldSetResponder` claims the gesture only when a drag reads horizontal (>8 px, dx>dy — a vertical first-move loses to the sheet's ScrollView, taps never reach the gate). While the finger travels, `locationX` maps to the hour and `setInnerSel`+`onSelectHour` fire once per hour crossed — the "leave HH:MM ≈ N µg" caption follows the finger live and the selection persists on release (the hint *settles*, no commit step). Per-cell `Pressable`s remain for taps/TalkBack. Everything gated on `onSelectHour` being wired — untwired mounts are byte-identical. |
| **ReceiptSheet — stat tiles** | Each tile is a `StatTile`: spring up + fade on open, `delay: 220 + i·80 ms` behind the previous tile (damp 15, stiff 210, mass 0.9 — settles ~250 ms, no overshoot). Done/Share/How-we-got-this/Save all get `PressSpring` (Done keeps `flex:1` on the wrapper so the row geometry is unchanged); `s.pressed` gone. |
| **CheckinSheet — facet pills** | Pills dip via `PressSpring`; selected fill is an absolute-fill overlay (old `optSel` paint) spring-crossfading in/out (damp 16, stiff 240, mass 0.7). |

## What did NOT get motion — deliberately

- **`Sheet` itself** — already has its own enter spring + drag-dismiss PanResponder; wrapping it would double-own the gesture.
- **`ModeRow`, `MapButton`, the depart-row's parent CTA in `ui.tsx`** — lead's files, untouched by this lane.
- **Bar heights in DepartGraph during scrub** — bars don't animate per-hour on purpose: the caption + selected-column brighten carry the feedback; re-laying bars per pixel would jank the hit zone.
- **No entrance choreography on cards/steps** — doc 20 §6: physics on real interactions only, no decorative motion. The stagger exists only where the spec put it (the receipt — earned content arriving).
- **`pressFx` elsewhere** (HomeScreen CTA etc.) — outside this lane's file list.

## useReduceMotion coverage

Every new animation path calls `useReduceMotion()` and collapses to instant/settled state: `PressSpring` skips the spring entirely; `OptionCard`/`Pill` selection values `setValue` direct; `StatTile` mounts already-visible. The depart scrub isn't an animation — it's gesture plumbing — and stays enabled (it's interaction, not motion decoration); it fires no springs.

## A judgement call to flag

The spec names `CheckinSheet.tsx` but that file didn't exist — the symptom-lens "checkin" card was `LensCard` living inside `HomeScreen.tsx` (the lead's file). Rather than skip the spec item, I extracted `LensCard` verbatim into `src/components/shell/CheckinSheet.tsx` and swapped the tag — a 5-line HomeScreen diff (one import, one tag swap, removed style block). Markup, props, and paint are identical; the pills inside got the new `surface2` tonal paint from the lead's sweep during the rebase. If the lead prefers the card to stay in HomeScreen, `CheckinSheet.tsx` inlines back cleanly.

## Gates — all green at `5add56a`

```
cd Mobile && npx tsc --noEmit     ✔
npx expo lint                      ✔
node src/store/test-runner.mjs     ✔ 18/18
node src/nav/test-runner.mjs       ✔ 70/70
```
