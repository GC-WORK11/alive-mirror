# Alive — Ops handover (verified on this AWS account)

**Purpose.** The second Devin account that owned ops is retired — this doc is
the complete institutional memory for demo-day ops. A stranger with the IAM
user `alive108` credentials should be able to run everything from this file
alone. Every claim below is copied from a command output or endpoint response
actually run; nothing is "should work". Verified **2026-10-07 ~08:30–09:10 UTC**.

**Account.** `185708268748`, region `ap-south-1`, IAM user
`arn:aws:iam::185708268748:user/alive108` (AdministratorAccess).
`aws sts get-caller-identity` returned that ARN verbatim.

**Prod.** `http://alive108-2699c171ddded465.elb.ap-south-1.amazonaws.com`
(NLB `alive108`, EIP `65.2.28.40`, listener :80 → TG `alive108-tg` :8080,
health check `GET /health`). **GET only — never POST anything except
`/v2/plan` and `/v2/reroute`.**

---

## 1. Deploy runbook — for THIS account

Entry point: `./scripts/deploy.sh` (repo root). `server/deploy-aws.sh` is a
8-line shim that `exec`s the same script — identical behavior, kept for
muscle memory. `run()` echoes every AWS call and dies loudly on failure;
`try()` probes never die.

### Preflight (read-only — verified all pass 2026-10-07)

```bash
export AWS_DEFAULT_REGION=ap-south-1
aws sts get-caller-identity                       # → Account 185708268748
aws ecr describe-repositories                     # → alive108-api + alive108-osrm
aws ecs describe-clusters --clusters alive108     # → ACTIVE, 1 running task, 1 svc
aws ecs describe-services --cluster alive108 --services alive108
#   → ACTIVE, task-def alive108:201, desired=running=1, loadBalancers attached,
#     PRIMARY deployment rolloutState COMPLETED, FARGATE_SPOT weight=1 base=1
aws elbv2 describe-load-balancers --names alive108   # → state active, dns above, IP 65.2.28.40
aws elbv2 describe-target-groups --names alive108-tg
#   → TCP:8080, target-type ip, HC HTTP /health every 30s
aws elbv2 describe-target-health \
  --target-group-arn arn:aws:elasticloadbalancing:ap-south-1:185708268748:targetgroup/alive108-tg/f16024d974b4c0bf
#   → 1 target 172.31.19.221:8080 healthy (matches running task ENI eni-059eb9b59857dd71b)
aws codebuild list-projects                       # → alive108-build, alive108-osrm-build, alive108-tiles-build
aws ecs describe-task-definition --task-definition alive108
#   → family alive108 rev 201, cpu 1024 / mem 3072 (OSRM sidecar adds 1GB),
#     exec role ecsTaskExecutionRole, task role alive108-task,
#     containers: alive108 (api:f9ea5ae8, essential) + osrm (osrm:latest, non-essential, 1GB)
aws secretsmanager list-secrets
#   → alive108/openaq, alive108/cpcb, alive108/admin-token, alive108/waqi
aws iam list-roles --query 'Roles[?contains(RoleName,`alive`)||contains(RoleName,`ecsTask`)].RoleName'
#   → alive108-codebuild, alive108-scheduler, alive108-task, ecsTaskExecutionRole
```

### Normal deploy

```bash
cd <repo> && git checkout base/v2 && git pull      # deploys HEAD as :<8-char sha>
./scripts/deploy.sh                                # env: AWS keys already in shell
```

Pipeline (from `scripts/deploy.sh`, read end-to-end 2026-10-07):

1. **Build** — `BUILD_MODE=auto`: local `docker build` if a daemon answers,
   else **CodeBuild**. CodeBuild mode: `git archive HEAD:server` → zip →
   `s3://alive108-build-185708268748/src.zip` → `alive108-build` project
   (`aws/codebuild/standard:7.0`, `server/buildspec.yml` at the **zip root** —
   archiving the repo root breaks it). Every build pushes `:<sha8>` **and**
   `:latest`; the task def pins the sha.
2. **Task def** — new `alive108` revision, cpu 1024 / mem 3072 when the OSRM
   sidecar is on (2048 otherwise), env `OSRM_URL=http://127.0.0.1:5000`,
   `AWS_REGION`, `COMMUNITY_BUCKET=alive108-build-185708268748`,
   `ALIVE_AIR_BUCKET=alive108-air`, `ALIVE_PMTILES`, `AGG_TABLE=alive108-agg`,
   `ALIVE_DPCC_INGEST=1`, `BUILD_SHA`; secrets `OPENAQ_API_KEY`, `WAQI_API_KEY`,
   `ALIVE_ADMIN_TOKEN` from Secrets Manager `alive108/*`.
3. **Redeploy** — `ecs update-service --task-definition <new-arn>
   --force-new-deployment` (service already carries `loadBalancers` in its own
   config — ECS registers each new task ENI itself; verified live: a rollout
   completed 2026-10-07 08:12 UTC with register→drain→steady-state events and
   zero manual intervention).
4. **Wait + verify** — `ecs wait services-stable`, then gate on the PRIMARY
   `rolloutState == COMPLETED` (plain services-stable can return early — the
   script checks the deployment itself). Discovers the new task's ENI →
   private IP, **deregisters every stale target**, re-registers the live IP
   on `alive108-tg`, blocks until `describe-target-health` says `healthy`,
   prints `STABLE -> http://65.2.28.40`.
5. **Post-deploy** — run `python3 tools/warm_task.py` immediately (cold task
   needs ~60–100 s to price the graph; first plan hit ~9–10 s). Details in
   `docs/demo-day.md` §Ops.

### Rollback

```bash
./scripts/deploy.sh rollback <sha>     # e.g. ./scripts/deploy.sh rollback f9ea5ae8
```

Sets `SKIP_BUILD=1 IMAGE_TAG=<sha>` — verifies `:<sha>` exists in ECR (sha
tags are immutable; `aws ecr list-images --repository-name alive108-api`
to list), then runs the identical task-def + NLB pipeline minus the build.
Known-good tags in ECR right now: `f9ea5ae8` (current), `227c25d8`,
`38492947`, `70914c00`, `e0aca004`, `dc6d0cc2`, `aea1c688`, `b12c6b3c`.

### What breaks if X is missing (every failure is loud, never silent)

| Missing | Behavior |
|---|---|
| ECR `alive108-api` repo | local-build mode creates it; CodeBuild role has `ecr:CreateRepository`. `SKIP_BUILD`/`rollback` fails closed: "no image … check tag" |
| ECR `alive108-osrm` image + `OSRM_SIDECAR=1` (default) | deploy **fails** at `describe-images`: "no alive108-osrm — build it first (scripts/geo/buildspec-osrm.yml via alive108-osrm-build) or deploy OSRM_SIDECAR=0" |
| CodeBuild project `alive108-build` | created on first deploy (`create-project`), updated after |
| IAM roles | created + policy (re)written every deploy — role deletion self-heals |
| Security group `alive108` | created with tcp:8080+80 ingress 0.0.0.0/0 (live: `sg-04242ea3003d9cb6f`, 8080 only — NLB fronts :80) |
| NLB/TG/listener | **only created when TG is absent** — full bring-up path allocates a new EIP. Live TG exists, so deploys never touch the EIP `eipalloc-014027e09da2995c4` |
| ECS service | created with `loadBalancers` attached — without that flag a service deploys to **zero targets** (the Oct-3 outage this script now prevents) |
| Secrets `alive108/*` | tasks can't start — rollout never completes, `rolloutState FAILED` |
| Local docker + `BUILD_MODE=auto` | falls through to CodeBuild — **no docker needed on the ops box** |

Kill-switches: `OSRM_SIDECAR=0` (API-only, mem 2048), `SKIP_BUILD=1`,
`IMAGE_TAG=<sha>`, `BUILD_MODE=local|codebuild`, `ECS_CLUSTER`/`ECS_SERVICE`/
`ECR_REPO`/`TG_NAME` overrides.

---

## 2. Alarm map — verified `aws cloudwatch describe-alarms` 2026-10-07

| Alarm | State | Watch | Breach condition | Missing data | Action |
|---|---|---|---|---|---|
| `alive108-field-age` | **OK** | `Alive` / `FieldAgeSeconds`, Maximum, 900 s × 2 | > 2700 s (field inputs stale >45 min) | notBreaching | SNS `alive108-ops` |
| `alive108-field-emitter-dead` | **OK** | `Alive` / `FieldAgeSeconds`, Average, 900 s × 3 | ≤ −1 (dead-man) | **breaching** — silence = ingest worker dead | SNS `alive108-ops` |
| `alive108-target-down` | **OK** | `AWS/NetworkELB` / `HealthyHostCount`, Minimum, 60 s × 2, dims `net/alive108/2699c171ddded465` + `targetgroup/alive108-tg/f16024d974b4c0bf` | < 1 healthy target | **breaching** — right for a down-detector | SNS `alive108-ops` |

**Metric truth (1 h of `get-metric-statistics`, verified):** `StationsUsed`
max 24 every 15 min; `MeanSigma` ~52–64; `FieldAgeSeconds` max 0.0 — honest:
the metric is `max(age_s)` of field **inputs at build time** (`ingest_worker.py`
`_emit_metrics`), and inputs are fetched fresh each cycle. A zero here is a
fresh build, not a stall — the >2700 s alarm only fires when inputs themselves
are stale at build time; age-less provenance emits *nothing* (227c25d8) so
silence means emitter dead. `HealthyHostCount` min 1.0 throughout.

**SNS delivery (verified `list-subscriptions-by-topic`):** topic
`arn:aws:sns:ap-south-1:185708268748:alive108-ops`, one EMAIL subscriber
`<owner-email>` — **subscription state = confirmed** (real
`…:c53694f5-…` SubscriptionArn; a pending sub shows the literal
`PendingConfirmation`). Owner confirmed his email today.

**Known drift vs `infra/provision.sh` — do NOT blindly re-run it:**
- provision.sh writes alarms on namespace `ALive108` — the live metrics are
  `Alive` (`ingest_worker.py:47`). The live alarms were hand-fixed; the
  script's alarm section is stale.
- provision.sh creates `alive108-5xx-rate` over `Http5xx`/`RequestCount` —
  those metrics don't exist; the alarm was **deleted** (always-OK false
  security). Re-running provision would resurrect it.
- Scheduler drift: `alive108-rollup-daily-0030IST` is ENABLED but its expr is
  `cron(30 0 * * ? *)` = 00:30 **UTC** (05:30 IST), not the 00:30-IST the name
  claims. `alive108-validate-weekly` is `cron(30 20 * * ? *)` = **daily**
  20:30 UTC (02:00 IST), not weekly. Both target the ECS cluster via role
  `alive108-scheduler`. `alive108-ingest-15min` is a DISABLED stub — **ingest
  runs inside the API task** (`ALIVE_DPCC_INGEST=1`), not via EventBridge.
- Amazon Location: **no API key exists** (`location list-keys` → `[]`) and
  `/health` reports `sources.location.up=false, key=unset`. Zero Location
  spend possible; nothing to do unless a feature needs it.

Dashboard `ALive-108` exists; log group `/ecs/alive108` (no retention cap);
`aws logs tail /ecs/alive108 --follow` for live logs.

---

## 3. Live numbers card — demo-day truth (verified ~08:40 UTC 2026-10-07)

All values re-derived by `scripts/verify_numbers.sh` against prod —
**zero flags: every quoted figure matches live within stated precision.**

| Surface | Reads right now | Source |
|---|---|---|
| Build / engine | `f9ea5ae8`, `alive_core` | `/health` |
| Graph | 1,070,459 edges / 819,846 nodes, **903,058 priced** | `/health` |
| Field | age ~55–258 s, refresh ~10–14 min, `stale:false` | `/health`, `/v2/city` |
| Stations | **53 instruments** live (`waqi+dpcc`, both feeds ok); 101 model samples | `/health` (accept 52–54; 24 = DPCC-stall degrade) |
| Fires | **44 total / 12 in-belt / 26.2 MW**, feed live, age ~16–20 min, smoke modifier **1.06** @CP | `/aqi`, `/v2/why` |
| PM2.5 @CP | **69.6 breathing / 65.6 ambient µg/m³**, US AQI **156**, nearest real sample 1.8 km | `/aqi` |
| Wind | 4.2 km/h from 187° (S), factor 0.14 | `/health`, `/v2/why` |
| Why-driver | **stagnation** score 0.85 — VC 1,483 m²/s vs ~3,000 typical; BLH 1,648 m, wind 0.9 m/s; trend 64→56 µg (−8) over 6 h/34 builds | `/v2/why` |
| Outlook @CP | today Moderate mid 70.9; **tomorrow Poor 106; Fri + Sat Very Poor 156 / 135** (demo days are Very Poor — heavy hours 20:30–23:30 IST + Fri early AM) | `/v2/outlook` |
| Plan demo OD | 9 options; car 8.7 → walk 287.8 µg, **33.1× slowest/best** (range 31–45× this week) | POST `/v2/plan` |
| Reach (walk 25 µg) | 3,150 edges / ~138 km of street | `/v2/reach` |
| Corridors | **12 publishable / 55 tracked** (k≥3 privacy) | `/v2/city` |
| Community | all-time **44 obs / 24 contributors / 1,278.9 µg avoided**; today 5 obs / 31.4 km / 10.9 µg dose / 312.9 µg avoided; latest obs 86 min old; top corridor Outer Circle (10 samples, 7 devices) | `/community` |
| Dosimeter | day_inhaled 700 µg ≈ 2.22 cigs; annualized walk-vs-car 144 mg vs 4.3 mg | landing/breath |
| Field skill | LOO MAE 8.8 µg, bias +0.2 (n=70); ±2σ coverage 95.4 % over 3,550 pairs / 85 stations | validation artifact |
| Transit | bus + metro compiled, real feeds | `/health` |
| Climatology | 125 stations × ~10 yr | `/health.history` |

Caveats verified on the wire: `community 24h` fields read `None` on
verify-numbers' probe (today's keys renamed `obs_today`/`km_today`/
`dose_ug_today`/`avoided_ug_today` — the 24 h window reads null when the
window is empty; the all-time block is the stable quote); `/aqi`
`station_readings` can sit ±2 off `/health`'s count (per-instrument aging);
plan `took_ms` ~10 s cold, ~sub-second warm — pre-heat before quoting.

---

## 4. Cost posture — verified `aws ce get-cost-and-usage` + `aws budgets`

**MTD gross usage Oct 1–7 (UnblendedCost by service, RECORD_TYPE split):**

| Service | Gross | Credits | Net |
|---|---|---|---|
| Amazon ECS (Fargate Spot) | $3.31 | −$3.31 | $0.00 |
| Elastic Load Balancing (NLB) | $2.84 | −$2.69 | $0.15 |
| CodeBuild | $2.24 | −$2.24 | $0.00 |
| Amazon VPC (public IPv4) | $1.23 | −$1.23 | $0.00 |
| ECR | $0.26 | −$0.26 | $0.00 |
| Secrets Manager | $0.19 | −$0.19 | $0.00 |
| Location Service | $0.16 | −$0.16 | $0.00 |
| AWS Cost Explorer | $0.08 | −$0.08 | $0.00 |
| S3 | $0.04 | −$0.04 | $0.00 |
| DynamoDB (PAY_PER_REQUEST) | $0.03 | −$0.03 | $0.00 |
| Data Transfer | $0.00 | −$0.16 | −$0.16 |
| **Total** | **~$10.4** | | **$0.00** |

- **Net billed last 7 days: $0.00** — promo credits absorb everything.
  Run-rate ≈ **$1.65/day gross ≈ $50/mo** if credits ran out ($10.4 ÷ ~6.3
  elapsed days × 31 — right at the budget cap, so the credits matter).
- **Budget `alive108-monthly`: $50 limit, ActualSpend $0.00,
  ForecastedSpend $16.25, HEALTHY**, alert at 80 % → SNS `alive108-ops`
  (owner email confirmed). Note the forecast reads lower than the
  CE-derived run-rate — it's a projection of *billed* spend after credits,
  not gross usage.
- Billable items (in order): **Fargate Spot** (1 vCPU/3 GB, 24/7 — $3.31 in
  6.3 d ≈ $16/mo), **NLB** ($2.84 ≈ $14/mo + NLCU), **CodeBuild** ($2.24 —
  build-minutes only, zero when nothing deploys), **VPC public IPv4**
  ($1.23 — EIP + task public IP, ≈ $6/mo), ECR storage, Secrets (4),
  Location ($0.16 — past calls, no key now), S3+DDB (pennies), CloudWatch
  (custom metrics + logs — below threshold, no line item).
- Stay-inside-free-tier rule: demo config is already minimal — single
  Fargate Spot task, no NAT (public IPs), on-demand DDB. The credit balance
  is the only thing standing between $0 and ~$50/mo; the budget alarm is the
  tripwire.

---

## 5. What to do if X

**`alive108-target-down` fires / site 502s or times out**
1. `aws ecs describe-services --cluster alive108 --services alive108` —
   running count, events tail (drain/register messages).
2. `aws elbv2 describe-target-health --target-group-arn
   arn:aws:elasticloadbalancing:ap-south-1:185708268748:targetgroup/alive108-tg/f16024d974b4c0bf`
   — a stale dead-IP target is the classic failure.
3. Manual re-register (runbook §3 block, verbatim): list RUNNING tasks →
   newest ENI → private IP → `elbv2 register-targets` → wait `healthy`.
4. If no RUNNING task: `aws ecs update-service --cluster alive108
   --service alive108 --force-new-deployment` — a task serves in ~4 min
   (transit is baked into the image since c3d9c11).
5. `aws logs tail /ecs/alive108 --follow` for the cause (OOM, ingest hang).

**Field stale / `alive108-field-age` fires** (`/health.field_age_s` climbing
past ~2700, `field_stale:true`)
- Ingest runs **inside the API task** (no EventBridge). Check
  `/health.sources`: `stations.feeds.dpcc` stalls ~02:00 IST most nights —
  the 90-min guard drops all 30 DPCC instruments (count 54→24) but the field
  stays fresh; **it recovers alone, do not deploy over it**.
- Check the newest snapshot:
  `aws s3 ls s3://alive108-air/field/$(date +%Y/%m/%d)/ | tail`.
- If snapshots stopped landing → same as emitter-dead below.

**`alive108-field-emitter-dead` fires** (metric silence ≥45 min)
- The in-task ingest worker (`ingest_worker.py`) stopped running or can't
  reach CloudWatch. `aws logs tail /ecs/alive108 --since 1h` → look for
  ingest tracebacks; `aws ecs update-service --force-new-deployment`
  restarts the task.

**Deploy mid-flight failure**
- CodeBuild failed: `aws codebuild batch-get-builds --ids <bid>` +
  CloudWatch logs; fix cause, re-run `./scripts/deploy.sh` (idempotent).
- `rolloutState FAILED`: read service events → usually secrets missing or
  container crash → fix, or `deploy.sh rollback <last-good-sha>`.

**Need the previous build back NOW**
- `./scripts/deploy.sh rollback f9ea5ae8` (or `aws ecr list-images
  --repository-name alive108-api` then pick the sha).

**Spot reclaim on demo morning**
- Expected behavior: ECS replaces the task, ~4 min to serve, NLB
  re-registers itself (loadBalancers attached). Alarms may flap once —
  that's the system working.
- If the owner wants zero reclaim risk for the shoot: the verbatim
  FARGATE_SPOT→FARGATE flip is in `docs/demo-day.md` §Ops (~₹50–100/day —
  **owner call, default is stay Spot**).

**Cost/budget alert**
- `aws ce get-cost-and-usage --region us-east-1 --time-period
  Start=<date>,End=<date> --granularity MONTHLY --metrics UnblendedCost
  --group-by Type=DIMENSION,Key=SERVICE` — find the line that moved.
  Amazon Location can't spend (no key). Biggest movers are Fargate hours
  and NLB.

**Quick "is it alive" sweep (2 min)**
```bash
curl -s http://alive108-2699c171ddded465.elb.ap-south-1.amazonaws.com/health
bash scripts/smoke_live.sh        # GETs + one /v2/plan POST — sanctioned
bash scripts/verify_numbers.sh    # full figure re-derivation, zero-flag = truth
python3 tools/warm_task.py        # also the post-deploy pre-heat
```

---

## Provenance

Verified 2026-10-07 ~08:30–09:10 UTC from this session's own CLI output
(`aws-cli/1.46.1`) and live `curl` responses; `verify_numbers.sh` run ended
zero-flag. Companion docs: `docs/plan/runbook.md` (bring-up/rotate details —
its alarm § is pre-fix, this doc supersedes it), `docs/demo-day.md` §Ops
(Spot flip + warm-task), `docs/plan/NUMBERS.md` (canonical figure ledger),
`docs/plan/handoff.md` cont.68–69 (the alarm surgery this audit confirms).
