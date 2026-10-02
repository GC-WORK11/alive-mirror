#!/usr/bin/env bash
# Deploy ALive-108 API to AWS App Runner (free-tier friendly).
# Prereqs: aws CLI configured with your account, ECR + App Runner perms.
# Usage:  ./deploy-aws.sh            (first deploy + updates)
set -euo pipefail
REGION="${AWS_REGION:-ap-south-1}"
ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
REPO=alive108-api
IMG=$ACCOUNT.dkr.ecr.$REGION.amazonaws.com/$REPO:latest

aws ecr describe-repositories --repository-names $REPO --region $REGION \
  >/dev/null 2>&1 || aws ecr create-repository --repository-name $REPO \
  --region $REGION >/dev/null

aws ecr get-login-password --region $REGION | \
  docker login --username AWS --password-stdin \
  $ACCOUNT.dkr.ecr.$REGION.amazonaws.com

docker buildx build --platform linux/amd64 -t $IMG --push .

cat > /tmp/apprunner-svc.json <<EOF
{
  "SourceConfiguration": {
    "ImageRepository": {
      "ImageIdentifier": "$IMG",
      "ImageRepositoryType": "ECR",
      "ImageConfiguration": {"Port": "8080"}
    },
    "AutoDeploymentsEnabled": true
  },
  "InstanceConfiguration": {"Cpu": "1024", "Memory": "2048"}
}
EOF

if aws apprunner list-services --region $REGION --query \
    "ServiceSummaryList[?ServiceName=='alive108']" --output text | grep -q alive108; then
  ARN=$(aws apprunner list-services --region $REGION --query \
    "ServiceSummaryList[?ServiceName=='alive108'].ServiceArn" --output text)
  echo "service exists ($ARN) — auto-deploy fires on image push"
else
  aws apprunner create-service --service-name alive108 \
    --cli-input-json file:///tmp/apprunner-svc.json --region $REGION > /dev/null
  echo "created service"
fi

aws apprunner list-services --region $REGION --query \
  "ServiceSummaryList[?ServiceName=='alive108'].ServiceUrl" --output text
