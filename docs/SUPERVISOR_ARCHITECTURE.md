# Enterprise Supervisor Architecture - Complete Implementation

## Overview

Enterprise-scale FA Meeting Prep AI using **LangGraph 1.0 Supervisor Pattern**.

**Architecture:** Dual Flow (Batch + Interactive)
**Scale:** 4,000 FAs | 800K Households | 5.6M Accounts | 840M Holdings
**Pattern:** ONE TOOL PER AGENT
**Critical Requirement:** NO BAD DATA to Financial Advisors

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    DUAL FLOW SYSTEM                          │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  BATCH FLOW (Nightly 2-6 AM)                                │
│  ┌────────────────────────────────────────────────┐         │
│  │  Stock Processing Agent                         │         │
│  │  └─ fetch_10k_8k_via_perplexity()              │         │
│  │     • Processes 5,000 stocks                    │         │
│  │     • 100 parallel workers                      │         │
│  │     • Saves to StockSummary table               │         │
│  └────────────────────────────────────────────────┘         │
│                                                               │
│  INTERACTIVE FLOW (Real-Time)                                │
│  ┌────────────────────────────────────────────────┐         │
│  │  Supervisor Agent (Claude Sonnet 4.5)          │         │
│  │                                                  │         │
│  │  ┌──────────────────────────────────────┐      │         │
│  │  │  1. Portfolio Agent                  │      │         │
│  │  │     └─ get_batch_portfolio_data()   │      │         │
│  │  └──────────────────────────────────────┘      │         │
│  │                  ↓                               │         │
│  │  ┌──────────────────────────────────────┐      │         │
│  │  │  2. News Agent                       │      │         │
│  │  │     └─ fetch_current_news()          │      │         │
│  │  └──────────────────────────────────────┘      │         │
│  │                  ↓                               │         │
│  │  ┌──────────────────────────────────────┐      │         │
│  │  │  3. Validator Agent  ⚠️ CRITICAL      │      │         │
│  │  │     └─ validate_all_claims()          │      │         │
│  │  │        • Source Verification          │      │         │
│  │  │        • Consistency Checks            │      │         │
│  │  │        • Hallucination Detection       │      │         │
│  │  └──────────────────────────────────────┘      │         │
│  │                  ↓                               │         │
│  │  ┌──────────────────────────────────────┐      │         │
│  │  │  4. Report Writer Agent              │      │         │
│  │  │     └─ generate_meeting_report()     │      │         │
│  │  └──────────────────────────────────────┘      │         │
│  └────────────────────────────────────────────────┘         │
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

---

## File Structure

```
src/
├── shared/
│   └── models/
│       └── enterprise_database.py       # 840M holdings scale
│
├── integrations/
│   ├── __init__.py
│   └── perplexity_client.py            # Async Perplexity wrapper
│
├── batch/
│   └── agents/
│       └── stock_processing_agent.py    # Batch stock processing
│
└── interactive/
    └── agents/
        ├── portfolio_agent.py           # Batch data retrieval
        ├── news_agent.py               # Real-time news
        ├── validator_agent.py          # 3-layer validation
        ├── report_writer_agent.py      # Claude Sonnet 4.5
        └── supervisor.py               # LangGraph orchestrator
```

---

## ONE TOOL PER AGENT Pattern

Each agent has **exactly ONE `@tool` decorated function**:

### 1. Portfolio Agent
**File:** `src/interactive/agents/portfolio_agent.py:32`

```python
@tool
def get_batch_portfolio_data(household_id: str) -> str:
    """Retrieve pre-generated portfolio from nightly batch run"""
```

**Returns:** Formatted portfolio summary with holdings, sectors, top positions

---

### 2. News Agent
**File:** `src/interactive/agents/news_agent.py:27`

```python
@tool
async def fetch_current_news(tickers: List[str], hours_back: int = 24) -> str:
    """Fetch real-time market news via Perplexity API"""
```

**Returns:** Formatted news with headlines, summaries, dates, sources, citations

---

### 3. Validator Agent ⚠️ CRITICAL
**File:** `src/interactive/agents/validator_agent.py:39`

```python
@tool
async def validate_all_claims(
    portfolio_data: str,
    news_data: str,
    household_id: str
) -> Dict:
    """
    3-Layer Validation:

    Layer 1: Source Verification
    - Batch data freshness (< 24 hours)
    - Ticker existence validation
    - Required fields present

    Layer 2: Consistency Checks
    - Portfolio numbers add up
    - Dates are logical
    - News has sources

    Layer 3: Hallucination Detection
    - Re-queries Perplexity to verify facts
    - Extracts factual claims from news
    - Verifies 90%+ of claims

    Returns confidence score (0.0-1.0)
    Requires 95%+ to pass - NO BAD DATA
    """
```

**Returns:**
```python
{
    "validation_passed": bool,        # True if confidence >= 0.95
    "confidence_score": float,        # 0.0-1.0
    "validation_layers": {
        "source_verification": {...},
        "consistency_checks": {...},
        "hallucination_detection": {...}
    },
    "issues_found": list[str],
    "recommendations": list[str],
    "validated_at": str,
    "validation_duration_seconds": float
}
```

---

### 4. Report Writer Agent
**File:** `src/interactive/agents/report_writer_agent.py:32`

```python
@tool
def generate_meeting_report(
    household_id: str,
    fa_id: str,
    portfolio_data: str,
    news_data: str,
    validation_result: Dict
) -> str:
    """Generate final meeting brief using Claude Sonnet 4.5"""
```

**Returns:** Markdown meeting prep report with:
- Executive summary
- Portfolio overview
- Market news highlights
- Discussion topics
- Data quality notice (if confidence < 95%)
- Metadata footer

---

### 5. Supervisor Agent
**File:** `src/interactive/agents/supervisor.py`

**Two implementations:**

#### A. create_react_agent (Recommended)
```python
def create_supervisor_agent():
    """
    LangGraph create_react_agent with:
    - Claude Sonnet 4.5 as supervisor LLM
    - All 4 subagent tools registered
    - MemorySaver for checkpointing
    """
    supervisor_llm = ChatAnthropic(
        model="claude-sonnet-4-5-20250929",
        temperature=0.1
    )

    tools = [
        get_batch_portfolio_data,
        fetch_current_news,
        validate_all_claims,
        generate_meeting_report
    ]

    return create_react_agent(
        model=supervisor_llm,
        tools=tools,
        state_modifier=system_message,
        checkpointer=MemorySaver()
    )
```

#### B. create_custom_supervisor_graph (Advanced)
```python
def create_custom_supervisor_graph():
    """
    Custom StateGraph for fine-grained control:
    - Portfolio Node → News Node → Validator Node → Report Writer Node
    - Sequential execution
    - MemorySaver checkpointing
    """
    workflow = StateGraph(SupervisorState)
    workflow.add_node("portfolio", portfolio_node)
    workflow.add_node("news", news_node)
    workflow.add_node("validator", validator_node)
    workflow.add_node("report_writer", report_writer_node)

    # Sequential edges
    workflow.set_entry_point("portfolio")
    workflow.add_edge("portfolio", "news")
    workflow.add_edge("news", "validator")
    workflow.add_edge("validator", "report_writer")
    workflow.add_edge("report_writer", END)

    return workflow.compile(checkpointer=MemorySaver())
```

---

## Usage

### High-Level API

```python
from src.interactive.agents.supervisor import generate_meeting_prep

# Async
result = await generate_meeting_prep(
    household_id="JOHNSON-001",
    fa_id="FA-001",
    session_id="meeting-2025-01-09"
)

# Sync
result = generate_meeting_prep_sync(
    household_id="JOHNSON-001",
    fa_id="FA-001"
)

# Result
{
    "success": bool,
    "final_report": str,              # Markdown meeting brief
    "validation_result": dict,
    "execution_time_seconds": float,
    "error": str | None
}
```

### Direct Agent Creation

```python
from src.interactive.agents.supervisor import create_supervisor_agent
from langchain_core.messages import HumanMessage

agent = create_supervisor_agent()

config = {"configurable": {"thread_id": "session-123"}}

result = await agent.ainvoke(
    {"messages": [HumanMessage(content="Generate meeting prep for JOHNSON-001")]},
    config=config
)
```

---

## Validation Requirements

The **Validator Agent is MANDATORY** in the execution flow:

1. **Confidence Threshold:** 95% minimum
2. **3-Layer Validation:** All layers must pass
3. **No Skipping:** Supervisor enforces validation before report generation
4. **Fail-Safe:** On error, validation fails (not passes)

**If Validation Fails:**
- Report Writer adds disclaimer
- Issues and recommendations included
- FA must verify critical data manually

---

## Model Selection

| Component | Model | Purpose |
|-----------|-------|---------|
| **Perplexity** | `llama-3.1-sonar-large-128k-online` | Real-time web search, SEC filings |
| **GPT-4o** | Stock summaries (200 words) | Summarization, data processing |
| **GPT-4o-mini** | Parsing structured data | Structured data extraction from Perplexity |
| **Claude Sonnet 4.5** | Supervisor + Report Writer | Orchestration, narrative generation |

---

## LangGraph Deployment

### Configuration (`langgraph.json`)

```json
{
  "dependencies": ["."],
  "graphs": {
    "supervisor_agent": "./src/interactive/agents/supervisor.py:create_supervisor_agent",
    "custom_supervisor_graph": "./src/interactive/agents/supervisor.py:create_custom_supervisor_graph"
  },
  "env": ".env",
  "python_version": "3.11"
}
```

### Deploy to LangGraph Cloud

```bash
# Install LangGraph CLI
pip install langgraph-cli

# Deploy
langgraph deploy

# Or run locally
langgraph dev
```

---

## Database Schema

**Optimized for 840M holdings scale:**

```python
# Key Tables
class Stock(Base):
    ticker = Column(String(10), primary_key=True, index=True)

class StockSummary(Base):
    summary_id = Column(UUID, primary_key=True)
    ticker = Column(String(10), ForeignKey("stocks.ticker"), index=True)
    batch_run_id = Column(UUID, ForeignKey("batch_runs.batch_run_id"))
    summary = Column(Text)  # 200-word summary
    filing_date = Column(DateTime)
    perplexity_citations = Column(JSONB)

class HouseholdSummary(Base):
    summary_id = Column(UUID, primary_key=True)
    household_id = Column(UUID, ForeignKey("households.household_id"), index=True)
    batch_run_id = Column(UUID, ForeignKey("batch_runs.batch_run_id"))
    total_value = Column(Numeric(15, 2))
    holdings_count = Column(Integer)
    top_holdings = Column(JSONB)
    sector_allocation = Column(JSONB)
    summary = Column(Text)
```

**Partitioning Strategy:**
- Monthly partitions for `stock_summaries` and `household_summaries`
- 90-day retention
- B-tree indexes on `fa_id`, `household_id`, `ticker`

---

## Perplexity Integration

**File:** `src/integrations/perplexity_client.py`

```python
class PerplexityClient:
    async def get_10k_8k(self, ticker: str) -> Dict:
        """Fetch SEC filings with structured parsing"""

    async def get_current_news(
        self,
        tickers: List[str],
        hours_back: int = 24
    ) -> Dict:
        """Fetch real-time market news"""

    async def verify_claim(self, claim: str) -> Dict:
        """Verify factual claims for Validator Agent"""
```

**Features:**
- Async/await for parallelization
- Automatic citation tracking
- GPT-4o-mini for structured data parsing
- Context managers for proper cleanup

---

## Performance Characteristics

### Batch Processing (Nightly)
- **5,000 stocks** processed in **~50 minutes**
- **100 parallel workers**
- Perplexity API rate limits respected
- Database writes batched

### Interactive (Real-Time)
- **Portfolio fetch:** < 500ms (database read)
- **News fetch:** 2-5s (Perplexity API)
- **Validation:** 5-10s (includes Perplexity re-queries)
- **Report generation:** 3-5s (Claude Sonnet 4.5)
- **Total:** 10-20s per meeting prep

---

## Next Steps

1. **Create FastAPI wrapper** for HTTP endpoints
2. **Implement batch supervisor graph** (Phase 1-3 orchestration)
3. **Add LangSmith tracing** throughout
4. **Set up cron triggers** for nightly batch (2 AM)
5. **Deploy to LangGraph Cloud**
6. **Build monitoring dashboard** (validation metrics, latency, error rates)

---

## Testing

Each agent has a `if __name__ == "__main__":` test block:

```bash
# Test Portfolio Agent
python -m src.interactive.agents.portfolio_agent

# Test News Agent
python -m src.interactive.agents.news_agent

# Test Validator Agent
python -m src.interactive.agents.validator_agent

# Test Report Writer
python -m src.interactive.agents.report_writer_agent

# Test Supervisor
python -m src.interactive.agents.supervisor
```

---

## Key Design Principles

1. **ONE TOOL PER AGENT** - Clean separation of concerns
2. **Validation-First** - NO BAD DATA to FAs (non-negotiable)
3. **Async by Default** - Maximize parallelization
4. **Fail-Safe** - On error, fail closed (not open)
5. **Observable** - LangSmith tracing on all operations
6. **Scalable** - Database partitioning, parallel processing
7. **Maintainable** - Clear agent boundaries, testable

---

## Support

**Documentation:** `/docs/`
**Issues:** GitHub Issues
**LangGraph Docs:** https://docs.langchain.com/langgraph
**Perplexity API:** https://docs.perplexity.ai
