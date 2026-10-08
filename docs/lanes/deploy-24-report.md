# deploy-24 — stays+playtime endpoints to prod

- **Shipped:** `c5ba61c0` → image `alive108-api:c5ba61c0`, task def `alive108:231`, STABLE on http://65.2.28.40 (CodeBuild path; macOS lane, no local docker — awscli via brew)
- **Rollback target:** `3ed8f9f4` / `:230` (`./scripts/deploy.sh rollback 3ed8f9f4`)
- **What's flying:** `c5ba61c` stays+playtime lane — NEW GET endpoints `/v2/stays` + `/v2/playtime` (server/v2/explore.py, 455 lines; wired into `_v2_router` via v2/__init__.py) + Mobile explore sheet (not in image) + docs/shots. Server-diff vs `:230` = explore.py + router wiring + 2 test files only — no new statics, verified.

## Pre-flight — CLEAN (second clean sweep in a row)

- **Statics sweep:** landing.html refs → `/hero-delhi-smog.webp` (route main.py:2055), `/ios-{choose-priced,dose}.{webp,png}` + `/ios-feat-{trips,week}.webp` (loop routes 2005-2014), `/delhi_subdistricts.geojson` (2068), `/ncr.geojson` (1832), `/`,`/city`,`/community`,`/v2/skill`,`/v2/why` — all covered, all files present in server/static/. admin.html refs only M-relative fetches + `/v2/city` — all mounted. `git show --stat c5ba61c` confirms zero new server/static/ files.
- **Handler check:** `@router.get("/stays")` + `@router.get("/playtime")` in server/v2/explore.py, `explore.router` in the `_v2_router` include list (v2/__init__.py:24). **Trap:** fresh FastAPI keeps included routers as lazy `_IncludedRouter` objects — a flat `app.routes` grep shows 0 `/v2/*` even though routing works; verify by TestClient, not route-table walk.
- **Local TestClient sweep (/tmp/alive-venv312, py3.12):** all 18 probes 200 — `/health`, `/`, `/city`, `/community`, `/grid?cells=40`, `/v2/stays`, `/v2/playtime`, `/v2/why`, `/v2/skill`, hero + ios statics, both geojson. `/v2/stays` → 8 ranked stays w/ sane fields; `/v2/playtime` → 24 hours + sparse flag. **No fix commit needed.**

## Verify gates — all PASS on prod

| gate | result |
|---|---|
| (a) `/` | 200 — 119,356 B, v14 landing: "Delhi's air, counted." + hero-delhi-smog.webp refs ×2 + `.top{` rail CSS + `dchip` ×25 |
| (b) `/health` | 200 — `build_sha: c5ba61c0`, engine alive_core, field_age 141 s, 1,070,459 edges / 903,058 priced, stations 54 up (waqi+dpcc ok) |
| (c) `/grid?cells=40` | 200 — 362,975 B GeoJSON in 1.45 s |
| (d) `/v2/stays?near=28.6315,77.2167` | 200 — 8 ranked stays, `lodging_rows: 15977` scored over `scored_h: 24`, `ranked_on: mean of the anchored forecast over the next 24 h at each stay's coordinates`, `sparse: false`, anchor 74.6 µg Moderate. Rows carry name/kind/dist_km/pm25_now/window_mean_ug/band/cleaner_by_ug/scored_on/nearest_station_km — no NaN, no negative dist |
| (e) `/v2/playtime?near=28.6315,77.2167` | 200 — 24 hourly points (h0 00:30 IST 74.6 µg Moderate → h23 23:30 160.7 µg Very Poor), `sparse: false`, `flat: false`, verdict "no clean stretch on the horizon — lightest reads 62 µg/m³", `best_window: null` (honest — none exists), `worst_window{start_h:19, 155.8 µg}`, confidence med |
| (f) admin mount | `<mount>` 200, 43,278 B — `01 live air · 02 coverage · 03 usage · 04 health` intact (deploy-23 analytics page NOT regressed); `/admin` honest 404 |
| (g) statics | hero-delhi-smog / ios-feat-trips / ios-feat-week / ios-dose / ios-choose-priced webp + delhi_subdistricts + ncr geojson — all 200 |
| (h) service | ACTIVE, 1/1 desired running on `:231` PRIMARY; TG `172.31.26.31` healthy, old `172.31.25.69` draining |

### /v2/stays top-3 as served live (proof the numbers breathe)

| # | name | dist | pm2.5 now | 24h mean | band | cleaner_by |
|---|---|---|---|---|---|---|
| 1 | The Hotel W | 0.2 km | 74.4 µg | 97.0 µg | Poor | 0.2 µg |
| 2 | Marina Hotel New Delhi | 0.2 km | 74.6 µg | 97.0 µg | Poor | 0.0 µg |
| 3 | Radisson Blu Marina (Business Class) | 0.3 km | 74.6 µg | 97.0 µg | Poor | 0.0 µg |

New-rev proof: taskdef `:230`→`:231`, image `3ed8f9f4`→`c5ba61c0`, TG cutover `172.31.25.69`→`172.31.26.31`, `/health` build_sha flip, prod `sparse:false` (this lane's box serves model-only so local pre-flight showed `sparse:true` — honest degradation, prod carries live feeds).
