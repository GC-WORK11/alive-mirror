# deploy-8 — server ship report

Shipped `base/v2` server tree to prod. Prod `6bc2b808` / task def `:210` →
`ea5dfb96` / `:213`. Two audit findings surfaced mid-deploy; each got a
fix + redeploy rather than a waived check.

## Deployed

- **commit** `ea5dfb96` (HEAD of base/v2 at deploy time)
- **image** `185708268748.dkr.ecr.ap-south-1.amazonaws.com/alive108-api:ea5dfb96`
  digest `sha256:dcf90f1ce632246b30f6d43ac763e1dff8f9b9fb86d68d89ec24e31cdc45690a`
- **task def** `arn:aws:ecs:ap-south-1:185708268748:task-definition/alive108:213`
- **service** alive108/alive108 ACTIVE 1/1, task `06c3d020` ENI
  `172.31.30.63` registered+healthy in TG `alive108-tg`; prior target draining.
- **CodeBuild** `alive108-build:5ff7e2dd-f9db-4821-a274-9d31fbad19a6`
- intermediate rollouts (superseded within the same lane): `:211` image
  `e22240c5`, `:212` image `869ae214` — the audit fixes below landed between them.

## Server delta shipped (vs prod 6bc2b808)

1. `e147dbd` leftover-fixup DEPLOY-PENDING: `transit_v2.line_name` feed-tag
   strip (paren tails, leading `0`, slug suppression→'Bus') +
   `v2/gazetteer._collapse_same_named` result-level dedupe.
2. `e22240c5` **audit fix 1 — departSavedPct caveat was REAL.** `/depart`
   pinned `'vs now'` percent to `slots[0]`; when the forecast had a gap at
   hour 0, `slots[0]` was hour 1+ and `pct_less_vs_now` compared best
   against a shifted base while still labelled 'vs now'. Now: no
   `hours_ahead==0` slot → `now:null`, `pct_less_vs_now:null`,
   `ug_saved_vs_now:null`. landing.html + DepartGraph handle `now:null`
   (no invented 'now is the light slot'). Test:
   `test_depart_missing_now_hour_serves_null_not_shifted_base`.
3. `869ae214` **audit fix 2 — `/v2/search` merge dedupe gap.** The
   endpoint's `_merge` collapsed same-name rows only ≤75 m, so the
   'Connaught Place' district↔macrohood pair (117 m) shipped two rows on
   the wire — the client's `sameNamedPlace` hid it in-app only, and the
   new `GAZ.search` collapse never ran on prod (T1 engine is
   `alive_core`). `_merge` now mirrors the client rule (<400 m when
   either kind is district/administrative; admin row yields its slot).
   Tests: `test_merge_collapses_admin_container_beyond_75m`,
   `test_merge_keeps_same_name_neighbours`.
4. `ea5dfb96` **audit fix 3 — dotted feed ids leaked.** Live prod served
   `Bus AIRPORTEXP.-4` on the CP→IGI OD: the slug class `[A-Z0-9_-]`
   missed `.`. Widened to `[A-Z0-9_.-]` + `LETTERS[.-]NUM`; first
   `line_name` test coverage (15 cases).

Plus `test_today_ledger_serves_todays_real_numbers` flake fix
(`offset_h` 1→0 — 'now-1h' crossed the UTC day boundary in the first
hour of a run).

## Live verification (all on http://65.2.28.40, build ea5dfb96)

| check | result |
|---|---|
| `GET /` landing | 200, 1.16 s |
| `GET /health` | `ok`, `build_sha=ea5dfb96`, field_age 152 s, `field_stale=false`, transit feeds on disk |
| `GET /aqi?lat=28.6139&lon=77.2090` | pm25 69.0, us_aqi 154, not beyond-field-edge |
| `GET /city` | 200, 0.94 s |
| `POST /v2/plan` CP→IGI | 24 options, no error |
| transit leg names | metro `Orange/Airport`; bus leg `line:"Bus"` (was `AIRPORTEXP.-4` before fix 3) |
| `GET /v2/search?q=connaught` | ONE `Connaught Place` row (macrohood wins the collapsed slot); district row gone; Connaught Lane pair correctly kept distinct (600 m apart) |
| `GET /depart` CP→IGI auto | `now` = hour-0 slot, `pct_less_vs_now` = `ug_saved_vs_now` = 3 |
| CloudWatch alarms | `alive108-field-age`, `alive108-field-emitter-dead`, `alive108-target-down` all `OK` |
| ECS/TG | service ACTIVE 1/1 on `:213`; new ENI healthy |

## Local gates

- `pytest tests` on `server/` (`PYTHONPATH=core/build312:.`): 1173 pass.
  First run showed 4 env-only failures, all resolved: alive_core .so was
  mid-build (re-run passed), p95 latency assert under build CPU
  contention (passed on re-run), UTC-midnight flake (test fix above).
- New tests: `test_depart_missing_now_hour_serves_null_not_shifted_base`,
  `test_merge_collapses_admin_container_beyond_75m`,
  `test_merge_keeps_same_name_neighbours`, 16 `line_name` cases.

## Rollback

`./scripts/deploy.sh rollback 6bc2b808` re-points the service at the
prior image (still in ECR). Task def `:210` remains registered.
