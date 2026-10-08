# e2e-prod-check — last independent audit before owner's hands

Date: 2026-10-08 ~04:19–04:30 UTC (09:49–10:00 IST). Target: `http://65.2.28.40` (prod, build `90766e25` per `/health` + landing footer `BUILD 90766E25`). Audit was read-only; every row below was hit live, no local mocks. Tree HEAD at audit: `b1421d0`.

## Verdict: READY — everything the owner will touch works; 2 minor degradations, both honest.

| # | Check | Result | Evidence |
|---|-------|--------|----------|
| 1 | `GET /health` | **PASS** | 200 in 0.48s. `build_sha=90766e25`, `engine=alive_core`, routing loaded (1,070,459 edges / 903,058 priced), `field_age_s=760` (<900s budget, `stale=false`), stations 53 up (waqi+dpcc both ok), fires 115 live (age 2,589s < 22,500 stale_after), transit bus+metro compiled, wind known |
| 2 | `GET /` (v8 landing) | **PASS** | 200 `text/html` 131KB. Served bytes == git blob `90766e25` exactly (`diff` clean). Browser-driven on prod: boot strip ran, breathing field painted edge-to-edge, live numeral rendered **49.1 µg/m³** (PM2.5·SATISFACTORY), sticky chrome live ticker "MAP 3 MIN FRESH", day-recorded bars, 4 district chips live-filled (SW Delhi 146 / Rohtak 131 / Gurugram 118 / Jhajjar 106), footer `BUILD 90766E25`. `dead-page` absent; `check_inline_scripts` clean at deployed sha (my earlier "syntax error" was my own regex eating a `<script>` mention inside a CSS comment — real script parses fine) |
| 3 | `GET /city` | **PASS** | 200, 89KB, title "Delhi NCR air, district by district", district/station/map/fresh markers present |
| 4 | `GET /community` | **PASS** | 200, 21KB, "everyone's trips, merged", privacy/ledger content present |
| 5 | `GET /admin` | **PASS** | 200, 165KB — engine-room gate serves (sign-in field, no auth bypass) |
| 6 | `GET /aqi` geo'd | **PASS** | 200 0.47s @CP: `pm25=60.7`, `nearest_station_km=1.6`, `beyond_field_edge=false`, 53 station readings listed w/ names, field age 780s, calibration (MAE 8.8µg leave-one-out) + typical (median 113.1, vs_now −46.3%) blocks intact |
| 7 | `GET /grid` | **PASS** | 200 — 99-cell GeoJSON FeatureCollection, per-cell `pm25` + `conf` |
| 8 | `GET /v2/city` | **PASS** | 200 0.63s — why drivers (stagnation primary, trend secondary), `pm25_stats` n=25 mean 49.5, 12h next_hours, species block, breath band |
| 9 | `GET /v2/districts` | **PASS** | 200 — 29 districts w/ live pm25/aqi/category/color, CPCB band table, `geojson` + `subdistrict_geojson` links, `field_age_s=795` |
| 10 | `GET /v2/skill` | **PASS** | 200 — warm 0.54s (<1.5s target), cold 0.70s. `pairs=436`, h0 MAE 3.4µg / band-hit 90.9%, all horizons `ok`, self-graded basis note present |
| 11 | `GET /depart` | **PASS** | 200 — 24 hourly slots w/ dose+avg_conc, best +5h (7.1µg vs now 7.3µg, `pct_less_vs_now=3`), worst +22h (17µg), forecast provenance + live_anchor block present. NOTE: requires `from_lat/from_lon` (lat/lon → 422, correct rejection) |
| 12 | `GET /v2/reverse` | **PASS** *(degraded path)* | 200 — "near Baba Kharak Singh Marg" 19.7m, `source:"gazetteer"`. Amazon Location is down (key unset, see #18) and the fallback answers honestly |
| 13 | `GET /search` ×4 | **PASS** | All 200: `connaught`→Connaught Place first (8 rows, 1.7s); `ashok nagar shadara`→Ashok Nagar **Shahdara** first — typo-tolerant (0.95s); `bakery near mandir`→mixed mandirs+bakeries incl `kind:bakery` — raw-phrase works (0.87s); `karol bagh`→metro stn + blocks (0.84s) |
| 14 | `GET /today` | **PASS** | 200 — 24h IST climatology curve, `openaq-s3-climatology` source labelled |
| 15 | `GET /v2/why` | **PASS** | 200 — drivers w/ evidence, 29 recorded field builds in history, `cannot_tell:[]`, honesty contract intact |
| 16 | `POST /v2/plan` ×3 real ODs | **PASS** | CP→IndiaGate: **23 options** 0.41s. Dwarka→Noida: **22** 6.5s. Rohini→Okhla: **24** 6.6s. Every response: modes span car/car_open/bike/auto/bus/metro+walk/cycle/walk; exactly 1 `recommended` + `reason_line`; `tag` marks "lightest for you"/"lightest for Delhi"; dose `lo/mid/hi` w/ `confidence`+`basis`; emissions w/ non-exhaust separated + PUC flag; **zero `_t1_pos` or merge-scratch keys on any wire**; `vehicle_requested` echo + `degraded` contract present; dose sanity: car@CP→IG mid 2.1µg @ conc 33.4 = VE≈0.6m³/h, plausible |
| 17 | Edge honesty | **PASS** | Mumbai OD → `{"options":[],"error":"outside service area…","code":"outside_service_area"}`; `/aqi` @lon 79 → `beyond_field_edge:true, nearest_station_km:167.4`; unknown path → 404; `/v2/aqi` → 404 (correct); `/observe` GET → 405; **no 5xx observed anywhere** |
| 18 | `ALIVE_LOCATION_KEY` | **DEGRADED** | `/health` `sources.location.up=false, key:"unset"` — Amazon Location reverse-geocode not configured on prod. `/v2/reverse` still 200s via gazetteer fallback and says so. Owner-visible: locality names stay gazetteer-grade |
| 19 | `/favicon.ico` | **DEGRADED** *(nit)* | 404. Landing declares a `data:` SVG icon so browsers use it; the bare URL still 404s — cosmetic, owner may notice in devtools network tab |
| 20 | Static/geojson assets | **PASS** | `/app-hero-708.png` 200 (198KB), `/app-choose-strip-848.png` 200 (302KB), `/ncr.geojson` 200 `application/geo+json`, `/delhi_subdistricts.geojson` 200, `/v2-light.json` 200 (offline-pack style contract intact) |

## Freshness
- Field age at audit: **760–831s**, `stale=false`, next refresh in ~90–140s (TTL 900s) — inside the <15min budget every call.
- Station readings: 53/53 live, waqi+dpcc feeds both `ok` (no DPCC stall this hour).
- Forecast (depart): 48 aq+met points, age 831s < 10,800s max.
- Fires: 115 belt-read, age ~2.6ks < 22.5ks stale_after, modifier 1.14 consistent across `/aqi`+`/v2/why`.

## Number honesty (cross-check)
| Surface | PM2.5 figure | Basis |
|---|---|---|
| `/aqi` @Connaught Place | 60.7 µg/m³ | point read (breathing-zone adjusted) |
| `/grid` cells near CP | ~55–72 | field cells |
| `/v2/city` mean | 49.5 | NCR 25-pt lattice |
| landing numeral | 49.1 | NCR-wide avg — same basis as `/v2/city`, ~2min refresh delta |
| `/v2/districts` Delhi NCT | 56.1 | district mean |
| landing district chips | 146/131/118/106 aqi | vs API 145/133/118/108 — 1–2pt refresh deltas only |

All inside one coherent 45–65 ballpark — nothing contradicts anything else. `typical.vs_now_pct` −46% honest (Oct median 113 vs live ~50: the field really did clear this morning, `/v2/why` trend driver shows 76.4→49.0 over 5.9h recorded).

## Fixes
None needed. The only web-side nit is the bare `/favicon.ico` 404, and the page already serves an inline `data:` favicon — not a bug worth a tree edit mid-freeze.

## What the owner will see that isn't perfect
1. `location` source down in `/health` — reverse-geocode is gazetteer-grade ("near Baba Kharak Singh Marg" style, still named and sane) until `ALIVE_LOCATION_KEY` is set.
2. `/favicon.ico` 404 in devtools network.
3. `/depart` shows a near-flat morning (dose ~7µg all slots until +9h) — that's the forecast being flat, not a bug; the +22h evening spike (17µg) proves the curve moves.
