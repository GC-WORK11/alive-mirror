# codebase-audit-report — ALive-108 @ base/v2 `6896b3a`

Lane: codebase-hygiene (docs/lanes/codebase-hygiene.md). Read of the whole repo:
server/ (~59k LOC incl. v2/), Bridge/contract.ts (1,037), Mobile/ (~39k LOC),
web surfaces (landing/city/community/admin.html), scripts/, tools/, infra/,
docs/, tests/, .github/workflows.

Baseline gates **before** any change (all green):
- `server`: 1151 passed, 5 skipped (`pytest -q tests`, PYTHONPATH=core/build312:.)
- `Mobile`: `npx tsc --noEmit` clean, `npx expo lint` clean
- `Bridge`: contract.ts is a pure type file — no emit gate needed

Class legend: dead / dummy / broken / dup / stale / perf / structure / risk.
Safe-fix means mechanically removable with zero behavioral change.

## HIGH

| class | file:line | evidence | safe-fix |
|---|---|---|---|
| broken | server/tests/test_transit.py:87 | `km = sum(l["distance_km"] for l in legs) if False else opt["distance_km"]` — `legs` is undefined (F821); guarded by `if False`, i.e. dead code hiding a stale refactor. If the guard ever flips the test crashes. | yes — `km = opt["distance_km"]` |
| risk | Mobile/src/*.test.ts (8 files: api/outlook, nav/strip, nav/pick, nav/counters, nav/offroute, nav/searchSpring, nav/reroute, store/ledger, store/daylog) | Mobile/package.json has **no test runner and no `test` script** (deps: expo/react-native only; devDeps: eslint+tsc). The unit-test files cannot execute in CI — coverage they imply does not exist. | needs-review (lead — Mobile/src off-limits; add a vitest/jest gate or drop the files) |
| dead | Mobile/src/components/FieldLayer.tsx:64 | `export function FieldLayer` — zero imports anywhere in Mobile/ (verified by basename grep over src + App.tsx). The AQI field-layer component docs/13-segments.md describes is not mounted. Possibly a dropped feature, not just dead weight. | needs-review (lead — off-limits; likely superseded by RouteTintSource/FieldLayer-on-web path) |
| dup | Open-Meteo URL ×4 live sources | `server/airfield.py:31 METEO`, `server/forecast.py:54 MET_API`, `server/validate_field.py:48 MET_API`, `server/fires.py:179` inline literal — four places to edit on an upstream change. | yes — single-source via `server/upstreams.py` |
| dup | Open-Meteo AQ URL ×3 | `server/airfield.py:30 OPEN_METEO`, `server/forecast.py:53 AQ_API`, `server/validate_field.py:47 AQ_API`. | yes — same upstreams.py |
| dup | OSRM public URL ×3 live + 1 dead | `server/main.py:639 OSRM_PUBLIC`, `server/routing_local.py:41 PUBLIC_OSRM`, `server/v2/deps.py:244` inline, + dead `server/main.py:242 OSRM` (has `/route/v1/driving/` suffix, unused). | yes — same upstreams.py |
| dup | OpenAQ v3 base ×3 | `server/airfield.py:32 OPENAQ`, `server/airindex.py:111 OPENAQ_V3`, `server/ingest_openaq.py:50 OPENAQ_V3`. | yes — same upstreams.py |
| dup | Photon reverse-geocode URL ×2 inline | `server/main.py:1420`, `server/main.py:1688` — literal `https://photon.komoot.io/reverse` twice while `PHOTON` const exists at :241 for the forward API. | yes — `upstreams.PHOTON_REVERSE` |
| dup | `LEDGER_SK_PREFIX` defined but trip# written inline | `server/agg_ddb.py:503` constant unused; `agg_ddb.py:549` writes `f"trip#{ts:.3f}"` by hand. Constant exists precisely to single-source the prefix. | yes — use the constant at :549 |

## MEDIUM

| class | file:line | evidence | safe-fix |
|---|---|---|---|
| dead | server/main.py:242 | `OSRM = "https://router.project-osrm.org/route/v1/driving/"` — zero refs repo-wide (superseded by `OSRM_PUBLIC`/`_osrm_base()`). | yes |
| dead | server/airfield.py:84 | `MAX_OD_KM = 700.0` — zero refs; OD bound enforced by `in_service_area()` + `SERVICE_MARGIN_DEG`, and route cap by `MAX_ROUTE_KM` (used at main.py:609/710/733, v2/deps.py:261). | yes |
| dead | server/exposure.py:166 | `APP_MODES = {"driving","cycling","walking"}` — zero refs. | yes |
| dead | server/ingest_cpcb.py:54 | `CATALOG_UUID` — zero refs (catalog probing is key-driven elsewhere). | yes |
| dead | server/history_builder.py:64,69 | `KEY_FMT`, `CLUSTER_KM` — def site + docstring mention only; actual key layout lives in `openaq_archive.py`. | yes |
| dead | server/rollup.py:152 | `_load_fields()` — superseded by `_load_fields_verbose()` (used at :248) which additionally counts skipped/corrupt blobs. Dead sibling is also *weaker* (silently `continue`s). | yes |
| dead | server/core_engine.py:361 | `_anchor_row()` — superseded by `_anchor_candidates()` (multi-candidate area check). Zero callers. | yes |
| dead | server/routegraph.py:243 | `_pack_i16()` — packing helper with zero callers (pack code inlined). | yes |
| dead | server/districts.py:237 | `districts_meta()` — reads geojson properties; zero callers repo-wide (not in routes, admin_agg, Mobile, docs). | yes |
| dead | server/agg_ddb.py:673 | `get_ledger_store()` — public factory (DDB→memory fallback); zero callers (v2 deps wires DeviceLedger directly). | yes |
| dead | server/admin.html:1437 | `fmFindDistrict(name)` — defined, never invoked (fmDistrict(lon,lat) is the live path). ~5 lines of dead JS. | yes |
| dead | server/segments.py:42 | `carry_i` — assigned in tuple, never read (F841). | yes |
| dead | 41× unused imports (ruff F401) | server: archive.py:58-59 `gzip,json`; core/ref_krige.py:30 `dataclasses.field`; history.py:26 `statistics`; ingest_openaq.py:45 `timezone`; openaq_archive.py:45 `_station_key`; rollup.py:36 `gzip`; routegraph.py:32 `bisect_right`; transit.py:26 `math`; transit_real.py:32 `math`,:42 `Callable`; validate_field.py:27 `statistics`; v2/day.py:30 `time`; v2/outlook.py:34 `math`,:37 `Optional`; test_api.py:9 `json`,:11 `time`; + 22 in tests/. | yes |

## LOW / NEEDS-REVIEW (report, no touch)

| class | file:line | evidence | safe-fix |
|---|---|---|---|
| stale | server/main.py:952-953, 1126-1127 | `/v2/depart` and `/v2/today` alias decorators — zero callers in Mobile (uses `/depart`, `/today`), web, scripts. Kept as API surface. | needs-review (route removal = owner-forbidden) |
| stale | server/v2/places.py:53 `/v2/place/{pid}` | Zero client callers (gen_api_docs + contract tests only). Mobile resolves places via `/v2/search` rows directly. | needs-review |
| stale | v1 REST surface: `/route` `/compare` `/decide` `/shift` `/escape` `/observe` `/report` `/search` `/reverse` (main.py:584..1676) | Zero live client calls — superseded by `/v2/*` + `/directions`; still exercised by test_api.py (46-assert live smoke), test_contract_sync, gen_api_docs. This is the documented public v1 API, not dead code. | needs-review (no route removal) |
| stale | server/transit_rt.py | GTFS-RT capability shim per docs/plan/transit-realtime.md — `refresh()` never invoked by any scheduler/ingest; module reachable only via its test. Documented as intentionally-unwired. | needs-review |
| stale | server/snapshot_gc.py | Imported only by its test; no schedule in infra/schedules/*.json, provision.sh, docker-compose, or docs calls it. Dormant maintenance tool. | needs-review |
| stale | server/iitm_probe.py | Diagnostic CLI (IITM EWS reachability); referenced by no doc/infra; run manually at need. | needs-review |
| stale | server/pyproject.toml vs requirements.txt | pyproject deps omit `numpy` + `h3` (requirements.txt has them). Dockerfile:60 declares requirements.txt authoritative — but `pip install .` would silently miss two real imports (v2/trip.py, krige.py). | needs-review |
| structure | server/main.py | 1,963 lines, 32 v1 handlers + router mounts + middleware — all v1 surface in one file; v2 is properly namespaced under v2/. Not a violation, but the next growth spurt should move v1 routes into a `v1/` package. | needs-review |
| structure | transit trio: server/transit.py, transit_v2.py, transit_real.py | Three coexisting transit layers: transit.py = v1 DMRC leg for `/compare`; transit_real.py = GTFS-real journeys; transit_v2.py = timetable-exact planner. All imported; naming overlap is a readability hazard, not dead code. | needs-review |
| risk | server/admin_agg.py:76-97,191,537 | `except Exception: return {}` status helpers — deliberate "null not crash" honesty rule (docstrings say callers report nulls). Broad catch also masks ImportError inside try — acceptable for an admin board, flagged for awareness. | needs-review |
| risk | server/tiles.py:138-140, routegraph.py:160,194 | PMTiles/routegraph header fields (`leaf_len`, `tile_len`, `n_contents`, `clustered`, `n_names`, `n_pts`) stored but never read — they're tuple-unpacked from binary headers; removing them individually would break the unpack arity. Keep as parse artifacts. | no |
| stale | Mobile/assets/delhi-gazetteer.json vs server/data/delhi-gazetteer.json | Both ~11.25 MB but **different md5** — the app-bundled corpus (used by src/search/t0.ts offline T0) has drifted from the server corpus. Intentional mirror, but no shared source-of-truth/generation stamp visible. | needs-review (lead) |
| stale | server/tests/test_*.py — vulture low-value noise | Unused test vars: `Bucket` ×8 (moto-ish client kwargs kept for parity), `capsys` fixture (test_contract_sync.py:570), `wind_nw`/`wind_se`/`cold_forecast`/`ambient_only` fixtures referenced only for side-effects. Test-local; cosmetic only. | no (keep — fixture semantics intentional) |
| style | RET504 unnecessary-assign-before-return ×4 | airfield.py:1055, observability.py:120, transit_real.py:94 (+3 test files). One-line cleanups; not worth a churn commit alone. | no (fold into future edits) |

## Not found (clean areas — verified, not assumed)

- **dummy/fake data on real endpoints**: zero. Every `fake|stub|placeholder|TODO|FIXME` grep hit is a *comment describing why the code refuses to fake* (house rule). The only placeholder tokens are `REPLACE_ME` secret sentinels with honest failure paths.
- **broken wiring**: every mounted route has ≥1 consumer or is a documented v1 surface; all Mobile fetches resolve to live routes; all web-surface fetches (`/v2/archive|outlook|reach|skill|reverse`, `/grid`, geojsons, `/admin/api*`) resolve.
- **silent `except: pass`**: zero occurrences repo-wide (non-test).
- **commented-out code blocks**: none (3+ line sweep found none).
- **sync-in-async**: no `requests.*` inside async handlers; network uses shared httpx client (`deps._http`).
- **perf**: no per-request file reads/recompiles/executor creation found on hot paths; ingest fetch legs already bounded-parallel (ingest-coldbuild lane); executors are module-scoped or per-ingest-cycle, not per-request.
- **Bridge**: contract.ts is the declared source of truth; Mobile deliberately shadows subsets (documented convention, drift guarded by test_contract_sync).
- **CI**: .github/workflows ci.yml + android-apk.yml + ios-sim.yml all current, matching the local gates.
- **junk files**: no tracked .pyc/.DS_Store/logs/node_modules; tools/corpus-venv is untracked local only.

## Phase-2 fix plan (applied after this report)

1. **commit `hygiene: drop dead imports`** — ruff `--fix` F401 (41 files) + carry_i + test_transit F821.
2. **commit `hygiene: remove zero-ref dead code`** — items marked `yes` in MEDIUM dead table (10 server symbols + fmFindDistrict).
3. **commit `hygiene: single-source upstream URLs + ledger prefix`** — new `server/upstreams.py` (OPEN_METEO_MET, OPEN_METEO_AQ, OSRM_PUBLIC, OPENAQ_V3, PHOTON_API, PHOTON_REVERSE); 9 call sites switched; `trip#` inline → `LEDGER_SK_PREFIX`.

Nothing touching Mobile/src, no route/feature/string removals, no reformatting.
