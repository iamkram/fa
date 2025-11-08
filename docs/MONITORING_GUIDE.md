# FA AI System - Monitoring Guide

## Overview

This guide covers monitoring, metrics, alerts, and troubleshooting for the FA AI System in production.

## Monitoring Stack

- **CloudWatch**: AWS native monitoring (metrics, logs, dashboards, alarms)
- **LangSmith**: LLM-specific tracing and evaluation
- **Application Logs**: Structured logging to CloudWatch Logs

---

## CloudWatch Dashboard

### Accessing the Dashboard

```
AWS Console → CloudWatch → Dashboards → FA-AI-System-Production
```

Or via CLI:
```bash
aws cloudwatch get-dashboard --dashboard-name FA-AI-System-Production --region us-east-1
```

### Dashboard Widgets

#### 1. Batch Volume & Success Rate

**Metrics:**
- `StocksProcessed` (Count)
- `BatchSuccessRate` (Percent)

**Expected Values:**
- Daily batch: 1,000 stocks
- Success rate: > 95%

**Alert Conditions:**
- Success rate < 95% → P1 incident
- Success rate < 90% → P0 incident

#### 2. Query Volume by Tier

**Metrics:**
- `QueryCount` by tier (Hook, Medium, Expanded)

**Expected Patterns:**
- Hook: ~50% of queries
- Medium: ~40% of queries
- Expanded: ~10% of queries

#### 3. Response Times (P50, P95, P99)

**Metrics:**
- `QueryLatency` (Milliseconds)

**SLA Targets:**
- P50: < 1s (1,000 ms)
- P95: < 3s (3,000 ms)
- P99: < 5s (5,000 ms)

**Alert Conditions:**
- P95 > 5s → P2 incident
- P95 > 10s → P1 incident

#### 4. Error Rates by Component

**Metrics:**
- `ErrorCount` by component (Ingestion, Vectorization, Generation, Validation)
- `ErrorRate` (Percent)

**Expected Values:**
- Overall error rate: < 1%
- Per-component error rate: < 2%

**Alert Conditions:**
- Error rate > 5% → P1 incident
- Error rate > 10% → P0 incident

#### 5. Cost Metrics

**Metrics:**
- `CostPerStock` (USD)
- `CostPerQuery` (USD)
- `DailyCost` (USD)
- `MonthlyCost` (USD)

**Budget Targets:**
- Cost per stock: < $0.40
- Cost per query: < $0.08
- Monthly total: < $2,000

**Alert Conditions:**
- Cost per stock > $0.50 → Warning
- Monthly cost > $1,800 (90% of budget) → P2 incident

#### 6. Token Usage by Model

**Metrics:**
- `TokensUsed` by model (Sonnet, Haiku)
- `ModelUsageDistribution` (Percent)

**Expected Distribution:**
- Sonnet: ~60% (complex tasks)
- Haiku: ~40% (simple tasks)

#### 7. Guardrail Pass Rate

**Metrics:**
- `GuardrailPassRate` (Percent)
- `FactCheckFailures` (Count)

**Expected Values:**
- Pass rate: > 95%
- Fact check failures: < 5% of summaries

**Alert Conditions:**
- Pass rate < 90% → P2 incident
- Indicates potential quality issues

#### 8. System Health

**Metrics:**
- `CPUUtilization` (Percent)
- `MemoryUtilization` (Percent)
- `DatabaseConnections` (Count)
- `RedisConnections` (Count)

**Expected Values:**
- CPU: 30-70% (sustained)
- Memory: 50-80%
- DB connections: < 80% of pool size
- Redis connections: < 80% of max

**Alert Conditions:**
- CPU > 90% for 5 minutes → Scale up
- Memory > 90% for 5 minutes → Scale up
- DB connections > 90% pool → P1 incident

---

## CloudWatch Metrics Reference

### Custom Metrics

All metrics published to namespace: `FA-AI-System`

#### Batch Processing Metrics

| Metric Name | Unit | Dimensions | Description |
|-------------|------|------------|-------------|
| `StocksProcessed` | Count | WorkloadType=Batch | Number of stocks processed |
| `BatchSuccessRate` | Percent | WorkloadType=Batch | Percentage of successful stocks |
| `BatchDuration` | Seconds | WorkloadType=Batch | Total batch run time |
| `CostPerStock` | None | WorkloadType=Batch | Average cost per stock |
| `RetryCount` | Count | WorkloadType=Batch | Number of retries needed |

#### Query Metrics

| Metric Name | Unit | Dimensions | Description |
|-------------|------|------------|-------------|
| `QueryCount` | Count | Tier=Hook/Medium/Expanded | Number of queries |
| `QueryLatency` | Milliseconds | Tier | Query response time |
| `QuerySuccess` | Count | Tier | Successful queries |
| `QueryFailure` | Count | Tier | Failed queries |
| `CostPerQuery` | None | Tier | Average cost per query |

#### Quality Metrics

| Metric Name | Unit | Dimensions | Description |
|-------------|------|------------|-------------|
| `GuardrailPassRate` | Percent | - | Percentage passing guardrails |
| `FactCheckPass` | Count | - | Summaries passing fact check |
| `FactCheckFail` | Count | - | Summaries failing fact check |
| `HallucinationDetected` | Count | Risk=Low/Medium/High/Critical | Hallucinations by risk level |
| `CitationCount` | Count | SourceType=EDGAR/BlueMatrix/FactSet | Citations by source |

#### Cost Metrics

| Metric Name | Unit | Dimensions | Description |
|-------------|------|------------|-------------|
| `TokensUsed` | Count | Model=Sonnet/Haiku | Tokens consumed by model |
| `APICallCount` | Count | API=Anthropic/OpenAI | External API calls |
| `DailyCost` | None | - | Total daily cost |
| `MonthlyCost` | None | - | Total monthly cost |

#### System Metrics

| Metric Name | Unit | Dimensions | Description |
|-------------|------|------------|-------------|
| `DatabaseConnections` | Count | - | Active DB connections |
| `DatabaseQueryTime` | Milliseconds | QueryType | DB query duration |
| `RedisHitRate` | Percent | CacheType=Embedding/Query | Cache hit percentage |
| `VectorSearchTime` | Milliseconds | Collection | Vector search duration |

---

## CloudWatch Alarms

### Critical Alarms (P0)

#### 1. Service Outage

```bash
aws cloudwatch put-metric-alarm \
  --alarm-name "FA-AI-Service-Outage" \
  --alarm-description "All queries failing" \
  --metric-name QueryFailure \
  --namespace FA-AI-System \
  --statistic Sum \
  --period 300 \
  --threshold 50 \
  --comparison-operator GreaterThanThreshold \
  --evaluation-periods 2 \
  --alarm-actions arn:aws:sns:us-east-1:account-id:critical-alerts
```

#### 2. Database Connection Pool Exhausted

```bash
aws cloudwatch put-metric-alarm \
  --alarm-name "FA-AI-DB-Pool-Exhausted" \
  --alarm-description "Database connection pool at capacity" \
  --metric-name DatabaseConnections \
  --namespace FA-AI-System \
  --statistic Average \
  --period 60 \
  --threshold 18 \
  --comparison-operator GreaterThanThreshold \
  --evaluation-periods 3
```

### High Priority Alarms (P1)

#### 3. High Error Rate

```bash
aws cloudwatch put-metric-alarm \
  --alarm-name "FA-AI-High-Error-Rate" \
  --alarm-description "Error rate exceeds 10%" \
  --metric-name ErrorRate \
  --namespace FA-AI-System \
  --statistic Average \
  --period 300 \
  --threshold 10 \
  --comparison-operator GreaterThanThreshold \
  --evaluation-periods 2 \
  --alarm-actions arn:aws:sns:us-east-1:account-id:high-priority-alerts
```

#### 4. Slow Query Performance

```bash
aws cloudwatch put-metric-alarm \
  --alarm-name "FA-AI-Slow-Queries" \
  --alarm-description "P95 latency exceeds 5 seconds" \
  --metric-name QueryLatency \
  --namespace FA-AI-System \
  --extended-statistic p95 \
  --period 300 \
  --threshold 5000 \
  --comparison-operator GreaterThanThreshold \
  --evaluation-periods 2
```

### Medium Priority Alarms (P2)

#### 5. Batch Success Rate Degraded

```bash
aws cloudwatch put-metric-alarm \
  --alarm-name "FA-AI-Batch-Success-Degraded" \
  --alarm-description "Batch success rate below 95%" \
  --metric-name BatchSuccessRate \
  --namespace FA-AI-System \
  --statistic Average \
  --period 3600 \
  --threshold 95 \
  --comparison-operator LessThanThreshold \
  --evaluation-periods 1
```

#### 6. Cost Budget Warning

```bash
aws cloudwatch put-metric-alarm \
  --alarm-name "FA-AI-Cost-Budget-Warning" \
  --alarm-description "Monthly cost approaching budget" \
  --metric-name MonthlyCost \
  --namespace FA-AI-System \
  --statistic Maximum \
  --period 86400 \
  --threshold 1800 \
  --comparison-operator GreaterThanThreshold \
  --evaluation-periods 1
```

---

## CloudWatch Logs

### Log Groups

| Log Group | Purpose | Retention |
|-----------|---------|-----------|
| `/ecs/fa-ai-system-blue` | Blue environment application logs | 30 days |
| `/ecs/fa-ai-system-green` | Green environment application logs | 30 days |
| `/aws/lambda/fa-ai-*` | Lambda function logs (if any) | 7 days |
| `/aws/rds/fa-ai-db` | Database logs | 7 days |

### Log Formats

**Application Logs (JSON):**
```json
{
  "timestamp": "2024-11-07T12:00:00.123Z",
  "level": "INFO",
  "logger": "src.batch.agents.medium_writer",
  "message": "Generated medium summary for AAPL",
  "context": {
    "ticker": "AAPL",
    "batch_run_id": "batch-20241107-023000",
    "word_count": 138,
    "processing_time_ms": 1247,
    "model": "claude-3-5-sonnet-20241022",
    "cost": 0.023
  }
}
```

**Error Logs:**
```json
{
  "timestamp": "2024-11-07T12:00:00.123Z",
  "level": "ERROR",
  "logger": "src.batch.nodes.edgar_ingestion",
  "message": "Failed to fetch EDGAR filing",
  "context": {
    "ticker": "AAPL",
    "filing_type": "10-K",
    "error_type": "HTTPError",
    "status_code": 503,
    "retry_count": 3
  },
  "stack_trace": "..."
}
```

### Useful Log Queries

#### Find All Errors in Last Hour

```
fields @timestamp, logger, message, context.ticker, context.error_type
| filter level = "ERROR"
| sort @timestamp desc
| limit 100
```

#### Track Batch Run Progress

```
fields @timestamp, message, context.ticker, context.processing_time_ms
| filter batch_run_id = "batch-20241107-023000"
| stats count(*) by context.status
```

#### Find Slow Queries (> 3s)

```
fields @timestamp, context.ticker, context.question, context.processing_time_ms
| filter context.processing_time_ms > 3000
| sort context.processing_time_ms desc
| limit 50
```

#### Cost Analysis by Model

```
fields @timestamp, context.model, context.cost
| filter context.cost > 0
| stats sum(context.cost) as total_cost by context.model
```

#### Fact Check Failures

```
fields @timestamp, context.ticker, context.fact_check_details
| filter context.fact_check_status = "failed"
| sort @timestamp desc
```

---

## LangSmith Monitoring

### Accessing LangSmith

```
https://smith.langchain.com/o/<org-id>/projects/fa-ai-system-production
```

### Key Features

#### 1. Traces

**View Full Request Flow:**
- Every query/batch run generates a trace
- See all LLM calls, embeddings, database queries
- Token usage per step
- Latency breakdown

**Example Trace:**
```
Query: "What were AAPL Q4 earnings?"
├─ classify_intent (100ms, 250 tokens)
├─ vector_search (450ms, 1536-dim embeddings)
├─ generate_response (1200ms, 1800 tokens)
│  ├─ claude-3-5-sonnet call (1150ms)
│  └─ format_response (50ms)
└─ fact_check (800ms, 2200 tokens)
   └─ claude-3-5-sonnet call (750ms)

Total: 2550ms, $0.023
```

#### 2. Evaluations

**Automated Regression Tests:**
- Run daily after batch processing
- Compare against ground truth dataset
- 5 evaluators: fact accuracy, citation quality, word count, response time, guardrail pass

**Evaluation Results:**
```
Experiment: regression-20241107
Dataset: fa-ai-regression-suite (100 examples)

Results:
- Fact Accuracy: 92.5% (target: > 80%)
- Citation Quality: 88.0% (target: > 75%)
- Word Count: 95.0% (target: > 90%)
- Response Time: 89.0% (target: > 85%)
- Guardrail Pass: 100.0% (target: 100%)

Overall: PASS ✅
```

#### 3. Playground

Test prompts interactively:
- Edit prompts and see real-time results
- Compare different model versions
- A/B test prompt variations

#### 4. Datasets

**Test Datasets:**
- `fa-ai-regression-suite`: 100 verified stock summaries
- `fa-ai-edge-cases`: 50 challenging queries
- `fa-ai-hallucination-tests`: 25 known hallucination scenarios

---

## Monitoring Workflows

### Daily Health Check (9 AM)

```bash
#!/bin/bash
# scripts/monitoring/daily_health_check.sh

echo "=== Daily Health Check ==="
echo ""

# 1. Check ECS service status
echo "1. ECS Service Status:"
aws ecs describe-services \
  --cluster fa-ai-system-cluster \
  --services fa-ai-system-blue-service \
  --query 'services[0].{Running: runningCount, Desired: desiredCount, Pending: pendingCount}' \
  --output table

# 2. Check yesterday's batch
echo ""
echo "2. Yesterday's Batch Run:"
python scripts/check_batch_status.py --date yesterday

# 3. Check error rate (last 24h)
echo ""
echo "3. Error Rate (Last 24 Hours):"
aws cloudwatch get-metric-statistics \
  --namespace FA-AI-System \
  --metric-name ErrorRate \
  --start-time $(date -u -d '24 hours ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 3600 \
  --statistics Average \
  --query 'Datapoints[*].[Timestamp,Average]' \
  --output table

# 4. Check cost (last 7 days)
echo ""
echo "4. Cost Trend (Last 7 Days):"
python scripts/monitoring/cost_report.py --days 7

# 5. Check active alarms
echo ""
echo "5. Active CloudWatch Alarms:"
aws cloudwatch describe-alarms \
  --state-value ALARM \
  --query 'MetricAlarms[*].[AlarmName,StateReason]' \
  --output table

echo ""
echo "=== Health Check Complete ==="
```

### Weekly Performance Review (Monday 10 AM)

```bash
# scripts/monitoring/weekly_review.sh

# 1. Generate LangSmith evaluation report
python tests/regression/run_regression_tests.py

# 2. Cost analysis
streamlit run dashboards/cost_dashboard.py --server.headless true --server.port 8501 &
echo "Cost dashboard: http://localhost:8501"

# 3. A/B test results
python scripts/analyze_ab_tests.py --week last

# 4. Performance trends
python scripts/monitoring/performance_trends.py --days 7
```

### Monthly Cost Review (1st of Month)

```bash
# scripts/monitoring/monthly_cost_review.sh

# 1. Generate cost report
python scripts/export_cost_report.py --month last --format pdf

# 2. Compare to budget
BUDGET=2000
ACTUAL=$(aws cloudwatch get-metric-statistics \
  --namespace FA-AI-System \
  --metric-name MonthlyCost \
  --start-time $(date -u -d '1 month ago' +%Y-%m-01T00:00:00) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 2592000 \
  --statistics Maximum \
  --query 'Datapoints[0].Maximum' \
  --output text)

echo "Budget: \$$BUDGET"
echo "Actual: \$$ACTUAL"
echo "Utilization: $(echo "scale=1; $ACTUAL / $BUDGET * 100" | bc)%"

# 3. Identify cost optimization opportunities
python scripts/monitoring/cost_optimization_report.py --month last
```

---

## Alerting Channels

### SNS Topics

| Topic | Severity | Subscribers |
|-------|----------|-------------|
| `fa-ai-critical-alerts` | P0 | PagerDuty, On-call phone, Slack #incidents |
| `fa-ai-high-priority-alerts` | P1 | On-call email, Slack #alerts |
| `fa-ai-medium-priority-alerts` | P2 | Email, Slack #monitoring |
| `fa-ai-info-alerts` | Info | Slack #fa-ai-notifications |

### Slack Integration

```bash
# Set up Slack webhook
aws sns subscribe \
  --topic-arn arn:aws:sns:us-east-1:account-id:fa-ai-critical-alerts \
  --protocol https \
  --notification-endpoint https://hooks.slack.com/services/T00/B00/XXXX
```

**Slack Message Format:**
```
🚨 [P0] FA AI System - Service Outage
Alarm: FA-AI-Service-Outage
Metric: QueryFailure
Threshold: > 50 in 10 minutes
Current Value: 87
Time: 2024-11-07 12:00:00 UTC

Runbook: https://docs.fa-ai.com/runbooks/service-outage
Dashboard: https://console.aws.amazon.com/cloudwatch/...
```

---

## Troubleshooting with Metrics

### Issue: High Latency

**Investigate:**
```bash
# 1. Check P95 latency trend
aws cloudwatch get-metric-statistics \
  --namespace FA-AI-System \
  --metric-name QueryLatency \
  --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 300 \
  --extended-statistics p95 \
  --output table

# 2. Check database query times
aws cloudwatch get-metric-statistics \
  --namespace FA-AI-System \
  --metric-name DatabaseQueryTime \
  --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 300 \
  --statistics Average,Maximum

# 3. Check vector search times
aws cloudwatch get-metric-statistics \
  --namespace FA-AI-System \
  --metric-name VectorSearchTime \
  --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 300 \
  --statistics Average,Maximum
```

### Issue: High Cost

**Investigate:**
```bash
# 1. Check token usage by model
aws cloudwatch get-metric-statistics \
  --namespace FA-AI-System \
  --metric-name TokensUsed \
  --dimensions Name=Model,Value=claude-3-5-sonnet-20241022 \
  --start-time $(date -u -d '24 hours ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 3600 \
  --statistics Sum

# 2. Analyze cost by agent
python scripts/monitoring/analyze_cost.py --by-agent --last-24h

# 3. Check for anomalies
python scripts/monitoring/detect_cost_anomalies.py
```

### Issue: Low Guardrail Pass Rate

**Investigate:**
```bash
# 1. Check fact check failure rate
aws cloudwatch get-metric-statistics \
  --namespace FA-AI-System \
  --metric-name FactCheckFail \
  --start-time $(date -u -d '24 hours ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 3600 \
  --statistics Sum

# 2. View recent failures in logs
aws logs filter-pattern '{ $.context.fact_check_status = "failed" }' \
  --log-group-name /ecs/fa-ai-system-blue \
  --start-time $(date -u -d '1 hour ago' +%s)000

# 3. Analyze hallucination patterns
python scripts/monitoring/analyze_hallucinations.py --last-24h
```

---

## Best Practices

1. **Review dashboards daily** - 5-minute morning check
2. **Investigate all alarms** - Even if auto-resolved
3. **Monitor costs weekly** - Catch trends early
4. **Run regression tests weekly** - Ensure quality
5. **Archive old logs** - After 30 days to S3
6. **Update dashboards** - As system evolves
7. **Test alerts** - Monthly drill
8. **Document incidents** - In runbook for learning

---

## Additional Resources

- [Operations Runbook](./OPERATIONS_RUNBOOK.md) - Incident response procedures
- [Deployment Guide](./DEPLOYMENT_GUIDE.md) - Deployment and rollback
- [Architecture Documentation](./ARCHITECTURE.md) - System design
