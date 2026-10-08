# deploy-20 — server ship report

Shipped `base/v2` server tree to prod. Prod `ea2c0fb7` / task def `:226`
→ `49a6c226` / `:227`. Headline ship: **landing-v11** (`ff976ec` —
full-bleed calm Delhi-dawn photograph hero: giant lowercase `alive`
(92→272px clamp) + `the air Delhi breathes — shown live.` + one ghost
pill + `delhi ncr` corner label on the image; live numeral/band/felt/ages
move out of hero chrome into a hidden `.hero-data{display:none}` home —
zero script changes, every live write still lands; `fgiant` ghost-fade
footer; `hero-alive.webp` 72,662B preload+LQIP). Also riding: `d1dc452`
audit-3 server-side fix — `/in/` + `/login` drain ONE rate bucket
(`_BUCKET_CLASS`, middleware.py) since they verify one credential — and
`727ad78`/`0e0ea54`/`96c7c6f` reports+shots. Search-depth server corpus
(`1f188e9`, 344,923-row gazetteer + Overture aux) was already live at
`:226` — covered by gate (h) below.

## Deployed

- **commit** `49a6c22` (HEAD of base/v2 at deploy time)
- **image** `185708268748.dkr.ecr.ap-south-1.amazonaws.com/alive108-api:49a6c226`
- **task def** `arn:aws:ecs:ap-south-1:185708268748:task-definition/alive108:227`
- **service** alive108/alive108 — new task `5ccfba5b` ENI
  `eni-02253e4bafa010c1d` → `172.31.25.160` registered in TG
  `alive108-tg`; prior target `172.31.30.106` deregistered.
- **CodeBuild** `alive108-build:a9b114fc-a80b-4de1-9033-5e5082f2701f`
  (clean, first try)
- **rollback target** `ea2c0fb7` / `:226`
  (`./scripts/deploy.sh rollback ea2c0fb7`)

## Pre-flight catch (fixed before shipping, `49a6c22`)

Same trap as deploy-19: `ff976ec` added `server/static/hero-alive.webp`
and referenced it twice in landing.html (`<link rel="preload">` +
`.hero-img` `url('/hero-alive.webp')`) but **no FastAPI route serves
it** — would have shipped a 404 and rendered the hero on the LQIP
fallback only (gate (b) fail). Added `@app.get("/hero-alive.webp")` →
`FileResponse` with `_STATIC_CACHE` beside the `/hero-haze.webp` route
(server/main.py:2025). Full statics sweep of the new landing.html: every
`url(`/`src=`/`srcset=`/`href=` resolves to an existing route
(ios-*.webp/png factory, `/v2/skill`, `/v2/why`, `#fieldSec` id present
at :763) — hero-alive was the only gap. `py_compile` clean.

## Server delta shipped (vs prod ea2c0fb7)

`git diff ea2c0fb..49a6c22 -- server/`:

| file | change |
|---|---|
| `server/landing.html` | v11 hero rebuild (153 lines): `.hero-card`/`.hero-art` killed → `.hero-img` full-bleed photo + graded scrim; `.hword`/`hline`/`hcta`/`hcorner` type on image; live ids moved into `.hero-data{display:none}`; `fgiant` ghost-fade. |
| `server/middleware.py` | +10: `_BUCKET_CLASS` merges `ADMIN_MOUNT+'/in/'` into the `/login` bucket — one credential, one guess budget (audit-3). |
| `server/static/hero-alive.webp` | New 72,662B generated calm Delhi-dawn skyline (India Gate haze, sage-dawn register). |
| `server/tests/test_admin_auth.py` | +34: audit-3 shared-bucket regression tests. |
| `server/tests/test_landing_serve.py` | markers updated → `hero-img`, `the air Delhi breathes`. |

## Live verification (all on http://65.2.28.40, build 49a6c226)

| check | result |
|---|---|
| **(a)** `GET /` | **PASS** — 200, 125,505B. Browser-driven, RENDERED: full-bleed calm Delhi-dawn photograph (India Gate through haze, dawn sun); giant lowercase `alive`; `the air Delhi breathes — shown live.`; ghost `get the app →` pill; `delhi ncr` corner; **no numeral in hero**; sticky nav pill live-painted `pm2.5 80.0 µg/m³ · map 4 min fresh`; black footer, giant ghost-fade `ALIVE`, **`build 49a6c226`** painted from `/health` = live-sha proof. Shots: `deploy-20-shots/prod-v11-hero.png`, `prod-v11-footer-build.png`. |
| **(b)** `GET /hero-alive.webp` | **PASS** — 200, `image/webp`, 72,662B (exactly the committed file; would have been 404 without the pre-flight fix). |
| **(c)** `GET /city`, `GET /community` | **PASS** — both 200 (`Accept: */*`). |
| **(d)** admin gate | **PASS** — `GET <mount>` 200 (162,661B anon body, unchanged), `GET /admin` 404. |
| **(e)** `POST /v2/plan` | **PASS** — 200, 24 options (`{from,to,vehicle:"car"}` Connaught→Noida-ish). |
| **(f)** `GET /health` | **PASS** — `build_sha=49a6c226`, `engine=alive_core`, feeds `waqi:ok dpcc:ok`. |
| **(g)** CloudWatch alarms | **PASS** — `alive108-field-age`, `alive108-field-emitter-dead`, `alive108-target-down` all `OK`, zero ALARM. |
| **(h)** search/gazetteer | **PASS** — `GET /search?q=connaught` 200 (gazetteer rows incl. new `outside_ncr` flag), `GET /search?q=karol+bagh` 200, `GET /v2/search?q=connaught` 200; `/ios-dose.webp` + `/ios-choose-priced.webp` still 200. |

All 8 gates green — no rollback. Prod runs `49a6c226` / `:227`.
