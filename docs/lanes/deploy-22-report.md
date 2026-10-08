# deploy-22 — v14 landing to prod

- **Shipped:** `fb5cbb79` → image `alive108-api:fb5cbb79`, task def `alive108:229`, STABLE on http://65.2.28.40 (~12 min CodeBuild path, one-shot env exec)
- **Rollback target:** `c2f63c9c` / `:228` (`./scripts/deploy.sh rollback c2f63c9c`)
- **Rode along:** `6b63dbe` v14 landing + `8b62cdc` scorer-prior (core_engine internals, no route delta) + `6af18e1` data-truth (docs + scripts/research only) + `70b733b` v14 shots

## Pre-flight catch — the statics trap, fourth recurrence

v14 (`6b63dbe`) shipped `server/static/hero-delhi-smog.webp` (56,634 B) + swapped the preload/CSS off `hero-nature.webp` — **but no FastAPI route**. Same failure class as deploy-19 (`hero-haze`), deploy-20 (`hero-alive`), deploy-21 (`hero-nature` + 2 ios-feat). Baseline confirmed it: prod answered `404` on `/hero-delhi-smog.webp` while still on `:228`; the hero would have shipped as a dead image.

**Fix:** `/hero-delhi-smog.webp` FileResponse handler added at `main.py:2055` (commit `fb5cbb7`), matching the hero-* convention, `_STATIC_CACHE` 1h. The full asset sweep this ship: landing.html references → `/hero-delhi-smog.webp`, `/ios-{dose,choose-priced}.{webp,png}`, `/ios-feat-{trips,week}.webp`, `/ncr.geojson`, `/delhi_subdistricts.geojson`, `/v2/*` fetches — every one route-covered after the fix.

**Server diff since `:228`** (`git diff c2f63c9c..HEAD -- server/`): only `alive_core_ref.py` (+6), `core_engine.py` (+346 scorer-prior internals — no new/changed routes), `landing.html` (+100 v14), the new webp. **No admin.html change, no new /v2/* endpoints** — admin-analytics rebuild and stays/playtime endpoints did not land by pull-time.

**Local gate** (proven recipe): `py_compile` clean; fresh `/tmp/alive-venv312` (brew py3.12, fastapi httpx numpy h3 boto3 python-dotenv) `import main` + TestClient sweep — 26 paths, zero ≥500, `/hero-delhi-smog.webp` 200/56,634 B, `/admin` honest-404, `<mount>` 200/162,661 B, `POST /v2/plan` 200.

## Verify gates — all PASS on prod

| gate | result |
|---|---|
| (f) `/health` | `build_sha: fb5cbb79`, `engine: alive_core`, field_age 132 s, 1,070,459 edges / 903,058 priced |
| (a) `/` RENDERED | delhi-smog India Gate hero full-bleed; left rail (`alive` + home/the field/delhi/community, `position:fixed;left:0`); grotesque lead + serif prose; margin indices 001–013; ruled districts leaderboard — "29 real boundaries, each filled live", numbered rows + boundary thumbs + right-aligned live aqi (worst-first 271…205); raw iOS shots (dose / choose-priced / feat-trips / feat-week — no bezel); ZERO navbar·boxes·github·download strings (only "no navbar" comments), `dosimeter` count 0; live data painting — **87.7 µg/m³**, pm2.5·moderate chip, "a day outside ≈ 4.0 cigarettes", 53 stations · map 3–5 min fresh · wind 6 km/h · 903k segments priced, why/forecast/record sections all live; footer `build fb5cbb79` |
| (b) hero asset | `/hero-delhi-smog.webp` → 200 `image/webp` 56,634 B |
| (c) surfaces | `/city` 200 (91,534 B) · `/community` 200 (JSON on `*/*`) |
| (d) admin | `<mount>` 200 (162,661 B console) · `<mount>/` 200 · `/admin` 404 · `<mount>/in/<wrong>` 404 (22 B honest-404) |
| (e) `POST /v2/plan` | 200 — 21 options (`from/to/vehicle` body) |
| (g) alarms | `alive108-field-age` OK · `alive108-field-emitter-dead` OK · `alive108-target-down` OK |
| (h) endpoints | `/search?q=connaught` 200 · `/v2/search?q=connaught` 200 · `/v2/city` · `/v2/districts` · `/v2/skill` · `/v2/reverse` · `/v2/why` · `/today` · `/v2/today` · both geojsons · all ios shots → all 200 |

New-rev proof: TG cutover `172.31.31.163` → `172.31.30.207`, footer sha flip `c2f63c9c` → `fb5cbb79` painted from `/health` by the page's own JS.

## Durable lessons

- **The statics-sweep gate is now 4-for-4 catching real breakage.** Every landing reskin (v10, v11, v13, v14) has added exactly one or more new statics with zero routes. Run the sweep before every deploy.sh: extract `url()/src/srcset/href/preload` refs from `landing.html`, diff vs the `@app.get`+router table, add `FileResponse` handlers for gaps.
- Both venvs get wiped with /tmp — recreate per session: `/opt/homebrew/bin/python3.12 -m venv /tmp/alive-venv312` + pip `fastapi httpx numpy 'h3>=4' boto3 python-dotenv`; `~/.aws-venv` + `awscli` for deploy.sh.
- `loading="lazy"` feat shots can look blank mid-scroll on prod — settle ~2 s before judging a "missing" image; the earlier white box was `ios-feat-trips.webp` mid-load, not a bug.

## Shots

`deploy-22-shots/`: 01 hero (India Gate smog) · 02 live 87.7 numeral + rail statusline · 03–06 raw feat shots (dose/choose/trips/week) · 07 live field map · 08 why+forecast+record · 09 ruled districts · 10 footer `build fb5cbb79`.
