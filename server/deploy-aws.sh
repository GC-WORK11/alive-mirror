#!/usr/bin/env bash
# Deploy ALive-108 API to AWS ECS Fargate — no local Docker needed.
# Image is built INSIDE AWS: S3 zip -> CodeBuild (docker) -> ECR -> ECS.
# This path exists because dev machines may lack Docker, and new AWS
# accounts can't subscribe to App Runner (SubscriptionRequiredException).
# Usage:  AWS_ACCESS_KEY_ID=... AWS_SECRET_ACCESS_KEY=... ./deploy-aws.sh
set -euo pipefail
REGION="${AWS_REGION:-ap-south-1}"
export AWS_DEFAULT_REGION=$REGION
ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
REPO=alive108-api
IMG=$ACCOUNT.dkr.ecr.$REGION.amazonaws.com/$REPO:latest
BUCKET=alive108-build-$ACCOUNT

# 1. source zip -> S3 (buildspec.yml in the server dir drives the build)
zip -qr /tmp/alive108-src.zip . -x "__pycache__/*" "*.venv*" ".git/*" "data/community.json"
aws s3 mb s3://$BUCKET --region $REGION 2>/dev/null || true
aws s3 cp /tmp/alive108-src.zip s3://$BUCKET/src.zip

# 2. CodeBuild service role (idempotent)
TRUST='{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":{"Service":"codebuild.amazonaws.com"},"Action":"sts:AssumeRole"}]}'
POLICY='{"Version":"2012-10-17","Statement":[
 {"Effect":"Allow","Action":["logs:CreateLogGroup","logs:CreateLogStream","logs:PutLogEvents"],"Resource":"*"},
 {"Effect":"Allow","Action":["s3:GetObject","s3:GetObjectVersion"],"Resource":"*"},
 {"Effect":"Allow","Action":["ecr:GetAuthorizationToken","ecr:CreateRepository","ecr:DescribeRepositories","ecr:BatchCheckLayerAvailability","ecr:GetDownloadUrlForLayer","ecr:BatchGetImage","ecr:InitiateLayerUpload","ecr:UploadLayerPart","ecr:CompleteLayerUpload","ecr:PutImage"],"Resource":"*"}]}'
aws iam create-role --role-name alive108-codebuild \
  --assume-role-policy-document "$TRUST" 2>/dev/null || true
aws iam put-role-policy --role-name alive108-codebuild \
  --policy-name alive108-cb --policy-document "$POLICY"

# 3. project + build
aws codebuild create-project \
  --name alive108-build \
  --source "type=S3,location=$BUCKET/src.zip,buildspec=buildspec.yml" \
  --artifacts type=NO_ARTIFACTS \
  --environment "type=LINUX_CONTAINER,image=aws/codebuild/standard:7.0,computeType=BUILD_GENERAL1_SMALL,privilegedMode=true,environmentVariables=[{name=ACCOUNT_ID,value=$ACCOUNT},{name=AWS_REGION,value=$REGION}]" \
  --service-role arn:aws:iam::$ACCOUNT:role/alive108-codebuild \
  --timeout-in-minutes 20 >/dev/null 2>&1 || \
aws codebuild update-project \
  --name alive108-build \
  --source "type=S3,location=$BUCKET/src.zip,buildspec=buildspec.yml" >/dev/null
BID=$(aws codebuild start-build --project-name alive108-build --query 'build.id' --output text)
echo "codebuild $BID running…"
until S=$(aws codebuild batch-get-builds --ids $BID --query 'builds[0].buildStatus' --output text) && [ "$S" != "IN_PROGRESS" ]; do sleep 15; done
[ "$S" = "SUCCEEDED" ] || { echo "build $S — check CloudWatch"; exit 1; }
echo "image pushed -> $IMG"

# 4. task exec role + task definition
ETRUST='{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":{"Service":"ecs-tasks.amazonaws.com"},"Action":"sts:AssumeRole"}]}'
aws iam create-role --role-name ecsTaskExecutionRole \
  --assume-role-policy-document "$ETRUST" 2>/dev/null || true
aws iam attach-role-policy --role-name ecsTaskExecutionRole \
  --policy-arn arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy 2>/dev/null || true
aws iam attach-role-policy --role-name ecsTaskExecutionRole \
  --policy-arn arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryReadOnly 2>/dev/null || true
aws ecs create-cluster --cluster-name alive108 >/dev/null 2>&1 || true
aws ecs register-task-definition \
  --family alive108 \
  --network-mode awsvpc \
  --requires-compatibilities FARGATE \
  --cpu 1024 --memory 2048 \
  --execution-role-arn arn:aws:iam::$ACCOUNT:role/ecsTaskExecutionRole \
  --container-definitions "[{\"name\":\"alive108\",\"image\":\"$IMG\",\"essential\":true,\"portMappings\":[{\"containerPort\":8080,\"protocol\":\"tcp\"}]}]" >/dev/null

# 5. service with public IP
SG=$(aws ec2 describe-security-groups --filters Name=group-name,Values=alive108 \
     --query 'SecurityGroups[0].GroupId' --output text)
if [ "$SG" = "None" ] || [ -z "$SG" ]; then
  SG=$(aws ec2 create-security-group --group-name alive108 \
       --description "ALive-108 public API" --query 'GroupId' --output text)
  aws ec2 authorize-security-group-ingress --group-id $SG \
    --protocol tcp --port 8080 --cidr 0.0.0.0/0 >/dev/null
fi
SUBNET=$(aws ec2 describe-subnets --query 'Subnets[0].SubnetId' --output text)
aws ecs create-service --cluster alive108 --service-name alive108 \
  --task-definition alive108 --desired-count 1 --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={subnets=[$SUBNET],securityGroups=[$SG],assignPublicIp=ENABLED}" 2>/dev/null || \
aws ecs update-service --cluster alive108 --service alive108 \
  --task-definition alive108 >/dev/null

sleep 75

# 6. stable address: NLB + Elastic IP (survives task redeploys;
#    raw Fargate public IPs do NOT — they die with the task)
TG=$(aws elbv2 describe-target-groups --names alive108-tg \
     --query 'TargetGroups[0].TargetGroupArn' --output text 2>/dev/null || echo None)
if [ "$TG" = "None" ]; then
  VPC=$(aws ec2 describe-vpcs --query 'Vpcs[0].VpcId' --output text)
  EIP=$(aws ec2 allocate-address --domain vpc --query 'PublicIp' --output text)
  EPIALLOC=$(aws ec2 describe-addresses --public-ips $EIP \
    --query 'Addresses[0].AllocationId' --output text)
  NLB=$(aws elbv2 create-load-balancer --name alive108 --type network \
    --subnet-mappings SubnetId=$SUBNET,AllocationId=$EPIALLOC \
    --query 'LoadBalancers[0].LoadBalancerArn' --output text)
  TG=$(aws elbv2 create-target-group --name alive108-tg --protocol TCP \
    --port 8080 --vpc-id $VPC --target-type ip \
    --health-check-protocol HTTP --health-check-path /health \
    --health-check-interval-seconds 30 \
    --query 'TargetGroups[0].TargetGroupArn' --output text)
  aws elbv2 create-listener --load-balancer-arn $NLB --protocol TCP \
    --port 80 --default-actions Type=forward,TargetGroupArn=$TG >/dev/null
else
  EIP=$(aws ec2 describe-addresses --query 'Addresses[0].PublicIp' --output text)
fi

# re-register the CURRENT task's private IP (deregister the stale one)
TASK=$(aws ecs list-tasks --cluster alive108 --service-name alive108 \
  --query 'taskArns[0]' --output text)
PRIV=$(aws ecs describe-tasks --cluster alive108 --tasks $TASK \
  --query 'tasks[0].containers[0].networkInterfaces[0].privateIpv4Address' \
  --output text)
OLD=$(aws elbv2 describe-target-health --target-group-arn $TG \
  --query 'TargetHealthDescriptions[0].Target.Id' --output text 2>/dev/null)
[ "$OLD" != "None" ] && [ -n "$OLD" ] && [ "$OLD" != "$PRIV" ] && \
  aws elbv2 deregister-targets --target-group-arn $TG --targets Id=$OLD,Port=8080 || true
aws elbv2 register-targets --target-group-arn $TG --targets Id=$PRIV,Port=8080
echo "STABLE -> http://$EIP  (try /health, /aqi, /decide, /admin)"
