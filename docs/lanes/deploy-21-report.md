# deploy-21 — server ship report

Shipped `base/v2` server tree to prod. Prod `49a6c226` / task def `:227`
→ `c2f63c9c` / `:228`. Headline ship: **landing-v13** (`0c1559f` —
cognition.com × devin.ai register, the FINAL face for launch: no navbar,
tiny `alive` + text links only; full-bleed generated mist-over-ridge
photograph `hero-nature.webp` 53,554B (preload + LQIP); modest serif
headline `Delhi's air, counted.`; ZERO cards/capsules — every section is
a margin index `001-012` + 1px hairline + content; all live data
UNBOXED as plain text lines (giant hnum still paints in the 'right now'
section; hidden `.hero-data` keeps eyebrow/liveDot/stnHero/fieldair/
toplive/status ids → zero JS changes); feature story = 4 numbered
sections (001 home `ios-dose` · 002 chooser `ios-choose-priced` ·
003 ledger `ios-feat-trips` · 004 week `ios-feat-week`) one serif
purpose line each; 'the field, honestly' ruled journal rows; cognition-
style footer columns + ghost ALIVE; tokens recorded in
`docs/design/web-register.md`). Also riding: `8973d86` perf-size
(Mobile-only — deferred field/city/reports/search-warm fetches +
deep-import fonts; **zero server-facing changes**, verified by diff —
see below), `ce22939` vid-retakes docs, `96789a3` v13 report+shots,
`52ee286` home-polish (Mobile-only), `6659e14` e2e-sweep report+shots
(docs only).

## Deployed

- **commit** `c2f63c9c` (HEAD of base/v2 at deploy time, pushed)
- **image** `185708268748.dkr.ecr.ap-south-1.amazonaws.com/alive108-api:c2f63c9c`
- **task def** `arn:aws:ecs:ap-south-1:185708268748:task-definition/alive108:228`
- **service** alive108/alive108 — new task `4c6a1c31` ENI
  `eni-06b715b64cbfe3080` → `172.31.31.163` registered in TG
  `alive108-tg`; prior target `172.31.25.160` deregistered.
- **CodeBuild** `alive108-build:260edacf-e589-4d14-b2d4-868f8ea5c00e`
  (clean, first try)
- **rollback target** `49a6c226` / `:227`
  (`./scripts/deploy.sh rollback 49a6c226`)

## Pre-flight catch (fixed before shipping, `c2f63c9c`)

The recurring trap, third time: `0c1559f` added **three** new statics —
`server/static/hero-nature.webp`, `ios-feat-trips.webp`,
`ios-feat-week.webp` — and referenced all three from landing.html
(`<link rel="preload">` + `.hero-img url()` / `<img src>`), but **no
FastAPI route served any of them** — would have shipped 404s: hero on
LQIP only + two broken feature frames (gates (a)+(b) fail). Fixes:
`@app.get("/hero-nature.webp")` FileResponse+`_STATIC_CACHE` beside the
hero-haze/hero-alive routes (server/main.py:2042), and a webp-only
`_ios_shot_route` registration loop for `ios-feat-trips`/`ios-feat-week`
(main.py:2011 — no png fallbacks ship for these). Full statics sweep of
the new landing.html: all 12 local refs resolve — `/`, `/city`,
`/community`, `/v2/skill`, `/v2/why`, hero-nature, ios-choose-priced
webp+png, ios-dose webp+png, ios-feat-trips, ios-feat-week.
`py_compile` clean; `/tmp/alive-smoke` venv TestClient sweep: `import
main` OK, all 3 new routes 200 `image/webp`, `/` 200 114,307B with v13
markers, zero forbidden strings.

## Server delta shipped (vs prod 49a6c226)

`git diff 49a6c226..c2f63c9c -- server/`:

| file | change |
|---|---|
| `server/landing.html` | v13 rebuild (1,265 lines changed): navbar/cards killed → margin-index hairline register; `.hero-img` photo; hidden `.hero-data` keeps all live ids. |
| `server/main.py` | +18 (this deploy): `/hero-nature.webp` route + `ios-feat-{trips,week}.webp` factory registrations. |
| `server/static/hero-nature.webp` | New 53,554B generated mist-over-ridge photograph. |
| `server/static/ios-feat-trips.webp` | New 21,368B ledger capture. |
| `server/static/ios-feat-week.webp` | New 32,794B week capture. |
| `server/tests/test_landing_serve.py` | markers updated → `Delhi's air, counted.`, `priced in lungs`. |

(`8973d86`, `52ee286`, `6659e14`, `ce22939` touch **zero** `server/`
files — `git show --stat` verified per commit. Mobile/docs only.)

## Live verification (all on http://65.2.28.40, build c2f63c9c)

| check | result |
|---|---|
| **(a)** `GET /` | **PASS** — 200, 114,307B. Browser-driven, RENDERED: no navbar (tiny `alive` + text links home/the field/delhi/community); full-bleed mist-over-ridge photograph; `Delhi's air, counted.`; live statusline `pm2.5 81.4 µg/m³ · map 4 min fresh`; below-fold 001–006+ numbered sections on hairlines — `81.4` giant numeral, `a day outside … = 3.7 cigarettes`, `52 stations live · 903k road segments priced` all unboxed plain text; 003 ledger + 004 week paint the NEW webps (route fix working in-page); 005 day's arithmetic `81.4 × 14.4 m³/day = ≈1,169 µg ≈ 3.7`; 006 raster field painting band colors `refreshed 10:52 pm IST`; footer ghost ALIVE + 3 columns + **`build c2f63c9c`** painted from `/health` = live-sha proof. ZERO github/download/admin/get-the-app strings (served-source grep = 0). Shots: `deploy-21-shots/prod-v13-*.png` (6). |
| **(b)** `GET /hero-nature.webp` | **PASS** — 200, `image/webp`, 53,554B (the committed file; would have been 404 without the pre-flight fix). `/ios-feat-trips.webp` 200 21,368B + `/ios-feat-week.webp` 200 32,794B — same catch. |
| **(c)** `GET /city` | **PASS** — 200 `text/html`. `GET /community` 200 `application/json` on `*/*`, 200 `text/html` on `Accept: text/html`. |
| **(d)** `GET <mount>` | **PASS** — 200 (`/a-AFiVSpmZ1Oc4YhaaQyhRie5yqnlKV_qs`). `GET /admin` + `/admin/` → honest 404. openapi.json contains 0 mount-path strings (no leak). |
| **(e)** `POST /v2/plan` | **PASS** — 200, `{"from":{28.6315,77.2167},"to":{28.6139,77.2090},"vehicle":"car"}` → 24 options. |
| **(f)** `GET /health` | **PASS** — `build_sha c2f63c9c`, `engine alive_core`, `ok true`. |
| **(g)** alarms | **PASS** — `alive108-field-age` OK, `alive108-field-emitter-dead` OK, `alive108-target-down` OK (cloudwatch describe-alarms ap-south-1). |
| **(h)** `GET /search` | **PASS** — `/search?q=connaught` 200 `application/json`; `/v2/search?q=connaught` 200 `application/json` (`results`+`count`+`t1` on wire). Bare `/search`/`/v2/search` 422 = honest required-param, by design. |

All 8 gates PASS — no rollback. Rollback target stays `49a6c226`/`:227`.
