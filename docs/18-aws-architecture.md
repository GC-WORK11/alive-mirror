# docs/18 — AWS architecture (deployed)

Rules require AWS in the running system *and visible in the video*.
This is what is actually running — verified live 2026-10-01.

## Architecture (live)

```
Mobile app (Android/iOS, EXPO_PUBLIC_API_URL=http://65.2.28.40)
   |  HTTP
   v
Elastic IP 65.2.28.40 + NLB alive108 :80
   |
   v
ECS Fargate service "alive108"  (1 vCPU / 3 GB, ap-south-1 — task runs
   |  the FastAPI engine + a self-hosted `osrm-routed` sidecar,
   |  `OSRM_URL=127.0.0.1:5000`, OSRM MLD over 4.4M NCR edges)
   |  FastAPI decision engine (server/Dockerfile image)
   +--> ECR repo "alive108-api"          (container image)
   +--> S3 "alive108-build-<acct>/src.zip" -> CodeBuild "alive108-build"
   |      (image is built INSIDE AWS — no local docker needed)
   +--> data/delhi_climatology.json.gz   (decade climatology built from
   |      OpenAQ's public S3 archive — 125 NCR stations × ~10 years;
   |      "9.04M measurements" was the raw-row count, unverified)
   +--> DynamoDB "alive108-agg"          (community aggregates, corridor
   |      cells, per-device ledger — 30-day cell TTL; durable across
   |      redeploys — Fargate's filesystem is ephemeral, the layer is not)
   +--> Secrets Manager "alive108/openaq" + "alive108/waqi" +
   |      "alive108/admin-token"         (never in repo — scripts/deploy.sh)
   +--> EventBridge rollup-daily + validate (one-off Fargate tasks;
   |      infra/schedules/ — ingest-15min DISABLED, in-app loop owns it)
   +--> Open-Meteo / FIRMS-public-csv / Photon / aqicn WAQI (external, free)
```

IAM: `ecsTaskExecutionRole` (image pull / logs) vs `alive108-task` (the
app's own identity — scoped to `s3:GetObject/PutObject` on the
`alive108-air` bucket incl `community/*`, DynamoDB `alive108-agg` R/W,
`geo-maps/places/routes:*`, `cloudwatch:PutMetricData` —
`scripts/deploy.sh` L155-162).

## Why ECS Fargate, not App Runner

`apprunner:CreateService` on a brand-new account returns
`SubscriptionRequiredException` — App Runner needs an account-level
subscription that only a root console can grant. Fargate needs no
subscription, is also serverless, and shows the same skill depth.

## What runs `scripts/deploy.sh` (one command — `server/deploy-aws.sh`
is now a deprecated shim that execs it)

1. zip `server/` → S3 bucket `alive108-build-<acct>`
2. IAM `alive108-codebuild` role (logs + s3:get + ecr) → CodeBuild project
   (privileged, `aws/codebuild/standard:7.0`, env ACCOUNT_ID + AWS_REGION)
   whose `buildspec.yml` does docker build → `docker push` to ECR
3. `ecsTaskExecutionRole` (managed policies) → task def `alive108` (ECR img)
4. SG `alive108` :8080 open → ECS service 1 task, `assignPublicIp=ENABLED`
5. NLB+Elastic IP once, then re-registers the current task's private
   IP so the stable http://65.2.28.40 survives every redeploy

## Video proof (~10 s of console footage)

ECS cluster page (service RUNNING) → task's public IP → phone browser on
`http://<ip>:8080/health` returning JSON → app pointing at the same URL.

## Cost (inside the $200 event credits)

Fargate 1vCPU/3GB ≈ $0.06/hr while running (~$46–50/mo run-rate, ~$36
for the whole event window at Spot pricing), CodeBuild runs inside the
always-free 100 build-min/month, ECR/S3/DynamoDB storage cents. Tell the
user: set a $5 Budgets alarm anyway.
