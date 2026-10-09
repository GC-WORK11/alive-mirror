# deploy-28 report — :234 → :235 (`aa724bb4`)

Shipped `aa724bb`/`base/v2` HEAD to prod ECS. Image `alive108-api:aa724bb4`,
task def `alive108:235`, new task ENI 172.31.25.137 healthy on `alive108-tg`
(old 172.31.18.90 deregistered by deploy.sh).

## What flew (547956d..aa724bb, server diff only)

| commit | contents |
|---|---|
| `0d4920c` | landing rail: spine-track rail — hairline track, 11 numbered stops mirroring section margin indices, 7px sliding in-view mark (IO rootMargin -34%/-56%), `alive▪` wordmark dot = live band `var(--bhex)`, `elsewhere` exits group, `scroll-behavior:smooth`, section ids `secNow…secPromise` |
| `3f9245f` | airmap-restyle (Mobile): per-cell pm25 ramp ≤.32 alpha, feathered edges |
| `98fd8ba` | stays-playtime-v2 (Mobile): warm stays + playtime sheets, en+hi |
| `c88bb0f` | trip-flow (Mobile): From/To entry, finding state, starved-spring tap fix |
| `aa724bb` | splash (Mobile): 'a → alive' first-run wordmark sweep |
| docs-only | `b283b17` deploy-27 report + landing-rail/stays-playtime/splash/trip-flow reports + shots — zero server |

`git diff --stat 547956d8..HEAD` under `server/`: `server/landing.html`
+128/-30 — the ONLY server-side change; zero new files under `server/`
(no new image assets). Mobile diffs don't ship in the image (git archive
server/ only) — carried along per brief, no server impact.

## Pre-flight

- Box was parked on `main` AGAIN (4th time on these boxes) — `git checkout
  base/v2`, `pull --rebase` clean at `aa724bb`.
- Static sweep: 11 refs extracted from landing.html
  (`src/href/srcset/url()`/root-relative) — every one resolves:
  `ios-choose-priced`/`ios-dose` png+webp + `ios-feat-stays`/
  `ios-feat-playtime.webp` via `_ios_shot_route` loops (main.py:2005-15),
  `hero-delhi-smog.webp` explicit route, all files present in
  `server/static/`. Page routes `/city` `/community` live; `/v2/skill`
  `/v2/why` on the v2 router.
- Diff eyeballed end-to-end: pure rail rework — no stray renderable text,
  no pasted commit-message class incident (the deploy-16 trap).
- aws cli recreated `~/.aws-venv` (aws-cli 1.46.1); deploy.sh one-shot
  exec, CodeBuild path.

## Gates — all PASS

| gate | result |
|---|---|
| (a) `/` renders new rail | 200 (126,275B); all 11 numbered stops on the wire ('001 right now' … '013 the promise'); `aria-label="on this page"` ('the page') + `aria-label="elsewhere"` groups; `class="wm"…alive` wordmark + `.wdot` band dot + `.mark` slider present |
| (b) `/health` | `ok:true`, `build_sha:aa724bb4`, `routing.loaded` (1,070,459 edges), `field_age_s:147` |
| (c) v2 endpoints | `/v2/city` 200; `/v2/stays?near=28.6315,77.2167&k=1` 200; `/v2/playtime?near=28.6315,77.2167` 200 |
| (d) admin mount | `GET /a-AFiVSpmZ1Oc4YhaaQyhRie5yqnlKV_qs` 200 (47,626B — 'Alive · engine room', gate form intact) |
| (e) service stable | ECS ACTIVE 1/1, PRIMARY rollout `COMPLETED` on task-def `alive108:235`; `/` 200 after settle; `/ios-feat-stays.webp` spot-check 200 (195,806B) |

## Rollback

`./scripts/deploy.sh rollback 547956d8` → redeploys image `:547956d8`
(the :234 build) through the same task-def + NLB pipeline.

## Box notes

- `git rev-parse --short=8` → tag `aa724bb4`; prod `/health build_sha`
  matches.
- Fresh box: `/opt/homebrew/bin/python3.12 -m venv ~/.aws-venv && pip
  install awscli`; AWS env injects into one-shot exec shells only — run
  deploy.sh one-shot, ~7min end-to-end.
- `aws ecs` one-shots need `--region ap-south-1` (deploy.sh exports it
  itself; ad-hoc aws calls don't inherit it).
