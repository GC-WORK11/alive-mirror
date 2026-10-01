# 03 · Models — Feasibility Analysis

Every candidate method scored on the 9 questions the brief demands. Verdicts: **MVP** (build now) / **V2** (post-hackathon) / **CUT** (doesn't earn complexity).

## 1. Concentration field C(x, t)

The base layer: estimated pollutant concentration at any Delhi coordinate, any hour.

### Method A — Station interpolation + covariates ⭐ MVP
- **What**: hourly readings from ~46 stations → spatial model per pollutant.
- **Method**: regression-kriging / GAM — smooth trend on covariates (distance to major road, land use, station-siting quality flag, upwind fire count) + kriged residuals; IDW as the naive fallback for comparison.
- **Inputs needed**: CPCB hourly (have it), OSM road classes (have it), Open-Meteo wind/BLH (have it), FIRMS fires (have it).
- **Speed**: 46 observations, ~2k grid cells → milliseconds.
- **Accuracy**: honest cross-validation RMSE; expectation ~15–30% on PM2.5 for unmonitored areas (say so).
- **Validation**: leave-one-station-out CV; back-test against held-out hours.
- **Failure modes**: station outages → flag stale; siting-biased stations → reliability weights; extreme events (Diwali) → widen uncertainty.
- **Moat**: per-station reliability learning + Delhi climatology accumulated over months.
- **Verdict: MVP** — simplest defensible field.

### Method B — Traffic-conditioned enhancement ⭐ MVP-lite
- **What**: additive near-road increment on top of the background field.
- **Method**: edge bump `ΔC = f(road class, speed proxy, hour-of-day, upwind/downwind)`, calibrated so decay ≈75% within 30 m, tails within ~500 m (per near-road literature). Speed proxy: time-of-day congestion prior from OSM road class + optional TomTom/Mappls live traffic on key corridors.
- **Accuracy**: increments of 0.1–2 µg/m³ PM2.5 (US near-road); Delhi arterial increments likely higher — treat as calibrated factor with wide uncertainty, not precise physics.
- **Verdict: MVP-lite** — justified because it's the difference between "road side" and "park side" decisions; keep it one transparent function, not a model.

### Method C — Kalman / state-space temporal fusion — V2
- **What**: per-station latent true-concentration state, correcting sensor bias/drift over time.
- **Why later**: pays off only after months of stored observations; needs the historical pipeline first. Real moat (self-improving calibration), wrong week to build it.

### Method D — Gaussian-process / Bayesian field — CUT (for now)
- Beautiful math, but at 46 stations it converges to the same answer as kriging with 10× the engineering cost. Revisit if low-cost sensor data appears.

### Method E — Physics-informed ML / GNN on road graph — V2
- Justified only with the historical corpus; the hackathon version earns nothing a tuned regression-kriging doesn't. Keep as documented moat path.

### Method F — Full dispersion modeling (street canyon, WRF-Chem-class) — CUT for product; cite as science
- Needs emissions inventories that are publicly stale (2018 SAFAR / 2021 TERI — the reason CAQM dropped DSS). We explicitly do NOT claim mechanistic dispersion; our near-road bump is empirical.

## 2. Personal exposure & dose model ⭐ MVP

**Dose for a trip** = Σ over legs: `D_leg = C̄_leg × IR(mode, activity) × t_leg`

where `IR` = ventilation rate (m³/h), `C̄_leg` = in-vehicle/in-microenvironment concentration.

### In-microenvironment ratio table (from published Delhi studies — measured, not assumed)

| Mode | In-microenvironment PM2.5 vs ambient on-road | Inhaled/km vs metro |
|---|---|---|
| Metro | lowest (~0.3–0.5× ambient) | 1× (baseline) |
| AC car | ~0.5–0.7× | low |
| AC bus | ~0.6–0.8× | low |
| Non-AC car | ~0.8–1.0× | medium |
| Bus (non-AC) | ~0.9–1.0× | medium |
| Auto-rickshaw | ~1.0–1.2× | **5.3×** |
| Bicycle | ~1.0–1.1× (but highest IR) | highest dose |
| Walking | ~1.0× ambient | **28.2×** (slow + high IR) |

Sources: Delhi transport-microenvironment studies (see doc 01 §7). We publish the table in-app — the honesty is the brand.

### Ventilation rates (IR)
Standard exposure-science values by activity (sitting ~0.4–0.5 m³/h; walking ~1.0–1.5; cycling ~1.6–2.5 m³/h). Parameter-sweep in validation; show the sensitivity in docs.

### Outputs we can defend
- Estimated dose µg PM2.5 per trip (with ± band)
- % exposure difference between itineraries
- "Equivalent to N minutes at roadside AQI" — relatable unit
- Conf: modeled-with-published-factors, not measured-your-lungs — label exactly that.

### What's explicitly NOT claimed
- Medical outcomes, hospital risk, "you will be healthier" — out of scope, legally and scientifically.
- Indoor/home exposure — different problem, cut.

## 3. Departure-time / temporal model ⭐ MVP-lite

- **What**: dose(itinerary, depart at t) for t ∈ {now … +8h}.
- **Method**: hour-of-day climatology from OpenAQ history per zone (morning-peak bump, evening plateau, post-midnight dip) × today's live field; stubble-season overlay from FIRMS-driven regional load (peaks late-morning→afternoon per the transport studies).
- **Honesty**: this is climatology-conditioned-nowcast, labeled "typical pattern", not a forecast claim. IITM AQEWS is the real forecast — we link it, we don't fake it.

## 4. Route optimization model ⭐ MVP

- **Candidate generation**: OSRM (car, 2W, cycle, walk) + OTP2 (transit itineraries incl. mixed walk+bus+metro). Each returns real geometry + times.
- **Cost per edge**: `w(e) = t(e) + λ·d(e)` where `d(e)` = dose on edge `e`; λ = user's "minutes-per-µg-avoided" tolerance (default slider → 3 presets: Fastest / Balanced / Cleanest).
- **Multi-objective**: return the Pareto frontier (time × dose × cost), not one magic answer — let the UI show the frontier and *recommend* one.
- **Justified math**: weighted shortest path on the OSM graph with exposure-weighted edges = textbook; exposure integral over polyline = Σ C(x)·IR·Δt. That's real math, honestly applied — no buzzwords.

## 5. Emissions model — SCOPED

- **In**: per-edge traffic-linked increment (Method B) + which modes the *user's choice* avoids (e.g., choosing metro over 2W avoids that tailpipe contribution).
- **Out**: city emissions inventory, fleet turnover, cold-start micro-models — can't be validated at hackathon scale; cut, listed in V2.
- Honest framing: we model *exposure consequences of choices*, and separately note *system benefit when many people switch* — never merge the two numbers.

## 6. Uncertainty propagation ⭐ MVP

- Kriging variance → per-segment σ → Monte-Carlo (n=200, vectorized) through the dose integral → per-itinerary dose interval.
- Output as "120–180 µg est." not "152.3 µg". This is the product's integrity in one feature.

## 7. Verdict summary

| Model | Verdict |
|---|---|
| Station field via regression-kriging | MVP |
| Near-road traffic increment (empirical) | MVP-lite |
| Mode-dose integral (published factors) | MVP |
| Departure-time climatology | MVP-lite |
| Pareto route scoring | MVP |
| MC uncertainty bands | MVP |
| Kalman temporal fusion | V2 |
| GNN/physics-ML field | V2 |
| Full dispersion modeling | CUT |
| Emissions inventory modeling | CUT (note in V2) |
| LLM decision layer | Optional narrator only — never computes numbers |
