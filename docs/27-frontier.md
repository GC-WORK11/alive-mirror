# 27 · The Frontier — verify or destroy "world-first"

*Research deliverable, 2026-10-03. Question under test: is (a) inhaled-dose
turn-by-turn navigation and (b) hardware-free passive citizen air-mapping
really unshipped anywhere on Earth? Answer first, sweep second, then the
next frontier, honestly ranked.*

---

## 0. Verdict up front

**Claim (a) — SURVIVES, but only in narrowed form.** "AQ-aware navigation"
is now a *shipped product category*: five consumer/gov tools launched
route-by-air-quality between 2023-2026, and two of them do real
turn-by-turn. What nobody ships is **inhaled dose (µg) computed across
motorized urban modes and accumulated live during navigation**. The
claim must be restated as *"first inhaled-dose turn-by-turn for a real
multimodal commute"* — and it is perishable: the closest competitor
already has both halves of the mechanism.

**Claim (b) — SURVIVES, and is the stronger of the two.** Every citizen
air map ever built needed hardware you buy or a report you file.
Nobody runs a loop where taking a trip *is* the observation and the
public field gets better because you drove through it. With one honesty
correction: GPS traversals cannot *measure* PM — so the world-first is a
**citizen dose-map** (aggregated experienced exposure), not a citizen
*concentration* measurement. Phrase it wrong and a smart jury kills it.

| Claim | Status | Must be worded as |
|---|---|---|
| (a) inhaled-dose TBT | Narrowed, alive | "first inhaled-µg turn-by-turn across real commute modes" |
| (b) passive citizen mapping | Alive | "first hardware-free citizen dose/exposure map" |

---

## 1. The sweep — everything that touched this space, 2020–2026

Columns: **alive?** · **C vs D** — does it compute concentration (µg/m³,
AQI) or inhaled dose (conc × ventilation × time × microenv) ·
**personal/city** — does it answer "what will *I* inhale" or "what is
the air like" · **depth** — real data plumbing or presentation layer.

### 1.1 Live products (the dangerous set)

| Product | Alive | C vs D | Personal/City | Depth | Why it doesn't kill us |
|---|---|---|---|---|---|
| **AirTrack** (Air Aware Labs, UK) | **LIVE — Plan a Route TBT shipped 2026-07-15** | Dose ("AirTrack Score", inhaled dose in API) | Personal, 24/7 background | Real — GEOS-CF/CAMS field, microenv adjust, Strava/Garmin/Health sync, indoor infiltration model | Walk/run/cycle only. No motorized modes, no metro. No turn-by-turn *dose counter* — dose accrues in background, routes are scored pre-trip. No citizen loop — your trips feed *your* score, not the public field. UK/sports, premium-gated. [site](https://www.airawarelabs.com/airtrack), [TBT launch](https://www.airawarelabs.com/article/air-aware-labs-gets-planning), [App Store](https://apps.apple.com/us/app/airtrack-breathe-cleaner/id6739182650) |
| **CleanRoute** (iOS) | Live 2025-26 | C (CleanScore) | Personal | TBT for drivers, fastest-vs-cleaner, smart-leave alerts | Driving-only, concentration not dose, US-centric, no citizen loop. [App Store](https://apps.apple.com/us/app/cleanroute-navigation/id6760449094) |
| **AQI Path** (Intellimax, India) | Live | C (AQI) | Personal | TBT walk/cycle/run/**drive**, loop routes, reroute alerts | Concentration-weighted, no dose model, no modes, no citizen layer. But: an Indian-built AQ-TBT app *exists* — kills any lazy "nobody shipped AQ navigation" phrasing. [App Store](https://apps.apple.com/ca/app/aqi-path/id6754751849) |
| **Clean Air Routes London** (Westminster × CERC) | **Live since 2025-09-22** | C (+airTEXT forecast) | City tool | Gov-built, 3 ranked walk/cycle routes by exposure | A city gov shipped clean routing — proof of demand; London-locked, walk/cycle, no dose counter. [launch](https://www.westminster.gov.uk/news/westminster-council-launches-clean-air-routes-london-reduce-public-exposure-air-pollution), [tool](https://carl.westminster.gov.uk/) |
| **Ambee Clean Routing** | Live B2B API | C (6 pollutants + 12 pollen) | Personal routes | Proven at ad-campaign scale: Allegra Airways 325K routes, $3M sales, Cannes Lion | B2B only, no consumer surface, concentration ranking, no modes. [Ambee](https://www.getambee.com/products/clean-routing) |
| **Google Air Quality API** (BreezoMeter IP) | Live GA, forecast endpoint added | C | City/point | 500m field, 96h forecast, India covered (`ind_cpcb`) | Google bought the routing pioneer ~$200M+, folded it into a *data API*, and never shipped consumer AQ routing — but holds a Dec-2024 patent on it (US20240418520). The API's existence means our field is not novel; the routing layer on top is what's empty. [docs](https://developers.google.com/maps/documentation/air-quality/overview), [patent](https://www.patents-review.com/a/20240418520-integrating-air-quality-urban-navigation.html) |
| **IQAir AirVisual** | Live, category king | C | City/point | 500K locations, forecasts, own sensor network | Data browser. No routing, no dose. [App Store](https://apps.apple.com/us/app/iqair-airvisual-air-quality/id1048912974) |
| **Sameer 2.0** (CPCB) | **Revamped 2025-09-23** | C | City/point | Interactive map, AQI calendar, *"location-based exposure identification"*, personalised alerts | Official app now nibbles at our frame — still station-echo + complaint tickets; complaints outside NCR go to email black holes. [HT](https://www.hindustantimes.com/cities/delhi-news/cpcbs-sameer-app-now-has-map-calendar-for-aqi-updates-101758565802523.html), [Deccan](https://www.deccanchronicle.com/southern-states/telangana/sameer-app-dysfunctional-complaints-go-unattended-1854571) |
| **Green Delhi** (DPCC) | Live, real scale | C | City | **84,765 complaints in 2024**, 85–97% resolved per agency | Working enforcement loop — but reports die in ticket queues; nothing feeds an exposure map. Proof Delhiites will report if the loop visibly closes. [ET](https://economictimes.indiatimes.com/news/india/delhi-govt-receives-over-84000-pollution-complaints-through-green-delhi-app-this-year/articleshow/116652458.cms) |
| **Meersens** | Live B2B | Exposure assistant | Personal | Exposome tracking, alerts | Invite-gated (employers/municipalities), not navigation. |
| **N.America smoke forecasters** (CA Smoke Spotter, Guidepole, SmokeWx, TrailSmoke) | Live | C | Personal alerts | 24–72h plume forecasts (BlueSky, NOAA HRRR-Smoke), "warned before it reaches you" | **Destroys "plume-arrival ETA" as a generic world-first** — US wildfire apps already do plume ETA + alerts. Ours can only claim *first for stubble/parali into a specific Indian megacity*. [CARB](https://ww2.arb.ca.gov/resources/fact-sheets/california-smoke-spotter), [Guidepole](https://guidepole.com/fire) |
| **Airveda / Prana / Oizom / aqi.in** | Live | C | City | Indian sensor cos; station display + own-device data | Display + hardware tie-in. Airveda Roam is a GPS-tagged *hardware* monitor that plots route AQ — citizen mapping, but you buy the device. [Roam](https://www.airveda.com/roam) |

### 1.2 Dead / absorbed (the cautionary list)

| Product | Fate | What it did | Lesson |
|---|---|---|---|
| **BreezoMeter** | Google acquired 2022; consumer app killed 2023 | Cleanest Route API (route AQ scores for brands) | Google paid $200-250M for this exact idea, then shelved the consumer surface. Market validated, seat empty. |
| **Plume Labs Flow** | AccuWeather 2022; sales ended 2023 | Personal PM *hardware* + app | Hardware exposure-tracking died at €200/unit. Software-dose is the surviving path. |
| **Dyson Zone** | Killed mid-2025 | Headphones logging personal air exposure | Even Dyson couldn't sell exposure hardware. Reinforces software-only dose. [WIRED](https://www.wired.com/story/dyson-has-killed-its-bizarre-zone-air-purifying-headphones/) |
| **Clean Air Route Finder** (CRP×Imperial) | **Shut 2024-07-04** after 9 yrs | Modelled dose (conc × distance × **ventilation**) per route, walk/cycle | Closest dose-routing precedent, city-locked, died quietly — replaced in spirit by Westminster CARL. Dose math on routes is *not* new; live dose during nav is. [CRP](https://crossriverpartnership.org/projects/clean-air-route-finder/) |
| **CleanSpace** (Drayson) | Faded ~2017 | Phone auto-tracked journeys for "CleanMiles" rewards; AQ map from models + planned Tag hardware | Passive journey tracking existed — but for gamified mode credit, never folded into a public field. Hardware plan never scaled. |
| **Hawa Badlo** (2016) | Dead loop | Photo complaints to authorities | Complaint-to-black-hole dies. |
| **hackAIR / CITI-SENSE** | Projects ended | Crowdsourced AQ *perception* reports + open-hardware sensors | Manual perception reports ≠ measurements; needed effort or DIY hardware. |
| **KT Air Map** (Korea) | Korea-only | 2,000-station telco network + alley-level app | The national-density strategy can't be copied; its *alley-level* promise is what users wanted. |

### 1.3 Academic frontier (published, never productized)

| System | City | Contribution | Why it stayed a paper |
|---|---|---|---|
| **DRUM** (IIT-KGP, TRR 2025) | **Delhi** | Web app: LEAP route −53% exposure vs +42% time, Central Delhi | **Most dangerous precedent.** Same city, same claim — but WAQI station-echo, concentration-weighted, no dose model, no modes, simulation-only. DRUM 2.0 *plans* crowdsourced sensors — hardware again. [Hindu](https://www.thehindu.com/sci-tech/energy-and-environment/iit-kgp-app-helps-commuters-pick-greener-routes-on-the-road/article69644558.ece), [TRR](https://sage.cnpereading.com/doi/10.1177/03611981251331011) |
| **AIRDELHI** (IIT-Delhi, NeurIPS'23) | **Delhi** | 13 DIMTS buses × 3 months IoT PM sensors, 559 km², public dataset | The paper itself names "pollution-free route recommendation" as motivation — never built. Our traversal approach is the hardware-free version of their bus fleet. [site](https://www.cse.iitd.ac.in/pollutiondata/delhi), [paper](https://proceedings.neurips.cc/paper_files/paper/2023/file/ee799aff607fcf39c01df6391e96f92c-Paper-Datasets_and_Benchmarks.pdf) |
| **U-Air** (MSRA, KDD'13) | Beijing | Fine-grained AQ inference from stations+traffic+POI | Founded the field-inference lineage; never consumerized. |
| **Green Paths** (U. Helsinki) | Helsinki | Exposure-optimised active-travel routing engine | Prototype software (JORS'21). |
| **CAR** (NTNU Taiwan) | Taipei | −17.1% exposure / +2.4% distance, OSM code public | Proof of tractability; no product. |
| **Leicester** (Frontiers'26), **Barcelona** (AAMAS'25), Thessaloniki | EU cities | Dose-ID evaluated routing; −2–8% typical, max ~60% | Simulations. Importantly: *dose* is now an academic metric (Leicester reports estimated inhaled dose), so "dose routing" alone isn't a claim — **TBT + live accumulation + motorized microenv** is. |
| **OpenSense** (ETH, 2010s) | Zürich | Tram-mounted sensors; thesis prototyped exposure routing 2015 | Research platform. |
| **ExpoApp** (ISGlobal et al.) | 5 EU cities | Smartphone dose system: location + activity + inhalation rate → inhaled UFP dose | Panel-study tool (158 adults), never consumer. Proves dose-by-phone is publishable science, not sci-fi. [PubMed](https://pubmed.ncbi.nlm.nih.gov/30849577/) |
| **COCAL / Trieste VSN** | Trieste | Crowdsensing PM fleet on buses, 50B readings | Hardware again — confirms the pattern: mobility-based air mapping exists only where sensors were physically mounted. |
| **MAQS / PULSE / DEVA-Compair** | US/EU | Personal exposure apps — every one needed a wearable, a portable monitor, or a sensor network | The hardware requirement is the documented graveyard. |

*Note on the prompt's "PathWeaver": no air-quality system by that name
exists (hits are robotics/ANN/networking tools). The systems it was
probably gesturing at are covered above as Green Paths / CAR / DRUM.*

### 1.4 What the sweep actually establishes

- **"AQ-aware navigation" is a shipped category** — AirTrack TBT (walk/cycle),
  CleanRoute + AQI Path (drive), CARL London (walk/cycle, govt), plus
  BreezoMeter's API lineage. Claiming "first AQ navigation" is dead.
- **"Dose" is now a live metric** — AirTrack computes personal dose
  24/7; its API returns "relative inhaled dose" per route; CARF London
  modelled ventilation-adjusted dose until 2024; Leicester'26 reports
  inhaled dose in its eval. Claiming "first dose math" is dead.
- **Unclaimed intersection**: dose × turn-by-turn × **motorized
  microenvironments** (metro/cabin/rickshaw factors) × live accumulation
  with a receipt. AirTrack has dose + TBT as *adjacent* features; nobody
  has merged them.
- **Unclaimed loop**: public air map updated by traversals of ordinary
  phones. Every citizen map is hardware (Aclima fleets, PurpleAir,
  AirCasting, VSN buses, AIRDELHI, Airveda Roam, MAQS) or manual
  reports (Green Delhi, Sameer, hackAIR, Meersens). Nobody does
  passive-inference citizen mapping.
- **Delhi-specific**: nothing shipped does a single Delhi-native mode —
  metro coaches, rickshaws, AC/non-AC cabins, buses — although Delhi's
  own literature already measured the factors (walk = 28.2× metro
  inhaled/km; rickshaw 5.3×; Magenta-line run-averages metro 34.2 vs
  rickshaw 113.2 µg/m³). [ScienceDirect](https://www.sciencedirect.com/science/article/abs/pii/S1309104220303457), [Springer'25](https://link.springer.com/article/10.1007/s44292-025-00071-5)

---

## 2. The Delhi gap — science built, product never shipped

Delhi has world-class research instrumentation and zero consumer
translation. The gap is the product thesis itself.

| Asset | Built by | What it does | Why citizens can't touch it |
|---|---|---|---|
| **IITM DSS** | IITM Pune / MoES | Daily source apportionment incl. **stubble % forecast** for next days (WRF-Chem + TERI inventory + CPCB assimilation) | Policymaker bulletin; portal itself flaky (private-IP DNS); city-level, no neighborhood ETA. [dss](https://ews.tropmet.res.in/dss/index.php) |
| **AQEWS** | IITM | 7–10 day severe-episode early warning | Feeds GRAP decisions, not consumer decisions. [ews](https://ews.tropmet.res.in/index-2.php) |
| **SAFAR-Air** | IITM | Official SAFAR app | Display-only, stale. |
| **AIRDELHI** | IIT Delhi | Bus-mounted PM network dataset | Released as data; nobody productized it. |
| **DRUM** | IIT-KGP | Delhi exposure routing | Simulation, no app store, WAQI-sourced. |
| **Green Delhi + Sameer** | DPCC/CPCB | ~85K complaints/yr processed | Reports → tickets, never → map. |
| **Bhuvan + IARI CREAMS + CAQM protocol** | ISRO/IARI/CAQM | Operational daily farm-fire counts, district-wise, seasonal | Raw feed for officials; no consumer plume product. [PIB](https://www.pib.gov.in/PressReleseDetailm.aspx?PRID=2223752&lang=1&reg=3) |
| **Mode-dose literature** | IIT/TERI/AIIMS orbit | 28.2×/5.3× factors; metro-vs-rickshaw runs; rickshaw-driver health | Published numbers, unused by any product until now. |
| **Gig-worker exposure** | NIT Calicut/CPR et al. | Delivery riders breathe illegal air; 67% unaware | Documented workforce, zero tooling. [Mongabay](https://india.mongabay.com/2023/08/gig-workers-in-india-are-exposed-to-highly-polluted-air-and-carcinogens-finds-preliminary-study/) |
| **Smog tower / Pariyayantra** | Govt/Manav Rachna | ₹20cr+ spectacle; bus-mounted filters pilot | Hardware stunts, died as pilots, produced no data layer. |

**The sentence that writes itself for the video**: *"IIT measured the
air, IITM forecast it, ISRO counts the fires, and citizens filed 85,000
complaints last year — and still nobody told a Delhiite what today's
commute cost their lungs."*

---

## 3. Candidate frontier features — ranked honestly

Ranking = (first-in-world? × provable-by-Oct-11? × jury legibility).
Each gets: verdict on novelty, 3-day feasibility vs current code, and a
4-line plain-English frame a random Delhi guy would get.

### #1 — The citizen dose-map: every trip measurably updates the public map
**First-in-world: YES — strongest claim we have.** Every predecessor
needed hardware (Aclima fleets, PurpleAir, AIRDELHI buses, AirCasting,
Airveda Roam, MAQS) or manual reports (Green Delhi, Sameer, hackAIR).
No shipped product folds utility-coupled traversals into a public
exposure map. **Honesty correction**: traversals don't measure PM —
the world-first is a map of *experienced dose* ("this corridor cost
commuters 2.3 cigarettes this week") + coverage/freshness + reports
verified against the live field — not "citizen-measured concentration."
**Provable in 3 days:** YES — `/observe`, corridor cells, CorridorLayer
already exist; delta is traversal-weighted confidence into `/route` +
per-corridor freshness decay + the "measured by N commutes" line.
**Frame**: *"Google shows you traffic because every phone reports its
speed. This app does the same for air — every ride you take makes the
city's pollution map a little more true, and you never tap a thing."*
**Tier: ENGINEERING BREAKTHROUGH** (see §4).

### #2 — Live inhaled-dose meter during navigation + the dose receipt
**First-in-world: YES in merged form.** AQ-TBT shipped (×5); personal
dose tracking shipped (AirTrack). Nobody accumulates µg *during* nav
with per-maneuver attribution and an end-of-trip receipt vs the
alternatives you rejected ("fastest route: +61µg"). **Perishability
warning**: AirTrack has both halves adjacent; a sprint apart from doing
exactly this. Window is weeks-to-months, not years. **Provable:** YES —
nav mode + "breathing N µg/m³" already shipped; delta is per-step
accumulator + receipt screen + delta-vs-rejected math. 1–2 days.
**Frame**: *"Your fuel gauge, but for your lungs. Watch the number
climb when you're stuck behind a truck, and at the end see the receipt:
this trip cost 214 micrograms — the metro option would have cost 38."*
**Tier: breakthrough-PROOF — the demo that makes #1 visible.**

### #3 — Driver-shift occupational dose record
**First-in-world: likely YES.** Gig-worker exposure is documented
science (Ghaziabad delivery riders; Delhi auto/vendors/sweepers studies)
with zero shipped tooling. A Rapido/Uber/porter driver's 10–12h shift
is the highest-dose job in the city and nobody measures it. **Honesty**:
needs no new science — reuses the dose engine across a shift; novelty
is the *record* + the framing ("invisible exposed workforce"), plus
unique data nobody else will generate. **Provable:** YES — `/shift`
exists; delta is shift sessioning + week rollup + a per-platform share
card. **Frame**: *"Ten lakh riders and drivers in this city breathe
traffic for a living and nobody has ever told them what a shift costs.
This is the first logbook for their lungs."*
**Tier: borderline — a feature engineering-wise, a breakthrough in
narrative/data (the only dataset of its kind once live).**

### #4 — Stubble-plume neighborhood arrival forecast
**First-in-world: NO globally, YES for Delhi.** US wildfire apps ship
72h plume ETA + alerts (BlueSky/HRRR-Smoke). But for *parali* smoke
into a specific Delhi neighborhood: nothing consumer exists — DSS gives
a city-level % bulletin, Bhuvan/IARI counts fires for officials.
**Provable:** PARTIAL — FIRMS + wind advection exists in code, October
timing means real fires likely demo-able; but fire→concentration
transfer is genuinely noisy, so ship as a watch-layer ("fires detected
in Punjab, plume likely reaches NCR tomorrow evening") not a precise
ETA, or a judge's fact-check stings. **Frame**: *"The farmers burnt
parali today in Punjab. We tell you when that smoke reaches your
street — before the smell does."*
**Tier: feature (borrowed physics), but the most visceral Delhi-
specific demo of the six.**

### #5 — "Your street breathed X cigarettes today" hyperlocal ledger
**First-in-world: NO.** Shoot! I Smoke did city-level cigarettes since
2018 (open source, Berkeley Earth 22µg/m³≈1 cig rule). Ours is only
new at *street* granularity + traversal-verified + cumulative. Cheap to
ship — the field and ledger already exist — but it's a reframing of
computed numbers. **Frame**: *"You didn't smoke today. Your street
smoked 4 cigarettes for you. Yesterday it was 7 — see the trend on your
own block."*
**Tier: feature — viral-shaped, thin science. Use as a share card, not
a headline.**

### #6 — Citizen-verified hotspot reporting → public map
**First-in-world: NO for reporting, YES for the verification loop.**
Green Delhi processes ~85K complaints/yr; Sameer takes them nationally;
Meersens does whistleblowing. Nobody cross-checks reports against the
live field + traversal traffic and publishes a *verified* public
hotspot layer — reports today vanish into agency queues. **Provable:**
PARTIAL — `/report`+`/reports` exist; "verified" needs the field-
corroboration logic (does our field already see that hotspot? did N
traversals pass through elevated dose there?) — honest version labels
"reported" vs "field-corroborated" separately, never merges them.
**Frame**: *"See something burning? Report it — and unlike the
government app, watch it show up on the map everyone else routes
around."*
**Tier: feature, with one breakthrough-adjacent gear (verification).**

### #7 — School-run exposure planner (bonus, prompt asked for it)
**First-in-world: consumer-YES, research-NO.** Manchester simulated
100K school routes (2015); a 200-taxi fleet study computed real
school-commute doses. No consumer planner. **Provable:** YES — it's a
subset of existing routing + a kid-scaled dose number. **Frame**: *"The
school bus sits in the Ring Road jam for forty minutes. Metro plus a
ten-minute walk costs your kid a third of the dose. Pick for their
lungs, not just the clock."*
**Tier: feature — but possibly the highest-emotional-value line in the
video.**

---

## 4. The line: raw engineering breakthrough vs app feature

A jury says "breakthrough" when removing the thing requires *new data
or new physics* — when a competent team can't rebuild it in a weekend
from public APIs. They say "app feature" when the data already existed
and you arranged it nicer.

Apply the test:

| Candidate | New data created? | New physics/plumbing? | Verdict |
|---|---|---|---|
| #1 citizen dose-map | **YES — aggregated experienced-dose per corridor, a quantity that didn't exist** | Traversal-weighted confidence, freshness decay, report-vs-field corroboration | **BREAKTHROUGH** |
| #2 live dose meter | Marginal (per-trip dose records) | Per-maneuver attribution + alternatives delta — engine already ours | Breakthrough's *demonstrator* — the proof #1's numbers are real |
| #3 driver-shift record | **YES — first occupational dose dataset** | None new (shift sessioning) | Feature engineered / breakthrough narrated |
| #4 stubble ETA | No | Borrowed advection (NA smoke apps did it) | Feature — new geography, old physics |
| #5 cig ledger | No | No | Feature — but made for sharing |
| #6 verified reports | Partial (verified-hotspot layer) | Field-corroboration check | Feature + one breakthrough gear |
| #7 school planner | No | No | Feature — emotional hook |

**So the honest architecture is: ONE breakthrough (#1), proven on
camera by #2, made legible to Delhi by #3/#4/#5/#7, verified in
public by #6.** Never present the features as separate inventions —
present them as views onto the same engine. A jury forgives features
orbiting a breakthrough; it punishes five "world-firsts" that share
one pipe.

---

## 5. Claims discipline — say these, never those

| SAFE (defensible) | DEAD (destroyed by evidence) |
|---|---|
| "First inhaled-dose turn-by-turn for real commute modes — metro, car, rickshaw" | "First air-quality navigation" (AirTrack, CleanRoute, AQI Path, CARL, HealthyPlaces) |
| "First citizen air map built with zero hardware and zero effort" | "First dose computation" (AirTrack ships dose tracking; CARF modelled ventilation dose till 2024) |
| "First product to use Delhi's own measured mode-dose factors" | "First exposure routing for Delhi" (DRUM/IIT-KGP — simulation, but published and press-covered) |
| "Delhi's stubble smoke, forecast to your neighborhood — a consumer first" | "First smoke-plume forecast" (US wildfire apps ship 72h plume ETA) |
| "First public map of what streets actually *cost* the people crossing them" | "First cigarette-equivalent air app" (Shoot! I Smoke, 2018) |
| "First dose receipt: your trip vs the one you didn't take" | "First pollution report app" (Green Delhi ~85K/yr, Sameer, Hawa Badlo) |

**Watch item**: AirTrack is one feature-sprint from collapsing claim
(a) — UK/sports/premium today, but the dose+TBT merge is obvious and
they ship fast (TBT launched Jul 2026). Our window is open *because*
we're Delhi-multimodal and they're athletic-European. The honest hedge:
claim (b) — the citizen dose-map — has no announced rival anywhere.

---

## 6. Recommended frontier for Oct 8–11

1. **Headline**: "The first air map that gets better every time Delhi
   commutes." (#1 — the breakthrough, defensible, compounding)
2. **Demo spine**: live dose meter through a Ring Road jam + the
   receipt vs the metro you didn't take. (#2 — proof on film)
3. **Delhi soul**: the Rapido-driver shift record and the parali-watch
   layer. (#3/#4 — the jury's "I haven't seen this" moment + the local
   data nobody else has)
4. **Shareable tail**: street-cigarette ledger + school-run pick.
   (#5/#7 — viral shapes, two lines of code each)
5. **Everywhere**: "reported" vs "field-corroborated" labeled
   separately on the public map. (#6 — keeps the honesty moat)

Everything above routes through the engine already shipped:
kriged/advected field → mode-microenv dose → trajectory ledger →
corridor confidence. The frontier isn't six features; it's one
feedback loop nobody else closes.
