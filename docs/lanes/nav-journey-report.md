# Lane report: nav-journey-verify — real moving trip end-to-end on-device

## Verdict
**FULL JOURNEY PASS + 2 REAL JANKS FIXED + 1 CRASH CLASS SEEN ON RELEASE.**
Drove a scripted 2.6 km bike trip India Gate → Khan Market on the iOS sim
(plan → pick → vehicle wizard → compare → start → live follow → deliberate
off-route deviation → reroute → arrive → receipt → Done → home). Camera,
puck, turn cues, dose strip, and counters all moved; arrival produced a
real receipt; consent-gated donation POSTed on arrival (ledger + empty
outbox prove it). Fixed two live-flow janks (dead CO₂ counter, inflated
×less claim on early-end receipts). Flagged: the search-sheet SIGSEGV
family now reproduces on the **Release** build (2 crashes), and a raw
transit line label leaks into receipt copy.

Rig: iPhone 17 sim EDD9B083-63F1-44E6-9A7B-0A6964CC2561, iOS 26.5,
Release build of `com.anonymous.app` from base/v2 @ 4fa85ea (+ lane
edits), `EXPO_PUBLIC_API_URL=http://65.2.28.40` baked (sim DNS can't
resolve the ELB hostname). Prod GETs only; the only prod write was the
app's own /v2/trip donation on arrival. Session 11:05–11:30 UTC Oct 7.

## How the trip was driven
`xcrun simctl location <udid> set lat,lon` every ~1.1 s along the real
`/v2/plan` geometry (101-pt polyline for `bike`, India Gate 28.6129,
77.2295 → Khan Market 28.60045, 77.22598, prod `dose.mid` 3.5 µg,
`eta_s` 240). Densified to ~5.7 m steps at 5.2 m/s ≈ 19 km/h — a real
scooter pace. Fixes injected = the app's only location stream; nothing
about the dose/emission math was stubbed.

## What was verified (receipts, not vibes)
- **Follow follows.** Camera trailed the puck turn-by-turn through
  Lodhi Rd → Man Singh Rd → Prithviraj; banner counted down per cue
  ("120 m Continue straight" → "150 m 1st exit onto Man Singh Rd" →
  "60 m 2nd exit …"); recenter + progress hairline alive the whole way.
- **Counters move.** Dose accrued 0 → 7.2 µg over the trip; band
  widened as it went (0–1 → 4.6–9.7 µg). Meta line ticked "km left"
  and "arrive" clock.
- **Off-route recovery.** Injected 5 fixes ~70 m east of the corridor
  (>OFF_ROUTE_M=40 ×OFF_ROUTE_FIXES=3): the engine rerouted — proven by
  the banner cue set changing to steps **not in the original plan**
  ("1st exit onto Man Singh Road" 140 m out — that step doesn't exist
  in the fetched geometry). Route re-converged onto the corridor, dose
  kept accruing, no reroute loop.
- **Arrival.** Last fix at the polyline end → odometer arrival →
  receipt "You're here." Mode chip "Bike / scooter" (PUC-calibrated
  2017–2020 petrol — vehicle profile persisted from the wizard).
- **Receipt honesty.** "You breathed ≈ 7.2 µg · about 4.6—9.7 µg" —
  dose mid ~2× the plan estimate (3.5 µg) because the ride took 8 min
  real vs 4 min route-ETA; the strip isn't faster than real time.
  Consistent and honest. "5.4× less than on foot" is vs the walk
  option's full-corridor dose — fair on a completed trip. Footnotes
  labelled "estimated for this kind of ride"; provenance footer
  "added anonymously to Delhi's air map".
- **Consent/donation.** consent.json `sharing:"on"` → on arrival the
  engine POSTed the privacy-trimmed trajectory (TRAJ_TRIM 300 m both
  ends, THIN 100 m, ROUND 4dp) and the receipt showed `receipt_donated`.
  outbox.json empty (nothing queued) + ledger.json has the trip:
  `dose_ug 7.2, avoided_ug 31.2, emit_kg 0.1, to "Khan Market"`.
  daylog.json gained ambient samples along the driven path.
- **Return to idle.** Done → home, today-count folded the trip in
  (18 µg "you've breathed today" from ~11 µg pre-trip ambient+ticks).

## Jank fixed in this lane (all verified live on rebuild)

### F1 — CO₂ counter read dead for the whole bike trip
`NavChrome` rendered `co2` at 1 dp kg ("0 kg / 0.0–0.1 kg"). A
2017–2020 petrol scooter puts out ~0.04–0.08 kg/km incl. cold start —
the cell sat on **0 kg for ~2 km** then flicked to 0.1. That's the
"counter freeze" complaint: the number was true but looked dead.
Fix: under 1 kg the chrome counter + band and the receipt stats tile /
footnote render **grams** (`nav_g`, en "{n} g" / hi "{n} ग्रा").
Verified live post-rebuild: same corridor, ~0.3 km in →
**"17 g · 12–23 g"** — visibly moving; early-end receipt stat tile
"18 g put out" + footnote "12–24 g". (`NavChrome.tsx`,
`ReceiptSheet.tsx`, `strings.ts`.)

### F2 — "33.5× less than on foot" on a 0.4 km stub
Ended the nav early (X) → receipt `tripEnded` claimed "33.5× less than
on foot · the smokiest way would have added ≈ 42 µg". The ratio is
full-route-worst-option dose ÷ accrued dose — on a partial trip it
divides by a fraction and inflates the win ~6×. Kill unexplained
numbers: `ratioTxt` and the `receiptSavedUg` line are suppressed when
`endedEarly` (the honest dose/distance/time/emissions all stay).
(`ReceiptSheet.tsx`.)

## Flagged — not fixed here

### X1 — search-sheet SIGBUS ×2 on the **Release** build
Post-reinstall cold launch → home rendered → tap "Where to?" →
`launchd_sim: exited due to SIGBUS | ran for 11179ms`, arbiter line
`KeyboardArbiter RX signalEventSourceChanged:UNK` ~0.1 s before death —
same signature family as `search-crash`'s d791879 fix and the
ios-journey lane's B1 "regression" note (they hit it 1/2 on dev). I hit
it **2/2 on Release** right after reinstall while the map was still
settling; third attempt after ~40 s idle opened the sheet fine —
consistent with the lane's map-tile-churn + focus-handoff window.
The earlier lane measured "Release clean" on cold launches only;
search-sheet opens under tile churn are the trigger, and Release is
**not** immune. Structural — belongs to whoever owns the
KeyboardArbiter/MapLibre churn class; do NOT claim Release-clean for
demo paths that open search early. Repro path logged in sim log
around 11:23:00 + 11:24:2x.

### X2 — raw transit line token in receipt copy
Early-end receipt alt line read "Bus CGOCOMPLEX-2 would have put out
≈ 0.1 kg" — `altEmit.label` is the server's transit line id verbatim.
Real data, but a raw token in user-facing copy; server-side label
quality, not client-mungeable. Flag for the transit-label owner.

## Nits (observed, not chased)
- ETA under-sells then self-corrects: "4 min" at start (plan ETA),
  stretched to "6–9 min" mid-trip as derived speed (19 km/h) fed in.
  Honest, just optimistic early — worth a note if riders complain.
- The off-route "finding new way" pill wasn't frame-captured (screenshot
  cadence ~2 s vs a ~2–4 s reroute window) — the reroute itself is
  proven by the step-set diff; pill visibility is inferred, not seen.
- App-level offline/stale pill not exercised — network stayed healthy;
  reroute + strip + donation all succeeded. Code-reviewed only.
- daylog's first ambient sample pinned lon 77.209 (~2 km west of the
  start fix) — a stale pre-trip fix, self-corrected by later samples.

## Evidence
`nav-journey-shots/` (sim screenshots): nav-start, follow-20m,
roundabout-cue, deviation-banner, post-deviation, converged, near-dest,
approach, receipt, home-after, grams-live, trip-ended-early (pre-fix),
trip-ended-early-fixed, search-recent.
Drive logs: `drive_log*.tsv` (fix stream). Ground truth: container
Documents/{consent,outbox,ledger,daylog}.json dumps quoted above.

## Gates
`npx tsc --noEmit` = 0 · `npx expo lint` = 0 ·
`node src/{store,nav,api,offline}/test-runner.mjs` all pass.
