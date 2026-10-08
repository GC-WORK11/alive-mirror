# deploy-16 — server ship report

Shipped `base/v2` server tree to prod. Prod `dd2aec33` / task def `:220`
→ `2d2fb795` / `:223`. Headline ships: **bug-hunter v2 server diffs**
(`e0bac51` — GRAP 'below stage i · aqi N' honest line replacing the fake
'stage 0' on `/`, spark `the next N hours` off-by-one fixed (was 11h),
districts strip fetch-failure repaints honest resting line instead of
blank) + **deploy-16 hotfix** (`2d2fb79` — see gate-(a) incident below).
Mobile diffs from e0bac51 (provLine `!counted` re-gate) ride along in the
repo but don't touch the server image.

## First attempt — gate (a) FAIL → rollback

`b0a615f9` / `:221` went live and gate (a) failed: `e0bac51` had pasted
its own commit message into `server/landing.html:540` —

```
<section class="panel" id="fieldSec"><div class="panel-pad"> (bug-hunter
v2: 5 defects in new surfaces — dead #fieldSec anchor, GRAP 'stage 0'
contradiction, counted-day air-age leak, spark hour-count, silent
district strip)
```

rendered as visible text atop the field panel on `/` (including a literal
'stage 0'). Absent in `:220`; introduced by the very commit being shipped.
Per procedure: `./scripts/deploy.sh rollback dd2aec33` → `:222`, prod
restored (`/health build_sha=dd2aec33`). Hotfix `2d2fb79` removed the
stray line (one-line revert inside the `<div class="panel-pad">` open
tag), `check_inline_scripts` green, pushed.

## Deployed

- **commit** `2d2fb795` (HEAD of base/v2 at deploy time)
- **image** `185708268748.dkr.ecr.ap-south-1.amazonaws.com/alive108-api:2d2fb795`
  digest `sha256:e2dd97f33fc198747c0154fb49b584add865cc04160fbc77a5dc3a2003cb5bb5`
- **task def** `arn:aws:ecs:ap-south-1:185708268748:task-definition/alive108:223`
- **service** alive108/alive108 ACTIVE 1/1, task `93da4cce` ENI
  `eni-05fdbdb8b9b3c8a43` → `172.31.17.3` registered+healthy in TG
  `alive108-tg`; prior target `172.31.20.142` (rollback task) deregistered.
- **CodeBuild** `alive108-build:da7bf930-74eb-4571-8c3e-1329c382bcf4`
  (first try `15df486c` FAILED on a transient Docker Hub 429 pulling
  `python:3.12-slim-bookworm` metadata — retry identical, succeeded)
- **rollback target** `dd2aec33` / `:220` (captured pre-deploy via
  `describe-task-definition`; `./scripts/deploy.sh rollback dd2aec33`)

## Server delta shipped (vs prod dd2aec33)

`git diff dd2aec33..2d2fb795 -- server/` — 1 file, +12/−4:

| file | change |
|---|---|
| `server/landing.html` | (1) GRAP vital: `stage ${n} · aqi` → roman I–IV map, served-0 renders `below stage i · aqi N`, hover `title` states "computed from the live field — the official stage is caqm's call" — matches /city + console frame. (2) Spark card off-by-one: `vs.length-1` → `vs.length` so the "next N hours" line says 12h for a 12-hour forecast. (3) Districts strip: `catch` now repaints chips with the resting line when empty instead of staying blank. (4) Hotfix: stray commit-message text removed from `fieldSec` open tag. |

## Live verification (all on http://65.2.28.40, build 2d2fb795)

| check | result |
|---|---|
| **(a)** `GET /` | **PASS** — 200, 96.0 KB board. Browser-driven: hero numeral paints **57.1 µg/m³ · SATISFACTORY**; vitals `stations live 52 · map 3 min · wind 7 km/h N · 903k segments priced`; **GRAP STAGE NOW renders `below stage i · aqi 95`** — honest line live, zero 'stage 0' in rendered DOM (only a JS comment documents "never 'stage 0'"); `NEXT 12H 64.2–99.3 µg/m³`; footer `BUILD 2D2FB795` painted from `/health` = live-sha proof. Stray text gone — field section opens clean. `/aqi?lat=28.6315&lon=77.2167` live: `pm25_ambient=64.2` |
| **(b)** `GET /city` | **PASS** — 200, 91.8 KB; 'below stage i' frame present |
| **(b)** `GET /community` | **PASS** — 200 (`text/html` 21.2 KB; `*/*` serves the JSON counters — contributors/corridor labels present) |
| **(c)** `GET <mount>/` | **PASS** — 200, 162.5 KB |
| **(c)** `GET /admin` | **PASS** — 404 honest, no redirect |
| **(c)** `GET <mount>/in/x` | **PASS** — 404 (hash-login gate rejects honestly) |
| **(d)** `POST /v2/plan` (CP→IGI, car) | **PASS** — 200 in 5.4 s: **24 options** with real geometries + least-smoke labels |
| **(e)** `GET /health` | **PASS** — `build_sha=2d2fb795` = deployed sha, `engine=alive_core`, `ok=true`, `field_stale=false`, `field_age_s=229`, stations `up, count=52, waqi+dpcc both ok` |
| **(f)** CloudWatch alarms | `alive108-field-age`, `alive108-field-emitter-dead`, `alive108-target-down` all `OK` |
| ECS/TG | rollout `COMPLETED` on `:223`; `172.31.17.3` healthy |

## Notes for the tree

- **e0bac51 is not deployable as-is** — the stray paste in landing.html
  survives any rebuild of that sha. The hotfix `2d2fb79` is the only diff
  between the failed `:221` image content and green `:223`; any lane
  shipping an e0bac51-era tree without `2d2fb79` will fail gate (a) again.
- Two full prod task-def revs were burned on the incident (`:221`,
  `:222`) — history is `:220 dd2aec33` → `:221 b0a615f9` (bad) → `:222
  dd2aec33` (rollback) → `:223 2d2fb795` (current).
- Docker Hub anonymous pull 429s hit CodeBuild occasionally; the failure
  is safe (build dies before push, prod untouched) — just rerun
  `deploy.sh`.
