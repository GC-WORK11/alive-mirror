# docs/26 — The Honest Impact Ledger

*Research deliverable: every impact claim ALive-108 can make at demo time,
ranked by how a skeptical judge can audit it. For each claim: is it provable,
to what precision, the attack a sharp judge runs, and our honest answer.
Per instructions: brutal. Anything we can't defend is on the kill list.*

Rule inherited from docs/05 and unchanged: *if we can't validate it, we
label it; if we can't label it honestly, we cut it.*

---

## 0. The challenged claim

> "Per-vehicle emission estimates are unprovable — different BS classes,
> fuels, ages, maintenance states."

**Verdict up front: the challenge is correct at point precision and wrong
at fleet precision.** The published methods (ARAI, TERI, ICCT, CPCB-funded
inventories) never estimate a *specific* vehicle — they estimate a
**fleet average per vehicle-class over a km**. The exact same source that
gives us per-class factors gives the standard deviation, and the SD
routinely exceeds the mean (§3.1). So:

- "your car emitted 4.3 g PM2.5" → **unprovable, kill it.**
- "a petrol car-km in Delhi emits ≈0.05 g PM2.5 *on fleet average*, band
  0.02–0.28 g" → **provable, this is literally the published method.**
- The counterfactual ("what you would have emitted") is a **modelling
  choice, not a measurement** — the accepted frameworks (WRI 2019, WBCSD
  2023) say: declare the reference scenario, prefer consequential
  accounting, disclose the band. We do all three.

The strongest version of our pitch is therefore: **lead the emissions
line with CO2e (tight band, ~±30%), present tailpipe-PM2.5 as a wide
fleet band, and lead the whole impact story with dose-avoided (our
provable, differentiating number).**

---

## 1. Auditability tiers

| Tier | What it means | Audit path for the judge |
|---|---|---|
| **1 — Reproducible** | A claim the judge can verify by running the product or re-running our validation | `/compare` output, `test_api.py`, `data/field_validation.md`, server logs |
| **2 — Published method + our inputs** | Standard methodology applied to declared inputs, reported as a band | Citation trail + our assumptions table |
| **3 — Mechanism exists, outcome unprovable** | A real channel/lever we plug into; we can prove the mechanism, not that we caused the outcome | External precedent + our logs of the mechanism firing |
| **4 — Kill list** | Anything requiring city-scale attribution or individual-vehicle truth | — |

---

## 2. The claims ledger, ranked by auditability

### Tier 1 — provable from the product itself (say these verbatim)

| # | Claim | Provable? | Precision | Judge's attack | Honest answer |
|---|---|---|---|---|---|
| 1 | "On the same trip, mode choice changes inhaled PM2.5 by up to ~30×" | Yes — re-run `/compare` on any FROM→TO; the 28.2× (walk) / 5.3× (rickshaw) vs metro per-km dose ratios are **measured in Delhi studies, not our model** | Factor ratios robust even if absolute field is off (attack #4); ratios from cohort-measured microenv campaigns | "Your field model could be wrong" | Ratio claim survives: the *ordering* (metro ≤ AC car < bus < rickshaw < walk < bike) is a literature invariant; docs/05 makes the model fail loudly if it violates it |
| 2 | "Our field model's error vs reference stations is MAE ~22 µg/m³ on the clean-air window (and it *over*-reads in clean air, under-reads in winter)" | Yes — `data/field_validation.md`, reproducible against the OpenAQ S3 archive, 3550 pairs / 85 stations | MAE/RMSE/bias are computed, not asserted | "Cherry-picked window" | Sep 28–30 window is documented as post-monsoon clean regime; winter LOO showed opposite bias — we publish both, which is itself the audit |
| 3 | "You avoided ≈X–Y µg on this trip" (band, never a point) | Yes as an **estimate**: dose = Σ conc(edge) × mode-factor × time; band = field σ × ventilation ±30% | Order-of-magnitude-correct central estimate; honest band width | "False precision" | We show the band and the 'est.' label on every number; no consumer product shows uncertainty — the band is the feature, not the weakness (docs/22 §b#3) |
| 4 | "Ledger: Σ µg avoided, cigarette-equivalents, % of WHO 24-h budget" | Yes — arithmetic over logged trips: 316 µg/cig (Berkeley Earth rule), 216 µg/day budget (WHO 15 µg/m³ × 14.4 m³) | Exact arithmetic; interpretation labeled "reference budget, not a medical threshold" | "Cigarette equivalence is pop science" | The 22 µg/m³-for-a-day ≈ 1 cig equivalence is the published Muller/Muller estimate, used by Berkeley Earth; we cite it in-app (docs/12) |
| 5 | "This corridor was measured by N commutes; data is H hours old" | Yes — `/observe` donations, per-cell counts and freshness are server-countable; CorridorLayer renders it live | Exact counts | "Cold-start numbers are yours" | True — seed traversals are ours and labeled as such in `/admin`; the mechanism is what's proven, coverage scale isn't claimed |
| 6 | "Every trip makes the next estimate better" | Yes — traversal → corridor confidence → field weighting is in the codepath; demo-able by donating a traversal and watching the cell light up | Binary (works / doesn't) | — | This is the compounding story judges like; claim the *mechanism*, never the city outcome |
| 7 | Latency, uptime, station freshness (≥80% <90 min) | Yes — ingest audit + `/meta` | p50/p95 logged | — | Trivially provable; shows engineering honesty |

### Tier 2 — published method + declared inputs, honest band (say these with the label)

| # | Claim | Provable? | Precision | Judge's attack | Honest answer |
|---|---|---|---|---|---|
| 8 | "Avoided **CO2e** if you take metro over a petrol car-km: ≈0.10–0.15 kg/km" | Yes — fuel-burn is a chemistry identity; fleet-avg petrol car EFs 0.103–0.267 kg CO2/km by class (WRI India 2015 table); on-road fuel economy is only ~14–22% worse than certified (Indian PEMS studies) | **±~30% — the tightest emissions number we can show** | "Fleet average isn't my car" | Correct — that's why we ask the user to declare vehicle class (or use fleet mix), and we show the class-table band; still 10–20× tighter than any PM factor |
| 9 | "Avoided **tailpipe PM2.5** per shifted car-km: fleet band ≈0.02–0.28 g (petrol car), ≈0.02–1.3 g (diesel car)" | Yes **as a band** — ASIF fleet-average is *the* published method (ARAI ICAP, Guttikunda Table 5, ICCT Roadmap, harmonized EF dataset 2026) | Order-of-magnitude band; **the source tables themselves give ±SD > mean** (0.050±0.228 g/km petrol car) | "Your band is so wide it's useless" | The width is the truth, published by ARAI/TERI — a point value would be the lie. Google publishes avoided-emissions with an admitted "single vehicle-type approximation"; we disclose our approximation the same way but more precisely |
| 10 | "Mode shift removes *non-tailpipe* PM too — ~86% of Delhi on-road PM10 is non-exhaust (resuspension 79%), and it scales with VKT" | Yes — Delhi-specific peer-reviewed estimate (Sahu/STOTEN, 100 m² inventory); resuspension is allocated per-VKT in every Indian inventory | Direction certain; magnitude ±~50% | "Dust doesn't disappear when one car leaves" | First-order VKT accounting is exactly what IIT-Kanpur/Guttikunda inventories do; per shifted car-km the non-exhaust share *dominates* — the objection actually strengthens our claim |
| 11 | "Delhi's legal fleet floor is ~BS-IV (SC: >10y diesel />15y petrol banned unless BS-IV+, Dec 2025 clarification)" | Yes — NGT orders upheld by SC Oct 2018, modified Dec 2025 | Legal fact | — | Sharpens the counterfactual: the dirtiest vintage classes are already legally off the road; reference fleet ≈ BS-IV+ dominated |

### Tier 3 — real mechanism, unprovable outcome (say these carefully)

| # | Claim | Provable? | Precision | Judge's attack | Honest answer |
|---|---|---|---|---|---|
| 12 | "GRAP-aligned advisory engine: our indicative-GRAP alert fires on the same triggers CAQM uses" | **Mechanism provable** — log our alerts vs CAQM stage invocations; Stage I literally includes "turn off engine at red lights" as a public advisory | Binary firing vs official stages | "Indicative ≠ official" | Labeled "indicative" in-app already; we can demonstrate alignment over the event window, never claim authority |
| 13 | "A report channel exists with tracked resolution (Green Delhi app: ~1 lakh complaints/5 yrs, 87% resolved, 30 departments)" | Channel existence provable; **our-attribution unprovable** | — | "So your app does nothing new" | The precedent proves citizen-reported complaints DO get resolved at scale in Delhi; we claim a smoother path into a real channel, not a new channel |
| 14 | "School-run exposure planning is adoptable (London School Streets: −23% NO2 at drop-off, 18% of parents drove less)" | Precedent provable; Delhi adoption unprovable | — | "Name one Indian school that did this" | We can't — it's a Tier-3 capability claim only. GRAP Stage III already mandates school-hybrid decisions, so the *policy hook* exists; say that, no more |
| 15 | "Traversals are zero-cost sensing that complements the ₹1.5-crore-per-station backbone" | Cost frame provable (Delhi tender ₹9 cr / 6 stations); calibration precedent published (A-PAG anchored 35-sensor design, AirQo 85+2) | — | "A phone GPS trace is not a PM sensor" | Correct and we never claim it is: a traversal records *where and when Delhi commutes* and what dose the field assigns there — a demand/exposure layer, not a concentration sensor. EPA's own category for this whole class is "non-regulatory supplemental monitoring" |

### Kill list — say these and we lose credibility

| Killed claim | Why it dies |
|---|---|
| "Your trip removed X g of PM2.5 from Delhi's air" | Requires the user's true counterfactual vehicle + fleet-wide accounting; we can only estimate a band on a declared class. Point values = indefensible |
| "Per-vehicle exact emissions" | The challenge itself: BS class × fuel × age × maintenance × superemitter tail (14% of vehicles → 17–57% of emissions, Jaiprakash–Habib) + real-world vs lab gap of 3–12× |
| "Delhi's AQI dropped because users rerouted" | City-scale attribution needs fleet-level VKT shifts; docs/05 already forbids merging personal exposure with pollution reduction — keep the two scopes separate everywhere |
| "You prevented an asthma attack / hospitalization" | Dose→outcome needs individual medical exposure-response; WHO-budget % is the honest proxy, and it *reads* stronger on video anyway |
| "Your phone measured 182 µg/m³" | The phone measures nothing; it traverses a model field. Say "the field estimates", never "your phone measured" |
| "We caught N illegal construction sites" | Report filing is provable; enforcement outcome belongs to the agency. Green Delhi's 87% is *their* number, not ours |
| "Stubble burning caused today's bad air" | We cite IITM DSS % (published) — our own source-attribution is unprovable and killed |
| "We reduced X tonnes CO2e" (aggregate) | Sum of fleet-band estimates over unverifiable counterfactuals; Google's headline works because they own the trip telemetry — we don't at demo scale. Claim per-trip band only |
| Any "AI/ML improves X by N%" without a validation run | SIH winners ship "mock AI engines" — the moment we echo that genre, our provable-data differentiator dies |

---

## 3. Research findings per thread

### 3.1 Counterfactual emission accounting — how the accepted methods actually work

**Every serious Indian emission inventory handles heterogeneity the same
way: fleet-average per class × activity, never per-vehicle truth.**

- **ARAI ICAP (2007/2008)** — "Emission Factor development for Indian
  Vehicles," sponsored by oil companies under CPCB/MoEF: chassis-dyno
  testing of in-use 2W/3W/cars/LCV/HCV across vintage bands (pre-1991,
  1991–96, 1996–2000, post-2000, post-2005), commercial vs improved
  fuels. This is the canonical Indian EF source.
- **ASIF framework** (Schipper et al.): Emissions = Activity × modal
  Share × Intensity × Factor — implemented for Delhi by Guttikunda &
  Mohan as `E(v,f,g,p) = NV × S × VKT × EF` summed over vehicle
  type × fuel × age group. ICCT's Roadmap model is the same
  stock-activity-EF shape globally; the ICCT India meta-study confirms
  ASIF is the standard accounting frame.
- **Published Delhi fleet-average factor table** (Guttikunda et al.
  2015, *Atmospheric Environment* 109: "Evolution of on-road vehicle
  exhaust emissions in Delhi" — Table 5, fleet-average ±SD for 2012):

  | Vehicle (fuel) | PM2.5 g/km | NOx g/km |
  |---|---|---|
  | Petrol car (small/mid) | 0.050 ± 0.228 / 0.101 ± 0.257 | 0.243 / 0.376 |
  | Diesel car | 0.162 ± 1.186 / 0.333 ± 1.365 | 0.657 / 1.162 |
  | Petrol 2W 4-stroke | 0.025 ± 0.051 | 0.392 |
  | Petrol 3W 4-stroke | 0.024 ± 0.174 | 0.692 |
  | Diesel taxi | 0.328 ± 1.558 | 1.209 |
  | Diesel bus | 2.672 ± 7.586 | 21.38 |
  | Diesel HDV | 3.975 ± 7.586 | 28.31 |
  | CNG car | 0.016 ± 0.118 | 0.198 |

  **Read the ±: for every diesel row the standard deviation is 2–4×
  the mean.** The literature itself says a point estimate is noise —
  our "fleet band" is not hedging, it is the published answer.
- **Real-world vs lab**: Jaiprakash & Habib (IIT Delhi) on-road chase
  measurements: real diesel-car NOx 3.3–12× literature/lab values,
  CO2 ~3.7×; **superemitters = 14% of traffic producing 17–57% of CO/
  CO2/NOx**. Any per-vehicle claim dies on this tail; fleet-mean claims
  survive because the tail is *inside* the band.
- **Harmonized factor dataset** (De Sarkar, Banerjee, Dey, Phuleria —
  IIT Bombay + CSTEP, Zenodo Aug 2026): India-specific EFs for 6 vehicle
  classes × petrol/diesel/CNG × BS-I→BS-VI in g/km for PM2.5, BC/EC, CO,
  NOx, VOC, CH4, N2O, NH3 — plus ARAI↔Euro(COPERT) and ARAI↔US(MOVES)
  ratio tables. **This is the factor table to wire in if we ever show
  emissions: published, class-fuel-BS resolved, Delhi-relevant.**
- **Avoided-emissions accounting** (the counterfactual frame):
  WRI GHG Protocol working paper *"Estimating and Reporting the
  Comparative Emissions Impacts of Products"* (2019) + WBCSD *"Guidance
  on Avoided Emissions"* (2023): the accepted method is — pick a
  **reference scenario** the product plausibly replaces, prefer
  consequential over attributional accounting, and **disclose** the
  counterfactual. Google's own fuel-efficient-routing claim (2.4 Mt
  CO2e "prevented" Oct 2021–2023) uses route-vs-route counterfactual
  with a publicly admitted *single-vehicle-type approximation*.
  Our method — declared class OR fleet-mix reference, fleet-average EF,
  band reported — is squarely inside accepted practice.
- **Fleet context for the reference scenario**: ~1.33 crore registered
  vehicles (2022), ~79 lakh estimated actually on-road (Mar-2023
  transport-dept estimate), ~90% 2W+cars; legal floor ≈ BS-IV in Delhi
  after the SC Dec-2025 clarification (sub-BS-IV >10y diesel/>15y
  petrol banned; BS-IV+ exempt from age limits). So the honest
  counterfactual fleet is *not* the dirtiest imaginable — which
  narrows the band defensibly.

**Is "declared vehicle class + fleet-average counterfactual + honest
band" the accepted method? Yes — it is the only method anyone
publishes.** The upgrade over a plain fleet average is letting the
user declare class/fuel (a real UX feature), which tightens the band
from city-fleet variance to class variance.

### 3.2 Non-tailpipe emissions — can mode-shift honestly count dust?

- Delhi on-road PM10 (Sahu et al., *STOTEN* 2020, 100 m² inventory):
  **non-exhaust = 86% of traffic PM; resuspension alone 79%**; cars are
  the largest single contributor to traffic PM (34%) *via resuspension*.
- Source apportionment for total PM2.5 (not traffic share): IIT-Kanpur
  2015 — emissions load road dust 38%, vehicles 20%; ambient winter
  vehicles ~28% incl. vehicle-origin secondary nitrate. TERI-ARAI 2018 —
  vehicles 20–23% winter / 18–20% summer; dust 15% winter / 31–34%
  summer; Delhi's own emissions = 36% of its PM2.5 winter.
- **Honest counting rule**: resuspension is allocated per-VKT in every
  Indian inventory (it scales with traffic volume and road dust load).
  A shifted car-km therefore removes its tailpipe EF *and* its
  VKT-proportional resuspension share — counting both is what the
  inventories do. What we must NOT claim: that the dust reservoir
  shrinks (it's a stock that other traffic resuspends). Per-VKT
  marginal accounting = accepted; city-level stock claim = killed.
- **Interesting flip**: since cars contribute more via resuspension
  than tailpipe in Delhi's PM10, a mode-shift claim measured on
  traffic-attributable PM is *larger* than tailpipe-only — a skeptical
  judge arguing "you ignored non-exhaust" actually undercounts us.
- **Measured intervention precedent**: A-PAG + IIT-Delhi (Jul 2023–Mar
  2024), 35 calibrated portable sensors anchored around CAAQMS in
  Jahangirpuri/Rohini/Karol Bagh, difference-of-difference: fixing
  dispersed sources (paving, potholes, footpaths) cut local PM2.5
  **26.6% / 15.7% / 15.3%** — the dust levers are real and measurable
  at hotspot scale, though civic-scale, not app-scale.

### 3.3 Data-infrastructure claims — the accepted value model for citizen/low-cost sensing

- **Cost asymmetry (provable)**: Delhi tender May 2025 — 6 new CAAQMS
  for ₹9 crore ≈ **₹1.5 cr/station** (→46 stations). CPCB halted
  imported CAAQMS procurement for all 131 NCAP cities (Dec 2022)
  explicitly on cost, pending indigenous CSIR-NPL systems. A traversing
  phone costs ₹0 in hardware — but it is **not a sensor** (see killed
  claim): the honest claim is coverage of *exposure-relevant space-time*
  (where people actually commute), not instrument density.
- **The accepted value model** is US EPA's: sensors are
  **"Non-regulatory Supplemental and Informational Monitoring" (NSIM)**
  — hotspots, local trends, forecasting, participatory science,
  emergency response; regulatory compliance stays with reference
  instruments. EPA published performance targets for this class
  (Feb 2021/2024). EU directive equivalent: "indicative measurements"
  tier. Saying our layer is "indicative + supplemental" is the
  *officially sanctioned* framing, not a dodge.
- **Field calibration against a reference field — yes, it's the
  literature's method**: co-location against BAM/CAAQMS then ML or
  regression calibration:
  - PurpleAir PA-II in India (AMT 2023): raw R² 0.55–0.74, NRMSE ≥40%
    → parsimonious seasonal calibration R² 0.82–0.95, NRMSE 20–30%;
    local/seasonal calibration required.
  - NW-IGP 10-month study (npj CAS 2024): raw R² ~0.4 → decision-tree
    RMSE 77.7 → 0.61 µg/m³.
  - AirQo Kampala: 85 sensors anchored on 2 BAM references; RF
    calibration RMSE 18.6 → 7.2 — that network now feeds NEMA capacity
    training for Uganda's air regulations.
  - A-PAG Delhi: portable sensors "anchored around CAAQMS" is exactly
    the architecture our `calibrate.py` uses (IDW-smoothed per-
    instrument debias, LOO-validated) — we can say our method is the
    published Indian pattern.
  - For *traversals* specifically: nothing in the literature pretends
    a phone is a PM sensor; the cited design (A-PAG, AirQo,
    Breathe London Street-View cars) all put *instruments* on moving
    platforms. Our honest version: traversals measure **demand and
    timing**, the field provides concentrations — same fusion as
    London's "exposure along routes" analyses.
- **Citizen data changing policy (the precedents that matter)**:
  - **PurpleAir → EPA**: since Aug 2020 PurpleAir crowdsourced PM2.5
    feeds the federal AirNow Fire & Smoke Map — after QC (dual-channel
    agreement) + a US-wide correction equation + NowCast. Citizen data
    in a *federal product*; the correction layer is the part to imitate.
  - **Safecast**: launched the day after Fukushima; **200M datapoints
    (Feb 2023)**, CC0, largest open radiation dataset; used by
    researchers and municipalities when official data was absent.
    Lesson: openness + instrument ownership made it credible.
  - **Breathe London**: 100 AQMesh pods + research-grade Street-View
    cars; explicitly designed to evaluate ULEZ / Expanded ULEZ /
    Low-Emission Bus Zones — a citizen-adjacent network whose stated
    job was policy evaluation.
  - **NEERI/EDF State-of-Play (2020)**: CSIR-NEERI ran sensor networks
    at 10 Delhi ambient sites + Mumbai; the report's whole thesis:
    "prohibitive cost of CAAQMS leaves blank spots" that sensor layers
    fill — i.e., the value model is *coverage augmentation*, which is
    our exact claim.

### 3.4 Enforcement / action levers — can a product trigger real reduction?

- **GRAP is a real, staged enforcement lever** (CAQM revised schedule
  Dec 2024; invoked *in advance* on IMD/IITM forecast):
  - Stage I (201–300): public Do's/Don'ts including **"do not idle,
    turn off engine at red lights"**; C&D sites ≥500 m² must be
    registered on the state web portal (Directions 11–18, Jun 2021)
    with video fencing, fortnightly self-audit, **and low-cost AQ
    sensors at the site** — the regulator itself mandates the sensor
    class we cite.
  - Stage II (301–400): daily mechanized sweeping + water sprinkling
    at hotspots/heavy corridors; augment CNG/e-bus + metro frequency.
  - Stage III (401–450): ban non-essential C&D work (earthwork,
    demolition, RMC, road work); restrict BS-III petrol / BS-IV diesel
    LMVs + Delhi diesel MGVs; **schools move to hybrid/online for
    junior classes** — the school-run lever is an actual GRAP action.
  - Stage IV (>450): truck entry bans, WFH advisories.
  → Our `/aqi` indicative-GRAP + alert timing is a provable *alignment*
  claim; we can show (log) that our stage warnings pre-date CAQM
  invocations. What we cannot claim: that any site complied *because*
  of us.
- **Report channels with tracked outcomes exist**: Green Delhi App —
  ~84,765 complaints in 2024, ~99,435 over 5 years, **87.48% resolved**
  across 30 departments (DPCC-compiled); MCD 84.8%, PWD 87.6%, DJB
  97.7%. A "file a dust/burning report" affordance that routes into
  this is a provable mechanism. Hawa Badlo (2016) is the corpse —
  complaints into a black hole killed it; Green Delhi is the living
  counter-example.
- **Anti-idling precedent with the honest lesson**: "Red Light On,
  Gaadi Off" (Oct 2020) — govt claimed potential 15–20% vehicular-
  pollution cut, deployed marshals, spent ₹10.46 cr on ads, then had
  to commission a **third-party audit** because the actual effect was
  unmeasured; WRI's own expert noted net benefit only when wait >1 min.
  Lesson: even the government couldn't claim an unmeasured % — and
  neither can we. Advisory-level claims only.
- **Schools**: London School Streets = 350+ timed closures, measured
  −23% NO2 at drop-off, 18% of parents drove less, 81% parent support —
  the measurable-outcome precedent for the school lever. No shipped
  Indian precedent; GRAP Stage-III school advisories are the hook.

### 3.5 What judges rewarded elsewhere (metric language autopsy)

| Competition / winner | What they claimed | The metric that did the work |
|---|---|---|
| **WeMakeDevs First Commit grand prize — Suraksha** | Agentic companion for an aging parent; ₹2L + $3k credits | Not an impact metric at all — **a working, deployed product in the video**. Confirms the rulebook: "if the video does not show it, it does not count" |
| **NASA Airathon (Predict AQ, DrivenData)** | 5 km daily PM2.5/NO2 nowcasts for LA/**Delhi**/Taipei | Pure accuracy leaderboard: winning PM2.5 model **R² = 0.81**. Judges scored a number, not a story |
| **NASA Space Apps 2025 global winner — AiRo** | Industrial AQ management: NASA TEMPO + OSM context + threshold alerts incl. automated calls | Framed as "measurable environmental and social impact" — but the shipped object was a **working alert pipeline**, not an audited outcome |
| **Smart India Hackathon 2025 (PS-25216, Delhi-NCR air)** | Multiple winning teams on "AI source identification + forecast + policy dashboard" | Won on breadth + dashboards; at least one winning repo openly ships a **"mock AI engine (ready for real models)"** — judges didn't audit data provenance. Our edge is being the submission that *can* be audited |
| **Pattern from this event's own rules (docs/15)** | "A small problem solved well beats a big one solved vaguely"; "clean and obvious beats clever and confusing" | The countable thing must be **visible on camera**: the ledger ticking, the corridor lighting, the validation table |

**Meta-lesson**: nobody won an air hackathon with an audited tonnes-of-
PM claim — they won with (a) a live working demo, (b) one concrete
number the judge can see/count, (c) a pipeline that could plausibly
scale. Our visible countable numbers: avoided-µg ledger, cigarette math,
corridor coverage counts, validation MAE. Lead with those; let the
emissions band be the *credible* second act no one else dares to show.

---

## 4. The defensible demo language (what survives cross-examination)

- **Show**: "Same trip: 214 µg by rickshaw, 61 µg by AC car, 8 µg by
  metro — the ratios are measured Delhi numbers, and this band is our
  field model's own published error."
- **Say**: "We estimate, we don't assert. Every number carries its
  band and its source; the ledger sums what we can prove."
- **Emissions line** (if shown): "Fleet-average basis — a petrol
  car-km you don't drive saves roughly 0.1–0.15 kg CO2e *and* a
  published band of tailpipe PM2.5; we use ARAI/TERI fleet factors
  because per-vehicle truth is unprovable — even India's own factor
  tables put ±4× on diesel-car PM."
- **The one-line honest pitch** (replaces docs/15's closer):
  *"We can't clean Delhi's air with an app — and we say so on the
  honesty slide. What we can prove: exactly what every commute costs
  your lungs, up to 30× less on the same trip, a ledger of what you
  avoided — and a sensing layer that gets sharper with every trip."*

## 5. Sources

- ARAI (Aug 2007): *Emission Factor development for Indian Vehicles*, ICAP/CPCB-MoEF+oil cos — `docslib.org/doc/9368879`
- TERI-ARAI (Aug 2018): *Source Apportionment of PM2.5 & PM10 of Delhi NCR* — `teriin.org/sites/default/files/2018-08/Report_SA_AQM-Delhi-NCR_0.pdf`
- IIT-Kanpur/DPCC (2015–16): *Comprehensive Study on Air Pollution and GHGs in Delhi* — road dust 38% PM2.5 load, vehicles 20%, winter vehicles ~28% w/ secondary nitrate — `home.iitk.ac.in/~mukesh/Publications/DPCC_2016_SA study IIT Kanpur report.pdf`
- Guttikunda et al. (2015): *Evolution of on-road vehicle exhaust emissions in Delhi*, Atmos. Env. — fleet-average EF table, ASIF chain — `urbanemissions.info/wp-content/uploads/docs/2015-01-AE-Delhi-Vehicle-Emissions-1990-2030.pdf`
- Guttikunda & Mohan (2014): *Benchmarking vehicle/passenger travel in Delhi* — ASIF + survival age-mix — `urbanemissions.info/wp-content/uploads/docs/2014-11-TBS-Delhi-Veh&Pass-Characteristics.pdf`
- Jaiprakash & Habib (2017–18): on-road EFs IIT-Delhi; real-vs-lit NOx 3.3–12×; superemitters 14%→17–57% — `sciencedirect.com/science/article/abs/pii/S1352231018301389`
- De Sarkar/Banerjee/Dey/Phuleria (Aug 2026): *Development & harmonization of road-transport emission factors for India*, Zenodo — 6 classes × 3 fuels × BS-I→VI g/km — dataset record via `exa.ai/library/publication/jln6v5j3qjq`
- Sahu et al. (2020): *High resolution vehicular PM10 emissions over megacity Delhi*, STOTEN — non-exhaust 86%, resuspension 79% — `sciencedirect.com/science/article/abs/pii/S0048969719342561`
- ICCT (May 2022): *Decarbonizing India's road transport* meta-analysis + Roadmap model docs — `theicct.org/publication/decarbonizing-india-road-transport-may22/`
- WRI GHG Protocol (2019): *Estimating & Reporting the Comparative Emissions Impacts of Products* — `ghgprotocol.org` ; WBCSD (2023): *Guidance on Avoided Emissions*
- Google (Oct 2023): fuel-efficient routing, 2.4 Mt CO2e, single-vehicle-type caveat — `blog.google/company-news/outreach-and-initiatives/sustainability/google-transportation-energy-emissions-reduction/`
- WRI India (2015): *India-Specific Road Transport Emission Factors* (CO2/km by class+fuel) — `shaktifoundation.in/.../WRI-2015-India-Specific-Road-Transport-Emission-Factors-1.pdf`
- NGT OA 21/2014 + SC 29.10.2018 + SC Dec-2025 clarification: >10y diesel/>15y petrol ban limited to sub-BS-IV — `pib.gov.in/PressReleaseIframePage.aspx?PRID=1941044`, `business-standard.com/india-news/sc-ban-old-vehicles-petrol-diesel-bs-vi-delhi-ncr-...`
- Delhi CAAQMS tender: 6 stations ₹9 cr ≈ ₹1.5 cr each — `theprint.in/india/delhi-clears-rs-9-crore-tender-...` ; CPCB halts imported CAAQMS — `timesofindia.indiatimes.com/india/centre-asks-states-not-to-procure-imported-air-quality-monitors-...`
- EPA: *Enhanced Air Sensor Guidebook* + NSIM performance targets — `epa.gov/air-sensor-toolbox` ; PurpleAir on Fire & Smoke Map — `epa.gov/air-sensor-toolbox/technical-approaches-sensor-data-airnow-fire-and-smoke-map`
- AMT (2023): *Seasonally optimized calibrations…PurpleAir in urban & rural India* — `amt.copernicus.org/articles/16/4357/2023/` ; npj CAS (2024) NW-IGP ML calibration — `nature.com/articles/s41612-024-00833-9`
- AirQo/ES:Atmospheres (2025): Kampala 85+2 anchored network → NEMA — `pubs.rsc.org/.../d4ea00081a`
- Safecast: 200M datapoints Feb 2023, CC0 — `safecast.org/200-million-datapoints/` ; IOPscience citizen-science review 2016
- EDF/NEERI/UT-Austin (2020): *State of Play of Low-Cost Sensors for Monitoring PM2.5 (India)* — `edf.org/sites/default/files/documents/State-of-Play-Low-Cost-Sensors-Monitoring-PM2.5-India.pdf`
- Breathe London methodology (ULEZ/LEBZ evaluation role) — `breathelondon.edf.org/methodology.html`
- CAQM: revised GRAP order + Stage tables + C&D Directions 11–18/97 — `caqm.nic.in`
- Green Delhi App stats — `economictimes.indiatimes.com` Dec 2024, `millenniumpost.in` Dec 2025
- Red Light On Gaadi Off — `timesofindia` Oct 2020, `economictimes` Mar 2022 (audit)
- London School Streets monitoring — `london.gov.uk/.../school_streets_monitoring_study_march21.pdf` + TfL release Mar 2021
- A-PAG/IIT-Delhi (Oct 2024): *Dispersed Sources Program impact* — `a-pag.org/wp-content/uploads/2024/10/IITDelhi_ImpactAssessment_Report.pdf`
- Winners: `wemakedevs.org/aws/first-commit/projects` (Suraksha); `blog.drivendata.org/blog/nasa-airathon-winners`; `dvloper.io/blog/the-airo-project-winner-of-the-nasa-space-apps-challenge-2025-2`; SIH-2025 PS-25216 winner repos/announcements
