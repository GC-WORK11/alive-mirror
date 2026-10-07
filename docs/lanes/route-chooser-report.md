# Lane report — route chooser (the cinematic "app visibly thinks" beat)

Owner ask: "put from and to location, make the trip — it shows
two-three ways animating, then settles on the safest and best path —
fastest also, including pollution." The data side already exists
(options priced by dose+time, per-span pm25 colours). This lane built
the choosing MOMENT: candidates draw as equals → camera fits all → the
engine's winner settles bold, losers drop to hairline, and a verdict
pill pins onto the route saying why — real numbers only.

## Baseline (item 1 — verified first, `baseline-compare.mov`)

The route-render lane (495957b) already faded alternates in staggered
(~280 ms apart), but the recommended route asserted bold from frame 0 —
there was no competition phase, no settle transition, and nothing said
WHY the winner won. Camera also framed only the selected route, so
alternates often entered off-screen. The "thinking" beat did not exist.

## What shipped — `Mobile/` on `base/v2`

### Candidates draw as equals (`RouteTint.tsx` + `routeTint.ts`)

`candidatesFor(options, selected, perOption, cap=3)` picks the drawable
candidates — **selected last** in rank order, everyone else first. On a
new option set both sources stage empty, then each candidate reveals
span-by-span (≤11 chunk groups × 34 ms, two `op` steps 0→0.3→0.85),
candidates staggered 220 ms apart. Nothing unmounts: staged opacity
rides the feature `op` prop through the always-mounted
`routeTintAlts`/`routeTintSel` sources (the SIGSEGV class is
mount-vs-draw — documented in-file).

### Camera fits every contender (`useShellFlow.ts`)

`show()` now unions the bounds of ALL option geometries and fitBounds
once per landing (padding clears the search pill + compare sheet;
+500 ms inside `whenMapDrawFree` so the sheet's own enter animation
isn't fighting the camera). Previously only the selected route was
framed — the chooser's whole point is seeing the rejected ways.

### The settle + verdict pill

At ~settleT (CHOOSE_START + (cands−1)·220 ms + reveal + 120 ms gap —
about 1.4–1.7 s for 3 candidates): the winner moves onto the selected
source at 0.45 opacity then settles to full 9px casing + 6px line;
losers drop to `DROP_OP` 0.32 hairlines, then rest at `ALT_OP` 0.5.

A verdict **pill** (always-mounted `Marker`, `anchor="bottom"`) pins
onto the winner at `pointAtFrac(geometry, 0.45)` — ON the line, just
past midpoint — fades in 240 ms, holds 4.2 s, fades out 340 ms.
`chooserVerdict` derives the ONE honest claim from served fields:

- `best` → "cleanest and fastest" (least dose AND quickest, mirroring
  CompareSheet's isSafest: explicit `safest_path` flag wins anywhere;
  flagless sets give the claim to the dose-min row)
- `cleanestVsFastest` → "cleanest · {n}% less than fastest" — n is
  `round((1 − selDose/fastestDose)·100)`, shown only when ≥ 4
- `cleanest` / `fastest` when only one claim holds
- `reason` → the option's own `reason_line` through the sheet's
  verbatim `reasonTxt` translator (a user pick that is neither cleanest
  nor fastest says the server's reason, never an invented one)

en + hi strings both shipped (`strings.ts` — parity is
compiler-enforced). Reduce-motion collapses all staging to the final
state instantly; the pill still labels. Every timer is interruptible:
a new plan generation-kills the old beat.

### The fix found BY verifying (item 5 caught a real bug)

First device run showed settled routes but NO stagger and NO pill.
Cause, verified on frames: beat timers lived in the effect's cleanup
list, but `tint` identity changes on EVERY strip arrival (`fetchStrip`
streams per-route strips for seconds after options land) → effect
re-ran → cleanup killed the pending settle + pill timers, and the
same-set `recolor` mapped over `next.features` so it also landed every
un-drawn chunk and the winner at default opacity mid-beat.

Fix: beat/swap timers moved to refs with a generation guard
(`beatGen`); only a NEW option set or unmount clears them — strip
churn now re-colours only already-staged features (`recolor` maps the
staged list, preserving `op`), so pending chunks stay pending and the
reveal survives data that arrives mid-animation.

## Verification — what was actually run

- `npx tsc --noEmit` clean; `npx expo lint` clean;
  `routeTint` node self-test **55 assertions** (candidatesFor ordering/
  cap/no-geom exclusion, chooserVerdict all five kinds + null,
  pointAtFrac midpoint/single/null).
- iOS sim (iPhone 17, iOS 26.5, release-style dev build,
  `EXPO_PUBLIC_API_URL` → prod ALB, sim location at Connaught Place):
  - **CP → Noida Sec-18 metro** (~13 km): candidates draw — frame
    `noida_candidates_mid.png` catches the eastbound route mid-reveal —
    settle + pill "cleanest and fastest" pinned on-route
    (`noida_pill.png`, video `chooser-fix1.mov` t≈49).
  - **CP → Rohini Sec-18** (~20 km): bare map → candidates → settle,
    pollution-coloured spans visible on the winner (dark red-brown
    spans where the field is worse — real segment paint, not a flat
    tint), pill fired (`rohini_pill.png`, `rohini_settled.png`).
  - **CP → Dwarka Sec-21** (~24 km): candidates drawing SW mid-beat
    (`dwarka_midbeat.png`).
  - Tap-swap path exercised (demote-settle timers now strip-proof too).
- Video evidence: `baseline-compare.mov` (before), `chooser-noida.mov`
  (319 s — the shipped-then-broken build: settle without stagger or
  pill — the bug this report's fix addresses), `chooser-fix1.mov`
  (238 s — the verified build). Videos kept out of the repo; shots in
  `route-chooser-shots/`.
- No fake routes anywhere: candidates are only the drawable options the
  plan actually returned; a thin response honestly draws fewer.

## Optional intel line (item 4) — assessed, honestly not shipped

Free real signals that DO exist on the wire: `via_names` (OSM street
names — already rendered in each card's "via Outer Circle → Vivek…"
line) and `duration_basis`/`freeflow_s` vs `eta_s`. For engine rows
`freeflow_s == eta_s` by construction (the graph is priced on freeflow
OSM maxspeed/class defaults — no congestion feed exists), so a
"+0 min vs freeflow" line would be noise, not intel. OSM
`maxspeed`/`smoothness`/`surface` live in the route graph's edges but
are not surfaced per-option on the wire; no free government accident
API exists. Per-route traffic-at-travel-time and road-quality lines
would require either new server surface or a new free source — out of
this lane's honest-data bar. Documented, not fabricated.

## Residual / honest gaps

- Each plan stages the beat TWICE — once on the engine-first rows
  (~1–2 s paint), once when the full public-router+transit set lands.
  Intended: fast first paint, then the honest re-stage on the real
  contender set. The second beat is the cinematic one.
- Reduce-motion collapse is code-path-verified (timers → instant) but
  not exercised on-device (sim a11y toggle not flipped this run).
- Sim SIGSEGV class respected throughout: sources/layers/Marker never
  unmount; every staged write rides a timer; camera moves wait for a
  draw-free window (`camDur→0` on sim).
