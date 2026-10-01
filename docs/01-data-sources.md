# 01 · Data Source Map

Every source verified 2026-10-01. "Free" means $0 usable for this project; restrictions noted where they bind.

## 1. Air quality — real-time

| Source | Endpoint / Access | Coverage Delhi | Update | License / Limits | Role |
|---|---|---|---|---|---|
| **CPCB via data.gov.in** ⭐ | `https://api.data.gov.in/resource/3b01bcb8-0b14-4abf-b6f2-c1bfd384ba69?api-key=KEY&filters[state]=Delhi` | ~46 CAAQMS stations (30 DPCC, 10 IMD/IITM, 6 CPCB) | Hourly | Govt of India open data; free API key (register at data.gov.in). Pollutants: PM2.5, PM10, NO2, Ozone, CO, SO2, NH3 | **Primary live feed** |
| **OpenAQ v3** ⭐ | `https://api.openaq.org/v3/...` header `X-API-Key` (free signup at explore.openaq.org) | Mirrors CAAQMS + some AirNow | Hourly | Free within rate limits; per-source license metadata on each location | **Primary live feed + station metadata** (lat/lon, instruments, licensing) |
| **CPCB AQI portal** | `https://airquality.cpcb.gov.in/AQI/` — bulletin archive | NCR bulletin + station AQI | Daily bulletin | Public web; scrape only the published bulletin PDFs/HTML, politely | City-level AQI bulletins; station list cross-check |
| **WAQI (aqicn.org)** | `https://aqicn.org/api/` free token, 1000 req/s quota | Station-level | Hourly | ⚠️ Terms: **no caching/redistribution of archived data**, no paid apps, attribution + non-profit notification required | Cross-check only; **do NOT build the DB on it** |
| **Google Air Quality API** | Maps Platform | India supported (`ind_cpcb`), 500 m grid, hourly + 4-day forecast + 30-day history | Hourly | Paid (~$0.50/1k calls after free tier in India) | Optional paid validation layer — **rejected for MVP** (budget) |
| **Ambee** | REST | Global incl. India | Hourly | 100 calls/day × 15 days trial — too thin | Competitor, not dependency |

### Monitoring-gap reality (matters for the model)
- IndiaSpend (Nov 2025): ~65% of Delhi's area lacks reliable station estimates — the fused field + uncertainty map is *the product's reason to exist*.
- Newslaundry (Dec 2024): many stations sited beside trees/walls contrary to CPCB norms → per-station reliability weighting is justified, not optional.

## 2. Air quality — historical (for back-testing & climatology)

| Source | Access | Depth | Cost | Role |
|---|---|---|---|---|
| **OpenAQ S3 archive** ⭐ | `s3://openaq-data-archive/records/csv.gz/locationid={id}/year=YYYY/month=MM/` — public, `--no-sign-request` | Per-location per-day csv.gz, multi-year | Free; already lives on AWS | **Historical backfill for calibration + back-testing** |
| CPCB bulletin archive | airquality.cpcb.gov.in bulletin PDFs | Daily city AQI, years | Free | Event labels (Diwali spikes, GRAP days) |

## 3. Meteorology

| Source | Access | Variables | Cost | Role |
|---|---|---|---|---|
| **Open-Meteo** ⭐ | `https://api.open-meteo.com/v1/forecast` + `/v1/archive` — no key | Wind speed/dir, temp, RH, precip, boundary-layer height; hourly; ERA5 archive to 1940 | Free ≤10k calls/day non-commercial, CC BY 4.0 | Met layer for dispersion + historical covariates |
| **Open-Meteo Air Quality** | `/v1/air-quality` | CAMS global 45 km, 3-hourly | Same | Coarse regional background only — too coarse for streets |
| **NASA FIRMS** ⭐ | `https://firms.modaps.eosdis.nasa.gov/api/area/csv/{MAP_KEY}/{SENSOR}/{bbox}/{days}` — free MAP_KEY | VIIRS SNPP/NOAA-20/21 fire detections, NRT | Free, 10-min rate window | **Stubble-fire transport signal** (Delhi Oct–Nov differentiator) |
| IMD/IITM AQEWS + DSS | Web portals | 3-day Delhi forecast; sector/regional source split | Free web (no API); known underprediction + old inventories | Benchmark our forecast honesty; cite limitations |

## 4. Routing, geocoding, maps

| Source | Access | What | Cost | Role |
|---|---|---|---|---|
| **OpenStreetMap** (Geofabrik `asia/india` extract) | download.geofabrik.de | Delhi road graph | Free, ODbL | Base network |
| **OpenTripPlanner 2** ⭐ | Docker `opentripplanner/opentripplanner` | Multimodal itineraries (walk + bus + metro) from GTFS+OSM | Free, OSS | **Transit router** |
| **OSRM** | github Project-OSRM, Docker | Car/2W/cycle/walk routing on OSM | Free, OSS | **Road router** |
| **Photon** ⭐ | komoot/photon + Nominatim import | Search-as-you-type autocomplete, typo-tolerant, location-biased | Free, OSS | **FROM/TO UX** |
| **Protomaps PMTiles** ⭐ | `pmtiles extract --bbox` Delhi | Vector basemap, single file | Free, ODbL | **Basemap** via MapLibre |
| Mappls (MapmyIndia) | REST `route.mappls.com` | India routing + `route_eta` live traffic | Free tier (key) | Optional live-traffic ETA check |
| TomTom / HERE | REST | Traffic-aware ETA | TomTom ~2.5k non-tile/day eval; HERE ~1k/day no-card plan | Traffic fallback only |
| Delhi OTD realtime | `otd.delhi.gov.in/api/realtime/VehiclePositions.pb` (key required) | Live bus positions | Free, key-gated | Post-MVP |

## 5. Transit — Delhi-specific ⭐⭐

**otd.delhi.gov.in** (Delhi Govt Transport Dept + IIIT-Delhi), official open GTFS:

| Feed | Contents | Freshness |
|---|---|---|
| Delhi buses | 543 routes, 3,464 stops, 16,562 trips, stop_times | ~monthly |
| DMRC metro | 262 stations, 36 routes, 17,997 trips, 411k stop_times | static schedule |

This is what makes mode-aware routing *legally* possible without Google. Verified June 2024 static dumps + GTFS-rt vehicle positions behind a key.

## 6. Vehicle emissions / Delhi fleet

| Source | What | Role |
|---|---|---|
| Goel & Guttikunda, *Atm. Env.* 2015 — "Evolution of on-road vehicle exhaust emissions in Delhi" | Delhi fleet emission factors by vehicle/fuel/age | Emission-factor priors |
| CPCB/ARAI emission factor reports | BS-IV/VI factors, speed correction | Congestion-linked emissions proxy |
| TERI/IIT-Kanpur Delhi source apportionment | Sector shares (transport ~20–40% seasonal) | Sanity bounds for road-increment model |

## 7. Delhi microenvironment dose studies (the exposure model's backbone)

| Study | Key numbers |
|---|---|
| "Analysis of various transport modes…", Delhi 2021 (6 modes, RDD) | PM2.5 inhaled/km: **walk 28.2×, rickshaw 5.3× metro**; AC car & metro lowest |
| "Variation of PM2.5 & inhalation dose across transport microenvironments in Delhi" (8 modes, 7 days × 3 periods) | Bicycle highest conc. (59.8 µg/m³) & dose; AC-bus/AC-car lowest (~40); **morning peak = worst dose** |
| Near-road network meta (Karner et al.; US near-road) | NO/CO/EC decay within ~500 m; PM2.5 gradient more gradual; **75% of increment decays 5→30 m**; rush-hour peaks |
| Respiratory deposition 5-yr Delhi (Sci. Rep. 2025) | Deposition patterns by season incl. Diwali/COVID |
| Stubble contribution (WRF-Chem, ES&T; Heliyon) | Oct–Nov mean ~20%; event days **50–75%** of Delhi PM2.5; peaks late-morning→afternoon |

## 8. GRAP / regulation context

CAQM GRAP stages (revised Dec 2024): I=201–300, II=301–400, III=401–450, IV=>450. Stage III/IV → hybrid school mode, truck restrictions, construction bans. Source: caqm.nic.in schedule PDFs. Feeds "bad-day" UX + honest "what does today mean" framing.

## 9. Explicitly unavailable / rejected

- Delhi pothole/road-condition feed: **no legit API exists** — dropped.
- Google Maps/Places API: paid + terms conflicts — Photon/OSM replaces it.
- PurpleAir-type low-cost network in Delhi: sparse + paid API — not a dependency.
- Paid LLM for numbers: deterministic engine computes; LLM (if any) only narrates.
