# deploy-13 — server ship report

Shipped `base/v2` server tree to prod. Prod `63b7ed42` / task def `:217` →
`61364f31` / `:218`. Headline ship: **the plain-words rewrite** (`61364f3`
— /city felt-words narrative + `story_age_s` so every narrative surface
wears its age ('updated N min ago'), landing de-jargon, community words,
en+hi app strings parallel). Docs-only cargo: demo-vid landing/admin lane
reports + demo-kit final state.

## Deployed

- **commit** `61364f3` (HEAD of base/v2 at deploy time; re-polled
  post-deploy — no mid-flight lane commits landed, nothing newer to carry)
- **image** `185708268748.dkr.ecr.ap-south-1.amazonaws.com/alive108-api:61364f31`
  digest `sha256:551875a9f694858c62dc8d292d1fb51ddf7aef1eb7b13a552d92882af26781df`
- **task def** `arn:aws:ecs:ap-south-1:185708268748:task-definition/alive108:218`
- **service** alive108/alive108 ACTIVE 1/1, task `431eca52` ENI
  `eni-08621284879c8e7df` → `172.31.25.238` registered+healthy in TG
  `alive108-tg`; prior target `172.31.24.166` deregistered.
- **CodeBuild** `alive108-build:20bea483-4006-46c3-a2e9-61e1f829c329`
- **rollback target** `63b7ed42` / `:217` (prev prod, captured pre-deploy
  via `describe-task-definition`)

## Server delta shipped (vs prod 63b7ed42)

One server-touching commit (`git diff 63b7ed42..61364f3 -- server/`);
the rest of the wave is docs/lanes + Mobile/demo-kit:

| files | change |
|---|---|
| `server/v2/why.py` | felt-words cause_note: 'carrying it our way / away from us', 'the usual local air', 'the air is barely moving — clearing at ~N% of its usual pace' (raw m²/s ventilation dropped), 'the city's average climbed/eased'; `_dir_word` map for compass→word; `_line` joins 'and' not '+' |
| `server/v2/city.py` | `story_age_s` added to the `why` block — worst staleness of the narrative's ingredient reads |
| `server/city.html` | narrative row shows 'updated N min ago' from story_age_s; felt-words copy |
| `server/landing.html` | de-jargon pass — 'count of three or more' (was k≥3 aggregates), 'Routing by breath is the proof' (was Dose-priced), 'We hid 3,550 real station readings…95.2% landed inside that band', 'group counts only · never one person · no profiles'; story_age wired into the why-now line |
| `server/community.html` | plain-words ('group counts', never-named phrasing) |
| `server/tests/test_v2_why.py` | expectations updated to new phrasing |

## Live verification (all on http://65.2.28.40, build 61364f31)

| check | result |
|---|---|
| `GET /health` | `build_sha=61364f31`, `engine=alive_core` |
| **(a)** `GET /` | **PASS** — 200 'Alive' title; browser drive: numeral **57.7 µg/m³** painted (PM2.5 · SATISFACTORY), `51 STATIONS LIVE · MAP 4 MIN FRESH · WIND 10 KM/H`; new copy live ('count of three or more', 'Routing by breath'); footer **BUILD 61364F31** painted from /health = live-sha proof. Shots: `deploy-13-shots/landing-live.jpg`, `landing-footer-build.jpg` |
| **(b)** `GET /city` | **PASS** — 200; felt-words narrative live: WHY NOW 'stubble smoke drifting in on the north-west wind'; PARALI WATCH '15 fires in the Punjab–Haryana belt, down from 27 5.8 hours back — a north-west wind at 9.9 km/h is carrying it our way · **updated 4 min ago** · measured, not reported'; 58 µg/m³ AQI 96, 29 districts live. Shot: `deploy-13-shots/city-felt-words.jpg` |
| **(c)** `GET /v2/why` | **PASS** — `story_age_s=168`, line + cause_note in new phrasing; `GET /v2/city` → `why.story_age_s=178`, `why.cause_note` same felt-words text; `field_age_s=167`, `stale=false`, `freshness=live` |
| **(d)** `GET /community` | **PASS** — 200, renders live ledger: 30 phones sharing, 53 trips all-time, 8.6 µg today, 5.5 km today; 'merged, never filed' plain-words cards. Shot: `deploy-13-shots/community.jpg` |
| **(e)** `GET /a-AFiVSpmZ1Oc4YhaaQyhRie5yqnlKV_qs` | **PASS** — 200 + `x-robots-tag: noindex, nofollow`, sign-in gate live |
| **(f)** `GET /admin` | **PASS** — 404 (honest, no redirect) |
| **(g)** `POST /v2/plan` (CP→India Gate, car) | **PASS** — 200, honest route options w/ dose bands on live field |
| CloudWatch alarms | `alive108-field-age`, `alive108-field-emitter-dead`, `alive108-target-down` all `OK` |
| ECS/TG | rollout `COMPLETED` on `:218`; ENI `172.31.25.238` healthy, stale `172.31.24.166` pruned |

No rollback — every required surface verified live on `61364f31`.
