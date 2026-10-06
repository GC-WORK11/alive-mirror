# ALive-108 — master audit + forward plan (2026-10-04)

Every mandate the owner has given, from the first prompt to the latest,
checked against code and **live AWS** (NLB :80, build `879d291f`, td:67).
✔ = verified live this pass · ◐ = shipped but has a measured gap · ✗ = not done.

## 1 · Mandate matrix

| # | Mandate (owner's words, condensed) | State | Evidence (measured, not claimed) |
|---|---|---|---|
| 1 | Route by what you inhale — "not the fastest but the safest", ms engine, C++ | ✔ | PathEngine edge-state A* over 1,070,459 edges / 819,846 nodes; 903,058 edges priced off the live raster every ≤600 s; C++ query ~70 ms; rows carry `engine_dose_ug` = exact minimized objective |
| 2 | Real-time AQI/PM2.5 + other species | ✔ | `/aqi` serves pm25+σ band + pm10/no2/o3/co/so2/nh3/dust/aod/us_aqi; `/grid` 484 cells; field age on `/health` |
| 3 | Legal, sane roads — no unsafe/wrong paths | ✔ | 230 OSM turn bans + 3,428 access overrides in A*; connectivity-screened snap; bike speed cap (b548bdc) |
| 4 | "Decision LLM or API" | ◐ (deliberate) | Decision is physics (dose × time × safety tier) in `decide.rank` + engine, explainable per row. No LLM: a keyless free LLM can't beat a priced objective and would add latency/cost. Pitch answer, not a gap |
| 5 | Every house / landmark, home-to-home, ms | ◐ | 97,447-entry corpus (16,949 address rows), 124,311-row bundled gazetteer (instant offline T0 <5 ms), server p50 ~1 ms engine. Probe battery 174 real queries: live 92.5% → 98.3% after leg-4. Remaining: platform rows outrank landmarks (`aiims`, `lodhi garden`); house-numbers only where OSM has them |
| 6 | What is Delhi — NCT + Haryana/UP borders, Ghaziabad | ✔ | Field bbox 76.8–77.9°E × 28.2–28.95°N; graph merges northern+central zones (Ghaziabad band 514 → 700k nodes); NCR choropleth now serves 29 rows (16 district cells + 13 Delhi sub-areas — `/v2/districts`, 2026-10-06); Gurugram→Ghaziabad plans live |
| 7 | Cigarettes OFF by default, settings toggle | ✔ | `settings.show_cig=false`; µg surfaces default; admin never shows per-user cigarettes |
| 8 | PUC-certificate emissions, not fleet guesses | ✔ | VehicleSheet `puc` step (BS + CO%/HC/λ by fuel) → `emissions._puc_calib` → `puc_calibrated:true` on the wire |
| 9 | Admin = Delhi's emission + exposure overview, light theme, official CPCB colours | ✔ | Board: districts strip, engine row, timing panel, corridors w/ CO₂/100m, day bars, species, sources. Dark landing replaced by light `/city` |
| 10 | Aggregates-only privacy ("we had 1 journey") | ✔ | Raw coords never stored (cells only), k≥3 corridors, banned-key test scans every admin endpoint; legacy per-device rows gone |
| 11 | Per-user dose/emission ledger | ✔ | on-device ledger + `GET/DELETE /v2/ledger` (token-keyed summaries) |
| 12 | Live community map from trips | ✔ | donations → Bayesian traverse update + corridors; dedupe on retries |
| 13 | Forecast / leave-later | ✔ (fixed today) | Semi-Lagrangian advection; two anchor bugs found + fixed (impossible 0.0 hours) |
| 14 | Android release app, tested like a user | ◐ | Release APK 135.8 MB, NLB baked, forensic drive 51 PASS/0 crash. **Unverified: TTS audio + gfxinfo jank** — no KVM on any box I control |
| 15 | iOS shown on demo day | ◐ | Builds + runs; upstream MapLibre-on-vGPU sim crash ~1/45 interactions (sim only). Demo: Android live, iOS recorded |
| 16 | No fake numbers / honest copy | ✔ | Old claims-audit ✗ list (10 items) re-verified closed; today removed the last "actually breathe" overclaims, "measured streets" → "commute-mapped" |
| 17 | $0 this month | ✔ | Cost Explorer Oct 1–4: **$0.00** (credits); FARGATE_SPOT; run-rate ~$46–50/mo after credits |
| 18 | Benchmarks real | ✔ | server stopwatch on `/admin/api/timing`: /health 6 ms, /districts cached p50≤5 ms; plan ~5.5 s / 20+ options (public OSRM dominates) |

## 2 · Bugs found + fixed in this pass (all live)

1. `/admin/api` **500** in prod — `corridors()` read `o["km"]` on pre-km snapshots → `_obs_km/_obs_cells` (879d291, regression test)
2. Forecast anchor at advected origin vs query point → impossible 0.0 hours (2b1eb3e)
3. Overshooting anchor → model degrade for future hours, live truth at hour 0 (9be494f, 0aa2624)
4. Deploy script race: `services-stable` returned before the forced rollout and evicted the fresh target → gated on PRIMARY `rolloutState` (76e46b4)
5. Copy overclaims (eacc413)

## 3 · Honest gaps, ranked by what a judge/user would hit first

| Rank | Gap | Why it matters | Plan | Cost |
|---|---|---|---|---|
| 1 | Plan latency ~5.5 s | judge's first tap | engine-first paint: stream engine rows (~0.3 s) before OSRM/transit arms land; client renders progressively | $0 |
| 2 | Platform/stop rows outrank landmarks | "AIIMS" → a platform | demote transit-platform kinds when a same-name landmark/POI exists (location agent, in flight) | $0 |
| 3 | TTS + jank unmeasured | user-mode nav | needs a KVM Linux box; physical Android phone on demo day covers it | $0 |
| 4 | `/decide` 10 s (legacy v1) | unused by app | leave or route through v2 planner | $0 |
| 5 | ~~Public OSRM dependency~~ CLOSED | shipped | self-hosted `osrm-routed` sidecar lives in the task today (`OSRM_URL=127.0.0.1:5000`, MLD over 4.4M NCR edges); public demo is the flagged fallback | done |
| 6 | Release signing | Play upload | keystore on owner | $0 |

## 4 · One-line breakthrough (for the pitch)

> Type from and to: in milliseconds a C++ engine searches Delhi's 1.07 million
> road edges, each priced by the smoke on it this minute, and gives you the
> route your lungs pay least for, with an honest uncertainty band.

## 5 · Next moves (in order)

1. Engine-first progressive plan response (biggest perceived-speed win)
2. Land the location agent's platform-demotion + battery fixes, then re-run the live battery
3. Routing agent: least-smoke vs fastest quality stats on 40 real ODs (% rows saving ≥10% dose for ≤15% time; detour ratio) for the pitch slide
4. Fresh APK + base/v2 → main merge
5. Demo-morning checklist: Spot → on-demand flip, warm the task 10 min before, physical Android phone
