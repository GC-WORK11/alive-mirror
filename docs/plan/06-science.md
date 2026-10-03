# 06 · The science — breath and smoke-out, honestly

## 1. Breath (inhaled dose)
```
dose_µg = Σ_segments  C(x,t) · ME(mode) · VE(mode) · Δt
```
- `C` — PM2.5 µg/m³ from the live H3 field at the segment's location and time, with band `[lo, hi]` from kriging variance.
- `ME` — microenvironment ratio per mode, from measured Delhi studies (already in `server/exposure.py`): metro 0.45, AC car 0.55, open car 0.80, bus 0.70, 2W 1.10, auto 1.15, cycle 1.10, walk 1.00.
- `VE` — minute ventilation per activity (sitting vs walking vs cycling; Zuurbier 2009 cycling ≈ 2.1× passengers).
- Near-road increment: traffic PM decays ~75% within 30 m (EPA/Karner) — applied to walk/cycle segments on arterials.
- Band: propagate `lo/hi` through the sum (conservatively: sum of lo, sum of hi).
- Consumer unit: cigarettes, `1 = 316 µg inhaled` (`CIG_UG`).

## 2. Smoke-out (trip emissions) — the inference chain
**We never know your exact vehicle. We know its class, the way Delhi's own enforcement does** (CAQM fuel-denial uses registration → age → fuel → BS class; docs/29).

```
declared {class, fuel, year?}
  → BS bucket (Delhi registration-year table, docs/29 §2; ±1 yr fuzzy edge)
  → emission factor median + spread per pollutant (ARAI/ICAP 2007 measured, real-world uplift; docs/29 §3)
  → speed-dependent curve ef(v) (COPERT structure)
  → idle floor (g/s), cold-start penalty on first ~4 km
  → integrate over the actual trip (live) or planned route (preview)
```
- Pollutants shown: **CO2** (kg) and **PM2.5** (g); NOx kept in details.
- "Not sure" year → Delhi fleet prior for that class+fuel (VAHAN dashboard mix, docs/29 §5).
- Shared modes: per-passenger with stated occupancy (auto 1.5, cab 1.3, bus 40% load, metro per pkm incl. electricity 11–25 g CO2e/pkm, docs/31 §3).
- Walk/cycle: 0 exhaust; shown as "none".
- Non-exhaust (road dust, brakes, tyres): shown in details as a separate band per vkm for road vehicles — ~86% of Delhi traffic PM10 is resuspended dust (docs/26), so a car-to-metro switch removes far more than tailpipe. Never folded into a single headline number.
- Band: class spread × speed-curve uncertainty; label: "estimated for vehicles like yours (2016 petrol car)".

## 3. Planned vs live
- **Preview** (options screen): uses route ETA with traffic and the free-flow duration → average speed → ef(v); idle share from (traffic − free-flow) time.
- **Live**: realized GNSS speed per tick; congestion surcharge = live − free-flow-equivalent, shown in the receipt details.

## 4. Ranking rule (one rule, explainable)
```
tied   = { o : dose_lo(o) ≤ 1.10 · min dose_lo }      # within our own error
winner = argmin emission in tied                       # Delhi breaks the tie
tag "lightest on both"   if winner is also min emission overall
else tag "lightest for you" (dose winner) and "lightest for Delhi" (emission winner)
time guard: never recommend an option > 1.6× the fastest ETA without saying "+N min"
```
Exactly the ε-constraint rule from docs/31: dose first (we measure it best, and it's personal), emissions decide among near-ties, both always shown.

## 5. Validation we publish
| What | How | Where |
|---|---|---|
| Field accuracy | leave-one-station-out MAE/bias vs CPCB/OpenAQ, by hour and season | `/city` + `validation/` |
| Dose model | reproduce the published Delhi mode ratios on the Magenta-line corridor | doc + test |
| Emission chain | reproduce ARAI table values at reference speeds; unit tests for cold/idle | `server/tests` |
| Engine parity | C++ and Python implementations agree to 1e-9 on 10k random routes | CI |
