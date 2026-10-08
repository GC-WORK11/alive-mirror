# deploy-11 — server ship report

Shipped `base/v2` server tree to prod. Prod `90766e25` / task def `:215` →
`05a3b4bd` / `:216`. Headline ship: **admin-obscure** (`05a3b4b` — the ops
console moved from `/admin` to the unguessable mount
`/a-AFiVSpmZ1Oc4YhaaQyhRie5yqnlKV_qs`; every `/admin*` path now answers an
honest 404, zero existence signal) plus **landing 'get the app' CTA**
(`34568a0`), **admin-taste polish** (`fbecd3e`), and the **search-coverage
corpus regen** (`7926c14`, gazetteer 124k→133k rows on the wire).

## Deployed

- **commit** `05a3b4b` (HEAD of base/v2 at deploy time)
- **image** `185708268748.dkr.ecr.ap-south-1.amazonaws.com/alive108-api:05a3b4bd`
  digest `sha256:1ca1e71d4d8a8ea221b3798f6ae309adfc6380f66bbf5e401261aba521d60acd`
- **task def** `arn:aws:ecs:ap-south-1:185708268748:task-definition/alive108:216`
- **service** alive108/alive108 ACTIVE 1/1, task `c608406d` ENI
  `eni-084ffc9517004027a` → `172.31.27.154` registered+healthy in TG
  `alive108-tg`; prior target `172.31.22.219` deregistered. Rollout `COMPLETED`.
- **CodeBuild** `alive108-build:3630641a-358e-4c9e-a60c-9522e7d9f231`
- **rollback target** `90766e25` / `:215` (prev prod, captured pre-deploy)

## Server delta shipped (vs prod 90766e25)

4 server-touching commits in the 16-commit wave (`git diff --stat
90766e2..05a3b4b -- server/`; the rest is Mobile/docs):

| commit | surface | change |
|---|---|---|
| `05a3b4b` admin-obscure | `server/admin_mount.py` (new, +20), `server/admin.html` +92/−40, `server/main.py`, `server/middleware.py`, `server/admin_*.py`, `server/tests/test_admin_*.py` | console mounts under `ADMIN_MOUNT = /a-AFiVSpmZ1Oc4YhaaQyhRie5yqnlKV_qs` (one file names it, all consumers import); `/admin`, `/admin/login`, `/admin/api` → honest 404; mount sends `x-robots-tag: noindex, nofollow`; all admin routes `include_in_schema=False` → zero openapi leak |
| `7926c14` search-coverage | `server/data/corpus/*` | gazetteer regen 124k→133k rows, 39 chunks; block-preserving addresses, alt-name rescue, fused-skeleton union |
| `34568a0` landing CTA | `server/landing.html` | 'get the app' → `github.com/<owner>/Delhi-Air-108/releases` (nav + close) |
| `fbecd3e` admin-taste | `server/admin.html`, `server/admin_*.py`, `server/community.py`, `server/v2/*` | fresh-badge honesty on down feeds, jargon/plural/unit/timezone cleanup, ledger dedupe |

## Live verification (all on http://65.2.28.40, build 05a3b4bd)

| check | result |
|---|---|
| `GET /health` | `build_sha=05a3b4bd`, `engine=alive_core` |
| **(a)** `GET /a-AFiVSpmZ1Oc4YhaaQyhRie5yqnlKV_qs` | **200**, `x-robots-tag: noindex, nofollow`, 168.0 kB html — console live at the opaque mount |
| **(b)** `/admin` honest-404 | **PASS** — `GET /admin` 404, `POST /admin` 404, `POST /admin/login` 404, `GET /admin/api` 404 (all bare 404s, no redirect/existence signal) |
| **(c)** `/openapi.json` leak check | **PASS** — mount literal absent, `"/admin` literal absent, 0 admin-bearing paths, 57 paths total |
| **(d)** `GET /` landing boot | **PASS** — 200, 131.3 kB; browser drive: boot strip completes, numeral **52.5 µg/m³** painted (PM2.5 · SATISFACTORY), `53 STATIONS LIVE · MAP 3 MIN FRESH · WIND 4 KM/H`, sticky chrome follows with live value; footer **`BUILD 05A3B4BD`** JS-painted from `/health`; 'get the app' CTA in nav + footer → `github.com/<owner>/Delhi-Air-108/releases` |
| **(e)** `GET /city`, `GET /community` | 200 `text/html` / 200 `application/json` |
| **(f)** `GET /v2/city` | `why.cause_note` present — "15 fires in the Punjab–Haryana belt, down from 27 over ~5.9 h — the wind isn't carrying it this way right now · air barely mixing — ventilation 880 m²/s vs ~3,000 typical" |
| **(g)** `POST /v2/plan` (CP→India Gate) | 200, honest shape — options[] with geometry+dose (mid 2.3 µg, high conf) + emissions + via_names + recommended tag, `engine=alive_core-path` |
| CloudWatch alarms | `alive108-field-age`, `alive108-field-emitter-dead`, `alive108-target-down` all `OK` |
| ECS/TG | rollout `COMPLETED` on `:216`; ENI `172.31.27.154` healthy, stale `172.31.22.219` pruned |

No rollback — every required surface verified live.
