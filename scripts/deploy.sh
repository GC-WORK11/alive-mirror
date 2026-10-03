#!/usr/bin/env bash
# ALive-108 deploy — image -> ECR -> ECS Fargate redeploy -> NLB target fix.
#
# Pipeline:
#   1. build image (local Docker if available, else AWS CodeBuild from a
#      `git archive` zip of server/ — buildspec.yml MUST sit at the zip root)
#   2. push to ECR (local mode; CodeBuild pushes inside AWS)
#   3. register task definition, force ECS redeploy, wait for stable
#   4. discover the NEW task's ENI private IP and re-register it on the
#      NLB target group (redeploys orphan the old task IP — known outage)
#   5. wait until target-health reports healthy
#
# Usage:
#   AWS_ACCESS_KEY_ID=... AWS_SECRET_ACCESS_KEY=... ./scripts/deploy.sh
# Env overrides: AWS_REGION (ap-south-1), ECS_CLUSTER, ECS_SERVICE, ECR_REPO,
#   TG_NAME, IMAGE_TAG, BUILD_MODE=auto|local|codebuild, SKIP_BUILD=1.
set -euo pipefail

REGION="${AWS_REGION:-ap-south-1}"
export AWS_DEFAULT_REGION="$REGION" AWS_REGION="$REGION"
CLUSTER="${ECS_CLUSTER:-alive108}"
SERVICE="${ECS_SERVICE:-alive108}"
REPO="${ECR_REPO:-alive108-api}"
TG_NAME="${TG_NAME:-alive108-tg}"
NLB_NAME="${NLB_NAME:-alive108}"
PORT="${CONTAINER_PORT:-8080}"
BUILD_MODE="${BUILD_MODE:-auto}"
TAG="${IMAGE_TAG:-$(git rev-parse --short HEAD 2>/dev/null || date +%Y%m%d%H%M%S)}"
ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"

log()  { echo "[deploy] $*"; }
fail() { echo "[deploy] FATAL: $*" >&2; exit 1; }

# run CMD... — echo the exact command, run it, die loudly on failure.
run() {
  echo "+ $*" >&2
  "$@" || fail "command failed (exit $?): $*"
}
# try CMD... — echo the command, run it, never die (create-if-missing probes).
try() {
  echo "+ $* (best-effort)" >&2
  "$@"
}

ACCOUNT="$(run aws sts get-caller-identity --query Account --output text)" \
  || fail "aws sts get-caller-identity — no credentials?"
ECR="$ACCOUNT.dkr.ecr.$REGION.amazonaws.com"
IMG="$ECR/$REPO"
BUILD_BUCKET="alive108-build-$ACCOUNT"

# ---------------------------------------------------------------- 1. build
build_local() {
  log "building locally (docker) -> $IMG:$TAG"
  try aws ecr describe-repositories --repository-names "$REPO" >/dev/null 2>&1 \
    || run aws ecr create-repository --repository-name "$REPO"
  run docker build -t "$IMG:$TAG" -t "$IMG:latest" "$ROOT/server"
  run aws ecr get-login-password \
    | run docker login --username AWS --password-stdin "$ECR"
  run docker push "$IMG:$TAG"
  run docker push "$IMG:latest"
  DEPLOY_IMG="$IMG:$TAG"
}

build_codebuild() {
  # GOTCHA: buildspec.yml must be at the zip ROOT -> archive the server/
  # subtree, not the repo root. `git archive HEAD:server` does exactly that.
  log "building in AWS CodeBuild (no local docker needed)"
  local zip=/tmp/alive108-src.zip
  run git archive --format=zip -o "$zip" "HEAD:server"
  try aws s3 mb "s3://$BUILD_BUCKET" >/dev/null 2>&1 || true
  run aws s3 cp "$zip" "s3://$BUILD_BUCKET/src.zip"

  local trust='{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":{"Service":"codebuild.amazonaws.com"},"Action":"sts:AssumeRole"}]}'
  local policy='{"Version":"2012-10-17","Statement":[
    {"Effect":"Allow","Action":["logs:CreateLogGroup","logs:CreateLogStream","logs:PutLogEvents"],"Resource":"*"},
    {"Effect":"Allow","Action":["s3:GetObject","s3:GetObjectVersion"],"Resource":"*"},
    {"Effect":"Allow","Action":["ecr:GetAuthorizationToken","ecr:CreateRepository","ecr:DescribeRepositories","ecr:BatchCheckLayerAvailability","ecr:GetDownloadUrlForLayer","ecr:BatchGetImage","ecr:InitiateLayerUpload","ecr:UploadLayerPart","ecr:CompleteLayerUpload","ecr:PutImage"],"Resource":"*"}]}'
  try aws iam create-role --role-name alive108-codebuild \
    --assume-role-policy-document "$trust" >/dev/null 2>&1 || true
  run aws iam put-role-policy --role-name alive108-codebuild \
    --policy-name alive108-cb --policy-document "$policy"

  local env="type=LINUX_CONTAINER,image=aws/codebuild/standard:7.0,computeType=BUILD_GENERAL1_SMALL,privilegedMode=true,environmentVariables=[{name=ACCOUNT_ID,value=$ACCOUNT},{name=AWS_REGION,value=$REGION},{name=BUILD_SHA,value=$TAG}]"
  try aws codebuild create-project --name alive108-build \
    --source "type=S3,location=$BUILD_BUCKET/src.zip,buildspec=buildspec.yml" \
    --artifacts type=NO_ARTIFACTS \
    --environment "$env" \
    --service-role "arn:aws:iam::$ACCOUNT:role/alive108-codebuild" \
    --timeout-in-minutes 20 >/dev/null 2>&1 \
  || run aws codebuild update-project --name alive108-build \
    --source "type=S3,location=$BUILD_BUCKET/src.zip,buildspec=buildspec.yml" \
    --environment "$env" >/dev/null

  local bid st
  bid="$(run aws codebuild start-build --project-name alive108-build \
    --query 'build.id' --output text)"
  log "codebuild $bid running…"
  until st="$(aws codebuild batch-get-builds --ids "$bid" \
      --query 'builds[0].buildStatus' --output text)" \
      && [ "$st" != "IN_PROGRESS" ]; do sleep 15; done
  [ "$st" = "SUCCEEDED" ] || fail "codebuild $bid status=$st — see CloudWatch logs"
  DEPLOY_IMG="$IMG:latest"   # buildspec.yml pushes :latest
}

if [ "${SKIP_BUILD:-0}" = "1" ]; then
  DEPLOY_IMG="$IMG:latest"
elif [ "$BUILD_MODE" = "local" ] || { [ "$BUILD_MODE" = "auto" ] && docker info >/dev/null 2>&1; }; then
  build_local
elif [ "$BUILD_MODE" = "codebuild" ] || [ "$BUILD_MODE" = "auto" ]; then
  build_codebuild
else
  fail "unknown BUILD_MODE=$BUILD_MODE (auto|local|codebuild)"
fi
log "deploy image: $DEPLOY_IMG"

# ------------------------------------------------- 2. roles, cluster, task
ETRUST='{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":{"Service":"ecs-tasks.amazonaws.com"},"Action":"sts:AssumeRole"}]}'
try aws iam create-role --role-name ecsTaskExecutionRole \
  --assume-role-policy-document "$ETRUST" >/dev/null 2>&1 || true
run aws iam attach-role-policy --role-name ecsTaskExecutionRole \
  --policy-arn arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy
# execution role also pulls secrets at container start (OPENAQ key)
run aws iam put-role-policy --role-name ecsTaskExecutionRole \
  --policy-name alive108-secrets \
  --policy-document '{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Action":["secretsmanager:GetSecretValue"],"Resource":"arn:aws:secretsmanager:'"$REGION"':'"$ACCOUNT"':secret:alive108/*"}]}'

try aws ecs create-cluster --cluster-name "$CLUSTER" >/dev/null 2>&1 || true

# task role — the app's own identity: S3 air bucket, DDB aggregates,
# community state, Amazon Location (maps/places/routes)
try aws iam create-role --role-name alive108-task \
  --assume-role-policy-document "$ETRUST" >/dev/null 2>&1 || true
run aws iam put-role-policy --role-name alive108-task \
  --policy-name alive108-app --policy-document '{"Version":"2012-10-17","Statement":[
   {"Effect":"Allow","Action":["s3:GetObject","s3:PutObject","s3:ListBucket"],"Resource":["arn:aws:s3:::alive108-air","arn:aws:s3:::alive108-air/*","arn:aws:s3:::'"$BUILD_BUCKET"'/community/*"]},
   {"Effect":"Allow","Action":["dynamodb:PutItem","dynamodb:GetItem","dynamodb:UpdateItem","dynamodb:Query","dynamodb:Scan"],"Resource":"arn:aws:dynamodb:'"$REGION"':'"$ACCOUNT"':table/alive108-agg"},
   {"Effect":"Allow","Action":["geo-maps:*","geo-places:*","geo-routes:*","geo:Search*","geo:GetPlace","geo:ReverseGeocode","geo:CalculateRoute"],"Resource":"*"},
   {"Effect":"Allow","Action":["cloudwatch:PutMetricData"],"Resource":"*"}]}'

TD_ARN="$(run aws ecs register-task-definition \
  --family alive108 --network-mode awsvpc \
  --requires-compatibilities FARGATE --cpu 1024 --memory 2048 \
  --execution-role-arn "arn:aws:iam::$ACCOUNT:role/ecsTaskExecutionRole" \
  --task-role-arn "arn:aws:iam::$ACCOUNT:role/alive108-task" \
  --container-definitions '[{"name":"alive108","image":"'"$DEPLOY_IMG"'","essential":true,
    "portMappings":[{"containerPort":'"$PORT"',"protocol":"tcp"}],
    "environment":[
      {"name":"AWS_REGION","value":"'"$REGION"'"},
      {"name":"COMMUNITY_BUCKET","value":"'"$BUILD_BUCKET"'"},
      {"name":"AIR_BUCKET","value":"alive108-air"},
      {"name":"AGG_TABLE","value":"alive108-agg"},
      {"name":"BUILD_SHA","value":"'"$TAG"'"}],
    "secrets":[{"name":"OPENAQ_API_KEY",
      "valueFrom":"arn:aws:secretsmanager:'"$REGION"':'"$ACCOUNT"':secret:alive108/openaq"}],
    "logConfiguration":{"logDriver":"awslogs","options":{
      "awslogs-group":"/ecs/alive108","awslogs-region":"'"$REGION"'",
      "awslogs-stream-prefix":"api","awslogs-create-group":"true"}}}]' \
  --query 'taskDefinition.taskDefinitionArn' --output text)"
log "task definition: $TD_ARN"

# ------------------------------------------------------- 3. service + NLB
SG="$(aws ec2 describe-security-groups --filters Name=group-name,Values=alive108 \
     --query 'SecurityGroups[0].GroupId' --output text)"
if [ "$SG" = "None" ] || [ -z "$SG" ]; then
  SG="$(run aws ec2 create-security-group --group-name alive108 \
       --description "ALive-108 public API" --query 'GroupId' --output text)"
  run aws ec2 authorize-security-group-ingress --group-id "$SG" \
    --protocol tcp --port "$PORT" --cidr 0.0.0.0/0 >/dev/null
  run aws ec2 authorize-security-group-ingress --group-id "$SG" \
    --protocol tcp --port 80 --cidr 0.0.0.0/0 >/dev/null
fi
SUBNET="$(run aws ec2 describe-subnets --query 'Subnets[0].SubnetId' --output text)"

if ! aws ecs describe-services --cluster "$CLUSTER" --services "$SERVICE" \
     --query 'services[?status==`ACTIVE`].serviceArn' --output text | grep -q .; then
  run aws ecs create-service --cluster "$CLUSTER" --service-name "$SERVICE" \
    --task-definition "$TD_ARN" --desired-count 1 --launch-type FARGATE \
    --network-configuration "awsvpcConfiguration={subnets=[$SUBNET],securityGroups=[$SG],assignPublicIp=ENABLED}"
else
  run aws ecs update-service --cluster "$CLUSTER" --service "$SERVICE" \
    --task-definition "$TD_ARN" --force-new-deployment >/dev/null
fi

# NLB + target group (first deploy only — survives task redeploys)
TG="$(aws elbv2 describe-target-groups --names "$TG_NAME" \
     --query 'TargetGroups[0].TargetGroupArn' --output text 2>/dev/null || echo None)"
if [ "$TG" = "None" ] || [ -z "$TG" ]; then
  VPC="$(run aws ec2 describe-vpcs --query 'Vpcs[0].VpcId' --output text)"
  EIP="$(run aws ec2 allocate-address --domain vpc --query 'PublicIp' --output text)"
  EPIALLOC="$(run aws ec2 describe-addresses --public-ips "$EIP" \
    --query 'Addresses[0].AllocationId' --output text)"
  run aws elbv2 create-load-balancer --name "$NLB_NAME" --type network \
    --subnet-mappings "SubnetId=$SUBNET,AllocationId=$EPIALLOC" >/dev/null
  NLB_ARN="$(run aws elbv2 describe-load-balancers --names "$NLB_NAME" \
    --query 'LoadBalancers[0].LoadBalancerArn' --output text)"
  TG="$(run aws elbv2 create-target-group --name "$TG_NAME" --protocol TCP \
    --port "$PORT" --vpc-id "$VPC" --target-type ip \
    --health-check-protocol HTTP --health-check-path /health \
    --health-check-interval-seconds 30 \
    --query 'TargetGroups[0].TargetGroupArn' --output text)"
  run aws elbv2 create-listener --load-balancer-arn "$NLB_ARN" --protocol TCP \
    --port 80 --default-actions "Type=forward,TargetGroupArn=$TG" >/dev/null
else
  EIP="$(aws ec2 describe-addresses --query 'Addresses[0].PublicIp' --output text)"
fi

# --------------------------------------------- 4. wait, then fix NLB target
log "waiting for service to stabilize (rolling deploy)…"
run aws ecs wait services-stable --cluster "$CLUSTER" --services "$SERVICE"

# Discover the NEWEST running task's ENI -> private IP. GOTCHA: after a
# redeploy the target group still points at the dead task's IP; the NLB
# does NOT follow ECS automatically. Always re-register.
TASKS="$(aws ecs list-tasks --cluster "$CLUSTER" --service-name "$SERVICE" \
  --desired-status RUNNING --query 'taskArns' --output text)"
[ -n "$TASKS" ] && [ "$TASKS" != "None" ] || fail "no RUNNING tasks in $CLUSTER/$SERVICE"
TASK_ARN="$(run aws ecs describe-tasks --cluster "$CLUSTER" --tasks $TASKS \
  --query 'sort_by(tasks, &createdAt)[-1].taskArn' --output text)"

ENI=""; PRIV=""
for _ in $(seq 1 12); do
  ENI="$(aws ecs describe-tasks --cluster "$CLUSTER" --tasks "$TASK_ARN" \
    --query 'tasks[0].attachments[0].details[?name==`networkInterfaceId`].value | [0]' \
    --output text 2>/dev/null || true)"
  [ -n "$ENI" ] && [ "$ENI" != "None" ] && break
  sleep 5
done
[ -n "$ENI" ] && [ "$ENI" != "None" ] || fail "task $TASK_ARN has no ENI attachment"
PRIV="$(run aws ec2 describe-network-interfaces --network-interface-ids "$ENI" \
  --query 'NetworkInterfaces[0].PrivateIpAddress' --output text)"
[ -n "$PRIV" ] && [ "$PRIV" != "None" ] || fail "ENI $ENI has no private IP"
log "new task $TASK_ARN ENI $ENI -> $PRIV"

# deregister EVERY stale target (old task IPs), register the live one
for OLD in $(aws elbv2 describe-target-health --target-group-arn "$TG" \
    --query 'TargetHealthDescriptions[*].Target.Id' --output text); do
  if [ "$OLD" != "$PRIV" ]; then
    run aws elbv2 deregister-targets --target-group-arn "$TG" \
      --targets "Id=$OLD,Port=$PORT"
  fi
done
run aws elbv2 register-targets --target-group-arn "$TG" \
  --targets "Id=$PRIV,Port=$PORT"

STATE=""
for _ in $(seq 1 15); do
  STATE="$(aws elbv2 describe-target-health --target-group-arn "$TG" \
    --targets "Id=$PRIV,Port=$PORT" \
    --query 'TargetHealthDescriptions[0].TargetHealth.State' --output text)"
  [ "$STATE" = "healthy" ] && break
  sleep 12
done
[ "$STATE" = "healthy" ] || fail "target $PRIV never became healthy (last=$STATE) — check /health + SG $SG"

log "STABLE -> http://$EIP  (try /health, /aqi, /decide, /admin)"
