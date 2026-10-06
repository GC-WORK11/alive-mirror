# Lane report: ios-journey-overnight — Oct-7 Lane-B checklist on the iOS sim

## Verdict
**1 REAL BUG + 2 i18n LEAKS.** The search-sheet SIGSEGV the `search-crash` lane
fixed in d791879 is **back / incompletely fixed** — a fresh SIGSEGV(11) fired
with the same `KeyboardArbiter stealKB` signature despite the
`runAfterInteractions` gate being in this checkout. Everything else on the
checklist passed against prod with exact-match numbers: welcome once + re-arm,
hero = live `/aqi` value at the sim fix (3 exact matches), real-time refresh
across two field epochs, honest profile budgets, full trip → receipt → ledger,
delete-data wipes everything and re-arms film + onboarding.

Rig: iPhone 17 sim (EDD9B083), iOS 26.5, Expo dev client `com.anonymous.app`
built from base/v2 @ 1b395fe, Metro serving
`EXPO_PUBLIC_API_URL=http://65.2.28.40` (sim DNS can't resolve the long ELB
hostname — raw EIP required). Prod GETs only. Session window 20:30–21:15 UTC
Oct 6. Shots in `ios-journey-overnight-shots/`.

## Bugs found

### B1 — SIGSEGV regression on search-sheet open (the fixed crash class)
`runningboardd` exit context, pid 9659, 2026-10-06 14:02:55 sim time
(≈21:02 UTC):

```
[app<com.anonymous.app>:9659] Process exited:
  <RBSProcessExitStatus| domain:signal(2) code:SIGSEGV(11)>
```

Steps: fresh post-wipe state → home → "the air map" (full MapLibre at India
Gate fix) → **two quick pans** → tap "Where to?" → gone ~2 s later, SpringBoard.
Last app-side lines before death are the identical signature the
`search-crash` lane documented for the responder handoff:

```
14:02:53.525 KeyboardArbiter: TX focusApplication (peekAppEvent) stealKB:Y
14:02:53.532 UIKit:Feedback <UISelectionFeedbackGenerator> cannot play feedback
14:02:53.5x  UIEvent/gesture dispatch stream → process dead at 14:02:55
```

The d791879 gate is present in this checkout
(`Mobile/src/screens/SearchScreen.tsx:260-265` —
`InteractionManager.runAfterInteractions` + `closingRef`), so this is either a
regression or a wider window than that fix covers. Notable delta vs the
lane's repro: their trigger was reopen-during-close-transition; here the map
had been panned ~15 s earlier and was likely still streaming tiles — so
map-tile churn + focus handoff may be enough without a close-transition.
Repro on the identical sequence 2nd time did NOT crash (1/2 attempts) —
timing race, as expected for the GC-heap-stomp class. No `.ips` written
(sim-app SIGSEGV, same as lane found); the runningboardd exit-context line
above is the authoritative proof. App relaunched cleanly, no state corruption.

### B2 — i18n leak: " km"/" m" hard-coded in 2 spots
`unitsKm: "किमी"` exists (`src/i18n/strings.ts:916`) and is used everywhere
else (Settings, CompareSheet meta, NavChrome, Sidebar, ReceiptSheet), but:
- `src/screens/SearchScreen.tsx:54-59` `fmtDist` hard-codes `" km"`/`" m"` →
  recent-places row renders "2.4 km" in हिंदी (visible in shot).
- `src/components/shell/CompareSheet.tsx:707` step-dist hard-codes `" km"`/`" m"`
  → transit itinerary steps leak in हिंदी.
No `unitsM` string exists — a fix needs one added (or reuse मीटर prose).

### Nits
- Receipt footer reads "saved — will send when back online" while the network
  was up; `outbox.json` was empty afterwards so the donation did flush —
  the copy implies queued-offline when it actually sent (or flushed instantly).
- A LogBox "!" pill ("Open debugger to view warnings") showed through most of
  the run; its text never reached Metro stdout or the sim system log — only
  benign SecTrust/ATS/KeyboardArbiter noise around it. Needs an RN-debugger
  attach to read; flagged not verified.

## Checkpoints

### 1. Welcome film — once, persists, no replay. PASS
- Fresh install Documents was empty → cold launch → digit-field film played
  → resolved frame **55.0 µg/m³ · PM2.5 · SATISFACTORY · "live · field mean
  over the ncr lattice"** (shot `film-live-number.png`).
- `GET /v2/city` at that moment: `pm25_stats.mean = 55.0` — exact match, the
  film's number is real.
- `Documents/welcome_seen_v1.json` = `{"seen":true,"ts":1791318654459}`.
- Second launch → straight to onboarding, no replay. Re-arm proof via
  delete-data below.

### 2. Hero is a REAL live value. PASS — 3 exact matches
| Sim fix (simctl location) | Hero shows | `GET /aqi?lat&lon` `pm25_ambient` |
|---|---|---|
| 28.6315, 77.2167 (CP) | "outside ~67" | 67.0 (field age 24 s) |
| 28.61302, 77.22767 (India Gate) | "outside ~51" | 51.1 |
| same, post-21:04 rebuild | "~50 µg/m³" | 50.0 |
Shot `home-hero-live.png` shows "~67 µg/m³" + "≈ 2.2 µg this week" +
"2 of 3 samples" — honest accumulating state.

### 3. Real-time refresh across a field epoch. PASS
- Field rebuilds observed (poll `/aqi` every 60 s): **20:33:45, 20:49:09,
  21:04:30 UTC** — ~15.4 min cadence, `field.age_s` resets to 0, `stale:false`.
- Home left open across the 20:49 rebuild with NO restart: hero moved
  ~67 → ~51 (new ambient 51.1 at the fix) and the "X मिनट गिने" freshness
  counter kept counting. `daylog.json` gained new samples at each poll.
- Bonus: after relaunch on the 21:04 field, hero reads ~50 (= 50.0) and the
  move card recomputed (heaviest ≈111 → ≈107 µg/m³, day avg 69 → 67) —
  forecast re-derives on new field, not just the ambient line.

### 4. Profile budgets + delete-data. PASS
- Budget card on home, all three segments honest (budget − 14 used):
  **general 216 → 202 left · sensitive 72 → 58 left · child 130 → 116 left**
  (`PROFILE_BUDGET_UG` constants).
- "Delete my data" (drawer, हिंदी confirm dialog) → `Documents/` listing:
  settings, consent, contributor, daylog, ledger, places, vehicle,
  welcome_seen_v1 ALL deleted; `alive-cache` emptied; only fresh
  `outbox.json` remains. Trips screen → "no trips yet".
- Relaunch → **welcome film replayed** (flag rewritten
  `{"seen":true,"ts":1791320309204}`) → onboarding re-armed → home with
  profile reset to general (216 ring) and lang back to English.
- Minor UX note: in-session the UI stayed हिंदी until restart (lang held in
  memory) — defensible, but the store wasn't flushed until cold start.

### 5. Trip journey. PASS
CP → "India Gate" search → plan → vehicle wizard (bike/scooter petrol
2017-2020 + BS-IV PUC) → compare sheet (shot `compare-doses.png`):
- Options vs ambient ~67: car(AC) ≈2-3, bike ≈5-7, auto ≈5-7, cycle ≈24-30,
  metro+walk ≈25, walk ≈52-68 µg — plausible spread, walk ≈ ambient-rate.
- Leave-later histogram "+12घं 13:30 ≈ 2 µg", "leave 13:30 → breathe ~11% less".
- Start → nav "Head out" 0 µg/0 kg; drove sim location to dest → dose ticked
  mid-nav → arrival jiggle → **receipt: ≈1.3 µg breathed, 54× less than on
  foot, ≈0.2 kg put out, 3.9 km, 2 min** (shot `receipt.png`).
- `ledger.json` entry: dose_ug 1.3, avoided_ug 66.5, emit_kg 0.2, your
  location → India Gate (28.612913, 77.229507); drawer groups it under "आज".
- Donation flushed (`outbox.json` empty after) — corridors on "Delhi today"
  show community aggregates 3-13 यात्राएँ per street with कम/ज़्यादा धुआँ tags.

### 6. हिंदी parity. PASS except B2 leaks
Audited drawer, home (hero/budget/move/day/week/days-ahead/windows),
Delhi-today sheet (pollutants, 10-yr compare, corridors, freshness), search,
compare sheet:
- Hours: everything 24-h clock (13:34-13:42 windows, ~18:30-, 01:30/07:30
  histogram ticks) — **no Latin am/pm anywhere to leak**.
- Units: kg → **किग्रा** (drawer trip row "≈ 0.2 किग्रा"), minutes → मिनट/मि,
  hours → +3घ/+6घ ticks, यात्राएँ counts, "5 मिनट पहले अपडेट". µg stays Latin
  µg — consistent scientific-unit choice.
- Day names: बु गु शु श र सो मं week dots; आज/कल/शुक्रवार/शनिवार/रविवार days-ahead.
- Proper nouns stay Latin (street/place names) — correct.
- Leaks = B2 above (SearchScreen recents "2.4 km", CompareSheet steps "km"/"m").

### 7. Crash hunt. **HIT — see B1.**
One SIGSEGV in ~90 min incl. ~15 sheet open/close cycles, 1 full nav
lifecycle, drawer + map use. Single repro path found; 1/2 attempts.

## Other observations
- Dev client survives Metro death via cached bundle (Metro died mid-session;
  app kept running live prod data — bundle restarted fine after).
- No-Office/WYSIWYG notes n/a — all shots via `simctl io … screenshot`
  (device-space truth, not desktop compositing).

## Evidence index
`ios-journey-overnight-shots/`: film-live-number.png (55.0 resolved frame),
home-hero-live.png (~67 exact-match), compare-doses.png, nav-mid.png,
receipt.png (≈1.3 µg), hindi-drawer.png, hindi-hero.png, hindi-compare.png
(+Nघं ticks), post-epoch-home.png (~50 after 21:04 rebuild).
Sim Documents dumps quoted inline; runningboardd excerpt quoted in B1.
