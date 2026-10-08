# Alive — Peak-Physics Feasibility Map

*Deep-research deliverable: the frontier beyond what is already shipped (kriged field + uncertainty bands, Kalman-smoothed stations, dose math, GTFS transit, wind-advected IDW, BLH stagnation factor in `/depart`). Question: what real mathematical/engineering machinery could a ~3-day build honestly ship that would make technical judges sit up.*

*Every data path below was verified live from this box on 2026-10-03 UTC. Citations inline.*

---

## Baseline — what already exists (so this doc doesn't re-claim it)

| Shipped | Where |
|---|---|
| Kriged/IDW field over 48-pt NCR grid + confidence tiers (hi/med/lo) | `server/airfield.py` |
| Wind-advected sampling weights (`UPWIND_GAIN`) | `server/airfield.py` |
| Per-station LOO debias + field calibration (MAE 8.8 µg/m³, n=70 WAQI+DPCC) | `server/calibrate.py` |
| Mode × ventilation × microenv dose = µg inhaled per route leg | `server/exposure.py` |
| `/depart` leave-later over 120h CAMS forecast + BLH stagnation factor | `server/forecast.py` |
| FIRMS fire pixels + DTP blackspot layers | `fires-blackspots` branch merge |
| Semi-Lagrangian-style field advection (decision "SHIP" from docs/22) | doc'd, partially in |

---

## Verdict table (ranked by feasibility × jury impact)

| Rank | Item (asked #) | Honest build time | Feasibility | WOW |
|---|---|---|---|---|
| 1 | **"Lid over Delhi" — daily ventilation coefficient** (topic 2) | **0.5–1 day** | **SHIP** — all inputs live-verified | One number that says how suffocated the city is today + its clean-air window. No product anywhere shows VC. |
| 2 | **Source-fraction estimate** (topic 3) | 1–2 days | **SHIP as labeled surrogate** — real DSS feed is unreachable (verified); climatological fractions + fire-calibrated fire-share are honest | "X% of your commute today is farm-fire smoke" — the question every Delhiite asks in November |
| 3 | **Satellite-constrained daily field** (topic 5) | 1–2 days (imagery: hours) | **PARTIAL** — MAIAC-NRT 1 km daily is real but needs Earthdata login; GIBS imagery is zero-auth NOW; trained downscaler is a 2-week build | "Delhi's haze, photographed from space this morning" in the demo video |
| 4 | **Advection-diffusion live field + assimilation** (topic 1) | 2–3 days prototype / 1–2 wk validated | **BORDERLINE** — OI/3D-Var is cheap on 1 CPU; the cost is validation data, not FLOPs | Pollution that moves like weather: plume replay animation + backward trajectories |
| 5 | **Personal microenv refinement** (topic 4) | 1 day (metro split + wind factor) | **SHIP the cheap half**; street-canyon OSPM is 1–2 wk; per-person wake is research-frontier | Honest "underground metro legs aren't actually clean" nuance nobody else models |
| — | Emission tomography / physics-GNN / 4D-Var | ≥2 weeks | **NO for hackathon** — document as moat | — |

---

## 1. Daily "lid over Delhi" — ventilation coefficient as a product number (TOPIC 2)

### What it is
The **ventilation coefficient** VC = ∫₀^H u(z) dz ≈ BLH × ū_BL (boundary-layer height × mean wind speed through the layer), units m²/s. It is *the* standard operational measure of how fast a city can flush its emissions — IMD/IITM use it for fog and pollution advisories, and Delhi has a published 30-year VC climatology and trend.

### The real math
- VC(h) = BLH(h) × ū_BL(h). ū_BL estimated from Open-Meteo hourly `wind_speed_10m/80m/120m/180m` — all four verified live today (daytime values 1.2–4.5 m/s).
- Daily diagnostic: mean VC + percentile vs Delhi October climatology → a 0–100 "breathability" index; sub-daily curve gives the **clean-air window** (hours when VC > ~4000 m²/s).
- Regime labels straight from the literature: **Normal / Stagnation / Heatwave / Photochemical** — a 2026 npj *Clean Air* paper classifies Delhi NCR days exactly this way from BLH + wind + ventilation index, and finds **stagnation days amplify black carbon +78% and NO₂ +80% in Delhi NCR vs normal days** ([Nature, s44407-026-00079-0](https://www.nature.com/articles/s44407-026-00079-0)).

### Delhi-specific literature anchors
- **Padmanabhamurty & Mandal 1979** — Delhi inversion/mixing-depth/VC climatology, MAUSAM ([doi:10.54302/mausam.v30i4.3091](https://doi.org/10.54302/mausam.v30i4.3091)).
- **Iyer & Ernest Raj 2013**, J. Earth Syst. Sci. — 30-yr radiosonde VC trends over four metros: **Delhi's December VC declined −49 m²/s per year**; Delhi has the highest pollution potential of the four because it's inland with no sea breeze ([paper](https://www.ias.ac.in/describe/article/jess/122/02/0537-0549)).
- **IGP semi-arid VC climatology** (2022): Delhi seasonal mean VC — **post-monsoon 907±522, winter 1112±574, monsoon 1358±680, pre-monsoon 3667±2140 m²/s**; VC >6000 m²/s = strong dispersion (Iyer & Raj convention).
- Vittal Murty et al. 1980 (Boundary-Layer Meteorology) — original Indian-city mixing-height/VC set.

### Data needed / availability (verified 2026-10-03)
| Input | Source | Status |
|---|---|---|
| Hourly BLH | Open-Meteo `boundary_layer_height` | ✅ live: today Delhi 30–1550 m diurnal |
| BL-mean wind | Open-Meteo 10/80/120/180 m | ✅ live: 1.1–4.5 m/s today |
| Climatology | Literature table above | ✅ static numbers, citeable |

**Today's measured output (computed live):** daily mean VC ≈ **1386 m²/s**; night mean ≈ **285 m²/s**; midday peak ≈ **6300 m²/s** — a textbook October day: night lid slams shut (~5% of daytime capacity), afternoon vent opens. This is already a demo line: *"Delhi's ventilation fell 96% between 1 pm and 7 pm — your 7 pm drive breathes air that cannot leave."*

### Honest feasibility in days
**0.5–1 day.** Arithmetic + climatology percentile + UI chip. Extends the BLH factor already in `/depart`/`forecast.py`.

### WOW for a jury
A single number and a 24-h curve that make the invisible lid tangible; backed by a 2026 paper that quantifies what stagnation *does* (+78% BC). Nobody — not AQI apps, not Sameer, not SAFAR's public page — publishes Delhi's daily VC to citizens.

### Honest limits
- Open-Meteo BLH is IFS-model output, not a Delhi sounding. Truth-check vs IMD Safdarjung radiosonde when obtainable; today's 15:00 UTC dip (BLH 95 m inside a convective window) shows model noise — smooth with a 3-h rolling floor or persistence check.
- VC is *dispersion capacity*, not concentration — same VC with tripled emissions still triples PM. Label it "how well Delhi can breathe," never "air quality forecast."

---

## 2. Source apportionment — "how much of today is farm fires?" (TOPIC 3)

### What it is
IITM Pune's **Decision Support System (DSS v1.0)** — a WRF-Chem tagged-source framework that decomposes Delhi's PM2.5 daily into: Delhi self, surrounding NCR, stubble burning in Punjab/Haryana, and everything else; plus an 8-sector within-Delhi breakdown and scenario levers (GMD 17, 2617, 2024 — [gmd-17-2617-2024](https://gmd.copernicus.org/articles/17/2617/2024/)).

### Real published numbers (citable)
- Seasonal means (post-monsoon | winter): Delhi **34.4% | 33.4%**, NCR rest **31.0% | 40.2%**, biomass **7.3% | 0.1%**, other regions **27.3% | 26.4%**. Peak episodes: Delhi sources ≤65%, farm fires ≤69% (DSS paper).
- Daily feed values as published in press: **35.1%** stubble on Nov 1, 2024 (season peak); **23.3/20.4/22.8%** Nov 4–6; transport **~11–12.5%** those days ([Hindustan Times, Nov 8 2024](https://www.hindustantimes.com/cities/delhi-news/punjab-haryana-farm-fires-account-for-20-of-delhi-pm2-5-from-nov-4-6-dss-data-101731001096428.html)); **31%** Nov 13 ([India Today, Nov 15 2024](https://www.indiatoday.in/cities/delhi/story/delhi-air-pollution-quality-stubble-burning-data-weather-2633695-2024-11-15)). Method per DSS's own disclaimer: yesterday's VIIRS fire count for the hindcast; climatological fires for the +3-day forecast.

### Reachable without keys? — verified today (2026-10-03)
| Host | Result |
|---|---|
| `ews.tropmet.res.in` (DSS portal) | ❌ resolves to **private IP 172.25.1.46**, TCP timeout — dead from outside IITM's network (third session confirming) |
| `ews1.tropmet.res.in` | ⚠️ public IP 103.251.184.15, HTTPS up, but serves only a "Site Under Maintenance" placeholder — DSS currently offline |
| `safar.tropmet.res.in` | ✅ **live** — Delhi NCR forecast page renders (200), but it's the legacy CMS; `map_data.php` AJAX endpoints return empty for all probed params; no machine-readable daily fractions |
| `safar.tropmet.res.in/source.pdf` | ✅ 2018 SAFAR Delhi high-resolution emission inventory exec summary — real sector inventory, useful as static prior |

**Verdict: the real daily DSS fractions are NOT programmatically reachable.** There is no key to request — the portal is dead infrastructure. (From India, site status may differ; we can't verify that.)

### What we CAN honestly ship
1. **Climatological fractions** — static seasonal sector split from DSS paper + SAFAR-2018 inventory + IITK-2015 + TERI-ARAI (all in docs/23). Zero risk, zero compute.
2. **Fire-share surrogate** — `stubble_share(t) ≈ f(upwind FIRMS fire count 72 h, NW-wind transport factor, 1/VC)`, **calibrated against the press-published DSS daily series** (Nov 2024 values above = 7+ ground-truth points for a monotone fit). FIRMS is already integrated. Label: *"modeled estimate calibrated to IITM DSS published values."*
3. Sector split shown as **climatological ranges with live fire overlay** — honest at day-1, sharpened if DSS comes back online.

### Honest feasibility
Static fractions + fire-share surrogate: **1–2 days**, including the calibration and the "modeled, not DSS" labeling. Scraping a dead portal: impossible.

### WOW
In November this is the single most-asked Delhi question. Personalized per-route: *"of the 61 µg this drive would cost you, ≈9 µg is farm-fire smoke that crossed Punjab yesterday."* Judges get a number they've only ever seen in newspapers — generated by our own physics.

### Honest limits
A surrogate fit on ~7 press numbers is prior-shaped; it will be wrong in structure on unusual days. Ship only with the label; it's a *diagnostic* not a claim of DSS equivalence.

---

## 3. Satellite-constrained spatial field — AOD → PM2.5 (TOPIC 5)

### What it is
Aerosol Optical Depth (column-integrated aerosol extinction) converted to surface PM2.5 — the standard trick: **C_surf ≈ AOD × ρ × f(RH) / BLH** (dry-aerosol mass density × humidity growth factor, spread over boundary-layer depth). Method lineage: Koelemeijer et al. 2006 → van Donkelaar GEOS-Chem conversion-factor global maps → India-specific 1-km products.

### Published Delhi/India evidence
- **15-year, 1-km MAIAC Delhi NCR study** (Sagnik Dey group, IIT Delhi; AE 2019): bias-corrected satellite PM2.5, upwind regions 1.25× cleaner than downwind; two peak episodes (post-Diwali fires, late-Dec local+secondary) ([web.iitd.ac.in/~sagnik/AE2019a.pdf](https://web.iitd.ac.in/~sagnik/AE2019a.pdf)).
- **20-year 1-km PM2.5 database for all of India** (MDPI Remote Sensing 2020, [12, 3872](https://www.mdpi.com/2072-4292/12/23/3872)) — the same stack, national scale.
- Himawari-8 AOD + fine-mode fraction → PM2.5 ML models beat AOD-only (MDPI RS 2021, [13, 2779](https://www.mdpi.com/2072-4292/13/14/2779)) — FMF helps on dust vs haze days.

### Data availability (all verified live 2026-10-03)
| Product | Resolution / cadence | Access | Verdict |
|---|---|---|---|
| **MODIS MAIAC NRT** `MCD19A2N` | 1 km, daily composite, Terra ~10:30 IST + Aqua ~13:30 IST overpass; **60–125 min latency** ([LANCE](https://www.earthdata.nasa.gov/data/instruments/modis/near-real-time-data)) | LAADS — free **Earthdata login required** | **User task: register Earthdata.** Then 1–2 snapshots/day over Delhi |
| **GIBS imagery** (corrected reflectance tiles) | 250 m true-color, daily | ✅ **zero auth** — tile fetched live today | Ship a "today's haze from space" layer in *hours* |
| **INSAT-3DR/3DS AOD** | 0.1° (~10 km), 6 retrievals/day 06:00–08:30 UTC, RMS ±0.20 | MOSDAC (ISRO) — free registration, daytime+cloud-free only | India's own product; coarse but ISRO-grade provenance |
| **Himawari-8/9 AOD** | hourly, ~5 km | JAXA P-Tree — free registration | The only *hourly* satellite option covering Delhi |
| **AERONET ground truth** | — | ✅ sites **IN Delhi**: `New_Delhi`, `New_Delhi_IMD`, `IIT_Delhi` (verified in site list today) | Calibration/validation pairs exist locally |
| **GEOS-CF** (docs/23) | 0.25°, hourly, speciated PM2.5, no key | ✅ S3/OPeNDAP | Pragmatic "satellite-grade model prior" — ensemble member or cross-check |

### Achievable vs not
- **Hours**: GIBS true-color tile overlay — literally today's Delhi haze photo, no auth, no processing.
- **1–2 days**: fetch MAIAC-NRT granule → ratio-scale our existing spatial prior (V5.GL.04-based) where retrievals exist → "satellite-corrected day" flag on the field.
- **2-week build, do not claim**: trained GWR/random-forest downscaler (needs a season of AOD×station pairs), hourly PM2.5-from-AOD. AOD retrievals also fail exactly on fog/haze days when Delhi needs them most — satellite is a *prior refiner*, not a live source. Say that.

### WOW
A real satellite photo of Delhi's pollution in the demo video, plus "our field is daily-calibrated against NASA's morning overpass" — and it doubles the AWS story (tile pipeline on S3).

---

## 4. Live advection / data assimilation (TOPIC 1)

### The honest map of the literature hierarchy
| Scheme | Math | Cost on our scale | Verdict |
|---|---|---|---|
| Optimal interpolation (OI) | analysis = background + K(obs − H·bg), K = BHᵀ(HBHᵀ+R)⁻¹ | **Kriging IS univariate OI** — we already run it | Already have it; reframe + extend to space-time covariance = **1 day** |
| Space-time OI / EnOI | same, with flow-following covariance | 105 obs × grid — microseconds | EnOI on GRAPES/CUACE cut PM2.5 RMSE 73.7→46.4 µg/m³, gains persist ~24 h ([GMD 2023](https://gmd.copernicus.org/articles/16/4171/2023/)); OI on NAQPMS over Beijing-Tianjin-Hebei ([Zheng 2018, AAQR](https://aaqr.org)) |
| Newtonian **nudging** into a forward advection-diffusion model | ∂C/∂t = −∇·(uC) + ∇·(K∇C) + E − λC + G·(obs−C) | 48-pt or 1-km NCR grid at 60-s step — trivially cheap; **the hard part is E** (emissions field), not compute | 2–3-day prototype possible; **1–2 weeks** to validate honestly (K coefficient, E prior, plausibility tests). Prototype-only for hackathon |
| 3D-Var | minimize J = (x−x_b)ᵀB⁻¹(x−x_b) + (y−Hx)ᵀR⁻¹(y−Hx) | B is *literally our kriging covariance* — same machinery | Doable in days but buys little over space-time OI at our density |
| EnKF / reduced-rank KF | ensemble propagation of state + covariance | needs an ensemble-generating process (perturbed met/emissions) — design is the research, not the FLOPs | 1–2 weeks; post-hackathon moat (already in docs/03,06) |
| 4D-Var | adjoint of the transport model over a window | needs a hand-written adjoint — the one genuinely multi-week item | **NO** — cite CAMS/IFS as what this is for ([Bocquet et al. 2015, ACP review](https://acp.copernicus.org/articles/15/5325/2015/)) |
| **Inverse emission tomography** | solve E(x,t) from ∂C/∂t + ∇·(uC) − ∇·(K∇C) + λC using our own field series | adjoint/regularized inverse on small grid — feasible; literature: Hutchinson et al. 2017 STE review, lightweight-adjoint urban STE (Build. Simul. 2025: 22 m localization error, 15% MAPE) | The true frontier nobody ships — "a live map of where Delhi is *emitting* right now". ≥1 week on top of the forward model |

### What fits on ~1 Fargate CPU — the honest answer
**All of it, numerically.** OI solve = 105×105 matrix. A 100×100-cell explicit advection-diffusion step is milliseconds. n≤10⁴ cells is the wrong place to look for a bottleneck — **the binding constraint is validation data**, not FLOPs: with ~105 hourly stations and no dense reference network, a fancy forward model can be tuned to anything and proven nothing. That's why the hackathon-grade claim is: *"we run the same mathematics CAMS runs (OI analysis + advected prior), honestly parameterized, and we show the uncertainty."*

### Honest feasibility
- **SHIP (framing + space-time OI)**: 1 day. Rebrand honestly: "kriging = the OI analysis step of operational data assimilation" (true — Cressie/Daley equivalence), then add temporal covariance so last hour's field shapes this hour's where stations go quiet.
- **Prototype only (labeled experimental)**: advection-diffusion + nudging + implied-E map = 2–3 days to demo, ≥1 week to *defend* numbers.
- **NO**: 4D-Var (adjoint), full chemistry — weeks.

### WOW
- Animated "pollution flows like weather" plume replay (forward model + real wind) — visually, the single most impressive thing on the list.
- Backward trajectories: "the PM hitting your lungs at 8 am left Jhajjar at 2 am."
- If prototyped: live implied-emission map = "the city is emitting hardest along NH-48 right now" — research-grade, honestly framed.

---

## 5. Personal plume / exposure refinement (TOPIC 4)

### What the literature actually supports (vs. what we'd be making up)

| Claim | Evidence | Ship? |
|---|---|---|
| **Mode microenv factors** | Delhi Magenta-line measured runs: metro 34.2, car(closed) 62.3, bus 63–69, auto-rickshaw 113.2, 2W 41.9 µg/m³ ([Springer Discover Atmosphere 2025](https://link.springer.com/article/10.1007/s44292-025-00071-5)); walk 28.2×, rickshaw 5.3× metro per-km inhaled mass ([ScienceDirect 2021](https://www.sciencedirect.com/science/article/abs/pii/S1309104220303457)) | ✅ already core to the dose engine |
| **Car cabin filtration** | I/O ratio 0.20 new filter → 0.60 aged; 70% recirculation → −55% cabin PM2.5; HVAC mode is the dominant variable (cited in docs/22) | ✅ cheap — powers "recirculate now" advisories |
| **Wind sensitivity of exposure** | London determinants study: exposure swings **1.5–2× between p10 and p90 wind days**; route+mode+wind explain ~35% of personal-exposure variance ([Atmos. Environ. 2001](https://www.sciencedirect.com/science/article/abs/S1352231001001947)) | ✅ **1 day** — widen dose bands by today's wind; it's published, we compute it |
| **Underground metro ≠ clean** | NYC: underground platforms **142±69** vs aboveground **29±20** µg/m³; in-train 88±14 underground vs 29±31 aboveground ([PMC](https://pmc.ncbi.nlm.nih.gov/articles/PMC10237451/)); Seoul: tunnel 132 → platform 58, mass balance shows 62% of platform PM2.5 comes from the tunnel ([Springer AAQR](https://link.springer.com/article/10.4209/aaqr.200573)); Fe 29–43% of underground PM mass (wheel/rail wear) — **elevated mass, different composition** (must cite both) | ✅ **1 day** — we have the DMRC underground-station registry; split metro dose into tunnel vs elevated legs. Honest and surprising |
| **Street canyon increment** | OSPM (Aarhus, operational since the '90s): plume model for direct + box model for canyon recirculation + traffic-produced turbulence; needs roof-level met + canyon geometry + fleet emissions ([model description](https://envs.au.dk/en/research-areas/air-pollution-emissions-and-effects/the-monitoring-program/air-pollution-models/ospm/description-of-the-ospm-model)) | ⚠️ canyon-lite (road class × congestion × wind parameterization) = 2–3 days; **true per-street OSPM = 1–2 wk** (Delhi OSM building heights are sparse — real data gap) |
| **Personal cloud / own wake** | ~20 µg/m³ coarse-mode self-generated particles (EXPOLIS, Harrison 2002) — real but mostly >PM2.5 | Footnote only |
| **Per-person plume around the walker** | No operational literature — research frontier (CFD pedestrian studies exist at single-street scale) | ❌ don't claim |

### Honest feasibility
- **1 day**: underground-metro leg factor + wind-modulated dose bands + cabin-REC advisory copy.
- **2–3 days**: canyon-lite corridor increment (parameterized, labeled).
- **1–2 weeks**: OSPM per street (needs building-height data we don't have).

### WOW
The counterintuitive finding *is* the demo: "the metro is our cleanest ride — except the underground legs, where iron-rich tunnel air isn't clean. We split your metro dose at the tunnel portal." Judges who know the subway-PM literature will recognize we did the homework; judges who don't get a surprising, citable fact.

---

## Frontier beyond the asked five (documented, not built)

1. **Emission tomography** — implied E(x,t) field from our own field's time series (inverse dispersion / STE literature: Hutchinson 2017; lightweight adjoint methods hit 22 m source localization on MUST). The most novel research-grade output here; gated on topic-1's forward model.
2. **Physics-guided graph models** — GraPhy (ACM TOSN 2026): GNN edges carrying convection-diffusion physics + wind-direction features; +9–56% over baselines in sparse-monitoring regions. At 105 stations we're in exactly that regime — but training needs the historical corpus; 1–2 weeks. *Post-hackathon moat, already flagged in docs/03.*
3. **Full 4D-Var / EnKF with adjoint** — what CAMS/WRF-Chem run; multi-week + adjoint authoring. Cite only.

---

## Ship list for a 3-day window (brutal ranking)

1. **VC daily index + clean-air window** (0.5–1 d) — do it first; it's a headline number with a 30-year Delhi climatology behind it.
2. **Source fractions: climatological + fire-share surrogate, labeled** (1 d) — the November question, answered honestly.
3. **GIBS "today's Delhi from space" tile** (hours) + MAIAC-NRT scaled prior if the user registers Earthdata (add ~1 d).
4. **Underground-metro dose split + wind-scaled dose bands** (1 d) — cheap depth on the existing engine.
5. **Only if time remains**: space-time OI reframing (relabel honestly, add temporal covariance) — 1 d, pure math, feeds the "we run CAMS's math" line.
6. **Do not attempt**: DSS scraping (dead infra), trained AOD downscaler, OSPM per-street, per-person wake, 4D-Var, emission tomography — mark all ≥1–2 weeks.

## User actions that would unlock items
- **Register NASA Earthdata** (free, 5 min) → unlocks MAIAC NRT MCD19A2N 1-km daily Delhi.
- **Register MOSDAC** → INSAT-3DR/3DS AOD (India's own, nice provenance line).
- **JAXA P-Tree registration** → Himawari hourly AOD (only hourly satellite option).
- Watch `ews1.tropmet.res.in` — if IITM's maintenance ends before Oct 11, real DSS daily fractions become reachable; design the UI so climatological fractions can be swapped for live ones.

## Verified-this-session log (2026-10-03 UTC)
- Open-Meteo BLH + 10/80/120/180 m winds: live, Delhi diurnal BLH 30→1550 m; today's computed VC: daily mean ≈1386 m²/s, night ≈285, midday peak ≈6300.
- `ews.tropmet.res.in` → 172.25.1.46 (private) + TCP timeout. `ews1.tropmet.res.in` → up but "Site Under Maintenance". `safar.tropmet.res.in` → 200, legacy CMS only; `map_data.php` empty for all param probes; `source.pdf` = 2018 SAFAR Delhi emission inventory.
- GIBS MODIS Terra true-color tile over Delhi: HTTP 200, zero auth.
- LAADS NRT portal: reachable (login-gated download). AERONET site list confirms `New_Delhi`, `New_Delhi_IMD`, `IIT_Delhi` validation sites. GEOS-CF bucket live (us-west-2). MOSDAC, JAXA P-Tree, CAMS ADS portals all reachable.
