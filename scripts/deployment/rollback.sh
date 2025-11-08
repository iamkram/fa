#!/bin/bash
# Rollback Script
# Quickly reverts all traffic back to blue environment

set -e

echo "⏪ FA AI System - Emergency Rollback"
echo "====================================="

# Configuration
APP_NAME="${APP_NAME:-fa-ai-system}"
AWS_REGION="${AWS_REGION:-us-east-1}"
ENVIRONMENT="${ENVIRONMENT:-production}"

echo ""
echo "Configuration:"
echo "  App Name: $APP_NAME"
echo "  Region: $AWS_REGION"
echo "  Environment: $ENVIRONMENT"
echo ""

# Get current distribution
echo "📊 Current traffic distribution:"
CURRENT_BLUE=$(terraform output -json | jq -r '.blue_weight.value' 2>/dev/null || echo "unknown")
CURRENT_GREEN=$(terraform output -json | jq -r '.green_weight.value' 2>/dev/null || echo "unknown")
echo "  Blue: ${CURRENT_BLUE}%"
echo "  Green: ${CURRENT_GREEN}%"
echo ""

# Check if rollback is needed
if [ "$CURRENT_BLUE" == "100" ]; then
    echo "ℹ️  Already running 100% on blue environment"
    echo "No rollback needed"
    exit 0
fi

# Confirm rollback
echo "⚠️  EMERGENCY ROLLBACK"
echo ""
echo "This will immediately shift ALL traffic back to blue environment:"
echo "  Blue: 100%"
echo "  Green: 0%"
echo ""
echo "❗ Use this only if green environment has critical issues"
echo ""
read -p "Do you want to proceed with rollback? (yes/no): " CONFIRM

if [ "$CONFIRM" != "yes" ]; then
    echo "❌ Rollback cancelled"
    exit 1
fi

# Check blue environment health
echo ""
echo "🏥 Checking blue environment health..."
BLUE_TG_ARN=$(terraform output -json | jq -r '.blue_target_group_arn.value')

BLUE_HEALTHY=$(aws elbv2 describe-target-health \
    --target-group-arn "$BLUE_TG_ARN" \
    --region "$AWS_REGION" \
    --query 'length(TargetHealthDescriptions[?TargetHealth.State==`healthy`])' \
    --output text)

if [ "$BLUE_HEALTHY" -eq 0 ]; then
    echo "❌ CRITICAL: No healthy targets in blue environment!"
    echo "Cannot rollback to unhealthy environment"
    echo "Manual intervention required"
    exit 1
fi

echo "  ✅ Blue has $BLUE_HEALTHY healthy targets"
echo ""

# Perform rollback
echo "🚀 Executing rollback..."

CURRENT_BLUE_IMAGE=$(terraform output -json | jq -r '.container_image_blue.value' 2>/dev/null || echo 'current-blue-image')
CURRENT_GREEN_IMAGE=$(terraform output -json | jq -r '.container_image_green.value' 2>/dev/null || echo 'current-green-image')

# Update Terraform variables to shift all traffic to blue
cat > terraform.tfvars <<EOF
aws_region            = "$AWS_REGION"
environment           = "$ENVIRONMENT"
app_name              = "$APP_NAME"
container_image_blue  = "$CURRENT_BLUE_IMAGE"
container_image_green = "$CURRENT_GREEN_IMAGE"
blue_weight           = 100
green_weight          = 0
EOF

# Apply immediately
terraform apply \
    -target=aws_lb_listener.http \
    -target=aws_ecs_service.blue \
    -target=aws_ecs_service.green \
    -auto-approve

echo ""
echo "✅ Rollback complete!"
echo ""

# Verify
echo "🔍 Verifying rollback..."
sleep 10

NEW_BLUE=$(terraform output -json | jq -r '.blue_weight.value')
NEW_GREEN=$(terraform output -json | jq -r '.green_weight.value')

echo "  Blue: ${NEW_BLUE}%"
echo "  Green: ${NEW_GREEN}%"

if [ "$NEW_BLUE" != "100" ] || [ "$NEW_GREEN" != "0" ]; then
    echo ""
    echo "⚠️  Warning: Traffic distribution may not have updated correctly"
    echo "Please verify ALB listener rules manually"
fi

# Check for any connection draining
echo ""
echo "📊 Monitoring green environment..."
GREEN_TG_ARN=$(terraform output -json | jq -r '.green_target_group_arn.value')

GREEN_DRAINING=$(aws elbv2 describe-target-health \
    --target-group-arn "$GREEN_TG_ARN" \
    --region "$AWS_REGION" \
    --query 'length(TargetHealthDescriptions[?TargetHealth.State==`draining`])' \
    --output text)

if [ "$GREEN_DRAINING" -gt 0 ]; then
    echo "  ⏳ $GREEN_DRAINING green targets are draining connections"
    echo "  This is normal and will complete within 30 seconds"
fi

echo ""
echo "====================================="
echo "✅ Rollback Successful!"
echo "====================================="
echo ""
echo "Current Status:"
echo "  Blue: 100% (active)"
echo "  Green: 0% (inactive)"
echo ""
echo "Next Steps:"
echo "  1. Investigate what went wrong with green environment"
echo "  2. Check CloudWatch logs for errors"
echo "  3. Review metrics comparison between blue and green"
echo "  4. Fix issues before attempting next deployment"
echo ""
echo "Green Environment Logs:"
echo "  aws logs tail /ecs/${APP_NAME}-green --follow --region ${AWS_REGION}"
echo ""
echo "CloudWatch Dashboard:"
echo "  https://console.aws.amazon.com/cloudwatch/home?region=${AWS_REGION}#dashboards:name=FA-AI-System-Production"
echo ""

# Log the rollback event
echo "📝 Logging rollback event..."
aws cloudwatch put-metric-data \
    --namespace "FA-AI-System" \
    --metric-name "RollbackEvent" \
    --value 1 \
    --dimensions Environment=${ENVIRONMENT} \
    --region ${AWS_REGION} 2>/dev/null || echo "  (CloudWatch logging skipped - not configured)"

echo ""
echo "🔔 Rollback complete. System is stable on blue environment."
echo ""
