# 08 — The Brutally Honest Verdict: What Alive Actually Is

Updated 2026-10-01 after deep verification pass. Every claim below has a source.

---

## The question

Does this solve something big, or is it another hackathon junkyard project?

**Answer: the problem is enormous and real; the solution space is real but bounded;
the specific combination we are building is genuinely unoccupied territory.**
Whether it wins is decided by execution, not by more features.

---

## What the physics + literature actually allow

### Verified big levers (the ones that matter)

| Lever | Verified magnitude | Source |
|---|---|---|
| **Mode switch** | Walking inhales ~28× more PM2.5/km than metro; auto-rickshaw ~5.3×. Measured on Delhi roads (6 microenvironments). | Sci. Total Environ. 2021, Delhi measurement study |
| **Mode microenvironment** | Measured in Delhi: auto-rickshaw 113.2, bus-open 68.9, car-closed 62.3, metro 34.2 µg/m³ | Springer Discover Atmosphere 2025, Magenta-line study |
| **Departure time** | Delhi's diurnal cycle is extreme: calm winter mornings with low boundary layer trap pollution; late-night/diurnal peaks can differ 2-5× within a day. IITM publishes a verified 72-hour hourly forecast. | IITM EWS (ews.tropmet.res.in), Open-Meteo BLH |
| **Route choice** | ~5-20% exposure reduction typical at ~2-3% longer distance. Published benchmark: CAR algorithm, 4,000 real scenarios, **17.1% avg exposure cut for +2.4% distance**. | CAR (Taiwan, 2019); Thessaloniki pedestrian routing (2026) |
| **Fire season** | Punjab/Haryana crop burning contributes ~14-20% of Delhi PM2.5 on Oct-Nov average — and **50-75% on episode days**. Hackathon week IS the start of fire season. NASA FIRMS gives 375m fire detections with <3h latency. | npj Clim. Atmos. Sci. 2025; WRF-Chem ES&T 2020; FIRMS |
| **Stagnation physics** | Boundary-layer height + wind speed are free hourly fields (Open-Meteo). Low BLH + calm = multiplier on the same emissions. This is real physics we can compute, not decoration. | Open-Meteo API |

### The honest physics of "which road is cleaner"

- Traffic-linked PM increments decay ~75% within the first ~30m of a major
  road; traffic species decay out to ~150-500m. A residential street
  parallel to a corridor is measurably cleaner — this is real.
- BUT PM2.5 *mass* decays more slowly than ultrafine counts — the
  curb-vs-100m difference for PM2.5 mass is real but modest, not 10×.
- Street canyons (tall buildings + narrow road) trap pollution — real
  effect, but Delhi building-height data is too sparse for true canyon CFD.
  Honest v1: road-class proxy (arterial vs residential) from OSM, labeled
  as model-based.

---

## What "real-time" actually means (and what we refuse to fake)

- CPCB CAAQMS stations natively record **15-minute averages**; the public
  feed is hourly-ish with gaps.
- **Documented fact**: multiple Delhi stations go BLANK during peak
  pollution hours (TOI reporting, Diwali/GRAP nights). Any app claiming
  smooth real-time truth is lying; ours will show provenance:
  "measured 47 min ago at RK Puram, 1.2 km away — station since went dark,
  estimate carries model error."
- Millisecond-level live pollution does not exist anywhere on Earth.
  What exists and we WILL do: every-timestamped history from 15-min now
  back to 2016 (~10 years via OpenAQ's public S3 archive — no key needed),
  live forecasts out 72h (IITM) and 5 days (CAMS), sub-minute *query*
  latency because the field is precomputed.

That provenance honesty is itself a differentiator — every AQI app fakes
precision; we show the chain of evidence.

---

## The product (final definition)

**Alive = a dose engine, not a route finder.**

For FROM → TO, it answers in one screen:

> "Right now: auto = 218 µg inhaled, car AC = 96 µg, metro leg = 41 µg.
> Wait until 19:00 and all of them drop ~35%."

Every number traces to a station or a published factor. Uncertainty shown
as a band, never fake precision.

Dose = Σ over route segments [ concentration(lat,lon,t) × microenvironment
factor(mode) × ventilation rate(mode) × time(segment) ].

- concentration: station-weighted IDW field + road-class uplift +
  BLH/stagnation correction + fire-day modifier
- microenvironment: measured Delhi ratios (metro/car/bus/auto/bike/walk)
- ventilation: published minute-ventilation by mode (cycling ~2.1× car)
- time: real OSRM duration per segment

### Decision engine, not LLM veneer

Deterministic scorer ranks route × mode × departure-time options on dose,
time, and cost delta. An LLM layer (if we add one) only *explains* ranked
structured results — it never invents a measurement.

---

## Explicitly cut (brutal honesty)

- Accident-avoidance / lane-guidance — off the Air track, pure distraction.
- "Verified by Google Maps" — ToS-illegal; OSM + TomTom free tier only.
- City-wide pollution-reduction claims — we cut *personal exposure*, not
  Delhi's emissions. Saying otherwise is faking.
- Street-canyon CFD, GNN surrogate models — no Delhi building data or
  training time. The IDW + physics-term field IS the defensible v1.
- Generic dashboards, AQI color maps — solved, boring, loses.

---

## Why this can win

- Track-perfect: it IS the air-pollution track, applied to the thing every
  Delhi judge does twice a day (commute).
- Nobody ships consumer multimodal dose routing for Delhi — the closest
  prior art (CAR, LEAP, Thessaloniki) are academic prototypes on cleaner
  cities without mode/time/uncertainty depth.
- Timing luck: hackathon falls at fire-season start; a live FIRMS overlay +
  fire-day dose modifier is a demo nobody else will have.
- The honesty layer (provenance, uncertainty bands, "station went dark")
  converts our biggest data weakness into the credibility story.

## What it will NOT do

- It will not replace Google Maps — it is the 10-second check you make
  before opening Google Maps.
- Route-only savings are bounded (~5-20%); the product must surface
  mode/time options honestly or it collapses to a map clone.
- If your trip is locked (same mode, same time, same route), savings are
  small — the app must say so. A dose number alone is still value:
  it makes the invisible visible.

---

## Build order (validated against evidence)

1. **Air field**: station registry → CPCB/Open-Meteo blend → IDW → /aqi
2. **Dose scorer**: polyline sampling × microenv × ventilation → per-route µg
3. **Time-shift**: IITM/CAMS hourly forecast → "leave later, breathe less"
4. **Corrections**: BLH stagnation + FIRMS fire-day modifier
5. **Provenance UI**: every number shows its station/factor + age
6. Demo: 3-minute video = same trip, three ways, dose on screen.
