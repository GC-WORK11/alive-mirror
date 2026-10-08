# deploy-23 — admin cognition-register analytics to prod

- **Shipped:** `3ed8f9f4` → image `alive108-api:3ed8f9f4`, task def `alive108:230`, STABLE on http://65.2.28.40 (CodeBuild path; macOS lane, no local docker — awscli via brew)
- **Rollback target:** `fb5cbb79` / `:229` (`./scripts/deploy.sh rollback fb5cbb79`)
- **Rode along:** `3609c43` admin-analytics rebuild (admin.html 3.1k→831 lines; admin_agg.py +19 — `/api/timing` now emits `requests{total,by_status}` + `errors[{route,class,n}]`) + `3ed8f9f` vid-retakes docs

## Pre-flight statics sweep — CLEAN (first clean sweep; trap bit 4x before)

landing.html refs → `/hero-delhi-smog.webp` (route + file, deploy-22 fix), `/ios-{choose-priced,dose}.png`, `/ios-feat-{trips,week}.webp` (loop routes, files present), `/`,`/city`,`/community`,`/v2/skill`,`/v2/why` — all covered. admin.html refs only routes + M-relative fetches (`/session`,`/api/{status,sources,timing}`,`/login`,`/logout`) — all mounted (`admin_agg.router` prefix `ADMIN_MOUNT+"/api"`, usage_router, main.py session endpoints). `admin_agg` AST-parses; flat-layout imports (`health`,`v2.store`,`admin_mount`) resolve under `uvicorn main:app`; `reg._counters` + `alive_http_{requests,errors}_total` labels verified at observability.py:445-452. **No fix commit needed.**

## Verify gates — all PASS on prod

| gate | result |
|---|---|
| (a) `/` | 200 — v14 landing: "Delhi's air, counted." present, hero-delhi-smog.webp preload+`url()` refs, 15 left-rail links, zero "get the app" |
| (b) `/health` | 200 — `build_sha: 3ed8f9f4`, engine alive_core, field_age 123 s, 1,070,459 edges / 903,058 priced, stations 53 up |
| (c) `/grid?cells=40` | 200 — GeoJSON, 1600 features |
| (d) `/v2/city` | 200 (11,694 B) |
| (e) statics | hero-delhi-smog/hero-alive/hero-nature/ios-feat-trips/ios-feat-week .webp — all 200 |
| (f) admin mount | `<mount>` 200, 43,278 B / 831 lines — served == shipped; `01 live air`/`02 coverage`/`03 usage`/`04 health` present; no box-visuals (only the sign-in gate-card + css comments); `/admin` honest 404 |
| (g) `/api/timing` | anon 401 (guard intact); via signed session → `requests{total:38, by_status:{2xx:36,4xx:2}}` + `errors[{route,class,n}]` — new shape live |
| (h) service | steady state, deployment completed, 1/1 desired running, TG `172.31.25.69` healthy, old target draining, no 5xx events |

New-rev proof: taskdef `:229`→`:230`, image `fb5cbb79`→`3ed8f9f4`, TG cutover `172.31.30.207`→`172.31.25.69`, `/health` build_sha flip.
