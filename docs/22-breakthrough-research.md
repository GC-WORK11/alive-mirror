# Alive — Breakthrough Research
*Deep-research deliverable for the exposure-aware Delhi router. Every load-bearing claim carries a source. Where a "never shipped" claim is made, the negative evidence is stated explicitly.*

---

## (a) Competitive map — who did what, who died, why

### The dead and the absorbed

| Product | What it was | What happened | Lesson |
|---|---|---|---|
| **BreezoMeter** (2014–2023) | Israeli AQ-data company; street-level AQ API, consumer app; launched **Cleanest Route** API Sep 2022 — routes scored 0–100 "Route Air Cleanliness Score" for brands to embed | Acquired by Google Sep 2022 for ~$200–250M; team absorbed into Google Haifa; **consumer app killed Sep 13, 2023**; tech folded into Google Maps Platform **Air Quality API** | The market validated AQ-aware routing enough for Google to pay a quarter-billion for it — then killed the consumer surface and made it a paid API. The consumer-facing clean-route slot is **empty**. Sources: [CTech](https://www.calcalistech.com/ctechnews/article/sycbrdpbi), [Globes](https://en.globes.co.il/en/article-google-launches-applications-based-on-breezometer-acquisition-1001456420), [BusinessWire Cleanest Route](https://www.businesswire.com/news/home/20220908005291/en/), [BreezoMeter shutdown post](https://www.linkedin.com/posts/breezometer_going-beyond-the-map-introducing-environment-activity-7107331789844549633-exkM) |
| **Plume Labs Flow / Flow 2** | Handheld personal PM sensor + app; "what is in the air I breathe" | Acquired by AccuWeather Jan 2022; **consumer sales ended spring 2023**; pivoted to B2B data | Personal exposure **hardware** died: €200-class devices never reached mainstream. Hardware-free dose estimation (what Alive does) is the survivor's path. Sources: [Plume Labs](https://plumelabs.com/en/flow/), [Preqin profile](https://www.preqin.com/data/profile/asset/plume-labs/176727), [AccuWeather FAQ](https://plumelabs.zendesk.com/hc/en-us/articles/4416148461842-FAQ-on-Plume-Labs-joining-AccuWeather) |
| **Hawa Badlo** (2016) | EPCA/Supreme-Court-ordered Delhi app: photo complaints of burning/dust to authorities | Launched with fanfare; no measurable adoption trace remains; effectively dead loop — complaints into a black hole | Pure "report pollution" apps without personal utility die. Delhi precedent. Source: [AP News](https://apnews.com/general-news-4a9cd761c50d4b5481a127863023389b) |
| **Sameer** (CPCB official) | National AQI app + photo complaints to pollution boards | Alive but utility-stagnant; complaint status rarely visible; AQI-only | Even the government's own app never made data actionable at the route/dose level. Source: [Play Store](https://play.google.com/store/apps/details?id=com.cpcb&hl=en), [data.gov.in](https://www.data.gov.in/catalog/sameer-national-air-quality-index) |

### Alive — feature-level competitors

| Product | AQ capability | Gap vs dose-aware routing |
|---|---|---|
| **Google Maps AQ layer** | AQI tile layer since 2022 (BreezoMeter/PurpleAir/gov stations); AQ API for devs (100+ countries, traffic-informed ML) | **Layer, not routing.** No route scoring, no dose, no turn-by-turn AQ. Sources: [Google blog](https://blog.google/products-and-platforms/products/search/get-some-fresh-air-outdoors-with-google/), [Maps Platform](https://blog.google/products-and-platforms/products/maps/google-maps-apis-environment-sustainability/) |
| **Apple Maps** | AQI label on map since iOS 12.2 (2019); health recommendations via BreezoMeter since iOS 14.3 | Label only. No routing use. Source: [GadgetHacks](https://ios.gadgethacks.com/how-to/view-air-quality-apple-maps-see-polluted-cities-destinations-are-0193020/), [MyHealthyApple](https://www.myhealthyapple.com/apple-improves-air-quality-health-recommendations-on-your-iphone-in-ios-14-3/) |
| **IQAir AirVisual** | Largest AQ app: ~350K MAU, 80K+ community sensors, UNEP partnership, forecasts | Data browser, not a router. Community = fixed sensors you must buy. Sources: [AppGoblin](https://appgoblin.info/apps/1048912974), [IQAir](https://www.iqair.com/air-quality-community/become-a-contributor-today) |
| **PurpleAir** | Crowdsourced sensor map; data feeds EPA Fire & Smoke Map | Sensor owners only; a map, not navigation. But see §d — its data got adopted into a *federal product*. Source: [PurpleAir](https://www.purpleair.com/real-time-map) |
| **Ambee Clean Routing** | B2B API: routes ranked by 6 pollutants + 30 pollen allergens | B2B2C only (Allegra Airways pharma campaign: 325K routes, $3M sales, Cannes Lion 2024). No consumer app. Source: [Ambee](https://www.getambee.com/products/clean-routing) |
| **CleanRoute** (iOS, new) | Turn-by-turn with CleanScore pollution-gradient, fastest-vs-cleaner compare, Smart Leave departure alerts | **Closest shipped competitor.** But: driving-only, no inhaled-dose model (no ventilation × microenv), no citizen sensing, US-centric. Confirms TBT+AQ is sellable; confirms nobody does dose. Source: [App Store](https://apps.apple.com/us/app/cleanroute-navigation/id6760449094) |
| **Meersens** | "Exposome" app: real-time + predictive env exposure, alerts/whistleblower community, B2B (employers/municipalities) | Exposure assistant, not navigation; gated behind employer/municipality invite. Source: [Meersens](https://meersens.com/meersens/) |
| **AirBeam/AirCasting** | Open-source palm PM sensor + largest open community-collected AQ database | Hardware required (~€85). Still the best-funded citizen-sensing survivor — its lesson: community survived on *openness + owning your data*. Source: [HabitatMap](https://www.habitatmap.org/aircasting) |
| **KT Air Map Korea** | Telecom-built 2,000-station fine-dust network + app + alleyway micro-maps | National platform, Korea-only; density-of-stations strategy India can't copy, but its *alley-level* promise is what citizens actually wanted. Source: [App Store listing](https://apps.apple.com/mw/app/airmap-%EB%AF%B8%EC%84%B8%EB%A8%BC%EC%A7%80-%EA%B3%B5%EA%B8%B0%EC%A7%88/id6747370465) |
| **IsCleanAir** | Italian benefit corp: water-based filterless APA abatement hardware, EU H2020 €1.28M | Purification hardware, not a navigation/data play. Source: [CORDIS](https://cordis.europa.eu/project/id/806756) |

### Research systems (the academic frontier)

| System | Org | Contribution | Status |
|---|---|---|---|
| **U-Air** | Microsoft Research Asia (Yu Zheng), KDD'13 | First big-data fine-grained AQ inference: co-training ANN (spatial) + linear-chain CRF (temporal) over stations + traffic + POI + meteorology | Landmark paper; never a product. Source: [MSR](https://www.microsoft.com/en-us/research/publication/u-air-when-urban-air-quality-inference-meets-big-data/) |
| **OpenSense** | ETH Zürich / Nano-Tera | Mobile sensors on **trams** for 3+ yrs; first multi-hop mobile-sensor calibration; thesis includes a *route-planning service to reduce exposure* | Research only; the thesis literally prototyped exposure-aware routing in 2015 — it was never consumerized. Source: [ETH](https://tec.ee.ethz.ch/research/networked-embedded-systems/opensense.html), [Hasenfratz thesis](https://pub.tik.ee.ethz.ch/people/thiele/paper/diss_hasenfratz.pdf) |
| **CAR algorithm** | NTNU Taiwan | PM2.5-weighted graph routing on OSM; **avg −17.1% exposure for +2.4% distance** over 4,000 trips | Code public; never productized. Source: [paper](https://exa.ai/library/publication/4phy3zcflbp), [GitHub](https://github.com/sachit27/CAR-Clean-Air-Routing-Algorithm) |
| **DRUM** | IIT-Kharagpur, 2025 | Delhi-specific web planner (React+Go+GraphHopper): shortest/fastest/**LEAP**/LECR; **LEAP cut exposure up to −53% in Central Delhi at +42% time** | **Most dangerous precedent**: same city, same claim, but simulation-only, WAQI-sourced, no dose model, no mode factors, no app, no citizen loop. Alive must position itself as the shipped, dose-accurate version of this idea. Sources: [The Hindu](https://www.thehindu.com/sci-tech/energy-and-environment/iit-kgp-app-helps-commuters-pick-greener-routes-on-the-road/article69644558.ece), [TRB paper](https://sage.cnpereading.com/doi/10.1177/03611981251331011) |
| **Clean Air Route Finder** | Cross River Partnership + Imperial College London | Route alternatives with *modelled dose* (conc × distance × ventilation) for walk/cycle; 20+ pre-mapped Clean Air Routes measured **30–60% lower** pollutants | Live London tool; single-mode-family, city-locked. Source: [CRP](https://crossriverpartnership.org/projects/clean-air-route-finder/) |
| Prototypes | Thessaloniki (OSRM+EAQI): −4% avg exposure / +3% distance; Leicester (OSMnx+Dijkstra): median −6% NO₂, max −48–60%; Barcelona (AAMAS'25): −7.8% NO₂ / +4.5% length; Lancaster: first *network dose* (µg inhaled, slope-aware ventilation) model | All single-city academic proofs; none shipped consumer TBT | Sources: [Thessaloniki](https://www.mdpi.com/2624-6511/9/2/24), [Leicester](https://www.frontiersin.org/journals/sustainable-cities/articles/10.3389/frsc.2026.1869860/full), [Barcelona](https://www.ifaamas.org/Proceedings/aamas2025/pdfs/p3015.pdf), [Lancaster](https://www.sciencedirect.com/science/article/abs/pii/S0048969714003684) |

**What has never shipped** (the honest answer to the prompt):
1. **Inhaled-dose turn-by-turn** — every shipped/attempted router weights *concentration* (µg/m³ or AQI). Nobody at consumer scale computes µg *inhaled* per maneuver (concentration × mode-specific ventilation × microenv factor × duration). Cleanest Route, CleanRoute, DRUM, CAR — all concentration-weighted.
2. **Hardware-free citizen traversal sensing** — every citizen-sensing predecessor required hardware (Flow, AirBeam, SensorBox, diffusion tubes) or manual reports (Hawa Badlo, Sameer). Nobody runs a Waze-style *passive* loop where taking a route IS the sensor sample.
3. **Mode-specific microenvironment correction at consumer scale** — Delhi's own measured literature (walk inhales 28.2× metro per km; rickshaw 5.3×) has never been wired into a consumer router. Source: [ScienceDirect](https://www.sciencedirect.com/science/article/abs/pii/S1309104220303457)
4. **Dose uncertainty bands** — no consumer product reports "you'll inhale 38–61 µg" instead of a false-precision point.

---

## (b) The 3 candidate breakthroughs — ranked by defensibility × feasibility (pre-Oct 10)

### #1 — "Your lungs, live": dose-aware turn-by-turn with a running inhaled-µg meter
- **What**: During active navigation, a live counter accumulates estimated µg inhaled — per-maneuver dose attribution, arrival "dose receipt" (this trip: 214 µg ≈ 0.68 cig), and post-trip comparison vs the rejected alternatives ("the fastest route would have cost you 61 µg more").
- **Defensibility**: Highest. BreezoMeter's Cleanest Route died as a B2B API; CleanRoute scores concentration; DRUM is a simulation paper. **Nobody has shipped an inhaled-dose TBT counter.** The demo also reads perfectly in a 3-min video: "watch the number tick while Devin drives past a burning pile."
- **Feasibility**: ~80% already exists (nav mode + "breathing N µg/m³" readout + dose model). The delta is: per-step dose accumulation, the receipt screen, the delta-vs-alternative math. **1–2 days.**
- **Risk**: It's a UX claim more than a science claim — pair with #3 to make the number defensible.

### #2 — "Waze for lungs": passive, hardware-free traversal sensing that measurably updates the field
- **What**: Every completed route passively donates its traversal (already built: `/observe` → community corridors). The breakthrough step nobody has shipped: **fold traversals back into the field** — corridors with recent traversals gain confidence, stale corridors decay, and the app shows "measured by 47 commutes this week." Users become coverage sensors *without hardware* — what Flow, AirBeam and EveryAware all failed to do without devices.
- **Defensibility**: Strong. All citizen-AQ precedents required hardware or manual effort; the literature (below) shows both died on that friction. A passive, utility-coupled loop is the documented missing design.
- **Feasibility**: `/observe`, corridor cells, and CorridorLayer exist. Delta: server-side per-cell traversal-weighted confidence that feeds `/aqi`/`/route` edge confidence, plus a per-corridor "freshness" decay. **2–3 days.** This is also the *only* mechanism that makes the product better the more Delhi uses it — the judges' favorite sentence: *"every trip makes the next trip healthier."*
- **Risk**: Cold-start (seed corridors manually with our own test traversals — already true today).

### #3 — Physics-grade honesty: wind-advected field + uncertainty bands on every dose
- **What**: Upgrade IDW→kriging (or kriging/IDW ensemble), advect the field by real wind (replace `UPWIND_GAIN` heuristic with semi-Lagrangian advection), and publish dose as a **band** ("42–68 µg") instead of a point. Microenv factors get a physics citation trail (vehicle REC/filter literature below).
- **Defensibility**: High for a hackathon — no consumer AQ product shows uncertainty, and every academic reviewer respects kriging variance propagated to dose. It converts our weakest attack surface ("how accurate is the number?") into the feature.
- **Feasibility**: 105 stations → ordinary kriging is ~milliseconds on the Fargate task (`pykrige` or a 105×103 covariance solve). Field advection over the existing 48-pt grid is O(grid). **1–2 days.**
- **Risk**: Band width will be wide in sparse areas — that's the point, and it's honest.

**Ranking rationale**: #1 demos best, #2 is the actual "nobody has shipped this" story and compounds, #3 is the cheapest scientific moat. Ship all three; lead the narrative with #2.

---

## (c) Math upgrade shortlist — computational requirements (target: 1 small Fargate task)

| Upgrade | Method | Compute cost | Literature anchor | Verdict |
|---|---|---|---|---|
| **Station-side Kalman filtering** | Scalar/linear KF per station to smooth + short-horizon-forecast readings before they enter the field | Trivial — O(#stations) per hour, microseconds | KF on low-cost sensors: +27% accuracy, **−68% RMSE** vs moving-average/ARIMA baselines — runs on a Raspberry Pi. [MDPI Applied Sciences](https://www.mdpi.com/2076-3417/9/9/1831) | **SHIP — free accuracy** |
| **Kriging over IDW** | Ordinary/universal kriging on ~105 stations; outputs variance surface | 105×105 covariance solve ≈ ms; done once/hour | Kriging beats IDW on RMSE/ME in Tehran PM2.5 and PM10 zoning comparisons; but "computationally demanding" only matters at n≫10³ — we're far under it. [Tehran](https://japh.tums.ac.ir/index.php/japh/article/view/244), [Yazd](https://jehsd.ssu.ac.ir/article-1-90-en.html), [env-science review](https://pmc.ncbi.nlm.nih.gov/articles/PMC10709237/) | **SHIP — unlocks #3's uncertainty bands** |
| **Semi-Lagrangian field advection** | Shift prior-hour field by wind×Δt + diffusion blur before blending fresh stations | O(48-pt grid) — trivial | Physics precedent: our `UPWIND_GAIN` heuristic is a degenerate version; real advection-diffusion is the standard. Full ADMS-Urban models need task-farms (weeks→35h on clusters) — we stay cheap. [ADMS-Urban](https://mdpi-res.com/d_attachment/atmosphere/atmosphere-12-00983/article_deploy/atmosphere-12-00983-v2.pdf), [fast canopy model ~50× LES](https://mdpi-res.com/d_attachment/atmosphere/atmosphere-14-01337/article_deploy/atmosphere-14-01337-v2.pdf) | **SHIP — cheap physics upgrade** |
| **Bayesian model-vs-station blend** | Precision-weighted fusion: weight ∝ 1/σ² for climatology model vs live stations vs traversals | Trivial arithmetic | Standard optimal-interpolation; formalizes our existing `_debias` ratio-IDW into a citable scheme | **SHIP** |
| **Ventilation-physics microenv model** | Per-mode factor table + sensitivity to vehicle recirculation/filter state | Table lookup | Vehicle cabin: 70% recirculation → **−55% cabin PM2.5** (new filter), HVAC mode is *the* dominant in-cabin exposure variable. [Springer REC study](https://link.springer.com/article/10.1007/s11356-023-25219-x), [MDPI VIAQ](https://www.mdpi.com/2073-4433/16/11/1238), Delhi mode factors: walk 28.2×/rickshaw 5.3× metro per-km dose [ScienceDirect](https://www.sciencedirect.com/science/article/abs/pii/S1309104220303457) | **SHIP — powers "roll up windows / recirculate now" advisories** |
| **GP hyperlocal nowcast** | Spatial GP (or sparse GP) over stations+traversals | n=105 trivial; GP over 9M climatology needs inducing points/sparse approx | Kampala AirQo GP: RMSE ~17–18 µg/m³ with uncertainty; exact GP is O(n³) — fine at station scale, not history scale. [Kampala GP](https://arxiv.org/html/2311.16625v1), [Cambridge](https://www.cambridge.org/core/journals/environmental-data-science/article/using-gaussian-processes-for-spatial-prediction-of-pm25-concentration-based-on-calibrated-data-from-distributed-lowcost-sensor-networks/AEDACE5CF73E43FCE1BD1F0D58806435), [million-point GP needed multi-GPU](https://ar5iv.labs.arxiv.org/html/1903.08114) | **POST-HACKATHON — kriging gives 80% of the value** |
| **Personal dose state-space (HMM/Kalman on trajectory)** | Per-user filter fusing GPS trace, mode, field, physiology | Trivial compute; heavy *data* requirement (personal baseline) | Minute-ventilation estimation via HR/breath-rate: ~8–11% error models exist; cyclists ventilate ~2.3× car occupants. [PLOS VE model](https://journals.plos.org/plosone/article?id=10.1371%2Fjournal.pone.0147578), [pooled VE](https://journals.plos.org/plosone/article/file?id=10.1371%2Fjournal.pone.0218673&type=printable), [cyclist VE](https://link.springer.com/article/10.1186/1476-069X-8-48) | **POST-HACKATHON — needs wearable/user HR data** |
| **Full urban-canopy advection-diffusion solver** | CFD/LES-class or ADMS-Urban | Infeasible: HPC-scale, source inventories we don't have | As above | **NO** |

---

## (d) Contribution-loop design rules — from the corpses and the survivors

**The corpses** (why citizen sensing dies):
- **e2democracy climate panels**: 36% of 1,159 registrants contributed *nothing*; 27% more dropped out in months 2–4. Causes, in order: participation cost too much time, data entry too complex, **no visible effect**. [Springer](https://link.springer.com/chapter/10.1007/978-3-319-25403-6_13)
- **Sensor.Community (Poland study)**: users join for *family health*, not civic duty; organisers never created agency — contributors didn't know their data's value → churn. Motive is **individualistic**, design must accept that. [MDPI Sustainability](https://ideas.repec.org/a/gam/jsusta/v13y2021i20p11406-d657282.html)
- **Rennes municipal sensors**: strong workshop turnout → disengagement within 11 weeks of fieldwork; duty-driven participation decays without personal benefit. [chapter](https://exa.ai/library/publication/k3vyp7qyly6)
- **Hawa Badlo / Sameer complaints**: effort → black hole, no status visibility → dead loop.
- **Incentive-mechanism surveys**: money/games work short-term but service-exchange (mutual benefit) sustains; incentives without utility don't survive. [IEEE COMST](https://dl.acm.org/doi/10.1109/COMST.2015.2415528), [ACM TOSN](https://psycnet.apa.org/doi/10.1145/2888398)

**The survivors** (what works):
- **Waze**: the core loop is **passive default-on** — your driving reports speed without a tap; active reports ride on top. Utility-first: you contribute *by consuming*. Gamification (points, Baby→Royalty ranks, map-editor tiers) is the *second* layer, never the reason to use it. NYC contribution data shows a concave "virtual crowdedness" effect — contributions rise with local user density then **saturate/bystander**: show people *uncovered* corridors, not "Delhi already has enough." [HBS](https://aiinstitute.hbs.edu/platform-digit/submission/waze-helping-people-create-local-driving-communities-that-work-together-to-improve-the-quality-of-everyones-daily-driving/), [ISR paper](https://ideas.repec.org/a/inm/orisre/v31y2020i4p1398-1420.html)
- **CitiSense (UCSD)**: real-time personal exposure display "bridged data and experience" → users spontaneously changed routes/habits and shared. Feedback must be **immediate and in-world**. [PervasiveHealth](https://eudl.eu/doi/10.4108/icst.pervasivehealth.2012.248724), [UCSD dissertation](https://escholarship.org/uc/item/52m1h315)
- **CurieuzeNeuzen (Antwerp→Flanders)**: 2,000 then **20,000** citizens, **98% kit return** — the largest AQ citizen-science project ever. Mechanics: hyper-local curiosity ("my street vs yours"), a fixed short campaign, visible citywide map of everyone's result, press amplification. Lesson: *bounded campaigns + personal address + public map*. [2016](https://2016.curieuzeneuzen.be/en/), [2018](https://2018.curieuzeneuzen.be/vlaanderen-2018/in-english/)
- **PurpleAir→EPA**: citizen data adopted into the federal Fire & Smoke Map — proof crowdsourced AQ can become official infrastructure. [PurpleAir map](https://www.purpleair.com/real-time-map)
- **INSINC (Singapore LTA)**: shifted commuters off-peak with **raffle rewards + social comparison + personalized offers**; pre-peak rail volume +12%; ~76% of peak trips came from 20% of commuters → target the few. [Stanford paper](https://web.stanford.edu/~balaji/papers/13INSINC.pdf), [NUS](https://news.nus.edu.sg/rail-passenger-volume-prior-to-morning-peak-period-up-by-12-after-introduction-of-incentives/)

**Rules for Alive's loop**:
1. **Donate by default, by doing** — traversal donation on option-select (already built), zero extra taps. Never make contribution a separate chore (that's the e2democracy/Sameer death).
2. **Immediate visible receipt** — post-trip: "You just measured Corridor 12 for the 47th time this week." CitiSense showed immediacy converts data→agency.
3. **Personal motive first, civic second** — lead with "your lungs/family" (Sensor.Community's actual motive), let the collective map be the *byproduct* that becomes the flex.
4. **Surface scarcity, not abundance** — quest prompts for unmeasured corridors near the user ("this street has never been measured"); counteracts bystander saturation found in Waze data.
5. **Close every report's loop** — hazard reports must show resolution/verification status; invisible outcomes killed every Indian predecessor.
6. **Raffles > points for behavior nudges** — when we later push off-peak (`/depart`), copy INSINC: lottery rewards + friend comparison beats flat incentives.

---

## (e) The strongest honest impact claim

**Primary claim (submission text)**:
> *"On Delhi's worst corridors, Alive's dose-ranked options cut modeled inhaled PM2.5 by up to ~50% versus the fastest route — typically 5–25% for near-zero added time — and mode choice alone changes per-km inhaled dose by up to 28×."*

Every clause is anchored:
- **up to ~50% on worst corridors**: DRUM's own Delhi simulation: LEAP −53% exposure (at +42% time — we say the tradeoff honestly). [TRB](https://sage.cnpereading.com/doi/10.1177/03611981251331011)
- **typically 5–25%**: Thessaloniki −4% avg/−24% of long routes >5% [MDPI](https://www.mdpi.com/2624-6511/9/2/24); Leicester median −6% NO₂, max −48–60% [Frontiers](https://www.frontiersin.org/journals/sustainable-cities/articles/10.3389/frsc.2026.1869860/full); CAR Taiwan −17.1% avg for +2.4% distance [paper](https://exa.ai/library/publication/4phy3zcflbp); London measured back-street routes −30–60% black carbon [Guardian](https://www.theguardian.com/environment/2017/jun/14/side-street-routes-avoid-city-pollution-cut-exposure-by-half), [CRP report](https://crossriverpartnership.org/wp-content/uploads/2019/04/clean-air-walking-routes-air-quality-monitoring-report-1-1.pdf); systematic review: high-vs-low routes differ 30±8% BC / 55±17% UFP, and **up to 36 of 10,000 deaths preventable** by low-exposure routing (WHO AirQ+ modeling). [Frontiers review](https://www.frontiersin.org/journals/sustainable-cities/articles/10.3389/frsc.2020.565733/full)
- **28× mode factor**: measured Delhi microenvironment study (inhaled µg/km: walking 28.2×, rickshaw 5.3× metro). [ScienceDirect](https://www.sciencedirect.com/science/article/abs/pii/S1309104220303457)
- **off-peak nudge works**: INSINC +12% pre-peak rail volume via modest incentives [Stanford](https://web.stanford.edu/~balaji/papers/13INSINC.pdf)
- **collective data reaches policy**: CAQM analyzed 115 public comments and demonstrably incorporated themes into Delhi air policy [PMC](https://pmc.ncbi.nlm.nih.gov/articles/PMC10703133/); crowdsourced sensors outperformed CPCB's capped-500 index during the Nov-2024 episode [The Hindu](https://www.thehindu.com/sci-tech/energy-and-environment/crowdsourced-devices-help-track-air-pollution-as-government-monitors-lag-behind/article68897298.ece); PurpleAir became EPA infrastructure.

**Required honesty guardrails** (say these, they strengthen not weaken):
- Reductions are *modeled* (field × microenv × ventilation), pending personal-sensor validation — the standard every paper above uses.
- We cut *personal inhaled dose*, not Delhi's concentration — population-level exposure is emissions-limited (Stockholm mode-shift study shows citywide −7% NOₓ while individual benefits dominate). [STOTEN](https://www.sciencedirect.com/science/article/pii/S0048969717301559)
- "Delhi air should get lower" happens via two documented mechanisms we can claim: (i) **our aggregated traversal corridors become public evidence** the Sameer/Hawa Badlo complaint loops never produced, and (ii) off-peak shifting is proven elastic (INSINC). We cannot yet claim measured citywide PM reduction — don't try.

---

## (f) 5 stealable consumer features

1. **"Delhi Air Wrapped" — yearly/monthly share card.** Spotify Wrapped works via personalization (cocktail-party effect), narrative bias, and social signaling — users share what makes them look interesting. Ours: "In October I inhaled the cleanest 3% of Delhi commutes — 412 cigarettes dodged." Sources: [Growth.Design](https://growth.design/case-studies/spotify-wrapped-psychology), [ChoiceHacking](https://www.choicehacking.com/2023/11/27/how-spotify-used-psychology/), [UX Collective](https://uxdesign.cc/why-is-spotify-wrapped-so-popular-5c503e79a3ee)

2. **Lung Streak (with streak-freeze).** Duolingo's streak is their biggest growth lever: **10M+ users hold ≥1-year streaks; a third of DAUs have friend streaks; Streak Revival resurrected 15.4M users; CURR 84%**. Their rules: the daily unit must be trivially simple ("one lesson" → ours: "one under-budget commute"), user-chosen commitment ("commit to my goal" copy tested better), and week-1 retention is where everything is decided. Sources: [Duolingo Q4FY24 letter](https://duolingo.gcs-web.com/static-files/99006c40-d8cf-41ca-b5b1-c5cb1fa5ba88), [Q2FY26 letter](https://investors.duolingo.com/static/files/3c8277ee-bc94-4f5d-9b77-0db3e46f88b8), [Lenny's breakdown](https://www.lennysnewsletter.com/p/behind-the-product-duolingo-streaks)

3. **Corridor leaderboards (Strava segments for air).** "Cleanest commuter on Ring Road this week" + ward-vs-ward dose leaderboard ("Malviya Nagar vs Lajpat Nagar: who breathed best?"). Strava's segment leaderboards are one of its highest-value engagement surfaces; group challenges became its #2 challenge type. Sources: [Strava design case](https://www.jessicagillis.com/work/strava), [Strava eng. on segments](https://medium.com/strava-engineering/rebuilding-the-segment-leaderboards-infrastructure-part-2-first-principles-of-a-new-system-cd2e77c82ba3)

4. **Dose ring + day-shape arc (Apple rings × Oura).** Close the ring = stay under daily dose budget (we already ship BUDGET_UG=216 µg in the ledger). The arc: dose accumulated by hour through the day vs yesterday — one glance shows *when* damage happened. Fits "health app" mental model users already pay for.

5. **"I avoided N cigarettes" social share card.** Sh*t! I Smoke — a single-sentence app (cigarettes = PM2.5 via Berkeley Earth's 22 µg/m³ rule) went globally viral on this exact mechanic, TV-to-newspapers reach. We've already got better math (CIG_UG=316 + real dose) — we just haven't made it a shareable artifact yet. Sources: [shootismoke.app](https://shootismoke.app/), [Highsnobiety](https://www.highsnobiety.com/p/smoking-pollution-air-app/), [Digital Trends](https://www.digitaltrends.com/home/air-pollution-cigarettes/)

*Honorable mentions worth a slide: school-run dose comparison ("this morning's school run cost 0.4 cig" — parents are the highest-motivation segment per Sensor.Community), business-district dose index (Connaught Place daily dose vs Gurgaon Cyber City), "recirculate now" in-cabin advisory driven by breakthrough #3's ventilation model.*

---

## One-paragraph verdict for the submission
Every concentration-weighted "clean route" product either died (BreezoMeter Cleanest Route → Google API), never shipped consumer-scale (DRUM, CAR, every academic prototype), or does AQI-overlays without dose (CleanRoute, Ambee). Every citizen-sensing loop either needed hardware that consumers abandoned (Flow, AirBeam, SensorBox) or routed effort into black holes (Hawa Badlo, Sameer). **The unclaimed territory is exactly the intersection Alive already sits in: inhaled-dose (not concentration) turn-by-turn navigation, with a passive traversal loop where every trip updates the field, and physics-honest uncertainty on every number.** Ship #1 for the demo, #2 for the story, #3 for the defense.
