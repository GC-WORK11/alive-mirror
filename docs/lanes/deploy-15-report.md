# deploy-15 — server ship report

Shipped `base/v2` server tree to prod. Prod `30af6b17` / task def `:219` →
`dd2aec33` / `:220`. Headline ships: **honesty-cluster server diffs**
(`2babf6d` — server-stamped today, suggested-ceiling disclosure, UTC-day
counter labels, search substitute marks, CO₂ counted/plan basis labels;
F2 F4 F6 F7 F8) + **landing dead-anchor fix** (`dd2aec3` — `id="fieldSec"`
restored on the field panel the v8-sync lane caught missing).

## Deployed

- **commit** `dd2aec33` (HEAD of base/v2 at deploy time)
- **image** `185708268748.dkr.ecr.ap-south-1.amazonaws.com/alive108-api:dd2aec33`
  digest `sha256:30f4fac8f94cbcf61a51ccf04e391b63acab8108b29b7f6b861034b3d2695376`
- **task def** `arn:aws:ecs:ap-south-1:185708268748:task-definition/alive108:220`
- **service** alive108/alive108 ACTIVE 1/1, task `6423b596` ENI
  `eni-032fe48a8478611d1` → `172.31.30.159` registered+healthy in TG
  `alive108-tg`; prior target `172.31.23.252` deregistered (draining).
- **CodeBuild** `alive108-build:c49112c5-ba63-4220-91ac-24345302a133`
- **rollback target** `30af6b17` / `:219` (prev prod, captured pre-deploy
  via `describe-task-definition`; `./scripts/deploy.sh rollback 30af6b17`)

## Server delta shipped (vs prod 30af6b17)

`git diff 30af6b17..dd2aec33 -- server/` — 4 files, +18/−7 (the commit's
Mobile-side honesty diffs don't ride the server image):

| file | change |
|---|---|
| `server/community.html` | F8 — intro line names the UTC day ("they reset at 05:30 IST"); counter strip prints `today = utc day · resets 05:30 ist` inline, not only in a hover title |
| `server/city.html` | F8 — ticker rows relabelled `shared trips · utc day` / `km shared · utc day`, matching the ledger head's 'counted since utc midnight' |
| `server/admin.html` | CO₂ tile gains `· counted-basis`; F6 split caption says the shares are **plan-basis** (donated receipts' planned-route phase estimate) while the counted kg is measured along each actual ride — the two bases never reconcile by construction |
| `server/landing.html` | `id="fieldSec"` on the field panel — the dead anchor the v8-sync port caught |

## Live verification (all on http://65.2.28.40, build dd2aec33)

| check | result |
|---|---|
| **(a)** `GET /` | **PASS** — 200, 95.5 KB board. Hero numeral nodes (`hnumA/B/T/V/W`) present; JS paints footer `BUILD` from `/health` (fetches `/health`, refs `build_sha`) = live-sha proof. `/aqi` live: pm2.5 **80.8 µg/m³** at CP — the numeral's source |
| **(b)** `GET /community` | **PASS** — 200; UTC-day qualification rendered in counters HTML: `utc day · resets 05:30 ist` + intro `UTC day — they reset at 05:30 IST.` |
| **(c)** `GET /city?q=connaught` + `/v2/city` | **PASS** — 200; felt-words live (`why.line` "stubble smoke drifting in on the north-west wind", `cause_note` + `cause_note_fields.basis=measured`); age stamps live (`freshness.label=live`, `age_min=3`, `field_age_s=206`, `story_age_s=220`; page paints `min ago · nearest read`) |
| **(d)** `GET <mount>/` | **PASS** — 200, 162.5 KB + `x-robots-tag: noindex, nofollow` |
| **(d)** `GET /admin` | **PASS** — 404 (honest, no redirect) |
| **(d)** `GET <mount>/in/bogustoken123` | **PASS** — 404 (hash-login gate rejects honestly, no oracle leak) |
| **(e)** `POST /v2/plan` (CP→Sarai Kale Khan) | **PASS** — honest 200: 23 options on the live field (97 samples, 52 station readings, `source=waqi+dpcc-stations+open-meteo/cams`), per-option `basis` labels, `took_ms=6318` |
| **(f)** `GET /health` | **PASS** — `build_sha=dd2aec33` = deployed sha, `engine=alive_core`, `ok=true`, `field_stale=false`, `field_age_s≈150–210` |
| **(g)** CloudWatch alarms | `alive108-field-age`, `alive108-field-emitter-dead`, `alive108-target-down` all `OK` |
| ECS/TG | rollout `COMPLETED` on `:220`; `172.31.30.159` healthy, `172.31.23.252` draining |

## Mid-flight drift (for next ship, not this one)

Re-polled `origin/base/v2` post-deploy: two commits landed during the
rollout — `e0bac51` (bug-hunter v2: 5 defects — dead #fieldSec anchor
companion fix, GRAP 'stage 0' contradiction, counted-day air-age leak,
spark hour-count, silent district strip) and `2db17fb` (demo-vid-android
report). Prod intentionally runs `dd2aec33` per this brief; both are
queued for the next deploy.

No rollback — every required surface verified live on `dd2aec33`.
