#!/usr/bin/env bash
# Build delhi.pmtiles in AWS CodeBuild and publish it to the air bucket —
# the cloud path for the tiles lane (this Mac has no docker daemon).
#
#   ./scripts/geo/build_tiles_aws.sh            # build + publish, then verify
#
# Source = `git archive HEAD:scripts/geo` -> s3://alive108-build-<acct>/
# geo-src.zip, built by project alive108-tiles-build whose buildspec is
# buildspec-tiles.yml (same layout as the OSRM lane — buildspec-osrm.yml
# / project alive108-osrm-build, docs/plan/osrm-selfhosted.md).
#
# Output lands at s3://alive108-air/geo/delhi.pmtiles. The API task pulls
# it via ingest_worker.sync_geo_artifacts (first pull at task boot, then
# every 30 min) — no redeploy needed; tiles.py hot-swaps on mtime change.
#
# Env: AWS_REGION (ap-south-1), AIR_BUCKET (alive108-air),
#   TILES_PROJECT (alive108-tiles-build), FORCE (1 rebuilds the extract).
set -euo pipefail
source "$(dirname "$0")/common.sh"

REGION="${AWS_REGION:-ap-south-1}"
export AWS_DEFAULT_REGION="$REGION" AWS_REGION="$REGION"
AIR_BUCKET="${AIR_BUCKET:-alive108-air}"
PROJECT="${TILES_PROJECT:-alive108-tiles-build}"
ROLE="alive108-codebuild"
S3_KEY="geo/delhi.pmtiles"

ACCOUNT="$(aws sts get-caller-identity --query Account --output text)" \
  || die "aws sts get-caller-identity — no credentials?"
BUILD_BUCKET="alive108-build-$ACCOUNT"

# ---------------------------------------------------------------- src zip
zip=/tmp/alive108-geo-src.zip
git archive --format=zip -o "$zip" "HEAD:scripts/geo"
log "source zip: $(du -h "$zip" | cut -f1) (git archive HEAD:scripts/geo)"
aws s3 mb "s3://$BUILD_BUCKET" >/dev/null 2>&1 || true
aws s3 cp "$zip" "s3://$BUILD_BUCKET/geo-src.zip" >/dev/null

# ---------------------------------------------------------------- IAM
# Same role the API/OSRM CodeBuild lanes use; the tiles lane additionally
# needs s3:PutObject on the air bucket's geo/ prefix for the publish step.
# KEEP THIS POLICY IN SYNC with the put-role-policy in scripts/deploy.sh —
# whichever runs last wins, so a stale copy would silently revoke access.
trust='{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":{"Service":"codebuild.amazonaws.com"},"Action":"sts:AssumeRole"}]}'
policy='{"Version":"2012-10-17","Statement":[
  {"Effect":"Allow","Action":["logs:CreateLogGroup","logs:CreateLogStream","logs:PutLogEvents"],"Resource":"*"},
  {"Effect":"Allow","Action":["s3:GetObject","s3:GetObjectVersion"],"Resource":"*"},
  {"Effect":"Allow","Action":["s3:PutObject"],"Resource":"arn:aws:s3:::'"$AIR_BUCKET"'/geo/*"},
  {"Effect":"Allow","Action":["ecr:GetAuthorizationToken","ecr:CreateRepository","ecr:DescribeRepositories","ecr:BatchCheckLayerAvailability","ecr:GetDownloadUrlForLayer","ecr:BatchGetImage","ecr:InitiateLayerUpload","ecr:UploadLayerPart","ecr:CompleteLayerUpload","ecr:PutImage"],"Resource":"*"}]}'
aws iam create-role --role-name "$ROLE" \
  --assume-role-policy-document "$trust" >/dev/null 2>&1 || true
aws iam put-role-policy --role-name "$ROLE" \
  --policy-name alive108-cb --policy-document "$policy"
log "codebuild role policy synced (geo PutObject on $AIR_BUCKET/geo/*)"

# ---------------------------------------------------------------- project
# MEDIUM not SMALL: tilemaker holds the extract in RAM — 7 GB headroom.
env="type=LINUX_CONTAINER,image=aws/codebuild/standard:7.0,computeType=BUILD_GENERAL1_MEDIUM,privilegedMode=true,environmentVariables=[{name=ACCOUNT_ID,value=$ACCOUNT},{name=AWS_REGION,value=$REGION},{name=AIR_BUCKET,value=$AIR_BUCKET}]"
aws codebuild create-project --name "$PROJECT" \
  --source "type=S3,location=$BUILD_BUCKET/geo-src.zip,buildspec=buildspec-tiles.yml" \
  --artifacts type=NO_ARTIFACTS \
  --environment "$env" \
  --service-role "arn:aws:iam::$ACCOUNT:role/$ROLE" \
  --timeout-in-minutes 60 >/dev/null 2>&1 \
|| aws codebuild update-project --name "$PROJECT" \
  --source "type=S3,location=$BUILD_BUCKET/geo-src.zip,buildspec=buildspec-tiles.yml" \
  --environment "$env" >/dev/null

bid="$(aws codebuild start-build --project-name "$PROJECT" \
  --query 'build.id' --output text)"
log "codebuild $bid running…"
until st="$(aws codebuild batch-get-builds --ids "$bid" \
    --query 'builds[0].buildStatus' --output text)" \
    && [ "$st" != "IN_PROGRESS" ]; do sleep 20; done
[ "$st" = "SUCCEEDED" ] \
  || die "codebuild $bid status=$st — see CloudWatch logs (/aws/codebuild/$PROJECT)"

log "published artifact:"
aws s3api head-object --bucket "$AIR_BUCKET" --key "$S3_KEY"
