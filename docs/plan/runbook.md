# ALive-108 — Ops runbook

Region: `ap-south-1` everywhere. Live service: ECS service `alive108` (cluster
`alive108`, Fargate) behind NLB `alive108` at **65.2.28.40** (`http://65.2.28.40`,
listener :80 → target group `alive108-tg` :8080, health check `GET /health`).

## 1. Deploy

```bash
AWS_ACCESS_KEY_ID=… AWS_SECRET_ACCESS_KEY=… ./scripts/deploy.sh
```

Pipeline (`scripts/deploy.sh`; `server/deploy-aws.sh` is a thin wrapper):

1. **Build.** `BUILD_MODE=auto` (default): local `docker build` if a daemon is
   reachable, else AWS CodeBuild. CodeBuild mode archives `git archive
   --format=zip HEAD:server` so `buildspec.yml` sits at the **zip root** —
   zipping the repo root breaks the build (known gotcha). CodeBuild pushes
   `:latest`; local mode pushes `:$GIT_SHA` + `:latest`.
2. **Task def.** New `alive108` revision: image + env (`AIR_BUCKET`,
   `AGG_TABLE`, `BUILD_SHA`, …) + secret `OPENAQ_API_KEY` ←
   `secretsmanager:alive108/openaq`.
3. **Redeploy.** `ecs update-service --force-new-deployment`, then
   `ecs wait services-stable`.
4. **NLB fix.** The NLB does **not** follow ECS — after a redeploy it keeps
   sending traffic to the dead task's private IP (known outage). The script
   finds the newest RUNNING task's ENI (`describe-tasks` →
   `networkInterfaceId` → `ec2 describe-network-interfaces`), deregisters
   every stale target, registers the live IP, and blocks until
   `describe-target-health` = `healthy`.

Dry-run / partial: `SKIP_BUILD=1` redeploys `:latest` without a build.
Overrides: `ECS_CLUSTER`, `ECS_SERVICE`, `ECR_REPO`, `TG_NAME`, `IMAGE_TAG`.

## 2. Rollback

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
  `secretsmanager:GetSecretValue` on `alive108/*`). Rotate: update the secret
  value, `SKIP_BUILD=1 ./scripts/deploy.sh`. Never commit keys — the repo has
  none by design.
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

- **Budget `alive108-monthly`** — alerts at 80% of `${MONTHLY_BUDGET_USD:-50}`
  via SNS `alive108-ops` (set `OPS_EMAIL` before provisioning for email).
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
./infra/provision.sh --dry-run     # prints every command, executes nothing
./infra/provision.sh               # S3, DDB, schedules, dashboard, alarms, budget, Location key
./infra/provision.sh --glacier     # + field/ -> GLACIER after 90d lifecycle
```

Scheduler targets are stubs (schedules created DISABLED) until you export
`INGEST_TARGET_ARN` / `ROLLUP_TARGET_ARN` / `VALIDATE_TARGET_ARN` /
`SCHEDULER_ROLE_ARN` and re-run.
