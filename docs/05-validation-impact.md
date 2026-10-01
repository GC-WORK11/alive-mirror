# 05 · Validation & Impact Frameworks

Rule: if we can't validate it, we label it; if we can't label it honestly, we cut it.

## 1. Field model validation

| Test | Method | Pass bar |
|---|---|---|
| Spatial skill | Leave-one-station-out CV on current field | RMSE ≤ IDW baseline −15%; report actual |
| Temporal skill | Back-test vs OpenAQ archive: predict hour t from t−1 field + covariates | Beat persistence baseline on RMSE |
| Zone coverage | Split stations by ward/zone; check per-zone bias | No zone systematically off >2× mean error |
| Rush vs off-peak | Validate separately on 8–10 AM and 2–4 PM hours | Report both; morning may be worse — say so |
| Weekday/weekend | Separate error tables | Report |
| Event days | Diwali + severe GRAP days from archive | Field must degrade *gracefully* (σ↑), not lie |
| Freshness | Ingest audit: % stations <90 min old at query time | ≥80% or surface stale badge |

## 2. Dose model validation

- **Factor provenance**: every mode factor cites its Delhi study; we expose the table in-app.
- **Sanity ordering**: expected ranking metro ≤ AC car < bus < rickshaw < walk < bicycle on dose/km must hold — if the model produces anything else, it's broken, not clever.
- **Sensitivity**: ventilation rate ±30% → dose band width; publish sensitivity in docs.
- **Cross-check**: model dose on a known commute vs the studies' measured trip doses — same order of magnitude or we don't ship the number.

## 3. System metrics

- p50/p95 latency per endpoint (logged, shown on /meta/sources)
- Route candidates: median itineraries returned, dedupe rate
- Cache hit rate for /route
- Uptime of field freshness (from ingest_audit)

## 4. Honest impact model

Three scopes, never merged:

| Scope | What we compute | What we claim |
|---|---|---|
| **Trip** | dose(chosen) − dose(best alternative) | "you avoided ≈X µg PM2.5 est." |
| **Personal ledger** | Σ trip deltas over logged trips | "your estimated avoided dose this month" |
| **Aggregate** | Σ over all logged trips | "N users avoided ≈Y µg est. total" |

**Explicit non-claims**: city AQI didn't drop because users rerouted; we do not claim emissions reduction unless we separately model tailpipe-avoided (V2, clearly labeled). Personal exposure reduction ≠ pollution reduction — one line on every ledger screen.

## 5. Failure modes & responses

| Failure | Detection | Response |
|---|---|---|
| CPCB feed down | ingest_audit age | Serve last-good field + "data N h old" badge |
| >30% stations stale | freshness check | Degrade: widen σ, show "low confidence" |
| Router down | health check | Remaining router only + note |
| Extreme event (Diwali spike) | value guards | Field updates; σ widens; advisory text, no fake precision |
| Photon misses a place | empty results | Fallback "choose on map" pin-drop |
| GTFS stale >60 days | feed check | Metro routing still fine (schedule stable); bus warns |

## 6. Demo-day risk register (Oct 8–11)

- CPCB hourly feed occasionally lags → pre-warm cache + archived fallback tile for the demo corridor.
- Conference Wi-Fi → full stack also runs locally; demo works on localhost + deployed URL both.
- Live video recorded in advance per judging rules (3-min recorded, no live demo) — so record the *real system* the day before with cached-real data visible in the provenance panel.
