# deploy-18 — server ship report

Shipped `base/v2` server tree to prod. Prod `697562f5` / task def `:224`
→ `06919cac` / `:225`. Headline ship: **landing-v9** (`06919ca` — landing
rebuilt in the a1mobile register: card hero, massive band-ink numeral,
black blocks, pill CTAs, ALIVE giant-letter footer, copy-law register
"Delhi's air is the worst in the world." — `dosimeter` removed
everywhere incl. the `test_landing_serve.py` marker) plus `0aad444`
ios-vid fixes (ride along in the repo; Mobile-only diffs don't touch
the server image).

## Deployed

- **commit** `06919ca` (HEAD of base/v2 at deploy time)
- **image** `185708268748.dkr.ecr.ap-south-1.amazonaws.com/alive108-api:06919cac`
  digest `sha256:84d22188e40e71d504af9ed4e3eea13419038eed468302c44df25ac01c72a5d8`
- **task def** `arn:aws:ecs:ap-south-1:185708268748:task-definition/alive108:225`
- **service** alive108/alive108 ACTIVE 1/1, task `a8035ab1` ENI
  `eni-07af94e85f884f0e8` → `172.31.17.182` registered+healthy in TG
  `alive108-tg`; prior target `172.31.17.225` (:224 task) draining.
- **CodeBuild** `alive108-build:379368b5-af24-444c-afc9-6de410a2798a`
  (clean, first try)
- **rollback target** `697562f5` / `:224` (captured pre-deploy:
  `/health build_sha=697562f5`; `./scripts/deploy.sh rollback 697562f5`)

## Server delta shipped (vs prod 697562f5)

`git diff 697562f5..06919ca -- server/` — 2 files, +713/−736:

| file | change |
|---|---|
| `server/landing.html` | Full v9 rebuild (~1,447 lines touched): floating pill top bar, one-card-per-section grammar on warm paper; `.hero-card` under `#heroZone` with live field + paper scrim; `h1` "Delhi's air is the worst in the world."; massive `hnum-v` numeral with band-ink + `PM2.5 · <band>` pill; `.cta` pill row (b/o/g); proof/field/story/forecast/city/app/mechanics cards; premium black get-app block; black `footer.foot` with giant `ALIVE` + `buildTag` painted from `/health`. |
| `server/tests/test_landing_serve.py` | Marker updated for the v9 page (dosimeter-era string dropped). |

## Live verification (all on http://65.2.28.40, build 06919cac)

| check | result |
|---|---|
| **(a)** `GET /` | **PASS** — 200. Browser-driven, RENDERED (not grepped): hero card paints on warm base with field visible under scrim; headline "Delhi's air is the worst in the world."; live numeral paints **64.4 µg/m³ · PM2.5 · MODERATE**; "53 public monitors", "a day outside in this air ≈ 2.9 cigarettes"; pill CTAs "get the app → / open the live field / community →"; sticky pill bar carries live `PM2.5 64.4 µg/m³ · MAP 4 MIN FRESH`; black get-app block + field/community rail cards paint; **black footer with giant `ALIVE` and `BUILD 06919CAC`** painted from `/health` = live-sha proof. |
| **(b)** forbidden strings in served bytes | **PASS** — `grep -ci 'stage 0'` = 0, `grep -ci 'dosimeter'` = 0 on the `/` response body. |
| **(c)** `GET /city` | **PASS** — 200 HTML; labels present (`below stage i` ×4, `µg/m³` ×16, `pm2.5/pm25` ×25). |
| **(c)** `GET /community` | **PASS** — 200 (`*/*` → JSON `obs_total=53 obs_today=5 today=2026-10-08 contributors=30 km_today=5.5 dose_ug_today=8.6`, top_corridors present; `text/html` → 200 HTML, corridor/contributor labels present). |
| **(d)** `GET <mount>/` | **PASS** — 200 (`/a-AFiVSpmZ1Oc4YhaaQyhRie5yqnlKV_qs`). |
| **(d)** `GET /admin` | **PASS** — 404 honest, no redirect. |
| **(d)** `GET <mount>/in/x` | **PASS** — 404 (hash-login gate rejects honestly). |
| **(e)** `POST /v2/plan` (CP→IGI, car) | **PASS** — 200, 564 KB, **24 options** with doc-06 §4 ranking, `took_ms≈5472`. |
| **(f)** `GET /health` | **PASS** — `build_sha=06919cac` = deployed sha, `engine=alive_core`, `ok=true`, `field_stale=false`, `field_age_s=142`. |
| **(g)** CloudWatch alarms | `alive108-field-age`, `alive108-field-emitter-dead`, `alive108-target-down` all `OK`; TG shows new task `172.31.17.182` healthy (old `172.31.17.225` draining). |

## Notes for the tree

- Verify markers for `/` changed again with v9: the editorial markers
  (`heroLive`, "a ledger for your lungs") are dead. Key on `heroZone` /
  `hero-card` / `hnum-v` / `hnumS` / `buildTag` / "Delhi's air is the
  worst in the world" / `fgiant` ALIVE footer.
- The served-HTML grep for `dosimeter` must now return 0 — copy-law
  register dropped it; a non-zero count means an old build is serving.
- Rollback history: `:224 697562f5` (prior) → `:225 06919cac` (current).
  One-shot rollback stays `./scripts/deploy.sh rollback 697562f5`.
