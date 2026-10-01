# 06 · MVP, Rejected Features, Demo Flow, Roadmap

## 1. The exact MVP

**One screen.** FROM → TO → 2–4 itineraries ranked by estimated inhaled PM2.5 dose.

In scope:
- Photon autocomplete (Delhi-biased, typo-tolerant) + map pin-drop fallback
- Itineraries across modes: drive/2W (OSRM), transit walk+bus+metro (OTP2+GTFS), walk
- Per-itinerary: dose band (µg, ±), minutes, ₹ estimate, "why" (top 2–3 factors)
- Field visualization: subtle grid overlay + station markers w/ freshness
- Departure-time curve for the chosen OD (climatology + today)
- `/now` strip: city PM2.5 band, GRAP stage, fire outlook, data freshness
- Provenance page: every source + timestamp + which numbers are modeled vs measured
- Deployed on AWS (eligibility ✔) + 3-min recorded demo video

Out of scope for MVP (each failed the tests):
- ❌ Accounts/login — adds burden, no exposure reduction (ledger works anonymously)
- ❌ Turn-by-turn navigation — Google Maps already wins; we're the *decision* layer
- ❌ Notifications/subscriptions — pull product, not push
- ❌ All-pollutant dose — PM2.5 is the defensible dose species in Delhi literature; NO2/PM10 shown as field context only
- ❌ City emissions dashboard — different claim, can't validate
- ❌ Chat interface — explicitly banned by the brief and by good sense
- ❌ Real-time bus positions — key-gated + time cost; static GTFS suffices for demo week
- ❌ Indoor air — different physics
- ❌ Wearables/hardware — zero-hardware constraint

## 2. Demo flow (3 minutes, recorded — judges see only this)

| t | Beat |
|---|---|
| 0:00–0:15 | Problem in one line: "Delhi AQI is 380. You still have to get to work." |
| 0:15–0:40 | Type "Kashmere Gate → Hauz Khas": autocomplete instant, real Delhi places |
| 0:40–1:30 | 3 itineraries appear: Drive 52 min / 2W 47 min / Metro+walk 38 min — with dose bands. Metro wins dose by ~5× *and* is fastest. (Real corridor where the contrast is sharp.) |
| 1:30–2:00 | Tap metro itinerary: dose-by-leg breakdown, near-road bumps on the walk legs, uncertainty band, "typical for 9 AM Tuesday" note |
| 2:00–2:25 | Departure slider: dose curve dips at 11 AM; "leave 2 h later, ~25% less dose" — climatology-labeled honestly |
| 2:25–2:45 | `/now` strip: GRAP stage today, Punjab fire count yesterday, station freshness — the Delhi-specific brain |
| 2:45–3:00 | Provenance page flash: 46 stations, sources, timestamps, p95 latency — "every number traces somewhere real" |

**Backup corridor picks** (test all live, pick the sharpest): Rohini→Connaught Place, Anand Vihar→Gurugram, Dwarka→Noida. Record whichever shows the biggest honest dose spread that morning.

## 3. Phased build plan (one session ≈ one phase)

| Phase | Deliverable | Exit check |
|---|---|---|
| **0 · Proof** (done — this package) | Research + verified sources | Every API verified reachable/free |
| **1 · Data foundation** | docker-compose: PostGIS+Timescale, Redis, OSRM(Delhi), OTP2(Delhi OSM+GTFS), Photon(Delhi); CPCB+OpenMeteo+FIRMS ingest; OpenAQ S3 backfill | `psql` shows stations + hourly obs flowing; OSRM/OTP2 answer Delhi queries |
| **2 · Core model** | field-builder (kriging+traffic bump) → `field_surface`; exposure scorer library w/ mode factors + σ | LOSO-CV numbers committed; scorer returns bands |
| **3 · Route engine** | `/route` endpoint: candidate itineraries → dose scoring → Pareto + explanation | Real OD pairs return sensible ranked itineraries <800 ms |
| **4 · Product** | PWA: search→compare→detail screens, map+tiles, `/now`, provenance | Judge-usable on phone |
| **5 · Validation** | Back-test tables, latency log, failure-mode flags | /meta/sources shows real metrics |
| **6 · Demo cut** | Trim to the 3-min flow; record video; freeze a demo snapshot of field | Video shows real data with timestamps |
| **7 · Post-hackathon** | Kalman fusion, GNN field, bus GTFS-rt, personal climatology, Android/iOS shells | — |

## 4. Hackathon strategy mapping (judging criteria → artifact)

| Judge criterion | What we show |
|---|---|
| Idea & impact | Real dose numbers on a real commute; impact ledger honestly scoped |
| Built on AWS | Deployed architecture + diagram; S3/CloudFront/App Runner/RDS live |
| Design & usability | One-screen product a non-team member can use with zero explanation |
| Execution | Working E2E on live CPCB data with freshness visible — not a mockup |
| Demo video | The 3-min flow above |

## 5. Post-hackathon expansion (honest path, not promises)

- **Kalman per-station fusion** — learns each DPCC station's bias vs the field (siting issues are documented; reliability weights become learned, not guessed)
- **Bus GTFS-rt** — live bus positions → real "take the 534 or walk" calls
- **Personal climatology** — "your commute corridor is worst at 8–9 AM; shift it"
- **GNN/physics-ML field** — once the historical corpus is months deep
- **School mode** — parent-facing "safest way to school today" on GRAP days
- **Open the model** — publish the field API for other Delhi builders (the moat is the calibrated corpus, not the code)
