# docs/31 — Dual-Objective Routing: inhale less AND emit less

*Research deliverable, 2026-10-03. Question: the product recommends
route×mode×departure — should it optimize personal dose only, trip
emissions only, or both, and what is the honest scoring rule + the
one-line consumer copy when the two objectives disagree?
Per instructions: deep research only, brutal where the literature is.*

Sister docs: 03 (models), 26 (the honest impact ledger — owns *emissions
claim* honesty; this doc owns the *routing/scoring* layer), 27 (frontier).

---

## 0. Verdict up front

**Recommended rule: rank by dose; break near-ties by emissions; label
the trade when they diverge.** Operationally — sort the option set by
expected dose `E[D]` (band-aware); inside the near-tie set (options
whose dose bands overlap, ~±10% of the minimum), pick min emissions;
if the dose winner emits >~10% more than the emissions winner, attach
one signed trade line. This is ε-constraint structure — the *same*
family Google uses for eco-routing ("lowest-carbon route when ETA ≈
fastest") — with dose as our primary and emissions as secondary.

**Why it is the right rule, in three sentences.** (a) Cross-mode the
two objectives are ~always aligned in Delhi — metro/e-bus win both by
3–10×, so a joint scalar would hide agreement that deserves a "wins
both" badge; the real conflict zone is intra-mode (longer-cleaner vs
shorter-dirtier driving alternates) and it is small. (b) Dose is the
only term we measure well (docs/26 kill list already bans per-vehicle
emission precision) — making it primary is both mission and
provability. (c) If a single scalar is ever needed, the calibrated one
is `S = norm(D) + λ·norm(E)` with **λ ≈ 0.15–0.25** on normalized
terms — equivalent to λ ≈ 0.02–0.05 µg per g CO2e in raw units, derived
from Delhi option spreads below — i.e. emissions may flip a ranking
only inside a dose near-tie, never outweigh a real dose gap.

**The honest consumer copy** (tested against every conflict shape we
found):

- Aligned (the common case): *"Metro — best for your lungs **and** for
  Delhi: −172 µg breathed, −1.3 kg CO2e emitted."*
- Conflict (rare, intra-mode): *"Breathes ~15% less, emits ~8% more
  than the fastest. We still pick it — your lungs first, Delhi sees
  the trade line."*
- Never show two "winners". One recommendation + one signed trade line.

---

## 1. Multi-objective routing theory — what the field actually does

### 1.1 The three scalarization families, and who uses which

Given objectives (time, dose, emission, cost), the literature offers
exactly three ways to pick one option — and the choice matters more
for UX than for math:

| Family | Rule | Strengths | Failure mode | Who ships it |
|---|---|---|---|---|
| **Weighted-sum** | score = Σwᵢ·xᵢ, one shortest path | Trivially tractable — collapses to a single-criterion shortest path | Only finds *supported* (convex-frontier) solutions; misses concave-notch Pareto points; weights across unlike units (µg vs kg vs min vs ₹) are uninterpretable to users | Almost every academic AQ-routing paper — edge cost `w(e) = t(e) + λ·d(e)` (CAR Taipei, Green Paths, DRUM, Thessaloniki) |
| **Lexicographic** | optimize objectives in priority order | Consumer-legible ("breathe least, then cleanest"); needs no cross-unit conversion | Ignores *magnitude* of sacrifice on lower objectives — a 1% dose edge can justify a 50% emissions loss | Rarely shipped pure; our dose-first near-tie rule is lexicographic-with-tolerance |
| **ε-constraint** | minimize primary s.t. secondaries ≤ thresholds | Produces exactly the "primary, plus tolerance" behaviour users expect; thresholds are legible ("within 5 min") | Needs a defensible ε | **Google eco-routing**: show lowest-fuel route when its ETA ≈ fastest |

The academic machinery exists for full Pareto search — label-setting
multi-objective Dijkstra/A* (NAMOA*, Martin's algorithm), McRAPTOR for
transit (keeps the arrival-time × transfers × fare Pareto set),
approximate-dominance filters (IJCAI'23 survey; EJOR 2020
classification survey). **We do not need it**: our multi-objective
problem lives at *option* level (8 modes × 2–4 route alternates ×
departure horizons ≈ 20–60 enumerated candidates), not inside the
graph search. Edge-level dose cost is already a weighted sum
(`w(e) = t(e) + λ·d(e)`, docs/03 §4); the frontier is computed by
enumerating and filtering candidates, which is exhaustive and exact at
this scale — a stronger claim than heuristic MOSP.

### 1.2 What eco-routing literature actually optimizes

Eco-routing minimizes **energy/fuel (hence CO2) per trip over edge
costs driven by vehicle dynamics** — speed, grade, congestion,
stop-go events, vehicle/powertrain class — not tailpipe-PM and not
anyone's dose. The canonical results:

| Study | Setup | Measured/claimed savings |
|---|---|---|
| Ericsson et al. 2006 (Lund, 109 real journeys) | Fuel-optimized vs drivers' own route choices | **46% of trips were not on the fuel-optimal route; those trips save ~8.2% fuel on average** |
| Ahn & Rakha 2008 (field GPS, highway vs arterial pair) | Faster-longer highway vs slower-shorter arterial | Slower arterial saved up to **23% energy, 20–71% pollutant emissions** at +17% time — i.e. fastest ≠ cleanest |
| Ahn & Rakha 2013 (Cleveland/Columbus network simulation) | Network-wide eco-routing at varying penetration | **3.3–9.3% network fuel savings** vs time-minimizing; bigger on grid networks, scales with penetration |
| INTEGRATION ECO-SFA (Rakha) | Multi-class dynamic assignment | ~15% fuel savings in favorable scenarios |
| **Google Maps eco-routing (2021– )** | ML fuel/energy model per route; NREL RouteE Powertrain (1M+ real-world drive-cycle miles × FASTSim powertrain library) + EEA data; factors: **engine type (gas/diesel/hybrid/EV), road grade/steepness, real-time + predicted stop-and-go traffic, road type, regional fleet consumption** | **2.4 Mt CO2e "prevented" Oct 2021–Sep 2023** ≈ ~500k fuel cars/yr equivalent (1.2 Mt by end-2022); per-user average −8.14 kg CO2/yr across *all* users. Rolled to India **Jan 2024 incl. two-wheelers** |

**Google's selection rule is the part to steal**: they do NOT show a
weighted score — they surface the lowest-fuel route **when it has
roughly the same arrival time** as the fastest; when the greener route
costs real time, they show the relative savings and let the user
choose (ε-constraint on time, minimize emissions inside the feasible
set). At a billion-user scale, that is the field-tested answer to
"one recommendation vs a frontier": **one recommendation inside a
tolerance band, alternatives priced honestly.**

### 1.3 The documented dose↔emission divergence

The conflict is published, not hypothetical:

- **Alam et al. 2018**: least-dose routes for car occupants **differ
  from, and can emit more CO2 than**, routes optimized on other cost
  bases — dose-optimal ≠ emission-optimal for the same vehicle.
- **Kickhöfer & Kern 2015 (Munich)**: an exposure-internalizing toll
  produces different flows than an emission toll — the two objectives
  conflict at system level.
- **Zhao 2024 (TRD, SF Bay + Tokyo)**: city-scale fuel-sensitive
  routing **pushes traffic onto local streets and increases residents'
  direct exposure** — eco-routing can *create* an exposure externality
  while fixing an emissions one. (Directly relevant to our
  "quieter-road" lever: routing cars through residential streets to
  save fuel exports exposure to the residents.)
- **UCR exposure-routing**: optimizing inhaled mass for roadside
  populations cuts PM2.5 inhaled mass **30–80%** — and costs different
  routes than emission-minimizing would.
- **Freight LER (METRANS)**: low-exposure truck routing cut inhaled
  PM/NOx 11–17% at only ~1% fuel cost — proof the two objectives are
  *sometimes* nearly free to satisfy together. Conflict is a
  possibility set, not a law.

---

## 2. Delhi case analysis — do dose-optimal and emission-optimal fight?

Method: work real Delhi trip shapes through our own factor tables
(docs/03 mode-dose ratios; WRI-India-2015 class CO2 EFs + CEA grid EF
below). Numbers are illustrative bands, not product output.

### 2.1 Three archetype trips

**Trip A — Rajiv Chowk → Nehru Place, ~11 km (Blue/Yellow line
available).**

| Option | Dose (est.) | Emissions (est.) | Time |
|---|---|---|---|
| Metro + walk legs | ~15–25 µg | ~0.15–0.3 kg CO2e | ~35 min |
| Petrol car AC | ~50–100 µg | ~1.1–2.0 kg | ~45 min |
| CNG auto | ~120–220 µg | ~0.8–1.2 kg | ~50 min |

→ **Fully aligned.** Metro dominates on every axis but time. This is
the shape of most of Delhi's core O-D pairs.

**Trip B — Dwarka → Gurugram Cyber Hub, ~18 km (metro = 2-transfer
loop ~85–100 min; car via NH-48 ~35 min).**
- Metro: dose ~35–55 µg (long in-coach leg at ~34 µg/m³ + outdoor
  access/wait legs at ambient), emissions ~0.3–0.5 kg.
- Car AC: dose ~60–110 µg (cabin I/O 0.2–0.6, highway ambient),
  emissions ~1.8–2.7 kg.
- → Same direction (metro wins both) but **the dose margin thins to
  ~1.5–2× while the time penalty explodes**. The real third axis shows
  up: dose vs emission don't fight — dose and time do. This is the
  most common "conflict" the UI will actually render, and it's a
  3-way trade, not a 2-way.

**Trip C — Same-car route alternates: Ring Road (14 km, ~30 min)
vs inner arterial (11 km, ~35 min through congested markets).**
- Driver dose: cabin I/O similar; arterial = higher near-road ambient
  + ~17% more time → dose ~+15–25%. Ring Road wins dose.
- Emissions: arterial burns ~20–30% more fuel/km (stop-go) but is
  ~20% shorter → roughly a wash, usually still worse. Ring Road wins
  both. **Congestion-dominated cities align the two objectives —
  stop-go is simultaneously the dose worst and the emissions worst.**
- The true intra-mode conflict needs a *detoured cleaner street*:
  parallel residential road −20–40% ambient (near-road decay,
  docs/08) at +10–25% distance/time → dose-optimal but
  emission-positive. Alam-2018 geometry. Real, but usually a
  *small* trade (±10–30% emission, ±15–40% dose).

### 2.2 Conflict incidence (honest estimate)

| Level | Conflict? | Frequency | Why |
|---|---|---|---|
| Mode vs mode | ~Never | <5% of option sets | Dose ratios (3–28×) and emission ratios (3–10×) point the same way; both are dominated by the cabin/coach microenvironment |
| Route alternates, same mode | Sometimes | ~10–25% of alternate pairs (bounded by when a parallel lower-ambient street exists that adds distance) | Ambient field varies ~±20–40% at 100–300 m; emission scales with km + stop-go — a cleaner detour pays dose only if the ambient gain beats the added km |
| Departure times | Aligned | — | Off-peak departure cuts dose AND congestion emissions together |
| System scale | **Can invert** | n/a at demo scale | Zhao-2024: eco-routing everyone through "clean" streets exports exposure to residents — our quieter-road lever has the same moral hazard at scale; flag it, don't ship blind |

**Answer to the prompt's question: in Delhi the objectives align in
the overwhelming majority of decisions** — because the same thing
(motorized road time in ambient traffic) generates both the dose and
the tailpipe. They conflict only in a narrow corridor: same-mode
detours and cabin-vs-coach edge cases. The honest resolution is a
**single recommendation with a signed trade line** — not two winners,
not a hidden scalar.

---

## 3. Mode-level reality — does counting emissions make transit always win?

### 3.1 The three accounting choices, and what each does to the answer

| Accounting boundary | Metro/e-bus | Verdict on "transit always wins" |
|---|---|---|
| **Tailpipe only** | Zero by construction | Transit wins trivially — and a sharp judge calls it rigged. Do not ship this alone. |
| **Tailpipe + generation (well-to-wheel, the right demo boundary)** | Metro ~10–25 g CO2e/pkm; e-bus ~20–60 g/pkm | **Transit still wins — by ~3–8× over car, not infinity — and now the claim survives the "coal-powered metro" rebuttal.** This is the defensible boundary. |
| **Full LCA (infrastructure + vehicle manufacturing amortized)** | +~10–30% on electricity-side | Correct boundary for papers; unjustifiable precision at demo scale — cite it, don't compute it. |

**Delhi numbers at the WTW boundary:**

| Mode | Energy basis | CO2e/pkm (est. band) | Basis |
|---|---|---|---|
| Metro (DMRC) | ~0.3–0.4 kWh/pax-trip ÷ ~17 km avg trip ≈ ~20 Wh/pkm; grid OM 0.823 → ~17 g; DMRC self-reports ~33% renewable (Rewa RUMSL 354 MU FY25 + 51.4 MWp rooftop) → **~11–25 g** | 11–25 g | DMRC Carbon Reduction Plan 2025; CEA v19–20 grid EF; 235.8 cr journeys/64.6 lakh daily 2025 |
| e-Bus (12 m) | 0.98–1.3 kWh/km (ITDP rollout guide: Hyderabad 0.98, Pune 1.3) × OM 0.823 ≈ 0.8–1.07 kg/km ÷ 15–40 onboard | 20–60 g | ITDP 2022; DTC fleet 4,538 e-buses (Apr 2026, largest in India); overnight depot charging = coal-heavy marginal grid |
| CNG bus | ~0.7–0.9 kg/km ÷ 15–40 | 20–60 g | WRI-India class EF; occupancy-dependent |
| CNG auto | ~0.08–0.11 kg/km ÷ ~1.3 | 60–90 g | WRI-India 2015 |
| Petrol 2W | ~0.04–0.06 kg/km ÷ ~1.3 | 35–50 g | WRI-India 2015 |
| Petrol car | 0.10–0.27 kg/km ÷ ~1.4 | 80–190 g | WRI-India 2015 (docs/26) |
| Walk/cycle | ~0 (food-energy aside) | ~0 | — |

*Occupancy is the load-bearing assumption: Delhi bus ridership fell to
~40.8 lakh/day (DTC+cluster 2024-25, −20% vs 2019-20) — an empty
e-bus (~60 g/pkm at 15 riders) can lose to a full 2W. We use
fleet-average occupancy and say so.*

### 3.2 The precedent that keeps us honest: CRRI's own finding

Sharma et al. (CRRI, *Atmospheric Pollution Research* 2014) ran the
exact accounting for Delhi Metro phases I–II: CO2 *saved* by road→metro
modal shift **≈ CO2 produced by metro electricity consumption — "the
present modal shift scenario does not yield CO2 benefits."** At 2006–
2011 ridership and a coal-heavy grid, the metro's net CO2 benefit was
~zero; only ridership growth + energy conservation + the 33% RE share
flipped it positive. DMRC's own UNFCCC CDM project (first metro in the
world to claim carbon credits, ~5.16 lakh CERs/yr Phase II) *is* the
include-electricity accounting — the metro could not have registered
credits while pretending its electricity was free.

**Defensible rule: include generation emissions at the grid margin
(CEA OM/CM ~0.82–0.92 kg/kWh), disclose DMRC's RE share as a
credit, disclose occupancy.** Excluding them makes transit win by
definition and invites the rebuttal; including them transit still wins
by a multiple — the honest multiple is the stronger claim.

### 3.3 The dose-side caveat to "metro is clean"

Counting emissions fairly does not change the dose ranking — but two
published nuances belong in the doc, not the sales pitch: underground
metro air is metal-rich (Fe/Si particles, indoor > outdoor platforms —
composition differs even when mass is lower), and metro's dose
advantage shrinks when access legs are long walks at ambient air
(Trip B arithmetic). Our dose math already handles both via per-leg
microenvironment factors.

---

## 4. The aggregation claim — what survives at demo scale

Target sentence under test: *"If everyone on our platform took the
recommended option, Delhi emitted X less."*

### 4.1 Google's own method (the template to copy honestly)

Google's 2.4 Mt headline is a **model, stated as one**: tally fuel on
chosen eco-routes, subtract predicted fuel on the fastest-route
counterfactual, apply adjustments (CO2e factor, fleet factor,
well-to-wheels, powertrain mismatch), convert via EPA equivalencies —
with a written admission of "single vehicle-type approximation" and
"inherent uncertainty … we report a central value." Nobody audits the
number because it owns trip telemetry at planetary scale; **we own
nothing like that at demo scale**, so our version must be visibly
conditional.

### 4.2 The three kill-shots on any aggregate claim

1. **Counterfactual unknowability.** A rider who "chose" metro may
   have taken the bus anyway. Delhi's own survey data: **57% of metro
   users shifted from buses, only ~29% from private motor vehicles**
   (binary logit, Open Transportation J. 2016; CRRI 2007/09 shows the
   same direction). Multiplying metro ridership by a car EF
   overestimates the avoided amount ~3×. Any aggregate we show must
   apply a mode-source composition — or label the raw number an
   upper bound.
2. **Rebound / equilibrium effects.** Braess-for-eco-routing is
   proven: when many drivers minimize their own fuel, network
   emissions can *rise* (arXiv 2207.13698, multiclass UE on real city
   networks). Zhao-2024 adds the exposure version — eco-routes
   redistribute traffic exposure onto residential streets. At demo
   scale (<0.1% of VKT) the effect is negligible, but it kills any
   linear scaling claim to city level.
3. **City-scale attribution.** Docs/26 already rules: "Delhi's AQI
   dropped because users rerouted" is a kill-list claim. Even a
   heroic 1-lakh-daily-active, 100%-compliance scenario is ~1–1.5% of
   Delhi VKT (≈1.1 billion avoided VKT/yr vs ~80–95 billion total) →
   ~1% of road-transport emissions → **~0.2–0.3% of Delhi's total
   PM2.5** (transport ≈ 20–25% of inventory). Real, bounded, and
   small. That *is* the honest number — and it sounds stronger as a
   ceiling than inflated.

### 4.3 What IS provable at demo scale

| Claim | Defensible? | Frame |
|---|---|---|
| "Per logged trip, recommendation vs chosen option: −X µg, −Y kg CO2e (band)" | Yes — Tier-2 published method + declared inputs (docs/26) | Per-trip counterfactual vs user's declared/selected alternative — same shape as Google's route-vs-route, more honest per unit |
| "Sum over our logged community traversals: scenario total" | Yes, as **labeled scenario arithmetic** | "If all N logged users had taken the recommendation: modeled −Z kg CO2e this week — a scenario, not a measurement" — the community ledger makes it a countable, on-camera number |
| "At fleet-average EFs, Delhi emits less if mode-shift scales" | Yes as conditional | "Every shifted petrol car-km removes ~0.1–0.15 kg CO2e ±30% + a published PM band" — per-unit claim, never multiplied into a city total |
| "Delhi emitted X less because of our app" | **No — kill list** | Requires fleet-scale VKT attribution we cannot observe |
| Metro-style aggregate ("we take N cars off the road") | Only with the mode-source correction | DMRC's own claim (~387 t/day, 141 kt/yr, WASET; ~6.3 lakh t/yr per CFA) uses vehicle-equivalent conversion + CDM methodology — if we borrow the genre, we borrow the correction factor (~29% PMV share), not just the arithmetic |

---

## 5. The verdict — scoring rule, λ, and the consumer copy

### 5.1 The recommendable single line

**Rank by dose; break near-ties by emissions; show both numbers always;
label the trade when they diverge.**

```text
recommend(option) =
  argmin E[emission]  among { o | dose_band_lo(o) ≤ (1+ε)·min_dose_lo }
  where ε ≈ 0.10 (options whose dose bands overlap the best are "tied")
trade_label shown iff: E[emission](winner) > 1.10 × min_emission
```

- This is Google's ε-constraint shape with our primary: a defensible
  "tied" set first, then emissions decide inside it. It is
  lexicographic dose-first with a tolerance — interpretable, auditable,
  no cross-unit conversion shown to the user.
- ε = 10% on dose matches our field's own band width at decision
  scale — pretending to resolve dose differences smaller than our
  error is fake precision; the near-tie rule converts that honesty
  into the decision rule itself.

### 5.2 If a single scalar is required (e.g. /decide extension)

`S = norm(dose) + λ·norm(emission)` with **λ ≈ 0.15–0.25**, justified
from Delhi data rather than chosen: on a representative option set
(15 km, 8 options) the dose spread is ~150–250 µg while the emission
spread is ~1–2 kg CO2e; requiring the emission term to act only as a
tie-breaker means λ·(emission span) ≤ ~25% of the dose span →
λ ≈ 0.2 normalized (≈ 0.02–0.05 µg per g CO2e raw). Same result from
budget-normalization: dose as % of the 216 µg WHO-24h reference
budget vs CO2e as % of a ~5.5 kg/day per-capita carbon budget
(~2 t/yr India per-capita) — a 15 km car trip is ~99% vs ~30%, a metro
trip ~19% vs ~7% — the two budgets are legible to a consumer as
*separate percentages*, which is why showing both beats fusing them.

**Simpler still — for /decide keep the shipped 3-term score and add
emission as reason+tiebreak**: `em` joins `decision_reasons`
("lowest-emission option") and orders inside the top band, rather
than a 4th weighted term. A 4th term spends legibility for a knob
nobody tunes.

### 5.3 The consumer copy (one line, every conflict shape)

| Case | One line |
|---|---|
| Aligned winner | "Best for your lungs **and** Delhi — −172 µg, −1.3 kg CO2e vs driving." |
| Real trade | "Breathes ~15% less, emits ~8% more than the fastest route — your lungs first." |
| Time-dominated | "−40 µg and −2 kg CO2e by metro — costs +50 min. Your call." |
| Nothing helps | "All options breathe roughly the same on this trip — leaving after 20:00 cuts all of them ~30%." |

Honesty invariants (non-negotiable, inherited from docs/26): fleet
bands not point precision on emissions; "est." on every number; the
counterfactual declared; never merge personal dose and city emissions
into one fake-currency unit — show them as two real numbers.

### 5.4 Product surface (delta over shipped code)

- `/compare`: add `emission_gco2e_band` per option from the WTW table
  above (declared vehicle class or fleet mix); leaf badge when dose
  winner = emission winner; trade line when not.
- `/decide`: keep `0.5·dose + 0.3·risk + 0.2·time`; emissions enter via
  near-tie ordering + "lowest-emission" reason tag — λ lives in the
  near-tie, not in the score.
- Ledger: optional second column "avoided CO2e (band)" — scenario-
  labeled per §4.3, never a city total.
- Quieter-road lever: add the Zhao-2024 caveat — a quieter street that
  adds fuel exports exposure *and* emissions to residents; cap detour
  suggestions at the existing ≥8% dose / ≤25% time gate and disclose
  the emission delta when it's positive.

---

## 6. Sources

- Ahn & Rakha (2008): *Effects of route choice decisions on vehicle
  energy consumption and emissions* — highway-vs-arterial — `sciencedirect.com/science/article/abs/pii/S1361920908000047`
- Ahn & Rakha (2013): *Network-wide impacts of eco-routing* — 3.3–9.3%
  — `sciencedirect.com/science/article/abs/pii/S1361920913001259`
- Ericsson, Larsson, Brundell-Freij (2006): *Optimizing route choice
  for lowest fuel consumption* — Lund, 46% of trips suboptimal, 8.2%
  — `sciencedirect.com/science/article/abs/pii/S0968090X06000799`
- Alam et al. (2018) + Kickhöfer & Kern (2015) + Bandeira — via
- Zhao et al. (2024): *Spatial system perspective of fuel-sensitive
  routes*, TRD — eco-routing raises residential exposure —
  `repositum.tuwien.at/bitstream/20.500.12708/205319/1/...`
- arXiv 2207.13698: *How Does Eco-Routing Affect Total System
  Emissions?* — Braess paradox for eco-routing — `ar5iv.labs.arxiv.org/html/2207.13698`
- UCR/CERT: *Vehicle Routing to Mitigate Human Exposure* — 30–80%
  inhaled-mass cut — `cert.ucr.edu/sites/default/files/2020-08/...`
- METRANS LER truck study — 11–17% inhaled cut at ~1% fuel —
  `metrans.org/assets/research/psr-20-20_boriboonsomsin_final-report_v2.pdf`
- EJOR (2020): *Objectives and methods in multi-objective routing* —
  survey/classification; IJCAI'23: *Heuristic-search approaches for
  the multi-objective shortest-path problem* — label-setting/lex/ε-dominance
  — `ijcai.org/proceedings/2023/0757.pdf`
- Google: eco-routes docs (factors, ε-ETA rule) —
  `developers.google.com/maps/documentation/routes/eco-routes`;
  2023 Environmental Report (model + 1.2 Mt + adjustments + caveats) —
  `blog.google/company-news/outreach-and-initiatives/sustainability/environmental-impact-report-2023/`;
  2.4 Mt Oct-21→Sep-23 + India launch Jan-2024 incl. 2W —
  `ianslive.in/google-maps-to-bring-fuel-efficient-routing-...`;
  per-user −8.14 kg/yr — `toolsofchange.com/en/case-studies/detail/769/`
- NREL RouteE (Powertrain: drive-cycle miles × FASTSim; Compass
  routing) — `nrel.gov/transportation/route-energy-prediction-model`,
  `nrel.gov/grid/news/program/2021/google-taps-nrel-expertise-...`
- DMRC Carbon Reduction Plan (33% RE FY25, Rewa 354 MU, 51.4 MWp,
  752 MU/yr energy split traction/non-traction) —
  `backend.delhimetrorail.com/documents/9405/Carbon-Reduction-Plan.pdf`;
  IIT-B DMRC energy deck — `ee.iitb.ac.in/~belur/railways/workshop/files/d3_sharat.pdf`
- DMRC ridership 235.8 cr journeys/64.6 lakh daily 2025 —
  `infra.economictimes.indiatimes.com/.../delhi-metro-achieves-historic-646-lakh-daily-riders-...`;
  avg trip 16.5→17.4 km — `indianexpress.com/.../delhi-metro-more-lines-rise-in-avg-distance-5640758/`
- Sharma, Singh, Dhyani, Gaur (CRRI, 2014): *Emission reduction from
  MRTS — Delhi metro*, Atmos. Pollution Research — modal-shift CO2 ≈
  metro-electricity CO2 at 2006–11 levels —
  `exa.ai/library/publication/tnvzttwvn6k`
- WASET: *Delhi Metro: A Race towards Zero Emission* — 17.3% motorized
  trips, ~387 t/day — `publications.waset.org/abstracts/157133.pdf`;
  CDM Phase II ~5.16 lakh CERs/yr — `unescap.org/.../Policy-segment2.pdf`;
  CFA "Riding on Debt" cites ~6.3 lakh t/yr claim + >80% of metro
  trips >10 km — `cenfa.org/wp-content/uploads/2018/09/...`
- CEA CO2 Baseline v19 (FY22-23): OM 0.823 / BM 0.971 / CM 0.867
  tCO2/MWh; v20 CM ~0.757 —
  `cea.nic.in/wp-content/uploads/baseline/2024/01/User_Guide__Version_19.0.pdf`,
  `climatiq.io` CEA-v20 record
- Open Transportation J. (2016): *Binary logistic model for mode shift
  into Delhi Metro* — 57% ex-bus / 28.8% ex-PMV —
  `opentransportationjournal.com/VOLUME/10/PAGE/124/FULLTEXT/`;
  CRRI 2007/09 commuter surveys via `downtoearth.org.in/environment/carriage-of-convenience-5`
- ITDP (2022): *Guidance for e-Bus Rollout in Indian Cities* — 12m
  e-bus 0.98–1.3 kWh/km vs CNG/diesel energy —
  `itdp.in/wp-content/uploads/2022/10/Guidance-for-e-Bus-Rollout-in-Indian-Cities.pdf`
- Delhi e-bus fleet 4,538 (DTC, Apr 2026); 2,917 of 5,267 public buses
  Sept 2025 — `en.wikipedia.org/wiki/Delhi_Transport_Corporation`,
  `timesofindia.indiatimes.com/.../dtc-phases-out-iconic-red-green-buses-.../124311865.cms`
- DTC+cluster ridership ~40.8 lakh/day 2024-25 (−20% vs 2019-20);
  DTC 24.3 lakh 2025-26 — Economic Survey of Delhi 2025-26 via
  `timesofindia`/`hindustantimes` Mar-2026 reports
- WRI-India (2015) class CO2 EFs; WRI GHG-Protocol 2019 + WBCSD 2023
  avoided-emissions framing — as cited in docs/26
