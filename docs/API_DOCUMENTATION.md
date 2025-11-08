# FA AI System - API Documentation

## Overview

The FA AI System provides two primary interfaces:
1. **Interactive Query API** - Real-time question answering (FastAPI)
2. **Batch Processing API** - Bulk summary generation (CLI)

---

## Interactive Query API

### Base URL

```
Production: https://fa-ai-system.example.com
Development: http://localhost:8000
```

### Authentication

```bash
# API Key in header
curl -H "X-API-Key: your-api-key" https://fa-ai-system.example.com/query
```

---

## Endpoints

### 1. Health Check

```http
GET /health
```

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2024-11-07T12:00:00Z",
  "version": "1.0.0",
  "dependencies": {
    "database": "connected",
    "redis": "connected",
    "anthropic_api": "available",
    "openai_api": "available"
  }
}
```

---

### 2. Stock Query

```http
POST /query
```

**Request Body:**
```json
{
  "ticker": "AAPL",
  "question": "What were the Q4 2024 earnings?",
  "tier": "medium",
  "include_citations": true
}
```

**Parameters:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `ticker` | string | Yes | Stock ticker symbol (e.g., "AAPL") |
| `question` | string | Yes | Natural language question |
| `tier` | string | No | Response detail level: "hook", "medium", "expanded" (default: "medium") |
| `include_citations` | boolean | No | Include source citations (default: true) |

**Response:**
```json
{
  "answer": "Apple Inc. reported Q4 2024 revenue of $94.9 billion, up 6% year-over-year. iPhone revenue reached $46.2B (+5% YoY), driven by strong demand for iPhone 15 Pro models. Services revenue grew 16% to $22.3B, setting a new record. The company announced a $90B share buyback program and raised its quarterly dividend by 4% to $0.25 per share.",
  "citations": [
    {
      "claim": "Q4 2024 revenue of $94.9 billion",
      "source_type": "EDGAR",
      "source_id": "0000320193-24-000123",
      "confidence": 0.98,
      "page_number": 3,
      "quote": "Total net sales increased 6 percent to $94.9 billion..."
    },
    {
      "claim": "iPhone revenue reached $46.2B",
      "source_type": "EDGAR",
      "source_id": "0000320193-24-000123",
      "confidence": 0.97,
      "page_number": 4
    },
    {
      "claim": "Services revenue grew 16% to $22.3B",
      "source_type": "BlueMatrix",
      "source_id": "BM-AAPL-2024-Q4",
      "confidence": 0.95
    }
  ],
  "tier": "medium",
  "processing_time_ms": 1247,
  "cost": 0.023,
  "model_used": "claude-3-5-sonnet-20241022",
  "token_usage": {
    "input_tokens": 1250,
    "output_tokens": 180
  },
  "metadata": {
    "sources_queried": ["EDGAR", "BlueMatrix", "FactSet"],
    "vectors_retrieved": 15,
    "guardrails_passed": true,
    "hallucination_risk": "low"
  }
}
```

**Status Codes:**

| Code | Description |
|------|-------------|
| 200 | Success |
| 400 | Invalid request (missing ticker or question) |
| 404 | Stock ticker not found |
| 429 | Rate limit exceeded |
| 500 | Internal server error |
| 503 | Service temporarily unavailable |

---

### 3. Get Stock Summary

```http
GET /summary/{ticker}
```

**Path Parameters:**
- `ticker` (string): Stock ticker symbol

**Query Parameters:**
- `tier` (string): "hook", "medium", or "expanded" (default: "medium")
- `fresh` (boolean): Force regenerate summary (default: false)

**Request:**
```bash
GET /summary/AAPL?tier=hook
```

**Response:**
```json
{
  "ticker": "AAPL",
  "company_name": "Apple Inc.",
  "summary": "Apple reported strong Q4 2024 earnings with revenue up 6% YoY.",
  "tier": "hook",
  "word_count": 12,
  "last_updated": "2024-11-07T02:30:00Z",
  "batch_run_id": "batch-20241107-023000",
  "citations_count": 3
}
```

---

### 4. Bulk Query

```http
POST /query/bulk
```

**Request Body:**
```json
{
  "queries": [
    {"ticker": "AAPL", "question": "What are the latest earnings?"},
    {"ticker": "MSFT", "question": "What is the cloud revenue?"},
    {"ticker": "GOOGL", "question": "What is the AI strategy?"}
  ],
  "tier": "medium",
  "include_citations": false
}
```

**Response:**
```json
{
  "results": [
    {
      "ticker": "AAPL",
      "answer": "...",
      "processing_time_ms": 1200,
      "cost": 0.022
    },
    {
      "ticker": "MSFT",
      "answer": "...",
      "processing_time_ms": 1350,
      "cost": 0.025
    },
    {
      "ticker": "GOOGL",
      "answer": "...",
      "processing_time_ms": 1180,
      "cost": 0.021
    }
  ],
  "total_processing_time_ms": 3730,
  "total_cost": 0.068,
  "successful": 3,
  "failed": 0
}
```

**Limits:**
- Maximum 10 queries per bulk request
- Rate limit: 100 requests per minute

---

### 5. List Available Stocks

```http
GET /stocks
```

**Query Parameters:**
- `limit` (int): Number of results (default: 100, max: 1000)
- `offset` (int): Pagination offset (default: 0)
- `has_summary` (boolean): Filter to stocks with summaries (default: false)

**Response:**
```json
{
  "stocks": [
    {
      "ticker": "AAPL",
      "company_name": "Apple Inc.",
      "last_summary_update": "2024-11-07T02:30:00Z",
      "has_hook": true,
      "has_medium": true,
      "has_expanded": true
    },
    {
      "ticker": "MSFT",
      "company_name": "Microsoft Corporation",
      "last_summary_update": "2024-11-07T02:45:00Z",
      "has_hook": true,
      "has_medium": true,
      "has_expanded": true
    }
  ],
  "total": 1000,
  "limit": 100,
  "offset": 0
}
```

---

### 6. Get Citations

```http
GET /citations/{ticker}
```

**Path Parameters:**
- `ticker` (string): Stock ticker symbol

**Response:**
```json
{
  "ticker": "AAPL",
  "citations": [
    {
      "id": 12345,
      "claim_text": "Revenue of $94.9 billion in Q4 2024",
      "source_type": "EDGAR",
      "source_id": "0000320193-24-000123",
      "confidence": 0.98,
      "page_number": 3,
      "exact_quote": "Total net sales increased 6 percent to $94.9 billion...",
      "created_at": "2024-11-07T02:30:15Z"
    }
  ],
  "total_citations": 15
}
```

---

## Error Responses

### Standard Error Format

```json
{
  "error": {
    "code": "INVALID_TICKER",
    "message": "Ticker 'XYZ' not found in database",
    "details": {
      "ticker": "XYZ",
      "suggestions": ["XYZE", "XYZW"]
    },
    "timestamp": "2024-11-07T12:00:00Z",
    "request_id": "req-abc123"
  }
}
```

### Error Codes

| Code | HTTP Status | Description |
|------|-------------|-------------|
| `INVALID_TICKER` | 404 | Ticker symbol not found |
| `INVALID_REQUEST` | 400 | Malformed request body |
| `MISSING_FIELD` | 400 | Required field missing |
| `RATE_LIMIT_EXCEEDED` | 429 | Too many requests |
| `API_KEY_INVALID` | 401 | Invalid or missing API key |
| `INSUFFICIENT_PERMISSIONS` | 403 | API key lacks permissions |
| `GUARDRAIL_FAILURE` | 422 | Content failed safety checks |
| `UPSTREAM_ERROR` | 502 | External API failure (Anthropic, OpenAI) |
| `DATABASE_ERROR` | 503 | Database temporarily unavailable |
| `INTERNAL_ERROR` | 500 | Unexpected server error |

---

## Rate Limits

### Standard Tier

| Endpoint | Limit | Window |
|----------|-------|--------|
| `/query` | 60 requests | per minute |
| `/query/bulk` | 10 requests | per minute |
| `/summary/*` | 100 requests | per minute |
| All endpoints | 1000 requests | per hour |

**Rate Limit Headers:**
```http
X-RateLimit-Limit: 60
X-RateLimit-Remaining: 45
X-RateLimit-Reset: 1699372800
```

### Enterprise Tier

Contact sales for higher limits.

---

## Batch Processing CLI

### Run Batch Job

```bash
python src/batch/run_batch_phase2.py [OPTIONS]
```

**Options:**

| Flag | Description | Default |
|------|-------------|---------|
| `--limit N` | Process N stocks | 1000 |
| `--concurrent` | Enable concurrent processing | False |
| `--max-concurrent N` | Max concurrent stocks | 100 |
| `--tickers AAPL,MSFT` | Process specific tickers | All |
| `--force` | Force regenerate all summaries | False |
| `--dry-run` | Simulate without writing | False |

**Examples:**

```bash
# Process all 1,000 stocks with concurrency
python src/batch/run_batch_phase2.py --limit 1000 --concurrent --max-concurrent 100

# Process specific tickers
python src/batch/run_batch_phase2.py --tickers AAPL,MSFT,GOOGL --concurrent

# Dry run to estimate cost
python src/batch/run_batch_phase2.py --limit 1000 --dry-run
```

**Output:**

```
############################################################
PHASE 2 BATCH RUN: batch-20241107-023000
Time: 2024-11-07 02:30:00
Features: Multi-source ingestion, 3-tier summaries, Concurrent (100 max)
############################################################

Processing 1000 stocks

================================================================================
CONCURRENT BATCH PROCESSING
Total stocks: 1000
Batch size: 100
Max concurrent: 100
Total batches: 10
================================================================================

[Batch 1/10] Processing 100 stocks (max 100 concurrent)
[Progress] 100/1000 (10%) | 50 stocks/min | ETA: 18 min

...

================================================================================
PHASE 2 BATCH RUN COMPLETE
================================================================================
Run ID: batch-20241107-023000
Duration: 3h 27m 15s
Processed: 1000 stocks
Successful: 990 (99.0%)
Failed: 10 (1.0%)
Retries: 25

Summary Tier Results:
  Hook (25-50 words): 990 generated
  Medium (100-150 words): 990 generated
  Expanded (200-250 words): 990 generated

Validation:
  Fact checks passed: 985 (99.5%)
  Fact checks failed: 5 (0.5%)
  Average citations per summary: 4.2

Cost Summary:
  Total cost: $382.50
  Cost per stock: $0.3825
  Average tokens per stock: 2,847 input, 523 output

Model Usage:
  Claude Sonnet: 2,970 calls ($340.20)
  Claude Haiku: 990 calls ($42.30)

Next Steps:
  - Review failed stocks in logs
  - Check CloudWatch dashboard for metrics
  - View results: python scripts/view_summaries.py --batch-id batch-20241107-023000
================================================================================
```

---

## WebSocket API (Future)

### Connect to Real-Time Updates

```javascript
const ws = new WebSocket('wss://fa-ai-system.example.com/ws');

ws.on('open', () => {
  ws.send(JSON.stringify({
    action: 'subscribe',
    ticker: 'AAPL'
  }));
});

ws.on('message', (data) => {
  const update = JSON.parse(data);
  console.log('Summary updated:', update);
});
```

**Message Format:**
```json
{
  "type": "summary_update",
  "ticker": "AAPL",
  "summary": "...",
  "tier": "medium",
  "timestamp": "2024-11-07T12:00:00Z"
}
```

---

## SDK Examples

### Python SDK

```python
from fa_ai_client import FAIClient

client = FAIClient(api_key="your-api-key")

# Simple query
response = client.query(
    ticker="AAPL",
    question="What were the latest earnings?",
    tier="medium"
)

print(response.answer)
print(f"Cost: ${response.cost}")

# Get summary
summary = client.get_summary("AAPL", tier="hook")
print(summary.text)

# Bulk query
results = client.bulk_query([
    {"ticker": "AAPL", "question": "Latest earnings?"},
    {"ticker": "MSFT", "question": "Cloud revenue?"}
])

for result in results:
    print(f"{result.ticker}: {result.answer}")
```

### JavaScript SDK

```javascript
import { FAIClient } from '@fa-ai/client';

const client = new FAIClient({ apiKey: 'your-api-key' });

// Query
const response = await client.query({
  ticker: 'AAPL',
  question: 'What were the latest earnings?',
  tier: 'medium'
});

console.log(response.answer);
console.log(`Cost: $${response.cost}`);

// Get summary
const summary = await client.getSummary('AAPL', { tier: 'hook' });
console.log(summary.text);
```

---

## Best Practices

### 1. Caching

```python
# Cache responses for identical queries
import hashlib

def cache_key(ticker: str, question: str, tier: str) -> str:
    return hashlib.md5(f"{ticker}:{question}:{tier}".encode()).hexdigest()

# Check cache before querying
cached = redis.get(cache_key(ticker, question, tier))
if cached:
    return json.loads(cached)

# Query API
response = client.query(ticker, question, tier)

# Cache for 5 minutes
redis.setex(cache_key(ticker, question, tier), 300, json.dumps(response))
```

### 2. Error Handling

```python
from fa_ai_client import FAIClient, FAIError, RateLimitError

client = FAIClient(api_key="your-api-key")

try:
    response = client.query("AAPL", "Latest earnings?")
except RateLimitError as e:
    # Wait and retry
    time.sleep(e.retry_after)
    response = client.query("AAPL", "Latest earnings?")
except FAIError as e:
    # Handle other errors
    logger.error(f"Query failed: {e.message}")
    return None
```

### 3. Batch Processing

```python
# Process in batches of 10
tickers = ["AAPL", "MSFT", "GOOGL", ..., "JPM"]  # 100 tickers

for i in range(0, len(tickers), 10):
    batch = tickers[i:i+10]
    queries = [{"ticker": t, "question": "Latest earnings?"} for t in batch]

    results = client.bulk_query(queries)

    for result in results:
        save_to_db(result)

    # Rate limiting: wait 6 seconds between batches (10 req/min)
    time.sleep(6)
```

---

## Monitoring API Usage

### Get Usage Stats

```http
GET /usage/stats
```

**Query Parameters:**
- `start_date` (ISO 8601): Start of period
- `end_date` (ISO 8601): End of period

**Response:**
```json
{
  "period": {
    "start": "2024-11-01T00:00:00Z",
    "end": "2024-11-07T23:59:59Z"
  },
  "total_requests": 45230,
  "successful_requests": 44890,
  "failed_requests": 340,
  "total_cost": 1247.82,
  "average_cost_per_request": 0.0276,
  "requests_by_tier": {
    "hook": 15000,
    "medium": 25000,
    "expanded": 5230
  },
  "top_tickers": [
    {"ticker": "AAPL", "requests": 1250},
    {"ticker": "MSFT", "requests": 1100},
    {"ticker": "GOOGL", "requests": 980}
  ]
}
```

---

## Changelog

### v1.0.0 (2024-11-07)
- Initial release
- Support for hook, medium, and expanded summaries
- Multi-source ingestion (EDGAR, BlueMatrix, FactSet)
- 3-layer hallucination detection
- Citation system
- Cost tracking

### Upcoming Features

**v1.1.0 (Planned)**
- WebSocket support for real-time updates
- Streaming responses
- Custom summary templates
- Advanced filters (date range, source type)

**v1.2.0 (Planned)**
- GraphQL API
- Batch processing via API
- Webhook notifications
- Multi-language support
