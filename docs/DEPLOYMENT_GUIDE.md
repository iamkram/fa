# FA AI System - Deployment Guide

## Overview

This guide covers deploying the Financial Advisor AI System to production using blue-green deployment strategy on AWS ECS.

## Table of Contents

- [Prerequisites](#prerequisites)
- [Initial Setup](#initial-setup)
- [Blue-Green Deployment Process](#blue-green-deployment-process)
- [Traffic Management](#traffic-management)
- [Rollback Procedures](#rollback-procedures)
- [Post-Deployment Validation](#post-deployment-validation)

---

## Prerequisites

### Required Tools

- **Terraform** >= 1.5.0
- **AWS CLI** >= 2.0
- **Docker** >= 20.10
- **jq** (JSON processor)
- **PostgreSQL** 16 with pgvector extension
- **Redis** 7.x

### AWS Permissions

Ensure your AWS credentials have permissions for:
- ECS (Elastic Container Service)
- ECR (Elastic Container Registry)
- ALB (Application Load Balancer)
- IAM (Identity and Access Management)
- CloudWatch (Logs and Metrics)
- Route53 (DNS)

### Environment Variables

```bash
export AWS_REGION="us-east-1"
export ENVIRONMENT="production"
export APP_NAME="fa-ai-system"
export ANTHROPIC_API_KEY="sk-ant-..."
export LANGSMITH_API_KEY="lsv2_pt_..."
export DATABASE_URL="postgresql://user:pass@host:5432/fa_ai_db"
export REDIS_URL="redis://host:6379/0"
```

---

## Initial Setup

### 1. Infrastructure Provisioning

```bash
cd infrastructure/deployment

# Initialize Terraform
terraform init

# Review the plan
terraform plan \
  -var="aws_region=${AWS_REGION}" \
  -var="environment=${ENVIRONMENT}" \
  -var="app_name=${APP_NAME}"

# Apply infrastructure
terraform apply -auto-approve
```

This creates:
- ECS Cluster
- Blue and Green ECS Services
- Application Load Balancer with target groups
- Security groups and IAM roles
- CloudWatch log groups

### 2. Database Setup

```bash
# Run database migrations
python scripts/setup_database.py

# Seed initial data (optional)
python scripts/seed_database.py
```

### 3. Build and Push Docker Image

```bash
# Get ECR login
aws ecr get-login-password --region ${AWS_REGION} | \
  docker login --username AWS --password-stdin <account-id>.dkr.ecr.${AWS_REGION}.amazonaws.com

# Build image
docker build -t fa-ai-system:latest .

# Tag image
docker tag fa-ai-system:latest \
  <account-id>.dkr.ecr.${AWS_REGION}.amazonaws.com/fa-ai-system:v1.0.0

# Push to ECR
docker push <account-id>.dkr.ecr.${AWS_REGION}.amazonaws.com/fa-ai-system:v1.0.0
```

---

## Blue-Green Deployment Process

### Overview

Blue-Green deployment allows zero-downtime updates by running two identical environments:
- **Blue**: Currently active (100% traffic)
- **Green**: New version (0% traffic initially)

### Step 1: Deploy to Green Environment

```bash
cd scripts/deployment

# Deploy new version to green
./deploy_green.sh <account-id>.dkr.ecr.us-east-1.amazonaws.com/fa-ai-system:v1.1.0
```

This script:
1. Validates current traffic distribution
2. Updates green task definition with new image
3. Deploys to green ECS service
4. Waits for tasks to be healthy
5. Runs health checks on green target group

**Expected Output:**
```
🚀 FA AI System - Green Environment Deployment
==============================================
Configuration:
  App Name: fa-ai-system
  Region: us-east-1
  Environment: production
  New Image: ...ecr...fa-ai-system:v1.1.0

📊 Checking current traffic distribution...
  Blue: 100%
  Green: 0%

📝 Updating Terraform configuration...
✅ Terraform configuration updated

🔍 Running Terraform plan...
...

🚀 Deploying to green environment...
✅ Green environment deployed successfully!

⏳ Waiting for green tasks to become healthy...
  Running: 3 / Desired: 3
✅ All green tasks are running!

🏥 Performing health checks on green environment...
  Healthy targets: 3 / 3
✅ Green environment is healthy!

==============================================
✅ Green Deployment Complete!
==============================================

Next Steps:
  1. Test the green environment (it's not receiving traffic yet)
  2. When ready, shift traffic: ./shift_traffic.sh 10
  3. Monitor metrics and gradually increase traffic
  4. If issues occur, rollback: ./rollback.sh
```

### Step 2: Gradual Traffic Shift

Start with 10% traffic to green:

```bash
./shift_traffic.sh 10
```

Monitor CloudWatch metrics for 15-30 minutes:
- Error rates
- Response times
- Success rates
- Cost per query

If metrics look good, increase gradually:

```bash
./shift_traffic.sh 25   # 25% to green
# Wait and monitor...

./shift_traffic.sh 50   # 50% to green
# Wait and monitor...

./shift_traffic.sh 100  # Full cutover
```

### Step 3: Post-Deployment Validation

Once green has 100% traffic:

```bash
# Verify traffic distribution
terraform output

# Check service health
aws ecs describe-services \
  --cluster fa-ai-system-cluster \
  --services fa-ai-system-green-service \
  --region us-east-1

# View logs
aws logs tail /ecs/fa-ai-system-green --follow --region us-east-1
```

### Step 4: Promote Green to Blue

After 24-48 hours of stable operation:

```bash
# Update blue to match green image
terraform apply -var="container_image_blue=<green-image>"

# Reset traffic to 100% blue
./shift_traffic.sh 0  # 0% to green = 100% to blue
```

---

## Traffic Management

### View Current Distribution

```bash
terraform output -json | jq '{blue: .blue_weight.value, green: .green_weight.value}'
```

### Shift Traffic

```bash
# Syntax: ./shift_traffic.sh <green-percentage>
./shift_traffic.sh 25  # 25% green, 75% blue
```

### Traffic Patterns

**Canary Release (Recommended):**
```
Blue: 100% → 90% → 75% → 50% → 25% → 0%
Green: 0% → 10% → 25% → 50% → 75% → 100%
```

**A/B Testing:**
```
Blue: 50%
Green: 50%
# Maintain for extended period to compare metrics
```

---

## Rollback Procedures

### Emergency Rollback

If green environment has critical issues:

```bash
./rollback.sh
```

This immediately shifts 100% traffic back to blue.

**Rollback Checklist:**
1. ✅ Verify blue environment is healthy
2. ✅ Shift all traffic to blue (100%)
3. ✅ Investigate green environment issues
4. ✅ Review CloudWatch logs
5. ✅ Document incident in runbook
6. ✅ Fix issues before next deployment

### Automated Rollback Triggers

Consider setting CloudWatch alarms to trigger rollback:
- Error rate > 5%
- P95 latency > 5 seconds
- Guardrail failures > 1%

---

## Post-Deployment Validation

### Health Check Endpoints

```bash
# Application health
curl https://fa-ai-system.example.com/health

# Database connectivity
curl https://fa-ai-system.example.com/health/db

# Redis connectivity
curl https://fa-ai-system.example.com/health/redis
```

### Smoke Tests

```bash
# Test batch processing
python src/batch/run_batch_phase2.py --limit 10 --concurrent

# Test interactive query
curl -X POST https://fa-ai-system.example.com/query \
  -H "Content-Type: application/json" \
  -d '{"ticker": "AAPL", "question": "What are the latest earnings?"}'
```

### Performance Validation

```bash
# Run regression tests
python tests/regression/run_regression_tests.py

# Check metrics in CloudWatch
# Expected SLAs:
# - Batch success rate: > 95%
# - Query response time: < 3s (P95)
# - Cost per stock: < $0.40
# - Cost per query: < $0.08
```

### LangSmith Validation

View deployment in LangSmith:
```
https://smith.langchain.com/o/<org>/projects/<project>/experiments
```

---

## Troubleshooting

### Tasks Not Starting

```bash
# Check task definition
aws ecs describe-task-definition \
  --task-definition fa-ai-system-green \
  --region us-east-1

# Check service events
aws ecs describe-services \
  --cluster fa-ai-system-cluster \
  --services fa-ai-system-green-service \
  --region us-east-1 \
  --query 'services[0].events[:10]'
```

### Unhealthy Targets

```bash
# Check target health
aws elbv2 describe-target-health \
  --target-group-arn <green-tg-arn> \
  --region us-east-1

# Common causes:
# - Health check path incorrect
# - Security group blocking ALB
# - Container not listening on correct port
```

### High Error Rates

```bash
# View CloudWatch logs
aws logs tail /ecs/fa-ai-system-green --follow

# Check specific errors
aws logs filter-pattern '{ $.level = "ERROR" }' \
  --log-group-name /ecs/fa-ai-system-green \
  --start-time 1h
```

---

## Best Practices

1. **Always deploy to green first** - Never modify blue while it's serving traffic
2. **Start with small traffic percentages** - 10% → 25% → 50% → 100%
3. **Monitor for sufficient time** - Wait 15-30 minutes between shifts
4. **Keep blue healthy** - Always have a rollback target
5. **Document changes** - Update CHANGELOG.md with each deployment
6. **Run regression tests** - Before and after deployment
7. **Check costs** - Monitor cost per stock/query metrics

---

## CI/CD Integration

### GitHub Actions Example

```yaml
name: Deploy to Production

on:
  push:
    tags:
      - 'v*'

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Run regression tests
        run: python tests/regression/run_regression_tests.py

      - name: Build and push Docker image
        run: |
          docker build -t fa-ai-system:${{ github.ref_name }} .
          docker push <ecr-repo>:${{ github.ref_name }}

      - name: Deploy to green
        run: ./scripts/deployment/deploy_green.sh <ecr-repo>:${{ github.ref_name }}

      - name: Canary traffic (10%)
        run: ./scripts/deployment/shift_traffic.sh 10

      # Manual approval step here

      - name: Full cutover
        run: ./scripts/deployment/shift_traffic.sh 100
```

---

## Additional Resources

- [Operations Runbook](./OPERATIONS_RUNBOOK.md)
- [Architecture Documentation](./ARCHITECTURE.md)
- [Monitoring Guide](./MONITORING_GUIDE.md)
- [API Documentation](./API_DOCUMENTATION.md)
