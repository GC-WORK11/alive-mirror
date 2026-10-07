# audit-fix lane — top findings repair

Owns the demo-blocking findings from `component-audit-report.md`:
#1 (home inset), #2+#3 (onboarding clip + banner), #4+#5 (dead layers +
invisible field), #10 (move copy), #21+#22 (compare slop), #24 (offline
lie). Nav/chooser/jargon findings stayed with their sibling lanes.

Rig: iPhone 17 sim (EDD9B083, iOS 26.5), Release build
`EXPO_PUBLIC_API_URL=http://65.2.28.40` baked into main.jsbundle,
geo set to 28.6139,77.2090. Shots in `shots/audit-fix/` — `simctl io
screenshot` unless noted.

## P0 — idle Air Map shows the air (audit #4/#5)

Before: field cells at 0.12 opacity under a plain basemap — the map
read as an empty street map.

Now: `airfieldCells` fill-opacity per confidence — hi .92 / med .60 /
lo .34 / default .45 — the exact `CONF_A` alphas the admin-dashboard
hero (`server/landing.html`) uses. New `airfieldEdges` line layer
steps cell borders through `bandInkIdx(0..5)` (0.55 opacity,
zoom-interpolated width) so the field reads as contours, not a flood.

Verified: open Air map → whole viewport carries the pm2.5 field in
band color with roads/labels above it (`06-airmap-field.png`,
51 live stations). Panning south shows real spatial variance —
#C05F3A (91–120) cells over INA/Sarojini with a #C7A34F (31–60)
pocket at Kidwai Nagar and cell-edge contours
(`07-airmap-variation.png`).

Also in the same finding: corridor glow ×~2 opacity (.26) and dots
radius 3→6 (was sub-pixel); blackspots dots 4.5/8px at zoom 11.5/15
(were 1.9/4.5 — sub-pixel at city zoom).

## offline pill lie (audit #24)

`offline/status.ts`: any single `down`/`stale` net event flipped the
pill. Now `failStreak` counts consecutive failures; the pill only
goes `stale`/`offline` at 3, a single `up` resets to `online`
immediately, and at the flip `probe(API)` re-checks within ~4 s so a
false flap self-corrects instead of sitting until the next poll.

Verified: 4 new unit cases drive `handleNetEvent` —
`src/offline/status.test.ts` (1–2 fails stay silent, 3rd flips +
probes exactly once, stale carries age, success resets the streak).
On device the pill never showed through a ~30 min session incl. the
plan fetch — home reads "air reading: N min old" (all home shots).
Hard-failure path not reproducible on this rig without killing host
net (no sudo for pf); logic covered headless instead.

## compare-sheet slop (audit #21/#22)

`CompareSheet.tsx`: `bandTxt` collapses equal-rounded lo/hi to one
number; `zeroBand` drops emission bands that are zero at display
precision — the `non_exhaust` note ("zero — no engine") now carries
the row instead of "0–0 kg CO2".

`api/plan.ts` `relabelLeastSmoke`: the engine's '· least-smoke rd/alt
N' names its own primary, not the displayed same-mode set — verified
live (0.8 µg alt wore the qualifier beside a 0.6 µg plain row). Now
the qualifier survives only on the group's true `dose.mid` minimum
(0.05 display-precision eps); everyone else degrades to '· alt N'.

Verified on device, CP → Lajpat Nagar railway:
- Car (AC) · least smoky way ≈6 (2–10); Car (AC) · alt 1 / alt 2
  ≈6 — qualifier only on the lowest mid.
- Bicycle · least smoky way ≈55 vs Bicycle 71 / alt 1 62 / alt 2 65
  (`10-bicycle-honest-labels.png`).
- On foot · least smoky way ≈132 vs 145/160.
- Bicycle detail shows "zero — no engine", no 0–0 rows
  (`11-bicycle-zero-engine.png`); Auto-rickshaw detail shows the real
  span "0.3–0.8 kg CO2 · 0.06–1.25 g PM2.5"
  (`09-auto-real-emissions.png`).
- 5 new unit cases — `src/api/plan.test.ts` (smoky-alt stripped, true
  min keeps, eps tie keeps, dose-less demoted, all-dose-less passes
  through).

## 'Where to?' occludes content (audit #1)

`HomeScreen`: sheet `paddingBottom` was a flat 12 — bottom cells sat
under the home-indicator zone. Now `useSafeAreaInsets()` →
`insets.bottom + 16`.

Verified: sheet scrolled to its last row — daily-limit chips sit well
clear of the screen edge (`08-home-bottom-inset.png`) and the
bottom-row "child" chip takes the tap (limit recomputes to 130 µg).

## '~2h of today left' at 10:56 AM (audit #10)

`HomeScreen` decisionLine: the short copy "only ~{n}h of today left"
fired whenever the day's card carried < 3 future hour-rows — mid-
morning included. Now gated on real IST time: the short phrasing only
runs when the day is actually ending (`istLeft <= n + 1.5`); earlier
in the day it reads "the next ~{n}h look {b} — the rest of today's
card isn't in yet" (`moveDec_cardShort`, en + hi in strings.ts).

Verified: code-path fix + healthy branch on device (home "the move"
card shows the outlook strip sanely at 12:1x PM). The buggy branch
needs a < 3-row card, not producible at midday without faking the
clock — the IST guard is the fix.

## first-run polish (audit #2/#3)

`OnboardingScreen`: `consent_footnote` moved out of the ScrollView to
a pinned slot above the footer — renders on every page without
scrolling.

`store/events.ts`: `checkAirEvents` now returns early until
`loadConsent().seen` — the air-event banner can only fire after
onboarding completes (was firing at mount inside the first aqiPoll).

Verified: cold install → page 1 footnote fully visible, zero banner
at ~12 s (`02-onboarding-fresh.png`) and still none at ~52 s
(`03-onboarding-60s.png`); consent page footnote intact. The moment
consent + notification permission land, the queued air-event banner
appears on the HOME screen — deferred, not dropped
(`12-banner-after-consent.png`, desktop shot).

## gates

```
npx tsc --noEmit        clean
npx expo lint           clean
node src/{nav,api,offline,store}/test-runner.mjs
                        76 + 17 + 16 + 84 = 193 pass, 0 fail
```

## files

- `Mobile/src/components/AirFieldLayer.tsx` — CONF_A opacities +
  airfieldEdges contour layer
- `Mobile/src/components/CorridorLayer.tsx` — glow/dots visibility
- `Mobile/src/components/HazardLayers.tsx` — blackspot dot radii
- `Mobile/src/offline/status.ts` — 3-failure debounce + recovery
  probe; `handleNetEvent`/`statusForTest` seams
- `Mobile/src/offline/status.test.ts` — new (4 cases)
- `Mobile/src/api/plan.ts` — `relabelLeastSmoke`; `mapPlan` exported
  for tests
- `Mobile/src/api/plan.test.ts` — new (5 cases)
- `Mobile/src/components/shell/CompareSheet.tsx` — `bandTxt` collapse,
  `zeroBand` hides 0–0 rows
- `Mobile/src/screens/HomeScreen.tsx` — safe-area inset + IST gate on
  the short move copy
- `Mobile/src/screens/OnboardingScreen.tsx` — footnote pinned off the
  scroll region
- `Mobile/src/store/events.ts` — consent-seen gate on air events
- `Mobile/src/i18n/strings.ts` — `mode_altN`, `moveDec_cardShort` (en+hi),
  `moveDec_short` reworded
- `Mobile/App.tsx` — field pull retry boot (3 tries / 7 s) so the P0
  field can't silently stay off after one early-boot miss
