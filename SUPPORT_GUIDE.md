# Application Support Guide: Financial Advisor AI Assistant

**Version:** 1.0
**Date:** November 7, 2025
**Audience:** Application Support Team
**Classification:** Internal Use

---

## Table of Contents

1. [System Overview](#system-overview)
2. [Architecture & Components](#architecture--components)
3. [Monitoring & Observability](#monitoring--observability)
4. [Daily Operations](#daily-operations)
5. [Common Issues & Troubleshooting](#common-issues--troubleshooting)
6. [Runbooks](#runbooks)
7. [Database Operations](#database-operations)
8. [LangSmith Debugging](#langsmith-debugging)
9. [Performance Troubleshooting](#performance-troubleshooting)
10. [Escalation Procedures](#escalation-procedures)
11. [Emergency Procedures](#emergency-procedures)
12. [Maintenance Windows](#maintenance-windows)

---

## System Overview

### What is the Financial Advisor AI Assistant?

An enterprise-grade multi-agent AI system that automatically synthesizes financial information from multiple sources (SEC EDGAR, BlueMatrix, FactSet) into three-tier summaries for financial advisors.

### Key Capabilities

- **Batch Processing**: Processes 1,000 stocks nightly in < 2 hours
- **Interactive Queries**: Real-time Q&A with < 60 second response time
- **Multi-Source Intelligence**: Combines EDGAR, BlueMatrix, FactSet data
- **Quality Control**: 95%+ accuracy with multi-layer fact-checking
- **Full Observability**: LangSmith tracing for every operation

### SLA Targets

| Metric | Target | Escalation Threshold |
|--------|--------|---------------------|
| Batch completion time | < 2 hours | > 3 hours |
| Batch success rate | > 99% | < 95% |
| Interactive response time (p95) | < 60 seconds | > 90 seconds |
| System uptime | 99.9% | < 99.5% |
| Fact-check pass rate | > 95% | < 90% |
| Hallucination rate | < 1% | > 2% |

---

## Architecture & Components

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Financial Advisors                       │
│                  (Web UI / API Clients)                      │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    Load Balancer (ALB)                       │
└─────────────────────────────────────────────────────────────┘
                              │
                ┌─────────────┴─────────────┐
                ▼                           ▼
┌───────────────────────────┐   ┌───────────────────────────┐
│   Batch Processing        │   │  Interactive Query API     │
│   (ECS Fargate)           │   │  (ECS Fargate)             │
│   - Nightly runs          │   │  - FastAPI / Uvicorn       │
│   - Concurrent workers    │   │  - LangGraph runtime       │
└───────────────────────────┘   └───────────────────────────┘
                │                           │
                └─────────────┬─────────────┘
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    PostgreSQL 16 + pgvector                  │
│                    (RDS Multi-AZ)                            │
│   - Stock metadata                                           │
│   - Generated summaries                                      │
│   - Vector embeddings (HNSW index)                          │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    External Services                         │
│   - Claude API (Anthropic)                                   │
│   - OpenAI Embeddings API                                    │
│   - LangSmith (Observability)                               │
│   - EDGAR API (SEC)                                          │
│   - BlueMatrix API                                           │
│   - FactSet API                                              │
└─────────────────────────────────────────────────────────────┘
```

### Key Components

#### 1. Batch Processing Service
- **File**: `src/batch/run_batch_phase2.py`
- **Purpose**: Nightly processing of 1,000 stocks
- **Runtime**: Scheduled cron (1:00 AM ET)
- **Concurrency**: 100 parallel workers (configurable)
- **Outputs**: 3-tier summaries (hook/medium/expanded)

#### 2. Interactive Query API
- **File**: `src/interactive/api/main.py`
- **Purpose**: Real-time Q&A for financial advisors
- **Technology**: FastAPI + LangGraph
- **Port**: 8000
- **Health Check**: `GET /health`

#### 3. PostgreSQL Database
- **Version**: PostgreSQL 16 with pgvector extension
- **Tables**:
  - `stocks` - Company metadata
  - `stock_summaries` - Generated summaries
  - `citations` - Source attribution
  - `batch_audit` - Processing logs
  - `edgar_filings`, `bluematrix_reports`, `factset_*` - Source data
- **Indexes**: HNSW vector indexes (1536 dimensions)

#### 4. LangSmith Integration
- **Purpose**: Observability, tracing, debugging
- **Projects**:
  - `fa-ai-system` - Interactive queries
  - `fa-ai-system-batch` - Batch processing
- **Features**: Full trace capture, prompt management, A/B testing

---

## Monitoring & Observability

### LangSmith Dashboard

**URL**: https://smith.langchain.com/

**Key Views**:

1. **Runs Dashboard** - All LLM invocations
   - Filter by project: `fa-ai-system` or `fa-ai-system-batch`
   - Filter by tags: `ticker:AAPL`, `batch:abc123`, etc.
   - View latency, cost, token usage

2. **Prompts Dashboard** - Prompt versioning
   - 6 managed prompts (hook/medium/expanded writers, fact checker, citation extractor, query classifier)
   - View usage stats, A/B test results

3. **Feedback Dashboard** - Quality metrics
   - Hallucination detection results
   - Fact-check pass rates
   - User feedback

### CloudWatch Metrics (if deployed to AWS)

**Namespace**: `FA-AI-System`

**Key Metrics**:
- `BatchProcessingTime` - Duration of nightly batch
- `BatchSuccessRate` - Percentage of stocks processed successfully
- `InteractiveQueryLatency` - p50, p95, p99 response times
- `DatabaseConnectionPoolSize` - Active connections
- `LLMAPIErrors` - Failed API calls to Claude/OpenAI
- `FactCheckPassRate` - Quality metric
- `HallucinationRate` - Quality metric

**Alarms**:
- Batch processing time > 3 hours
- Batch success rate < 95%
- Interactive query p95 > 90 seconds
- Database connection pool > 80% utilized
- LLM API error rate > 5%

### Log Aggregation

**Location**: CloudWatch Logs (or ECS container logs)

**Log Groups**:
- `/ecs/fa-ai-batch` - Batch processing logs
- `/ecs/fa-ai-interactive` - API server logs

**Key Log Patterns to Monitor**:
```
ERROR - Rate limit exceeded
ERROR - Database connection timeout
ERROR - Fact check failed
WARNING - Hook word count outside target
WARNING - Failed to load prompt from LangSmith
```

---

## Daily Operations

### Morning Checklist (First Thing Every Day)

**Time Required**: 10-15 minutes

1. **Check Batch Processing Results**
   ```bash
   # SSH to batch processing instance or check logs
   tail -n 100 /var/log/fa-ai-batch/latest.log | grep "Batch completed"

   # Look for:
   # - "Batch completed successfully: 1000/1000 stocks"
   # - Total time < 2 hours
   # - Success rate > 99%
   ```

   **Expected Output**:
   ```
   2025-11-07 03:15:42 | INFO | Batch completed successfully: 1000/1000 stocks
   2025-11-07 03:15:42 | INFO | Total time: 1h 47m 23s
   2025-11-07 03:15:42 | INFO | Success rate: 99.8%
   2025-11-07 03:15:42 | INFO | Total cost: $147.32
   ```

2. **Check LangSmith Dashboard**
   - Go to https://smith.langchain.com/
   - Select project: `fa-ai-system-batch`
   - Filter by last 24 hours
   - Verify:
     - ✅ All traces completed successfully
     - ✅ No error spikes
     - ✅ Average cost per stock ≈ $0.15

3. **Check Database Health**
   ```sql
   -- Run in database client (psql or pgAdmin)

   -- Check latest batch run
   SELECT
       batch_run_id,
       status,
       started_at,
       completed_at,
       stocks_processed,
       stocks_succeeded,
       stocks_failed
   FROM batch_audit
   ORDER BY started_at DESC
   LIMIT 1;

   -- Expected: status='completed', stocks_succeeded ≈ 1000, stocks_failed < 10
   ```

4. **Check Interactive API Health**
   ```bash
   curl http://localhost:8000/health

   # Expected response:
   # {"status":"healthy","database":"connected","version":"1.0.0"}
   ```

5. **Review CloudWatch Alarms** (if configured)
   - Check AWS Console → CloudWatch → Alarms
   - Verify no critical alarms in "ALARM" state

### Weekly Checklist (Every Monday)

**Time Required**: 30 minutes

1. **Review Weekly Metrics**
   - Batch success rate (should be > 99%)
   - Average batch processing time
   - Interactive query volume
   - Top 10 most queried stocks

2. **Database Maintenance**
   ```sql
   -- Check database size growth
   SELECT
       schemaname,
       tablename,
       pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
   FROM pg_tables
   WHERE schemaname = 'public'
   ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;

   -- Run VACUUM ANALYZE on large tables
   VACUUM ANALYZE stock_summaries;
   VACUUM ANALYZE citations;
   VACUUM ANALYZE edgar_filings;
   ```

3. **Review Cost Trends**
   - LLM API costs (Claude + OpenAI)
   - Data API costs (BlueMatrix + FactSet)
   - AWS infrastructure costs
   - Target: < $275/day total

4. **Check for Stale Data**
   ```sql
   -- Find stocks with no recent summaries
   SELECT
       s.ticker,
       s.company_name,
       MAX(ss.created_at) as last_summary
   FROM stocks s
   LEFT JOIN stock_summaries ss ON s.stock_id = ss.stock_id
   GROUP BY s.ticker, s.company_name
   HAVING MAX(ss.created_at) < NOW() - INTERVAL '7 days'
   ORDER BY last_summary;
   ```

---

## Common Issues & Troubleshooting

### Issue 1: Batch Processing Didn't Complete

**Symptoms**:
- No batch completion log message
- Missing summaries in database
- Users complaining about stale data

**Diagnosis**:
```bash
# Check batch logs
tail -n 500 /var/log/fa-ai-batch/latest.log

# Look for errors like:
# - "Rate limit exceeded"
# - "Database connection timeout"
# - "Out of memory"
```

**Resolution**:

1. **Rate Limit Error**:
   ```
   ERROR - Rate limit exceeded from Claude API
   ```
   - **Cause**: Too many concurrent requests to Claude
   - **Fix**: Reduce `max_concurrent` in config from 100 to 50
   - **File**: Edit `src/config/settings.py` or set env var `MAX_CONCURRENT=50`

2. **Database Connection Timeout**:
   ```
   ERROR - Database connection pool exhausted
   ```
   - **Cause**: Not enough database connections
   - **Fix**: Increase connection pool size
   - **File**: Edit `DATABASE_POOL_SIZE` in `.env` from 10 to 20

3. **Out of Memory**:
   ```
   ERROR - MemoryError: Unable to allocate array
   ```
   - **Cause**: Processing too many stocks concurrently
   - **Fix**: Reduce batch size or increase ECS task memory
   - **Short-term**: Set `MAX_CONCURRENT=25`
   - **Long-term**: Increase ECS task from 4GB to 8GB

**Manual Retry**:
```bash
# SSH to batch processing instance
cd /app
python3 -m src.batch.run_batch_phase2 --limit 1000
```

---

### Issue 2: Interactive Queries Timing Out

**Symptoms**:
- Users report "Request timed out" errors
- Response times > 90 seconds
- 504 Gateway Timeout from load balancer

**Diagnosis**:
```sql
-- Check recent query performance
SELECT
    query_text,
    response_time_ms,
    created_at
FROM query_logs
WHERE created_at > NOW() - INTERVAL '1 hour'
ORDER BY response_time_ms DESC
LIMIT 20;
```

**Resolution**:

1. **Slow Vector Search**:
   - **Cause**: HNSW index not being used
   - **Check**:
     ```sql
     EXPLAIN ANALYZE
     SELECT * FROM stock_summaries
     ORDER BY embedding <-> '[0.1, 0.2, ...]'::vector
     LIMIT 5;

     -- Should show "Index Scan using stock_summaries_embedding_idx"
     -- If it shows "Seq Scan", index is not being used
     ```
   - **Fix**: Rebuild HNSW index
     ```sql
     REINDEX INDEX stock_summaries_embedding_idx;
     ```

2. **LLM API Latency**:
   - **Cause**: Claude API experiencing high latency
   - **Check LangSmith**: Filter by last 1 hour, sort by latency
   - **Fix**:
     - Reduce `max_tokens` in LLM calls (edit prompt constraints)
     - Use cached responses when possible
     - Contact Anthropic support if widespread

3. **Database Connection Pool Exhausted**:
   - **Cause**: Too many concurrent queries
   - **Fix**: Increase connection pool or implement query queuing
   ```python
   # Edit src/config/settings.py
   DATABASE_POOL_SIZE = 20  # Increase from 10
   ```

---

### Issue 3: Fact-Check Failures Spiking

**Symptoms**:
- Fact-check pass rate drops below 95%
- LangSmith shows many "fact_check_failed" tags
- Users reporting inaccurate summaries

**Diagnosis**:
```bash
# Check LangSmith for fact-check failures
# 1. Go to https://smith.langchain.com/
# 2. Filter by tag: "fact_check_failed"
# 3. Review failed examples
```

**Common Causes**:

1. **Stale Source Data**:
   - EDGAR API down or delayed
   - BlueMatrix/FactSet data not updating
   - **Fix**: Check data ingestion pipeline
   ```sql
   -- Check last data refresh
   SELECT
       'edgar' as source,
       MAX(filing_date) as last_data
   FROM edgar_filings
   UNION ALL
   SELECT
       'bluematrix',
       MAX(report_date)
   FROM bluematrix_reports
   UNION ALL
   SELECT
       'factset',
       MAX(price_date)
   FROM factset_price_data;
   ```

2. **Conflicting Data Across Sources**:
   - Different numbers in EDGAR vs FactSet
   - **Fix**: Update fact-checker prompt to handle discrepancies
   - **Escalate to Engineering** if systemic

3. **Hallucination Detection Too Sensitive**:
   - **Fix**: Adjust hallucination threshold in `src/batch/agents/fact_checker.py`
   ```python
   # Lower threshold from 0.9 to 0.85 (less sensitive)
   hallucination_threshold = 0.85
   ```

---

### Issue 4: Missing Citations

**Symptoms**:
- Summaries show "[No citation]" instead of source links
- `citations` table has fewer rows than expected
- Compliance team flags missing audit trail

**Diagnosis**:
```sql
-- Find summaries without citations
SELECT
    ss.summary_id,
    ss.ticker,
    ss.summary_type,
    COUNT(c.citation_id) as citation_count
FROM stock_summaries ss
LEFT JOIN citations c ON ss.summary_id = c.summary_id
WHERE ss.created_at > NOW() - INTERVAL '1 day'
GROUP BY ss.summary_id, ss.ticker, ss.summary_type
HAVING COUNT(c.citation_id) = 0;
```

**Resolution**:

1. **Citation Extractor Agent Failing**:
   - **Check LangSmith**: Filter by tag "citation_extraction"
   - **Common Error**: Prompt parsing issues
   - **Fix**: Update citation extractor prompt in LangSmith hub
   - **Manual Reprocessing**:
     ```bash
     python3 -m src.batch.reprocess_citations --summary-ids 123,456,789
     ```

2. **Database Transaction Rollback**:
   - **Cause**: Summary saved but citations transaction failed
   - **Fix**: Enable better transaction handling
   - **Escalate to Engineering**

---

### Issue 5: High LLM API Costs

**Symptoms**:
- Daily costs > $200 (budget is $150/day)
- Unexpected spikes in Claude API usage
- OpenAI embedding costs increasing

**Diagnosis**:
```bash
# Check LangSmith cost analytics
# 1. Go to https://smith.langchain.com/
# 2. Navigate to "Analytics" → "Cost"
# 3. Group by: "Model"
# 4. Filter: Last 7 days
```

**Common Causes**:

1. **Using Sonnet Instead of Haiku**:
   - **Issue**: All queries using expensive Sonnet model
   - **Fix**: Ensure query classifier routes simple queries to Haiku
   ```python
   # Check src/interactive/agents/query_classifier.py
   # Should route to:
   # - Haiku: Simple fact lookups, single stock queries
   # - Sonnet: Complex analysis, multi-stock comparisons
   ```

2. **Embedding Cache Miss Rate High**:
   - **Issue**: Regenerating embeddings for same content
   - **Fix**: Check cache hit rate
   ```sql
   -- Check embedding cache performance
   SELECT
       DATE(created_at) as date,
       COUNT(*) as total_embeddings,
       SUM(CASE WHEN from_cache = true THEN 1 ELSE 0 END) as cached,
       ROUND(100.0 * SUM(CASE WHEN from_cache = true THEN 1 ELSE 0 END) / COUNT(*), 2) as cache_hit_rate
   FROM embedding_logs
   GROUP BY DATE(created_at)
   ORDER BY date DESC
   LIMIT 7;

   -- Target cache hit rate: > 60%
   ```

3. **Fact-Checker Running Too Many Validations**:
   - **Issue**: Re-validating every claim on every run
   - **Fix**: Enable fact-check caching for unchanged content
   - **Escalate to Engineering**

**Immediate Cost Reduction**:
```bash
# Reduce batch concurrency (slower but cheaper)
export MAX_CONCURRENT=50

# Use Haiku for hook summaries (edit src/batch/agents/hook_writer.py)
model="claude-haiku-20250514"  # Change from sonnet

# Restart batch processing
python3 -m src.batch.run_batch_phase2
```

---

## Runbooks

### Runbook 1: Restart Batch Processing (Manual)

**When to Use**:
- Batch crashed mid-run
- Need to reprocess specific stocks
- Testing new configuration

**Steps**:

1. **SSH to Batch Processing Instance**
   ```bash
   ssh -i ~/.ssh/fa-ai-batch.pem ec2-user@<batch-instance-ip>
   ```

2. **Navigate to Application Directory**
   ```bash
   cd /app/fa-ai-system
   ```

3. **Check Current Status**
   ```bash
   # Check if batch is already running
   ps aux | grep run_batch_phase2

   # If running, note the PID
   ```

4. **Stop Existing Batch (if needed)**
   ```bash
   # Kill gracefully
   pkill -f run_batch_phase2

   # Wait 10 seconds
   sleep 10

   # Force kill if still running
   pkill -9 -f run_batch_phase2
   ```

5. **Start New Batch**
   ```bash
   # Process all stocks (1000)
   python3 -m src.batch.run_batch_phase2 --limit 1000

   # Or process specific ticker
   python3 -m src.batch.run_batch_phase2 --ticker AAPL

   # Or process with validation enabled
   python3 -m src.batch.run_batch_phase2 --limit 1000 --validate
   ```

6. **Monitor Progress**
   ```bash
   # Tail logs in real-time
   tail -f /var/log/fa-ai-batch/latest.log

   # Look for progress indicators:
   # "[1/1000] Processing AAPL..."
   # "[500/1000] Processing TSLA..."
   # "Batch completed successfully"
   ```

7. **Verify Completion**
   ```sql
   -- Check batch audit table
   SELECT * FROM batch_audit
   ORDER BY started_at DESC
   LIMIT 1;

   -- Verify summaries created
   SELECT COUNT(*)
   FROM stock_summaries
   WHERE created_at > NOW() - INTERVAL '2 hours';
   ```

---

### Runbook 2: Restart Interactive API Server

**When to Use**:
- API returning 500 errors
- Health check failing
- Memory leak suspected
- After configuration changes

**Steps**:

1. **Check Current Status**
   ```bash
   # Check if server is running
   curl http://localhost:8000/health

   # Check process
   ps aux | grep uvicorn
   ```

2. **Stop Existing Server**
   ```bash
   # Find and kill uvicorn process
   pkill -f "uvicorn src.interactive"

   # Wait for graceful shutdown
   sleep 5

   # Force kill if needed
   pkill -9 -f "uvicorn src.interactive"
   ```

3. **Start Server**
   ```bash
   cd /app/fa-ai-system

   # Start using script
   ./scripts/start_interactive_server.sh

   # Or start manually
   uvicorn src.interactive.api.main:app \
       --host 0.0.0.0 \
       --port 8000 \
       --workers 4
   ```

4. **Verify Server Started**
   ```bash
   # Wait 10 seconds for startup
   sleep 10

   # Check health endpoint
   curl http://localhost:8000/health

   # Expected: {"status":"healthy","database":"connected","version":"1.0.0"}
   ```

5. **Test Query Endpoint**
   ```bash
   curl -X POST http://localhost:8000/query \
     -H "Content-Type: application/json" \
     -d '{
       "question": "What is the latest news on Apple?",
       "session_id": "test-session"
     }'

   # Should return summary within 60 seconds
   ```

6. **Monitor Logs**
   ```bash
   # Tail server logs
   tail -f /var/log/fa-ai-interactive/latest.log

   # Look for errors or warnings
   ```

---

### Runbook 3: Database Connection Issues

**Symptoms**:
- "Connection pool exhausted" errors
- "Too many connections" errors
- Slow query performance
- Application timeouts

**Steps**:

1. **Check Active Connections**
   ```sql
   -- See all active connections
   SELECT
       pid,
       usename,
       application_name,
       client_addr,
       state,
       query_start,
       state_change,
       LEFT(query, 50) as query_snippet
   FROM pg_stat_activity
   WHERE datname = 'fa_ai_db'
   ORDER BY state_change DESC;

   -- Count by state
   SELECT state, COUNT(*)
   FROM pg_stat_activity
   WHERE datname = 'fa_ai_db'
   GROUP BY state;
   ```

2. **Identify Long-Running Queries**
   ```sql
   -- Find queries running > 1 minute
   SELECT
       pid,
       now() - query_start AS duration,
       state,
       query
   FROM pg_stat_activity
   WHERE state != 'idle'
       AND now() - query_start > interval '1 minute'
   ORDER BY duration DESC;
   ```

3. **Kill Long-Running Queries (if safe)**
   ```sql
   -- Kill specific query
   SELECT pg_terminate_backend(12345);  -- Replace with actual PID

   -- Kill all idle connections (use with caution)
   SELECT pg_terminate_backend(pid)
   FROM pg_stat_activity
   WHERE state = 'idle'
       AND state_change < NOW() - INTERVAL '30 minutes';
   ```

4. **Increase Connection Pool (if needed)**
   ```bash
   # Edit .env file
   vi /app/fa-ai-system/.env

   # Update:
   DATABASE_POOL_SIZE=20  # Increase from 10
   DATABASE_MAX_OVERFLOW=10  # Add overflow capacity

   # Restart application
   ./scripts/restart_all.sh
   ```

5. **Check PostgreSQL Max Connections**
   ```sql
   -- Check max connections setting
   SHOW max_connections;

   -- If needed, increase (requires restart)
   -- ALTER SYSTEM SET max_connections = 200;
   -- Then restart PostgreSQL
   ```

---

### Runbook 4: Rebuild Vector Indexes

**When to Use**:
- Slow vector similarity searches
- Query latency > 90 seconds
- After large data import
- Index corruption suspected

**Steps**:

1. **Check Index Status**
   ```sql
   -- List all vector indexes
   SELECT
       indexname,
       tablename,
       indexdef
   FROM pg_indexes
   WHERE indexdef LIKE '%vector%';

   -- Check index size
   SELECT
       indexname,
       pg_size_pretty(pg_relation_size(indexname::regclass)) as size
   FROM pg_indexes
   WHERE indexdef LIKE '%vector%';
   ```

2. **Analyze Query Performance**
   ```sql
   -- Test vector search with EXPLAIN
   EXPLAIN ANALYZE
   SELECT
       ticker,
       summary_text,
       embedding <-> '[0.1, 0.2, ...]'::vector(1536) AS distance
   FROM stock_summaries
   ORDER BY embedding <-> '[0.1, 0.2, ...]'::vector(1536)
   LIMIT 5;

   -- Should show:
   -- "Index Scan using stock_summaries_embedding_idx"
   -- Planning time: < 1 ms
   -- Execution time: < 100 ms
   ```

3. **Rebuild Index (Off-Peak Hours Only)**
   ```sql
   -- Drop and recreate index
   DROP INDEX IF EXISTS stock_summaries_embedding_idx;

   CREATE INDEX stock_summaries_embedding_idx
   ON stock_summaries
   USING hnsw (embedding vector_cosine_ops)
   WITH (m = 16, ef_construction = 64);

   -- This may take 10-30 minutes for large tables
   ```

4. **Verify Index Rebuild**
   ```sql
   -- Re-run EXPLAIN ANALYZE
   EXPLAIN ANALYZE
   SELECT
       ticker,
       summary_text,
       embedding <-> '[0.1, 0.2, ...]'::vector(1536) AS distance
   FROM stock_summaries
   ORDER BY embedding <-> '[0.1, 0.2, ...]'::vector(1536)
   LIMIT 5;

   -- Execution time should be < 100 ms
   ```

5. **Run VACUUM ANALYZE**
   ```sql
   VACUUM ANALYZE stock_summaries;
   ```

---

## Database Operations

### Backup & Restore

**Daily Automated Backups** (if using RDS):
- Retention: 7 days
- Window: 2:00 AM - 3:00 AM ET (during low usage)
- Location: AWS RDS automated backups

**Manual Backup**:
```bash
# Full database dump
pg_dump -h <db-host> -U <db-user> -d fa_ai_db -F c -f backup_$(date +%Y%m%d).dump

# Specific table
pg_dump -h <db-host> -U <db-user> -d fa_ai_db -t stock_summaries -F c -f stock_summaries_$(date +%Y%m%d).dump
```

**Restore from Backup**:
```bash
# Restore full database
pg_restore -h <db-host> -U <db-user> -d fa_ai_db -c backup_20251107.dump

# Restore specific table
pg_restore -h <db-host> -U <db-user> -d fa_ai_db -t stock_summaries stock_summaries_20251107.dump
```

### Data Retention & Archival

**Retention Policies**:
- Stock summaries: Keep all (never delete)
- Batch audit logs: 90 days
- Query logs: 30 days
- LangSmith traces: 90 days (configurable in LangSmith)

**Monthly Archival Script**:
```sql
-- Archive old batch audit logs
INSERT INTO batch_audit_archive
SELECT * FROM batch_audit
WHERE started_at < NOW() - INTERVAL '90 days';

DELETE FROM batch_audit
WHERE started_at < NOW() - INTERVAL '90 days';

-- Archive old query logs
INSERT INTO query_logs_archive
SELECT * FROM query_logs
WHERE created_at < NOW() - INTERVAL '30 days';

DELETE FROM query_logs
WHERE created_at < NOW() - INTERVAL '30 days';

-- Run VACUUM to reclaim space
VACUUM FULL batch_audit;
VACUUM FULL query_logs;
```

### Database Monitoring Queries

**Table Sizes**:
```sql
SELECT
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS total_size,
    pg_size_pretty(pg_relation_size(schemaname||'.'||tablename)) AS table_size,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename) - pg_relation_size(schemaname||'.'||tablename)) AS indexes_size
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;
```

**Index Usage**:
```sql
SELECT
    schemaname,
    tablename,
    indexname,
    idx_scan as index_scans,
    idx_tup_read as tuples_read,
    idx_tup_fetch as tuples_fetched
FROM pg_stat_user_indexes
ORDER BY idx_scan DESC;
```

**Cache Hit Ratio**:
```sql
SELECT
    'cache hit rate' AS metric,
    ROUND(100.0 * sum(heap_blks_hit) / (sum(heap_blks_hit) + sum(heap_blks_read)), 2) AS percentage
FROM pg_statio_user_tables;

-- Target: > 95%
```

---

## LangSmith Debugging

### Viewing Traces

**For Batch Processing**:
1. Go to https://smith.langchain.com/
2. Select project: `fa-ai-system-batch`
3. Filter by:
   - Date range: Last 24 hours
   - Tag: `ticker:AAPL` (for specific stock)
   - Tag: `batch:abc12345` (for specific batch run)
4. Click on trace to see:
   - Full LLM inputs/outputs
   - Token usage and cost
   - Latency breakdown
   - Errors and warnings

**For Interactive Queries**:
1. Select project: `fa-ai-system`
2. Filter by:
   - Tag: `session:user123` (for specific user session)
   - Status: "error" (to see failed queries)
3. Inspect:
   - User question
   - Retrieved context
   - Generated answer
   - Citations used

### Common Trace Patterns

**Successful Hook Summary Generation**:
```
├─ batch_AAPL_abc12345 (38s, $0.15)
   ├─ edgar_fetcher (2s, $0.02)
   ├─ bluematrix_fetcher (3s, $0.03)
   ├─ factset_fetcher (1s, $0.01)
   ├─ hook_writer (5s, $0.04)
   ├─ fact_checker (10s, $0.03)
   └─ citation_extractor (7s, $0.02)
```

**Failed Fact-Check**:
```
├─ batch_TSLA_def67890 (45s, $0.18) [ERROR]
   ├─ edgar_fetcher (2s, $0.02) [SUCCESS]
   ├─ bluematrix_fetcher (3s, $0.03) [SUCCESS]
   ├─ factset_fetcher (1s, $0.01) [SUCCESS]
   ├─ hook_writer (5s, $0.04) [SUCCESS]
   └─ fact_checker (15s, $0.03) [FAILED: Conflicting revenue numbers]
```

### Debugging Prompt Issues

**View Prompt Versions**:
1. Go to LangSmith → Prompts
2. Click on prompt name (e.g., "hook_summary_writer")
3. View version history
4. Compare input/output for different versions

**A/B Testing Prompts**:
```python
# In code, specify version
from src.shared.utils.prompt_manager import get_prompt

# Use specific version
prompt_v1 = get_prompt("hook_summary_writer", version="1")
prompt_v2 = get_prompt("hook_summary_writer", version="2")

# LangSmith will track which version was used in each trace
```

---

## Performance Troubleshooting

### Batch Processing Slow

**Diagnosis**:
```bash
# Check concurrency setting
echo $MAX_CONCURRENT

# Check database connection pool
psql -h <db-host> -U <db-user> -d fa_ai_db -c "SELECT COUNT(*) FROM pg_stat_activity WHERE datname='fa_ai_db';"

# Check LangSmith for bottlenecks
# Filter by slowest traces (sort by latency desc)
```

**Optimizations**:

1. **Increase Concurrency** (if resources allow):
   ```bash
   export MAX_CONCURRENT=150  # Up from 100
   ```

2. **Optimize Database Queries**:
   ```sql
   -- Add missing indexes
   CREATE INDEX IF NOT EXISTS idx_edgar_ticker ON edgar_filings(ticker);
   CREATE INDEX IF NOT EXISTS idx_bluematrix_ticker ON bluematrix_reports(ticker);
   ```

3. **Use Faster LLM Model**:
   ```python
   # Edit src/batch/agents/hook_writer.py
   # Change from Sonnet to Haiku for hook summaries
   model="claude-haiku-20250514"
   ```

### Interactive Queries Slow

**Common Bottlenecks**:

1. **Vector Search**:
   - Check HNSW index is being used (see Runbook 4)
   - Reduce number of results: `LIMIT 5` instead of `LIMIT 20`

2. **LLM Generation**:
   - Reduce `max_tokens` from 2000 to 1500
   - Use Haiku for simple queries

3. **Database Connection Wait**:
   - Increase connection pool size
   - Implement connection queuing

**Performance Targets**:
| Operation | Target | Action if Exceeded |
|-----------|--------|-------------------|
| Vector search | < 100ms | Rebuild index |
| LLM generation | < 30s | Reduce tokens or use Haiku |
| Fact-checking | < 15s | Cache recent checks |
| Total response | < 60s | Investigate all above |

---

## Escalation Procedures

### Level 1 Support (You)

**Responsibilities**:
- Monitor daily batch runs
- Respond to user-reported issues
- Perform basic troubleshooting
- Restart services as needed
- Follow runbooks

**Escalate to Level 2 if**:
- Issue not resolved within 2 hours
- Requires code changes
- Database corruption suspected
- Security incident

### Level 2 Support (Engineering Team)

**Contact**: engineering@fa-ai-system.com

**Escalation Template**:
```
Subject: [URGENT] FA-AI System Issue - [Brief Description]

Issue: [Detailed description]

Symptoms:
- [Symptom 1]
- [Symptom 2]

Steps Taken:
1. [Step 1]
2. [Step 2]

Logs:
[Attach relevant logs or LangSmith trace URLs]

Impact:
- Users affected: [Number]
- Services down: [Batch / Interactive / Both]
- Data loss risk: [Yes/No]

Requested Action:
[What do you need from engineering?]
```

### Level 3 Support (Vendor Support)

**When to Contact**:
- Anthropic (Claude API issues)
- OpenAI (Embedding API issues)
- LangChain (LangSmith platform issues)
- AWS (Infrastructure issues)

**Anthropic Support**:
- Email: support@anthropic.com
- Include: API key (first 8 chars), timestamp, error message
- SLA: 4 hours for critical issues

**LangChain Support**:
- Email: support@langchain.com
- Include: Project name, trace URL, screenshot
- SLA: 24 hours

---

## Emergency Procedures

### Emergency 1: Complete System Down

**Definition**: Both batch and interactive services unresponsive

**Immediate Actions** (within 5 minutes):

1. **Alert Stakeholders**:
   ```
   To: leadership@company.com, users@company.com
   Subject: FA-AI System Outage - Investigating

   We are aware of a system outage affecting the FA-AI Assistant.
   Our team is investigating and will provide updates every 30 minutes.

   Estimated resolution: TBD
   Workaround: Please use manual research methods temporarily.
   ```

2. **Check Infrastructure**:
   ```bash
   # Check ECS tasks
   aws ecs list-tasks --cluster fa-ai-cluster --desired-status RUNNING

   # Check RDS database
   aws rds describe-db-instances --db-instance-identifier fa-ai-db

   # Check load balancer
   aws elbv2 describe-target-health --target-group-arn <tg-arn>
   ```

3. **Attempt Service Restart**:
   ```bash
   # Restart ECS services
   aws ecs update-service --cluster fa-ai-cluster --service fa-ai-batch --force-new-deployment
   aws ecs update-service --cluster fa-ai-cluster --service fa-ai-interactive --force-new-deployment
   ```

4. **Escalate Immediately** if not resolved in 15 minutes

### Emergency 2: Data Loss Detected

**Definition**: Missing or corrupted data in database

**Immediate Actions**:

1. **Stop All Writes**:
   ```bash
   # Stop batch processing
   pkill -f run_batch_phase2

   # Stop interactive API (read-only mode)
   # Set READ_ONLY=true in environment
   ```

2. **Assess Damage**:
   ```sql
   -- Count records by day
   SELECT
       DATE(created_at) as date,
       COUNT(*) as records
   FROM stock_summaries
   GROUP BY DATE(created_at)
   ORDER BY date DESC;

   -- Look for sudden drops
   ```

3. **Restore from Backup** (if needed):
   ```bash
   # Use most recent backup
   pg_restore -h <db-host> -U <db-user> -d fa_ai_db -c backup_latest.dump
   ```

4. **Document Incident**:
   - What data was lost
   - Time range affected
   - Root cause (if known)
   - Recovery steps taken

### Emergency 3: Security Incident

**Definition**: Unauthorized access, data breach, or suspicious activity

**Immediate Actions**:

1. **Do NOT investigate further** (preserve evidence)

2. **Contact Security Team Immediately**:
   - Email: security@company.com
   - Phone: [Security Hotline]

3. **Isolate Affected Systems** (if instructed):
   ```bash
   # Disable public access to API
   aws elbv2 modify-rule --rule-arn <rule-arn> --actions Type=fixed-response,FixedResponseConfig={StatusCode=503}

   # Revoke suspicious API keys
   # (Anthropic, OpenAI, LangSmith)
   ```

4. **Preserve Logs**:
   ```bash
   # Copy all logs to secure location
   aws s3 cp /var/log/fa-ai-batch/ s3://security-incident-logs/fa-ai-$(date +%Y%m%d)/ --recursive
   ```

---

## Maintenance Windows

### Scheduled Maintenance

**Frequency**: Monthly (First Sunday of each month)
**Time**: 2:00 AM - 6:00 AM ET (low usage period)

**Pre-Maintenance Checklist** (1 week before):
- [ ] Notify users via email
- [ ] Update status page
- [ ] Test changes in staging environment
- [ ] Prepare rollback plan
- [ ] Schedule team availability

**Maintenance Tasks**:
1. Database maintenance (VACUUM, REINDEX)
2. OS security patches
3. Dependency updates
4. Log archival
5. Performance optimizations

**Post-Maintenance Checklist**:
- [ ] Verify batch processing runs successfully
- [ ] Test interactive queries
- [ ] Check all monitoring dashboards
- [ ] Send completion notification to users
- [ ] Update maintenance log

### Emergency Maintenance

**Criteria**:
- Critical security vulnerability
- Data corruption risk
- System stability issue

**Approval Required From**:
- Engineering Lead
- Product Owner
- (If during business hours: also notify users 30 min in advance)

---

## Support Contacts

### Internal Team

| Role | Contact | Escalation Hours |
|------|---------|-----------------|
| Engineering Lead | engineering-lead@company.com | 24/7 for critical |
| Product Owner | product@company.com | Business hours |
| Database Admin | dba@company.com | 24/7 for critical |
| Security Team | security@company.com | 24/7 |

### External Vendors

| Vendor | Support Email | Support Phone | SLA |
|--------|--------------|---------------|-----|
| Anthropic | support@anthropic.com | - | 4 hours |
| OpenAI | support@openai.com | - | 24 hours |
| LangChain | support@langchain.com | - | 24 hours |
| AWS | AWS Support Console | Premium Support | 1 hour (critical) |

### On-Call Rotation

- **Week 1-2**: Support Engineer A
- **Week 3-4**: Support Engineer B
- **Backup**: Engineering Lead

**On-Call Responsibilities**:
- Monitor alerts 24/7
- Respond to critical issues within 15 minutes
- Follow runbooks and escalation procedures
- Document all incidents

---

## Appendix: Quick Reference

### Useful Commands

```bash
# Check batch status
tail -f /var/log/fa-ai-batch/latest.log | grep "Batch completed"

# Restart interactive API
pkill -f uvicorn && ./scripts/start_interactive_server.sh

# Check database connections
psql -h <db-host> -U <db-user> -d fa_ai_db -c "SELECT COUNT(*) FROM pg_stat_activity;"

# View LangSmith traces
open "https://smith.langchain.com/projects/fa-ai-system-batch"

# Check disk space
df -h

# Check memory usage
free -h

# Check CPU usage
top -n 1
```

### Useful SQL Queries

```sql
-- Latest batch run status
SELECT * FROM batch_audit ORDER BY started_at DESC LIMIT 1;

-- Stocks processed today
SELECT COUNT(*) FROM stock_summaries WHERE created_at > CURRENT_DATE;

-- Failed stocks in last batch
SELECT ticker, error_message
FROM batch_audit_details
WHERE batch_run_id = (SELECT batch_run_id FROM batch_audit ORDER BY started_at DESC LIMIT 1)
AND status = 'failed';

-- Slow queries
SELECT query, mean_exec_time, calls
FROM pg_stat_statements
ORDER BY mean_exec_time DESC
LIMIT 10;
```

### LangSmith Filters

- **Show only errors**: `status:error`
- **Show specific ticker**: `tags:ticker:AAPL`
- **Show batch runs**: `tags:batch-processing`
- **Show today's runs**: `start_time:[now-24h TO now]`
- **Show expensive runs**: `total_cost:[0.50 TO *]`

---

## Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2025-11-07 | AI Assistant | Initial version |

---

**Last Updated**: November 7, 2025
**Next Review**: December 7, 2025
**Document Owner**: Support Team Lead
