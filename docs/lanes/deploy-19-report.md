# deploy-19 — server ship report

Shipped `base/v2` server tree to prod. Prod `06919cac` / task def `:225`
→ `ea2c0fb7` / `:226`. Headline ship: **landing-v10** (`fecf312` — total
theme replacement across all four web surfaces: warm `#FBFBFA` cream
base, one sans stack with 800-weight tight headlines, zero caps-track,
1.5px ink-bordered cards + one soft shadow, forest accent + CPCB band
inks only, pill CTAs, black footer; photographic Delhi smog-scape hero
`hero-haze.webp` under graded scrim, 34s drift, reduced-motion gated;
live field canvas kept). Also riding: `1f188e9` search-depth server-side
corpus (344,923-row corpus incl. Overture-places aux, gzipped in image)
and **`ea2c0fb` deploy-19 hotfix** — see pre-flight catch below.

## Deployed

- **commit** `ea2c0fb` (HEAD of base/v2 at deploy time)
- **image** `185708268748.dkr.ecr.ap-south-1.amazonaws.com/alive108-api:ea2c0fb7`
  digest `sha256:a07e5f4165488ed1eae57686c9fbfca5918131a41f02ce7d01a3677c6ad704e2`
- **task def** `arn:aws:ecs:ap-south-1:185708268748:task-definition/alive108:226`
- **service** alive108/alive108, new task ENI `eni-0c727f5cf2370a9b6` →
  `172.31.31.224` registered+healthy in TG `alive108-tg`; prior target
  `172.31.17.182` (:225 task) draining.
- **CodeBuild** `alive108-build:3d3d7d1e-6f7e-4bbb-bafb-72cf02d01ae6`
  (clean, first try)
- **rollback target** `06919cac` / `:225` (captured pre-deploy:
  `/` 200 125,414B w/ v9 markers, `/health build_sha=06919cac`,
  `/hero-haze.webp` 404 as expected; `./scripts/deploy.sh rollback 06919cac`)

## Pre-flight catch (fixed before shipping, `ea2c0fb`)

`fecf312` added `server/static/hero-haze.webp` (56KB) and the hero CSS
`background:url('/hero-haze.webp')` but **no FastAPI route serves it** —
no catch-all, no StaticFiles mount, so the asset would have shipped as a
404 and the hero rendered bare (gate (b) fail). Added
`@app.get("/hero-haze.webp")` → `FileResponse(server/static/hero-haze.webp)`
with `_STATIC_CACHE`, same register as the other landing asset routes
(server/main.py:2012). Also verified the other three surfaces reference
zero external assets — every `url(`/`src=`/`srcset=`/`href=` in
landing/city/community/admin resolves to an existing route.

## Server delta shipped (vs prod 06919cac)

`git diff 06919cac..ea2c0fb7 -- server/` — 10 files, +481/−430:

| file | change |
|---|---|
| `server/landing.html` | v10 rebuild: warm cream register, `.hero-art` smog-scape + live field canvas, 800-weight tight display, ink-bordered cards, pill CTAs, black `ALIVE` footer w/ `buildTag`. |
| `server/city.html` | Same register rewrite (186 lines); zero `text-transform:uppercase`; all tracking ≤ .045em micro. |
| `server/community.html` | Same register rewrite (107 lines); same zero-caps-track. |
| `server/admin.html` | Gate + board restyled to v10 (237 lines); auth/cookie/in-flow untouched. |
| `server/main.py` | +13: `/hero-haze.webp` route (pre-flight fix above). |
| `server/static/hero-haze.webp` | New 56KB generated Delhi smog-scape (India Gate into amber haze). |
| `server/data/corpus/*` | search-depth: corpus 2.6MB→16.8MB gz (344,923 rows) + `aux/overture-places.jsonl.gz` (244,425 NCR Overture rows), STATS.md refresh. |

## Live verification (all on http://65.2.28.40, build ea2c0fb7)

| check | result |
|---|---|
| **(a)** `GET /` | **PASS** — 200, 125,551B. Browser-driven, RENDERED (not grepped): warm cream base; hero card carries the **photographic smog-scape** (amber haze photo visible bleeding the card edge under scrim); 800-weight tight headline "Delhi's air is the worst in the world."; live numeral **75.3 µg/m³** in band ink with `pm2.5 · moderate` pill; "a day outside in this air ≈ 3.4 cigarettes"; "52 stations live · map 4 min fresh · wind 3 km/h"; pill CTAs; ink-bordered field/community rail cards; **black footer with giant `ALIVE` and `build ea2c0fb7`** painted from `/health` = live-sha proof. |
| **(b)** `GET /hero-haze.webp` | **PASS** — 200, `image/webp`, 56,112B (exactly the committed file; 404 pre-deploy on :225). |
| **(c)** `GET /city` | **PASS** — 200, 91,534B HTML. Served bytes: `text-transform:uppercase` ×0; letter-spacing only micro-track `.01em`/negative-tight values (33×`.01em`, rest ≤`.038em`); no letterspaced all-caps labels (residual `[A-Z]{3,}` runs = `ALIVE` brandmark, `AQI`, roman `GRAP stage I` only). |
| **(c)** `GET /community` | **PASS** — 200 (`*/*` → 1,482B JSON; `text/html` → 21,093B HTML). Same audit: `text-transform:uppercase` ×0, tracking ≤ `.01em`, no caps-track labels. |
| **(d)** `GET <mount>` | **PASS** — 200, gate shell carries v10 register in served bytes (`#FBFBFA` ×5, `font-weight:800` ×9, tight tracking only, 0 uppercase transforms, "the engine room"). |
| **(d)** `GET /admin` | **PASS** — 404 honest (22B). |
| **(d)** `GET <mount>/in/x` | **PASS** — 404 honest (22B — byte-identical shape to unknown path). |
| **(d)** login flow | **PASS** — `GET <mount>/in/<real token>` → **303** → clean mount + `Set-Cookie: alive_admin=v1.<ts>.<hmac>; HttpOnly; Max-Age=28800; SameSite=strict`, `cache-control: no-store`, `x-robots-tag: noindex, nofollow`, `referrer-policy: no-referrer`. With cookie: `GET <mount>/session` → `{"authenticated":true}` (anon: false), `GET <mount>/api` → 200 live ops JSON (anon: 401 "admin sign-in required"). Gate-vs-board branch is client-side on the same shell — by design. |
| **(e)** `POST /v2/plan` | **PASS** — 200, 410KB body, **21 options** with real geometry (CP→Noida). |
| **(f)** `GET /health` | **PASS** — `build_sha=ea2c0fb7` = deployed sha, `engine=alive_core`, `ok=true`, `field_stale=false`, `field_age_s=313`, feeds `waqi`+`dpcc`, routing 1,070,459 edges / 903,058 priced. |
| **(g)** CloudWatch alarms | `alive108-field-age`, `alive108-field-emitter-dead`, `alive108-target-down` all `OK`; TG `172.31.31.224` healthy (`172.31.17.182` draining). |

## Notes for the tree

- Asset-route discipline: landing-v10's checklist should include a
  served-URL sweep (`url(`/src/srcset vs `@app.get` table) — every other
  v10 reference resolved, only the hero slipped. The route is now part
  of the shipped surface; any future hero asset needs the same handler.
- `/community` still JSON-negotiates on `Accept: */*` — use
  `Accept: text/html` when checking served HTML bytes.
