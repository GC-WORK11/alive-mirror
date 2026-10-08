# deploy-17 — server ship report

Shipped `base/v2` server tree to prod. Prod `2d2fb795` / task def `:223`
→ `697562f5` / `:224`. Headline ship: **the RESTORED editorial landing**
(`1243cbb` — magazine-register page back at `/`, reverting the merge-home
board; boot-strip overlay removed; three real iPhone frames pulled
through the gate as `server/static/ios-*` + eight `/ios-*.webp|png`
FileResponse routes in `main.py`; "a typical <month>" computed live, not
hardcoded). Mobile diffs (`5bffa8d` pick-race + nav-crash, `347153e`
onboarding-gate) ride along in the repo but don't touch the server image.

## Deployed

- **commit** `697562f5` (HEAD of base/v2 at deploy time)
- **image** `185708268748.dkr.ecr.ap-south-1.amazonaws.com/alive108-api:697562f5`
  digest `sha256:a63e1fdaaef74f4885844d01bbe6f98f252b23f6b9d1b8d07876ddfa83ca320a`
- **task def** `arn:aws:ecs:ap-south-1:185708268748:task-definition/alive108:224`
- **service** alive108/alive108 ACTIVE 1/1, task `884083d0` ENI
  `eni-0bd81ed3d59a3a627` → `172.31.21.143` registered+healthy in TG
  `alive108-tg`; prior target `172.31.20.186` (:223 task) deregistered.
- **CodeBuild** `alive108-build:44c499af-3442-4e15-ba64-0b2b11e5a498`
  (clean, first try — no Docker Hub 429 this time)
- **rollback target** `2d2fb795` / `:223` (captured pre-deploy via
  `describe-services`; `./scripts/deploy.sh rollback 2d2fb795`)

## Server delta shipped (vs prod 2d2fb795)

`git diff 2d2fb795..697562f5 -- server/` — 11 files, +1226/−585:

| file | change |
|---|---|
| `server/landing.html` | Editorial page restored in place of the merge-home board: hero = live kriged field fills the viewport behind the copy, instrument numeral (`heroLive`) anchored at the hero's foot, "a day of breathing it" dose math, "The field, in your hands" interactive air map + forecast strip + measured-vs-served honesty line, "The city, kept" district cards, `buildTag` footer painted from `/health`. Boot-strip overlay gone (no `boot*` markup or script). "A typical **October**" — month pulled from the record, not a literal. |
| `server/main.py` | +23: `_ios_shot_route()` factory + 8 `app.get` routes serving the ios-* captures (`.webp` with `image/webp`, `.png` fallback). |
| `server/static/ios-{choose-priced,choose-verdict,choose-bold,dose}.{png,webp}` | 8 new assets — real 720×1566 iPhone shots referenced by the landing's `<picture>` tags. |
| `server/tests/test_landing_serve.py` | 1-line marker update for the restored page. |

## Live verification (all on http://65.2.28.40, build 697562f5)

| check | result |
|---|---|
| **(a)** `GET /` | **PASS** — 200, 128.6 KB `text/html`. Browser-driven: **editorial page, not the board** — eyebrow `GOOD EVENING · DELHI NCR — A DOSIMETER WITHOUT HARDWARE`, serif headline "A ledger for your lungs, kept on your phone."; **no boot overlay** — content paints directly, zero `boot*` strings in served HTML; live numeral paints **60.3 µg/m³ · MODERATE** with `LIVE · THE NCR-WIDE AVERAGE · WORST ≈6.7 CIGARETTES`; ticker `52 STATIONS LIVE · MAP 5 MIN FRESH · WIND 7 KM/H · 903K ROAD SEGMENTS PRICED`; iOS device-framed shots paint (three `<picture>` frames, routes below); "The city, kept" district cards live (NW Delhi 145 aqi, NE Delhi 133, GBN 125); "a typical **OCTOBER**" = correct dynamic month; footer `BUILD 697562F5` painted from `/health` = live-sha proof. |
| **(b)** `GET /ios-*` | **PASS** — all 8 routes 200: `ios-{choose-priced,choose-verdict,choose-bold,dose}.webp` (`image/webp`, 41–74 KB) + `.png` (`image/png`, 680–928 KB). |
| **(c)** `GET /city` | **PASS** — 200 HTML; labels present (`below stage i`, µg/m³, district rows, pm2.5). |
| **(c)** `GET /community` | **PASS** — 200 (`*/*` → JSON `obs_total=53 obs_today=5 today=2026-10-08 contributors=30 km_today=5.5 dose_ug_today=8.6`; `text/html` → 200 HTML). |
| **(d)** `GET <mount>/` | **PASS** — 200 + `x-robots-tag: noindex, nofollow` + `referrer-policy: no-referrer`. |
| **(d)** `GET /admin`, `GET /admin/` | **PASS** — 404 honest, no redirect. |
| **(d)** `GET <mount>/in/x` | **PASS** — 404 (hash-login gate rejects honestly); openapi.json mount-string count = 0. |
| **(e)** `POST /v2/plan` (CP→IGI, car) | **PASS** — 200, 667 KB, **23 options** with ranking. |
| **(f)** `GET /health` | **PASS** — `build_sha=697562f5` = deployed sha, `engine=alive_core`, `ok=true`, `field_stale=false`, `field_age_s=22`, stations `up, count=52, waqi+dpcc both ok`, routing `loaded, 1,070,459 edges / 903,058 priced`. |
| **(g)** CloudWatch alarms | `alive108-field-age`, `alive108-field-emitter-dead`, `alive108-target-down` all `OK`; TG shows sole target `172.31.21.143` healthy. |

## Notes for the tree

- The board is gone from `/` — any verify recipe grepping for merge-home
  markers (`panel-pad`, command-deck strings) should now key on editorial
  markers instead (`heroZone`, `heroLive`, `buildTag`, "a ledger for
  your lungs"). The deploy-16 stray-paste class is still worth an
  eyeball — this ship was eyeballed rendered, not just grepped.
- `/city` under `Accept: */*` serves HTML (same as before — it has no
  JSON variant); `/community` is the one that content-negotiates JSON
  on `*/*`.
- Rollback history: `:223 2d2fb795` (prior) → `:224 697562f5` (current).
  One-shot rollback stays `./scripts/deploy.sh rollback 2d2fb795`.
