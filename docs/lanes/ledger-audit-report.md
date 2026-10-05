# Ledger-math audit — is "≈N breathed" provable?

Lane: `docs/lanes/ledger-audit.md`. Base: `base/v2`. Live field: production NLB
(read-only: GETs + /v2/plan only, per lane rules).

## The path

```
GET /aqi?lat&lon  (every 60 s while foregrounded — App.tsx aqiPoll)
  → AmbientSample { ts, lat, lon, amb = pm25_ambient, bz = pm25 }
    recorded iff ≥8 min since last sample OR moved >~450 m        (store/daylog.ts)
  → daylog.json (on-device only — never uploaded)

reconstructDay(day, samples, trips, now)                          (store/daylog.ts)
  stays: consecutive pairs ≤45 min apart → covered span [t0,t1] clipped to
         [dayStart, min(dayStart+24h, now)]; conc(t) = linear ramp between
         the two measured values c = bz ?? amb
  trips: Trip.dose_ug (LiveCounters' 1 Hz integral over the /v2/strip
         field: conc × ME(mode) × VE(mode) m³/s × dt — ME_VE mirrors
         server/exposure.py verbatim) lands on its hour
  dose_ug = ∫ conc dt × VE_REST(0.6 m³/h = 10 L/min seated)        per stay
  totalUg = Σ stays + Σ trips     ← the hero (HomeScreen ≈{doseUgRound})
  thin    = <3 samples today AND no trips → "—", never a number
```

## Fixture proof — live field, hand recomputed

Reads captured 2026-10-06 ~02:45 IST, field `age_s`≈163, kriging on,
`waqi-stations+open-meteo/cams`, smoke_modifier 1.09:

| point | amb (µg/m³) | bz (µg/m³) | /aqi band | nearest stn |
|---|---|---|---|---|
| Connaught Place 28.6315,77.2167 | 69.2 | 75.4 | 58.8–92.1 | 1.8 km |
| Saket 28.5245,77.2066 | 57.5 | 62.6 | 31.4–93.9 | 2.0 km |
| Karol Bagh 28.6519,77.1907 | 54.7 | 59.6 | 30.4–88.8 | 2.1 km |

Fixture timeline (the mandate's shape): stand at CP 08:00→08:25 (two reads),
ride to Saket arriving 08:40 (ramping pair), indoors at Saket until 09:05,
plus the logged auto trip at 08:35 — a live `POST /v2/plan` CP→Saket auto
mid = 17.6 µg (lo 9.7 / hi 25.5).

| segment | hand trapezoid | app `parts` | ∆ |
|---|---|---|---|
| A 08:00–08:25 CP flat 75.4 | 75.4×0.6×25/60 = **18.85** | 18.85 | 0 |
| B 08:25–08:40 ramp 75.4→62.6 | 69.0×0.6×15/60 = **10.35** | 10.35 | 0 |
| C 08:40–09:05 Saket flat 62.6 | 62.6×0.6×25/60 = **15.65** | 15.65 | 0 |
| trip 08:35 auto CP→Saket | /v2/plan mid = **17.6** | 17.6 | 0 |
| **hero totalUg** | **62.45 → 62.5** | **62.5** | 0 |
| Σ arc hour bars | 62.45 | ~~63.41 pre-fix~~ **62.45 fixed** | **was +0.96** |

Harness: `cd Mobile && node src/store/test-runner.mjs` —
`src/store/daylog.test.ts` drives the same `reconstructDay` the home stack
imports (13 tests, all green). A judge reproduces the whole table with two
curls and one `node` command.

## Bugs found → fixed (Mobile/ only)

1. **Arc-vs-hero disagreement on ramps.** Per-hour `dose_ug`/`conc` accrued
   each sub-span's *left-edge* concentration while `parts`/`totalUg` used the
   trapezoid. On the fixture the bars summed 63.41 vs hero 62.45; a steep
   40-min 50→350 µg/m³ ramp would show 20 µg in the arc while the hero counted
   80. Fixed: per-sub-span trapezoid — the hour bars now sum to the hero
   exactly, and `conc` is the true time-weighted mean.
2. **Past-day arc truncated at "now"'s clock hour.** `arc` was sliced at
   `nowHour+1` for every day — yesterday's evening hours silently vanished
   from the structure (and `covered` flags past nowHour were force-cleared).
   No shipped surface renders a past-day arc (week dots + lens use `totalUg`),
   but the data lied. Fixed: bound = the day's own coverage end
   (`min(dayStart+24h, now)`), so past days keep all 24 h.

## Edge-case verdicts

| case | verdict |
|---|---|
| sparse cold-open (<3 samples, no trips) | honest — hero renders "—" + "still sparse — the phone has sampled today's air too little to count it yet"; zero invented µg (test) |
| location permission off | reconstructs — samples fall back to the Delhi centroid (the read is still a real field value *at that point*); attribution windows stay clock-labelled, no invented places; outside NCR the forecast cards bow out but the local ledger still renders |
| consent OFF | unaffected — sampling + reconstruction have no consent reference; only the donation POST /v2/trip is gated (`shareEnabled`) |
| segment crossing a field rebuild | two real reads at their own instants → linear ramp across ≤45 min — the honest bound of measurement, no epoch-aware claim |
| gap hours (>45 min between reads) | hole in the arc, not an interpolation; `coveredMin` and the hero count only covered spans (test) |
| midnight-crossing stay | clipped into both days at the ramp's interpolated boundary value (test) |
| future | never claimed — spans clip at `now`, arc ends at the last coverable hour (test) |

## Wire-shape check

- **Units** µg/m³ × m³/h × h → µg. ✓
- **Ventilation** stays use VE_REST = 0.6 m³/h ≡ 10 L/min — the engine's
  seated/transit tier (VENTILATION_LPM 10.0–10.5). Trips carry the full
  ME_VE table, verified verbatim against server/exposure.py (8/8 modes:
  metro .45/10 … walk 1.3/14, cycle 1.1/22).
- **Resolution** stays read the kriged *point* value at the phone's real
  position (finer than the cells=8 forecast grid, which feeds only the
  days-ahead card); trips integrate the ~250 m route strip.
- **FINDING (server-side, not a Mobile fix):** stays prefer `bz` =
  ambient × smoke_modifier while trip legs integrate raw ambient —
  `/v2/strip` and `/v2/plan` never apply the modifier. With modifier 1.09
  today, a stay counts ~9 % more than the same concentration inside a trip.
  `bz` is the server's own breathing-zone estimate, so Mobile should not
  downgrade to `amb`; the engine lane should apply the modifier in
  plan/strip (or serve `bz` on the strip).
- Noted, harmless: trips credit a flat +15 min/hop (≤60) in `coveredMin`
  display; dedupe comment says ~450 m but the gate is |∆lat|+|∆lon| < 0.008°
  (~850 m diagonal at Delhi) — sparsity only, no math impact.

## The one sentence

> "Every µg in that number is ∫C(t)·0.6 m³/h·dt over stretches where the
> phone actually read the live field at your position — a unit test
> recomputes it by hand and the hour bars sum exactly to the hero; wherever
> the phone wasn't watching, the arc stays blank and says so."

## Proof artifacts

- `Mobile/src/store/daylog.test.ts` — 13 tests: live-field fixture (per-segment
  + total + arc-sum), sparse/gap/midnight/now-clip/future honesty, bz→amb
  fallback, recordSample dedupe.
- `Mobile/src/store/test-runner.mjs` — node:test harness (expo-file-system +
  startup/idle stubs), mirrors `src/nav/test-runner.mjs`.
- Gates: `npx tsc --noEmit` clean, `npx expo lint` clean, nav suite 38/38.
