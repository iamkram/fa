# Batch Scheduler - 2 AM Nightly Processing

The batch scheduler automatically triggers the FA AI System batch processing at 2:00 AM local time daily.

## Overview

This scheduler uses APScheduler to run the batch assistant graph on a cron schedule. It processes all stocks in the database through the Phase 2 pipeline with validation, generating 3-tier summaries with multi-source data integration.

## Architecture

- **Scheduler**: `batch_scheduler.py` - Main scheduler using APScheduler
- **Graph**: `batch_assistant_graph.py` - LangGraph assistant orchestrating the batch job
- **Orchestrator**: `ConcurrentBatchOrchestrator` - Concurrent processing (5 stocks at a time)
- **Audit**: `BatchRunAudit` - Database tracking of batch runs

## Schedule

- **Trigger Time**: 2:00 AM local time
- **Frequency**: Daily
- **Cron Expression**: `0 2 * * *` (minute=0, hour=2)

## Usage

### Start the Scheduler

```bash
# Start the scheduler (runs continuously)
./scripts/start_batch_scheduler.sh

# Or run directly with Python
python3 src/batch/scheduler/batch_scheduler.py
```

### Run as Background Service

```bash
# Start in background with nohup
nohup ./scripts/start_batch_scheduler.sh > logs/scheduler.log 2>&1 &

# Check if running
ps aux | grep batch_scheduler

# View logs
tail -f logs/scheduler.log

# Stop the scheduler
pkill -f batch_scheduler.py
```

### Run with System Cron (Alternative)

If you prefer to use system cron instead of the continuous Python scheduler:

```bash
# Edit crontab
crontab -e

# Add this line to run at 2 AM daily
0 2 * * * cd /Users/markkenyon/fa-ai-system && python3 -c "import asyncio; from src.batch.scheduler.batch_scheduler import BatchScheduler; scheduler = BatchScheduler(); asyncio.run(scheduler.run_batch_job())" >> logs/cron_batch.log 2>&1
```

## How It Works

### 1. Scheduler Initialization
The scheduler starts and registers the cron job:
```python
scheduler.add_job(
    run_batch_job,
    trigger=CronTrigger(hour=2, minute=0),  # 2:00 AM daily
    id='nightly_batch_job'
)
```

### 2. Batch Job Execution (at 2 AM)
When triggered, the scheduler:
1. Initializes the batch run with a new `batch_run_id`
2. Fetches all stocks from the database
3. Creates a `BatchRunAudit` record with status "RUNNING"
4. Processes stocks through `ConcurrentBatchOrchestrator` (5 at a time)
5. Each stock goes through the Phase 2 pipeline with validation
6. Updates `BatchRunAudit` with final results

### 3. LangGraph Flow
```
START → initialize → process_stocks → finalize → END
```

- **initialize**: Create batch run, fetch stocks, create audit record
- **process_stocks**: Run concurrent processing through Phase 2 pipeline
- **finalize**: Update audit record with results, log completion

## Monitoring

### Check Next Run Time
The scheduler logs the next scheduled run time on startup:
```
⏭️  Next scheduled run: 2025-11-10 02:00:00
```

### View Logs
```bash
# Scheduler logs
tail -f logs/batch_scheduler.log

# Batch processing logs
tail -f logs/batch_processing.log
```

### Database Audit
Query the `batch_run_audit` table to see historical batch runs:
```sql
SELECT
    batch_run_id,
    run_date,
    status,
    total_stocks,
    stocks_processed,
    stocks_failed,
    end_time
FROM batch_run_audit
ORDER BY run_date DESC
LIMIT 10;
```

## Configuration

The scheduler respects all environment variables from `.env`:
- `DATABASE_URL` - PostgreSQL connection
- `OPENAI_API_KEY` - OpenAI API key
- `LANGSMITH_API_KEY` - LangSmith tracing
- `LANGSMITH_PROJECT` - LangSmith project name

## Graceful Shutdown

The scheduler handles SIGINT (Ctrl+C) and SIGTERM signals gracefully:
```bash
# Send termination signal
pkill -SIGTERM -f batch_scheduler.py
```

## Testing

### Test Scheduler Startup
```bash
# Test that the scheduler module loads correctly
python3 -c "from src.batch.scheduler.batch_scheduler import BatchScheduler; print('✅ OK')"
```

### Test Batch Job Manually
```bash
# Run a batch job immediately (without waiting for 2 AM)
python3 -c "
import asyncio
from src.batch.graphs.batch_assistant_graph import batch_assistant_graph
from datetime import datetime

async def test():
    state = {
        'trigger_time': datetime.now().isoformat(),
        'stocks_to_process': [],
        'processed_count': 0,
        'failed_count': 0,
        'batch_run_id': '',
        'status': 'INITIALIZING',
        'error_message': None
    }
    result = await batch_assistant_graph.ainvoke(state)
    print(f'Status: {result[\"status\"]}')
    print(f'Processed: {result[\"processed_count\"]}')
    print(f'Failed: {result[\"failed_count\"]}')

asyncio.run(test())
"
```

## Troubleshooting

### Scheduler Not Starting
- Check that APScheduler is installed: `pip show apscheduler`
- Verify database connection in `.env`
- Check logs directory exists: `mkdir -p logs`

### Batch Job Failing
- Check `BatchRunAudit` table for error messages
- Review `logs/batch_scheduler.log` for stack traces
- Verify all stocks are properly seeded in database
- Check OpenAI API key is valid

### Time Zone Issues
The scheduler uses local system time. To change:
```python
# In batch_scheduler.py, add timezone parameter
from pytz import timezone
CronTrigger(hour=2, minute=0, timezone=timezone('America/New_York'))
```

## LangGraph Platform (Cloud Alternative)

If you're using LangGraph Platform (hosted service), you can configure cron jobs through the platform instead:

```bash
# Using LangGraph Cloud API
langgraph cron create \
  --graph batch_assistant_graph \
  --schedule "0 2 * * *" \
  --name "nightly_batch_processing"
```

This local scheduler is designed for self-hosted deployments where you want full control over execution.
