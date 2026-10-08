# deploy-14 — server ship report

Shipped `base/v2` server tree to prod. Prod `61364f31` / task def `:218` →
`30af6b17` / `:219`. Headline ships: **the merge-home board** (`4101bd8`
— `/` rebuilt in the admin register: live numeral hero + vitals rail +
kriged field map + strips/districts + app shots in CSS device frames),
**hash-login** (`65d413a` — `GET <mount>/in/<token>` mints the cookie
server-side + 303 to clean mount, honest-404 on miss, own rate bucket,
log-redacted; console boot strip deleted; stale sign-out label fixed),
**search unit-adjacency** (`d05b737` — 'b 7' binds as one unit, scattered
covers rejected), **bug-hunt guards** (`6f799ee`+`f9e6e72` — personal-sample
eligibility, painted-grid age). Mobile cargo: app-home-sexy diffs
(`2f683cb`, `30af6b1` — no server effect).

## Deployed

- **commit** `30af6b17` (HEAD of base/v2 at deploy time; re-polled
  post-deploy — the running honesty-cluster lane landed nothing
  mid-flight, nothing newer to carry)
- **image** `185708268748.dkr.ecr.ap-south-1.amazonaws.com/alive108-api:30af6b17`
  digest `sha256:ea1da213e93b3e0e77aaf2c41c8887fa3fddb32ff207d888edcba2cf0d47fd1c`
- **task def** `arn:aws:ecs:ap-south-1:185708268748:task-definition/alive108:219`
- **service** alive108/alive108 ACTIVE 1/1, task `e7c735e1` ENI
  `eni-09fdfc197d1636a76` → `172.31.23.252` registered+healthy in TG
  `alive108-tg`; prior target `172.31.25.238` deregistered.
- **CodeBuild** `alive108-build:d6b314de-4dc3-45bd-9cca-0831f6bb8fbb`
- **rollback target** `61364f31` / `:218` (prev prod, captured pre-deploy
  via `describe-task-definition`; `./scripts/deploy.sh rollback 61364f31`)

## Server delta shipped (vs prod 61364f31)

`git diff 61364f31..30af6b17 -- server/` — 11 files, +838/−1447:

| files | change |
|---|---|
| `server/landing.html` | full rebuild in the admin/board register — live numeral hero, vitals rail (stations live · map age · wind · segments priced · GRAP stage · next-12h), kriged field map w/ smooth band ramp + inspect/A-B pickers, strips+districts live, app shots in CSS device frames, `BUILD <sha>` footer painted from /health |
| `server/main.py` | `GET <mount>/in/<token>` route — `compare_digest` against the SM token, mints the same v1 cookie, 303 → clean mount; honest-404 on miss, own (0.2,5) rate bucket, log-redacted |
| `server/admin.html` | console boot strip deleted — form is the fallback sign-in; stale sign-out label fix (tokBtnRefresh re-runs after checkSession) |
| `server/core_engine.py`, `server/middleware.py`, `server/observability.py` | bug-hunt guards — personal-sample eligibility, painted-grid age; /in/ logging hooks |
| `server/static/app-*.{png,webp}` | 3 real app captures for the device frames (hero / choose-settle / air-map, png + webp) |
| `server/tests/test_admin_auth.py` | hash-login + boot-strip-removal expectations |

## Live verification (all on http://65.2.28.40, build 30af6b17)

| check | result |
|---|---|
| `GET /health` | `build_sha=30af6b17`, `engine=alive_core`, `ok=true`, field_age_s 330 |
| **(a)** `GET /` | **PASS** — 200, 95.5 KB. Board markup confirmed (class histogram byte-identical to `server/landing.html`@HEAD; zero old-editorial markers — no `hero-copy`/`get-the-app`). Browser drive: live numeral **53.7 µg/m³** painted (PM2.5 · SATISFACTORY), vitals rail live (52 STATIONS · MAP 5 MIN FRESH · 9 KM/H NW · 903k SEGMENTS · GRAP stage 0 · next 12h 65.0–101.2), kriged field map rendering, 3 device-framed app shots all painted (hero / route-plan / air-map), footer **BUILD 30AF6B17** from /health = live-sha proof. Shots: `deploy-14-shots/landing-live.jpg`, `landing-footer-build.jpg` |
| **(b)** `GET <mount>/in/x` (wrong token) | **PASS** — 404, byte-identical body (22 B) to a random nonexistent path — route exists and rejects honestly, no oracle leak |
| **(c)** real-token test | skipped per brief (mints owner credential cookie); route presence proven by (b) + code review of the shipped image (`git archive HEAD:server`) |
| **(d)** `GET <mount>` | **PASS** — 200, 162 KB + `x-robots-tag: noindex, nofollow`. Zero boot-strip element — the only `boot` hits are a code comment and the 'since boot' timing label, identical to source |
| **(e)** `GET /v2/city` | **PASS** — felt-words live: `why.cause_note` '15 fires in the Punjab–Haryana belt — a north-west wind at 9.3 km/h is carrying it our way'; `why.story_age_s=240` |
| **(f)** `GET /community` | **PASS** — 200 |
| **(g)** `GET /admin` | **PASS** — 404 (honest, no redirect) |
| **(h)** `POST /v2/plan` (CP→India Gate, car, fast) | **PASS** — 200, 5 honest options on live field (52 station readings, kriging on, `stale=false`), 60.5 ms server-side |
| **(i)** `GET /health` build_sha | **PASS** — `30af6b17` = deployed sha |
| CloudWatch alarms | `alive108-field-age`, `alive108-field-emitter-dead`, `alive108-target-down` all `OK` |
| ECS/TG | rollout `COMPLETED` on `:219`; ENI `172.31.23.252` healthy, stale `172.31.25.238` pruned |

No rollback — every required surface verified live on `30af6b17`.
