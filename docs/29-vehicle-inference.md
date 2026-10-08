# 29 · The Emissions Inference Problem — what a Delhi vehicle emits when every vehicle is different

*Deep-research deliverable, 2026-10-03. Question under test: Alive tracks the user's trip dose AND their vehicle's emissions live — but every vehicle in Delhi differs by age, fuel, BS class and PUC status. Can we honestly say "your trip emitted X"? All data paths verified live unless noted.*

---

## 0. Verdict up front

**There is no public or official way to look up an arbitrary vehicle's PUC status or emission reading in India today — and even if there were, a PUC record could not tell us its PM2.5/CO2/NOx anyway.** The PUC test itself only measures CO + HC at idle (petrol/CNG/LPG) or smoke opacity (diesel); it produces no PM2.5 mass, no NOx, no CO2 figure. So the "emissions inference" is not a lookup problem — it is a classification problem, and Delhi's own enforcement apparatus already does exactly that: CAQM's fuel-denial and GRAP bans work off **registration → age → fuel → BS class**, never off PUC readings.

**The best honest inference chain (2 taps):** vehicle class + fuel (optional: model year) → BS-class bucket via the Delhi registration-year table (§2) → class×fuel×BS emission factor from the measured-factor literature (§3) → reported as a **band around a class median**, never a point value, in "vehicles like yours" language (§5). Within-class spread is real — the newest measured data (ICCT TRUE remote sensing, Delhi/Gurugram 2024; IIT-B Kamshet tunnel 2024) shows usage pattern (taxi vs private) and condition (maintenance, overloading) can move a single vehicle 2–14× off its class mean. We claim **"estimated for a 2016 diesel car (BS-IV)"** — we must NEVER claim **"your car emitted 42 g of PM"**.

| Question | One-line answer |
|---|---|
| Per-vehicle PUC lookup? | **No** — citizen form needs chassis digits + CAPTCHA; the real API is approval-gated; unofficial resellers exist but are paid/ToS-restricted. |
| Would PUC data even help? | **No** — it records idle CO/HC or smoke opacity, not PM2.5/NOx/CO2. |
| Can year → BS class work? | **Yes** — Delhi cutovers are precise (§2), with a ±1-reg-year edge band at cutovers. |
| Do EF tables exist? | **Yes** — ARAI/ICAP 2007 measured table (usable today), IIT-B/CSTEP harmonized BS-I→VI set (right source, **embargoed**), SIM/Guttikunda PM2.5 set, ICCT real-world uplifts. |
| Honest product claim? | Class-median ± spread band. "Vehicles like yours emit ≈X–Y" — never per-vehicle truth. |

---

## 1. PUC per-vehicle lookup — every channel, honestly

### What a PUCC actually contains
A Pollution Under Control Certificate records: reg no, date, validity, odometer, and the **measured readings** — which for petrol/CNG/LPG vehicles are **idle-test CO% and HC ppm**, and for diesels **free-acceleration smoke opacity** (light-absorption m⁻¹ / Hartridge units). Statutory limits under CMVR Rule 115: diesel smoke ≤ 2.45 m⁻¹ / 65 HSU; BS-IV+ petrol ≤ 0.3% CO + 200 ppm HC at idle.

**Consequence:** PUC readings cannot yield an emission factor. CSE's on-road emissions review states it plainly: *"no accurate correlation found between smoke readings and PM mass … PM and NOx emissions cannot be tested"* ([CSE presentation](http://cdn.cseindia.org/attachments/0.39388400_1560943654_On-road-emissions-Vivek.pdf)). Hindustan Times' 2026 explainer on Delhi's "no PUC, no fuel" drive makes the same point — the test "cannot detect nitrogen oxides or the fine particles that escape a modern diesel's filter" ([HT, 29 Sep 2026](https://www.hindustantimes.com/ht-explainers/puc-test-delhi-ncr-winter-air-pollution-caqm-plan-what-the-test-does-particulate-matter-vehicle-emissions-test-101790655803929.html)). And it barely screens: Delhi diesel PUC failure rate ≈ 6% (CSE). A valid PUC ≈ "not a gross CO/smoke emitter at idle" — nothing more.

### Channel-by-channel

| Channel | Status | What it gives | Blocker |
|---|---|---|---|
| **puc.parivahan.gov.in citizen lookup** | ✅ exists | Own PUCC PDF: reg no + **last-5 chassis** + security code (CAPTCHA) | Needs chassis digits an app never has; CAPTCHA = no legal automation; owner-self-service only. Verified page live today: `puc.parivahan.gov.in/puc/views/PucCertificate.xhtml`. |
| **PUCC public dashboard** (same site) | ✅ open, no key | National aggregates: 423M+ certificates issued, split by **norms (BS-IV 107.8M / BS-VI 74.4M / other 241.2M), fuel, category, plus PUCC-defaulter counts** | Aggregate only — no per-vehicle rows. Still useful: real compliance-mix stats for product copy. |
| **MoRTH National Transport Repository (NTR) API** — the only real per-vehicle API | ⚠️ **approval-gated** | Search ANY vehicle by reg/chassis/engine; registration, fuel, norms fields; personal data masked | MoRTH data-sharing policy: access only for **approved data recipients** (insurers, financiers, govt, researchers via application) — not self-serve, not instant. Legacy portal `vahan.parivahan.gov.in/paidnrservices/` shows *"new payments for data access discontinued"* and migration to `services.parivahan.gov.in/ntr/` (legacy closed 15 Sep 2026 — already dead). Policy: [parivahan.gov.in data-sharing-policy.pdf](https://parivahan.gov.in/sites/default/files/policy/data-sharing-policy.pdf). |
| **VAHAN citizen "know your vehicle" / mParivahan app** | ⚠️ owner-gated | RC details incl. norms/fuel | Behind owner-mobile OTP — masked for non-owners. Cannot be used for vehicles that aren't the user's. |
| **DigiLocker** | ⚠️ partner-gated | Issued docs incl. transport docs pulled with user consent | Third-party pull requires becoming a DigiLocker **Authorized Partner/Requester** (onboarding, agreements) — real but a partnership track, not a weekend integration. |
| **data.gov.in** | ✅ open | Only aggregate catalogs (state/RTO/fuel/norms registration counts, TERI-ARAI source shares) | Zero per-vehicle data by design. |
| **Delhi Transport Dept portal** | ❌ nothing extra | CNG retro-fitment application forms, circulars | No separate PUC/vehicle lookup — Delhi rides the national PUCC/VAHAN systems. |
| **Unofficial B2B APIs** (vahanx-type "RC verification" vendors) | ⚠️ exists, paid | Per-vehicle RC lookups resold from NTR data-sharing | Paid per-call, B2B agreements, redistribution/ToS restrictions — wrong shape for a free hackathon app and legally gray at scale. |

### The telling precedent
Delhi-NCR's own enforcement **does not use PUC readings**: CAQM Direction No. 89 mandates **ANPR cameras at fuel stations denying fuel to end-of-life vehicles** (diesel >10 yr, petrol >15 yr) — the camera resolves the plate against VAHAN's age/fuel record. The Oct-2026 "no PUC, no fuel" drive similarly gates on certificate *validity*, not the vehicle's measured output. **The state infers vehicle class from the registration database, not from per-vehicle emissions data. That is the only model that exists, and it is the model we should use.**

---

## 2. Registration year → BS class, for Delhi specifically

### The cutover table (verified against SC judgment in *M.C. Mehta*, 24 Oct 2018, and PIB/MoRTH notifications)

| Delhi-registered vintage | BS class (4W/LMV) | Notes |
|---|---|---|
| before ~2001 | pre-BS / BS-I | BS-II applied NCR 2001 (4W) |
| Apr 2001 – Mar 2005 | BS-II | Delhi among first metros (with Mumbai, Kolkata, Chennai) |
| Apr 2005 – Mar 2010 | **BS-III** | Only BS-III new registrations allowed in Delhi+NCR+metros from 1 Apr 2005; dealers could clear pre-existing BS-II stock briefly — registration-year mapping has a **months-scale fuzzy edge at every cutover** (SC judgment records the "accumulated stock" overlap). |
| Apr 2010 – Mar 2020 | **BS-IV** | BS-IV mandatory in NCR+13 cities 1 Apr 2010, nationwide 1 Apr 2017 — Delhi registrations this whole window are BS-IV. |
| Apr 2020 – today | **BS-VI** | Nationwide 1 Apr 2020 (BS-V skipped). Grace: BS-IV built pre-Apr-2020 registerable to **30 Jun 2020** (drive-away chassis 30 Sep 2020). Delhi filled BS-VI *fuel* from Apr 2018, so some 2018–19 Delhi registrations are early BS-VI — year → BS is conservative here. |
| 2W/3W caveat | — | 2W/3W BS-III only nationwide Apr 2010; BS-IV new models Apr 2016, all sales Apr 2017, BS-VI Apr 2020. For 2W: pre-2010 = BS-II, 2010–16 ≈ BS-III, 2017–20 = BS-IV, 2020+ = BS-VI. |

### Delhi's own classification rules (already enforced — they validate the year→class ontology)

- **End-of-life ban (NGT 7 Apr 2015, ratified SC 29 Oct 2018):** diesel >10 yr and petrol >15 yr may not ply/register in NCR — enforced today via ANPR fuel-denial at pumps (CAQM Dir. 89). A 2012 diesel in Delhi is *illegal regardless of condition* — the app can hard-flag it.
- **GRAP Stage III (AQI 401–450):** bans **BS-III petrol and BS-IV diesel LMVs** in Delhi + Gurugram, Faridabad, Ghaziabad, Gautam Buddh Nagar; tighter goods-vehicle rules (CAQM revised schedule, Dec 2024; Direction 88 bars non-Delhi BS-III goods vehicles from 1 Nov 2025, BS-IV goods only till 31 Oct 2026). Delhi law literally sorts the fleet by BS×fuel — same buckets we'd infer.
- **CNG retrofit:** allowed only on petrol vehicles with ICAT/ARAI type-approved kits per model/engine-capacity window (±25% cc); BS-VI petrol retrofit notified 2022 (≤3.5 t GVW, ~≤1500 cc, 3-yr approval). Delhi public transport (bus, auto, taxi) has been CNG-mandated since ~2002–03 — an "auto" in Delhi is CNG, a "taxi" almost certainly petrol/CNG or CNG, and a private diesel car >2014 cannot legally exist in NCR.

### What a 2-question picker honestly yields

- **Type + fuel alone** (2 taps): fixes the biggest PM driver — class×fuel. PM2.5 spans ~100× across classes (CNG bus 0.044 vs old diesel truck ~2 g/km, §3).
- **+ model year** (optional slider/3rd tap): adds BS class — worth another ~5–10× on diesel PM (BS-II-era diesel car ~0.15 vs BS-VI DPF ~0.003 g/km).
- **What it cannot resolve:** condition/maintenance (the 2–14× real-world spread, §4), which is why output is a **band**, not a number.

---

## 3. Published emission-factor tables — what exists, what to quote

| Source | Coverage | Status for us |
|---|---|---|
| **ARAI / ICAP 2007**, *Emission Factor Development for Indian Vehicles* (CPCB+MoEF+oil cos; chassis-dyno, in-use fleet, MIDC) | Class × fuel × vintage (1991–96/96–2000/post-2000/post-2005) — CO, HC, NOx, CO2, PM + toxics | **The usable base table today.** It is the measurement foundation nearly every Indian inventory cites. Vintage-era (BS-II fuel) — apply real-world uplifts for modern classes. |
| **IIT-Bombay + CSTEP harmonized EF dataset** — Zenodo [10.5281/zenodo.21899911](https://doi.org/10.5281/zenodo.21899911) (Aug 2026, CC-BY-4.0) | 6 classes × petrol/diesel/CNG × **BS-I→BS-VI**, CO/NOx/OC/BC/**PM2.5**/VOC/CH4/N2O/NH3 + ARAI↔COPERT↔MOVES ratio maps | **The right source — but embargoed.** Metadata public, files closed (verified today). Switch the EF backend to it when released; cite it in the writeup as the harmonization lineage. |
| **SIM / urbanemissions (Guttikunda) PM2.5 set** (SIM-24-2009 and successors) | PM2.5 g/km by class×fuel: petrol car 0.05, diesel car 0.15, CNG car 0.03, bus diesel 0.34 / CNG 0.02, 3W petrol 0.08 / CNG 0.03, 2W 0.05 | Coarse but Delhi-calibrated (CNG bus/auto fleets); good PM2.5 cross-check. |
| **TERI–ARAI 2018 Delhi-NCR source apportionment** | Inventory EFs behind Delhi's transport share (receptor + dispersion, ~36% winter / ~26% summer of Delhi's own PM2.5 emissions) | Fleet-level; cite for the sector share, not per-vehicle factors. |
| **Type-approval limits** (context, not real-world) | Diesel car PM: BS-III 0.05 → BS-IV 0.025 → BS-VI 0.0045 g/km (+PN); BS-VI RDE conformity factor NOx 1.43 | Sets the *floor*; real-world is 1.4–14× above (below). |

### ARAI 2007 measured values worth shipping (g/km, MIDC, in-use Delhi-era fleet)

| Vehicle | PM (g/km) | CO2 (g/km) |
|---|---|---|
| 2-stroke auto (pre-2000) → post-2005 | 0.110 → 0.043 | 55 → 72 |
| 4-stroke motorcycle/scooter | 0.010–0.035 | 23–46 |
| Petrol car (<1400 cc) | 0.004–0.008 | 95–143 |
| Diesel car | **0.015–0.19 by vintage** | 129–157 |
| CNG car (retrofit) | 0.001–0.006 | 131–150 |
| MUV diesel | 0.096–0.57 | 164–256 |
| LCV diesel | 0.475–0.998 | 327–401 |
| City bus diesel (by vintage) | 0.30–2.01 | 602–921 |
| **CNG bus** | **0.044** | 807 |
| Truck diesel | 1.24–1.97 | 762–838 |

### Real-world correction (the honest uplift)

- **Jaiprakash & Habib (IIT Delhi, on-road tailpipe):** post-2010 diesel cars **CO2 556±261 g/km** (vs ~150 lab) and NOx 3.1±2.9 — the ±261 *is* the within-class spread.
- **Delhi onboard study 2021 (58 cars):** diesel CO 3.99 / NOx 0.54, petrol CO 7.26 / NOx 0.62 g/km real-world.
- **ICCT (BS-IV analysis):** real-world NOx **5–7×** and CO **10–22×** type-approval limits.
- **ICCT PEMS BS-VI (Pune 2022–24):** LNT diesels exceed NOx limits, SCR within; India BS-VI RDE CF = NOx 1.43 / PN 1.5.

Honest summary: **BS class × fuel explains ~1–2 orders of magnitude of PM difference; condition and use-pattern explain another 2–14× around that.** CO2 is the tightest factor (fuel burn, ±30–50% by drive-cycle/loading); PM/NOx are the widest.

---

## 4. Within-class spread and the counterfactual frame

- **IIT-B Kamshet-I tunnel** (Debbarma, Raparthi, Phuleria, Venkataraman — India's first real-world super-emitter census, Mumbai–Pune Expressway): **21% of the fleet are super-emitters** — 10% visible-plume, 11% overloaded freight. LDV super-emission tracks **age + maintenance**; HDV tracks **overloading** on top of those. They ship a model predicting super-emitter share from HDV/LDV mix, age, fuel — i.e., even researchers infer, they don't measure per-vehicle.
- **ICCT TRUE remote sensing, Delhi + Gurugram (Aug 2024):** BS-VI vehicles genuinely better across pollutants — **but usage dominates**: BS-VI taxi fleet NOx **2.4×** and light-goods fleet **5.0×** the private-car fleet, same BS class. And CNG is not a free pass: measured BS-VI CNG vehicles ran **1.5–14×** above type-approval limits. "Same class, different life" is the exact reason per-vehicle claims fail.
- Classic remote-sensing finding (global, holds in the Indian data): a minority of vehicles produces the majority of emissions — the tail is what matters, and it's invisible to year+fuel.

### The honest counterfactual
"Your trip emitted X" is computable only as **E(class, fuel, BS-band) × distance × drive-cycle factor**, where E is a class median with a stated band (order ~×0.5–2 typical, wider tail for super-emitters). "Avoided Y" = E(your class) − E(counterfactual mode) — defensible because both sides carry the same assumption set. Metro/e-bus legs are ~0 tailpipe (generation-side caveat noted); the avoided-emission story is strongest as **class-vs-class**, never per-vehicle.

---

## 5. VERDICT — the inference chain to ship

**Ask (≤2 taps):** ① vehicle class (2W / auto / car / taxi / bus) ② fuel (petrol / diesel / CNG / EV). *Optional* year slider upgrades year→BS.

**Derive:** year → BS bucket (§2 Delhi table, ±1-year cutover band) → EF median from ARAI-2007/SIM (§3) with real-world uplift for diesels/high-use → report **median ± band**.

**Band honesty:** label every output "estimated for a {year} {fuel} {class} (BS-n)"; show the spread explicitly; flag "condition can move a real vehicle 2–10× — maintained cars live at the bottom of the band" (true per IIT-B: age+maintenance drives LDV super-emission).

**NEVER claim:**
- per-vehicle emissions from PUC — the data isn't public and can't measure PM anyway;
- a point value ("your car emitted 42.0 g PM") — no honest model can;
- "CNG = clean" — ICCT TRUE shows high-use CNG 1.5–14× over limits;
- PUC-valid = low-emitter — it screens idle CO/smoke only (~6% fail).

**Legal data paths that DO go further:**
- **VAHAN public dashboards** (`vahan.parivahan.gov.in/vahan4dashboard`, moving to `analytics.parivahan.gov.in`): open pivot of registrations by RTO × year × fuel × **norms** — Delhi fleet mix ground truth, no key; dataful.in datasets 18128/18274 mirror it as CSV. When the user skips the year question, we can honestly say "the average Delhi {fuel} {class} is a {dominant BS class}" — a real prior, not a guess.
- **PUCC dashboard aggregates**: Delhi PUC-defaulter rates by norms/fuel for compliance-mix stats in the writeup.
- **FASTag open data** (dataful.in 21607): toll-plaza × vehicle-class volumes — real highway fleet mix by class for the inter-city leg product.
- **Optional power-user path (v2):** user photographs/keys in their own PUC readings → narrows the *petrol-CO* side of their band (self-reported, labeled) — the only legitimate per-vehicle datum, because it comes from the owner.

**One-line answer to the core question:** we cannot know *which* vehicle emits how much — India keeps that data behind approval gates and the PUC test couldn't measure it anyway; what we CAN know, the way the government itself enforces it, is *which class* a vehicle is in — and class×fuel×vintage explains most of the variance that matters for a trip-level estimate shown as an honest band.
