# docs/18 — AWS architecture (deployed)

Rules require AWS in the running system *and visible in the video*.
This is what is actually running — verified live 2026-10-01.

## Architecture (live)

```
Mobile app (Android/iOS, EXPO_PUBLIC_API_URL=http://13.235.89.248:8080)
   |  HTTP
   v
ECS Fargate service "alive108"  (1 vCPU / 2 GB, public IP, ap-south-1)
   |  FastAPI decision engine (server/Dockerfile image)
   +--> ECR repo "alive108-api"          (container image)
   +--> S3 "alive108-build-<acct>/src.zip" -> CodeBuild "alive108-build"
   |      (image is built INSIDE AWS — no local docker needed)
   +--> data/delhi_climatology.json.gz   (9M-measurement decade product,
   |      built from OpenAQ's public S3 archive, baked into image)
   +--> Open-Meteo / OSRM / Photon / OpenAQ-v3 (external, free)
```

## Why ECS Fargate, not App Runner

`apprunner:CreateService` on a brand-new account returns
`SubscriptionRequiredException` — App Runner needs an account-level
subscription that only a root console can grant. Fargate needs no
subscription, is also serverless, and shows the same skill depth.

## What runs `deploy-aws.sh` (server/deploy-aws.sh — one command)

1. zip `server/` → S3 bucket `alive108-build-<acct>`
2. IAM `alive108-codebuild` role (logs + s3:get + ecr) → CodeBuild project
   (privileged, `aws/codebuild/standard:7.0`, env ACCOUNT_ID + AWS_REGION)
   whose `buildspec.yml` does docker build → `docker push` to ECR
3. `ecsTaskExecutionRole` (managed policies) → task def `alive108` (ECR img)
4. SG `alive108` :8080 open → ECS service 1 task, `assignPublicIp=ENABLED`
5. prints the live public URL (~75s to healthy)

## Video proof (~10 s of console footage)

ECS cluster page (service RUNNING) → task's public IP → phone browser on
`http://<ip>:8080/health` returning JSON → app pointing at the same URL.

## Cost (inside the $200 event credits)

Fargate 1vCPU/2GB ≈ $0.05/hr while running (~$36 for the whole event
window), CodeBuild runs inside the always-free 100 build-min/month,
ECR/S3 storage cents. Tell the user: set a $5 Budgets alarm anyway.
