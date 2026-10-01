# 02 · Competitive Landscape

Verdicts from checking what actually ships today, not claims.

## 1. What already exists

| Product / Project | What it does | Data | Live? | Delhi-usable? | Limits |
|---|---|---|---|---|---|
| **Google Air Quality API** (BreezoMeter→Google) | 500 m AQ field, hourly + 4-day forecast + 30-day history, 70+ indexes incl. `ind_cpcb` | Stations + models + satellite | Yes | Data yes (paid) | It's a *data layer*, not a routing product; Google Maps itself doesn't offer exposure routing in India |
| **Ambee Clean Air Routing** | B2B API: routes ranked by pollution+pollen exposure | Own AQ models + pollen | Yes | India yes | B2B API, no consumer app, no Delhi transit modes, paid |
| **LEAP academic tool** (TRR, Mar 2026 — closest prior art) | Web app: shortest/fastest/least-exposure/least-energy routes | GraphHopper + Mapbox traffic + WAQI stations | Research demo | **Built on Delhi** | Car-road only; WAQI station-echo (no fused field); no modes; no dose; not a maintained product |
| **Breeze Technologies "HealthyPlaces"** | Walking routes by least pollution (EU) | Own sensors + city data | App | No (Europe) | Walk-only, sensor-network-dependent |
| **IQAir / AirNow / SAFAR apps** | AQI display, forecasts, advisories | Stations + models | Yes | Display only | Tell you air is bad; zero movement decisions |
| **aqi.in / Indian AQI apps** | Station list, city AQI, trends | CPCB mirrors | Yes | Display only | Same — information, not decisions |
| **Delhi govt portals** (CPCB, DSS, CAQM) | Bulletins, forecasts, GRAP orders | Official | Yes | Reference | Not consumer tooling |

## 2. What's already solved (don't rebuild)

- **AQI display**: solved a dozen times. We never show a bare AQI page.
- **Station lookup**: CPCB + OpenAQ already publish — we consume, not replicate.
- **Generic routing**: OSRM/OTP2 are excellent — we add exposure cost, not a new router.
- **City-level forecasting**: IITM AQEWS does 3-day Delhi forecasts (~80% hit rate on high-pollution days per CEEW study). We don't compete with it; we cite and contextualize.

## 3. What's genuinely open — our gap

Nobody ships a **consumer, multimodal, dose-aware trip engine for Delhi**. Specifically unbuilt:

1. **Mode-aware exposure routing** — using the measured fact that metro/AC-car exposure per km is a fraction of rickshaw/walk. LEAP re-routes *roads*; nobody re-routes *modes*. Delhi's 262-station metro + 543-route bus GTFS is sitting there unused for this.
2. **Inhaled-dose comparison** (concentration × ventilation × time), not just mean-concentration-along-path. A slower metro ride on a higher-ambient corridor can still win on dose.
3. **Departure-time decisions** on a fused field: morning-peak dose vs mid-day vs evening, with stubble-fire days flagged.
4. **Uncertainty as a first-class output** — everyone else shows point estimates; 65% of Delhi is unmonitored, so honesty is a differentiator.
5. **Bad-day operational layer**: GRAP-stage-aware "should my kid take the school bus or metro" decisions — named in the track brief, shipped by nobody.

## 4. Novelty statement (honest)

- Established: pollution-aware road re-routing (LEAP, Ambee), AQ fields (Google), station display (all).
- Partially solved: multimodal transit routing (OTP2 is generic — nobody feeds it Delhi GTFS + exposure weighting).
- **Underexplored combination — our position**: Delhi CAAQMS fusion + Delhi GTFS multimodal routing + published Delhi mode-dose factors + stubble-fire signal → a single FROM→TO decision product. We claim *combination* novelty and *depth* novelty (Delhi-specific calibration), not "first ever clean routing" — LEAP proves the concept is feasible; we prove it can be a product.

## 5. What we should NOT copy

- Ambee's B2B API shape — we're consumer.
- LEAP's WAQI station-echo — circular and license-risky; we fuse CPCB directly.
- IQAir's index-first UX — users can't act on an index; we surface *decisions*.
