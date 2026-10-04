#!/usr/bin/env bash
# ALive-108 — flip the WAQI API token end-to-end.
#
#   1. aws secretsmanager put-secret-value alive108/waqi {"api_key":"<token>"}
#   2. aws ecs update-service --force-new-deployment (new task picks up
#      WAQI_API_KEY at container start; the old task keeps serving)
#   3. Poll /health -> sources.stations until stations.count > 0 and the
#      winning feed is "waqi" (feeds.waqi == "ok").
#
# Safe by construction: refuses to run when the supplied token is the
# REPLACE_ME placeholder or empty, and never touches any other secret.
#
# Usage:
#   bash tools/flip_waqi_token.sh <waqi-token> [base-url]
#
# Env overrides: AWS_REGION (ap-south-1), ECS_CLUSTER, ECS_SERVICE,
#                FLIP_TIMEOUT_S (900), NLB_URL default below.
set -euo pipefail

REGION="${AWS_REGION:-ap-south-1}"
export AWS_DEFAULT_REGION="$REGION" AWS_REGION="$REGION"
CLUSTER="${ECS_CLUSTER:-alive108}"
SERVICE="${ECS_SERVICE:-alive108}"
SECRET_NAME="${WAQI_SECRET_NAME:-alive108/waqi}"
NLB_URL="${2:-http://alive108-2699c171ddded465.elb.ap-south-1.amazonaws.com}"
TIMEOUT="${FLIP_TIMEOUT_S:-900}"

log() { printf '[%(%H:%M:%S)T] %s\n' -1 "$*"; }
die() { log "ERROR: $*"; exit 1; }

TOKEN="${1:-}"
[ -n "$TOKEN" ] || die "usage: bash tools/flip_waqi_token.sh <waqi-token> [base-url]"
# The placeholder must never be pushed as a credential — it would go
# live as a guaranteed-invalid key. Also reject the WAQI demo token,
# which silently serves Shanghai data (fake — never usable here).
[ "$TOKEN" != "REPLACE_ME" ] || die "REPLACE_ME is the placeholder, not a token"
[ "$TOKEN" != "demo" ]       || die "WAQI demo token serves Shanghai — never use"

command -v aws >/dev/null  || die "aws CLI not found"
command -v jq >/dev/null   || die "jq not found"
command -v curl >/dev/null || die "curl not found"

# --- 1. rotate the secret --------------------------------------------------
log "put-secret-value $SECRET_NAME"
aws secretsmanager put-secret-value \
  --secret-id "$SECRET_NAME" \
  --secret-string "{\"api_key\":\"$TOKEN\"}" \
  --region "$REGION" >/dev/null
log "secret updated"

# --- 2. force a new deployment ---------------------------------------------
TD_ARN="$(aws ecs describe-services --cluster "$CLUSTER" --service "$SERVICE" \
  --query 'services[0].taskDefinition' --output text --region "$REGION")"
[ "$TD_ARN" != "None" ] && [ -n "$TD_ARN" ] || die "service $CLUSTER/$SERVICE not found"
log "force-new-deployment on $TD_ARN"
aws ecs update-service --cluster "$CLUSTER" --service "$SERVICE" \
  --task-definition "$TD_ARN" --force-new-deployment \
  --region "$REGION" >/dev/null

# --- 3. poll /health until waqi wins ----------------------------------------
log "waiting for a task serving $NLB_URL/health with stations feed 'waqi' (<= ${TIMEOUT}s)"
deadline=$(( $(date +%s) + TIMEOUT ))
last=""
while [ "$(date +%s)" -lt "$deadline" ]; do
  body="$(curl -fsS --max-time 10 "$NLB_URL/health" 2>/dev/null)" || { last="health unreachable"; sleep 10; continue; }
  st="$(printf '%s' "$body" | jq -r '.sources.stations // {}')"
  count="$(printf '%s' "$st" | jq -r '.count // 0')"
  src="$(printf '%s'  "$st" | jq -r '.source // "none"')"
  waqi="$(printf '%s' "$st" | jq -r '.feeds.waqi // "n/a"')"
  last="count=$count source=$src waqi=$waqi"
  if [ "$count" -gt 0 ] 2>/dev/null && [ "$src" = "waqi" ]; then
    log "OK — stations live: $last"
    exit 0
  fi
  sleep 10
done
die "timed out waiting for waqi stations (last: $last)"
