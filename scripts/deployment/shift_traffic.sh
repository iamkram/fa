#!/bin/bash
# Shift Traffic Between Blue and Green Environments
# Gradually shifts traffic using weighted target groups

set -e

echo "🔀 FA AI System - Traffic Shifting"
echo "==================================="

# Configuration
APP_NAME="${APP_NAME:-fa-ai-system}"
AWS_REGION="${AWS_REGION:-us-east-1}"
ENVIRONMENT="${ENVIRONMENT:-production}"
GREEN_PERCENTAGE="${1}"

# Validate inputs
if [ -z "$GREEN_PERCENTAGE" ]; then
    echo "❌ Error: Green traffic percentage not specified"
    echo "Usage: ./shift_traffic.sh <green-percentage>"
    echo "Example: ./shift_traffic.sh 25  (shifts 25% to green, 75% stays on blue)"
    exit 1
fi

# Validate percentage
if ! [[ "$GREEN_PERCENTAGE" =~ ^[0-9]+$ ]] || [ "$GREEN_PERCENTAGE" -lt 0 ] || [ "$GREEN_PERCENTAGE" -gt 100 ]; then
    echo "❌ Error: Invalid percentage. Must be between 0 and 100"
    exit 1
fi

BLUE_PERCENTAGE=$((100 - GREEN_PERCENTAGE))

echo ""
echo "Configuration:"
echo "  App Name: $APP_NAME"
echo "  Region: $AWS_REGION"
echo "  Environment: $ENVIRONMENT"
echo "  Target Distribution: Blue ${BLUE_PERCENTAGE}% | Green ${GREEN_PERCENTAGE}%"
echo ""

# Get current distribution
echo "📊 Current traffic distribution:"
CURRENT_BLUE=$(terraform output -json | jq -r '.blue_weight.value' 2>/dev/null || echo "unknown")
CURRENT_GREEN=$(terraform output -json | jq -r '.green_weight.value' 2>/dev/null || echo "unknown")
echo "  Blue: ${CURRENT_BLUE}%"
echo "  Green: ${CURRENT_GREEN}%"
echo ""

# Confirm action
echo "⚠️  This will shift traffic to:"
echo "  Blue: ${BLUE_PERCENTAGE}%"
echo "  Green: ${GREEN_PERCENTAGE}%"
echo ""
read -p "Do you want to continue? (yes/no): " CONFIRM

if [ "$CONFIRM" != "yes" ]; then
    echo "❌ Traffic shift cancelled"
    exit 1
fi

# Check green environment health
if [ "$GREEN_PERCENTAGE" -gt 0 ]; then
    echo ""
    echo "🏥 Checking green environment health..."

    GREEN_TG_ARN=$(terraform output -json | jq -r '.green_target_group_arn.value')

    HEALTHY_TARGETS=$(aws elbv2 describe-target-health \
        --target-group-arn "$GREEN_TG_ARN" \
        --region "$AWS_REGION" \
        --query 'length(TargetHealthDescriptions[?TargetHealth.State==`healthy`])' \
        --output text)

    if [ "$HEALTHY_TARGETS" -eq 0 ]; then
        echo "❌ No healthy targets in green environment!"
        echo "Cannot shift traffic to unhealthy environment"
        exit 1
    fi

    echo "  ✅ Green has $HEALTHY_TARGETS healthy targets"
fi

# Update Terraform variables
echo ""
echo "📝 Updating traffic weights..."

CURRENT_BLUE_IMAGE=$(terraform output -json | jq -r '.container_image_blue.value' 2>/dev/null || echo 'current-blue-image')
CURRENT_GREEN_IMAGE=$(terraform output -json | jq -r '.container_image_green.value' 2>/dev/null || echo 'current-green-image')

cat > terraform.tfvars <<EOF
aws_region            = "$AWS_REGION"
environment           = "$ENVIRONMENT"
app_name              = "$APP_NAME"
container_image_blue  = "$CURRENT_BLUE_IMAGE"
container_image_green = "$CURRENT_GREEN_IMAGE"
blue_weight           = $BLUE_PERCENTAGE
green_weight          = $GREEN_PERCENTAGE
EOF

# Apply changes
echo "🚀 Applying traffic shift..."
terraform apply \
    -target=aws_lb_listener.http \
    -target=aws_ecs_service.blue \
    -target=aws_ecs_service.green \
    -auto-approve

echo ""
echo "✅ Traffic shift complete!"
echo ""

# Monitor for a bit
echo "📈 Monitoring traffic for 30 seconds..."
sleep 30

# Check target group health after shift
echo ""
echo "🏥 Post-shift health check..."

if [ "$BLUE_PERCENTAGE" -gt 0 ]; then
    BLUE_TG_ARN=$(terraform output -json | jq -r '.blue_target_group_arn.value')
    BLUE_HEALTHY=$(aws elbv2 describe-target-health \
        --target-group-arn "$BLUE_TG_ARN" \
        --region "$AWS_REGION" \
        --query 'length(TargetHealthDescriptions[?TargetHealth.State==`healthy`])' \
        --output text)
    echo "  Blue: $BLUE_HEALTHY healthy targets (${BLUE_PERCENTAGE}% traffic)"
fi

if [ "$GREEN_PERCENTAGE" -gt 0 ]; then
    GREEN_TG_ARN=$(terraform output -json | jq -r '.green_target_group_arn.value')
    GREEN_HEALTHY=$(aws elbv2 describe-target-health \
        --target-group-arn "$GREEN_TG_ARN" \
        --region "$AWS_REGION" \
        --query 'length(TargetHealthDescriptions[?TargetHealth.State==`healthy`])' \
        --output text)
    echo "  Green: $GREEN_HEALTHY healthy targets (${GREEN_PERCENTAGE}% traffic)"
fi

echo ""
echo "==================================="
echo "✅ Traffic Shift Complete!"
echo "==================================="
echo ""
echo "Current Distribution:"
echo "  Blue: ${BLUE_PERCENTAGE}%"
echo "  Green: ${GREEN_PERCENTAGE}%"
echo ""

if [ "$GREEN_PERCENTAGE" -eq 100 ]; then
    echo "🎉 Fully migrated to green environment!"
    echo ""
    echo "Next Steps:"
    echo "  1. Monitor for 24-48 hours"
    echo "  2. If stable, update blue to match green image"
    echo "  3. Decommission old blue version"
elif [ "$GREEN_PERCENTAGE" -eq 0 ]; then
    echo "⏪ Fully reverted to blue environment"
    echo ""
    echo "Next Steps:"
    echo "  1. Investigate green environment issues"
    echo "  2. Fix problems and redeploy green"
else
    echo "📊 Partial traffic shift active"
    echo ""
    echo "Next Steps:"
    echo "  1. Monitor CloudWatch metrics for both environments"
    echo "  2. Compare error rates, latency, and costs"
    echo "  3. If green is stable: ./shift_traffic.sh $(($GREEN_PERCENTAGE + 25))"
    echo "  4. If issues occur: ./rollback.sh"
fi

echo ""
echo "Monitor at: CloudWatch Dashboard (fa-ai-system-production)"
echo ""
