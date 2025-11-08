# FA AI System - Operations Runbook

## Overview

This runbook provides step-by-step procedures for operating and troubleshooting the FA AI System in production.

## Table of Contents

- [Daily Operations](#daily-operations)
- [Incident Response](#incident-response)
- [Common Issues](#common-issues)
- [Performance Tuning](#performance-tuning)
- [Database Operations](#database-operations)
- [Cost Management](#cost-management)
- [On-Call Procedures](#on-call-procedures)

---

## Daily Operations

### Morning Health Check (Daily 9 AM)

```bash
# 1. Check service status
aws ecs describe-services \
  --cluster fa-ai-system-cluster \
  --services fa-ai-system-blue-service fa-ai-system-green-service \
  --region us-east-1

# 2. View CloudWatch dashboard
# Navigate to: CloudWatch > Dashboards > FA-AI-System-Production

# 3. Check yesterday's batch run
python scripts/check_batch_status.py --date yesterday

# 4. Review error logs
aws logs filter-pattern '{ $.level = "ERROR" }' \
  --log-group-name /ecs/fa-ai-system-blue \
  --start-time 24h
```

**Expected Results:**
- ✅ All ECS tasks: RUNNING
- ✅ Target health: 100% healthy
- ✅ Error rate: < 1%
- ✅ P95 latency: < 3s
- ✅ Yesterday's batch: 100% success

**Action if Failed:**
- If any check fails → See [Incident Response](#incident-response)

### Weekly Batch Processing (Sunday 2 AM)

Automated via cron, but verify completion:

```bash
# Check last batch run
python src/batch/run_batch_phase2.py --check-last-run

# Expected output:
# Batch Run: <batch-id>
# Start Time: 2024-XX-XX 02:00:00
# End Time: 2024-XX-XX 05:30:00
# Total Stocks: 1000
# Successful: 990 (99%)
# Failed: 10 (1%)
# Total Cost: $385.00 ($0.385/stock)
```

**Acceptable Ranges:**
- Success rate: > 95%
- Cost per stock: < $0.40
- Duration: < 4 hours

### Monthly Cost Review (1st of Month)

```bash
# Launch cost dashboard
streamlit run dashboards/cost_dashboard.py

# Review:
# 1. Total monthly spend vs budget
# 2. Cost per stock trend
# 3. Cost per query trend
# 4. Model usage distribution (Sonnet vs Haiku)

# Export cost report
python scripts/export_cost_report.py --month last
```

---

## Incident Response

### Severity Levels

| Severity | Description | Response Time | Examples |
|----------|-------------|---------------|----------|
| P0 (Critical) | Complete service outage | 15 minutes | All queries failing, batch system down |
| P1 (High) | Degraded service | 1 hour | High error rate (>10%), slow responses |
| P2 (Medium) | Partial impact | 4 hours | Single feature broken, moderate errors |
| P3 (Low) | Minor issue | Next business day | Minor bugs, cosmetic issues |

### P0: Complete Service Outage

**Symptoms:**
- Health check endpoint returning 503
- All queries timing out
- Zero healthy targets in ALB

**Immediate Actions:**

```bash
# 1. Check ECS service status
aws ecs describe-services \
  --cluster fa-ai-system-cluster \
  --services fa-ai-system-blue-service \
  --region us-east-1

# 2. Check recent deployments
terraform output -json | jq '{blue: .blue_weight.value, green: .green_weight.value}'

# 3. If recent deployment, rollback immediately
cd scripts/deployment
./rollback.sh

# 4. Check task health
aws ecs list-tasks \
  --cluster fa-ai-system-cluster \
  --service-name fa-ai-system-blue-service \
  --region us-east-1

# 5. View task logs
aws logs tail /ecs/fa-ai-system-blue --follow --since 30m
```

**Common Causes:**
1. **Recent deployment issue** → Rollback via `./rollback.sh`
2. **Database connection pool exhausted** → Restart tasks, tune pool size
3. **API key expired/invalid** → Rotate keys in AWS Secrets Manager
4. **Resource exhaustion (CPU/memory)** → Scale up task count

**Resolution Steps:**
1. Identify root cause from logs
2. Execute appropriate fix (rollback, restart, scale)
3. Verify service recovery
4. Document incident in incident log
5. Schedule post-mortem within 48 hours

### P1: High Error Rate

**Symptoms:**
- Error rate: 10-30%
- Some queries succeeding
- Degraded performance

**Diagnostic Steps:**

```bash
# 1. Check CloudWatch metrics
# Error rate, latency, guardrail failures

# 2. Sample error logs
aws logs filter-pattern '{ $.level = "ERROR" }' \
  --log-group-name /ecs/fa-ai-system-blue \
  --start-time 1h \
  | head -50

# 3. Check external dependencies
# - Anthropic API status
# - OpenAI embeddings API status
# - Database connectivity
# - Redis connectivity

# 4. Check rate limits
grep "rate_limit" /var/log/fa-ai-system/app.log
```

**Common Patterns:**

| Error Pattern | Cause | Solution |
|---------------|-------|----------|
| "429 Too Many Requests" | API rate limit | Implement exponential backoff, request limit increase |
| "Connection timeout" | Database/Redis issue | Check connection pool, restart if needed |
| "Fact check failed" | Hallucination detected | Review guardrail thresholds, check source data quality |
| "Vector search failed" | pgvector issue | Check index health, rebuild if needed |

### P2: Partial Feature Broken

**Examples:**
- Hook summaries working, but expanded failing
- BlueMatrix ingestion failing, but EDGAR working
- Cost tracking not publishing to CloudWatch

**Response:**
1. Isolate affected component
2. Check component-specific logs
3. Review recent code changes
4. Deploy hotfix if critical, otherwise schedule fix

---

## Common Issues

### Issue: "Batch Processing Taking Too Long"

**Symptoms:**
- Batch run exceeding 4 hours
- Low throughput (< 250 stocks/hour)

**Diagnosis:**

```bash
# Check concurrent processing
python src/batch/run_batch_phase2.py --check-stats

# View active workers
ps aux | grep "batch.*phase2"

# Check database query performance
psql $DATABASE_URL -c "SELECT query, calls, mean_exec_time FROM pg_stat_statements ORDER BY mean_exec_time DESC LIMIT 20;"
```

**Solutions:**

1. **Increase concurrency:**
```python
# src/config/settings.py
batch_max_concurrency: int = 150  # Increase from 100
```

2. **Check embedding cache:**
```bash
redis-cli
> KEYS embedding_cache:*
> INFO memory
```

3. **Optimize database:**
```sql
-- Check index usage
SELECT schemaname, tablename, indexname, idx_scan
FROM pg_stat_user_indexes
WHERE idx_scan = 0;

-- Vacuum and analyze
VACUUM ANALYZE stock_summaries;
VACUUM ANALYZE citations;
```

### Issue: "High API Costs"

**Symptoms:**
- Cost per stock > $0.40
- Cost per query > $0.08
- Unexpected spike in Anthropic bills

**Diagnosis:**

```bash
# Launch cost dashboard
streamlit run dashboards/cost_dashboard.py

# Check model distribution
python scripts/analyze_model_usage.py --last-24h

# Expected:
# Sonnet: 60% (complex tasks)
# Haiku: 40% (simple tasks)
```

**Solutions:**

1. **Enable Haiku router:**
```python
# src/config/settings.py
enable_haiku_routing: bool = True
```

2. **Reduce word count targets:**
```python
# Adjust if consistently overshooting
word_count_targets = {
    "hook": (20, 40),      # Reduced from (25, 50)
    "medium": (90, 130),   # Reduced from (100, 150)
    "expanded": (180, 220) # Reduced from (200, 250)
}
```

3. **Review prompt efficiency:**
```bash
# Check token usage by agent
python scripts/analyze_token_usage.py --by-agent
```

### Issue: "Hallucination Detection Failures"

**Symptoms:**
- High false positive rate
- Summaries being rejected incorrectly
- Fact check layer failures

**Diagnosis:**

```bash
# Check hallucination detection stats
python scripts/analyze_hallucinations.py --last-week

# View rejected summaries
psql $DATABASE_URL -c "SELECT ticker, fact_check_status, fact_check_details FROM stock_summaries WHERE fact_check_status = 'failed' ORDER BY updated_at DESC LIMIT 10;"
```

**Solutions:**

1. **Adjust thresholds:**
```python
# src/shared/utils/hallucination_detector.py
LAYER_WEIGHTS = {
    "cross_source": 0.4,    # Reduced from 0.5
    "temporal": 0.3,        # Increased from 0.2
    "uncertainty": 0.3
}

RISK_THRESHOLDS = {
    HallucinationRisk.CRITICAL: 0.8,  # Increased from 0.7
    HallucinationRisk.HIGH: 0.6,
    HallucinationRisk.MEDIUM: 0.4,
    HallucinationRisk.LOW: 0.0
}
```

2. **Improve source data quality:**
```bash
# Check source data coverage
python scripts/check_source_coverage.py

# Expected:
# EDGAR: 100%
# BlueMatrix: > 80%
# FactSet: 100%
```

### Issue: "Database Connection Pool Exhausted"

**Symptoms:**
- "could not obtain connection from pool"
- Slow query responses
- Connection timeouts

**Immediate Fix:**

```bash
# Restart ECS tasks to reset connections
aws ecs update-service \
  --cluster fa-ai-system-cluster \
  --service fa-ai-system-blue-service \
  --force-new-deployment \
  --region us-east-1
```

**Long-term Solution:**

```python
# src/shared/database/connection.py
engine = create_engine(
    settings.database_url,
    poolclass=QueuePool,
    pool_size=20,          # Increase from 10
    max_overflow=30,       # Increase from 20
    pool_timeout=30,
    pool_recycle=3600
)
```

---

## Performance Tuning

### Batch Processing Optimization

**Target Metrics:**
- Throughput: > 250 stocks/hour
- Success rate: > 95%
- Cost per stock: < $0.40

**Tuning Parameters:**

```python
# src/config/settings.py

# Concurrency
batch_max_concurrency: int = 100  # Adjust based on load

# Embedding
embedding_batch_size: int = 100  # Higher = faster, more memory
embedding_cache_ttl: int = 604800  # 7 days

# Database
db_pool_size: int = 20
db_max_overflow: int = 30

# Redis
redis_max_connections: int = 50
```

**Monitoring:**

```bash
# Real-time batch monitoring
python src/batch/run_batch_phase2.py --concurrent --max-concurrent 100 --verbose

# Expected output every 5 minutes:
# [Progress] 250/1000 stocks (25%) | 50 stocks/min | ETA: 15 min
```

### Query Response Time Optimization

**Target SLA:**
- P50: < 1s
- P95: < 3s
- P99: < 5s

**Optimization Checklist:**

1. **Enable query caching:**
```python
# Cache identical queries for 5 minutes
@lru_cache(maxsize=1000)
def query_stock(ticker: str, question: str) -> QueryResponse:
    ...
```

2. **Optimize vector search:**
```sql
-- Ensure HNSW index is optimal
CREATE INDEX IF NOT EXISTS idx_bluematrix_embedding
ON bluematrix_reports
USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 200);  -- Adjust m and ef_construction
```

3. **Use model router:**
```python
# Simple queries use Haiku (4x faster, 4x cheaper)
model_router = ModelRouter(enable_haiku=True)
```

---

## Database Operations

### Backup Procedures

**Automated Daily Backups:**
```bash
# RDS automated backups (7-day retention)
aws rds describe-db-snapshots \
  --db-instance-identifier fa-ai-system-db \
  --region us-east-1
```

**Manual Backup:**
```bash
# Full database backup
pg_dump $DATABASE_URL > backup_$(date +%Y%m%d).sql

# Backup to S3
aws s3 cp backup_$(date +%Y%m%d).sql s3://fa-ai-backups/db/
```

### Database Maintenance

**Weekly Maintenance (Sunday 3 AM):**

```sql
-- Vacuum and analyze
VACUUM ANALYZE;

-- Reindex for performance
REINDEX DATABASE fa_ai_db;

-- Check for bloat
SELECT schemaname, tablename,
       pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;
```

**Monthly Maintenance (1st Sunday):**

```sql
-- Update statistics
ANALYZE VERBOSE;

-- Check index health
SELECT indexrelname, idx_scan, idx_tup_read, idx_tup_fetch
FROM pg_stat_user_indexes
ORDER BY idx_scan ASC;

-- Archive old data (> 1 year)
DELETE FROM batch_audit WHERE created_at < NOW() - INTERVAL '1 year';
```

---

## Cost Management

### Budget Alerts

**Monthly Budget: $2,000**

- Batch processing: $1,200 (60%)
- Interactive queries: $600 (30%)
- Infrastructure: $200 (10%)

**Alert Thresholds:**
- 50% ($1,000) → Warning email
- 75% ($1,500) → Slack notification
- 90% ($1,800) → Page on-call engineer
- 100% ($2,000) → Auto-disable batch processing

### Cost Optimization Actions

**If costs exceed budget:**

1. **Reduce batch frequency:**
```bash
# Change from daily to every 3 days
crontab -e
# 0 2 */3 * * python src/batch/run_batch_phase2.py
```

2. **Increase Haiku usage:**
```python
# src/shared/utils/model_router.py
# Change more tasks to SIMPLE complexity
self.task_complexity_map = {
    "hook_summary": TaskComplexity.SIMPLE,
    "medium_summary": TaskComplexity.SIMPLE,      # Changed from MODERATE
    "expanded_summary": TaskComplexity.MODERATE,  # Changed from COMPLEX
    "fact_check": TaskComplexity.COMPLEX,
}
```

3. **Reduce embeddings:**
```python
# Use cached embeddings more aggressively
embedding_cache_ttl: int = 2592000  # 30 days instead of 7
```

---

## On-Call Procedures

### On-Call Rotation

- Primary: Week 1, 3, 5...
- Secondary: Week 2, 4, 6...
- Escalation: Engineering Manager

### Runbook for On-Call

**When Paged:**

1. **Acknowledge alert** (within 5 minutes)
2. **Check severity** (P0/P1/P2/P3)
3. **Follow incident response** (see above)
4. **Update status page** if user-facing
5. **Document actions** in incident log
6. **Resolve and close** alert

### Escalation Path

1. **Primary on-call** (15 minutes)
2. **Secondary on-call** (30 minutes)
3. **Engineering manager** (1 hour)
4. **VP Engineering** (2 hours)

### Contact Information

```
Primary On-Call: [PagerDuty rotation]
Secondary On-Call: [PagerDuty rotation]
Engineering Manager: manager@example.com
Status Page: https://status.fa-ai-system.com
```

---

## Monitoring Dashboards

### CloudWatch Dashboard

**URL:** CloudWatch > Dashboards > FA-AI-System-Production

**Key Widgets:**
1. Batch Volume & Success Rate
2. Query Volume by Tier
3. Response Times (P50, P95, P99)
4. Error Rates
5. Cost Metrics
6. System Health (CPU, Memory, Connections)

### LangSmith Dashboard

**URL:** https://smith.langchain.com/o/<org>/projects/<project>

**Monitor:**
- Trace latency
- Token usage
- Agent performance
- Evaluation scores

---

## Additional Resources

- [Deployment Guide](./DEPLOYMENT_GUIDE.md)
- [Architecture Documentation](./ARCHITECTURE.md)
- [Monitoring Guide](./MONITORING_GUIDE.md)
- [Incident Log](../runbooks/incident_log.md)
