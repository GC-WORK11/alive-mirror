# Alive — Ops runbook

Region: `ap-south-1` everywhere. Live service: ECS service `alive108` (cluster
`alive108`, Fargate) behind NLB `alive108` at **65.2.28.40** (`http://65.2.28.40`,
listener :80 → target group `alive108-tg` :8080, health check `GET /health`).

## 0. Phase-0 bring-up — run top-to-bottom

Owner gates (plan 00 open items): **[B1] IAM scope**, **[B2] OpenAQ/CPCB key**,
**[B3] spend cap**. Each gates the step it is called out on — do not skip past.

**Step 0 — credentials.** *Gate [B1]: the IAM principal needs `sts`, `iam`
(create/put-role-policy), `ecr`, `ecs`, `elbv2`, `ec2`, `s3`, `dynamodb`,
`scheduler`, `cloudwatch`, `sns`, `secretsmanager`, `geo:*`, and `budgets` +
billing on us-east-1.*
```bash
aws sts get-caller-identity
# → {"Account": "123456789012", "Arn": "arn:aws:iam::…"} — anything else: stop.
```

**Step 1 — dry-run provision (no AWS calls).**
```bash
DRY_RUN=1 ./infra/provision.sh      # or ./infra/provision.sh --dry-run
# → "# check: …" + "+ aws …" lines for every resource;
#   ends "(dry-run — nothing was executed)"
```

**Step 2 — provision.** *Gate [B3]: owner sets the monthly cap + alert email
now — `alive108-monthly` is the only hard stop for Amazon Location spend too.*
```bash
export ALIVE_MONTHLY_BUDGET_USD=50 OPS_EMAIL=ops@example.com
# optional — without these the 3 schedules are created DISABLED stubs:
# export SCHEDULER_ROLE_ARN=… INGEST_TARGET_ARN=… ROLLUP_TARGET_ARN=… \
#        VALIDATE_TARGET_ARN=…
./infra/provision.sh
# → "=== provision done ==="  (S3, DDB, schedules, dashboard, 2 alarms,
#   budget, 2 secret scaffolds, Location key)
```

**Step 3 — real data keys.** *Gate [B2]: scaffolds hold `{"api_key":"REPLACE_ME"}`;
until real values land, ingest runs degraded (CAMS model + stale OpenAQ
archive) and `/health` must say so.*

> **Update 2026-10-06:** stations are live — `alive108/waqi` (24 instruments)
> and the DPCC adapter (30) feed the field without OpenAQ; `alive108/cpcb`
> is a dead path (data.gov.in TCP-refused). The task also needs
> `alive108/admin-token` for the console api (unlisted mount — `docs/plan/admin-login.md`) — both wired by
> `scripts/deploy.sh`'s secrets block.

```bash
aws secretsmanager put-secret-value --region ap-south-1 \
  --secret-id alive108/openaq --secret-string '{"api_key":"<REAL_OPENAQ_V3_KEY>"}'
aws secretsmanager put-secret-value --region ap-south-1 \
  --secret-id alive108/waqi  --secret-string '{"api_key":"<REAL_AQICN_TOKEN>"}'
# → {"VersionId": "…"} each. Keys never enter git — this script included.
```

**Step 4 — deploy.**
```bash
./scripts/deploy.sh
# → "[deploy] STABLE -> http://<eip>" — builds (local docker else CodeBuild),
#   pushes :<8-char sha> + :latest, redeploys ECS, re-registers NLB target.
```

**Step 5 — verify** (plan 09 Phase-0 accept):
```bash
curl -s http://<eip>/health | jq '{build_sha, field_age_s, sources}'
# → build_sha = pushed sha tag; field_age_s null until first ingest (ok on day 0)
aws budgets describe-budget --region us-east-1 --account-id <acct> \
  --budget-name alive108-monthly --query 'Budget.BudgetLimit'
# → {"Amount": "50", "Unit": "USD"} (your cap)
aws cloudwatch describe-alarms --alarm-names alive108-field-age alive108-5xx-rate \
  --query 'MetricAlarms[].StateValue'
# → ["INSUFFICIENT_DATA"|"OK", …] — field-age goes OK once metrics flow
aws location describe-key --key-name alive108-app \
  --query 'Key.Restrictions.AllowActions'
# → maps/places/routes actions only. Console: CloudWatch → Dashboards → ALive-108.
```

**Rollback:** `./scripts/deploy.sh rollback <sha>` — redeploys the image tag CI
already pushed, same pipeline minus the build (§2).

## 1. Deploy

```bash
AWS_ACCESS_KEY_ID=… AWS_SECRET_ACCESS_KEY=… ./scripts/deploy.sh
```

Pipeline (`scripts/deploy.sh`; `server/deploy-aws.sh` is a thin wrapper):

1. **Build.** `BUILD_MODE=auto` (default): local `docker build` if a daemon is
   reachable, else AWS CodeBuild. CodeBuild mode archives `git archive
   --format=zip HEAD:server` so `buildspec.yml` sits at the **zip root** —
   zipping the repo root breaks the build (known gotcha). Every build —
   local or CodeBuild — pushes `:<8-char sha>` **and** `:latest`; the ECS
   task def pins the sha tag (`:latest` is a moving convenience tag only).
2. **Task def.** New `alive108` revision: image + env (`AIR_BUCKET`,
   `AGG_TABLE`, `ALIVE_DPCC_INGEST=1`, `ALIVE_PMTILES`, `BUILD_SHA`, …)
   + secrets `OPENAQ_API_KEY`, `WAQI_API_KEY`, `ALIVE_ADMIN_TOKEN` ←
   `secretsmanager:alive108/openaq` / `alive108/waqi` / `alive108/admin-token`
   (`scripts/deploy.sh` L195-215).
3. **Redeploy.** `ecs update-service --force-new-deployment`, then
   `ecs wait services-stable`.
4. **NLB fix.** The NLB does **not** follow ECS — after a redeploy it keeps
   sending traffic to the dead task's private IP (known outage). The script
   finds the newest RUNNING task's ENI (`describe-tasks` →
   `networkInterfaceId` → `ec2 describe-network-interfaces`), deregisters
   every stale target, registers the live IP, and blocks until
   `describe-target-health` = `healthy`.

Dry-run / partial: `SKIP_BUILD=1` redeploys `:${IMAGE_TAG:-latest}` without a
build (fails if the tag is not in ECR). Overrides: `ECS_CLUSTER`,
`ECS_SERVICE`, `ECR_REPO`, `TG_NAME`, `IMAGE_TAG`.

## 2. Rollback

Fastest — redeploy the last good image tag CI pushed (builds are immutable
`:<sha>` tags; list them with `aws ecr list-images --repository-name alive108-api`):

```bash
./scripts/deploy.sh rollback <sha>   # e.g. ./scripts/deploy.sh rollback 6fada20c
```

It verifies the tag exists in ECR, registers a task def on `:<sha>`, forces a
deployment and re-runs the NLB fix — identical path to a deploy minus the build.

Manual alternative — point the service at the previous task-def revision:

```bash
# find the previous task-def revision
aws ecs list-task-definitions --family-prefix alive108 \
  --sort DESC --query 'taskDefinitionArns[1]' --output text

aws ecs update-service --cluster alive108 --service alive108 \
  --task-definition <prev-arn> --force-new-deployment
# then re-run the NLB fix — easiest is:
SKIP_BUILD=1 ./scripts/deploy.sh   # or the manual block below
```

For a bad image, retag the last good one in ECR and redeploy; the ECS service
keeps the old task alive until the new target is `healthy`.

## 3. NLB re-register — manual fallback

If the API is up (`curl http://<task-ip>:8080/health`) but the NLB 502s/timeout:

```bash
TG=$(aws elbv2 describe-target-groups --names alive108-tg \
     --query 'TargetGroups[0].TargetGroupArn' --output text)
TASKS=$(aws ecs list-tasks --cluster alive108 --service-name alive108 \
        --desired-status RUNNING --query 'taskArns' --output text)
ENI=$(aws ecs describe-tasks --cluster alive108 --tasks $TASKS \
      --query 'sort_by(tasks,&createdAt)[-1].attachments[0].details[?name==`networkInterfaceId`].value|[0]' \
      --output text)
IP=$(aws ec2 describe-network-interfaces --network-interface-ids $ENI \
     --query 'NetworkInterfaces[0].PrivateIpAddress' --output text)
aws elbv2 register-targets --target-group-arn $TG --targets Id=$IP,Port=8080
aws elbv2 describe-target-health --target-group-arn $TG   # wait for "healthy"
```

## 4. Secrets

- **Secrets Manager `alive108/openaq`** — OpenAQ v3 key. Injected into the
  container as env `OPENAQ_API_KEY` (execution role has
  `secretsmanager:GetSecretValue` on `alive108/*`). **`alive108/waqi`** —
  aqicn token feeding the live WAQI instruments; **`alive108/admin-token`**
  — Bearer for the console api (unlisted mount). **`alive108/cpcb`** —
  data.gov.in/CPCB hourly feed key, read by the worker only (dead path —
  data.gov.in TCP-refused). All are
  scaffolded by `provision.sh` with `{"api_key":"REPLACE_ME"}` placeholders —
  real values go in via `put-secret-value` (§0 step 3). Rotate: update the
  secret value, `SKIP_BUILD=1 ./scripts/deploy.sh`. Never commit keys — the
  repo has none by design.
- Amazon Location key `alive108-app` (provision.sh): scoped to
  `geo-maps:GetTile/GetStaticMap`, `geo-places:Autocomplete/Suggest`,
  `geo-routes:CalculateRoutes`, expires `${LOCATION_KEY_DAYS:-90}`d.
- No user DB; DynamoDB `alive108-agg` holds aggregates only (TTL 30d on
  corridor cells).

## 5. Health & freshness

```bash
curl -s http://65.2.28.40/health | jq
# build_sha, version, field_age_s, sources{model,stations,fires,location}, uptime_s
```

- `field_age_s`: seconds since the newest snapshot under
  `data/field/snapshots` (mirrors `s3://alive108-air/field/YYYY/MM/DD/`).
  `null` = no snapshot ever landed → ingest broken. CloudWatch alarm
  **alive108-field-age** breaches >45 min (missing data = breaching).
- Ingest failures: `IngestFailures` metric (dashboard + alarm), EventBridge
  Scheduler console → `alive108` group → invocation history, and worker logs:
  `aws logs tail /ecs/alive108 --follow`.
- Quick S3 check:
  `aws s3 ls s3://alive108-air/field/$(date +%Y/%m/%d)/ --region ap-south-1 | tail`

## 6. Cost watch

- **Budget `alive108-monthly`** — alerts at 80% of
  `${ALIVE_MONTHLY_BUDGET_USD:-50}` via SNS `alive108-ops`; `OPS_EMAIL` also
  adds a direct EMAIL subscriber to the budget at create time
  (legacy env `MONTHLY_BUDGET_USD` still read).
- Big-ticket items: NLB hourly (~$16/mo + NLCU), Fargate 1×(1 vCPU/2 GB)
  (~$30/mo if 24/7), CloudWatch metrics/alarms, NAT (avoid — tasks use public
  IPs), S3→Glacier lifecycle (`./infra/provision.sh --glacier`).
- Amazon Location free tier: 500k tiles / 10k suggest / 10k routes per month
  for 3 months — the API key is action-scoped; a public launch blows past it
  (see plan 00 open item 3).
- `aws budgets describe-budget --region us-east-1 --account-id <acct>
  --budget-name alive108-monthly` or console → Cost Explorer.

## 7. Provisioning (one time / drift repair)

```bash
DRY_RUN=1 ./infra/provision.sh     # or --dry-run: prints every command, executes nothing
./infra/provision.sh               # S3, DDB, schedules, dashboard, alarms, budget, secrets, Location key
./infra/provision.sh --glacier     # + field/ -> GLACIER after 90d lifecycle
```

Scheduler targets are stubs (schedules created DISABLED) until you export
`INGEST_TARGET_ARN` / `ROLLUP_TARGET_ARN` / `VALIDATE_TARGET_ARN` /
`SCHEDULER_ROLE_ARN` and re-run.
