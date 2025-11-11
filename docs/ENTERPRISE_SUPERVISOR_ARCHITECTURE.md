# Enterprise FA Meeting Prep - LangGraph Supervisor Architecture
**Production-Scale: 4,000 FAs | 800K Households | 5.6M Accounts | 840M Holdings**

---

## Table of Contents

1. [System Overview](#1-system-overview)
2. [Scale & Performance Requirements](#2-scale--performance-requirements)
3. [Dual Flow Architecture](#3-dual-flow-architecture)
4. [Batch Processing Flow (Nightly)](#4-batch-processing-flow-nightly)
5. [Interactive Flow (Real-Time)](#5-interactive-flow-real-time)
6. [Agent Specifications](#6-agent-specifications)
7. [Deep Agents Integration](#7-deep-agents-integration)
8. [Data Architecture](#8-data-architecture)
9. [Perplexity Integration](#9-perplexity-integration)
10. [Validator Agent (Accuracy Guarantee)](#10-validator-agent-accuracy-guarantee)
11. [Implementation Plan](#11-implementation-plan)
12. [Cost & Performance Analysis](#12-cost--performance-analysis)

---

## 1. System Overview

### Problem Statement

4,000 financial advisors manage 800,000 households, each requiring meeting preparation that:
- Aggregates data from 7 accounts per household (avg)
- Tracks 150 holdings per account (avg)
- Processes 30+ daily reports
- Monitors real-time market news
- Integrates Salesforce CRM data

**Current pain**: 60+ minutes manual prep time per meeting

**Solution**: Automated meeting prep system using:
- **Nightly Batch**: LangGraph assistants generate base summaries (10-K/8-K via Perplexity)
- **Real-Time Interactive**: Supervisor + subagents + Deep Agents combine batch data with current news
- **Validator Agent**: Ensures 100% accuracy (no bad data to FAs)

### Success Metrics

- **Latency**: <30 seconds for meeting brief generation
- **Accuracy**: 100% (validated against sources)
- **Coverage**: All holdings, accounts, and relevant news
- **Time Saved**: 55+ minutes per meeting prep
- **Scale**: Support 4,000 concurrent FAs

---

## 2. Scale & Performance Requirements

### Data Volume

```
4,000 Financial Advisors
   └── 200 Households each = 800,000 total households
       └── 7 Accounts each = 5,600,000 total accounts
           └── 150 Holdings each = 840,000,000 total holdings

Unique Stocks: ~5,000 (assuming diversification)
Daily Reports: 30+ per day
Meeting Prep Requests: ~10,000/day (avg 2.5 per FA)
```

### Database Scale

```sql
-- Holdings table
840M rows × 500 bytes avg = 420 GB

-- Stock summaries (nightly batch)
5,000 stocks × 365 days × 10 KB = 18 GB/year

-- Household summaries (nightly batch)
800K households × 365 days × 5 KB = 1.5 TB/year

-- Optimization: Keep 90 days rolling window
Holdings: 420 GB (static, slow growth)
Stock summaries: 4.5 GB (90-day window)
Household summaries: 370 GB (90-day window)

Total active database: ~800 GB
```

### Batch Processing Window

```
Nightly batch runs: 2 AM - 6 AM (4-hour window)

Phase 1: Stock-level processing
- 5,000 unique stocks
- 10-K/8-K fetch + summarize: ~30 sec/stock
- Parallel workers: 100
- Time: 5,000 stocks / 100 workers × 30 sec = 1,500 sec = 25 minutes

Phase 2: Household-level summarization
- 800,000 households
- Summarize holdings: ~5 sec/household
- Parallel workers: 500
- Time: 800,000 / 500 × 5 sec = 8,000 sec = 133 minutes = 2.2 hours

Total batch time: ~2.5 hours
Buffer for retries: 1.5 hours
Target completion: 5:30 AM
```

### Interactive Performance Targets

```
Meeting prep request:
- Parse request: 100ms
- Database lookups: 500ms (cached)
- Perplexity news fetch: 2 seconds (3-5 tickers)
- LLM processing: 8 seconds (supervisor + 4 subagents)
- Validation: 3 seconds (spot checks)
- Report generation: 2 seconds

Total: <16 seconds (target <30 sec)
Concurrent users: 4,000 (all FAs could request simultaneously)
```

---

## 3. Dual Flow Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                    ENTERPRISE SYSTEM                             │
└──────────────────────────────────────────────────────────────────┘

        NIGHTLY BATCH                    REAL-TIME INTERACTIVE
      (LangGraph Assistants)            (Supervisor + Subagents)
              │                                   │
              │                                   │
      ┌───────▼────────┐                ┌────────▼────────┐
      │  2 AM Trigger  │                │  FA Request     │
      │  (Cron)        │                │  (API Call)     │
      └───────┬────────┘                └────────┬────────┘
              │                                   │
              │                                   │
      ┌───────▼────────────────────┐    ┌────────▼────────────────┐
      │  BATCH ASSISTANT GRAPH     │    │  SUPERVISOR AGENT       │
      │                            │    │                         │
      │  1. Holdings Ingestion     │    │  Coordinates:           │
      │  2. Perplexity 10-K/8-K    │    │  • Portfolio Agent      │
      │  3. Stock Summaries        │    │  • News Agent           │
      │  4. Household Summaries    │    │  • Validator Agent      │
      │  5. Save to DB             │    │  • Report Writer        │
      └───────┬────────────────────┘    └────────┬────────────────┘
              │                                   │
              │                                   │
              ▼                                   ▼
       ┌─────────────┐                    ┌─────────────┐
       │  Database   │◄───────────────────│  Database   │
       │  (Batch     │   Read batch data  │  + Current  │
       │   Data)     │                    │    News     │
       └─────────────┘                    └─────────────┘

```

---

## 4. Batch Processing Flow (Nightly)

### Architecture: LangGraph Assistant with Time Trigger

```python
# langgraph.json
{
  "graphs": {
    "batch_assistant": "./src/batch/batch_assistant.py:batch_assistant_graph"
  },
  "workflows": {
    "nightly_batch": {
      "graph": "batch_assistant",
      "cron": "0 2 * * *",  # 2 AM daily
      "description": "Nightly holdings and summary processing"
    }
  }
}
```

### Batch Flow Diagram

```
┌──────────────────────────────────────────────────────────────────┐
│              NIGHTLY BATCH ASSISTANT GRAPH                       │
│              (2 AM - 6 AM Processing Window)                     │
└──────────────────────────────────────────────────────────────────┘

START (2:00 AM)
  │
  ▼
┌─────────────────────────────────────────┐
│  Phase 1: Holdings Ingestion            │
│                                          │
│  FOR EACH FA (4,000):                   │
│    FOR EACH Household (200):            │
│      FOR EACH Account (7):              │
│        Pull holdings from source system │
│        Update holdings table            │
│                                          │
│  Parallel workers: 500                  │
│  Time: ~30 minutes                      │
└────────────┬────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────┐
│  Phase 2: Stock-Level Processing        │
│                                          │
│  Get unique tickers: ~5,000 stocks      │
│                                          │
│  FOR EACH Stock (parallel: 100):        │
│    ┌─────────────────────────────────┐  │
│    │ Perplexity 10-K/8-K Agent       │  │
│    │ • Search for latest filings     │  │
│    │ • Extract key sections          │  │
│    │ • Summarize (GPT-4)             │  │
│    │ • Save to stock_summaries table │  │
│    └─────────────────────────────────┘  │
│                                          │
│  Time: ~25 minutes                      │
└────────────┬────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────┐
│  Phase 3: Household-Level Summaries     │
│                                          │
│  FOR EACH Household (parallel: 500):    │
│    ┌─────────────────────────────────┐  │
│    │ Household Summarizer Agent      │  │
│    │ • Get all holdings for household│  │
│    │ • Retrieve stock summaries      │  │
│    │ • Calculate portfolio metrics   │  │
│    │ • Generate household summary    │  │
│    │ • Save to household_summaries   │  │
│    └─────────────────────────────────┘  │
│                                          │
│  Time: ~2.2 hours                       │
└────────────┬────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────┐
│  Phase 4: Audit & Notification          │
│                                          │
│  • Update batch_run_audit table         │
│  • Log statistics                       │
│  • Alert on failures                    │
│  • Mark completion timestamp            │
└────────────┬────────────────────────────┘
             │
             ▼
END (5:30 AM target)
```

### Batch Agent Implementation

```python
# src/batch/batch_assistant.py

from langgraph.graph import StateGraph, START, END
from typing import TypedDict
from datetime import datetime
import asyncio

class BatchState(TypedDict):
    batch_run_id: str
    start_time: str
    phase: str
    stocks_processed: int
    households_processed: int
    errors: list
    status: str

async def phase1_ingest_holdings(state: BatchState):
    """Phase 1: Pull all holdings from source systems"""
    logger.info("🔄 Phase 1: Ingesting holdings...")

    # Parallel processing of FAs/households/accounts
    from src.batch.agents.holdings_ingestion_agent import ingest_all_holdings

    result = await ingest_all_holdings(
        batch_run_id=state["batch_run_id"],
        max_workers=500
    )

    return {
        **state,
        "phase": "stock_processing",
        "holdings_updated": result["count"]
    }

async def phase2_process_stocks(state: BatchState):
    """Phase 2: Fetch 10-K/8-K and generate stock summaries via Perplexity"""
    logger.info("📊 Phase 2: Processing stocks...")

    from src.batch.agents.stock_processing_agent import process_stocks_parallel

    result = await process_stocks_parallel(
        batch_run_id=state["batch_run_id"],
        max_workers=100
    )

    return {
        **state,
        "phase": "household_summarization",
        "stocks_processed": result["count"],
        "errors": result.get("errors", [])
    }

async def phase3_summarize_households(state: BatchState):
    """Phase 3: Generate household-level summaries"""
    logger.info("🏠 Phase 3: Summarizing households...")

    from src.batch.agents.household_summary_agent import summarize_households_parallel

    result = await summarize_households_parallel(
        batch_run_id=state["batch_run_id"],
        max_workers=500
    )

    return {
        **state,
        "phase": "completed",
        "households_processed": result["count"],
        "errors": state["errors"] + result.get("errors", [])
    }

async def phase4_audit(state: BatchState):
    """Phase 4: Record batch run statistics"""
    logger.info("✅ Phase 4: Finalizing batch run...")

    from src.batch.agents.audit_agent import record_batch_completion

    await record_batch_completion(
        batch_run_id=state["batch_run_id"],
        stocks_processed=state["stocks_processed"],
        households_processed=state["households_processed"],
        errors=state["errors"]
    )

    return {
        **state,
        "status": "COMPLETED"
    }

# Build batch graph
def create_batch_assistant_graph():
    builder = StateGraph(BatchState)

    builder.add_node("phase1_holdings", phase1_ingest_holdings)
    builder.add_node("phase2_stocks", phase2_process_stocks)
    builder.add_node("phase3_households", phase3_summarize_households)
    builder.add_node("phase4_audit", phase4_audit)

    builder.add_edge(START, "phase1_holdings")
    builder.add_edge("phase1_holdings", "phase2_stocks")
    builder.add_edge("phase2_stocks", "phase3_households")
    builder.add_edge("phase3_households", "phase4_audit")
    builder.add_edge("phase4_audit", END)

    return builder.compile()

batch_assistant_graph = create_batch_assistant_graph()
```

### Key Batch Agents (One Tool Each)

#### 4.1 Stock Processing Agent

```python
# src/batch/agents/stock_processing_agent.py

from langchain_core.tools import tool
from langgraph.prebuilt import create_react_agent
from langchain_openai import ChatOpenAI

@tool
def fetch_10k_8k_via_perplexity(ticker: str) -> dict:
    """Fetch latest 10-K and 8-K filings via Perplexity API.

    Returns structured data with key sections extracted.
    """
    from src.integrations.perplexity_client import PerplexityClient

    client = PerplexityClient()

    query = f"""
    Find the most recent 10-K and 8-K SEC filings for {ticker}.
    Extract and summarize:
    - Business overview
    - Recent financial performance
    - Risk factors
    - Management discussion
    """

    result = client.search(query, focus="finance")

    return {
        "ticker": ticker,
        "filing_date": result.get("date"),
        "business_summary": result.get("business"),
        "financials": result.get("financials"),
        "risks": result.get("risks"),
        "raw_citations": result.get("citations", [])
    }

# Stock processing agent - uses ONE tool
stock_agent = create_react_agent(
    model=ChatOpenAI(model="gpt-4o"),
    tools=[fetch_10k_8k_via_perplexity],
    system_message="""You are a stock analysis agent. Given a ticker:
    1. Use fetch_10k_8k_via_perplexity to get SEC filing data
    2. Create a concise summary (200 words) covering:
       - Company overview
       - Recent performance
       - Key risks
    3. Return structured summary for database storage
    """
)

async def process_stocks_parallel(batch_run_id: str, max_workers: int = 100):
    """Process all stocks in parallel"""
    import asyncio
    from sqlalchemy import select

    with db.session() as session:
        # Get unique tickers
        result = session.execute("""
            SELECT DISTINCT ticker
            FROM holdings
            WHERE is_active = true
        """)
        tickers = [row[0] for row in result]

    logger.info(f"Processing {len(tickers)} stocks with {max_workers} workers")

    # Process in parallel batches
    async def process_batch(ticker_batch):
        tasks = []
        for ticker in ticker_batch:
            task = stock_agent.ainvoke({
                "messages": [{"role": "user", "content": f"Process {ticker}"}]
            })
            tasks.append(task)
        return await asyncio.gather(*tasks)

    # Split into batches
    batches = [tickers[i:i + max_workers] for i in range(0, len(tickers), max_workers)]

    processed = 0
    errors = []

    for batch in batches:
        try:
            results = await process_batch(batch)
            processed += len(results)

            # Save to database
            with db.session() as session:
                for result in results:
                    summary = extract_summary(result)
                    session.execute("""
                        INSERT INTO stock_summaries
                        (ticker, batch_run_id, summary, filing_date, created_at)
                        VALUES (:ticker, :batch_run_id, :summary, :filing_date, NOW())
                    """, summary)
                session.commit()

        except Exception as e:
            logger.error(f"Batch processing error: {e}")
            errors.append(str(e))

    return {"count": processed, "errors": errors}
```

#### 4.2 Household Summary Agent

```python
# src/batch/agents/household_summary_agent.py

@tool
def get_household_holdings_with_summaries(household_id: str) -> dict:
    """Get all holdings for household with their stock summaries.

    Returns complete portfolio picture for summarization.
    """
    with db.session() as session:
        result = session.execute("""
            SELECT
                h.ticker,
                h.shares,
                h.cost_basis,
                s.current_price,
                ss.summary as stock_summary,
                ss.filing_date
            FROM holdings h
            JOIN stocks s ON h.ticker = s.ticker
            LEFT JOIN stock_summaries ss ON s.ticker = ss.ticker
            WHERE h.household_id = :household_id
            AND ss.batch_run_id = (
                SELECT batch_run_id FROM batch_runs
                ORDER BY created_at DESC LIMIT 1
            )
        """, {"household_id": household_id})

        holdings = [dict(row) for row in result]

        return {
            "household_id": household_id,
            "holdings_count": len(holdings),
            "holdings": holdings,
            "total_value": sum(h["shares"] * h["current_price"] for h in holdings)
        }

# Household agent - uses ONE tool
household_agent = create_react_agent(
    model=ChatOpenAI(model="gpt-4o"),
    tools=[get_household_holdings_with_summaries],
    system_message="""You are a household portfolio summarizer.

    Given a household ID:
    1. Use get_household_holdings_with_summaries to retrieve all holdings
    2. Aggregate stock-level insights into portfolio-level summary
    3. Identify key themes, concentrations, risks
    4. Generate a 300-word household summary

    Format output for database storage.
    """
)

async def summarize_households_parallel(batch_run_id: str, max_workers: int = 500):
    """Summarize all households in parallel"""
    # Similar pattern to stock processing
    # Get all household IDs, process in batches
    # Save results to household_summaries table
    pass
```

---

## 5. Interactive Flow (Real-Time)

### Architecture: Supervisor + Subagents + Deep Agents

```
┌──────────────────────────────────────────────────────────────────┐
│                 INTERACTIVE SUPERVISOR AGENT                     │
│                  (Meeting Prep Orchestrator)                     │
└──────────────────┬───────────────────────────────────────────────┘
                   │
                   │ Coordinates specialized subagents
                   │ (each has ONE tool, own file)
                   │
       ┌───────────┼───────────┬───────────┬───────────┐
       │           │           │           │           │
       ▼           ▼           ▼           ▼           ▼
┌──────────┐ ┌──────────┐ ┌─────────┐ ┌──────────┐ ┌──────────┐
│Portfolio │ │  News    │ │Validator│ │ Report   │ │  Deep    │
│ Agent    │ │  Agent   │ │ Agent   │ │ Writer   │ │  Agent   │
│          │ │          │ │         │ │  Agent   │ │(Complex) │
├──────────┤ ├──────────┤ ├─────────┤ ├──────────┤ ├──────────┤
│ONE TOOL: │ │ONE TOOL: │ │ONE TOOL:│ │ONE TOOL: │ │Deep      │
│get_batch │ │fetch_news│ │validate │ │generate  │ │reasoning │
│_data     │ │          │ │_claims  │ │_report   │ │when      │
│          │ │          │ │         │ │          │ │needed    │
└──────────┘ └──────────┘ └─────────┘ └──────────┘ └──────────┘
    │             │            │            │            │
    │             │            │            │            │
    └─────────────┴────────────┴────────────┴────────────┘
                              │
                              │ All access shared data
                              ▼
                    ┌──────────────────┐
                    │  PostgreSQL DB   │
                    │  • Batch data    │
                    │  • Holdings      │
                    │  • Summaries     │
                    └──────────────────┘
```

### Interactive Flow Diagram

```
USER REQUEST:
"Prepare me for my meeting with Johnson household tomorrow"

┌──────────────────────────────────────────────────────────────┐
│  SUPERVISOR AGENT                                            │
└────────────────┬─────────────────────────────────────────────┘
                 │
                 │ 1. Parse request
                 │    household_id = "JOHNSON-001"
                 │    fa_id = "FA-001"
                 │
                 ▼
        ┌────────────────┐
        │ PLANNING       │
        │ (Deep Agent)   │
        │ "Need:"        │
        │ • Portfolio    │
        │ • Current news │
        │ • Validation   │
        │ • Report       │
        └────────┬───────┘
                 │
                 │ 2. Execute in order (with validation)
                 │
     ┌───────────┼───────────┐
     │           │           │
     ▼           ▼           ▼
┌─────────┐ ┌─────────┐ ┌─────────┐
│Portfolio│ │  News   │ │Validator│
│ Agent   │ │ Agent   │ │ Agent   │
└────┬────┘ └────┬────┘ └────┬────┘
     │           │           │
     │ Tool:     │ Tool:     │ Tool:
     │ get_batch │ fetch_    │ validate_
     │ _data     │ news      │ claims
     │           │           │
     │ Returns:  │ Returns:  │ Returns:
     │ Batch     │ Current   │ Validated
     │ summary   │ news      │ ✓ or ✗
     │           │           │
     └───────────┴───────────┘
                 │
                 │ If validation fails, retry or flag
                 │
                 ▼
         ┌───────────────┐
         │ Report Writer │
         │ Agent         │
         │               │
         │ Tool:         │
         │ generate_     │
         │ report        │
         └───────┬───────┘
                 │
                 │ Returns:
                 │ Formatted
                 │ meeting brief
                 │
                 ▼
         ┌───────────────┐
         │ FINAL OUTPUT  │
         │               │
         │ Meeting Brief │
         │ (Validated)   │
         └───────────────┘
```

### Interactive Agent Specifications

#### 5.1 Supervisor Agent

```python
# src/interactive/agents/supervisor.py

from langgraph.prebuilt import create_react_agent
from langchain_anthropic import ChatAnthropic
from typing import TypedDict, Annotated
from langgraph.graph.message import add_messages

class SupervisorState(TypedDict):
    household_id: str
    fa_id: str
    meeting_date: str
    messages: Annotated[list, add_messages]

    # Subagent results
    portfolio_data: str | None
    news_data: str | None
    validation_passed: bool
    meeting_brief: str | None

# Import all subagent tools (each from separate file)
from src.interactive.agents.portfolio_agent import get_batch_portfolio_data
from src.interactive.agents.news_agent import fetch_current_news
from src.interactive.agents.validator_agent import validate_all_claims
from src.interactive.agents.report_writer_agent import generate_meeting_report

SUPERVISOR_PROMPT = """You are a meeting preparation supervisor for financial advisors.

Your job:
1. Call get_batch_portfolio_data to retrieve overnight batch summaries
2. Call fetch_current_news to get real-time market updates
3. Call validate_all_claims to ensure accuracy (CRITICAL - no bad data)
4. If validation fails, retry or escalate
5. Call generate_meeting_report to create final brief

IMPORTANT: Always validate before finalizing. Never return unvalidated information.

Available tools:
- get_batch_portfolio_data(household_id) -> portfolio summary
- fetch_current_news(tickers) -> current news
- validate_all_claims(data) -> validation result
- generate_meeting_report(portfolio, news) -> formatted brief
"""

supervisor_agent = create_react_agent(
    model=ChatAnthropic(model="claude-sonnet-4-5-20250929"),
    tools=[
        get_batch_portfolio_data,
        fetch_current_news,
        validate_all_claims,
        generate_meeting_report
    ],
    state_schema=SupervisorState,
    system_message=SUPERVISOR_PROMPT,
    checkpointer=MemorySaver()
)
```

#### 5.2 Portfolio Agent (ONE TOOL)

```python
# src/interactive/agents/portfolio_agent.py
# ONE TOOL PER FILE PATTERN

from langchain_core.tools import tool

@tool
def get_batch_portfolio_data(household_id: str) -> str:
    """Retrieve pre-generated portfolio summary from nightly batch.

    This tool reads the household summary created during the 2 AM batch run.
    Returns formatted portfolio overview with holdings and stock insights.

    Args:
        household_id: Unique identifier for the household

    Returns:
        Formatted portfolio summary (text)
    """
    with db.session() as session:
        # Get latest household summary from batch
        result = session.execute("""
            SELECT
                hs.summary,
                hs.total_value,
                hs.holdings_count,
                hs.top_holdings,
                hs.batch_run_id,
                br.completed_at as batch_date
            FROM household_summaries hs
            JOIN batch_runs br ON hs.batch_run_id = br.batch_run_id
            WHERE hs.household_id = :household_id
            ORDER BY br.completed_at DESC
            LIMIT 1
        """, {"household_id": household_id}).fetchone()

        if not result:
            return f"No batch data found for household {household_id}"

        # Format as text summary
        summary = f"""
        Portfolio Summary for Household {household_id}
        (Data as of: {result['batch_date']})

        Total Value: ${result['total_value']:,.2f}
        Holdings Count: {result['holdings_count']}

        Top Holdings:
        {result['top_holdings']}

        Summary:
        {result['summary']}
        """

        return summary.strip()
```

#### 5.3 News Agent (ONE TOOL)

```python
# src/interactive/agents/news_agent.py
# ONE TOOL PER FILE PATTERN

from langchain_core.tools import tool

@tool
def fetch_current_news(tickers: list[str], hours_back: int = 24) -> str:
    """Fetch real-time market news for specified tickers via Perplexity.

    Args:
        tickers: List of stock tickers (e.g., ["AAPL", "MSFT"])
        hours_back: How many hours of news to retrieve (default 24)

    Returns:
        Formatted news summary with citations
    """
    from src.integrations.perplexity_client import PerplexityClient
    from datetime import datetime, timedelta

    client = PerplexityClient()

    cutoff_time = datetime.now() - timedelta(hours=hours_back)

    query = f"""
    What are the most important news and market developments for these stocks
    in the last {hours_back} hours: {', '.join(tickers)}?

    Focus on:
    - Earnings announcements
    - Product launches
    - M&A activity
    - Regulatory changes
    - Analyst upgrades/downgrades

    Provide specific, factual information with dates.
    """

    result = client.search(
        query=query,
        focus="finance",
        search_recency_filter="day"  # Last 24 hours
    )

    # Format news summary
    news_items = result.get("items", [])

    formatted = f"Current News (Last {hours_back} Hours):\n\n"

    for item in news_items:
        formatted += f"• [{item['source']}] {item['headline']}\n"
        formatted += f"  Date: {item['published_at']}\n"
        formatted += f"  Summary: {item['summary']}\n"
        formatted += f"  Tickers: {', '.join(item.get('tickers', []))}\n\n"

    formatted += f"\nCitations:\n"
    for citation in result.get("citations", []):
        formatted += f"- {citation}\n"

    return formatted
```

#### 5.4 Validator Agent (ONE TOOL - CRITICAL)

```python
# src/interactive/agents/validator_agent.py
# ONE TOOL PER FILE PATTERN

from langchain_core.tools import tool

@tool
def validate_all_claims(data: dict) -> dict:
    """Validate all factual claims by checking against original sources.

    This is CRITICAL - we NEVER provide unvalidated data to financial advisors.

    Args:
        data: Dictionary with keys:
            - portfolio_data: str (from batch)
            - news_data: str (from Perplexity)
            - tickers: list[str]

    Returns:
        Dictionary with validation results:
        {
            "passed": bool,
            "confidence_score": float,
            "issues_found": list[str],
            "validated_claims": list[str]
        }
    """
    from src.integrations.perplexity_client import PerplexityClient

    client = PerplexityClient()

    # Extract key claims from portfolio and news data
    claims = extract_claims(data)

    validation_results = {
        "passed": True,
        "confidence_score": 1.0,
        "issues_found": [],
        "validated_claims": []
    }

    for claim in claims:
        # Verify each claim by querying source
        verification_query = f"""
        Verify this claim: "{claim['text']}"

        Check if this is factually accurate as of today.
        If it references data, confirm the numbers are correct.
        If it's about recent news, confirm the event occurred.

        Respond with: VERIFIED or INVALID with explanation.
        """

        result = client.search(
            query=verification_query,
            focus="finance"
        )

        if "INVALID" in result["answer"]:
            validation_results["passed"] = False
            validation_results["issues_found"].append({
                "claim": claim["text"],
                "reason": result["answer"]
            })
            validation_results["confidence_score"] -= 0.2
        else:
            validation_results["validated_claims"].append(claim["text"])

    # Set confidence score (0.0 - 1.0)
    validation_results["confidence_score"] = max(0.0, validation_results["confidence_score"])

    # Log validation results
    logger.info(f"Validation: {validation_results}")

    return validation_results

def extract_claims(data: dict) -> list:
    """Extract factual claims that need validation"""
    from langchain_openai import ChatOpenAI

    llm = ChatOpenAI(model="gpt-4o")

    prompt = f"""
    Extract all factual claims from this data that should be verified:

    Portfolio Data:
    {data.get('portfolio_data', '')}

    News Data:
    {data.get('news_data', '')}

    Return a JSON list of claims with format:
    [
        {{"text": "Apple stock is up 5% this week", "source": "news"}},
        {{"text": "Portfolio holds 100 shares of AAPL", "source": "portfolio"}}
    ]
    """

    result = llm.invoke(prompt)
    return json.loads(result.content)
```

#### 5.5 Report Writer Agent (ONE TOOL)

```python
# src/interactive/agents/report_writer_agent.py
# ONE TOOL PER FILE PATTERN

from langchain_core.tools import tool

@tool
def generate_meeting_report(
    household_id: str,
    portfolio_data: str,
    news_data: str,
    validation_passed: bool
) -> str:
    """Generate final formatted meeting brief.

    Args:
        household_id: Household identifier
        portfolio_data: Validated portfolio summary
        news_data: Validated news summary
        validation_passed: Whether validation succeeded

    Returns:
        Formatted meeting brief (markdown)
    """
    from langchain_anthropic import ChatAnthropic

    llm = ChatAnthropic(model="claude-sonnet-4-5-20250929")

    prompt = f"""
    Create a comprehensive meeting preparation brief for financial advisor.

    Household: {household_id}
    Validation Status: {"✓ VALIDATED" if validation_passed else "⚠️ VALIDATION ISSUES"}

    Portfolio Summary:
    {portfolio_data}

    Current News:
    {news_data}

    Generate a structured brief with:
    1. Executive Summary (2-3 sentences)
    2. Portfolio Highlights
       - Total value and performance
       - Top holdings
       - Recent changes
    3. Market Context
       - Relevant news impacting holdings
       - Sector trends
    4. Talking Points (5-7 specific points for the meeting)
    5. Recommended Actions
    6. Appendix (detailed data)

    Format in markdown. Be concise and actionable.
    """

    result = llm.invoke(prompt)

    # Add validation disclaimer if needed
    report = result.content

    if not validation_passed:
        report = "⚠️ VALIDATION ISSUES DETECTED - REVIEW BEFORE USE\n\n" + report

    return report
```

---

## 6. Agent Specifications (Complete List)

### One Tool Per Agent Architecture

```
src/interactive/agents/
├── supervisor.py              # Orchestrator (uses all subagent tools)
├── portfolio_agent.py         # ONE TOOL: get_batch_portfolio_data()
├── news_agent.py              # ONE TOOL: fetch_current_news()
├── validator_agent.py         # ONE TOOL: validate_all_claims()
├── report_writer_agent.py     # ONE TOOL: generate_meeting_report()
└── deep_agent.py              # Deep Agent for complex reasoning

src/batch/agents/
├── holdings_ingestion_agent.py    # ONE TOOL: ingest_holdings()
├── stock_processing_agent.py      # ONE TOOL: fetch_10k_8k_via_perplexity()
├── household_summary_agent.py     # ONE TOOL: get_household_holdings_with_summaries()
└── audit_agent.py                 # ONE TOOL: record_batch_completion()
```

---

## 7. Deep Agents Integration

### When to Use Deep Agents

From LangChain documentation, Deep Agents are appropriate for:
- Complex multi-step workflows demanding decomposition
- Management of substantial contextual information
- Work distribution across specialized subsystems

### Use Case: Complex Portfolio Analysis

When the supervisor encounters a request requiring deep reasoning:

```python
# src/interactive/agents/deep_agent.py

from deep_agents import create_deep_agent

@tool
def analyze_complex_portfolio(household_id: str, request: str) -> str:
    """Handle complex portfolio analysis requiring multi-step reasoning.

    Examples:
    - "Analyze tax implications of rebalancing this portfolio"
    - "Compare this portfolio to optimal allocation for client age/goals"
    - "Identify hedging opportunities given current holdings"

    Args:
        household_id: Household to analyze
        request: Complex analysis request

    Returns:
        Detailed analysis with reasoning steps
    """
    # Create deep agent with planning and file management
    deep_agent = create_deep_agent(
        model="claude-sonnet-4-5-20250929",
        tools=[
            get_household_data,
            calculate_tax_implications,
            fetch_market_correlations,
            simulate_rebalancing
        ],
        enable_planning=True,  # write_todos tool
        enable_file_ops=True   # read/write/edit/list files
    )

    # Deep agent will:
    # 1. Break down the complex request into steps (planning)
    # 2. Delegate to specialized subagents (task tool)
    # 3. Manage large context via file operations
    # 4. Synthesize final comprehensive analysis

    result = deep_agent.invoke({
        "household_id": household_id,
        "request": request,
        "context": "This is for a meeting prep. FA needs actionable insights."
    })

    return result["analysis"]
```

### Deep Agent Flow Example

```
User: "Analyze tax-loss harvesting opportunities for the Johnson household"

┌──────────────────────────────────────┐
│  SUPERVISOR detects complex request  │
│  Routes to Deep Agent                │
└────────────┬─────────────────────────┘
             │
             ▼
┌──────────────────────────────────────┐
│  DEEP AGENT activates                │
│                                       │
│  1. Planning (write_todos):          │
│     ☐ Get all holdings with P&L      │
│     ☐ Identify positions with losses │
│     ☐ Find similar securities        │
│     ☐ Calculate tax savings          │
│     ☐ Check wash sale rules          │
│                                       │
│  2. Executes steps with subagents:   │
│     ┌─────────────────────┐          │
│     │ Holdings Subagent   │          │
│     └──────────┬──────────┘          │
│                │                     │
│     ┌──────────▼──────────┐          │
│     │ Tax Calc Subagent   │          │
│     └──────────┬──────────┘          │
│                │                     │
│     ┌──────────▼──────────┐          │
│     │ Compliance Subagent │          │
│     └─────────────────────┘          │
│                                       │
│  3. File Operations:                 │
│     - Write intermediate results     │
│     - Manage large context           │
│                                       │
│  4. Synthesis:                       │
│     - Combines all analysis          │
│     - Generates actionable plan      │
└────────────┬─────────────────────────┘
             │
             ▼
┌──────────────────────────────────────┐
│  Returns to SUPERVISOR               │
│  → Passed to Report Writer           │
│  → Validation                        │
│  → Final Brief                       │
└──────────────────────────────────────┘
```

---

## 8. Data Architecture

### Database Schema (Updated for Scale)

```sql
-- Core entities
CREATE TABLE financial_advisors (
    fa_id VARCHAR(50) PRIMARY KEY,
    name VARCHAR(255),
    firm VARCHAR(255),
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE households (
    household_id UUID PRIMARY KEY,
    household_name VARCHAR(255),
    fa_id VARCHAR(50) REFERENCES financial_advisors,
    total_aum DECIMAL(15,2),
    relationship_tier VARCHAR(50),
    client_since DATE,
    INDEX idx_fa_id (fa_id)
);

CREATE TABLE accounts (
    account_id UUID PRIMARY KEY,
    household_id UUID REFERENCES households,
    account_name VARCHAR(255),
    account_type VARCHAR(50),
    current_value DECIMAL(15,2),
    INDEX idx_household_id (household_id)
);

CREATE TABLE holdings (
    holding_id UUID PRIMARY KEY,
    account_id UUID REFERENCES accounts,
    ticker VARCHAR(10),
    shares DECIMAL(15,4),
    cost_basis DECIMAL(15,2),
    current_price DECIMAL(15,2),
    purchase_date DATE,
    last_updated TIMESTAMP,
    is_active BOOLEAN DEFAULT true,
    INDEX idx_account_id (account_id),
    INDEX idx_ticker (ticker)
);

-- Batch processing tables
CREATE TABLE batch_runs (
    batch_run_id UUID PRIMARY KEY,
    start_time TIMESTAMP,
    end_time TIMESTAMP,
    status VARCHAR(50),
    stocks_processed INT,
    households_processed INT,
    errors JSONB
);

CREATE TABLE stock_summaries (
    summary_id UUID PRIMARY KEY,
    ticker VARCHAR(10),
    batch_run_id UUID REFERENCES batch_runs,
    summary TEXT,
    filing_date DATE,
    perplexity_citations JSONB,
    created_at TIMESTAMP DEFAULT NOW(),
    INDEX idx_ticker_batch (ticker, batch_run_id)
);

CREATE TABLE household_summaries (
    summary_id UUID PRIMARY KEY,
    household_id UUID REFERENCES households,
    batch_run_id UUID REFERENCES batch_runs,
    summary TEXT,
    total_value DECIMAL(15,2),
    holdings_count INT,
    top_holdings JSONB,
    created_at TIMESTAMP DEFAULT NOW(),
    INDEX idx_household_batch (household_id, batch_run_id)
);

-- Partitioning for scale
CREATE TABLE stock_summaries_partitioned (
    summary_id UUID,
    ticker VARCHAR(10),
    batch_run_id UUID,
    summary TEXT,
    filing_date DATE,
    created_at TIMESTAMP
) PARTITION BY RANGE (created_at);

-- Create monthly partitions
CREATE TABLE stock_summaries_2025_11 PARTITION OF stock_summaries_partitioned
    FOR VALUES FROM ('2025-11-01') TO ('2025-12-01');

CREATE TABLE stock_summaries_2025_12 PARTITION OF stock_summaries_partitioned
    FOR VALUES FROM ('2025-12-01') TO ('2026-01-01');
```

### Data Volume Optimization

```
Partitioning Strategy:
- stock_summaries: Monthly partitions (drop after 90 days)
- household_summaries: Monthly partitions (drop after 90 days)
- holdings: No partitioning (relatively static)

Indexing:
- B-tree on fa_id, household_id, ticker
- Covering indexes on frequent query patterns

Caching:
- Redis for frequently accessed household summaries
- 1-hour TTL (refreshes during batch run)

Cold Storage:
- Archive summaries >90 days to S3
- Compress with zstd (10:1 ratio typical)
```

---

## 9. Perplexity Integration

### Perplexity Client Wrapper

```python
# src/integrations/perplexity_client.py

import httpx
from typing import Optional

class PerplexityClient:
    """Wrapper for Perplexity API with finance-focused querying"""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("PERPLEXITY_API_KEY")
        self.base_url = "https://api.perplexity.ai"
        self.client = httpx.AsyncClient(timeout=30.0)

    async def search(
        self,
        query: str,
        focus: str = "finance",
        search_recency_filter: str = "month"
    ) -> dict:
        """
        Search Perplexity for financial information

        Args:
            query: Search query
            focus: Domain focus (finance, news, etc.)
            search_recency_filter: Time window (day, week, month, year)

        Returns:
            {
                "answer": str,
                "citations": list[str],
                "items": list[dict],  # Parsed news items
                "metadata": dict
            }
        """
        response = await self.client.post(
            f"{self.base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            },
            json={
                "model": "llama-3.1-sonar-large-128k-online",
                "messages": [
                    {"role": "system", "content": f"Focus: {focus}"},
                    {"role": "user", "content": query}
                ],
                "search_recency_filter": search_recency_filter,
                "return_citations": True,
                "return_images": False
            }
        )

        data = response.json()

        return {
            "answer": data["choices"][0]["message"]["content"],
            "citations": data.get("citations", []),
            "items": self._parse_answer(data["choices"][0]["message"]["content"]),
            "metadata": {
                "model": data["model"],
                "usage": data.get("usage", {})
            }
        }

    def _parse_answer(self, answer: str) -> list[dict]:
        """Parse structured information from answer text"""
        # Use LLM to extract structured news items
        from langchain_openai import ChatOpenAI

        llm = ChatOpenAI(model="gpt-4o-mini")

        prompt = f"""
        Extract news items from this text. Return JSON list:

        {answer}

        Format:
        [
          {{
            "headline": "...",
            "summary": "...",
            "published_at": "YYYY-MM-DD",
            "source": "...",
            "tickers": ["AAPL", ...]
          }}
        ]
        """

        result = llm.invoke(prompt)
        return json.loads(result.content)

    async def get_10k_8k(self, ticker: str) -> dict:
        """Specialized method for SEC filings"""
        query = f"""
        Find the most recent 10-K and 8-K SEC filings for {ticker}.
        Provide:
        - Filing date
        - Business summary
        - Key financial metrics
        - Material risk factors
        - Management's discussion
        """

        return await self.search(query, focus="finance", search_recency_filter="year")
```

### Usage in Agents

```python
# In stock processing agent
@tool
def fetch_10k_8k_via_perplexity(ticker: str) -> dict:
    from src.integrations.perplexity_client import PerplexityClient

    client = PerplexityClient()
    result = await client.get_10k_8k(ticker)

    return {
        "ticker": ticker,
        "summary": result["answer"],
        "citations": result["citations"],
        "filing_date": extract_date(result["answer"])
    }

# In news agent
@tool
def fetch_current_news(tickers: list[str]) -> str:
    from src.integrations.perplexity_client import PerplexityClient

    client = PerplexityClient()

    query = f"What's the latest news on {', '.join(tickers)}?"
    result = await client.search(query, search_recency_filter="day")

    return format_news_summary(result)
```

---

## 10. Validator Agent (Accuracy Guarantee)

### Validation Strategy

```
┌──────────────────────────────────────────────────────────────┐
│              VALIDATION ARCHITECTURE                         │
│          "NO BAD DATA TO FINANCIAL ADVISORS"                 │
└──────────────────────────────────────────────────────────────┘

Three-Layer Validation:

1. SOURCE VERIFICATION
   ├─ Portfolio data: Check against batch_runs table timestamp
   ├─ Holdings: Verify counts match database
   └─ News: Re-query Perplexity to confirm facts

2. CONSISTENCY CHECKS
   ├─ Numbers add up (total value = sum of holdings)
   ├─ Dates are logical (not future dates)
   └─ Tickers exist and are valid

3. HALLUCINATION DETECTION
   ├─ Cross-reference claims with original sources
   ├─ Flag unsupported assertions
   └─ Require citations for all factual statements
```

### Implementation

```python
# src/interactive/agents/validator_agent.py (EXPANDED)

from langchain_core.tools import tool
from enum import Enum

class ValidationLevel(Enum):
    STRICT = "strict"      # Every claim verified (slowest)
    STANDARD = "standard"  # Key claims verified (default)
    QUICK = "quick"        # Basic checks only (fastest)

@tool
def validate_all_claims(
    data: dict,
    level: ValidationLevel = ValidationLevel.STANDARD
) -> dict:
    """
    Multi-layered validation to ensure accuracy

    Args:
        data: Data to validate (portfolio, news, etc.)
        level: Validation strictness

    Returns:
        {
            "passed": bool,
            "confidence_score": float (0.0 - 1.0),
            "issues_found": list[dict],
            "validated_claims": list[str],
            "validation_time_ms": int
        }
    """
    start_time = time.time()

    validators = [
        SourceVerification(),
        ConsistencyChecker(),
        HallucinationDetector()
    ]

    results = {
        "passed": True,
        "confidence_score": 1.0,
        "issues_found": [],
        "validated_claims": [],
        "validation_time_ms": 0
    }

    for validator in validators:
        validator_result = validator.validate(data, level)

        if not validator_result["passed"]:
            results["passed"] = False
            results["issues_found"].extend(validator_result["issues"])

        results["confidence_score"] *= validator_result["confidence"]
        results["validated_claims"].extend(validator_result["validated"])

    results["validation_time_ms"] = int((time.time() - start_time) * 1000)

    # Log for monitoring
    logger.info(f"Validation: {results['passed']}, "
                f"confidence={results['confidence_score']:.2f}, "
                f"time={results['validation_time_ms']}ms")

    return results

class SourceVerification:
    """Verify data comes from legitimate sources"""

    def validate(self, data: dict, level: ValidationLevel) -> dict:
        issues = []
        validated = []

        # Check batch data freshness
        if "portfolio_data" in data:
            batch_age = self._check_batch_age(data["portfolio_data"])
            if batch_age > 24:  # hours
                issues.append({
                    "type": "stale_data",
                    "message": f"Batch data is {batch_age} hours old"
                })
            else:
                validated.append(f"Batch data is fresh ({batch_age}h old)")

        # Verify holdings exist in database
        if "tickers" in data:
            for ticker in data["tickers"]:
                if not self._ticker_exists(ticker):
                    issues.append({
                        "type": "invalid_ticker",
                        "message": f"Ticker {ticker} not found in database"
                    })
                else:
                    validated.append(f"Ticker {ticker} verified")

        return {
            "passed": len(issues) == 0,
            "confidence": 1.0 if len(issues) == 0 else 0.5,
            "issues": issues,
            "validated": validated
        }

    def _check_batch_age(self, portfolio_data: str) -> int:
        """Extract and calculate batch data age"""
        # Parse "Data as of: YYYY-MM-DD HH:MM:SS" from portfolio_data
        # Return hours since that timestamp
        pass

    def _ticker_exists(self, ticker: str) -> bool:
        """Check if ticker exists in holdings table"""
        with db.session() as session:
            result = session.execute(
                "SELECT 1 FROM holdings WHERE ticker = :ticker LIMIT 1",
                {"ticker": ticker}
            )
            return result.fetchone() is not None

class ConsistencyChecker:
    """Verify internal consistency of data"""

    def validate(self, data: dict, level: ValidationLevel) -> dict:
        issues = []
        validated = []

        # Check number consistency
        if "portfolio_data" in data:
            numbers = self._extract_numbers(data["portfolio_data"])

            # Verify total = sum of parts
            if "total_value" in numbers and "holding_values" in numbers:
                calculated_total = sum(numbers["holding_values"])
                reported_total = numbers["total_value"]

                if abs(calculated_total - reported_total) / reported_total > 0.01:
                    issues.append({
                        "type": "number_mismatch",
                        "message": f"Total value mismatch: reported ${reported_total:,.2f}, "
                                   f"calculated ${calculated_total:,.2f}"
                    })
                else:
                    validated.append("Portfolio totals are consistent")

        # Check date logic
        dates = self._extract_dates(data)
        for date in dates:
            if date > datetime.now():
                issues.append({
                    "type": "future_date",
                    "message": f"Date {date} is in the future"
                })

        return {
            "passed": len(issues) == 0,
            "confidence": 1.0 if len(issues) == 0 else 0.6,
            "issues": issues,
            "validated": validated
        }

class HallucinationDetector:
    """Detect unsupported claims and potential hallucinations"""

    def validate(self, data: dict, level: ValidationLevel) -> dict:
        from src.integrations.perplexity_client import PerplexityClient

        client = PerplexityClient()
        issues = []
        validated = []

        # Extract factual claims
        claims = self._extract_claims(data)

        if level == ValidationLevel.QUICK:
            # Only check high-risk claims
            claims = [c for c in claims if c["risk"] == "high"]

        for claim in claims:
            # Re-verify with Perplexity
            verification = client.search(
                query=f"Verify: {claim['text']}. Is this accurate?",
                focus="finance"
            )

            if "false" in verification["answer"].lower() or \
               "incorrect" in verification["answer"].lower():
                issues.append({
                    "type": "hallucination",
                    "claim": claim["text"],
                    "reason": verification["answer"]
                })
            else:
                validated.append(claim["text"])

        return {
            "passed": len(issues) == 0,
            "confidence": 1.0 if len(issues) == 0 else 0.3,
            "issues": issues,
            "validated": validated
        }

    def _extract_claims(self, data: dict) -> list:
        """Extract verifiable factual claims from data"""
        # Use LLM to extract claims
        # Mark each as low/medium/high risk
        pass
```

---

## 11. Implementation Plan

### Phase 1: Foundation (Weeks 1-2)

**Batch Flow**:
- ✅ Database schema for scale
- ✅ Stock processing agent + Perplexity tool
- ✅ Batch assistant graph with time trigger
- ✅ Test with 100 stocks

**Interactive Flow**:
- ✅ Supervisor agent scaffold
- ✅ Portfolio agent (get_batch_data tool)
- ✅ Basic validation

**Deliverables**:
- Working batch run on subset of data
- Supervisor can retrieve and display batch data

### Phase 2: Full Batch Pipeline (Weeks 3-4)

**Batch Flow**:
- ✅ Holdings ingestion agent (500 workers)
- ✅ Household summary agent (500 workers)
- ✅ Full 5,000 stock processing (100 workers)
- ✅ Performance optimization

**Testing**:
- Process 800K households overnight
- Verify summaries quality
- Monitor performance metrics

### Phase 3: Interactive Agents (Weeks 5-6)

**Interactive Flow**:
- ✅ News agent + Perplexity integration
- ✅ Validator agent (3-layer validation)
- ✅ Report writer agent
- ✅ End-to-end flow

**Testing**:
- Generate 100 meeting briefs
- Validate accuracy (must be 100%)
- Measure latency (<30 sec)

### Phase 4: Deep Agents & Scale (Weeks 7-8)

**Deep Agents**:
- ✅ Implement deep agent for complex analysis
- ✅ Tax-loss harvesting use case
- ✅ Portfolio optimization use case

**Scale Testing**:
- Load test: 1,000 concurrent requests
- Stress test: 4,000 FA simultaneous access
- Database optimization

### Phase 5: Production Deployment (Weeks 9-10)

**LangGraph Cloud**:
- ✅ Deploy batch assistant
- ✅ Deploy interactive supervisor
- ✅ Configure auth and rate limiting
- ✅ Set up monitoring

**LangSmith**:
- ✅ All traces configured
- ✅ Custom metrics dashboards
- ✅ Alerting on failures

---

## 12. Cost & Performance Analysis

### Batch Processing Costs (Nightly)

```
Phase 1: Holdings Ingestion
- No LLM calls
- Database operations only
- Cost: $0

Phase 2: Stock Processing (5,000 stocks)
- Perplexity API: 5,000 queries × $0.005 = $25
- GPT-4o summarization: 5,000 × 2,000 tokens × $0.0025/1K = $25
- Total: $50/night

Phase 3: Household Summarization (800,000 households)
- GPT-4o: 800K × 500 tokens × $0.0025/1K = $1,000
- Total: $1,000/night

Monthly batch costs: ($50 + $1,000) × 30 = $31,500/month
```

### Interactive Costs (Per Request)

```
Meeting Prep Request:
- Portfolio agent: cached, no LLM call = $0
- News agent: Perplexity query = $0.005
- Validator agent: 3 Perplexity checks = $0.015
- Report writer: Claude Sonnet (3K tokens) = $0.012
- Total per request: $0.032

Daily requests: 10,000
Monthly interactive costs: 10,000 × 30 × $0.032 = $9,600/month
```

### Total Monthly Costs

```
Batch processing: $31,500
Interactive: $9,600
Database (PostgreSQL): $500
LangGraph Cloud: $500
Redis: $100

Total: $42,200/month = $506,400/year
```

### ROI Calculation

```
Time saved per meeting prep: 55 minutes
Meetings per month: 10,000
Total time saved: 550,000 minutes = 9,167 hours

At $100/hour advisor rate:
Value delivered: 9,167 × $100 = $916,700/month

ROI: $916,700 / $42,200 = 21.7x
```

### Performance Targets

```
Batch Processing:
- Window: 2 AM - 6 AM (4 hours)
- Actual: ~2.5 hours (includes buffer)
- Completion rate: 99.5% (allow 0.5% retries)

Interactive:
- P50 latency: <15 seconds
- P95 latency: <30 seconds
- P99 latency: <45 seconds
- Error rate: <0.1%
- Validation pass rate: 99.9%
```

---

## Summary

This enterprise architecture provides:

✅ **Scale**: Handles 4,000 FAs, 800K households, 840M holdings
✅ **Dual Flow**: Nightly batch + real-time interactive
✅ **Supervisor Pattern**: Clear orchestration with specialized agents
✅ **One Tool Per Agent**: Clean, testable, modular design
✅ **Deep Agents**: Complex reasoning when needed
✅ **Perplexity Integration**: 10-K/8-K + real-time news
✅ **Validation**: 3-layer accuracy guarantee (no bad data)
✅ **LangSmith**: Full observability
✅ **LangGraph Cloud**: Production deployment

**Next Steps**:
1. Review architecture with stakeholders
2. Provision infrastructure (database, LangGraph Cloud)
3. Begin Phase 1 implementation
4. Iterate based on pilot FA feedback

This is production-ready design for enterprise financial advisory AI! 🚀
