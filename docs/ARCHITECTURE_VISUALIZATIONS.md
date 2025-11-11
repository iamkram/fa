# FA AI System - Agent Architecture Visualizations

Complete visual documentation of all LangGraph agent flows in the Financial Advisor AI System.

---

## 1. Interactive Query Flow (Real-Time Chat Assistant)

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         INTERACTIVE FLOW                             │
│                     Real-Time Query Processing                       │
└─────────────────────────────────────────────────────────────────────┘

Financial Advisor Query → FastAPI → Interactive Graph → Response

Trigger: HTTP POST /query
Latency: <3 seconds
Use Case: FA asking questions about stocks, clients, portfolios
```

### Detailed Flow Diagram

```
┌──────────┐
│  START   │
└────┬─────┘
     │
     ▼
┌─────────────────────┐
│ Input Guardrails    │──────► Blocked? ──► END
│ - Prompt injection  │         (unsafe)
│ - Jailbreak detect  │
│ - PII/PHI check     │
└────┬────────────────┘
     │ Safe ✓
     ▼
┌─────────────────────┐
│ Query Classifier    │
│ (GPT-4o-mini)       │
│ ┌─────────────────┐ │
│ │ Intent:         │ │
│ │ • Simple        │ │
│ │ • Deep Research │ │
│ └─────────────────┘ │
└──────┬──────────────┘
       │
       ├──────────────┬─────────────────┐
       │              │                 │
   Simple ✓       Deep ✓
       │              │
       ▼              ▼
┌─────────────┐  ┌──────────────────────────────────────┐
│ Batch Data  │  │    DEEP RESEARCH PATH                │
│ Retrieval   │  │                                      │
│             │  │  ┌────────────────┐                  │
│ • PostgreSQL│  │  │  EDO Context   │                  │
│ • Recent    │  │  │  - Vector DB   │                  │
│   summaries │  │  │  - EDGAR docs  │                  │
│ • Cached    │  │  │  - BlueMatrix  │                  │
│   data      │  │  │  - FactSet     │                  │
└──────┬──────┘  │  └───────┬────────┘                  │
       │         │          │                           │
       │         │          ▼                           │
       │         │  ┌────────────────┐                  │
       │         │  │ News Research  │                  │
       │         │  │ (Tool: Search) │                  │
       │         │  │ - Real-time    │                  │
       │         │  │ - News APIs    │                  │
       │         │  └───────┬────────┘                  │
       │         │          │                           │
       │         │          ▼                           │
       │         │  ┌────────────────┐                  │
       │         │  │ Memory Node    │                  │
       │         │  │ - Conv history │                  │
       │         │  │ - User context │                  │
       │         │  └───────┬────────┘                  │
       │         │          │                           │
       │         │          ▼                           │
       │         │  ┌────────────────┐                  │
       │         │  │ Assemble       │                  │
       │         │  │ Context        │                  │
       │         │  │ - Merge all    │                  │
       │         │  │ - Rank sources │                  │
       │         │  └───────┬────────┘                  │
       │         │          │                           │
       │         │          ▼                           │
       │         │  ┌────────────────┐                  │
       │         │  │ Response       │                  │
       │         │  │ Writer Agent   │                  │
       │         │  │ (Claude Sonnet)│                  │
       │         │  │ - Generate     │                  │
       │         │  │ - Citations    │                  │
       │         │  └───────┬────────┘                  │
       │         │          │                           │
       │         │          ▼                           │
       │         │  ┌────────────────┐                  │
       │         │  │ Fact Verify    │                  │
       │         │  │ - Check claims │                  │
       │         │  │ - Validate     │                  │
       │         │  └───────┬────────┘                  │
       │         └──────────┴──────────────────────────┘
       │                    │
       └────────────────────┘
                │
                ▼
       ┌────────────────┐
       │ Output         │
       │ Guardrails     │
       │ - Hallucination│
       │ - Compliance   │
       │ - PII redact   │
       └───────┬────────┘
               │
               ▼
          ┌────────┐
          │  END   │
          └────────┘
```

### Integration Points

```
┌─────────────────────────────────────────────────────────────┐
│                    DATA SOURCES                              │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────────┐   ┌──────────────┐   ┌──────────────┐   │
│  │ PostgreSQL   │   │ pgvector     │   │ Redis Cache  │   │
│  ├──────────────┤   ├──────────────┤   ├──────────────┤   │
│  │ • Stocks     │   │ • EDGAR docs │   │ • Sessions   │   │
│  │ • Clients    │   │ • BlueMatrix │   │ • Queries    │   │
│  │ • Holdings   │   │ • FactSet    │   │ • Results    │   │
│  │ • Summaries  │   │ • Embeddings │   │              │   │
│  └──────────────┘   └──────────────┘   └──────────────┘   │
│                                                              │
└─────────────────────────────────────────────────────────────┘
           │                   │                   │
           └───────────────────┴───────────────────┘
                               │
                               ▼
                     ┌───────────────────┐
                     │ Interactive Graph │
                     └───────────────────┘
```

### State Management

```
InteractiveGraphState:
├── query_text: str              # Original FA question
├── fa_id: str                   # Financial advisor ID
├── session_id: str              # Conversation session
│
├── input_safe: bool             # Passed guardrails?
├── query_intent: str            # "simple" | "deep"
│
├── batch_data: dict             # PostgreSQL results
├── edo_context: str             # Vector search results
├── news_results: list           # Real-time news
├── memory_context: str          # Conversation history
├── assembled_context: str       # Merged data
│
├── response_text: str           # Final answer
├── citations: list              # Source references
├── fact_check_passed: bool      # Verification result
│
└── output_safe: bool            # Passed final guardrails
```

---

## 2. Batch Processing Flow (Nightly Stock Summary Generation)

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                     BATCH PROCESSING FLOW                            │
│                Phase 2: 3-Tier Summary Generation                    │
└─────────────────────────────────────────────────────────────────────┘

Trigger: 2 AM daily (APScheduler)
Duration: ~30 minutes (for 50 stocks @ 5 concurrent)
Use Case: Generate fresh summaries for all stocks nightly
```

### Detailed Flow Diagram

```
┌──────────┐
│  START   │
└────┬─────┘
     │
     ▼
┌────────────────────────────────────────────────────────────────┐
│              PARALLEL INGESTION (3 sources)                    │
│                                                                 │
│  ┌────────────────┐  ┌────────────────┐  ┌────────────────┐  │
│  │ EDGAR Fetcher  │  │ BlueMatrix     │  │ FactSet API    │  │
│  │                │  │ Fetcher        │  │                │  │
│  ├────────────────┤  ├────────────────┤  ├────────────────┤  │
│  │ • 10-K filings │  │ • Research     │  │ • Financials   │  │
│  │ • 10-Q reports │  │   reports      │  │ • Estimates    │  │
│  │ • 8-K events   │  │ • Analyst      │  │ • Consensus    │  │
│  │               │  │   notes        │  │ • Ownership    │  │
│  │ Vector embed  │  │ • Ratings      │  │                │  │
│  │ + store       │  │                │  │ Vector embed   │  │
│  └───────┬────────┘  └───────┬────────┘  └───────┬────────┘  │
│          │                   │                   │            │
│          └───────────────────┴───────────────────┘            │
│                              │                                │
└──────────────────────────────┼────────────────────────────────┘
                               │
                               ▼
                    ┌────────────────────┐
                    │  All sources ready │
                    └──────────┬─────────┘
                               │
        ┌──────────────────────┴──────────────────────┐
        │                                              │
        ▼                                              │
┌─────────────────────────────────────────────────────┤
│              TIER 1: HOOK (1 sentence)              │
├─────────────────────────────────────────────────────┤
│                                                      │
│  ┌─────────────────┐                                │
│  │ Hook Writer     │                                │
│  │ (Claude Sonnet) │                                │
│  │ • 1 sentence    │                                │
│  │ • Attention-    │                                │
│  │   grabbing      │                                │
│  └────────┬────────┘                                │
│           │                                          │
│           ▼                                          │
│  ┌─────────────────┐                                │
│  │ Fact Check Hook │                                │
│  │ (GPT-4o)        │                                │
│  │ • Verify claims │                                │
│  │ • Check sources │                                │
│  └────────┬────────┘                                │
│           │                                          │
│           ├───► Failed? ──┐                          │
│           │               │                          │
│           │ Passed ✓      │ Retry < 2?              │
│           │               │                          │
│           │               ▼                          │
│           │      ┌─────────────────┐                 │
│           │      │ Retry Hook      │                 │
│           │      │ (Negative       │                 │
│           │      │  prompting)     │                 │
│           │      └────────┬────────┘                 │
│           │               │                          │
│           │               └──► Loop back to          │
│           │                    Fact Check            │
│           │                                          │
└───────────┼──────────────────────────────────────────┘
            │
            ▼
┌─────────────────────────────────────────────────────┐
│         TIER 2: MEDIUM (2-3 paragraphs)             │
├─────────────────────────────────────────────────────┤
│                                                      │
│  ┌─────────────────┐                                │
│  │ Medium Writer   │                                │
│  │ (Claude Sonnet) │                                │
│  │ • 150-200 words │                                │
│  │ • Key insights  │                                │
│  │ • Balanced      │                                │
│  └────────┬────────┘                                │
│           │                                          │
│           ▼                                          │
│  ┌─────────────────┐                                │
│  │ Fact Check      │                                │
│  │ Medium          │                                │
│  └────────┬────────┘                                │
│           │                                          │
│           ├───► Failed? ──► Retry (max 2x)          │
│           │                                          │
│           │ Passed ✓                                 │
│           │                                          │
└───────────┼──────────────────────────────────────────┘
            │
            ▼
┌─────────────────────────────────────────────────────┐
│       TIER 3: EXPANDED (4-5 paragraphs)             │
├─────────────────────────────────────────────────────┤
│                                                      │
│  ┌─────────────────┐                                │
│  │ Expanded Writer │                                │
│  │ (Claude Sonnet) │                                │
│  │ • 300-400 words │                                │
│  │ • Comprehensive │                                │
│  │ • Citations     │                                │
│  └────────┬────────┘                                │
│           │                                          │
│           ▼                                          │
│  ┌─────────────────┐                                │
│  │ Fact Check      │                                │
│  │ Expanded        │                                │
│  └────────┬────────┘                                │
│           │                                          │
│           ├───► Failed? ──► Retry (max 2x)          │
│           │                                          │
│           │ Passed ✓                                 │
│           │                                          │
└───────────┼──────────────────────────────────────────┘
            │
            ▼
   ┌────────────────┐
   │    Storage     │
   │                │
   │ Save to DB:    │
   │ • hook_text    │
   │ • medium_text  │
   │ • expanded_text│
   │ • fact_checks  │
   │ • citations    │
   │ • word_counts  │
   └───────┬────────┘
           │
           ▼
      ┌────────┐
      │  END   │
      └────────┘
```

### Retry Logic with Negative Prompting

```
┌──────────────────────────────────────────────────────────┐
│              FACT-CHECK RETRY MECHANISM                  │
├──────────────────────────────────────────────────────────┤
│                                                           │
│  Attempt 1: Generate summary                             │
│             ↓                                             │
│          Fact Check ──► Failed? (errors detected)        │
│             ↓                                             │
│  Attempt 2: Regenerate with negative prompting           │
│             "Do NOT include: [specific errors]"          │
│             ↓                                             │
│          Fact Check ──► Failed? (still errors)           │
│             ↓                                             │
│  Attempt 3: Final regeneration with all errors listed    │
│             ↓                                             │
│          Fact Check ──► Accept result (pass or fail)     │
│             ↓                                             │
│          Proceed to next tier                            │
│                                                           │
│  Max retries: 2 per tier (3 total attempts)              │
│                                                           │
└──────────────────────────────────────────────────────────┘
```

### State Management

```
BatchGraphStatePhase2:
├── ticker: str                      # Stock ticker (e.g., "AAPL")
├── stock_id: UUID                   # Database ID
│
├── edgar_docs: list                 # 10-K, 10-Q, 8-K filings
├── bluematrix_reports: list         # Analyst research
├── factset_data: dict               # Financial data
│
├── hook_text: str                   # Tier 1 (1 sentence)
├── hook_fact_check: FactCheckResult # Verification
├── hook_retry_count: int            # Retry tracker
│
├── medium_text: str                 # Tier 2 (2-3 para)
├── medium_fact_check: FactCheckResult
├── medium_retry_count: int
│
├── expanded_text: str               # Tier 3 (4-5 para)
├── expanded_fact_check: FactCheckResult
├── expanded_retry_count: int
│
├── citations: list                  # Source references
└── summary_id: UUID                 # Final DB record
```

---

## 3. Batch Scheduler Flow (2 AM Orchestrator)

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                   BATCH SCHEDULER FLOW                               │
│                    Nightly Orchestrator                              │
└─────────────────────────────────────────────────────────────────────┘

Trigger: APScheduler Cron (2:00 AM daily)
Processes: All stocks (5 concurrent workers)
Duration: ~30 minutes for 50 stocks
```

### Detailed Flow Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                     APSCHEDULER                             │
│                                                              │
│  Cron Trigger: CronTrigger(hour=2, minute=0)                │
│  Schedule: "0 2 * * *" (Daily at 2:00 AM)                   │
└────────────────────┬────────────────────────────────────────┘
                     │
                     │ 2:00 AM ⏰
                     │
                     ▼
            ┌────────────────┐
            │     START      │
            │ Batch Run      │
            └───────┬────────┘
                    │
                    ▼
     ┌──────────────────────────────┐
     │    Initialize Batch Run      │
     │                               │
     │  1. Generate batch_run_id    │
     │     UUID: "abc-123-def..."   │
     │                               │
     │  2. Query all stocks         │
     │     SELECT * FROM stocks     │
     │                               │
     │  3. Create audit record      │
     │     INSERT INTO              │
     │     batch_run_audit (        │
     │       batch_run_id,          │
     │       run_date,              │
     │       status='RUNNING',      │
     │       total_stocks=50        │
     │     )                         │
     └───────────┬──────────────────┘
                 │
                 ▼
    ┌────────────────────────────────────────┐
    │   Process All Stocks (Concurrent)      │
    │                                         │
    │   Orchestrator: ConcurrentBatch        │
    │   Max Workers: 5                       │
    │                                         │
    │   ┌─────────────────────────────────┐  │
    │   │  Worker Pool (5 parallel)       │  │
    │   │                                  │  │
    │   │  ┌──────┐  ┌──────┐  ┌──────┐  │  │
    │   │  │ AAPL │  │ MSFT │  │ GOOGL│  │  │
    │   │  └──┬───┘  └──┬───┘  └──┬───┘  │  │
    │   │     │         │         │       │  │
    │   │     └─────────┴─────────┘       │  │
    │   │            │                    │  │
    │   │            ▼                    │  │
    │   │   ┌────────────────────┐       │  │
    │   │   │ Phase2 Validation  │       │  │
    │   │   │ Graph              │       │  │
    │   │   │ (see Flow #2)      │       │  │
    │   │   └────────┬───────────┘       │  │
    │   │            │                    │  │
    │   │            ▼                    │  │
    │   │   Result: {                    │  │
    │   │     status: "success",         │  │
    │   │     stock: "AAPL",             │  │
    │   │     summary_id: "xyz..."       │  │
    │   │   }                             │  │
    │   │                                  │  │
    │   │  Process next batch...          │  │
    │   │  ┌──────┐  ┌──────┐  ┌──────┐  │  │
    │   │  │ TSLA │  │ AMZN │  │ NVDA │  │  │
    │   │  └──────┘  └──────┘  └──────┘  │  │
    │   │                                  │  │
    │   │  ... continues for all 50 ...   │  │
    │   └─────────────────────────────────┘  │
    │                                         │
    │   Results Aggregation:                 │
    │   • Processed: 48/50 ✓                 │
    │   • Failed: 2/50 ✗                     │
    │                                         │
    └────────────┬────────────────────────────┘
                 │
                 ▼
      ┌──────────────────────┐
      │  Finalize Batch Run  │
      │                       │
      │  UPDATE               │
      │  batch_run_audit      │
      │  SET                  │
      │    status='COMPLETED',│
      │    stocks_processed=48│
      │    stocks_failed=2,   │
      │    end_time=NOW()     │
      │  WHERE                │
      │    batch_run_id='...' │
      └──────────┬────────────┘
                 │
                 ▼
            ┌────────┐
            │  END   │
            │        │
            │ Wait   │
            │ for    │
            │ next   │
            │ 2 AM   │
            └────────┘
```

### Concurrent Processing Detail

```
┌─────────────────────────────────────────────────────────────┐
│         CONCURRENT BATCH ORCHESTRATOR                       │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  Worker Pool: 5 concurrent workers                          │
│                                                              │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐             │
│  │ Worker 1 │    │ Worker 2 │    │ Worker 3 │             │
│  ├──────────┤    ├──────────┤    ├──────────┤             │
│  │ Stock 1  │    │ Stock 2  │    │ Stock 3  │             │
│  │ AAPL     │    │ MSFT     │    │ GOOGL    │             │
│  │          │    │          │    │          │             │
│  │ Phase2   │    │ Phase2   │    │ Phase2   │             │
│  │ Pipeline │    │ Pipeline │    │ Pipeline │             │
│  │ ↓        │    │ ↓        │    │ ↓        │             │
│  │ Ingest   │    │ Ingest   │    │ Ingest   │             │
│  │ Hook     │    │ Hook     │    │ Hook     │             │
│  │ Medium   │    │ Medium   │    │ Medium   │             │
│  │ Expanded │    │ Expanded │    │ Expanded │             │
│  │ Store    │    │ Store    │    │ Store    │             │
│  │          │    │          │    │          │             │
│  │ ✓ Done   │    │ ✓ Done   │    │ ✓ Done   │             │
│  └────┬─────┘    └────┬─────┘    └────┬─────┘             │
│       │               │               │                     │
│       └───────────────┴───────────────┘                     │
│                       │                                     │
│                       ▼                                     │
│              ┌─────────────────┐                            │
│              │ Worker 4        │    Worker 5               │
│              │ Stock 4 (TSLA)  │    Stock 5 (AMZN)        │
│              └─────────────────┘                            │
│                                                              │
│  Average time per stock: ~36 seconds                        │
│  Total time for 50 stocks: ~6 minutes (5 parallel)         │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### State Management

```
BatchAssistantState:
├── trigger_time: str            # "2025-11-10T02:00:00"
├── batch_run_id: str            # UUID for this run
│
├── stocks_to_process: list      # ["AAPL", "MSFT", ...]
├── processed_count: int         # 48
├── failed_count: int            # 2
│
├── status: str                  # "RUNNING" | "COMPLETED" | "FAILED"
└── error_message: str | None    # Error details if failed
```

### Monitoring & Audit Trail

```
┌─────────────────────────────────────────────────────────────┐
│                    BATCH RUN AUDIT                          │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  Database Table: batch_run_audit                            │
│                                                              │
│  ┌────────────────┬──────────────────────────────────────┐  │
│  │ batch_run_id   │ abc-123-def-456                      │  │
│  │ run_date       │ 2025-11-10 02:00:00                  │  │
│  │ status         │ COMPLETED                            │  │
│  │ total_stocks   │ 50                                   │  │
│  │ stocks_processed│ 48                                  │  │
│  │ stocks_failed  │ 2                                    │  │
│  │ start_time     │ 2025-11-10 02:00:05                  │  │
│  │ end_time       │ 2025-11-10 02:06:32                  │  │
│  │ error_message  │ NULL                                 │  │
│  └────────────────┴──────────────────────────────────────┘  │
│                                                              │
│  Query historical runs:                                      │
│  SELECT * FROM batch_run_audit                              │
│  ORDER BY run_date DESC LIMIT 30;                           │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## 4. System Integration Map

### Complete Data Flow

```
┌───────────────────────────────────────────────────────────────────┐
│                        FA AI SYSTEM                               │
│                    Complete Architecture                          │
└───────────────────────────────────────────────────────────────────┘

┌─────────────┐
│  External   │
│  Sources    │
├─────────────┤
│ • SEC EDGAR │──┐
│ • BlueMatrix│  │
│ • FactSet   │  │
│ • News APIs │  │
└─────────────┘  │
                 │
                 │  Batch Ingestion
                 │  (2 AM daily)
                 ▼
        ┌──────────────────┐
        │   PostgreSQL     │
        │   + pgvector     │
        ├──────────────────┤
        │ Tables:          │
        │ • stocks         │
        │ • stock_summaries│◄────┐
        │ • clients        │     │
        │ • holdings       │     │
        │ • citations      │     │
        │ • batch_audit    │     │
        │                  │     │
        │ Vector Store:    │     │
        │ • edgar_filings  │     │
        │ • bluematrix     │     │
        │ • factset_data   │     │
        └────────┬─────────┘     │
                 │                │
                 │                │ Store Results
                 │                │
    ┌────────────┼────────────────┘
    │            │
    │            │  Query Data
    │            │
    ▼            ▼
┌─────────┐  ┌──────────────┐
│ Batch   │  │ Interactive  │
│ Scheduler│  │ API          │
│         │  │              │
│ 2AM Cron│  │ FastAPI      │
└────┬────┘  └──────┬───────┘
     │              │
     │              │
     ▼              ▼
┌──────────┐   ┌───────────┐
│ Batch    │   │Interactive│
│ Assistant│   │ Graph     │
│ Graph    │   │           │
└────┬─────┘   └─────┬─────┘
     │               │
     │               │
     ▼               ▼
┌──────────┐   ┌───────────┐
│ Phase2   │   │ Financial │
│ Validation   │ Advisor   │
│ Graph    │   │ (Web UI)  │
└──────────┘   └───────────┘


KEY:
────►  Data flow
◄────  Write back
═══►  API calls
```

### LLM Model Usage

```
┌─────────────────────────────────────────────────────────────┐
│                    MODEL ASSIGNMENTS                         │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  Interactive Flow:                                           │
│  ├─ Query Classifier ──────────► GPT-4o-mini               │
│  ├─ Response Writer ───────────► Claude Sonnet 3.5          │
│  └─ Fact Verification ─────────► GPT-4o                     │
│                                                              │
│  Batch Flow:                                                 │
│  ├─ Hook Writer ───────────────► Claude Sonnet 3.5          │
│  ├─ Medium Writer ─────────────► Claude Sonnet 3.5          │
│  ├─ Expanded Writer ───────────► Claude Sonnet 3.5          │
│  └─ Fact Checking (all tiers) ► GPT-4o                      │
│                                                              │
│  Embeddings:                                                 │
│  └─ Vector Store ──────────────► text-embedding-3-large     │
│                                  (1536 dimensions)           │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### Performance Metrics

```
┌─────────────────────────────────────────────────────────────┐
│                  PERFORMANCE TARGETS                         │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  Interactive Query:                                          │
│  ├─ Simple Path: <1 second                                  │
│  ├─ Deep Path: 2-3 seconds                                  │
│  └─ Timeout: 30 seconds                                     │
│                                                              │
│  Batch Processing:                                           │
│  ├─ Per Stock: ~36 seconds (includes all 3 tiers + retries) │
│  ├─ Concurrent: 5 workers                                   │
│  ├─ 50 stocks: ~6 minutes                                   │
│  └─ Total batch window: 2:00 AM - 2:30 AM                   │
│                                                              │
│  Database:                                                   │
│  ├─ Vector Search: <100ms                                   │
│  ├─ Stock Lookup: <50ms                                     │
│  └─ Summary Retrieval: <50ms                                │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## 5. Error Handling & Resilience

### Retry Strategies

```
┌─────────────────────────────────────────────────────────────┐
│                   ERROR HANDLING                             │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  Interactive Flow:                                           │
│  ├─ Input Guardrails Blocked ──► Return safe error message │
│  ├─ LLM Timeout ───────────────► Return cached summary     │
│  ├─ Database Error ────────────► Retry 3x with backoff     │
│  └─ Vector Search Failed ──────► Fall back to SQL search   │
│                                                              │
│  Batch Flow:                                                 │
│  ├─ Fact Check Failed ─────────► Retry with negative prompt│
│  │                                (max 2x per tier)         │
│  ├─ Data Source Unavailable ───► Log & continue            │
│  ├─ Single Stock Failed ───────► Continue with others      │
│  └─ Critical Error ────────────► Mark batch as FAILED      │
│                                                              │
│  Scheduler Flow:                                             │
│  ├─ Database Connection Lost ──► Retry batch run           │
│  ├─ Partial Completion ────────► Resume from last success  │
│  └─ Scheduler Crash ───────────► Next 2 AM run auto-starts │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### Observability

```
┌─────────────────────────────────────────────────────────────┐
│                    OBSERVABILITY                             │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  LangSmith Tracing:                                          │
│  ├─ Project: fa-ai-dev                                      │
│  ├─ Trace every LLM call                                    │
│  ├─ Capture full graph execution                            │
│  └─ Performance analytics                                   │
│                                                              │
│  Logs:                                                       │
│  ├─ logs/batch_scheduler.log ─► Scheduler events           │
│  ├─ logs/batch_processing.log ► Individual stock runs      │
│  └─ logs/interactive.log ──────► API queries                │
│                                                              │
│  Database Audit:                                             │
│  ├─ batch_run_audit ───────────► Batch run history         │
│  ├─ stock_summaries ───────────► Summary versions          │
│  └─ citations ─────────────────► Source tracking           │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## 6. Deployment Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                   DEPLOYMENT TOPOLOGY                        │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌────────────────────────────────────────────────────┐     │
│  │              Next.js Frontend                      │     │
│  │              (Port 3000)                           │     │
│  │  • Stock search                                    │     │
│  │  • Summary history                                 │     │
│  │  • Delta comparison                                │     │
│  └─────────────────┬──────────────────────────────────┘     │
│                    │                                         │
│                    │ HTTP                                    │
│                    ▼                                         │
│  ┌────────────────────────────────────────────────────┐     │
│  │        FastAPI Backend (Interactive)               │     │
│  │        (Port 8000)                                 │     │
│  │  • POST /query ──► Interactive Graph               │     │
│  │  • GET /api/stocks/{ticker}                        │     │
│  │  • GET /api/stocks/{ticker}/summaries/history      │     │
│  └─────────────────┬──────────────────────────────────┘     │
│                    │                                         │
│                    │                                         │
│  ┌────────────────┴────────────────┐                        │
│  │                                  │                        │
│  ▼                                  ▼                        │
│  ┌───────────────┐        ┌────────────────┐               │
│  │ PostgreSQL 16 │        │ Redis 7        │               │
│  │ + pgvector    │        │ (Cache)        │               │
│  │ (Port 5432)   │        │ (Port 6379)    │               │
│  └───────────────┘        └────────────────┘               │
│                                                              │
│  ┌────────────────────────────────────────────────────┐     │
│  │     Batch Scheduler (Background Service)           │     │
│  │     python3 src/batch/scheduler/batch_scheduler.py │     │
│  │                                                     │     │
│  │  • APScheduler cron                                │     │
│  │  • Triggers at 2:00 AM daily                       │     │
│  │  • Runs batch_assistant_graph                      │     │
│  └────────────────────────────────────────────────────┘     │
│                                                              │
│  External Services:                                          │
│  ├─ LangSmith (Observability)                               │
│  ├─ OpenAI API (GPT-4o, embeddings)                         │
│  └─ Anthropic API (Claude Sonnet 3.5)                       │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## Summary

The FA AI System consists of three primary agent flows:

1. **Interactive Flow**: Real-time query processing with guardrails, classification, and deep research capabilities
2. **Batch Flow**: Nightly 3-tier summary generation with fact-checking and retry logic
3. **Scheduler Flow**: 2 AM orchestrator managing concurrent batch processing

All flows integrate with PostgreSQL + pgvector for data storage, LangSmith for observability, and use a combination of Claude Sonnet 3.5 and GPT-4o models for optimal performance and cost.
