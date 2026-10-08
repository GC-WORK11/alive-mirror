# Lane report — home polish (`HomeScreen` hero)

**Owner brief:** *"app HOME feel 'sexy/orgasmic'… POLISH PASS (small, real, verified — NOT a rewrite): numeral animates value changes (~600ms, no layout jump); band ink transitions cross-fade; balance the felt line + provenance; tracked-caps → normal case; field preview breathing if tasteful. Nothing moves position-wise — pure feel."*
**Design Read (per `docs/design/taste-skill/*/SKILL.md`):** instrument-grade editorial hero — warm neutral base, band colour only where it means air. Polish = deepen the existing grammar, never decorate.
**Files touched:** `Mobile/src/screens/HomeScreen.tsx`, `Mobile/src/ui.tsx` (one component signature — nothing else).
**Verified on:** iPhone 17 sim (iOS 26.5, `EDD9B083…`) running the dev client against a local `:8317` band-drive proxy (rewrites `pm25_ambient` per request → bands flipped live without touching prod).

## What changed, and proof

| # | Change | Where | Proof |
|---|--------|-------|-------|
| a1 | Hero numeral re-tweens at **600ms** (was 480) and mounts tween on open | `CountUp` (`ui.tsx`) → `Animated.Text`; `duration={600}` on both hero call-sites | `shots/v4-numtick-clip.mp4` — launch sweep `9→45→76→90→110→118→119→120`; `shots/a4-midtick.png` caught mid-value |
| a2 | **Band ink cross-fades ~600ms** instead of snapping — numeral colour, felt word, band square, BreathLine share one fade clock | new `useInkTone()` hook (`HomeScreen.tsx` ~L420), the MoodCanvas pair-fade grammar one level down | `shots/v2-crossfade-clip.mp4` — severe→satisfactory flip: ink visibly melts red→amber under a held "250", then the new value lands |
| a3 | `heroBandSq` + felt word now `Animated.View`/`Animated.Text` so they ride the ink fade | felt row | same clip — square + word melt together |
| b  | Optical rhythm under the numeral, +2–4px only: felt row 12→14 · ref 6→9 · prov 8→10 · band scale 16→18 | `ss.heroFeltRow/heroRef/heroProv/heroScale` | compare `shots/b2-good-40.png` ↔ `shots/a1-good-40.png` — airier read, nothing moved |
| c  | Last positive tracking on the hero removed (`µg` unit `letterSpacing: 0.5`) — labels were already sentence/lowercase elsewhere | `ss.heroUg` | visual pair above |
| d  | Sparse-arc live dot breathes — 5.2s sine `1→0.35→1` (JS driver: svg props aren't view styles), skipped under Reduce Motion | `SparseAirArcInner` (`APulse` = animated `Circle`) | visible on sparse days where the arc mounts |

Nothing moved positionally — all deltas are opacity/colour/duration/single-digit margins.

## Found & fixed in verification (would have shipped broken)

- **Native↔JS driver clash.** `BreathLine` ran its opacity loop `useNativeDriver: true` while receiving the new JS-side colour interpolation — RN migrates the whole animated node to native and `useInkTone`'s timing throws `Attempting to run JS driven animation on animated node that has been moved to "native"` (red-boxed on first AFTER boot). Fix: breath loop → `useNativeDriver: false` (one 2px hairline — cost is nothing, and it keeps the node single-domain). Caught by the sim pass, not by tsc.
- **Hook order.** Both `useInkTone` calls sit *before* the `if (!data)` skeleton return — fixed call order on every render.

## Honest caveats (observed on tape, not hidden)

1. **On a live ambient flip the numeral lands as a beat-late step, not a visible sweep** — the rAF tween starves during the poll tick's concurrent `/grid` burst (proxy log showed 11 tile hits on the same tick). Ink fade still melts visibly (~2–3s effective under that load vs the 600ms design). The 600ms sweep itself is verified clean on mount (`v4-numtick-clip.mp4`, idle JS). Follow-up idea if the owner cares: drive `disp` off an `Animated.Value` listener or defer the field-tile fetch a beat after a band change.
2. **One ~0.4s stale-value flash** seen on a flip (120-brick → 40-olive → 120): a straggler re-render replayed the pre-update ambient state. Upstream of this diff (the `aqiPoll` write path sets `ambientUg`/`aqiField`/`ambientMeta`/`nearestKm` in one fetch callback — the racing writes are pre-existing); flagged, not chased.
3. **CountUp micro-note:** `prev.current` only updates when a tween *completes* — a cancelled tween leaves `from` stale and the next change snaps. Didn't rewrite the component (polish lane), but it's the mechanism behind caveat 1.

## Gates

`npx tsc --noEmit` 0 errors · `npx expo lint` clean · `node src/{store,nav,api,offline}/test-runner.mjs` 99 + 100 + 37 + 16 pass.

## Evidence

`home-polish-shots/` — before: `b1-severe-250.png`, `b2-good-40.png`; after: `a1-good-40.png`, `a2-severe-250.png`, `a3-moderate-120.png`, `a4-midtick.png`; clips: `v4-numtick-clip.mp4` (numeral ticking), `v2-crossfade-clip.mp4` (ink melt).
