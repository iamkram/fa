#!/bin/bash
# Deploy Green Environment Script
# Deploys new version to green environment while blue remains active

set -e

echo "🚀 FA AI System - Green Environment Deployment"
echo "=============================================="

# Configuration
APP_NAME="${APP_NAME:-fa-ai-system}"
AWS_REGION="${AWS_REGION:-us-east-1}"
ENVIRONMENT="${ENVIRONMENT:-production}"
NEW_IMAGE="${1}"

# Validate inputs
if [ -z "$NEW_IMAGE" ]; then
    echo "❌ Error: Docker image not specified"
    echo "Usage: ./deploy_green.sh <docker-image-tag>"
    echo "Example: ./deploy_green.sh 123456789012.dkr.ecr.us-east-1.amazonaws.com/fa-ai-system:v1.2.3"
    exit 1
fi

echo ""
echo "Configuration:"
echo "  App Name: $APP_NAME"
echo "  Region: $AWS_REGION"
echo "  Environment: $ENVIRONMENT"
echo "  New Image: $NEW_IMAGE"
echo ""

# Check current traffic distribution
echo "📊 Checking current traffic distribution..."
CURRENT_BLUE_WEIGHT=$(terraform output -json | jq -r '.blue_weight.value')
CURRENT_GREEN_WEIGHT=$(terraform output -json | jq -r '.green_weight.value')

echo "  Blue: ${CURRENT_BLUE_WEIGHT}%"
echo "  Green: ${CURRENT_GREEN_WEIGHT}%"
echo ""

if [ "$CURRENT_GREEN_WEIGHT" -gt 0 ]; then
    echo "⚠️  Warning: Green environment is currently receiving ${CURRENT_GREEN_WEIGHT}% of traffic"
    read -p "Do you want to continue? (yes/no): " CONFIRM
    if [ "$CONFIRM" != "yes" ]; then
        echo "❌ Deployment cancelled"
        exit 1
    fi
fi

# Update Terraform variables for green deployment
echo "📝 Updating Terraform configuration..."
cat > terraform.tfvars <<EOF
aws_region            = "$AWS_REGION"
environment           = "$ENVIRONMENT"
app_name              = "$APP_NAME"
container_image_blue  = "$(terraform output -json | jq -r '.container_image_blue.value' 2>/dev/null || echo 'current-blue-image')"
container_image_green = "$NEW_IMAGE"
blue_weight           = 100
green_weight          = 0
EOF

echo "✅ Terraform configuration updated"
echo ""

# Run Terraform plan
echo "🔍 Running Terraform plan..."
terraform plan \
    -target=aws_ecs_task_definition.green \
    -target=aws_ecs_service.green \
    -out=tfplan

echo ""
read -p "Do you want to apply this plan? (yes/no): " APPLY_CONFIRM
if [ "$APPLY_CONFIRM" != "yes" ]; then
    echo "❌ Deployment cancelled"
    rm -f tfplan
    exit 1
fi

# Apply Terraform changes
echo ""
echo "🚀 Deploying to green environment..."
terraform apply tfplan
rm -f tfplan

echo ""
echo "✅ Green environment deployed successfully!"
echo ""

# Wait for green tasks to be healthy
echo "⏳ Waiting for green tasks to become healthy..."
GREEN_SERVICE_NAME="${APP_NAME}-green-service"
CLUSTER_NAME="${APP_NAME}-cluster"

MAX_WAIT=600  # 10 minutes
WAIT_TIME=0
INTERVAL=15

while [ $WAIT_TIME -lt $MAX_WAIT ]; do
    RUNNING_COUNT=$(aws ecs describe-services \
        --cluster "$CLUSTER_NAME" \
        --services "$GREEN_SERVICE_NAME" \
        --region "$AWS_REGION" \
        --query 'services[0].runningCount' \
        --output text)

    DESIRED_COUNT=$(aws ecs describe-services \
        --cluster "$CLUSTER_NAME" \
        --services "$GREEN_SERVICE_NAME" \
        --region "$AWS_REGION" \
        --query 'services[0].desiredCount' \
        --output text)

    echo "  Running: $RUNNING_COUNT / Desired: $DESIRED_COUNT"

    if [ "$RUNNING_COUNT" -eq "$DESIRED_COUNT" ] && [ "$RUNNING_COUNT" -gt 0 ]; then
        echo "✅ All green tasks are running!"
        break
    fi

    sleep $INTERVAL
    WAIT_TIME=$((WAIT_TIME + INTERVAL))
done

if [ $WAIT_TIME -ge $MAX_WAIT ]; then
    echo "❌ Timeout waiting for green tasks to be healthy"
    echo "Please check ECS service status manually"
    exit 1
fi

# Health check
echo ""
echo "🏥 Performing health checks on green environment..."
ALB_DNS=$(terraform output -json | jq -r '.alb_dns_name.value')
GREEN_TG_ARN=$(terraform output -json | jq -r '.green_target_group_arn.value')

# Get target health
HEALTHY_TARGETS=$(aws elbv2 describe-target-health \
    --target-group-arn "$GREEN_TG_ARN" \
    --region "$AWS_REGION" \
    --query 'length(TargetHealthDescriptions[?TargetHealth.State==`healthy`])' \
    --output text)

TOTAL_TARGETS=$(aws elbv2 describe-target-health \
    --target-group-arn "$GREEN_TG_ARN" \
    --region "$AWS_REGION" \
    --query 'length(TargetHealthDescriptions)' \
    --output text)

echo "  Healthy targets: $HEALTHY_TARGETS / $TOTAL_TARGETS"

if [ "$HEALTHY_TARGETS" -eq 0 ]; then
    echo "❌ No healthy targets in green environment"
    echo "Please investigate and fix issues before shifting traffic"
    exit 1
fi

echo "✅ Green environment is healthy!"
echo ""

# Summary
echo "=============================================="
echo "✅ Green Deployment Complete!"
echo "=============================================="
echo ""
echo "Next Steps:"
echo "  1. Test the green environment (it's not receiving traffic yet)"
echo "  2. When ready, shift traffic: ./shift_traffic.sh 10  (start with 10%)"
echo "  3. Monitor metrics and gradually increase traffic"
echo "  4. If issues occur, rollback: ./rollback.sh"
echo ""
echo "ALB DNS: $ALB_DNS"
echo "Green Target Group: $GREEN_TG_ARN"
echo ""
