# FA Meeting Prep Assistant - Supervisor Architecture Plan

**LangGraph 1.0 Supervisor Pattern with Subagents**

---

## Executive Summary

This plan outlines a complete rebuild of the Financial Advisor AI system using LangGraph's supervisor pattern to create an intelligent **Meeting Preparation Assistant**. The system will help financial advisors prepare for client meetings by automatically gathering, analyzing, and synthesizing information from multiple data sources into actionable meeting briefs.

### Key Requirements Met

- ✅ LangGraph 1.0 supervisor pattern architecture
- ✅ Specialized subagents with domain-specific tools
- ✅ Handles 200 households with multiple accounts and holdings
- ✅ Processes 30+ daily reports + news + Salesforce data
- ✅ Generates tailored meeting prep for specific client/household
- ✅ LangSmith observability integration
- ✅ Deployable to LangGraph Cloud

---

## 1. Problem Statement & Use Case

### Current Pain Points

Financial advisors spend **1+ hours** preparing for each client meeting:

- 📊 30+ new research reports arrive daily
- 📈 Multiple holdings across multiple accounts per household
- 💼 Salesforce CRM data scattered across systems
- 📰 Need to track relevant market news
- 📝 Internal team reports and communications
- 🔄 Manual aggregation and synthesis

### Target User Journey

```
FA logs in → Selects household → System auto-generates meeting brief
              ↓
     Brief includes:
     • Household portfolio summary
     • Recent holdings changes
     • Relevant research reports
     • Market news impacting their positions
     • Salesforce notes and action items
     • Recommended talking points
```

### Success Metrics

- Reduce meeting prep time from 60+ minutes to **<5 minutes**
- Surface all relevant information (0 missed critical updates)
- Provide actionable insights (not just data dumps)
- Personalized to specific household context

---

## 2. Architecture Overview

### High-Level Design: Supervisor + 5 Subagents

```
┌─────────────────────────────────────────────────────────────┐
│                    SUPERVISOR AGENT                          │
│          "Meeting Preparation Orchestrator"                  │
│                                                              │
│  Responsibilities:                                           │
│  • Understand FA's meeting prep request                     │
│  • Route tasks to appropriate subagents                     │
│  • Synthesize results into cohesive meeting brief          │
│  • Ensure all critical information is covered              │
└──────────────────┬──────────────────────────────────────────┘
                   │
                   │  Coordinates 5 Specialized Subagents
                   │
       ┌───────────┴───────────┬───────────┬───────────┬──────────┐
       │                       │           │           │          │
       ▼                       ▼           ▼           ▼          ▼
┌─────────────┐      ┌──────────────┐ ┌─────────┐ ┌──────────┐ ┌──────────┐
│ Portfolio   │      │ Research     │ │ News    │ │Salesforce│ │ Talking  │
│ Agent       │      │ Agent        │ │ Agent   │ │ Agent    │ │ Points   │
│             │      │              │ │         │ │          │ │ Agent    │
├─────────────┤      ├──────────────┤ ├─────────┤ ├──────────┤ ├──────────┤
│ Tools:      │      │ Tools:       │ │ Tools:  │ │ Tools:   │ │ Tools:   │
│ • Get       │      │ • Query      │ │• Search │ │• Get     │ │• Generate│
│   holdings  │      │   reports    │ │  news   │ │  notes   │ │  talking │
│ • Calc      │      │ • Filter by  │ │• Filter │ │• Get     │ │  points  │
│   returns   │      │   ticker     │ │  by     │ │  tasks   │ │• Identify│
│ • Identify  │      │ • Extract    │ │  ticker │ │• Get     │ │  risks   │
│   changes   │      │   insights   │ │• Get    │ │  opps    │ │• Suggest │
│             │      │              │ │  market │ │          │ │  actions │
└─────────────┘      └──────────────┘ └─────────┘ └──────────┘ └──────────┘
       │                     │             │           │            │
       │                     │             │           │            │
       └──────────────┬──────┴─────────────┴───────────┴────────────┘
                      │
                      │  All agents access shared data layer
                      ▼
         ┌────────────────────────────────────┐
         │        DATA LAYER                  │
         ├────────────────────────────────────┤
         │ • PostgreSQL (holdings, accounts)  │
         │ • pgvector (reports, embeddings)   │
         │ • Salesforce API                   │
         │ • News APIs (Bloomberg, Reuters)   │
         │ • Internal report storage (S3)     │
         └────────────────────────────────────┘
```

### Architecture Principles

1. **Supervisor as Orchestrator**: Never does the work, only routes and synthesizes
2. **Subagents as Domain Experts**: Each owns a specific knowledge domain
3. **Tools as Capabilities**: Structured, testable, composable functions
4. **Shared State**: All agents can access household context
5. **LangSmith Throughout**: Every LLM call traced end-to-end

---

## 3. Detailed Agent Specifications

### 3.1 Supervisor Agent

**Role**: Meeting preparation orchestrator

**System Prompt**:
```
You are a meeting preparation coordinator for financial advisors. Your job is to:

1. Understand what household the FA is meeting with
2. Delegate information gathering to specialized subagents
3. Synthesize all findings into a comprehensive meeting brief
4. Ensure nothing critical is missed

Available subagents:
- portfolio_agent: Analyzes household holdings, performance, changes
- research_agent: Finds relevant research reports for held securities
- news_agent: Surfaces market news impacting the portfolio
- salesforce_agent: Retrieves CRM notes, tasks, opportunities
- talking_points_agent: Generates FA-ready conversation starters

Always delegate to the appropriate subagent. Never try to answer directly.
Your output should be a well-structured meeting brief document.
```

**Tools** (5 subagents wrapped as tools):
```python
@tool
def analyze_portfolio(household_id: str) -> str:
    """Analyze household portfolio holdings, performance, and recent changes."""

@tool
def gather_research(tickers: list[str]) -> str:
    """Find relevant research reports for specified tickers."""

@tool
def find_relevant_news(tickers: list[str], days: int = 7) -> str:
    """Search for market news impacting specified tickers."""

@tool
def get_salesforce_context(household_id: str) -> str:
    """Retrieve CRM notes, tasks, and opportunities for household."""

@tool
def generate_talking_points(context: dict) -> str:
    """Create FA-ready talking points based on all gathered information."""
```

**State**:
```python
class SupervisorState(TypedDict):
    household_id: str
    fa_id: str
    meeting_date: str
    messages: Annotated[list, add_messages]
    portfolio_summary: Optional[str]
    research_findings: Optional[str]
    news_summary: Optional[str]
    crm_context: Optional[str]
    talking_points: Optional[str]
    final_brief: Optional[str]
```

---

### 3.2 Portfolio Agent

**Role**: Household portfolio analysis specialist

**System Prompt**:
```
You are a portfolio analysis expert. Given a household ID, you:

1. Retrieve all accounts and holdings for the household
2. Calculate current positions, cost basis, unrealized gains/losses
3. Identify significant recent changes (new purchases, sales)
4. Note any concentration risks (>10% in single position)
5. Highlight performance trends

Return a structured summary focusing on what matters for the meeting.
```

**Tools**:
```python
@tool
def get_household_holdings(household_id: str) -> dict:
    """Retrieve all holdings across all accounts for household.

    Returns:
        {
            "accounts": [
                {
                    "account_id": "ACC-001",
                    "account_name": "Joint Brokerage",
                    "holdings": [
                        {
                            "ticker": "AAPL",
                            "shares": 100,
                            "cost_basis": 150.00,
                            "current_price": 180.00,
                            "market_value": 18000,
                            "unrealized_gain": 3000,
                            "percentage": 0.25
                        }
                    ]
                }
            ],
            "total_value": 72000
        }
    """
    with db_manager.get_session() as session:
        # Query holdings joined with accounts
        results = session.query(
            Account, ClientHolding, Stock
        ).join(...)
        return format_holdings(results)

@tool
def calculate_returns(household_id: str, period_days: int = 30) -> dict:
    """Calculate returns over specified period."""

@tool
def identify_recent_changes(household_id: str, days: int = 7) -> list:
    """Find recent trades/rebalancing for the household."""
```

**Output Format**:
```
Portfolio Summary for [Household Name]:

Total AUM: $X.XXM across Y accounts

Key Holdings:
• AAPL (25% of portfolio): +15% return, added 50 shares last week
• MSFT (18% of portfolio): -2% return, no recent activity
• NVDA (12% of portfolio): +45% return, concentration risk alert

Recent Activity:
• Sold 100 shares SPY on [date]
• Added $10K to growth equity position

Performance:
• 30-day return: +8.5%
• YTD return: +12.3%
```

---

### 3.3 Research Agent

**Role**: Research report discovery and synthesis

**System Prompt**:
```
You are a research report specialist. Given a list of tickers:

1. Search the report database for recent research (last 30 days)
2. Filter by relevance and date
3. Extract key insights, ratings, price targets
4. Prioritize actionable information
5. Note any major rating changes

Focus on reports that would be valuable to discuss in the meeting.
```

**Tools**:
```python
@tool
def query_research_reports(
    tickers: list[str],
    days_back: int = 30,
    sources: list[str] = ["bluematrix", "internal"]
) -> list:
    """Vector search research reports for specified tickers.

    Returns:
        [
            {
                "ticker": "AAPL",
                "title": "Apple Q4 Earnings Preview",
                "source": "Goldman Sachs",
                "date": "2025-11-08",
                "rating": "Buy",
                "price_target": 200,
                "key_insights": ["Services growth...", "iPhone demand..."],
                "relevance_score": 0.92
            }
        ]
    """
    # Vector search against bluematrix_reports collection
    results = vector_store.similarity_search(
        query=f"research on {', '.join(tickers)}",
        filter={"ticker": {"$in": tickers}},
        k=10
    )
    return parse_reports(results)

@tool
def extract_report_insights(report_id: str) -> dict:
    """Deep dive into specific report for detailed insights."""

@tool
def compare_ratings(ticker: str, days_back: int = 90) -> dict:
    """Track rating changes over time for a ticker."""
```

**Output Format**:
```
Research Insights for Portfolio Holdings:

AAPL (25% of portfolio):
• Goldman Sachs (Nov 8): Buy, PT $200 → Upgraded from Neutral
  - Services segment accelerating (15% growth)
  - iPhone 15 demand exceeding expectations

• Morgan Stanley (Nov 5): Overweight, PT $195
  - AI features driving upgrade cycle

MSFT (18% of portfolio):
• JPM (Nov 7): Buy, PT $425
  - Azure growth remains strong (28% YoY)
  - Copilot monetization ahead of schedule

Key Takeaway: 2 of 3 top holdings have recent positive analyst updates
```

---

### 3.4 News Agent

**Role**: Market news aggregation and filtering

**System Prompt**:
```
You are a market news curator. Given a list of tickers:

1. Search news from the last 7 days
2. Filter for material events (earnings, M&A, regulatory, macro)
3. Exclude noise (price movements without news catalyst)
4. Summarize impact on the specific position
5. Flag anything urgent or surprising

Prioritize news the FA should definitely mention in the meeting.
```

**Tools**:
```python
@tool
def search_news(
    tickers: list[str],
    days_back: int = 7,
    categories: list[str] = ["earnings", "ma", "regulatory", "product"]
) -> list:
    """Search Bloomberg/Reuters/internal news feeds.

    Returns:
        [
            {
                "ticker": "AAPL",
                "headline": "Apple announces new AI features",
                "source": "Bloomberg",
                "date": "2025-11-09",
                "category": "product",
                "sentiment": "positive",
                "summary": "...",
                "impact": "potential revenue driver"
            }
        ]
    """
    # Could integrate with Bloomberg API, news aggregator, etc.

@tool
def get_market_context(date: str) -> dict:
    """Get broader market context (indices, rates, commodities)."""

@tool
def filter_by_relevance(
    news_items: list,
    portfolio_exposure: dict
) -> list:
    """Prioritize news by portfolio impact."""
```

**Output Format**:
```
Recent News Impacting Portfolio:

AAPL (⬆️ +2.5% this week):
• Nov 9: Apple announces new AI chip partnership with Broadcom
  Impact: Positive for services revenue, addresses AI concerns

• Nov 7: Q4 earnings beat expectations (EPS $1.52 vs $1.48)
  Impact: Confirms strong iPhone demand highlighted in research

NVDA (⬆️ +5.2% this week):
• Nov 8: New H100 chip orders from major cloud providers
  Impact: Validates continued AI infrastructure spending

Market Context:
• S&P 500: +1.2% this week
• 10Y Treasury: 4.35% (down 5 bps)
• Tech sector outperforming (+2.8%)
```

---

### 3.5 Salesforce Agent

**Role**: CRM data retrieval and synthesis

**System Prompt**:
```
You are a CRM specialist. Given a household ID:

1. Retrieve recent notes and interactions
2. Identify open tasks and opportunities
3. Note any upcoming events (reviews, rebalancing)
4. Highlight relationship context (tenure, preferences)
5. Flag any outstanding action items

Focus on information that will help the FA have a productive conversation.
```

**Tools**:
```python
@tool
def get_salesforce_notes(
    household_id: str,
    days_back: int = 90
) -> list:
    """Retrieve recent notes and interactions from Salesforce.

    Returns:
        [
            {
                "date": "2025-10-15",
                "author": "FA-001",
                "note_type": "phone_call",
                "content": "Client expressed interest in ESG investments",
                "tags": ["esg", "portfolio_review"]
            }
        ]
    """
    # Salesforce API call
    sf = Salesforce(...)
    query = f"""
        SELECT Id, CreatedDate, Body, Type
        FROM Note
        WHERE Account.HouseholdId = '{household_id}'
        AND CreatedDate > LAST_N_DAYS:90
    """
    return sf.query(query)

@tool
def get_open_tasks(household_id: str) -> list:
    """Get open tasks/opportunities for household."""

@tool
def get_relationship_history(household_id: str) -> dict:
    """Get client tenure, preferences, relationship tier."""
```

**Output Format**:
```
CRM Context for [Household Name]:

Relationship Details:
• Client since: 2018 (7 years)
• Relationship tier: Platinum ($1M+ AUM)
• Primary contact: John Smith (johnt@email.com)
• Preferred contact: Email

Recent Interactions:
• Oct 15: Phone call - Client interested in ESG investments
• Sep 20: Annual review completed
• Aug 10: Added son as beneficiary

Open Action Items:
• ⚠️ Follow up on ESG fund options (due Nov 15)
• Send updated beneficiary forms for signing
• Schedule Q1 2026 planning meeting

Opportunities:
• Potential $50K rollover from 401(k) (in discussion)
• Estate planning review needed (last done 2022)
```

---

### 3.6 Talking Points Agent

**Role**: Meeting conversation guide generator

**System Prompt**:
```
You are an expert at crafting financial advisor talking points. Given:
- Portfolio summary
- Research findings
- Recent news
- CRM context

Generate 5-7 actionable talking points for the meeting that:

1. Start with the most important items
2. Are specific to this household
3. Include supporting data points
4. Suggest questions to ask the client
5. Highlight opportunities for value-add

Make it easy for the FA to have a productive, relationship-building conversation.
```

**Tools**:
```python
@tool
def generate_talking_points(
    portfolio_summary: str,
    research_findings: str,
    news_summary: str,
    crm_context: str
) -> str:
    """Generate structured talking points using GPT-4."""

    prompt = f"""Given this meeting prep information, generate 5-7 talking points:

    Portfolio: {portfolio_summary}
    Research: {research_findings}
    News: {news_summary}
    CRM: {crm_context}

    Format each talking point with:
    • Main point (1-2 sentences)
    • Supporting data
    • Suggested client question
    • Potential action item
    """

    response = llm.invoke(prompt)
    return response.content

@tool
def identify_risks(portfolio_summary: str) -> list:
    """Flag concentration risks, tax issues, rebalancing needs."""

@tool
def suggest_opportunities(context: dict) -> list:
    """Identify upsell/cross-sell opportunities based on context."""
```

**Output Format**:
```
Meeting Talking Points for [Household Name]:

1. 🎯 Strong Recent Performance (+12.3% YTD)
   "Your portfolio is up 12.3% year-to-date, outpacing the S&P 500 by 2.8%.
   This is driven primarily by your tech holdings (AAPL, MSFT, NVDA)."

   💬 Ask: "How are you feeling about this level of tech exposure?"
   ✅ Action: Consider rebalancing if they're nervous about concentration

2. 🔍 Apple Position Upgraded by Goldman Sachs
   "Goldman Sachs just upgraded Apple to Buy with a $200 price target.
   They're citing strong iPhone demand and accelerating services growth.
   You currently hold $18K in AAPL (25% of portfolio)."

   💬 Ask: "Have you been following Apple's AI announcements?"
   ✅ Action: No immediate action needed, but worth monitoring

3. ⚠️ Follow-up: ESG Investment Interest
   "In our last call (Oct 15), you mentioned interest in ESG funds.
   I've identified 3 options that align with your risk profile and values."

   💬 Ask: "Is this still a priority for you?"
   ✅ Action: Present ESG fund comparison if interested

4. 💼 Potential 401(k) Rollover Opportunity
   "You mentioned a potential $50K rollover. This could provide:
   • More investment options
   • Consolidated management
   • Potential fee savings"

   💬 Ask: "What's the status of your old 401(k)?"
   ✅ Action: Start rollover paperwork if ready

5. 📅 Estate Planning Review (Overdue)
   "Your last estate plan review was in 2022. Given market performance
   and recent beneficiary changes, an update would be valuable."

   💬 Ask: "Any major life changes we should account for?"
   ✅ Action: Schedule estate planning review with specialist
```

---

## 4. Implementation Workflow

### 4.1 Complete Request Flow

```
User Input:
"Prepare me for my meeting with the Johnson household tomorrow"

┌──────────────────────────────────────────────────────────────┐
│ SUPERVISOR RECEIVES REQUEST                                  │
└────────────────┬─────────────────────────────────────────────┘
                 │
                 │ 1. Parse request → household_id = "JOHNSON-001"
                 │ 2. Identify FA → fa_id = "FA-001"
                 │ 3. Extract meeting_date = "2025-11-10"
                 │
                 ▼
┌──────────────────────────────────────────────────────────────┐
│ SUPERVISOR PLANS EXECUTION                                   │
│ Decision: Need portfolio, research, news, CRM, talking points│
└────────────────┬─────────────────────────────────────────────┘
                 │
                 │ Parallel execution (can run concurrently)
                 │
     ┌───────────┼───────────┬───────────┬───────────┐
     │           │           │           │           │
     ▼           ▼           ▼           ▼           ▼
┌─────────┐ ┌─────────┐ ┌─────────┐ ┌──────────┐ (wait)
│Portfolio│ │Research │ │  News   │ │Salesforce│
│ Agent   │ │ Agent   │ │ Agent   │ │  Agent   │
└────┬────┘ └────┬────┘ └────┬────┘ └─────┬────┘
     │           │           │           │
     │ Gets      │ Searches  │ Searches  │ Gets CRM
     │ holdings  │ reports   │ news by   │ notes,
     │ for       │ for AAPL, │ AAPL,     │ tasks,
     │ JOHNSON-  │ MSFT,     │ MSFT,     │ opps
     │ 001       │ NVDA      │ NVDA      │
     │           │           │           │
     └───────────┴───────────┴───────────┘
                 │
                 │ All results returned to supervisor
                 │
                 ▼
┌──────────────────────────────────────────────────────────────┐
│ SUPERVISOR SYNTHESIZES                                       │
│ • Reviews all subagent outputs                               │
│ • Identifies gaps or inconsistencies                         │
│ • Calls talking_points_agent with full context              │
└────────────────┬─────────────────────────────────────────────┘
                 │
                 ▼
           ┌──────────┐
           │ Talking  │
           │ Points   │
           │ Agent    │
           └─────┬────┘
                 │
                 │ Generates 5-7 talking points
                 │
                 ▼
┌──────────────────────────────────────────────────────────────┐
│ SUPERVISOR CREATES FINAL BRIEF                               │
│ • Formats all information into cohesive document             │
│ • Adds executive summary                                     │
│ • Highlights critical action items                           │
│ • Includes appendix with raw data                            │
└────────────────┬─────────────────────────────────────────────┘
                 │
                 ▼
            ┌─────────┐
            │ OUTPUT  │
            │ Meeting │
            │ Brief   │
            └─────────┘
```

### 4.2 Sample Output

```markdown
# Meeting Prep Brief: Johnson Household
**Date**: November 10, 2025
**FA**: John Advisor (FA-001)
**Client**: Johnson Household (Client since 2018)

## Executive Summary
The Johnsons' portfolio is performing well (+12.3% YTD), driven by strong
tech holdings. Recent positive analyst upgrades support current positioning.
Key discussion topics: ESG investment interest (follow-up from Oct call),
potential 401(k) rollover, and overdue estate planning review.

## Portfolio Snapshot
- **Total AUM**: $720,000 (↑ 8.5% in 30 days)
- **# of Accounts**: 3 (Joint Brokerage, IRA, Roth IRA)
- **Top Holdings**: AAPL (25%), MSFT (18%), NVDA (12%)
- **Recent Activity**: Sold SPY, added growth equity last week

## Recent Research & News
- ✅ AAPL upgraded to Buy by Goldman Sachs (PT $200)
- ✅ MSFT seeing strong Azure growth (28% YoY)
- 📰 Apple announced AI chip partnership (Nov 9)
- 📰 NVDA received new H100 orders (Nov 8)

## CRM Context
- **Last Contact**: Oct 15 - Phone call about ESG interests
- **Open Tasks**:
  - ⚠️ Follow up on ESG fund options (due Nov 15)
  - Send beneficiary forms
- **Opportunities**: $50K 401(k) rollover in discussion

## Talking Points
[Full talking points from Talking Points Agent]

## Appendices
[Detailed portfolio holdings, research summaries, news articles]
```

---

## 5. Technical Implementation Plan

### 5.1 Project Structure

```
fa-meeting-prep/
├── src/
│   ├── agents/
│   │   ├── supervisor.py              # Main orchestrator
│   │   ├── portfolio_agent.py         # Holdings analysis
│   │   ├── research_agent.py          # Report search
│   │   ├── news_agent.py              # News aggregation
│   │   ├── salesforce_agent.py        # CRM integration
│   │   └── talking_points_agent.py    # Brief generation
│   │
│   ├── tools/
│   │   ├── portfolio_tools.py         # DB queries for holdings
│   │   ├── research_tools.py          # Vector search reports
│   │   ├── news_tools.py              # News API calls
│   │   ├── salesforce_tools.py        # Salesforce API
│   │   └── generation_tools.py        # LLM-based generation
│   │
│   ├── models/
│   │   ├── state.py                   # State definitions
│   │   ├── schemas.py                 # Pydantic models
│   │   └── database.py                # SQLAlchemy models
│   │
│   ├── graphs/
│   │   └── meeting_prep_graph.py      # Main LangGraph
│   │
│   └── integrations/
│       ├── salesforce.py              # Salesforce client
│       ├── bloomberg.py               # News API client
│       └── vector_store.py            # pgvector wrapper
│
├── tests/
│   ├── test_agents/
│   ├── test_tools/
│   └── test_integration/
│
├── config/
│   ├── agents.yaml                    # Agent configurations
│   ├── tools.yaml                     # Tool definitions
│   └── prompts/                       # Prompt templates
│       ├── supervisor.txt
│       ├── portfolio_agent.txt
│       └── ...
│
├── langgraph.json                     # LangGraph Cloud config
├── pyproject.toml                     # Dependencies
└── README.md
```

### 5.2 Core State Definition

```python
from typing import TypedDict, Annotated, Optional
from langgraph.graph.message import add_messages

class MeetingPrepState(TypedDict):
    """Shared state across all agents"""

    # Input context
    household_id: str
    fa_id: str
    meeting_date: str

    # Conversation
    messages: Annotated[list, add_messages]

    # Subagent results
    portfolio_summary: Optional[str]
    research_findings: Optional[str]
    news_summary: Optional[str]
    crm_context: Optional[str]
    talking_points: Optional[str]

    # Intermediate data (for tool access)
    tickers: Optional[list[str]]  # Extracted from portfolio
    portfolio_data: Optional[dict]  # Raw holdings data

    # Final output
    meeting_brief: Optional[str]
    brief_markdown: Optional[str]
```

### 5.3 Supervisor Implementation

```python
from langchain_anthropic import ChatAnthropic
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.memory import MemorySaver

# Initialize LLM
llm = ChatAnthropic(model="claude-sonnet-4-5-20250929")

# Load supervisor prompt
with open("config/prompts/supervisor.txt") as f:
    supervisor_prompt = f.read()

# Create supervisor agent with subagent tools
supervisor_agent = create_react_agent(
    model=llm,
    tools=[
        analyze_portfolio,      # Wraps portfolio_agent
        gather_research,        # Wraps research_agent
        find_relevant_news,     # Wraps news_agent
        get_salesforce_context, # Wraps salesforce_agent
        generate_talking_points # Wraps talking_points_agent
    ],
    state_schema=MeetingPrepState,
    checkpointer=MemorySaver(),
    system_message=supervisor_prompt
)

# Export for LangGraph Cloud
meeting_prep_graph = supervisor_agent
```

### 5.4 Subagent as Tool Pattern

```python
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI

# Create portfolio subagent
portfolio_llm = ChatOpenAI(model="gpt-4o")

portfolio_subagent = create_react_agent(
    model=portfolio_llm,
    tools=[
        get_household_holdings,
        calculate_returns,
        identify_recent_changes
    ],
    state_schema=PortfolioAgentState,
    system_message=load_prompt("portfolio_agent.txt")
)

# Wrap subagent as a tool for supervisor
@tool
def analyze_portfolio(household_id: str) -> str:
    """Analyze household portfolio holdings, performance, and recent changes.

    Use this when you need comprehensive portfolio information for a household.
    Returns a formatted summary suitable for inclusion in meeting brief.

    Args:
        household_id: The unique identifier for the household

    Returns:
        Formatted portfolio summary with holdings, performance, and insights
    """
    # Invoke portfolio subagent
    result = portfolio_subagent.invoke({
        "household_id": household_id,
        "messages": [
            {"role": "user", "content": f"Analyze portfolio for {household_id}"}
        ]
    })

    # Extract final message
    return result["messages"][-1].content
```

---

## 6. Data Integration Strategy

### 6.1 Database Schema

```sql
-- Core entities
CREATE TABLE households (
    household_id UUID PRIMARY KEY,
    household_name VARCHAR(255),
    fa_id VARCHAR(50),
    total_aum DECIMAL(15,2),
    relationship_tier VARCHAR(50),
    client_since DATE
);

CREATE TABLE accounts (
    account_id UUID PRIMARY KEY,
    household_id UUID REFERENCES households,
    account_name VARCHAR(255),
    account_type VARCHAR(50), -- brokerage, ira, roth_ira
    current_value DECIMAL(15,2)
);

CREATE TABLE holdings (
    holding_id UUID PRIMARY KEY,
    account_id UUID REFERENCES accounts,
    ticker VARCHAR(10),
    shares DECIMAL(15,4),
    cost_basis DECIMAL(15,2),
    current_price DECIMAL(15,2),
    purchase_date DATE,
    last_updated TIMESTAMP
);

-- Vector store for reports
CREATE TABLE research_reports (
    report_id UUID PRIMARY KEY,
    ticker VARCHAR(10),
    title TEXT,
    source VARCHAR(100),
    report_date DATE,
    content TEXT,
    embedding vector(1536),  -- pgvector
    metadata JSONB
);

CREATE INDEX ON research_reports
USING hnsw (embedding vector_cosine_ops);
```

### 6.2 External API Integrations

```python
# Salesforce integration
class SalesforceClient:
    def __init__(self):
        self.sf = Salesforce(
            username=os.getenv("SF_USERNAME"),
            password=os.getenv("SF_PASSWORD"),
            security_token=os.getenv("SF_TOKEN")
        )

    def get_household_notes(self, household_id: str, days: int = 90):
        query = f"""
            SELECT Id, CreatedDate, Body, CreatedBy.Name
            FROM Note
            WHERE Account.HouseholdId__c = '{household_id}'
            AND CreatedDate > LAST_N_DAYS:{days}
            ORDER BY CreatedDate DESC
        """
        return self.sf.query(query)

# Bloomberg/Reuters news
class NewsClient:
    def __init__(self):
        self.bloomberg_api = Bloomberg(api_key=os.getenv("BLOOMBERG_KEY"))

    def search_news(self, tickers: list[str], days: int = 7):
        results = []
        for ticker in tickers:
            articles = self.bloomberg_api.search(
                query=ticker,
                start_date=(datetime.now() - timedelta(days=days)),
                categories=["earnings", "ma", "regulatory"]
            )
            results.extend(articles)
        return results

# Internal report storage (S3)
class ReportStorage:
    def __init__(self):
        self.s3 = boto3.client('s3')

    def search_reports(self, tickers: list[str]):
        # Search by tags/metadata
        pass
```

---

## 7. LangSmith Integration

### 7.1 Tracing Setup

```python
import os
from langsmith import traceable

# Enable tracing
os.environ["LANGCHAIN_TRACING_V2"] = "true"
os.environ["LANGCHAIN_API_KEY"] = "lsv2_pt_..."
os.environ["LANGCHAIN_PROJECT"] = "fa-meeting-prep"

# Trace all agent invocations
@traceable(name="supervisor_agent")
def run_supervisor(household_id: str, fa_id: str):
    result = supervisor_agent.invoke({
        "household_id": household_id,
        "fa_id": fa_id,
        "messages": [{"role": "user", "content": "Prepare meeting brief"}]
    })
    return result

# Trace individual tool calls
@traceable(name="portfolio_tool")
@tool
def get_household_holdings(household_id: str):
    # Implementation
    pass
```

### 7.2 Custom Metrics

```python
from langsmith import Client

client = Client()

# Log custom metrics
def log_meeting_prep_metrics(run_id: str, metrics: dict):
    client.create_feedback(
        run_id=run_id,
        key="meeting_prep_quality",
        score=metrics["quality_score"],
        comment=f"""
        Completeness: {metrics["completeness"]}/5
        Relevance: {metrics["relevance"]}/5
        Actionability: {metrics["actionability"]}/5
        """
    )

# Log user feedback
def log_fa_feedback(run_id: str, rating: int, comments: str):
    client.create_feedback(
        run_id=run_id,
        key="fa_satisfaction",
        score=rating,
        comment=comments
    )
```

### 7.3 LangSmith Dashboard Monitoring

Track key metrics:
- **Latency**: Total time to generate meeting brief
- **Token Usage**: Across all agents and LLM calls
- **Success Rate**: Briefs generated without errors
- **Agent Usage**: Which subagents are called most frequently
- **User Ratings**: FA feedback on brief quality

---

## 8. LangGraph Cloud Deployment

### 8.1 langgraph.json Configuration

```json
{
  "dependencies": ["."],
  "graphs": {
    "meeting_prep": "./src/graphs/meeting_prep_graph.py:meeting_prep_graph"
  },
  "env": ".env",
  "python_version": "3.11",
  "workflows": {
    "scheduled_reports": {
      "graph": "meeting_prep",
      "cron": "0 6 * * *",
      "description": "Generate morning meeting prep reports"
    }
  }
}
```

### 8.2 Deployment Commands

```bash
# Install LangGraph CLI
pip install langgraph-cli

# Test locally
langgraph dev

# Deploy to cloud
langgraph deploy

# Create API
langgraph cloud api create \
  --name "meeting-prep-api" \
  --graph "meeting_prep"

# Configure auth
langgraph cloud auth configure \
  --api-key $LANGCHAIN_API_KEY
```

### 8.3 Cloud API Usage

```python
from langgraph_sdk import get_client

# Initialize client
client = get_client(url="https://fa-meeting-prep.langchain.app")

# Create thread
thread = client.threads.create()

# Run meeting prep
response = client.runs.create(
    thread_id=thread["thread_id"],
    graph_id="meeting_prep",
    input={
        "household_id": "JOHNSON-001",
        "fa_id": "FA-001",
        "meeting_date": "2025-11-10"
    }
)

# Stream results
for chunk in client.runs.stream(
    thread_id=thread["thread_id"],
    run_id=response["run_id"]
):
    print(chunk)

# Get final result
final_state = client.threads.get_state(thread["thread_id"])
meeting_brief = final_state["values"]["meeting_brief"]
```

---

## 9. Implementation Phases

### Phase 1: Foundation (Weeks 1-2)

**Goal**: Set up core infrastructure and one working subagent

**Deliverables**:
- ✅ Project scaffold with structure
- ✅ Database schema and seed data
- ✅ PostgreSQL + pgvector setup
- ✅ LangSmith integration configured
- ✅ Portfolio Agent + tools implemented
- ✅ Basic supervisor that can call portfolio agent
- ✅ Unit tests for portfolio tools

**Success Criteria**:
- Can query household holdings from database
- Portfolio agent returns formatted summary
- LangSmith shows traces for all LLM calls

### Phase 2: Remaining Subagents (Weeks 3-4)

**Goal**: Implement all 5 subagents with their tools

**Deliverables**:
- ✅ Research Agent (vector search reports)
- ✅ News Agent (API integration)
- ✅ Salesforce Agent (CRM integration)
- ✅ Talking Points Agent (generation)
- ✅ All tools unit tested
- ✅ Integration tests for each agent

**Success Criteria**:
- Each agent works independently
- Tools return expected data formats
- All agents traced in LangSmith

### Phase 3: Supervisor Integration (Week 5)

**Goal**: Wire all subagents to supervisor orchestrator

**Deliverables**:
- ✅ Supervisor prompt engineering
- ✅ Subagent-as-tool wrappers
- ✅ End-to-end graph execution
- ✅ Brief formatting and synthesis logic
- ✅ Error handling and fallbacks

**Success Criteria**:
- Supervisor successfully coordinates all 5 agents
- Complete meeting brief generated
- Handles missing data gracefully

### Phase 4: Polish & Testing (Week 6)

**Goal**: Production-ready quality

**Deliverables**:
- ✅ Comprehensive test suite
- ✅ Performance optimization (caching, parallel calls)
- ✅ Output formatting improvements
- ✅ User feedback collection mechanism
- ✅ Documentation and examples

**Success Criteria**:
- <30 second end-to-end latency
- 95%+ success rate on test cases
- Positive feedback from pilot FAs

### Phase 5: LangGraph Cloud Deployment (Week 7)

**Goal**: Production deployment

**Deliverables**:
- ✅ LangGraph Cloud configuration
- ✅ API endpoints deployed
- ✅ Authentication and authorization
- ✅ Monitoring dashboards
- ✅ Rate limiting and cost controls

**Success Criteria**:
- API accessible via HTTPS
- LangSmith dashboards showing metrics
- Production traffic handling successfully

---

## 10. Migration from Current System

### What to Reuse

**✅ Keep:**
- Database schema (stocks, holdings, accounts, summaries)
- pgvector setup and embeddings
- Report ingestion pipelines
- Fact-checking validation logic (adapt for tools)
- UI components (can reuse React components)

**🔄 Adapt:**
- Summary generation → becomes Talking Points Agent
- EDO context retrieval → becomes Research Agent tools
- Query classifier → supervisor routing logic
- Guardrails → add as middleware to tools

**🗑️ Replace:**
- Current graph architecture (too coupled)
- Batch processing (not needed for real-time prep)
- Phase2 validation graph (overkill for this use case)

### Data Migration

```python
# Existing data is compatible!
# Just need to map to new schema

# Map existing stocks/holdings → households
def create_households():
    with db.session() as session:
        clients = session.query(Client).all()
        for client in clients:
            household = Household(
                household_id=client.client_id,
                household_name=client.name,
                fa_id=client.advisor.fa_id,
                total_aum=sum(h.market_value for h in client.holdings),
                client_since=client.created_at
            )
            session.add(household)
        session.commit()

# Existing stock_summaries become research reports
# Existing vector embeddings can be reused
```

---

## 11. Cost Analysis

### Per Meeting Prep Request

**LLM Costs** (assuming Claude Sonnet 3.5 + GPT-4o):

| Component | Model | Input Tokens | Output Tokens | Cost |
|-----------|-------|--------------|---------------|------|
| Supervisor (routing) | Sonnet 3.5 | 1,000 | 500 | $0.005 |
| Portfolio Agent | GPT-4o | 2,000 | 800 | $0.028 |
| Research Agent | GPT-4o | 5,000 | 1,000 | $0.060 |
| News Agent | GPT-4o | 3,000 | 800 | $0.038 |
| Salesforce Agent | GPT-4o | 2,000 | 600 | $0.026 |
| Talking Points | Sonnet 3.5 | 8,000 | 2,000 | $0.034 |
| Supervisor (synthesis) | Sonnet 3.5 | 10,000 | 3,000 | $0.042 |
| **Total per brief** | | **31,000** | **7,700** | **$0.233** |

**Monthly Costs** (200 households, 2 meetings/month avg):
- Meeting preps: 400 * $0.23 = **$92/month**
- Database: $50/month (PostgreSQL + pgvector)
- LangGraph Cloud: $100/month (Starter tier)
- External APIs: $150/month (Bloomberg, Salesforce)
- **Total: ~$392/month** or **$4,704/year**

**ROI**: If saves 55 minutes per meeting prep:
- 400 meetings/month * 55 min = 22,000 minutes saved
- 367 hours saved per month
- At $100/hour advisor rate = **$36,700/month value**
- **ROI: 93x**

---

## 12. Success Metrics

### Technical Metrics

- **Latency**: <30 seconds end-to-end (P95)
- **Success Rate**: >95% (meeting brief generated)
- **Token Efficiency**: <50K total tokens per request
- **Tool Accuracy**: >90% (tools return valid data)
- **LangSmith Traces**: 100% coverage

### Business Metrics

- **Time Saved**: 55+ minutes per meeting prep
- **FA Adoption**: >80% of target FAs using within 3 months
- **Usage Frequency**: 8+ briefs per FA per month
- **FA Satisfaction**: >4.5/5 rating
- **Client Meeting Quality**: Measured by post-meeting surveys

### Quality Metrics

- **Completeness**: All relevant data sources checked
- **Relevance**: >90% of talking points deemed useful by FA
- **Actionability**: >3 concrete action items per brief
- **Accuracy**: <5% factual errors (validated by FAs)
- **Personalization**: >80% of brief specific to household

---

## 13. Risk Mitigation

### Technical Risks

| Risk | Mitigation |
|------|------------|
| LLM hallucinations | Fact-checking middleware, citation requirements |
| API failures | Fallback data sources, graceful degradation |
| Slow response times | Caching, parallel agent execution, timeout handling |
| Token limits exceeded | Chunking strategies, summarization |
| Cost overruns | Rate limiting, budget alerts, model selection |

### Business Risks

| Risk | Mitigation |
|------|------------|
| Low FA adoption | User training, gradual rollout, feedback loop |
| Inaccurate briefs | Human-in-loop validation, confidence scoring |
| Compliance issues | Audit trails, data retention policies |
| Data privacy concerns | Encryption, access controls, compliance review |
| Over-reliance on AI | Emphasize AI as assistant, not replacement |

---

## 14. Next Steps

### Immediate Actions

1. **Stakeholder Alignment**
   - Review plan with product, engineering, compliance
   - Get FA input on talking points format
   - Validate data access (Salesforce API, Bloomberg)

2. **Proof of Concept** (Week 1)
   - Build minimal supervisor + portfolio agent
   - Generate one meeting brief end-to-end
   - Demo to stakeholders for feedback

3. **Technical Setup** (Week 1)
   - Provision LangGraph Cloud account
   - Set up LangSmith project
   - Configure database and pgvector
   - Scaffold project structure

4. **Phase 1 Kickoff** (Week 2)
   - Begin portfolio agent + tools implementation
   - Set up CI/CD pipeline
   - Write initial tests

### Long-Term Vision

- **Multi-modal briefs**: Voice summaries, interactive dashboards
- **Proactive insights**: Alert FAs to portfolio risks automatically
- **Client-facing version**: Meeting summaries for clients
- **Scalability**: Expand to 1000+ households
- **Continuous learning**: Fine-tune agents based on FA feedback

---

## 15. Appendix: Code Examples

### Full Supervisor Implementation

```python
# src/graphs/meeting_prep_graph.py

from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.memory import MemorySaver
from langchain_anthropic import ChatAnthropic
from typing import TypedDict, Annotated, Optional
from langgraph.graph.message import add_messages
import os

# Import all subagent tools
from src.agents.portfolio_agent import analyze_portfolio
from src.agents.research_agent import gather_research
from src.agents.news_agent import find_relevant_news
from src.agents.salesforce_agent import get_salesforce_context
from src.agents.talking_points_agent import generate_talking_points

# State definition
class MeetingPrepState(TypedDict):
    household_id: str
    fa_id: str
    meeting_date: str
    messages: Annotated[list, add_messages]
    portfolio_summary: Optional[str]
    research_findings: Optional[str]
    news_summary: Optional[str]
    crm_context: Optional[str]
    talking_points: Optional[str]
    meeting_brief: Optional[str]

# Initialize LLM
llm = ChatAnthropic(
    model="claude-sonnet-4-5-20250929",
    temperature=0,
    max_tokens=4000
)

# Load supervisor prompt
SUPERVISOR_PROMPT = """You are a meeting preparation coordinator for financial advisors.

Your job is to gather information from specialized agents and create a comprehensive
meeting brief. Available agents:

1. analyze_portfolio: Get household holdings, performance, recent changes
2. gather_research: Find relevant analyst research for held securities
3. find_relevant_news: Surface recent market news impacting the portfolio
4. get_salesforce_context: Retrieve CRM notes, tasks, opportunities
5. generate_talking_points: Create FA-ready conversation starters

Process:
1. Call analyze_portfolio first to understand what securities are held
2. Use the ticker list to call gather_research and find_relevant_news
3. Get CRM context with get_salesforce_context
4. Once you have all information, call generate_talking_points
5. Synthesize everything into a well-formatted meeting brief

Always call the agents in this order. Do not try to answer directly."""

# Create supervisor agent
meeting_prep_graph = create_react_agent(
    model=llm,
    tools=[
        analyze_portfolio,
        gather_research,
        find_relevant_news,
        get_salesforce_context,
        generate_talking_points
    ],
    state_schema=MeetingPrepState,
    checkpointer=MemorySaver(),
    system_message=SUPERVISOR_PROMPT
)

# Enable LangSmith tracing
os.environ["LANGCHAIN_TRACING_V2"] = "true"
os.environ["LANGCHAIN_PROJECT"] = "fa-meeting-prep"
```

### Sample Subagent Implementation

```python
# src/agents/portfolio_agent.py

from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent
from langchain_core.tools import tool
from typing import TypedDict, Optional
import json

# Portfolio agent tools
@tool
def get_household_holdings(household_id: str) -> str:
    """Retrieve all holdings across all accounts for a household."""
    from src.integrations.database import db_manager

    with db_manager.get_session() as session:
        holdings = session.execute("""
            SELECT
                a.account_name,
                h.ticker,
                s.company_name,
                h.shares,
                h.cost_basis,
                s.current_price,
                (h.shares * s.current_price) as market_value,
                ((s.current_price - h.cost_basis) / h.cost_basis * 100) as gain_pct
            FROM holdings h
            JOIN accounts a ON h.account_id = a.account_id
            JOIN stocks s ON h.ticker = s.ticker
            WHERE a.household_id = :household_id
            ORDER BY market_value DESC
        """, {"household_id": household_id}).fetchall()

        return json.dumps([dict(row) for row in holdings], indent=2)

@tool
def calculate_returns(household_id: str, period_days: int = 30) -> str:
    """Calculate portfolio returns over specified period."""
    # Implementation
    pass

@tool
def identify_recent_changes(household_id: str, days: int = 7) -> str:
    """Find recent trades for the household."""
    # Implementation
    pass

# Portfolio agent state
class PortfolioState(TypedDict):
    household_id: str
    messages: list
    holdings_data: Optional[str]
    returns_data: Optional[str]
    changes_data: Optional[str]

# Portfolio agent prompt
PORTFOLIO_PROMPT = """You are a portfolio analysis expert.

Given a household ID, analyze their holdings:

1. Get all holdings with get_household_holdings
2. Calculate returns with calculate_returns (30-day default)
3. Check recent changes with identify_recent_changes (7-day default)

Create a concise summary covering:
- Total AUM and account breakdown
- Top 5 holdings with allocations
- Performance (30-day and YTD if available)
- Recent activity (buys/sells)
- Any concentration risks (>15% single position)

Format your output as structured text suitable for a meeting brief."""

# Create portfolio agent
portfolio_llm = ChatOpenAI(model="gpt-4o", temperature=0)

portfolio_agent = create_react_agent(
    model=portfolio_llm,
    tools=[
        get_household_holdings,
        calculate_returns,
        identify_recent_changes
    ],
    state_schema=PortfolioState,
    system_message=PORTFOLIO_PROMPT
)

# Wrap as tool for supervisor
@tool
def analyze_portfolio(household_id: str) -> str:
    """Analyze household portfolio holdings, performance, and recent changes."""
    result = portfolio_agent.invoke({
        "household_id": household_id,
        "messages": [
            {"role": "user", "content": f"Analyze portfolio for {household_id}"}
        ]
    })
    return result["messages"][-1].content
```

---

## Conclusion

This plan provides a comprehensive roadmap for rebuilding the FA AI system using LangGraph's supervisor pattern. The new architecture:

✅ **Meets all requirements**: Supervisor + subagents, tools, LangSmith, LangGraph Cloud
✅ **Solves the real problem**: Reduces meeting prep from 60+ to <5 minutes
✅ **Scales effectively**: 200 households, 30+ reports, multiple data sources
✅ **Production-ready**: Error handling, monitoring, cost controls
✅ **Maintainable**: Clear separation of concerns, testable components

**Next Step**: Schedule stakeholder review and proceed with Phase 1 POC.
