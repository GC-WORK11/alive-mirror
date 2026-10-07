# codebase-server report — endpoint census, fake-hunt, dead-code verify, consistency

Split A (server + web) of the code-truth pass. Base: `b563da2` on `base/v2`.
Prod probed: `http://alive108-2699c171ddded465.elb.ap-south-1.amazonaws.com`
(running build `f9ea5ae8` — one commit behind HEAD, admin-auth `b563da2` not
yet deployed). GET-only; POST routes probed via GET → 405 (registered, body
not exercised). All curls 2026-10-07 ~09:25 UTC.

Built on, did not re-litigate: `deadcode-report.md` (b7b951e),
`codebase-audit-report.md`, `pentest-report.md`.

## Verdict up front

- **64 routes** enumerated (62 decorators + `/metrics` + FastAPI defaults).
  Every reachable GET serves **real data**; every 4xx observed is honest
  (missing params / admin gate / absent tile / deploy lag).
- **Zero stub/dummy endpoints.** Every `stub|dummy|placeholder|TODO` grep hit
  in server code is a "never fake" house-rule comment, matching the audit.
- **Zero duplicate JSON keys** — AST-scanned all dict literals in server/ and
  replayed 30 prod responses through a `object_pairs_hook` scanner.
- **Zero µg↔AQI unit leaks** — `pm25_g` in `/v2/city/moves` verified grams of
  tailpipe PM2.5 (`pm25_g_mid` → `s.pm25G.mid` in `Mobile/src/nav/engine.ts`),
  correctly named.
- **2 real bugs fixed in this pass** (below, FIXED), **1 shadowed route**
  + 4 live-but-unwired surfaces filed as findings (owner's call per law).

## Fixes applied (unambiguous real bugs)

1. **`server/v2/day.py` `_end_label` — naive datetime → host-local TZ read.**
   `hour_entry["start"]` is the forecast's naive-UTC label
   (`"YYYY-MM-DDTHH:MM"`); `datetime.fromisoformat(x).astimezone(_IST)` on a
   naive dt interprets it as **host-local** — right only because prod runs
   UTC; wrong on any non-UTC host (end labels shift by host offset).
   Sibling `_resolve_slot` (day.py:103) already pins naive→UTC; applied the
   same `replace(tzinfo=timezone.utc)` guard here. `pytest tests/test_v2_day.py
   tests/test_v2_outlook.py` → 31 pass.

2. **`server/admin.html` timing PNAMES/order — two paths that can never
   exist.** Metrics label `route` = the route *template*
   (`observability.py:133-138`; unmatched paths collapse to `"unmatched"`),
   so `/v2/trip/donate` and `/plan` can never appear in `timing.routes`
   (real templates: `/v2/trip`, `/route`). Trip-donation latency was invisible
   under its intended name — fell into "everything else". Renamed to the real
   templates. `check_inline_scripts.py` → OK.

## Endpoint census

`prod` = live curl. `refs` = shipped callers (Mobile/, server/*.html,
Bridge/contract.ts) — docs/tests noted separately.

### v1 REST (main.py)

| endpoint | prod | referenced by | verdict |
|---|---|---|---|
| GET /health | 200 real | App.tsx keepalive, offline/net.ts, landing/city/community/admin html | live, core |
| GET /search | 200 real | contract.ts; (Mobile uses /v2/search) | live |
| GET /route | 200 real | contract.ts, test_api | live |
| GET /compare | 200 real | contract.ts | live |
| GET /depart | 200 real | api/depart.ts, admin/landing html | live |
| GET /v2/depart | 200 real | **nothing** | live alias — finding F4 |
| GET /aqi | 200 real | App.tsx, city/admin html | live |
| GET /today | 200 real | useShellFlow, landing/admin html | live |
| GET /v2/today | 200 real | **nothing** | live alias — finding F4 |
| GET /grid | 200 real (147KB FC) | api/dayfield.ts, landing/city/admin html | live, core |
| POST /observe | 405 (reg'd) | **nothing** (410-retired handler) | intentionally retired — serves honest 410 to POSTs |
| POST /report | 405 (reg'd) | **nothing ships a writer** | finding F3 — input with no caller; GET /reports is the read side |
| POST /v2/feedback | 405 (reg'd) | SettingsScreen.tsx | live |
| GET /reports | 200 (empty FC) | App.tsx, community.html | live — empty because zero writers exist (F3) |
| GET /blackspots | 200 real | App.tsx | live |
| GET /fires | 200 real | App.tsx, admin.html | live |
| GET /community | 200 real (JSON) / HTML to browsers | App.tsx, community.html, unfurlers | live — content-negotiates on Accept + `_UNFURL_UAS` (3782c95) |
| GET /escape | 200 real | contract.ts | live |
| GET /decide | 200 real | contract.ts | live |
| GET /shift | 200 real | contract.ts | live |
| GET /reverse | 200 real | contract.ts, landing html | live |
| GET /directions | 200 real | useShellFlow.ts | live |
| GET /v2/admin/session | **404 on prod** | admin.html | not a bug — deploy lag (b563da2 > f9ea5ae8) |
| POST /v2/admin/login | **404 on prod** (405 at HEAD) | admin.html | deploy lag, same |
| POST /v2/admin/logout | **404 on prod** | admin.html | deploy lag, same |
| GET /admin/api | 401 (gate) | admin.html | live behind `_admin_guard` — see finding F2 (shadows admin_agg index) |
| GET /admin/api/reviews | 401 (gate) | admin.html | live behind gate |

### HTML / static

| endpoint | prod | verdict |
|---|---|---|
| GET / , /landing | 200, 93KB landing.html | live |
| GET /admin, /admin.html | 200, 163KB | live |
| GET /city | 200, 88KB city.html | live |
| GET /ncr.geojson | 200, 96KB | live — baked static |
| GET /delhi_subdistricts.geojson | 200, 37KB | live — baked static |
| GET /app-hero.png | 200, 531KB | live — baked static |

### v2 router (`/v2`)

| endpoint | prod | referenced by | verdict |
|---|---|---|---|
| GET /v2/skill | 200 real | landing/admin html | live |
| GET /v2/city | 200 real | WelcomeScreen, api/city.ts, landing/city/admin html | live, core |
| GET /v2/districts | 200 real | city/admin html | live |
| GET /v2/city/moves | 200 real | api/city.ts | live |
| GET /v2/reach | 200 real (196KB) | city.html | live |
| GET /v2/why | 200 real | store/events.ts, landing/admin html | live |
| POST /v2/plan | 405 (reg'd) | api/plan.ts ×2 | live |
| POST /v2/reroute | 405 (reg'd) | api/reroute.ts | live |
| GET /v2/place/{pid} | 200 real (gaz:0→Hindon Airport) | **contract tests + gen_api_docs only** | live, zero shipped callers — finding F5 |
| GET /v2/reverse | 200 real | shell/net.ts, landing/admin html | live |
| POST /v2/trip | 405 (reg'd) | nav/engine.ts, offline/queue.ts | live |
| GET /v2/ledger | 422 token-gate | contract.ts | live |
| DELETE /v2/ledger | 405→(GET) | App.tsx data-wipe | live |
| GET /v2/day | 200 real | api/dayfield.ts | live, core |
| GET /v2/outlook | 200 real | api/outlook.ts, city/admin html | live |
| GET /v2/archive | 200 real (130KB) | city/admin html | live |
| GET /v2/search | 200 real | api/search, admin html | live |
| GET /v2/strip | 422 (route_id required) | api/strip.ts | live — needs route_id from a /v2/plan round |

### tiles

| endpoint | prod | verdict |
|---|---|---|
| GET /tiles/tilejson.json | 200 | live |
| GET /tiles/delhi/{z}/{x}/{y}.mvt | 200 in-bounds (z12 2926/1707, 97KB); 404 out-of-bounds — honest absent tile | live |
| GET /tiles/delhi.pmtiles | 200, 22.6MB | live |
| GET /tiles/health | 200 (archive 22.7MB, z0-14) | live |

### admin aggregates (`/admin/api/*`, all behind `_admin_guard`)

| endpoint | prod | verdict |
|---|---|---|
| GET /admin/api (agg index, admin_agg.py:248) | — | **SHADOWED — never serves** (finding F2) |
| GET /admin/api/timing | 401 | live behind gate |
| GET /admin/api/status | 401 | live behind gate |
| GET /admin/api/sources | 401 | live behind gate |
| GET /admin/api/corridors | 401 | live behind gate |
| GET /admin/api/model | 401 | live behind gate |
| GET /admin/api/donations | 401 | live behind gate |
| GET /admin/api/global | 401 | live behind gate |
| GET /admin/api/validation | 401 | live behind gate |
| GET /v2/usage | 401 | live behind gate (admin usage tab) |
| GET /metrics | 200, 55KB Prometheus text | live |
| GET /docs, /openapi.json, /redoc | 200 | live (FastAPI defaults) |

## Findings (severity-ranked; none removed — owner's call)

- **F2 MED — shadowed route: `/admin/api` is registered twice.**
  `main.py:1688 admin_api()` (ops snapshot) registers first and wins;
  `admin_agg.py:248 index()` (endpoint map + privacy text) is unreachable —
  dead code by construction. admin.html only wants the ops snapshot, so the
  user-visible behavior is correct; the aggregate index can never serve.
  Options: rename index → `/admin/api/index`, or mark it for removal.
- **F3 LOW — `POST /report`: input surface with zero shipped writers.**
  Handler live and wired to `community.report`; no Mobile/html client POSTs
  it. Read side `GET /reports` serves an empty FeatureCollection on prod
  (`{"features":[]}`) — self-consistent, just unpopulated. Either wire a
  caller or accept it as API-surface-for-later.
- **F4 LOW — `/v2/depart` + `/v2/today` aliases: zero callers anywhere**
  (Mobile and every html use `/depart`/`/today`). Prior audit already kept
  them deliberately; noting they remain pure surface cost.
- **F5 LOW — `/v2/place/{pid}`: live and correct but only contract tests /
  `gen_api_docs` reference it.** `gaz:` ids resolve locally; `amz:` ids need
  Amazon Location (key unset → honest 503 path). Same audit-kept class as F4.
- **F6 INFO — prod deploy lag:** `/v2/admin/session|login|logout` 404 on prod
  (build `f9ea5ae8`); they exist at HEAD (`b563da2`). Everything else probed
  is already live on prod.
- **F7 INFO — UTC-vs-IST day convention is deliberate and consistent:**
  aggregate buckets (`community._DAYS`, `store._days`, `/v2/city/moves`
  window) key on UTC day; card-facing `/v2/day`, `/v2/outlook`, `/today`
  correctly pivot on `_IST`. The only non-deliberate IST bug found was the
  `_end_label` naive-parse, now fixed.
- **F8 INFO (carried, docs-debt from deadcode report):**
  `ReceiptSheet.tsx` header comment stale; a tsc-emit recipe described in a
  header that no runner executes.

## Dead-code verification (verify-only, per lane brief)

- Deadcode report (b7b951e) claims re-spot-checked at HEAD: **12/12 pass** —
  `WIND_GONE_S`, `_lev_le1`, `city_median`, `nearest_stop` gone;
  `bias_s`→`_bias_s` at validate_field.py:287; `markers.tsx`/`index.ts`
  deleted; `cacheGet`, `labelFor`, `bandWashMidIdx`, `VEHICLE_CLASSES`,
  `YEAR_BANDS`, 11 glyph entries gone.
- **New-dead-code sweep since b7b951e:** 6 commits touched server/
  (`70914c0` health rename, `326e64e` copy pass, `227c25d` metrics,
  `f9ea5ae`+`f017dad` landing fix+gate, `b563da2` admin auth). Every new def
  in them has callers or is a test helper (`_login_client` = pytest helper).
  `history.stations`→`stations_climatology` rename is clean — zero stale
  readers, prod already emits the new key (70914c0 < f9ea5ae8). The one
  artifact found is the shadowed `/admin/api` index (F2).

## Consistency-bug hunt results

- Dup JSON keys: none (AST scan + 30-response wire scan via
  `object_pairs_hook`).
- Unit leaks: none — `pm25_g` = grams of tailpipe PM2.5 (verified against
  `pm25_g_mid` contract in `Mobile/src/nav/engine.ts:253`,
  `Bridge/contract.ts:660`); `/grid?param=us_aqi` documented honest
  projection through `_d.us_aqi` (main.py:1224).
- IST math: the `_end_label` naive-parse bug (fixed) was the only real one;
  the UTC-bucket/IST-card split is documented intent.

## Method note

Census = decorator grep + `include_router` mounts (admin_agg `prefix=/admin/api`,
v2 `prefix=/v2`, tiles root-mounted, usage_router `/v2/usage`, observability
`/metrics`). Prod column = live GET curls; POSTs probed as GET→405 to confirm
registration without writing. `admin_agg.index` shadow proven by registration
order (main.py decorator at import ≪ include_router at main.py:1965), not by
curl — the gate returns 401 for both.
