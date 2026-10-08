#!/usr/bin/env bash
# Alive infra provisioning — idempotent create-if-missing.
#
# Resources (all tagged Project=ALive-108, all in ${AWS_REGION:-ap-south-1}):
#   S3 bucket alive108-air        private, AES256, optional Glacier@90d (--glacier)
#   DynamoDB alive108-agg         PAY_PER_REQUEST, pk/sk, TTL attr `ttl`
#   EventBridge Scheduler group alive108:
#     alive108-ingest-15min       rate(15 minutes)
#     alive108-rollup-daily-0030IST   cron(30 19 * * ? *)  (00:30 IST = 19:00 UTC)
#     alive108-validate-weekly    cron(0 20 ? * SUN *)     (Sun 20:00 UTC = Mon 01:30 IST)
#   CloudWatch dashboard ALive-108   (infra/dashboard.json)
#   Alarms: field-age>45min, 5xx>1% (+ SNS topic alive108-ops)
#   Budget alive108-monthly          80% of ${ALIVE_MONTHLY_BUDGET_USD:-50}
#                                    (legacy env MONTHLY_BUDGET_USD also read;
#                                    OPS_EMAIL adds a direct EMAIL subscriber)
#   Secrets Manager scaffolds        alive108/openaq, alive108/cpcb — created
#                                    with placeholder {"api_key":"REPLACE_ME"};
#                                    fill real values out-of-band (runbook §4)
#   Amazon Location API key alive108-app  scoped actions + ${LOCATION_KEY_DAYS:-90}d expiry
#
# Scheduler targets are STUBS unless you export real ARNs:
#   INGEST_TARGET_ARN / ROLLUP_TARGET_ARN / VALIDATE_TARGET_ARN
#   SCHEDULER_ROLE_ARN   (role EventBridge assumes to RunTask)
# Stubbed schedules are created DISABLED so nothing fires against a fake ARN.
#
# Usage:
#   ./infra/provision.sh [--dry-run] [--glacier] [--region REGION]
#   DRY_RUN=1 ./infra/provision.sh   # same as --dry-run: prints, never calls AWS
# Env: AWS_REGION, ALIVE_MONTHLY_BUDGET_USD (or MONTHLY_BUDGET_USD),
#      GLACIER_DAYS, LOCATION_KEY_DAYS,
#      LOCATION_KEY_RESOURCES (comma-sep ARNs), OPS_EMAIL,
#      INGEST_TARGET_ARN, ROLLUP_TARGET_ARN, VALIDATE_TARGET_ARN, SCHEDULER_ROLE_ARN.
set -euo pipefail

REGION="${AWS_REGION:-ap-south-1}"
DRY_RUN="${DRY_RUN:-0}"
GLACIER=0
while [ $# -gt 0 ]; do
  case "$1" in
    --dry-run) DRY_RUN=1 ;;
    --glacier|--enable-glacier) GLACIER=1 ;;
    --region) REGION="$2"; shift ;;
    -h|--help) sed -n '1,30p' "$0"; exit 0 ;;
    *) echo "unknown flag: $1" >&2; exit 2 ;;
  esac
  shift
done
export AWS_DEFAULT_REGION="$REGION" AWS_REGION="$REGION"

AIR_BUCKET="alive108-air"
AGG_TABLE="alive108-agg"
SCHED_GROUP="alive108"
DASH_NAME="ALive-108"
SNS_TOPIC="alive108-ops"
BUDGET_NAME="alive108-monthly"
LOC_KEY="alive108-app"
TAGS="Project=ALive-108"
GLACIER_DAYS="${GLACIER_DAYS:-90}"
LOCATION_KEY_DAYS="${LOCATION_KEY_DAYS:-90}"
MONTHLY_BUDGET_USD="${ALIVE_MONTHLY_BUDGET_USD:-${MONTHLY_BUDGET_USD:-50}}"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ACCOUNT: real one from STS, or a readable placeholder under --dry-run.
if [ "$DRY_RUN" = 1 ]; then
  ACCOUNT="${AWS_ACCOUNT_ID:-<ACCOUNT_ID>}"
else
  ACCOUNT="$(aws sts get-caller-identity --query Account --output text)" \
    || { echo "no AWS credentials — aborting" >&2; exit 1; }
fi

echo "=== Alive provision  region=$REGION account=$ACCOUNT dry_run=$DRY_RUN glacier=$GLACIER ==="

# run CMD...  — print the exact command; skip execution under --dry-run.
run() {
  echo "+ $*"
  [ "$DRY_RUN" = 1 ] && return 0
  "$@"
}
# check CMD... — existence probe; real mode: silent, true if the call succeeds.
# dry-run: prints the probe and returns 1 so create commands are always shown.
check() {
  echo "# check: $*"
  [ "$DRY_RUN" = 1 ] && return 1
  "$@" >/dev/null 2>&1
}
note() { echo "# $*"; }

# ---------------------------------------------------------------- S3 bucket
note "S3 bucket $AIR_BUCKET (private)"
if check aws s3api head-bucket --bucket "$AIR_BUCKET"; then
  note "exists — skip create"
else
  if [ "$REGION" = "us-east-1" ]; then
    run aws s3api create-bucket --bucket "$AIR_BUCKET" --region "$REGION"
  else
    run aws s3api create-bucket --bucket "$AIR_BUCKET" --region "$REGION" \
      --create-bucket-configuration "LocationConstraint=$REGION"
  fi
fi
run aws s3api put-public-access-block --bucket "$AIR_BUCKET" \
  --public-access-block-configuration \
  "BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true"
run aws s3api put-bucket-encryption --bucket "$AIR_BUCKET" \
  --server-side-encryption-configuration \
  '{"Rules":[{"ApplyServerSideEncryptionByDefault":{"SSEAlgorithm":"AES256"}}]}'
run aws s3api put-bucket-tagging --bucket "$AIR_BUCKET" \
  --tagging 'TagSet=[{Key=Project,Value=ALive-108}]'
if [ "$GLACIER" = 1 ]; then
  note "lifecycle: field/ snapshots -> GLACIER after ${GLACIER_DAYS}d"
  run aws s3api put-bucket-lifecycle-configuration --bucket "$AIR_BUCKET" \
    --lifecycle-configuration '{"Rules":[{"ID":"snapshots-to-glacier","Status":"Enabled","Filter":{"Prefix":"field/"},"Transitions":[{"Days":'"$GLACIER_DAYS"',"StorageClass":"GLACIER"}]}]}'
else
  note "pass --glacier to add field/ -> GLACIER lifecycle (${GLACIER_DAYS}d)"
fi

# ------------------------------------------------------------- DynamoDB agg
# docs/plan/05 §4: PK holds `day#2026-10-09` or `cell#<h3>`, SK `mode#metro` —
# generic attribute names pk/sk; TTL attribute `ttl` expires corridor cells (30d).
note "DynamoDB table $AGG_TABLE (PAY_PER_REQUEST, pk/sk, ttl)"
if check aws dynamodb describe-table --table-name "$AGG_TABLE"; then
  note "exists — skip create"
else
  run aws dynamodb create-table --table-name "$AGG_TABLE" \
    --attribute-definitions AttributeName=pk,AttributeType=S AttributeName=sk,AttributeType=S \
    --key-schema AttributeName=pk,KeyType=HASH AttributeName=sk,KeyType=RANGE \
    --billing-mode PAY_PER_REQUEST \
    --tags Key=Project,Value=ALive-108
  run aws dynamodb wait table-exists --table-name "$AGG_TABLE"
fi
run aws dynamodb update-time-to-live --table-name "$AGG_TABLE" \
  --time-to-live-specification "Enabled=true,AttributeName=ttl"

# ------------------------------------------------------ EventBridge schedules
note "EventBridge Scheduler group $SCHED_GROUP + 3 schedules"
try_role="${SCHEDULER_ROLE_ARN:-arn:aws:iam::$ACCOUNT:role/alive108-scheduler-STUB}"
if check aws scheduler get-schedule-group --name "$SCHED_GROUP"; then
  note "group exists — skip"
else
  run aws scheduler create-schedule-group --name "$SCHED_GROUP" \
    --tags Key=Project,Value=ALive-108
fi

schedule() { # $1 name  $2 expr  $3 env-var-of-target-arn  $4 job-input
  local name="$1" expr="$2" tvar="$3" input="$4"
  local target="${!tvar:-arn:aws:ecs:$REGION:$ACCOUNT:task/alive108/STUB-$name}"
  local state="ENABLED" warn=""
  case "$target" in *STUB*) state="DISABLED"; warn="  [STUB — set $tvar to enable]";; esac
  note "schedule $name: '$expr' -> $target$warn"
  run aws scheduler create-schedule --name "$name" --group-name "$SCHED_GROUP" \
    --schedule-expression "$expr" \
    --schedule-expression-timezone "UTC" \
    --state "$state" \
    --flexible-time-window "Mode=OFF" \
    --target "Arn=$target,RoleArn=$try_role,Input=$input" \
    || run aws scheduler update-schedule --name "$name" --group-name "$SCHED_GROUP" \
      --schedule-expression "$expr" --schedule-expression-timezone "UTC" \
      --state "$state" --flexible-time-window "Mode=OFF" \
      --target "Arn=$target,RoleArn=$try_role,Input=$input"
  run aws scheduler tag-resource \
    --resource-arn "arn:aws:scheduler:$REGION:$ACCOUNT:schedule/$SCHED_GROUP/$name" \
    --tags Key=Project,Value=ALive-108 2>/dev/null || true
}
schedule alive108-ingest-15min          'rate(15 minutes)'      INGEST_TARGET_ARN   '{"job":"ingest"}'
schedule alive108-rollup-daily-0030IST  'cron(30 19 * * ? *)'   ROLLUP_TARGET_ARN   '{"job":"rollup"}'
schedule alive108-validate-weekly       'cron(0 20 ? * SUN *)'  VALIDATE_TARGET_ARN '{"job":"validate"}'

# ------------------------------------------------------------------ SNS ops
note "SNS topic $SNS_TOPIC (alarm + budget notifications)"
TOPIC_ARN="arn:aws:sns:$REGION:$ACCOUNT:$SNS_TOPIC"
run aws sns create-topic --name "$SNS_TOPIC" --tags Key=Project,Value=ALive-108
if [ -n "${OPS_EMAIL:-}" ]; then
  run aws sns subscribe --topic-arn "$TOPIC_ARN" --protocol email \
    --notification-endpoint "$OPS_EMAIL" || true
else
  note "OPS_EMAIL unset — no subscription (alarms still visible in console)"
fi

# ---------------------------------------------------------- CW dashboard
note "CloudWatch dashboard $DASH_NAME (infra/dashboard.json)"
DASH_BODY="$(sed "s/\${AWS_REGION}/$REGION/g" "$HERE/dashboard.json")"
if [ "$DRY_RUN" = 1 ]; then
  echo "+ aws cloudwatch put-dashboard --dashboard-name $DASH_NAME --dashboard-body <rendered infra/dashboard.json>"
else
  run aws cloudwatch put-dashboard --dashboard-name "$DASH_NAME" \
    --dashboard-body "$DASH_BODY"
fi

# ------------------------------------------------------------------ alarms
note "alarm: field age >45min (missing data = ingest is dead = breach)"
run aws cloudwatch put-metric-alarm \
  --alarm-name alive108-field-age \
  --namespace ALive108 --metric-name FieldAgeSeconds \
  --statistic Maximum --period 300 --evaluation-periods 1 \
  --threshold 2700 --comparison-operator GreaterThanThreshold \
  --treat-missing-data breaching \
  --alarm-actions "$TOPIC_ARN" \
  --tags Key=Project,Value=ALive-108

note "alarm: HTTP 5xx >1% of requests (metric math over ALive108 ns)"
run aws cloudwatch put-metric-alarm \
  --alarm-name alive108-5xx-rate \
  --evaluation-periods 2 --datapoints-to-alarm 2 \
  --threshold 1 --comparison-operator GreaterThanThreshold \
  --treat-missing-data notBreaching \
  --metrics '[
    {"Id":"e1","Expression":"100*m5xx/mreq","Label":"5xx %","ReturnData":true,"Period":300},
    {"Id":"m5xx","MetricStat":{"Metric":{"Namespace":"ALive108","MetricName":"Http5xx"},"Period":300,"Stat":"Sum"},"ReturnData":false},
    {"Id":"mreq","MetricStat":{"Metric":{"Namespace":"ALive108","MetricName":"RequestCount"},"Period":300,"Stat":"Sum"},"ReturnData":false}
  ]' \
  --alarm-actions "$TOPIC_ARN" \
  --tags Key=Project,Value=ALive-108

note "budget: $BUDGET_NAME — alert at 80% of \$${MONTHLY_BUDGET_USD}/mo"
# Budgets is a global service — its only endpoint is us-east-1.
# Subscribers: SNS topic always; OPS_EMAIL adds a direct EMAIL subscriber.
BUDGET_SUBS='{"SubscriptionType":"SNS","Address":"'"$TOPIC_ARN"'"}'
if [ -n "${OPS_EMAIL:-}" ]; then
  BUDGET_SUBS="$BUDGET_SUBS"',{"SubscriptionType":"EMAIL","Address":"'"$OPS_EMAIL"'"}'
fi
if check aws budgets describe-budget --region us-east-1 \
     --account-id "$ACCOUNT" --budget-name "$BUDGET_NAME"; then
  note "exists — skip create"
else
  run aws budgets create-budget --region us-east-1 --account-id "$ACCOUNT" \
    --budget '{
      "BudgetName":"'"$BUDGET_NAME"'","BudgetType":"COST","TimeUnit":"MONTHLY",
      "BudgetLimit":{"Amount":"'"$MONTHLY_BUDGET_USD"'","Unit":"USD"}
    }' \
    --notifications-with-subscribers '[
      {"Notification":{"NotificationType":"ACTUAL","ComparisonOperator":"GREATER_THAN","Threshold":80,"ThresholdType":"PERCENTAGE"},
       "Subscribers":['"$BUDGET_SUBS"']}
    ]' \
    --resource-tags '[{"Key":"Project","Value":"ALive-108"}]' || \
  note "budget create failed (budgets API needs us-east-1 endpoint + billing access)"
fi

# -------------------------------------------- Secrets Manager scaffolds
# Placeholder values ONLY — {"api_key":"REPLACE_ME"}. Never put real keys in
# this script or the repo; fill them out-of-band (runbook §4). Creating the
# entries here means the ECS task def can reference them and nothing crashes
# before the owner's keys land — the app must treat REPLACE_ME as missing.
note "Secrets Manager scaffolds alive108/openaq + alive108/cpcb (REPLACE_ME placeholders)"
secret_scaffold() { # $1 secret name  $2 what-it-is-for
  local name="$1" purpose="$2"
  if check aws secretsmanager describe-secret --secret-id "$name"; then
    note "exists — skip create (rotate: aws secretsmanager put-secret-value)"
  else
    run aws secretsmanager create-secret --name "$name" \
      --description "ALive-108: $purpose — REPLACE_ME placeholder, set real value out-of-band" \
      --secret-string '{"api_key":"REPLACE_ME"}' \
      --tags Key=Project,Value=ALive-108
  fi
}
secret_scaffold "alive108/openaq" "OpenAQ v3 API key (env OPENAQ_API_KEY in the task def)"
secret_scaffold "alive108/cpcb"  "data.gov.in / CPCB hourly station feed key"

# ------------------------------------------------------ Amazon Location key
# SPEND-LIMIT GUIDANCE (owner blocker — plan 00 open item 3):
# Amazon Location has NO per-key spend cap. The only guardrails are:
#   1. AllowActions scoped below (maps/places/routes only, no geofences etc.)
#   2. AllowResources — export LOCATION_KEY_RESOURCES="arn:aws:geo:.../map/…,…/place-index/…,…/route-calculator/…"
#      before launch; "*" is demo-only.
#   3. The alive108-monthly AWS Budget above — the real money stop.
#   4. A usage alarm: CW billing metric EstimatedCharges filtered to the
#      Location service (us-east-1 only) — wire it if the owner sets a
#      dedicated Location cap.
# Free tier: 500k tiles / 10k suggest / 20k geocode / 10k routes per month,
# 3 months only. A public launch blows past it — demo key only until the
# owner approves the spend cap.
note "Amazon Location API key $LOC_KEY (restricted actions, ${LOCATION_KEY_DAYS}d expiry)"
note "spend guardrails: action-scoped key + LOCATION_KEY_RESOURCES + $BUDGET_NAME budget"
LOC_RESOURCES="${LOCATION_KEY_RESOURCES:-*}"
if [ "$LOC_RESOURCES" = "*" ]; then
  note "LOCATION_KEY_RESOURCES unset -> AllowResources=[\"*\"]; tighten for launch"
fi
EXPIRY="$(date -u -d "+${LOCATION_KEY_DAYS} days" +%Y-%m-%dT%H:%M:%SZ 2>/dev/null \
       || date -u -v+${LOCATION_KEY_DAYS}d +%Y-%m-%dT%H:%M:%SZ)"
# comma-sep list -> JSON array  ("arn:a,arn:b" -> ["arn:a","arn:b"])
RES_JSON="\"$(printf '%s' "$LOC_RESOURCES" | sed 's/,/","/g')\""
if check aws location describe-key --key-name "$LOC_KEY"; then
  note "exists — skip create (rotate: delete + re-run)"
else
  run aws location create-key --key-name "$LOC_KEY" \
    --expire-time "$EXPIRY" \
    --restrictions '{
      "AllowActions":[
        "geo-maps:GetTile","geo-maps:GetStaticMap",
        "geo-places:Autocomplete","geo-places:Suggest",
        "geo-routes:CalculateRoutes"
      ],
      "AllowResources":['"$RES_JSON"']
    }' \
    --tags Key=Project,Value=ALive-108 \
    --description "ALive-108 app key — maps/places/routes only"
fi

echo "=== provision done ==="
[ "$DRY_RUN" = 1 ] && echo "(dry-run — nothing was executed)"
