# deploy-27 report — :233 → :234 (`547956d8`)

Shipped `547956d`/`base/v2` HEAD to prod ECS. Image `alive108-api:547956d8`,
task def `alive108:234`, new task ENI 172.31.18.90 healthy on `alive108-tg`
(old 172.31.23.189 draining post-deploy, deregistered by deploy.sh).

## What flew (90bc055d..547956d, server diff only)

| commit | contents |
|---|---|
| `c5bb130` | v16 landing: real 4-feature story — "the stay" (ios-feat-stays) + "the hour" (ios-feat-playtime) sections; districts + pledge promoted to own sections |
| `5c3d1aa` | admin-v3: blend reads `city.field` on native engine; stale>up feed verdicts; secrets blob stripped; journeys-24h + contributors + corridors; plain-word coverage/errors |
| `547956d` | admin-v3 lane report + shots |
| docs-only | `dfdb432` `4d50097` `2529a75` `66c0c8e` `9c3e842` (morning-launch, x-cut-v7, apk-v7, deploy-26 reports) — docs/plan/Mobile assets, zero server |

`git diff --stat 90bc055d..HEAD`: `server/admin.html` +139/-61,
`server/landing.html` +34/-14, everything else under `docs/`. No Mobile/
touches, no `server/*.py` or `server/v2/*` changes.

## Pre-flight

- Branch was parked on `main` (recurring box trap) — checked out `base/v2`,
  `pull --rebase` clean at `547956d`.
- Static sweep: 11 asset refs in landing.html + 4 in admin.html extracted
  (`url()/src/srcset/href/preload`) — every ref resolves: ios-feat-stays/
  playtime.webp via `_ios_shot_route` loop (main.py:2013-15), hero-delhi-smog
  (main.py:2057), ios-choose-priced/ios-dose png+webp (2005-09), all files
  present in `server/static/`.
- admin.html fetch endpoints all mount under `ADMIN_MOUNT` — `/session`,
  `/api`, `/api/{status,sources,timing}` (admin_agg router), `/api/usage`
  (usage_router), `/login`, `/logout`, `/in/{secret}`.
- Marker strings verified on disk: 'Sleep where the air is kindest.' +
  'Go out when the air lets up.' both present.

## Gates — all PASS

| gate | result |
|---|---|
| (a) `/` renders v16 | 120,634B; both markers present; stays+playtime frames referenced |
| (b) `/health` | `ok:true`, `build_sha:547956d8`, `engine:alive_core` |
| (c) v2 endpoints | `/v2/city` 200 (10,627B); `/v2/stays?near=28.6315,77.2167&k=1` 200 (5,501B — real scored stays, e.g. "The Hotel W" 0.2km, pm25_now 91.3, `scored_on:next24h`); `/v2/playtime?near=28.6315,77.2167` 200 (10,788B — CAMS hourly model) |
| (d) admin mount | `GET /a-AFiVSpmZ1Oc4YhaaQyhRie5yqnlKV_qs` 200 (47,626B); journey lines present ('journeys shared per utc hour, last twenty-four', 'journeys sparkline', `journeys_per_hour`); contributor lines present ('contributors', 'contributors_suppressed') |
| (e) feat frames | `/ios-feat-stays.webp` 200 — 195,806B image/webp; `/ios-feat-playtime.webp` 200 — 197,058B image/webp (byte-identical to deploy-26 captures) |
| (f) service stable | ECS ACTIVE 1/1 on task-def :234, PRIMARY deploy running; TG target 172.31.18.90 `healthy`; `/health` 200 + `/aqi` 200 (5,620B) after settle |

## Rollback

`./scripts/deploy.sh rollback 90bc055d8` → redeploys image `:90bc055d8`
(the :233 build) through the same task-def + NLB pipeline.

## Box notes

- Fresh box: no aws cli → `/opt/homebrew/bin/python3.12 -m venv ~/.aws-venv
  && pip install awscli` (aws-cli 1.46.1). AWS env vars inject into
  one-shot exec shells; launched `./scripts/deploy.sh` one-shot,
  CodeBuild path, ~9min end-to-end. No Docker needed.
- `git rev-parse --short=8` → tag `547956d8`; prod `/health build_sha`
  matches.
