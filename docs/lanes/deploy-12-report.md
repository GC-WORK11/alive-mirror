# deploy-12 — server ship report

Shipped `base/v2` server tree to prod. Prod `05a3b4bd` / task def `:216` →
`63b7ed42` / `:217`. Headline ship: **the 'Alive' rebrand** (`0c5f9cc` —
the 108 dropped from every user-visible surface; wordmark now `ALIVE`,
titles 'Alive — …', FastAPI `Alive API`), the **freshness-fix** (`a7814cb`
— 8 numbers that could sit stale>15min while reading live; server side:
`/v2/city` STALE_S 2×TTL→1×TTL so 'live' never outlives one cadence,
`/city` poll refresh clamp), and the **city+community taste pass**
(`b04d544` + report `63b7ed4` — v8 register: sans-300 numerals, tonal
pills, ambient shadows; whyline/µg-case/forecast-cache fixes).

## Deployed

- **commit** `63b7ed4` (HEAD of base/v2 at deploy time)
- **image** `185708268748.dkr.ecr.ap-south-1.amazonaws.com/alive108-api:63b7ed42`
  digest `sha256:82c5e4054f5fd1517d02029f17cfd216a30ab4ed91b1df0b6cb299462d56f361`
- **task def** `arn:aws:ecs:ap-south-1:185708268748:task-definition/alive108:217`
- **service** alive108/alive108 ACTIVE 1/1, task `b717777a` ENI
  `eni-088432baf9f2827fd` → `172.31.20.142` registered+healthy in TG
  `alive108-tg`; prior target `172.31.27.154` deregistered.
- **CodeBuild** `alive108-build:3fba7264-7366-42a8-94aa-f040f0e80d23`
- **rollback target** `05a3b4bd` / `:216` (prev prod, captured pre-deploy)

## Wait-gate

Held for the city-taste lane per brief — it landed mid-gate at ~06:58 UTC
(`b04d544` + `63b7ed4`), so the deploy carries all four commits
(`a7814cb`, `0c5f9cc`, `b04d544`, `63b7ed4`). Deploy started 06:59 UTC.

## Server delta shipped (vs prod 05a3b4bd)

3 server-touching commits in the 12-commit wave (`git diff 05a3b4b..63b7ed4 --
server/`; the rest is Mobile/docs):

| commit | surface | change |
|---|---|---|
| `a7814cb` freshness-fix | `server/v2/city.py`, `server/city.html`, `server/landing.html`, `server/tests/test_v2_city.py` | STALE_S = `_FIELD_TTL` (was 2×) — 'live' label never outlives one cadence; `/city` poll caps refresh_in_s at 10min; landing timeline cell_epoch stamp + 900s touched floor + invalidate on field rebuild/visibility re-entry; landing daybar re-marks 'now' on the 120s beat; wind tags print '· Nm old' past one cadence; boundary pinned in tests |
| `0c5f9cc` rebrand | `server/landing.html`, `server/city.html`, `server/community.html`, `server/admin.html`, `server/main.py`, `server/tiles.py`, UA strings | wordmark `ALIVE` (was `ALIVE·108`), titles/og/boot-strips 'Alive — …', FastAPI `title="Alive API"`, tilejson name, admin 'engine room' label. Kept: AWS names/tags, repo URLs, ids, git history |
| `b04d544` city-taste | `server/city.html`, `server/community.html` | v8 register — sans-300 numerals, tonal pills, ambient shadows; whyline hidden fix, µg case, forecast-cache TTL, refresh clamp (report `63b7ed4`) |

## Live verification (all on http://65.2.28.40, build 63b7ed42)

| check | result |
|---|---|
| `GET /health` | `build_sha=63b7ed42`, `engine=alive_core` |
| **(a)** `GET /` landing boot | **PASS** — 200; browser drive: boot strip completes, numeral **54.2 µg/m³** painted (PM2.5 · SATISFACTORY, 'LIVE · THE NCR-WIDE AVERAGE'), `52 STATIONS LIVE · MAP 5 MIN FRESH · WIND 3 KM/H`; title 'Alive — a personal dosimeter for Delhi air', wordmark `ALIVE` — zero `·108` literals in the html; 'get the app' CTA in nav + body → github releases. Shot: `deploy-12-shots/landing-after-boot.jpg` |
| **(b)** `GET /city` | **PASS** — 200 `text/html`, title 'Alive — Delhi NCR air, district by district', `ALIVE` wordmark + LIVE chip w/ IST clock; live numbers: **54 µg/m³** AQI 91 'SATISFACTORY', 29 districts live, heaviest Central North Delhi 135, GRAP stage I note, parali watch (15 fires). Shot: `deploy-12-shots/city.jpg` |
| **(b)** `GET /community` | **PASS** — 200 (`application/json` on `*/*`, `text/html` on `Accept: text/html` — unchanged negotiation), title 'Alive — everyone's trips, merged', `ALIVE` wordmark; live ledger: 29 phones sharing, 52 trips all-time, 5.4 µg today, 2.4 km today. Shot: `deploy-12-shots/community.jpg` |
| **(c)** `GET /a-AFiVSpmZ1Oc4YhaaQyhRie5yqnlKV_qs` | **PASS** — 200, 'ALIVE / engine room' wordmark, OPERATOR ONLY sign-in gate live. Shot: `deploy-12-shots/admin-login.jpg` |
| **(d)** `GET /admin` | **PASS** — 404 (honest, no redirect) |
| **(e)** `GET /openapi.json` | **PASS** — `info.title = "Alive API"`, 57 paths, zero admin-bearing paths; only 'admin' literals in the whole doc are `admin_level=5` (OSM term in the delhi_subdistricts geojson description) — zero console leak |
| **(f)** `GET /v2/city` honesty | **PASS** — `field.age_s=208`, `stale=false`, `freshness.label=live` at 208s < 900s TTL; code boundary now `STALE_S = _FIELD_TTL` (1×, was 2×) — 'live' can never outlive one cadence; `wind.age_s=224` |
| **(g)** `POST /v2/plan` (CP→India Gate, car) | **PASS** — 23 options, dose bands on live field (avg_conc ~40 µg/m³, confidence high, coverage 1.0), took 310ms |
| CloudWatch alarms | `alive108-field-age`, `alive108-field-emitter-dead`, `alive108-target-down` all `OK` |
| ECS/TG | rollout stable on `:217`; ENI `172.31.20.142` healthy, stale `172.31.27.154` pruned |

No rollback — every required surface verified live on `63b7ed42`.
