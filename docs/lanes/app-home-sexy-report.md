# app-home-sexy report — the ambient number as the instrument

Lane: `app-home-sexy`. Owner's ask: *"the main home screen of Alive should be
very sexy and orgasmic, like the main admin/landing — the number should be the
home screen with a very sexy look. I love the subtle-state map colors — make
them more improved."* Ported the landing's `.hnum` instrument grammar
(`server/landing.html`) to `HomeScreen`'s hero and deepened the subtle-state
band work — band colour still only where it means air.

- **Branch:** `base/v2` @ `2f683cb` (pushed on top of `4101bd8` merge-home)
- **Device:** iOS 26.5 sim (iPhone 17, `EDD9B083`), dev-client build of this
  tree, Metro `EXPO_PUBLIC_API_URL=http://65.2.28.40` (prod ALB, GET-only)
- **Evidence:** `docs/lanes/app-home-sexy-shots/` — before/after PNGs + two
  landing videos assembled from `simctl io screenshot` frame loops
  (`simctl io recordVideo` was wedged "host recording in progress" all session;
  frame-capture at ~2 fps is the honest substitute)

## What changed

**The numeral IS the hero** (`Mobile/src/screens/HomeScreen.tsx`)

- `heroNum` 112pt → **132pt**, `line-height 138`, `letter-spacing -6` — landing
  scale on a phone. Same `famSerif(lang,"light")` thin cut + tabular nums.
- New `BreathLine` under the numeral — the landing's `.hnum::after` breathing
  baseline: 2px band-inked rule, `Animated.loop` sine 2200 ms, opacity
  0.10↔0.32; reduce-motion → static 0.16. Only under a real number.
- Felt word now the landing's `.hnum-band` row: 10px solid band square
  (`bandColorIdx`) + `heroFelt` serif word — position/swatch before the word.
- Provenance merged into ONE citation line (landing `.statusline`): locality +
  monitor distance + field age joined `  ·  ` under the refs — was two stacked
  footnotes. Live-mode honesty kept verbatim (`homeAirMetaPlace`, edge/atGps/
  model fallbacks, `airAgeLine`).
- `µg` unit re-set at `label13`/text3, baseline-locked to the numeral.

**Subtle-state band work** (`theme.ts`, `BandScale.tsx`, `MoodCanvas`)

- `bandWashDeepIdx` 26% → 32% band, `bandInkIdx` +15% → +20% toward ink —
  washes still whispers, but the band reads at a glance on the warm base.
- `BandScale` rewritten: was six discrete dashes; now one continuous washed
  CPCB ramp (SVG `LinearGradient`, each 40%-edge band tone interpolated at its
  segment centre → smooth neighbour blends) with today's band as a solid
  band-inked segment isolated by a paper seam. Position = meaning, no words.
- `MoodCanvas` gradient falls smoother (`0 → 0.26@0.62 → 0.52@0.30 → bg@0.8`),
  cross-fade 900 → 750 ms inOut-cubic.

**Cringe killed:** the `homeDoseWhat` gloss under the counted number ("µg =
micrograms… explaining the unit") deleted — the number no longer explains
itself. Kept the honesty captions: `homeAirWhat*` (names the number + served
usAqi), provenance, `4.3× WHO`, sparse-count.

**Choreography:** `CountUp` 900 → **480 ms** (inside the 300–500 ms ask);
sheet-enter spring `damping 26 / stiffness 230 / mass 0.9` (ζ≈0.9 — felt
settle, no bounce slop).

**Not touched** (verified): data logic, `PM25_BREAKS`, ambient/poll wiring,
`t()` keys — and every tour anchor (`useMeasureTarget("heroLedger")`,
`TourTarget id=hero|cta|day|week`, `useMeasureTarget("doorMap")`,
`useTourScroller`, `tourScrolled`) — `git diff` contains zero anchor lines.

## Gates — all green

| gate | result |
|---|---|
| `npx tsc --noEmit` | 0 errors (BandScale `LinearGradient` needs `ReactElement[]` — stops hoisted to a typed const) |
| `npx expo lint` | clean |
| `node src/store/test-runner.mjs` | 16 pass / 0 fail |
| `node src/nav/test-runner.mjs` | 94 pass / 0 fail |
| `node src/api/test-runner.mjs` | 26 pass / 0 fail |
| `node src/offline/test-runner.mjs` | 16 pass / 0 fail |

## Sim verification

Before/after via the skill's JS-swap (stash 3 src files → Metro serves parent
bundle → shoot → pop; same native build both ways).

| shot | state | what it proves |
|---|---|---|
| `before-home-forecast.png` | forecast, 65 µg | old hero: 112pt, no breath line, bare felt word, dashed scale |
| `after-home-forecast.png` | forecast, 65 µg | 132pt + breath line + `■ moderate` square + smooth ramp + proud seg |
| `after-home-live-provenance.png` | live, 66 µg | merged citation line: locality/lock + `air reading: 11 min old` |
| `after-home-dose.png` | counted, 10 µg | dose hero: `you've breathed today · ■ good · 5% of daily limit` |
| `after-band-verypoor-mock.png` | mocked /aqi → 175 | **band change correct**: `outside ~175 · very poor`, proud seg → position 5, mood canvas → very-poor rose, dose tier stays `good`-blue |
| `after-landing-midcount.png` | remount frame | numeral mid-count-up at `0` while scale/arc fade in |

Band-change method: `simctl` can't fabricate prod field states, so a
`localhost:8317` proxy forwarded everything to `65.2.28.40` verbatim except
`/aqi`, where only `pm25_ambient`/`pm25`/`us_aqi` were rewritten to 175
(very poor). Map `/grid`, day curve, news stayed prod-real. Result confirms
one source of truth: numeral ink, band square, felt word, ramp segment and
mood wash all read the same `airNowIdx` — CPCB semantics exact.

Videos (frame-assembled, ~2 fps honest cadence):
- `after-landing-remount.mp4` — home → Where-to sheet → back → numeral
  re-lands 0 → 65 (CountUp 480 ms)
- `after-coldopen-landing.mp4` — cold open → sparse → number lands

## Gaps / honest notes

- `simctl io recordVideo` reported "host recording in progress" for the whole
  session (zombie lock, no process to kill) — videos are screenshot-frame
  assemblies, so the 480 ms count shows as 1–2 frames, not butter.
- Ambient `outside …` line on the counted hero wasn't re-shot on prod at the
  end (poll hadn't re-landed a position); it was verified live earlier in the
  session and under the mock.
- The coach-tour card overlaid the first cold open; dismissed via `skip` —
  anchors verified addressable in the diff.
