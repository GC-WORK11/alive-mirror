# docs/32 — Delhi Fleet Ground Truth

*Deep-research deliverable: the consumer-facing "Delhi context" numbers for the
emission/dose dashboard, each traced to a citable source. Rule inherited from
docs/05 and docs/26: every number a judge could fact-check must survive the
check. Where two reputable sources disagree, we print the range, not a pick.*

*All URLs live-verified from this box on 2026-10-03 UTC.*

---

## 0. Verdict up front — the five numbers that survive scrutiny

| # | Say this | Don't say this | Why it survives |
|---|---|---|---|
| 1 | "**~83 lakh vehicles are legally allowed on Delhi's roads today** — the active fleet, after 66+ lakh over-age vehicles were deregistered (Delhi transport dept, Sept 2024; Economic Survey 2025-26). Cumulative registrations on VAHAN: **1.56 crore** (FY 2024-25)." | "Delhi has 12M vehicles" | 12M is neither number — it's below cumulative (15.6M) and above active (8.3M). Both real figures are in official data a judge can pull |
| 2 | "**Roughly two-thirds of Delhi's active fleet is two-wheelers** (56.6 lakh of ~83 lakh; DES data via PTI Jan-2026; DES 2020: 66.3% motorcycles). Cars+jeeps ≈ 20.9 lakh (~25%). Together ~93% of the active fleet." | "70% are two-wheelers" | 68% ≈ two-thirds; "70%" is over-rounding against the current official split |
| 3 | "**~89% of vehicles measured on Delhi roads are BS-IV or BS-VI; ~11% are pre-BS-IV** (TRUE/ICCT remote-sensing, 111,712 tailpipe measurements, Dec 2022–Apr 2023)." | "Delhi is full of BS-III smoke-belchers" | The fleet is already legally BS-IV+ for the oldest classes — the remaining dirty tail is a *minority of the fleet* that produces a *majority of emissions* (super-emitter argument, not a count argument) |
| 4 | "**~31% of Delhi's active vehicles were riding on an expired PUC** — 26.2 lakh of 82.9 lakh (Delhi govt data, ET/ETAuto, Sept 2024)." | "Half the fleet is uncertified" | 31.6% is the published figure; say "nearly a third" |
| 5 | "**Transport is ~18–39% of Delhi's PM2.5 depending on which study and which question** — emissions inventories: IIT-K 20% / SAFAR 39.2% / Guttikunda 17.9% / TERI-ARAI 39% of Delhi's own emissions; ambient concentration: TERI-ARAI 28% winter, 17% summer; daily source-attribution (DSS): ~11–12% typical, lower on stubble-peak days." | "Vehicles cause 40% of Delhi's pollution" | The honest range is wide because the questions differ (emitted vs breathed, Delhi vs NCR, primary vs secondary, season). Cite the range, name the study, and the claim is bulletproof |

**Killed phrasing (do not ship):** "12M vehicles" (untrue in both directions),
"half the vehicles lack PUC", "your vehicle emits X g" as a point value (docs/26
already rules: class-average band only), "most Delhi vehicles are pre-BS-IV".

---

## 1. Fleet composition — what Delhi actually drives

### 1.1 Two different "how many vehicles" numbers — use the right one

| Figure | Value | Date | Source |
|---|---|---|---|
| **Cumulative registrations** (VAHAN books, ever registered minus never-cleaned historical entries) | **1,56,31,150** | FY 2024-25 | Dept of Economics & Statistics, GNCTD, via [PTI/ThePrint, 15 Jan 2026](https://theprint.in/india/delhi-sees-steady-growth-in-registered-vehicles-over-last-four-years/2828134/) |
| — earlier: 1,42,04,810 (FY23), 1,48,87,713 (FY24) | growth ≈ +7.4 lakh/yr | FY23/FY24 | same |
| **Active fleet** (vehicles legally allowed to ply: diesel <10y, petrol <15y, not deregistered) | **82.9 lakh** | Sept 2024 | Delhi transport dept, via [ET, 4 Sep 2024](https://economictimes.indiatimes.com/news/india/unveiling-the-shocking-truth-more-than-30-of-delhi-city-vehicles-lack-pollution-under-control-certificates-pucc/articleshow/113053429.cms) and [ETAuto](https://auto.economictimes.indiatimes.com/news/industry/a-third-of-active-vehicles-in-delhi-have-expired-pucc/113052774) |
| On-road estimate (independent) | ~79.45 lakh | Mar 2023 | DES/Statistical Abstract, per docs/23 inventory |

The gap between 1.56 crore and ~83 lakh *is the scrappage programme itself* —
see §2.2. **For anything user-facing, the active fleet (~83 lakh) is the honest
denominator.** Cumulative registrations count lakhs of vehicles that are legally
dead.

### 1.2 Class split (active fleet, FY 2024-25, DES via PTI)

| Class | Count | Share of ~83 lakh active |
|---|---|---|
| Two-wheelers (motorcycles/scooters) | **56.59 lakh** | **~68%** |
| Cars & jeeps | **20.88 lakh** | **~25%** |
| Autos + taxis + buses + goods + e-rickshaws + rest | ~5.5 lakh | ~7% |

Cross-checks: DES 2020 puts motorcycles at **66.33%** and cars/jeeps at **28.53%**
of registered fleet (1,13,91,551 total, 2018-19) — [TERI, Cost-effectiveness of
interventions for air pollution control in Delhi, 2021, citing DES](https://teriin.org/sites/default/files/2021-12/Cost-effectiveness-of%20-interventions-for-control-of%20-air-pollution-in-Delhi.pdf).
2011 travel-demand model: 2W 63%, cars 32% of 7.45M registered — [DIMTS Base Year
Travel Demand Model](https://www.toi.no/getfile.php/1348327-1530707770/Publikasjoner/DELHI_%20Base%20Year%20Travel%20Demand%20Model.pdf).
The two-thirds figure is stable across a decade of sources.

### 1.3 Commercial segments (the exposure-relevant fleet)

| Segment | Count | Source |
|---|---|---|
| Auto-rickshaws | **1.14 lakh registered**; CNG autos capped at 1 lakh by SC order (11 Nov 2011), 92,849 on VAHAN Apr-2022 | [Indian Express, Feb 2023](https://indianexpress.com/article/cities/delhi/how-much-are-bike-taxis-used-in-delhi-more-than-youd-think-8459198/); [The Hindu, Apr 2022](https://www.thehindu.com/news/cities/Delhi/hc-pulls-up-delhi-govt-over-regulation-of-auto-e-rickshaws/article65299463.ece) |
| Taxis (aggregators + kaali-peeli) | **1.12 lakh registered**; ~30–35k plying daily, up to 60–65k with NCR cabs | [Indian Express, Feb 2023](https://indianexpress.com/article/cities/delhi/how-much-are-bike-taxis-used-in-delhi-more-than-youd-think-8459198/) |
| E-rickshaws | **2,04,131 registered** (VAHAN, Jan 2026); transport dept estimates ~4 lakh total incl. unregistered; draft EV Policy 2.0 proposes a 2.5 lakh cap | [Business Standard, Jan 2026](https://www.business-standard.com/india-news/delhi-may-allow-one-month-window-to-register-unregistered-e-rickshaws-126011401163_1.html); [HT, May 2026](https://www.hindustantimes.com/cities/delhi-news/delhi-govt-to-limit-e-rickshaws-at-2-50-000-to-address-urban-congestion-101780027238991.html) |
| Aggregator-licensed vehicles (cabs + delivery 2W/3W/4W) | **>1 lakh vehicles** across 21 onboarded entities under the Motor Vehicle Aggregator & Delivery Service Provider Scheme 2023 — Smartshift >50k, ANI/Ola >36k, Zomato >22k, Blinkit >10k | [ET, 13 Jul 2024](https://economictimes.indiatimes.com/tech/technology/ola-uber-zomato-among-21-entities-registered-under-delhis-motor-vehicle-aggregator-scheme/articleshow/111718833.cms) |
| Buses | DTC 3,819 (FY25) + DIMTS cluster 3,147 | [PTI/ThePrint, Jan 2026](https://theprint.in/india/delhi-sees-steady-growth-in-registered-vehicles-over-last-four-years/2828134/) |
| Electric vehicles | **3,17,515 registered** (exempt from PUC) | [ETAuto, Sept 2024](https://auto.economictimes.indiatimes.com/news/industry/a-third-of-active-vehicles-in-delhi-have-expired-pucc/113052774); EV share of new sales: 11.2% in CY2023 (73,610 of 6,57,312; Dec-2023 monthly share 19.5%), then collapsed to ~220/mo by Nov-2024 after incentive lapse — [FE/Gahlot](https://preprod.financialexpress.com/business/express-mobility-delhi-saw-evs-make-up-for-20-of-new-vehicle-sales-in-december-highest-amongst-any-state-in-india-says-kailash-gahlot-3354511/), [Business Standard, Dec 2024](https://www.business-standard.com/industry/news/delhi-ev-policy-woes-registrations-drop-in-capital-while-other-states-grow-124121600945_1.html) |

### 1.4 Fuel mix — what's actually in the lanes

- **Measured on-road fleet (TRUE/ICCT remote sensing, Dec 2022–Apr 2023, 20
  sites): petrol 45%, CNG 32%, diesel 23%** — of 111,712 valid measurements
  (75.4% private cars, 14.4% taxis, ~6% 2W+3W, 2.5% LGV, 1.3% buses; >50%
  Delhi-registered). 2Ws all petrol; 3Ws, LGVs and buses captured all CNG;
  taxis predominantly CNG. [TRUE Delhi report, Nov 2024](https://trueinitiative.org/wp-content/uploads/2024/11/true-delhi-rs-report.pdf);
  [ICCT fact sheet](https://theicct.org/wp-content/uploads/2024/08/ID-200-%E2%80%93-Delhi-RS-TRUE-Fact-Sheet-A4-65003-v5.pdf)
- **Diesel's fall is real and post-2015:** diesel was **40–45% of Delhi
  passenger-car sales before Dec 2015** (Maruti: ~35% of Delhi sales FY15),
  dropped to ~30–35% within weeks of the NGT/SC orders, and kept falling —
  plus >10y diesels are now legally off the road entirely. [Business Standard,
  30 Dec 2015](https://www.business-standard.com/article/companies/delhi-diesel-car-market-on-a-decline-post-ngt-order-115123000709_1.html);
  [FE, Dec 2015](https://preprod.financialexpress.com/policy/economy-after-odd-even-formula-by-delhi-govt-ngt-says-no-to-new-diesel-vehicles-177711/)

**Dashboard phrasing that survives:** "Delhi's road fleet: ~2/3 two-wheelers,
~1/4 cars — and nearly a third of everything measured runs on CNG, the highest
CNG share TRUE has measured anywhere."

---

## 2. Age & Bharat-Stage mix — what vintage is actually out there

### 2.1 Measured on-road BS distribution (best available: remote sensing, not models)

| Vintage | Share of measured fleet | Source |
|---|---|---|
| **BS-IV + BS-VI** | **~89%** (BS-IV the single largest block) | [TRUE/ICCT Delhi remote sensing, Nov 2024](https://trueinitiative.org/wp-content/uploads/2024/11/true-delhi-rs-report.pdf) — 111,712 measurements, Dec 2022–Apr 2023 |
| **Pre-BS-IV (BS-I/II/III)** | **~11%** | same |

Why BS-IV dominates the measured mix: Delhi adopted BS-IV in 2010 (7 years
before national), BS-VI in 2020, and the >10y-diesel/>15y-petrol bans have
been removing the oldest blocks since Jan 2022. ADB's fleet model baseline
for 2020 shows the same direction (2W: BS-III 13.85% → BS-IV 46.88% → BS-VI
growing; [ADBI WP1297](https://www.adb.org/sites/default/files/publication/762211/adbi-wp1297.pdf)).

**Honest nuance the judges will respect:** the ~11% pre-BS-IV tail is
disproportionately dirty — remote-sensing shows emissions fall sharply per
vintage step, and per docs/26 the super-emitter tail (Jaiprakash–Habib: ~14% of
vehicles → 17–57% of emissions) does the damage. Delhi's fleet is *newer than
its reputation*; its emissions problem is a *distribution*, not a *count*.

### 2.2 Scrappage — the world's largest deregistration drive, on paper and on the ground

| Milestone | Number | Source |
|---|---|---|
| Overage vehicles deregistered by Mar-2023 | **53,78,514** (incl ~80,000 govt vehicles) | [Indian Express, 30 Mar 2023](https://indianexpress.com/article/cities/delhi/delhi-govt-launches-drive-to-send-overage-vehicles-directly-for-scrapping-8527728/) |
| — same series | >54 lakh by 27 Mar 2023 | [The Hindu, Apr 2023](https://www.thehindu.com/news/cities/Delhi/delhi-govt-deregisters-more-than-54-lakh-overage-vehicles-data/article66775321.ece) |
| — cumulative | **66.2 lakh by 19 Mar 2026** | Economic Survey 2025-26 via [TOI, Mar 2026](https://waps.l3s.uni-hannover.de/live/https:/timesofindia.indiatimes.com/city/delhi/delhi-deregisters-66-lakh-overaged-vehicles-yet-vehicle-numbers-surge/articleshow/129760315.cms) |
| Actually scrapped (RVSF), cumulative | 18.08 lakh by FY25 (vs 4,923 in FY22) | DES via [PTI/ThePrint, Jan 2026](https://theprint.in/india/delhi-sees-steady-growth-in-registered-vehicles-over-last-four-years/2828134/) |

*Reading it honestly:* deregistration outruns physical scrapping ~3.7:1 — most
deregistered vehicles migrate on NOC to other states, which is why "Delhi
banned 66 lakh vehicles" is true while "66 lakh vehicles were scrapped" is not.
Legal basis: NGT order (upheld SC Oct-2018), enforced from 1 Jan 2022; the
docs/26 legal floor stands — the dirtiest vintages are already off Delhi
plates.

### 2.3 PUC — the compliance gap

- **26.2 lakh of 82.9 lakh active vehicles (31.6%) were on an expired PUC** in
  Sept 2024; ₹10,000 fine; 30 motorcycle squads deployed at petrol pumps.
  [ET](https://economictimes.indiatimes.com/news/india/unveiling-the-shocking-truth-more-than-30-of-delhi-city-vehicles-lack-pollution-under-control-certificates-pucc/articleshow/113053429.cms) / [ETAuto](https://auto.economictimes.indiatimes.com/news/industry/a-third-of-active-vehicles-in-delhi-have-expired-pucc/113052774), 4 Sep 2024.
- For calibration of "does PUC even work": national PUC test *fail* rates are
  0.55–2.7% of tested vehicles/yr (Lok Sabha annex, 2021–2026) — the test
  filters almost nothing; the bigger problem is the third of the fleet that
  never shows up.

---

## 3. The "invisible dose" — gig & occupational riders

### 3.1 Fleet size — the defensible stack

| Layer | Number | Source |
|---|---|---|
| Registered under Delhi's Aggregator Scheme (cabs + delivery + e-comm, 21 entities) | **>1,00,000 vehicles** (Smartshift >50k, Ola/ANI >36k, Zomato >22k, Blinkit >10k) | [ET, Jul 2024](https://economictimes.indiatimes.com/tech/technology/ola-uber-zomato-among-21-entities-registered-under-delhis-motor-vehicle-aggregator-scheme/articleshow/111718833.cms) |
| + Registered taxis & autos (the non-app overlap) | 1.12 lakh + 1.14 lakh | [Indian Express, Feb 2023](https://indianexpress.com/article/cities/delhi/how-much-are-bike-taxis-used-in-delhi-more-than-youd-think-8459198/) |
| + E-rickshaws | ~2 lakh registered, ~4 lakh estimated on ground | [BS](https://www.business-standard.com/india-news/delhi-may-allow-one-month-window-to-register-unregistered-e-rickshaws-126011401163_1.html)/[HT](https://www.hindustantimes.com/cities/delhi-news/delhi-govt-to-limit-e-rickshaws-at-2-50-000-to-address-urban-congestion-101780027238991.html), 2026 |
| National context | Zomato 4.0→5.32 lakh monthly delivery partners, Swiggy 3.9→6.91 lakh (FY24→H1FY26); NITI Aayog: 77 lakh gig workers (2020-21) → 2.35 crore projected (2029-30) | [Hindu BusinessLine, Jan 2026](https://www.thehindubusinessline.com/data-stories/data-focus/delivery-partner-numbers-increase-but-payout-growth-stays-uneven-across-platforms/article70500886.ece); [NITI Aayog policy brief, Jun 2022](https://www.niti.gov.in/sites/default/files/2023-06/Policy_Brief_India%27s_Booming_Gig_and_Platform_Economy_27062022.pdf) |

**"10M" verdict:** as a *fleet* claim, 10M is wrong — the occupationally-exposed
fleet is **~3–5 lakh humans** (1 lakh+ licensed aggregator vehicles + surviving
taxi/auto/e-rick drivers), and as a *trips* claim the honest line is **"several
million unfiltered trips a day"**: 15.1M motorized daily trips (2007 base,
→17.4M projected 2021; [DIMTS Rapid Demand Estimation](https://www.toi.no/getfile.php/1348336-1530707950/Publikasjoner/DELHI_%20Revised%20Rapid_Demand_Estimation.pdf))
of which 2W alone was 25.5% and public-transport 2W/auto legs aren't filtered
either. Ship **"lakh of drivers dose all day; millions of riders dose twice a
day"** — both halves sourced — and drop the literal 10M.

### 3.2 What the exposure studies actually measured

- **Delivery riders (Ghaziabad, NCR — closest to our user):** PM and VOC
  (incl. carcinogenic benzene) far above CPCB/WHO limits; 67% of surveyed
  riders unaware of any risk. Sekar et al., *Atmospheric Pollution Research*
  2023 — [Mongabay summary, Aug 2023](https://india.mongabay.com/2023/08/gig-workers-in-india-are-exposed-to-highly-polluted-air-and-carcinogens-finds-preliminary-study/)
- **Auto-rickshaw cabin (Delhi):** in-vehicle PM2.5 geometric mean **190
  µg/m³**, BC 42 µg/m³, PN 280k/cm³ — 1.5×/3.6×/8.4× ambient; a Delhi rickshaw
  commute ≈ full-day exposure in high-income countries. [Apte et al.,
  *Atmospheric Environment* 2011](https://www.sciencedirect.com/science/article/abs/pii/S1352231011005206)
- **Mode multipliers (Delhi):** PM2.5 inhaled per km — **walking 28.2× and
  rickshaw 5.3× the metro** (already our dose-model anchor). [Maji et al.,
  *Atmospheric Pollution Research* 2021](https://www.sciencedirect.com/science/article/abs/pii/S1309104220303457)
- **Occupational lung function:** auto/cab drivers show elevated symptom and
  illness burden vs indoor workers ([Jain & Barthwal, ESPR 2021](https://exa.ai/library/publication/l0v2dyw8pqf));
  outdoor workers (drivers, vendors, police): **62.7% restrictive lung pattern**
  vs indoor controls ([Barthwal et al., ESPR 2022](https://link.springer.com/content/pdf/10.1007/s11356-022-18886-9.pdf));
  traffic policemen: significantly lower FVC/FEV1/PEFR vs controls
  ([Int. J. Physiology, 2017](https://indianjournals.com/article/ijp2-5-1-025)).
- **Hours:** riders interviewed in NCR report 8–10 h/day on the road
  ([PUDR gig report](https://www.pudr.org/publicatiosn-files/PUDR-report-on-gig-workers-Behind-the-Veil-of-Algorithms.pdf);
  [Mongabay](https://india.mongabay.com/2023/08/gig-workers-in-india-are-exposed-to-highly-polluted-air-and-carcinogens-finds-preliminary-study/))
  — so at rickshaw-class concentrations (~113 µg/m³ run-average, Maji) an 8-h
  shift is an occupational exposure nobody counts.

---

## 4. Where vehicles rank among Delhi's PM2.5 sources — the honest range

Every serious study agrees transport is #1 or #2; they disagree on the share
because they answer different questions. **Cite with the question attached.**

| Study | Question asked | Transport share of PM2.5 | Source |
|---|---|---|---|
| **SAFAR/IITM 2018** emission inventory (70×65 km, Delhi-NCR) | What fraction of *emitted* PM2.5 is transport? | **39.2%** (42.23 of 107.79 Gg/yr) — largest sector; industry 22%, windblown dust 18% | [SAFAR 2018 inventory](https://questionofcities.org/wp-content/uploads/2022/11/SAFAR-High-Resolution-Emission-Inventory-of-Mega-City-Delhi-2018.pdf); corroborated by [CEEW review](https://www.ceew.in/publications/delhi-air-pollution-sources-and-causes) |
| **TERI-ARAI 2018** (Delhi's own emissions) | Same, Delhi-only | **39%** of Delhi's own PM2.5 emissions | [TERI-ARAI report](https://teriin.org/sites/default/files/2018-08/Report_SA_AQM-Delhi-NCR_0.pdf) |
| **TERI-ARAI 2018** ambient concentration | What fraction of *breathed* PM2.5 is transport (incl. secondary)? | **28% winter / 17% summer**; within winter transport: trucks 8, 2W 7, 3W 5, cars 3.4 | same |
| **IIT-Kanpur 2015** (DPCC) | Emissions inventory | **~20%** (road dust 38% largest); ambient winter ~28% incl. secondaries | [IITK report](https://cerca.iitd.ac.in/uploads/Reports/1576211826iitk.pdf) (via docs/23) |
| **Guttikunda 2018** | Emissions inventory | **17.9%** (industry-led) | [CEEW review](https://www.ceew.in/publications/delhi-air-pollution-sources-and-causes) |
| **IITM DSS** daily attribution (recent seasons) | What's driving *today's* Delhi PM2.5? | **~11–12%** typical; dwarfed on peak-fire days (stubble hit 35.1% on 1 Nov 2024) | DSS daily bulletins via HT/India Today (docs/25) |

*Why the range is the answer:* inventories count what's emitted (~18–39%);
receptor/dispersion models count what's breathed (~17–28% transport, diluted by
regional inflow — Delhi's own emissions are only ~36% of its winter PM2.5);
daily attribution tracks episodes (single digits to ~40% swings). For the app:
**"transport is the largest or second-largest controllable source of Delhi's
PM2.5 — roughly a fifth to two-fifths by emissions accounting, ~11–12% on an
average winter day, and the one source you can personally dodge by 30×."**

---

## 5. Disclaimer language — "your vehicle emits X" that survives

Adopt verbatim from docs/26 (the legal frame is already settled there); this is
the user-facing copy:

> **"We can't measure your tailpipe. No app can. What we can tell you is what a
> vehicle of your class emits on Delhi fleet average — the published government
> method (ARAI/TERI emission-factor tables), shown as a range, because the
> range is the honest answer."**

Rules that keep it true:
- **Always a band, never a point.** "A petrol car-km ≈ 0.02–0.28 g PM2.5
  (fleet average, ±SD published)" — the SD exceeding the mean is the *source's*
  finding, not our hedge (Guttikunda Table 5).
- **Class-declared, not identity-claimed.** The user picks car/2W/auto/BS-class;
  we apply the class-average EF. If they don't declare, use the fleet mix in
  §1 and label it "Delhi average vehicle".
- **Lead with CO2e where tightness matters** (±30%, chemistry identity), then
  dose-avoided (our provable number); tailpipe-PM is context, not headline.
- **Anchor in breath, not emission.** "Your share of what Delhi breathes" is
  weaker than "what you breathe is 5–28× mode-dependent" — the multiplier is
  measured, the attribution is not.

---

## 6. Source list

1. Dept of Economics & Statistics (GNCTD) vehicle data via PTI — [ThePrint, 15 Jan 2026](https://theprint.in/india/delhi-sees-steady-growth-in-registered-vehicles-over-last-four-years/2828134/)
2. PUCC compliance — [ET](https://economictimes.indiatimes.com/news/india/unveiling-the-shocking-truth-more-than-30-of-delhi-city-vehicles-lack-pollution-under-control-certificates-pucc/articleshow/113053429.cms), [ETAuto](https://auto.economictimes.indiatimes.com/news/industry/a-third-of-active-vehicles-in-delhi-have-expired-pucc/113052774), 4 Sep 2024
3. PUC test outcomes — [Lok Sabha Q annex (NIC data)](https://sansad.in/getFile/lsapps/loksabhaquestions/annex/188/AU794_fztwdY.pdf)
4. TRUE/ICCT remote sensing Delhi — [full report](https://trueinitiative.org/wp-content/uploads/2024/11/true-delhi-rs-report.pdf), [ICCT fact sheet](https://theicct.org/wp-content/uploads/2024/08/ID-200-%E2%80%93-Delhi-RS-TRUE-Fact-Sheet-A4-65003-v5.pdf) (Dec 2022–Apr 2023 campaign)
5. TERI cost-effectiveness study (DES 2020 fleet split) — [TERI, 2021](https://teriin.org/sites/default/files/2021-12/Cost-effectiveness-of%20-interventions-for-control-of%20-air-pollution-in-Delhi.pdf)
6. Auto/taxi counts & SC 1-lakh cap — [Indian Express, Feb 2023](https://indianexpress.com/article/cities/delhi/how-much-are-bike-taxis-used-in-delhi-more-than-youd-think-8459198/); [The Hindu, Apr 2022](https://www.thehindu.com/news/cities/Delhi/hc-pulls-up-delhi-govt-over-regulation-of-auto-e-rickshaws/article65299463.ece)
7. E-rickshaw counts/cap — [Business Standard, Jan 2026](https://www.business-standard.com/india-news/delhi-may-allow-one-month-window-to-register-unregistered-e-rickshaws-126011401163_1.html); [HT, May 2026](https://www.hindustantimes.com/cities/delhi-news/delhi-govt-to-limit-e-rickshaws-at-2-50-000-to-address-urban-congestion-101780027238991.html)
8. Deregistration drive — [Indian Express, Mar 2023](https://indianexpress.com/article/cities/delhi/delhi-govt-launches-drive-to-send-overage-vehicles-directly-for-scrapping-8527728/); [The Hindu, Apr 2023](https://www.thehindu.com/news/cities/Delhi/delhi-govt-deregisters-more-than-54-lakh-overage-vehicles-data/article66775321.ece); [TOI, Mar 2026](https://waps.l3s.uni-hannover.de/live/https:/timesofindia.indiatimes.com/city/delhi/delhi-deregisters-66-lakh-overaged-vehicles-yet-vehicle-numbers-surge/articleshow/129760315.cms)
9. Aggregator scheme fleet counts — [ET, Jul 2024](https://economictimes.indiatimes.com/tech/technology/ola-uber-zomato-among-21-entities-registered-under-delhis-motor-vehicle-aggregator-scheme/articleshow/111718833.cms)
10. National gig fleet — [Hindu BusinessLine, Jan 2026](https://www.thehindubusinessline.com/data-stories/data-focus/delivery-partner-numbers-increase-but-payout-growth-stays-uneven-across-platforms/article70500886.ece); [NITI Aayog, Jun 2022](https://www.niti.gov.in/sites/default/files/2023-06/Policy_Brief_India%27s_Booming_Gig_and_Platform_Economy_27062022.pdf)
11. Gig/rider exposure — [Mongabay, Aug 2023](https://india.mongabay.com/2023/08/gig-workers-in-india-are-exposed-to-highly-polluted-air-and-carcinogens-finds-preliminary-study/) (Sekar et al., APR 2023); [Rest of World, Feb 2024](https://restofworld.org/2024/riders-in-the-smog-gig-workers-pollution/); [PUDR report](https://www.pudr.org/publicatiosn-files/PUDR-report-on-gig-workers-Behind-the-Veil-of-Algorithms.pdf)
12. Exposure microenvironments — [Apte et al. 2011](https://www.sciencedirect.com/science/article/abs/pii/S1352231011005206); [Maji et al. 2021](https://www.sciencedirect.com/science/article/abs/pii/S1309104220303457)
13. Occupational lung studies — [Jain & Barthwal 2021](https://exa.ai/library/publication/l0v2dyw8pqf); [Barthwal et al. 2022](https://link.springer.com/content/pdf/10.1007/s11356-022-18886-9.pdf); [traffic policemen 2017](https://indianjournals.com/article/ijp2-5-1-025)
14. Source apportionment — [TERI-ARAI 2018](https://teriin.org/sites/default/files/2018-08/Report_SA_AQM-Delhi-NCR_0.pdf) + [press release](https://teriin.org/press-release/strong-policies-needed-clean-delhi-ncr-air-2025-arai-teri-report); [SAFAR-IITM 2018](https://questionofcities.org/wp-content/uploads/2022/11/SAFAR-High-Resolution-Emission-Inventory-of-Mega-City-Delhi-2018.pdf); [CEEW comparison](https://www.ceew.in/publications/delhi-air-pollution-sources-and-causes); IITK 2015 (docs/23)
15. Travel demand — [DIMTS Base Year Travel Demand Model](https://www.toi.no/getfile.php/1348327-1530707770/Publikasjoner/DELHI_%20Base%20Year%20Travel%20Demand%20Model.pdf); [Rapid Demand Estimation](https://www.toi.no/getfile.php/1348336-1530707950/Publikasjoner/DELHI_%20Revised%20Rapid_Demand_Estimation.pdf)
16. Fleet evolution model — [ADBI WP1297](https://www.adb.org/sites/default/files/publication/762211/adbi-wp1297.pdf)
17. Diesel decline — [Business Standard, Dec 2015](https://www.business-standard.com/article/companies/delhi-diesel-car-market-on-a-decline-post-ngt-order-115123000709_1.html); [FE, Dec 2015](https://preprod.financialexpress.com/policy/economy-after-odd-even-formula-by-delhi-govt-ngt-says-no-to-new-diesel-vehicles-177711/)
18. EV registrations/share — [FE/Gahlot, Jan 2024](https://preprod.financialexpress.com/business/express-mobility-delhi-saw-evs-make-up-for-20-of-new-vehicle-sales-in-december-highest-amongst-any-state-in-india-says-kailash-gahlot-3354511/); [Business Standard, Dec 2024](https://www.business-standard.com/industry/news/delhi-ev-policy-woes-registrations-drop-in-capital-while-other-states-grow-124121600945_1.html)
