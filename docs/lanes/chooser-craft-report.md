# chooser-craft — the from → to → choose beat

**Lane ask:** make the chooser beat feel *sexy, not functional* — owner's
spec: "a nice animation where it puts your from and to location → then
shows two-three ways → then one safest and best path."

## Baseline verdict (driven on-device, iPhone 17 sim, Release build)

Recorded the old beat (`~/chooser-craft/baseline-beat.mp4`, 122 s).
What read *functional*:

- The whole option set painted essentially instantly after the search
  pick — no endpoint moment, no sense of alternatives arriving; the
  camera's `fitBounds` was the only motion, so the trip never read as
  "framed".
- The verdict pill rarely survived: it pinned only when the draw was
  lucky, and the first-run vehicle sheet covered the settle anyway.

## What shipped — a four-act beat (all in `Mobile/src/components/RouteTint.tsx`)

The sexy is choreography only: timing, staging, easing. No confetti,
no color beyond what already means air.

1. **Frame** — before any line draws, a ring breathes once on the origin
   (text ink) then the destination (`pinDest`), ~170 ms apart, anchored
   on the passed `from`/`to` pins (falls back to the winner's snapped
   ends). The endpoint pins themselves now *drop* on mount
   (`EndpointPin` spring in `ui.tsx`: origin pops, destination lands a
   hair later — the map "placing" the trip's two ends).
2. **Alternates** — ≤3 drawable candidates (selected last) trace on at
   an ease-out cadence, ~540 ms apart; each option's spans cascade in 11
   staggered groups so every line gets a felt moment instead of a lump.
3. **Settle** — after a ~300 ms breath, losers dip to hairline (0.18 →
   hairline alternate style) while the winner re-traces itself bold in
   two sweep slices; alternates ease back to their rest weight.
4. **Verdict** — ~260 ms after the winner's weight lands, the pill pins
   at `pointAtFrac(geometry, 0.45)` of the selected route: leaf glyph +
   one honest line — `cleanest and fastest` / `cleanest · {n}% less
   than fastest` / `the cleanest way there` / `the fastest way there` /
   the server's own `reason_line`. ~4.2 s hold, then it fades out so the
   route stays the object.

Total felt beat ≈ 4.5–6 s depending on candidate count; reduce-motion
collapses it to the final state.

**Honesty gates kept:** the pill's flash is gated on
`pillReady.current = {text, anchor}` mirrored through a ref, so a stale
closure can never pin a claim the data doesn't back; the Marker renders
`<View/>` when either is missing. Engine-first rows (plan `fast:true`)
carry no honest verdict → no pill until the full plan's own beat — the
pill never lies.

## Why it took surgery, not tuning (the bug found mid-lane)

Beat + swap timers now live in **refs**, not effect cleanups: Effect A
re-runs on every `tint` churn (strips stream in per-option for seconds
after a plan), and a cleanup-owned beat died on the first strip — the
final state simply appeared, which was the "functional" read. A stale
`whenMapDrawFree` callback can't resurrect a dead beat because it checks
the generation before scheduling; the SIGSEGV law is intact (sources,
markers, rings and the pill Marker are always mounted, children swap).

## Verified on-device (Release build, iPhone 17 iOS 26.5)

- `chooser-craft-shots/act0-frame.png` — endpoints marked, map framed,
  no lines yet (the FROM → TO moment reads).
- `act1-candidate-draw.png` — first candidate mid-trace from origin.
- `act1-all-candidates.png` — full set drawn as genuine alternatives.
- `settle-bold-winner.png` — winner bold, alternates hairlined.
- `pill-cleanest-and-fastest.png` — verdict pinned mid-route: leaf +
  "cleanest and fastest" (Connaught Place plan, verdict kind `best`).
- `pill-53pct-lodhi.png` — "cleanest · 53% less than fastest"
  (Lodhi Gardens plan, `cleanestVsFastest`, pct 53 — the honest number
  from `chooserVerdict`, not decoration).

Video of the full arc on the VM: `~/chooser-craft/final2.mp4`,
`~/chooser-craft/debug3.mp4` (the debug3 runs carried throwaway stub
text for pill diagnosis — the shipped path is the gated `line && anchor`
one shown in the Lodhi shot).

## Diagnosis trail for the "missing pill" scare (worth keeping)

Frames across several recordings showed no pill; bisected on-device with
a diagnostic build. Findings: the pill Marker, anchor, epoch and opacity
chain all worked — what was absent was `line` on the *engine-first*
options subset (rows with neither cleanest nor fastest claim and empty
`reason_line` → `chooserVerdict` null → correctly suppressed by the
existing gate). The full-options beat pins the real verdict. A
second finding, unrelated to the beat: the simulator's **hardware
keyboard connection** was invalidating the app's scene whenever the
search sheet autofocused its field (SpringBoard, process stays alive —
`UISceneKeyboardProxyLayer` update failure in the device log). Fix for
future sim drives: `defaults write com.apple.iphonesimulator
ConnectHardwareKeyboard -bool false`.

## Gates

`npx tsc --noEmit` clean · `npx expo lint` clean · `routeTint` self-test
55 assertions OK. Touched only the chooser/map-draw layer
(`RouteTint.tsx` beat, `ui.tsx` EndpointPin drop, `App.tsx` passes
`from`/`to` pins); no strings.ts churn, no plan-flow/jank files.

## Known real-world caveat

A first-run user gets the vehicle-mode sheet exactly when the settle
would land (it covers the map once, then never again) — the beat they
*see* first is post-sheet. Fixing that ordering is plan-flow's call,
not this lane's.
