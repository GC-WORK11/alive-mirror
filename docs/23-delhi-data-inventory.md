# Delhi Air Data Inventory — deep source map for Alive

Researched 2026-10-02. Every row cites a URL; anything not confirmed against a primary
page is marked **[UNVERIFIED]**. "Free" = $0 usable in a demo app; terms noted where they bind.

Legend: ✅ in use today · 🆕 not in use · ⚠️ usable with caveats · ❌ rejected

---

## A. Source inventory

### A1. Ground stations — official government feeds

| # | Source | Endpoint / access | Cadence | Delhi coverage | Key? | Rate limit | Redistribution terms | Status |
|---|---|---|---|---|---|---|---|---|
| 1 | **CPCB CCR — Central Control Room for Air Quality Management, Delhi NCR** | `https://app.cpcbccr.com/ccr` (Next.js portal). Internal JSON POSTs used by community scrapers: `POST /aqi_dashboard/aqi_all_Parameters` (base64 payload `{"station_id":"site_NNNN","date":"…Z"}`), `POST …/fetch_table_data`. Scrapers: github.com/gsidhu/cpcbccr-data-scraper, github.com/sakethramanujam/cpcbccr-python-client | Station files push every **15 min** (CPCB transmission protocol: `app.cpcbccr.com/ccr_docs/Protocol_CAAQM.pdf`); portal repo lets you pull 15-min / hourly / 24-h aggregates | **~84 CAAQMS in the NCR list (Nov 2025), ~40 inside Delhi** (DPCC, CPCB, IMD, IITM operators) + Gurugram/Faridabad/Noida/Ghaziabad/etc. | Free registration for repo downloads; dashboard endpoints unofficial | Repo caps each query (~1 week of 15-min data per station×pollutant, per UrbanEmissions) | Govt of India data; portal has no explicit license — attribute CPCB. **Raw concentrations, not just AQI** — this is the richest free feed | 🆕 **best upgrade available** |
| 2 | **data.gov.in OGD — "Real time Air Quality Index"** | `https://api.data.gov.in/resource/3b01bcb8-0b14-4abf-b6f2-c1bfd384ba69?api-key=KEY&filters[state]=Delhi&format=json` — fields: station, last_update, pollutant_id, pollutant_min/max/avg | Hourly | ~40 Delhi stations (all CAAQMS operators merged) | Free API key from data.gov.in account | No officially published limit; third parties report ~2,000 req/hour [UNVERIFIED exact figure] | OGD India license (CC-BY-style attribution) | ✅ in use (key pending w/ user) |
| 3 | **CPCB daily AQI bulletin** | `https://cpcb.nic.in/` → "Daily AQI Bulletin (PDF)"; linked from `cpcb.nic.in/special-monitoring-data/` | Daily (~4pm IST) | City-level AQI for Delhi + all cities | None | n/a | Public bulletin; fine to quote with attribution | ✅ used for event labels |
| 4 | **DPCC own portal** | `https://www.dpccairdata.com/` (real-time per-station display pages); monthly reports at `dpcc.delhigovt.nic.in` | ~hourly display | 24–30 DPCC stations + 40 manual monitoring locations | None (web only) | n/a | Public display; no bulk license | ⚠️ same data as #1/#2 via back-end; use only if CCR fails |
| 5 | **HSPCB (Haryana)** | No live public portal of its own — `hspcb.gov.in` publishes reports only; per UPPCB/HSPCB docs, real-time CAAQMS data flows to the national portal (Sameer/CCR) | hourly via CCR | Gurugram, Faridabad, Sonipat, Panipat, Bhiwani, Mandikhera… (~22 CAAQMS tendered) | — | — | — | ⚠️ via #1/#2 only |
| 6 | **UPPCB (Uttar Pradesh)** | `uppcb.up.gov.in` — monthly manual-station data; real-time CAAQMS via national portal/Sameer (stated in their own micro-plan PDF) | hourly via CCR | Noida ×4, Greater Noida ×2, Ghaziabad ×4, Hapur, Baghpat, Meerut, Muzaffarnagar, Khurja, Bulandshahr | — | — | — | ⚠️ via #1/#2 only |
| 7 | **CPCB SAMEER app** | Mobile app (com.cpcb.sameer); data.gov.in catalog page: `data.gov.in/catalog/sameer-national-air-quality-index` | Hourly | Same national CAAQMS feed — 560 stations / 293 cities as of Jun 2025 (CPCB) | App | — | Public; backed by #1 | ⚠️ convenience only — same data |
| 8 | **Delhi hourly AQI archive (data.opencity.in CKAN)** | `https://data.opencity.in/dataset/delhi-hourly-air-quality-reports` — per-station CSVs | Hourly rows, **2017–2023** | 39 Delhi stations | None | Bulk CSV | Open civic mirror of CPCB data | 🆕 free backfill, no scraping |
| 9 | **US Embassy & Consulates monitor (AirNow)** | Map+archive: `https://gispub.epa.gov/airnowembassy/` (Archive tab = CSV); AirNow API free key at `docs.airnowapi.org`; also mirrored as WAQI feed `@7024` | Hourly | 1 BAM station, Chanakyapuri (reference-grade, independent of CPCB QC) | Free AirNow key | generous public tier | US Gov public data — attribution | 🆕 **independent truth source for calibration/debias** |
| 10 | **SAFAR — IITM Pune** | `https://safar.tropmet.res.in` (portal, email alerts); station list page confirms **11 Delhi AQMS** (NPL, DU, IGI-T3, Noida-NCMRWF, CRRI, Aya Nagar, Lodhi Rd, IIT-D, Dhirpur, Gurugram-NISE, Chandni Chowk) | ~15-min instruments; 1–3 day location-specific forecast | 11 stations incl. Gurugram/Noida | None public; formal data-sharing requires IITM collaboration | web only | Public display; bulk terms unclear [UNVERIFIED] | ⚠️ stations already surface via CCR/OpenAQ as IITM-operated sites |
| 11 | **IITM AQEWS + DSS** | `https://ews.tropmet.res.in/` (72 h WRF-Chem PM2.5 forecast, daily bulletin PDF) and `/dss/index.php` (stubble-burning % + local/non-local sector split, 4-day outlook; TERI-2021 inventory, assimilates CPCB PM2.5 + MODIS AOD + VIIRS fires) | Daily | Delhi-specific | None | web only | Public bulletin, cite as IITM | 🆕⚠️ **cite daily sector %**; note: host resolved to private IP (172.25.1.46) from our VM Oct 2026 — reachability intermittent |
| 12 | **NAMP manual stations (CPCB/DPCC)** | Monthly reports via DPCC site / CPCB "Manual Monitoring Data" | 2×/week grab samples | ~40 Delhi manual locations | None | PDF/web | Public | ⚠️ historical context only |

### A2. Aggregators & commercial APIs

| # | Source | Endpoint / access | Cadence | Delhi coverage | Key? | Rate limit | Redistribution terms | Status |
|---|---|---|---|---|---|---|---|---|
| 13 | **OpenAQ v3** | `https://api.openaq.org/v3/…` header `X-API-Key` (free at explore.openaq.org) | Hourly | ~105 CPCB/DPCC/HSPCB instruments registered in NCR (verified in-session; 30 DPCC + 24 WAQI live today — OpenAQ key dormant) | Yes (free) | **60/min + 2,000/hour** (docs.openaq.org/using-the-api/rate-limits) | Per-source license metadata; attribution required | ⚠️ dormant without a fresh key (stored key 401); archive below still powers climatology |
| 14 | **OpenAQ S3 archive** | `s3://openaq-data-archive/records/csv.gz/locationid={id}/year=YYYY/month=MM/` `--no-sign-request` | Daily files, multi-year | All NCR stations back to ~2016 | None | S3 public | Same as above | ✅ powers climatology (125 stations × ~10 years; "9.04M rows" = raw-row count, unverified) |
| 15 | **WAQI / aqicn.org** | `https://api.waqi.info/feed/@{id}/?token=…`, city/feed/search/map endpoints | Hourly | All Delhi stations + others | Free token | Stated quota **1,000 req/s** (aqicn.org/api/); older ToS page says ~16 RPS + 60 burst | ⚠️ **No caching/archived redistribution, no paid apps, attribution mandatory, non-profit needs notification, for-profit needs agreement** | ✅ **primary measured feed today** (24 instruments live; the "cross-check only" caveat was written pre-integration) |
| 16 | **IQAir AirVisual API** | `https://api-docs.iqair.com/` | Hourly | Global incl. Delhi stations | Free key via dashboard | Community: **5 calls/min, 500/day, 10,000/month** (iqair.com/kw/air-quality-monitors/api) | ToS restrict redistribution; display w/ attribution | ⚠️ rich Delhi coverage but thin quota; validation only |
| 17 | **AirGradient Public API + world feed** | `https://api.airgradient.com/public/api/v1/world/locations/measures/current` — **works with no token** (verified 2026-10-02: 2,867 public monitors worldwide); per-monitor history needs free dashboard token; Swagger docs | ~1–5 min | **Only 3 public monitors in NCR bbox** (verified live: GK1/Oberoi Terrace, Vasant Kunj, Sector 62 Gurugram) | Optional for world feed | Generous | CC-BY-SA 4.0 (API) / CC-BY 4.0 via OpenAQ | ❌ density insufficient for Delhi today — recheck later |
| 18 | **sensor.community (luftdaten)** | `https://archive.sensor.community/` — per-sensor daily CSVs, `csv_per_month/`, parquet monthly dumps; `data.sensor.community` live API | ~2.5-min raw | India coverage very sparse; Delhi count [UNVERIFIED — likely <10] | None | Bulk files | Public database, attribution | ⚠️ too sparse for Delhi |
| 19 | **aqi.in (Purelogic Labs / Airveda network)** | Public site + unofficial JSON API `https://apiserver.aqi.in` (endpoints: getNearestLocation, 12h–30d history, rankings; OSS clients: github.com/neo773/aqi-in-api, PyPI `aqi-in-api`) | Hourly | **Densest Delhi low-cost network** (Kaiterra/Sensible monitors) | JWT auto-generated (unofficial) | Unknown | Terms unpublished — redistribution rights [UNVERIFIED]; unofficial access is fragile/ToS-gray | ⚠️ tempting density, risky license — do NOT build on it |
| 20 | **OpenWeather Air Pollution API** | `https://api.openweathermap.org/data/2.5/air_pollution{,/forecast,/history}?lat&lon&appid=` | Hourly, model-derived | Global point data | Free key | Free tier: **60 calls/min, 1M/month** | OWM license — attribution, limited redistribution | 🆕 cheap backup field (model, not stations) |
| 21 | **Google Air Quality API** | `airquality.googleapis.com` | Hourly + 4-day fcst + 30-day history | **500×500 m grid**, India incl. `ind_cpcb` NAQI | Paid | 6,000 QPM | Paid Maps Platform | ❌ budget (already rejected) |
| 22 | **Ambee / Meteomatics / Tomorrow.io / BreezoMeter** | REST | Hourly | Global | Paid | Ambee trial ~100 calls/day×15 days | Paid | ❌ thin trials (already rejected) |
| 23 | **PurpleAir** | `api.purpleair.com` | 2-min | Sparse Delhi coverage | Paid API points | — | Paid | ❌ sparse + paid (already rejected) |
| 24 | **Plume Labs** | — | — | — | — | — | API discontinued post-AccuWeather acquisition | ❌ dead |

### A3. Satellite & model fields

| # | Source | Endpoint / access | Cadence | Resolution over Delhi | Key? | Rate limit | Terms | Status |
|---|---|---|---|---|---|---|---|---|
| 25 | **NASA GEOS-CF v2** (GEOS + GEOS-Chem analysis+forecast) | OPeNDAP `http://opendap.nccs.nasa.gov/dods/gmao/geos-cf/v2/fcst/…` — **no login**; public S3 `s3://smce-geos-cf-public/geos-cf-v2-fcst-latest.zarr/`; CFAPI point-timeseries (email request); files via NCCS portal | Hourly, 5-day forecast | **0.25° (~25 km)** — PM2.5 total **speciated** (BC/dust/nitrate/ammonium/OC/SOA/sea-salt at RH35) + NO2, O3, CO | None for OPeNDAP/S3 | bulk | NASA open data | 🆕 **best free forecast field** — beats CAMS 0.4° |
| 26 | **CAMS global composition forecasts** | `cdsapi` → dataset `cams-global-atmospheric-composition-forecasts`, ads.atmosphere.copernicus.eu | 00/12 UTC ×2/day, hourly surface | **0.4° (~44 km)** PM1/2.5/10 + dust/BC/etc. | Free CDS account + per-dataset licence click | Queued retrieval | Copernicus licence (attribution) | ✅ via Open-Meteo AQ today |
| 27 | **CAMS EAC4 reanalysis** | same ADS | 3-hourly | 0.75° | same | same | same | 🆕 historical model backfill |
| 28 | **Sentinel-5P TROPOMI L2** | Copernicus Data Space `dataspace.copernicus.eu` (OData/openEO/Sentinel-Hub `sentinel-5p-l2`) | Daily (~13:30 local overpass) | **3.5×5.5 km** NO2 (tropospheric col), HCHO, CO, SO2, O3, aerosol index | Free CDSE account | bulk | Free & open Copernicus data | 🆕 daily emission-field proxy (NO2→traffic/industry) |
| 29 | **MAIAC MCD19A2 (MODIS Terra+Aqua)** | LAADS DAAC `ladsweb.modaps.eosdis.nasa.gov` / Earthdata | Daily | **1 km AOD (0.47/0.55 µm)** + smoke injection height + column water vapor | Free Earthdata login | bulk | NASA open | 🆕 **1-km daily haze layer** — best satellite texture for PM field |
| 30 | **MODIS/VIIRS Dark Target & Deep Blue AOD** | LAADS / Earthdata | Daily | 3–10 km | Earthdata login | bulk | NASA open | 🆕 AOD alternative to MAIAC |
| 31 | **van Donkelaar V5.GL.04 annual PM2.5** | `sites.wustl.edu/acag/surface-pm2-5-archive/` + NASA SEDAC (data.nasa.gov) | Annual 1998–2022 | **0.01° (~1 km)** GeoTIFF/netCDF, GWR-calibrated vs ground monitors | None | bulk | Cite ACAG/WUSTL + SEDAC | 🆕 **research-grade spatial prior for under-monitored cells** |
| 32 | **NASA FIRMS** | `firms.modaps.eosdis.nasa.gov/api/area/csv/{MAP_KEY}/{SENSOR}/{bbox}/{days}` | NRT (~3 h lag) | VIIRS SNPP/NOAA-20/21 375 m, MODIS 1 km fire pixels | Free MAP_KEY | **5,000 transactions / 10-min**; multi-day queries count extra | NASA open | ✅ module ready (key pending) |
| 33 | **ISRO MOSDAC — INSAT-3D/3DR AOD** | `mosdac.gov.in/mosdac-satellite-data-download-api` (mdapi.py + datasetId `3DIMG_L2G_AOD`); catalog `mosdac.gov.in/catalog-app/satellite.php` | **Geostationary ~30-min** | ~1 km AOD over Indian region | Free MOSDAC SSO | per-request | ISRO open (registration) | 🆕 **only sub-hourly satellite aerosol — smoke-plume tracking in daytime** |
| 34 | **JAXA Himawari-8/9 AOD** | `www.eorc.jaxa.jp/ptree/` (Himawari Monitor + P-Tree data) | Hourly daytime | ~5 km Asia disk | Free registration | bulk | Free w/ registration | [UNVERIFIED for bulk PM use] — geostationary complement to #33 |
| 35 | **MERRA-2 aerosol reanalysis** | GES DISC / Earthdata | Hourly | 0.5°×0.625° | Earthdata login | bulk | NASA open | ⚠️ too coarse; backfill only |
| 36 | **Pandonia Global Network (Pandora)** | `pandonia-global-network.org` data portal | ~min | Column NO2/O3/HCHO ground truth | None | web/API | Public | ❌ no Delhi instrument — nearest is ARIES Nainital (~250 km, since 2024, research deployment) |
| 37 | **AERONET** | `aeronet.gsfc.nasa.gov` download tool + web service | ~15-min daytime | Gual_Pahari (Gurugram district, NCR) site exists in network lists [verify current activity]; historical Delhi-region AOD | None | bulk | Public domain — cite AERONET+PI | 🆕 AOD truth for satellite calibration |
| 38 | **Open-Meteo (met + AQ)** | `api.open-meteo.com/v1/{forecast,archive}`, `/v1/air-quality` (CAMS) | Hourly; archive→1940 | ERA5-Land ~0.1° met; CAMS ~0.4° AQ | None | ≤10k/day, 5k/h, 600/min **non-commercial only** | **CC BY 4.0 — attribution required** | ✅ in use |
| 39 | **Met.no Locationforecast** | `api.met.no/weatherapi/locationforecast/2.0/` | Hourly | Global ~10 km | None (needs User-Agent) | ~20 req/s fair-use | CC BY 4.0 + Norwegian licence | 🆕 free backup met |
| 40 | **NOAA HYSPLIT (READY)** | `ready.arl.noaa.gov` web + local model | On demand | Back/forward trajectories | None | web | Public | 🆕 explain "smoke arriving" days mechanically |

### A4. Delhi-specific datasets (emissions, traffic, safety, transit)

| # | Source | Access | What it gives | Terms | Status |
|---|---|---|---|---|---|
| 41 | **Delhi OTD (otd.delhi.gov.in)** — Transport Dept + IIIT-D | `/data/static/` (bus GTFS zip: 543 routes/3,464 stops), `/data/staticDMRC/` (metro GTFS zip: 262 stations/36 routes), `/api/realtime/VehiclePositions.pb?key=` | Official GTFS static **free**; GTFS-RT bus positions **key on request** | Open data | ✅ static in use; RT key owed |
| 42 | **MoRTH black-spot MIS** | `blackspot.morth.gov.in` — **Delhi: 115 of 8,882 national**; mirror CSV `dataful.in/datasets/21559/` (8,862 rows, 2014–2025); data.gov.in "top-10" resources | Accident black-spot locations + repair status | Govt open data | 🆕 **half-day unblock for safety layer (no key needed via dataful)** |
| 43 | **TomTom Traffic Index** | `tomtom.com/traffic-index/city/new-delhi/` | Annual metro stats: Delhi 2025 congestion **60.2%**, 24:28/10 km, 104 h/yr rush-hour loss (India #4) | Web stats free; API paid | 🆕 cite stats; congestion context |
| 44 | **VAHAN / Delhi Economic Survey / Statistical Abstract** | `des.delhi.gov.in` PDFs | Fleet: **79.45 lakh** on-road Mar-2023; 1.42 crore cumulative; ~90.5% 2W+cars; +6.5 lakh in 2023-24; 473 veh/1000 pop | Public reports | 🆕 citation numbers |
| 45 | **EDGAR v8.1** | `edgar.jrc.ec.europa.eu/dataset_ap81` | Monthly emission gridmaps 0.1° 1970–2022, all pollutants+sectors | Free w/ citation | 🆕 background emission field |
| 46 | **TERI-ARAI 2018 source apportionment** | `teriin.org/sites/default/files/2018-08/Report_SA_AQM-Delhi-NCR_0.pdf` | Delhi-own emissions = **36% winter / 26% summer** of Delhi PM2.5; receptor+dispersion models | Report, cite | ✅ cited |
| 47 | **IIT-Kanpur 2015 (DPCC)** | `cerca.iitd.ac.in/uploads/Reports/1576211826iitk.pdf` | PM2.5 load 59 t/d; emissions: road dust 38%, vehicles 20%, domestic 12%, industry 11%; ambient winter: secondary 25–30%, vehicles ~28%, biomass 17–26% | Report, cite | ✅ cited |
| 48 | **SAFAR emission inventory** | tropmet.res.in project page | **1×1 km GIS emission inventory** for SAFAR cities incl. Delhi (biofuel, power, transport, residential, dust, crematoria) | Research product | 🆕 finest official inventory grid |
| 49 | **UrbanEmissions.info APnA (Guttikunda)** | `urbanemissions.info/delhi-air-quality-forecasts/` | Delhi 80×80 km, **0.01° (~1 km), hourly, 72-h forecast** — WRF-CAMx on gridded inventory, dynamically updated with gridded speed maps | Research site, cite w/ attribution | 🆕 **a working Delhi hyperlocal model to borrow/cite** |
| 50 | **AIRDELHI (IIT-Delhi, NeurIPS 2023)** | `cse.iitd.ac.in/pollutiondata` | Bus-mounted mobile PM2.5/PM10 dataset, Delhi-NCR | Public research dataset | 🆕 method-training data |
| 51 | **Kaiterra/UChicago 28-sensor Delhi deployment** | npj Climate s41612-022-00293-z | 2 yr, 28 sensors south Delhi; also arXiv:2410.04309 — **space-time kriging hit 98% precision for hotspots with sparse sensors** | Papers + partner data | 🆕 method template |
| 52 | **MoRTH "Road Accidents in India"** | morth.nic.in annual PDFs | Mode-wise crash/fatality shares | Public | ✅ mode-risk factors |
| 53 | **NCAP Delhi city action plan** | CPCB/ncap tracker | City action plan + funding progress | Public | 🆕 policy context |
| 54 | **OSM (Geofabrik asia/india)** | download.geofabrik.de | Road graph + landuse/industrial/green polygons for LUR predictors | ODbL | ✅ base network; no formal Delhi completeness audit found [UNVERIFIED quality %] |
| 55 | **LUR predictor layers** | ESA WorldCover 10 m (`worldcover2021.esa.int`), GHSL built surface (`ghsl.jrc.ec.europa.eu`), WorldPop 100 m (`worldpop.org`), VIIRS nightlights (`eogdata.mines.edu/products/vnl/`) | Free global layers for land-use regression | Open | 🆕 playbook inputs |

### A5. Exposure-science inputs (mode dose factors)

| # | Source | Numbers | Status |
|---|---|---|---|
| 56 | **Goel et al. 2021, Sustainable Cities & Society** (Delhi 6-mode, RDD) | Inhaled PM2.5/km: **walk 28.2×, rickshaw 5.3× metro**; AC car & metro lowest | ✅ backbone |
| 57 | **Delhi 8-mode microenvironment study (TRID 2321797)** | Mean PM2.5: bicycle 59.8 (highest), metro 55.8, AC-bus 40.8, AC-car 40.2 µg/m³; **morning peak = worst dose** | ✅ |
| 58 | **Delhi Metro Magenta-line study (Discover Atmosphere 2025)** | Run-avg PM2.5: **auto-rickshaw 113.2 > car-open 71 > bus-open 68.9 > car-closed 62.3 > bus-closed 63.1 > 2W 41.9 > metro 34.2 µg/m³** | 🆕 cite |
| 59 | **Underground metro station study (Athens J. Sci. 2016)** | Platform particle metals (Fe, Si, Mn, Cu) **indoor > outdoor** — metro is cleaner on PM2.5 mass but metal-rich underground | 🆕 nuance |
| 60 | **Zuurbier et al. 2009 (Environ. Health)** | Cyclist minute ventilation **2.1× car, 2.0× bus** (measured) | ✅ |
| 61 | **US EPA Exposure Factors Handbook ch.5** | Reference inhalation-rate table by activity (sedentary→heavy; standard values used by all dose papers) | ✅ reference |
| 62 | **Cabin filtration studies (Environ. Sci. Pollut. Res. 2020/2023)** | In-cabin I/O PM2.5: **0.20 new filter, 0.60 aged**; ionizer→0.15–0.20; **70% recirculation −55%/−39% PM2.5** | 🆕 AC-car factor justification |
| 63 | **Karner et al. 2010 near-road meta-analysis (ES&T)** | Traffic-tracer decay ~within **500 m**; sharpest drop first 5–30 m; PM2.5 gradient gentler than NOx/BC | ✅ road-increment prior |
| 64 | **Delhi built-environment traffic-PM ANN (Bahadur Shah Zafar Rd)** | Traffic variable~2× more significant in open terrain than canyon; supports road-class weighting | 🆕 |
| 65 | **APT-MAXIMA 22-sensor Delhi network (2021)** | Seasonal PM2.5 means: **winter 205.2, autumn 171.7, summer 64.6, monsoon 27.6 µg/m³**; sensors R² 0.84–0.95 vs BAM | 🆕 seasonal anchors |

---

## B. Top 5 sources NOT in use — ranked by impact per day of work

1. **CPCB CCR raw portal** (`app.cpcbccr.com`) — raw **15-min concentrations** for ~84 NCR stations (vs ~40 hourly AQI rows in data.gov.in), all pollutants + met params. Programmatic pull via the documented POST endpoints / the two OSS scraper clients. **Impact:** denser field, more stations beyond Delhi proper (Gurugram/Noida/Ghaziabad), finer time resolution for /depart. **Effort:** ~1–2 days. This is the single biggest upgrade.
2. **van Donkelaar V5.GL.04 annual PM2.5 (0.01°)** — research-grade 1-km climatology, free GeoTIFF. Blend as spatial prior wherever station distance > ~5 km (i.e., the ~65% of Delhi IndiaSpend says lacks reliable coverage) — upgrades every weakly-monitored cell from pure-IDW guess to satellite-calibrated estimate. **Effort:** <1 day.
3. **NASA GEOS-CF** (OPeNDAP / public S3 Zarr, no key) — hourly **speciated** PM2.5 (dust/BC/nitrate/SOA…) + NO2 at 0.25° for 5 days — richer forecast field than Open-Meteo's CAMS 0.4° and **free with no registration**. **Effort:** ~1 day.
4. **IITM DSS + AQEWS** — daily official stubble %, transport %, local/non-local split + 72-h WRF-Chem forecast. Borrow their daily stubble fraction as a fire-season field modifier and cite DSS as provenance for "why today is bad". **Effort:** ~half day (web scrape) — *caveat: ews.tropmet.res.in was unreachable from our VM Oct 2026 (DNS→private IP); verify reachability before committing*.
5. **MoRTH black spots via dataful mirror** (`dataful.in/datasets/21559/`) — 115 Delhi spots as CSV **without waiting for the data.gov.in key**; completes the already-designed safety layer. **Effort:** ~half day.

Honorable mentions: **AirNow embassy BAM archive** (independent calibration truth, ~half day), **MAIAC 1-km AOD** (best satellite texture but ~3–5 days of QC/humidity-correction work), **UrbanEmissions Delhi 1-km CAMx** (a finished hyperlocal model to validate against), **Delhi OTD GTFS-RT key** (live bus density → congestion proxy), **aqi.in** (densest low-cost net but license-unverified — skip).

---

## C. Delhi-specific numbers to cite (hardcode nowhere)

- **GRAP stages (CAQM revised schedule, Dec 2024)**: I = AQI 201–300 'Poor', II = 301–400 'Very Poor', III = 401–450 'Severe', IV = >450 'Severe+'; stages invoked **in advance** on IMD/IITM forecast; III/IV trigger school hybrid mode, truck/C&D restrictions. Source: caqm.nic.in schedule PDF.
- **Annual PM2.5**: Delhi **91.6 µg/m³ in 2024** (92.7 in 2023) — world's most polluted capital 6th straight year; India mean 50.6; worst city globally = Byrnihat 128.2 (IQAir WAQR 2024).
- **Seasonal PM2.5 (IIT-Bombay APT network 2019–20)**: winter ~205, autumn ~172, summer ~65, monsoon ~28 µg/m³.
- **Source apportionment**: IIT-K 2015 — PM2.5 load 59 t/d; emissions road dust 38% / vehicles 20% / domestic 12% / industry 11%; ambient winter vehicles ~28% incl. secondary nitrate, biomass 17–26%. TERI-ARAI 2018 — **Delhi's own emissions only 36% (winter) / 26% (summer) of Delhi PM2.5** → regional transport dominates → explain "you can't outrun winter".
- **Stubble share**: DSS — Nov 1 2024 = **35.1%** (season high), Nov 4–6 = 20–23%, Nov 13 = 31%; transport #2 at ~11–12% same week. Peak-event literature range 20–40%; IITK winter biomass 17–26%.
- **Farm fires**: Punjab **5,114** and Haryana **662** in season-2025 (−53%/−86%/−90%/−93% vs 2024/23/22/21 for Punjab) per CAQM PR 01-Dec-2025; monitoring window Sep 15–Nov 30 (ISRO protocol via IARI CREAMS, MODIS+VIIRS). **iFOREST Dec 2025**: official counts miss **>90% of large fires** (burning shifted post-15:00, after satellite passes) — treat fire counts as floor, not truth.
- **Fleet**: **79.45 lakh** vehicles on road Mar-2023 (+6.5 lakh in 2023-24), 1.42 crore cumulative registrations; ~90.5% two-wheelers + cars; 473 vehicles/1000 people. DTC fleet 3,937 buses.
- **Ridership**: Metro ~46 lakh/day, DTC ~25 lakh, Cluster ~16.4 lakh (2022-23 Economic Survey).
- **Congestion**: TomTom 2025 — Delhi 60.2% congestion, 24:28 per 10 km, 104 h/yr lost (India #4 after Bengaluru/Pune/Mumbai).
- **Monitoring density**: ~40 CAAQMS inside Delhi (~84 in NCR list); ~65% of Delhi's area lacks reliable station estimates (IndiaSpend Nov 2025) — the product's reason to exist.
- **Exposure ratios**: walk 28.2× and rickshaw 5.3× metro inhaled PM2.5/km (Goel 2021); rickshaw ride mean ~113 vs metro ~34 µg/m³ (Magenta-line 2025); AC-car cabin I/O 0.2 (new filter)–0.6 (aged), 70% recirc −55% PM2.5; cyclist ventilation 2.1× car passenger (Zuurbier 2009); morning peak = highest dose (8-mode study).
- **Safety**: 115 MoRTH black spots in Delhi; MoRTH annual report for mode fatality shares.
- **WHO guideline**: 5 µg/m³ annual PM2.5 — Delhi runs ~18× that.

---

## D. Street-level modeling playbook — cheapest path to a real hyperlocal field

What exists already, proven on Delhi:

- **Saraswat et al. (UW Marshall lab, ES&T 2013)**: Delhi LUR for PM2.5/BC/UFP — morning R² **0.85** using only population density + road variables + a fixed-site covariate. The method works in Delhi with predictors we already have (OSM roads + WorldPop).
- **Kaiterra/UChicago 28-sensor deployment (npj Climate + arXiv:2410.04309)**: space-time kriging over sparse sensors found **189 extra hotspots** beyond the govt network's 660; 98% precision @ 50% sensor failure. Proves kriging-with-limited-sensors is the honest method here — deep nets needed multimodal data that "was not reliably, frequently and accurately available in the New Delhi context".
- **UrbanEmissions APnA**: a complete 1-km WRF-CAMx Delhi model already running (72-h forecast, emission inventory updated via gridded speed maps) — use as validation/citation, not as a dependency.
- **van Donkelaar V5.GL.04**: research-grade 1-km annual PM2.5 for every Delhi cell (1998–2022) — the spatial prior that kills the "65% unmonitored" problem.

Cheapest credible pipeline (all free):

1. **Prior**: resample V5.GL.04 → Delhi grid; scale each year to the CPCB station-median annual mean (keeps satellite *spatial texture*, replaces its absolute level with ground truth).
2. **Live backbone**: CPCB CCR 15-min pulls for all ~84 NCR stations → QC (spike/range checks) → krige or IDW residuals over the prior (spatially-varying: strong where stations are dense, prior-led where sparse — report the blend weight as our existing `data_km`/confidence field).
3. **Road increment layer**: OSM road-class density (primary/trunk/motorway weighted > residential) × Karner decay (increment concentrated in first ~30 m, tail to ~300–500 m), scaled by congestion context (TomTom annual level + own corridor proxy; OTD GTFS-RT bus density when the key lands). This produces street-vs-street contrast the station grid cannot.
4. **Land-use/LUR residual**: fit the Saraswat-style regression — predictors: road density, population (WorldPop), industrial+green fractions (OSM polygons / ESA WorldCover 10 m), nightlights (VIIRS). Apply as small bounded correction (±10–20%) to the kriged field.
5. **Event texture**: FIRMS fire counts (smoke days), MAIAC 1-km AOD (day-specific haze, humidity/BLH-corrected then regressed to CPCB same-day), DSS stubble % as provenance label; HYSPLIT for a "smoke arriving" narrative on peak days.
6. **Honest calibration & QA**: leave-one-out against CCR stations; hold out **US Embassy BAM** as a never-trained-on truth; keep low-cost sources (AirGradient×3, sensor.community, aqi.in) out of the field until density/licensing improves — use AIRDELHI bus-sensor data only to sanity-check street-level gradients.
7. **Forecast**: GEOS-CF speciated field for the +6/+12/+24 h horizons (better texture than CAMS 0.4°), dampened toward the climatology as skill drops; DSS/AQEWS bulletins for official early-warning days.

What this avoids: any paid API, any license-ambiguous aggregator, any hardware, any unverifiable numbers — and it upgrades the field from "station interpolation" to "street-aware, satellite-informed, cited" for roughly **3–4 days of work** (steps 1–4; steps 5–7 are stretch items).

---

### Appendix — quickly verified negatives
- AirGradient public network: **2,867 monitors worldwide but only 3 inside NCR** (live-checked 2026-10-02) — insufficient for Delhi hyperlocal.
- Pandonia/Pandora: India is not on the PGN country list; only deployment is ARIES Nainital (2024, research) — no Delhi data.
- sensor.community & PurpleAir: too sparse in Delhi to matter.
- Plume Labs API: discontinued.
- No free real-time Delhi traffic API exists (TomTom/HERE/Mappls all paid or eval-tier); own corridor density is the honest proxy.
