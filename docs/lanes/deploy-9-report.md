# deploy-9 — server ship report

Shipped `base/v2` server tree to prod. Prod `ea5dfb96` / task def `:213` →
`585a7171` / `:214`. Single-purpose ship: the `_t1_pos` wire-contract fix
from union-regression-v2 (leak was live on prod, confirmed below).

## Deployed

- **commit** `585a717` (HEAD of base/v2 at deploy time)
- **image** `185708268748.dkr.ecr.ap-south-1.amazonaws.com/alive108-api:585a7171`
  digest `sha256:4ea5b4e52703c795f2529d9c0185cb1533b12b88284872be1428eee06c2a2ce7`
- **task def** `arn:aws:ecs:ap-south-1:185708268748:task-definition/alive108:214`
- **service** alive108/alive108 ACTIVE 1/1, task `04e191ee` ENI
  `172.31.31.105` registered+healthy in TG `alive108-tg`; prior target
  `172.31.30.63` deregistered. Rollout `COMPLETED`.
- **CodeBuild** `alive108-build:e7725cab-8eb1-483c-a993-bfc68bcda098`

## Server delta shipped (vs prod ea5dfb96)

One commit touched `server/`: `585a717` (union-regression-v2). Full diff
= `server/v2/search.py` +6/−1 — `_merge` now strips `_t1_pos` merge-scratch
from the `t1 + t2` source lists, not just `merged`. A row that loses the
widened 400 m admin dedupe stays in `t1_rows`, and the endpoint returns
that array raw → the scratch key rode the wire. No other server changes
(the commit's other files are Mobile t0 + the lane report).

### Before / after (live prod, `GET /v2/search?q=connaught`)

- **before** (`ea5dfb96`): `t1[2]` `Connaught Place` macrohood row carried
  `"_t1_pos": 2` — the dedupe loser leaking scratch. `results` already
  correct (one CP row).
- **after** (`585a7171`): `_t1_pos` count in entire response = **0**.
  `results` still one `Connaught Place` (macrohood wins the collapsed
  slot); `t1` diagnostic array still honestly lists both engine rows,
  now scratch-free. Contract
  `test_contract_sync.py::test_nested_place_and_strip_rows` restored.

## Live verification (all on http://65.2.28.40, build 585a7171)

| check | result |
|---|---|
| `GET /health` | `ok`, `build_sha=585a7171`, field_age 135 s, `field_stale=false` |
| `GET /v2/search?q=connaught` | 6 results, ONE `Connaught Place` row; `_t1_pos` nowhere in response (was on `t1[2]` pre-deploy) |
| `GET /` landing | 200, 1.16 s, 118.8 kB |
| `GET /city` | 200, 0.93 s, 89.1 kB |
| `GET /aqi?lat=28.6139&lon=77.2090` | pm25 66.2, us_aqi 152 |
| `POST /v2/plan` CP→IGI | 24 options, no error; metro `Orange/Airport`, bus `Bus` — no feed-id slugs on the wire |
| `GET /depart` CP→IGI auto | `now` = hour-0 slot (dose 18.5 µg, conc 61.1), `pct_less_vs_now` = `ug_saved_vs_now` = 1 |
| CloudWatch alarms | `alive108-field-age`, `alive108-field-emitter-dead`, `alive108-target-down` all `OK` |
| ECS/TG | service PRIMARY rollout `COMPLETED` on `:214`; new ENI healthy, stale target pruned |

## Local gates

- `pytest tests/test_contract_sync.py tests/test_v2.py` (fresh `.venv312`,
  `PYTHONPATH=core/build312:.`): **85 pass** — incl. the `_t1_pos` wire
  contract + the admin-collapse probes. Full suite (1262p/5s) was run by
  union-regression-v2 on this exact tree; not re-run here.
- Note for future deploy lanes on this box: no `aws` CLI, no docker —
  awscli went in `~/awsenv` (pip, py3.12); deploy.sh ran the CodeBuild
  path. Secrets inject into one-shot shells only — persistent `shell_id`
  shells start without them (first deploy attempt failed on
  `sts get-caller-identity`; re-ran as one-shot).

## Rollback

`./scripts/deploy.sh rollback 6bc2b808` re-points the service at the
prior image (still in ECR). Task def `:210` remains registered;
intermediate `:213` (`ea5dfb96`) also remains registered.
