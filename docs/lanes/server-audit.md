# Lane report — server/backend audit (read-only)

Scope: full `server/` tree (FastAPI `main.py`, `v2/*`, `airfield.py`, `forecast.py`,
`exposure.py`, `emissions.py`, `routegraph.py`, `community.py`, `ingest_*.py`,
`admin_agg.py`, `observability.py`, `middleware.py`, `agg_ddb.py`, `fires.py`,
`history*.py`, `skill.py`, `rollup_lambda.py`, `alive_core_ref.py`,
`server/core/bindings.cpp`) + `Bridge/contract.ts`. Live probes against prod
(`alive108-2699c171ddded465.elb.ap-south-1.amazonaws.com`) were GET-only.

**Verdict: the thing that would hurt most on stage is the deploy lag — prod
runs `ce01ec5c`, 20 commits behind `base/v2` HEAD `823323e`. The missing
commits include the failed-fetch retry gates (`77941dc`): on prod, a dead
upstream (CAMS / Open-Meteo / FIRMS) still re-runs the whole ~50-request
fetch inside *every* request — the exact stall that fix was built to kill.
Demo-day rebuild is the single highest-value action in this lane.**
Everything else checks out: the privacy pipeline, k≥3 corridor gate, dose
contracts and fallback labelling are real and verified live — no fabricated
data path found anywhere in the tree.

## Findings

| severity | category | finding | evidence | why a judge/user cares |
|---|---|---|---|---|
| high | JUDGE-RISK | Prod is 20 commits behind repo truth; retry-cooldown + city overhaul not deployed | `GET /health` → `build_sha: ce01ec5c`; `git rev-list ce01ec5c..823323e` = 20 commits; `git diff` shows `FETCH_RETRY_S` (airfield.py:45), `RETRY_S` (fires.py:36), `RETRY_S` (forecast.py:58) all absent in prod build | Without `77941dc` a dead upstream re-pays the full grid fetch per request — an upstream blip during judging stalls the API at the worst moment. Missing `6c36219` also means judges see the pre-overhaul city/community surface |
| med | JUDGE-RISK | Amazon Location unset → T2 search tier + paid-ETA comparisons disabled | `GET /health` → `sources.location: {up:false, key:unset}`; `v2/plan.py` `_aws_rows()` | The "runs on AWS services" story loses its paid tier on live demo; `/v2/search` answers `t2_status: "disabled"` honestly but a judge who asks may read it as incomplete |
| med | JUDGE-RISK | Engine rows run freeflow duration model — no congestion feed; engine dose can exceed OSRM dose on the same OD | `v2/plan.py:1886-1891` (`duration_model:"estimated"`, `duration_basis:"freeflow"`); `Bridge/contract.ts:447-449` documents the caveat; `docs/plan/handoff.md` 40-OD re-run: "n worse-dose rows — all duration-model artifact, 0 genuinely-smokier corridors" | A judge eyeballing the option table can catch a least-inhalation route that is *slower and dirtier* than the OSRM row; the flags say why, but it needs a rehearsed answer, not discovery on stage |
| med | BUG | `/v2/trip` donations are not geographically bounded to NCR | `v2/trip.py:230-281`: cells minted for any in-range lat/lon (only `_parse` finite/±90/±180 checks); `record_trip` into day aggregates is unconditional; outside-NCR endpoints just return `origin_area=None` | A buggy or hostile client anywhere on Earth inflates "how Delhi moves" totals and can mint non-NCR corridor cells (k≥3 caps anonymity, not geography). Trip `_BOUNDS` cap magnitude, not location |
| med | NIT | Rate limiter keys buckets on client-supplied `X-Forwarded-For[0]` | `middleware.py:80-82` — `fwd.split(",")[0]` | Behind the NLB the first XFF hop is attacker-controlled; rotating the header defeats per-IP budgets. The balancer-appended (rightmost) address is the honest key |
| low | NIT | `assert` used as runtime tripwires for the k≥3 contract | `admin_agg.py:514,736`; `observability.py:458` | `python -O` strips asserts and the fail-loud layer silently vanishes. Dockerfile:122 runs plain `python -m uvicorn` today, so it's live — but one flag flip and the tripwire is gone. The actual mechanism (the `_publishable_cells` filter, `v2/store.py:198`) is real code, unaffected |
| low | NIT | `engine:"alive_core-path"` emitted by *both* path-engine twins | `core/bindings.cpp:173` and `routegraph.py:721` emit the identical literal; `contract.ts:445` declares it as engine-row provenance | Wire can't distinguish C++ vs Python twin per-response (parity-tested so honest); if a judge asks "prove the C++ engine priced that route", only `/health.engine` answers — not the route body |
| low | JUDGE-RISK | `/v2/ledger` keeps `?token=` back-compat | `v2/ledger.py:19-28` documents it; Dockerfile:117-122 runs uvicorn `--no-access-log` so the server-log leak is already closed | Residual: token lands in browser history + Referer headers for shipped clients. X-Device-Token header path exists and is preferred — retired clients aside, new traffic should never see `?token=` |
| low | JUDGE-RISK | Fires modifier is a city-wide scalar on a normalized baseline | `fires.py:51-52` (`BASELINE_FIRES_48H=160`), `fires.py:206-219` NW-quadrant gate → live wire shows `wind_deg:137 → modifier 1.08` (off-quadrant downscale ×0.3 working as coded) | "Why does my street breathe more than the station reads when the wind isn't carrying smoke?" — the answer is in the wire (`smoke_modifier`, `wind_deg`, `belt_fires`) but the scalar-over-city simplification is the attack surface |
| low | JUDGE-RISK | `/v2/skill` self-grades honestly: forecast MAE 4.0→26.4 µg/m³ h0→h4, band-hit 89→44% | `GET /v2/skill` → `pairs:219`, per-horizon table; `skill.py:30-34` earliest-capture rule + `MIN_PAIRS` thin floor | A hostile judge can quote "your 4-hour forecast is wrong by half a band" — but publishing the self-grade is the honesty play; the counter is that h+4 MAE ≈ station-vs-station disagreement anyway. Have it ready |
| low | NIT | Donation dedupe signature can collapse two genuinely distinct trips | `v2/trip.py:52-60` — key = token + first/last cell + distance + duration, 24h TTL | Two real trips sharing all four fields within 24h get counted once. Rare; only bites replay-style or templated traffic |

## Clean bill — checked and genuinely real

- **Dose math** — `exposure.dose` → `Σc·ME·VE·t` contract verified; `alive_core_ref.integrate_dose` + C++ kernel exist with 1e-9 parity tests; `/health` reports `engine:"alive_core"` live.
- **Privacy pipeline** — `v2/trip.py:178-235`: 300 m endpoint trim → 100 m thin → 4-dp round → h3-res-8 cells; raw trajectory discarded, never stored/logged; token sha256-hashed *before* touching any store.
- **k≥3 enforcement** — real mechanism inside `v2/store.py:198 _publishable_cells` (locked, under-key filter), re-asserted at `admin_agg.py:514,736`; live `/v2/city` corridors all carry `devices ≥ 3` (observed 3–10), `cells_tracked:54` vs `publishable_corridors:12` proves the gate filters.
- **Banned keys** — `observability.py:80-120`: allowlisted log fields only, bodies/query-string never read, `>2dp` decimals truncated to ~1 km; `assert` tripwire on emit; prod runs `--no-access-log`.
- **Ledger** — `agg_ddb.py:508+ DDBDeviceLedger`: rows keyed `ledger#<hash>`, TTL 90d, sanitized summary fields only (no cells/coords); `/v2/ledger DELETE` wipes rows + meta counter; `backend` flag distinguishes memory/DDB.
- **Honest degrade** — every probed failure path returns an honest body: `/v2/plan` errors → `options:[] + error + code:"outside_service_area"` + `degraded:[arms]` when arms time out (`plan.py:2020-2024`); `/v2/reach` refuses to serve unpriced field ("would flood every edge to the cap at cost 0", `reach.py:172-174`); `/v2/day` cold forecast → `hours:[] + error`; `/v2/skill` → `{"status":"thin"}` under `MIN_PAIRS`.
- **No stale-as-fresh** — every fallback labels itself on the wire: `EMIT_BASIS` "fallback static table" + `engine:"static-table fallback"` (`plan.py:185,248`); airfield `serving: snapshot|live|none` + `stale` flag at 45 min; fires feed has own `stale_after_s` TTL bar; GRAP block is `indicative_stage` with "not the official CAQM declaration" note (`/aqi` wire).
- **Live wire verified** — `/health`: 1,070,459 edges loaded / 903,058 priced, transit `real_feeds:{metro:true,bus:true}`, stations `waqi+dpcc` ok, history = OpenAQ archive (125 stations, built 2026-10-01); `/v2/city`: 54 stations blended, typical climatology vs_now −48.3%, breath band basis disclosed; `/aqi`: `pm25_lo/hi` from krige σ × smoke_modifier, `us_aqi` computed over served species (not CAMS's own cell — `us_aqi_model` kept for provenance), `nearest_sample_km` disclosed; `/v2/why`: stagnation driver with ventilation computed from live BLH+wind; `/v2/reach`: 403,204 settled edges, `frontier_budget_ug 9.9999 ≤ 10`, partial-serve disclosed; `/v2/day`: real windows + generated decisions, band-blend basis string; `/v2/districts`: 29 districts, `partial_field_coverage` flagged per row; `/v2/skill`: 219 real recorded-vs-served pairs.
- **Admin surface** — `_admin_guard` (`main.py:1547-1565`): Bearer token when `ALIVE_ADMIN_TOKEN` set, loopback-only when unset; live probe answers `"admin token required"` (401).
- **DPCC + fires feeds live** — `stations_status:{waqi:"ok",dpcc:"ok"}`, 54 readings blended; fires `status:"live"`, `source:"firms-public-csv"`, 67 fires / 15 belt, age 4.1 h < 6.25 h TTL, NW-wind gate verified against `wind_deg:137`.
- **Contract drift** — `Bridge/contract.ts` declares every emitted key including the honesty flags (`reaches_destination`, `degraded`, `t2_status`, `us_aqi_model`, `duration_basis`); `server/tests/test_contract_sync.py` enforces it server-side.
- **Ingest pipeline** — `rollup_lambda.py` documents EventBridge schedules are disabled stubs and `rollup_tick` is the real driver on the single-task ECS deploy (status honest, not hidden).
- **C++/Python twins** — `alive_core_ref.py` is the parity oracle AND documented fallback; `get_search_index`/`get_field_view` prefer C++ when importable; parity tests exist; `get_field_view` contract documented at `alive_core_ref.py:563-584`.

## Notes for the demo-day checklist

1. **Rebuild/redeploy to `823323e` before Oct 8.** The retry-gate fix is the
   only prod gap that can turn a routine upstream blip into a stage failure.
2. Amazon Location key: either set it or rehearse "T2 is the paid tier —
   T1's local engine already answers; location shows `disabled`" in one line.
3. For `/v2/skill`, lead with the self-grade *before* a judge finds it —
   publishing your own error bars is the strongest honesty move in the deck.
4. Engine-row `duration_basis:"freeflow"` is disclosable in the UI — if the
   demo explains "graph speeds, no live congestion feed yet" unprompted,
   the worse-dose-rows question never lands.

Lane: server/backend audit · repo `base/v2` @ 823323e · prod build ce01ec5c ·
probed 2026-10-07 ~00:26-00:30 UTC
