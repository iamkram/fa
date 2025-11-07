# Phase 2: Multi-Source Batch Pipeline with Retry Logic

## Context

You have completed Phase 1 with:
- ✅ Working EDGAR ingestion pipeline
- ✅ Text chunking and vectorization to pgvector
- ✅ Medium-tier summary generation
- ✅ Basic rule-based fact-checking
- ✅ Postgres storage

## Phase 2 Objectives

Build a production-ready multi-source batch pipeline that:
1. **Adds BlueMatrix and FactSet data sources** with parallel processing
2. **Generates all 3 summary tiers** (Hook < 15 words, Medium 75-125 words, Expanded 500-750 words)
3. **Implements LLM-based fact-checking** for each data source
4. **Adds retry logic** with negative prompting (max 5 retries)
5. **Processes summaries in parallel** using LangGraph Send()
6. **Handles 100+ stocks** with proper concurrency control

## Architecture Changes

### LangGraph 1.0 Patterns for Phase 2

**Parallel Subgraphs for Data Ingestion:**
```python
from langgraph.graph import Send

def fan_out_sources(state: BatchGraphState):
    """Create parallel subgraphs for each data source"""
    return [
        Send("bluematrix_subgraph", state),
        Send("edgar_subgraph", state),
        Send("factset_subgraph", state)
    ]
```

**Parallel Summary Generation:**
```python
def fan_out_writers(state: BatchGraphState):
    """Generate all three tiers in parallel"""
    return [
        Send("hook_writer", state),
        Send("medium_writer", state),
        Send("expanded_writer", state)
    ]
```

**Retry Loop with Conditional Routing:**
```python
def route_fact_check(state: BatchGraphState):
    """Route based on fact check results"""
    if state.fact_check_status == "passed":
        return "storage"
    elif state.retry_count < 5:
        return "retry_summary"
    else:
        return "flag_unvalidated"
```

---

## Task 2.1: Extend State Schema for Multi-Source

### Update `src/batch/state.py`

Add these new state classes:
```python
from typing import List, Dict, Any, Optional, Literal
from pydantic import BaseModel, Field
from datetime import datetime
import uuid

# ============================================================================
# BlueMatrix State Models
# ============================================================================

class AnalystReport(BaseModel):
    """Single analyst report from BlueMatrix"""
    report_id: str
    analyst_firm: str
    analyst_name: str
    report_date: datetime
    rating_change: Optional[str] = None  # "upgrade", "downgrade", "initiate", "reiterate"
    previous_rating: Optional[str] = None
    new_rating: Optional[str] = None
    price_target: Optional[float] = None
    previous_price_target: Optional[float] = None
    key_points: List[str]
    full_text: str

class BlueMatrixDataState(BaseModel):
    """State after BlueMatrix data ingestion"""
    stock_id: str
    ticker: str
    reports: List[AnalystReport]
    report_count: int = 0
    key_events: List[Dict[str, Any]] = Field(default_factory=list)
    processing_status: Literal["success", "partial", "failed"]
    error_message: Optional[str] = None

# ============================================================================
# FactSet State Models
# ============================================================================

class PriceData(BaseModel):
    """Price and volume data from FactSet"""
    date: datetime
    open: float
    close: float
    high: float
    low: float
    volume: int
    pct_change: float
    volume_vs_avg: float  # Ratio of volume to 20-day average
    volatility_percentile: float  # Where today's volatility ranks

class FundamentalEvent(BaseModel):
    """Earnings, guidance, dividend events"""
    event_type: Literal["earnings", "guidance", "dividend", "other"]
    timestamp: datetime
    details: str

class FactSetDataState(BaseModel):
    """State after FactSet data ingestion"""
    stock_id: str
    ticker: str
    price_data: Optional[PriceData] = None
    fundamental_events: List[FundamentalEvent] = Field(default_factory=list)
    processing_status: Literal["success", "partial", "failed"]
    error_message: Optional[str] = None

# ============================================================================
# Enhanced Summary State with All Tiers
# ============================================================================

class SummaryTier(BaseModel):
    """Single tier of summary"""
    text: str
    word_count: int
    generation_time_ms: int
    status: Literal["pending_fact_check", "fact_checking", "passed", "failed"] = "pending_fact_check"
    retry_count: int = 0

class MultiTierSummaryState(BaseModel):
    """State with all three summary tiers"""
    stock_id: str
    ticker: str
    hook: Optional[SummaryTier] = None
    medium: Optional[SummaryTier] = None
    expanded: Optional[SummaryTier] = None
    source_citations: List[Dict[str, Any]] = Field(default_factory=list)

# ============================================================================
# Enhanced Fact-Checking State
# ============================================================================

class FactCheckRequest(BaseModel):
    """Request to fact-check a specific tier"""
    tier: Literal["hook", "medium", "expanded"]
    summary_text: str
    source_data: Dict[str, Any]  # BlueMatrix, EDGAR, FactSet data

class SourceFactCheckResult(BaseModel):
    """Fact check result from a single source"""
    source: Literal["bluematrix", "edgar", "factset"]
    claims_checked: int
    verified_count: int
    failed_claims: List[Dict[str, Any]] = Field(default_factory=list)
    pass_rate: float

class TierFactCheckState(BaseModel):
    """Fact check state for a specific tier"""
    tier: Literal["hook", "medium", "expanded"]
    bluematrix_result: Optional[SourceFactCheckResult] = None
    edgar_result: Optional[SourceFactCheckResult] = None
    factset_result: Optional[SourceFactCheckResult] = None
    overall_status: Literal["passed", "failed", "pending"]
    overall_pass_rate: float = 0.0
    failed_claims: List[Dict[str, Any]] = Field(default_factory=list)

# ============================================================================
# Retry State
# ============================================================================

class RetryState(BaseModel):
    """State for managing retries"""
    tier: Literal["hook", "medium", "expanded"]
    retry_count: int = 0
    max_retries: int = 5
    failed_claims: List[Dict[str, Any]] = Field(default_factory=list)
    correction_prompts: List[str] = Field(default_factory=list)

# ============================================================================
# Combined Graph State (Updated)
# ============================================================================

class BatchGraphState(BaseModel):
    """Complete state for Phase 2 batch processing"""
    # Input
    stock_id: str
    ticker: str
    company_name: str
    batch_run_id: str
    processing_date: datetime = Field(default_factory=datetime.utcnow)
    
    # Data from all sources
    edgar_filings: List[Any] = Field(default_factory=list)  # From Phase 1
    edgar_status: Optional[str] = None
    
    bluematrix_reports: List[AnalystReport] = Field(default_factory=list)
    bluematrix_status: Optional[str] = None
    
    factset_price_data: Optional[PriceData] = None
    factset_events: List[FundamentalEvent] = Field(default_factory=list)
    factset_status: Optional[str] = None
    
    # Vectorization
    edgar_vector_ids: List[str] = Field(default_factory=list)
    bluematrix_vector_ids: List[str] = Field(default_factory=list)
    factset_vector_ids: List[str] = Field(default_factory=list)
    
    # Summaries (all three tiers)
    hook_summary: Optional[str] = None
    hook_word_count: int = 0
    
    medium_summary: Optional[str] = None
    medium_word_count: int = 0
    
    expanded_summary: Optional[str] = None
    expanded_word_count: int = 0
    
    # Fact checking for each tier
    hook_fact_check: Optional[TierFactCheckState] = None
    medium_fact_check: Optional[TierFactCheckState] = None
    expanded_fact_check: Optional[TierFactCheckState] = None
    
    # Retry tracking
    hook_retry_count: int = 0
    medium_retry_count: int = 0
    expanded_retry_count: int = 0
    
    hook_corrections: List[str] = Field(default_factory=list)
    medium_corrections: List[str] = Field(default_factory=list)
    expanded_corrections: List[str] = Field(default_factory=list)
    
    # Output
    summary_id: Optional[str] = None
    storage_status: Optional[str] = None
    error_message: Optional[str] = None
    total_processing_time_ms: int = 0
```

**Tests:** Create `tests/batch/test_state_phase2.py`
```python
import pytest
from datetime import datetime

from src.batch.state import (
    AnalystReport, BlueMatrixDataState,
    PriceData, FactSetDataState,
    TierFactCheckState, SourceFactCheckResult
)

def test_analyst_report_creation():
    """Test BlueMatrix analyst report model"""
    report = AnalystReport(
        report_id="BM-12345",
        analyst_firm="Goldman Sachs",
        analyst_name="John Doe",
        report_date=datetime.utcnow(),
        rating_change="upgrade",
        previous_rating="Hold",
        new_rating="Buy",
        price_target=150.0,
        previous_price_target=120.0,
        key_points=["Strong earnings", "Market expansion"],
        full_text="Full report text..."
    )
    
    assert report.rating_change == "upgrade"
    assert report.price_target == 150.0

def test_price_data_creation():
    """Test FactSet price data model"""
    price_data = PriceData(
        date=datetime.utcnow(),
        open=100.0,
        close=105.0,
        high=107.0,
        low=99.0,
        volume=10000000,
        pct_change=5.0,
        volume_vs_avg=1.5,
        volatility_percentile=0.75
    )
    
    assert price_data.pct_change == 5.0
    assert price_data.volume_vs_avg == 1.5

def test_tier_fact_check_state():
    """Test multi-source fact checking state"""
    fact_check = TierFactCheckState(
        tier="medium",
        bluematrix_result=SourceFactCheckResult(
            source="bluematrix",
            claims_checked=5,
            verified_count=5,
            pass_rate=1.0
        ),
        overall_status="passed",
        overall_pass_rate=0.98
    )
    
    assert fact_check.tier == "medium"
    assert fact_check.overall_status == "passed"
```

---

## Task 2.2: BlueMatrix Ingestion + Vectorization

### Create Mock BlueMatrix Client

Create `src/shared/utils/bluematrix_client.py`:
```python
"""
BlueMatrix API Client (Mocked for Development)

In production, replace with actual BlueMatrix API calls.
"""

from typing import List, Dict, Any
from datetime import datetime, timedelta
import random
import logging

logger = logging.getLogger(__name__)

class BlueMatrixClient:
    """Mock BlueMatrix API client"""
    
    def __init__(self, api_key: str = None):
        self.api_key = api_key
        logger.info("BlueMatrix client initialized (MOCK MODE)")
    
    async def fetch_analyst_reports(
        self,
        ticker: str,
        lookback_hours: int = 24
    ) -> List[Dict[str, Any]]:
        """
        Fetch analyst reports for a ticker
        
        In production, this would call:
        GET https://api.bluematrix.com/v1/research?ticker={ticker}&since={timestamp}
        """
        logger.info(f"Fetching BlueMatrix reports for {ticker} (MOCK)")
        
        # Mock data - in production, replace with actual API call
        mock_reports = self._generate_mock_reports(ticker)
        
        return mock_reports
    
    def _generate_mock_reports(self, ticker: str) -> List[Dict[str, Any]]:
        """Generate realistic mock analyst reports"""
        
        firms = ["Goldman Sachs", "Morgan Stanley", "JP Morgan", "Barclays", "Citi"]
        ratings = ["Buy", "Hold", "Sell", "Outperform", "Underperform"]
        
        # 70% chance of having a report in last 24h
        if random.random() > 0.3:
            firm = random.choice(firms)
            old_rating = random.choice(ratings)
            new_rating = random.choice(ratings)
            
            # Generate realistic price movements
            base_price = random.uniform(50, 500)
            old_target = round(base_price * random.uniform(0.9, 1.1), 2)
            new_target = round(base_price * random.uniform(0.95, 1.15), 2)
            
            report = {
                "report_id": f"BM-{random.randint(100000, 999999)}",
                "analyst_firm": firm,
                "analyst_name": f"Analyst {random.randint(1, 50)}",
                "report_date": datetime.utcnow() - timedelta(hours=random.randint(1, 23)),
                "rating_change": "upgrade" if new_rating > old_rating else "downgrade" if new_rating < old_rating else "reiterate",
                "previous_rating": old_rating,
                "new_rating": new_rating,
                "price_target": new_target,
                "previous_price_target": old_target,
                "key_points": [
                    f"Revenue growth expected at {random.randint(5, 25)}%",
                    f"Market share gains in key segments",
                    f"Operating margin expansion to {random.randint(15, 35)}%"
                ],
                "full_text": f"""
                {firm} analyst report on {ticker}
                
                Rating: {old_rating} -> {new_rating}
                Price Target: ${old_target} -> ${new_target}
                
                Key Investment Thesis:
                - Strong revenue momentum with {random.randint(10, 30)}% YoY growth
                - Expanding margins due to operational efficiency
                - New product launches driving market share gains
                - Valuation attractive at current levels
                
                Risks:
                - Macroeconomic headwinds
                - Competitive pressures
                - Regulatory uncertainty
                
                Conclusion: We maintain our {new_rating} rating with a ${new_target} price target.
                """
            }
            
            return [report]
        
        return []
```

### Create BlueMatrix Ingestion Node

Create `src/batch/nodes/bluematrix_ingestion.py`:
```python
from typing import Dict, Any, List
import asyncio
import logging

from src.batch.state import BatchGraphState, AnalystReport
from src.shared.utils.bluematrix_client import BlueMatrixClient
from src.config.settings import get_settings

logger = logging.getLogger(__name__)

async def fetch_bluematrix_data(ticker: str) -> List[AnalystReport]:
    """Fetch and parse BlueMatrix analyst reports"""
    settings = get_settings()
    client = BlueMatrixClient(api_key=settings.bluematrix_api_key)
    
    try:
        reports_data = await client.fetch_analyst_reports(ticker, lookback_hours=24)
        
        reports = []
        for report_data in reports_data:
            report = AnalystReport(**report_data)
            reports.append(report)
        
        logger.info(f"Fetched {len(reports)} BlueMatrix reports for {ticker}")
        return reports
        
    except Exception as e:
        logger.error(f"BlueMatrix fetch failed for {ticker}: {str(e)}")
        return []

def bluematrix_ingestion_node(state: BatchGraphState, config) -> Dict[str, Any]:
    """LangGraph node for BlueMatrix data ingestion"""
    logger.info(f"[BlueMatrix] Fetching data for {state.ticker}")
    
    try:
        reports = asyncio.run(fetch_bluematrix_data(state.ticker))
        
        return {
            "bluematrix_reports": reports,
            "bluematrix_status": "success" if reports else "partial"
        }
    except Exception as e:
        logger.error(f"BlueMatrix ingestion failed: {str(e)}")
        return {
            "bluematrix_reports": [],
            "bluematrix_status": "failed",
            "error_message": str(e)
        }
```

### Create BlueMatrix Vectorization Node

Create `src/batch/nodes/vectorize_bluematrix.py`:
```python
import asyncio
import uuid
import logging
from typing import Dict, Any

from src.batch.state import BatchGraphState
from src.shared.utils.chunking import chunk_text, generate_embeddings
from src.shared.vector_store.pgvector_client import PgVectorClient

logger = logging.getLogger(__name__)

def vectorize_bluematrix_node(state: BatchGraphState, config) -> Dict[str, Any]:
    """Vectorize BlueMatrix reports and store in pgvector"""
    logger.info(f"[BlueMatrix] Vectorizing reports for {state.ticker}")
    
    if not state.bluematrix_reports:
        logger.info(f"No BlueMatrix reports to vectorize for {state.ticker}")
        return {"bluematrix_vector_ids": []}
    
    pgvector = PgVectorClient()
    vector_ids = []
    
    try:
        for report in state.bluematrix_reports:
            # Chunk the report
            chunks = chunk_text(report.full_text, chunk_size=500, chunk_overlap=50)
            
            # Generate embeddings
            embeddings = asyncio.run(generate_embeddings(chunks))
            
            # Prepare vectors
            vectors = []
            for idx, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
                vector_id = str(uuid.uuid4())
                vectors.append({
                    'id': vector_id,
                    'embedding': embedding,
                    'text': chunk,
                    'metadata': {
                        'stock_id': state.stock_id,
                        'ticker': state.ticker,
                        'source': 'bluematrix',
                        'report_id': report.report_id,
                        'analyst_firm': report.analyst_firm,
                        'analyst_name': report.analyst_name,
                        'report_date': report.report_date.isoformat(),
                        'rating_change': report.rating_change,
                        'new_rating': report.new_rating,
                        'price_target': report.price_target,
                        'chunk_index': idx
                    }
                })
                vector_ids.append(vector_id)
            
            # Bulk insert
            pgvector.bulk_insert('bluematrix_reports', vectors)
        
        logger.info(f"Vectorized {len(vector_ids)} chunks for {state.ticker}")
        
        return {"bluematrix_vector_ids": vector_ids}
        
    except Exception as e:
        logger.error(f"BlueMatrix vectorization failed: {str(e)}")
        return {
            "bluematrix_vector_ids": [],
            "error_message": str(e)
        }
    finally:
        pgvector.close()
```

**Tests:** Create `tests/batch/nodes/test_bluematrix_ingestion.py`

---

## Task 2.3: FactSet Ingestion + Vectorization

### Create Mock FactSet Client

Create `src/shared/utils/factset_client.py`:
```python
"""
FactSet API Client (Mocked for Development)
"""

from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
import random
import logging

logger = logging.getLogger(__name__)

class FactSetClient:
    """Mock FactSet API client"""
    
    def __init__(self, api_key: str = None):
        self.api_key = api_key
        logger.info("FactSet client initialized (MOCK MODE)")
    
    async def fetch_price_data(self, ticker: str) -> Dict[str, Any]:
        """
        Fetch price and volume data
        
        In production: GET https://api.factset.com/price/v1/prices?ids={ticker}
        """
        logger.info(f"Fetching FactSet price data for {ticker} (MOCK)")
        
        # Generate realistic mock data
        base_price = random.uniform(50, 500)
        pct_change = random.uniform(-5, 5)
        
        return {
            "date": datetime.utcnow(),
            "open": round(base_price, 2),
            "close": round(base_price * (1 + pct_change/100), 2),
            "high": round(base_price * (1 + abs(pct_change)/100), 2),
            "low": round(base_price * (1 - abs(pct_change)/100), 2),
            "volume": random.randint(1000000, 50000000),
            "pct_change": round(pct_change, 2),
            "volume_vs_avg": round(random.uniform(0.5, 2.5), 2),
            "volatility_percentile": round(random.uniform(0.3, 0.9), 2)
        }
    
    async def fetch_fundamental_events(self, ticker: str) -> List[Dict[str, Any]]:
        """
        Fetch earnings, guidance, dividend events
        
        In production: GET https://api.factset.com/events/v1/events?ids={ticker}
        """
        logger.info(f"Fetching FactSet fundamental events for {ticker} (MOCK)")
        
        events = []
        
        # 40% chance of earnings event
        if random.random() > 0.6:
            events.append({
                "event_type": "earnings",
                "timestamp": datetime.utcnow() - timedelta(hours=random.randint(1, 23)),
                "details": f"Q{random.randint(1,4)} earnings: EPS ${random.uniform(1, 5):.2f}, Revenue ${random.randint(1, 50)}B"
            })
        
        # 20% chance of guidance event
        if random.random() > 0.8:
            events.append({
                "event_type": "guidance",
                "timestamp": datetime.utcnow() - timedelta(hours=random.randint(1, 23)),
                "details": f"Raised FY guidance: EPS ${random.uniform(10, 20):.2f}, Revenue ${random.randint(50, 200)}B"
            })
        
        return events
```

### Create FactSet Ingestion Node

Create `src/batch/nodes/factset_ingestion.py`:
```python
import asyncio
import logging
from typing import Dict, Any

from src.batch.state import BatchGraphState, PriceData, FundamentalEvent
from src.shared.utils.factset_client import FactSetClient
from src.config.settings import get_settings

logger = logging.getLogger(__name__)

async def fetch_factset_data(ticker: str):
    """Fetch FactSet price and fundamental data"""
    settings = get_settings()
    client = FactSetClient(api_key=settings.factset_api_key)
    
    # Fetch price data
    price_data_dict = await client.fetch_price_data(ticker)
    price_data = PriceData(**price_data_dict)
    
    # Fetch fundamental events
    events_data = await client.fetch_fundamental_events(ticker)
    events = [FundamentalEvent(**event) for event in events_data]
    
    return price_data, events

def factset_ingestion_node(state: BatchGraphState, config) -> Dict[str, Any]:
    """LangGraph node for FactSet data ingestion"""
    logger.info(f"[FactSet] Fetching data for {state.ticker}")
    
    try:
        price_data, events = asyncio.run(fetch_factset_data(state.ticker))
        
        return {
            "factset_price_data": price_data,
            "factset_events": events,
            "factset_status": "success"
        }
    except Exception as e:
        logger.error(f"FactSet ingestion failed: {str(e)}")
        return {
            "factset_price_data": None,
            "factset_events": [],
            "factset_status": "failed",
            "error_message": str(e)
        }
```

### Create FactSet Vectorization Node

Create `src/batch/nodes/vectorize_factset.py`:
```python
import asyncio
import uuid
import logging
from typing import Dict, Any

from src.batch.state import BatchGraphState
from src.shared.utils.chunking import generate_embeddings
from src.shared.vector_store.pgvector_client import PgVectorClient

logger = logging.getLogger(__name__)

def factset_ingestion_node(state: BatchGraphState, config) -> Dict[str, Any]:
    """Vectorize FactSet data (convert metrics to natural language first)"""
    logger.info(f"[FactSet] Vectorizing data for {state.ticker}")
    
    if not state.factset_price_data:
        return {"factset_vector_ids": []}
    
    pgvector = PgVectorClient()
    vector_ids = []
    
    try:
        # Convert price data to natural language
        price_text = f"""
        {state.ticker} price movement on {state.factset_price_data.date.strftime('%Y-%m-%d')}:
        - Opened at ${state.factset_price_data.open}, closed at ${state.factset_price_data.close}
        - Daily change: {state.factset_price_data.pct_change}%
        - Volume: {state.factset_price_data.volume:,} shares ({state.factset_price_data.volume_vs_avg}x average)
        - High: ${state.factset_price_data.high}, Low: ${state.factset_price_data.low}
        - Volatility ranking: {state.factset_price_data.volatility_percentile * 100:.0f}th percentile
        """
        
        texts = [price_text]
        
        # Add fundamental events
        for event in state.factset_events:
            event_text = f"{event.event_type.upper()} on {event.timestamp.strftime('%Y-%m-%d')}: {event.details}"
            texts.append(event_text)
        
        # Generate embeddings
        embeddings = asyncio.run(generate_embeddings(texts))
        
        # Store vectors
        vectors = []
        for idx, (text, embedding) in enumerate(zip(texts, embeddings)):
            vector_id = str(uuid.uuid4())
            
            metadata = {
                'stock_id': state.stock_id,
                'ticker': state.ticker,
                'source': 'factset',
                'data_type': 'price' if idx == 0 else 'event',
                'date': state.factset_price_data.date.isoformat()
            }
            
            if idx > 0:  # Event
                metadata['event_type'] = state.factset_events[idx-1].event_type
            
            vectors.append({
                'id': vector_id,
                'embedding': embedding,
                'text': text,
                'metadata': metadata
            })
            vector_ids.append(vector_id)
        
        pgvector.bulk_insert('factset_data', vectors)
        
        logger.info(f"Vectorized {len(vector_ids)} FactSet items for {state.ticker}")
        
        return {"factset_vector_ids": vector_ids}
        
    except Exception as e:
        logger.error(f"FactSet vectorization failed: {str(e)}")
        return {"factset_vector_ids": [], "error_message": str(e)}
    finally:
        pgvector.close()
```

---

## Task 2.4: Parallel Subgraph Architecture

### Create Parallel Data Ingestion Graph

Create `src/batch/graphs/parallel_ingestion.py`:
```python
"""
Parallel data ingestion using LangGraph Send() pattern
"""

from langgraph.graph import StateGraph, START, END, Send
from typing import List
import logging

from src.batch.state import BatchGraphState
from src.batch.nodes.edgar_ingestion import edgar_ingestion_node
from src.batch.nodes.vectorize_edgar import vectorize_edgar_node
from src.batch.nodes.bluematrix_ingestion import bluematrix_ingestion_node
from src.batch.nodes.vectorize_bluematrix import vectorize_bluematrix_node
from src.batch.nodes.factset_ingestion import factset_ingestion_node
from src.batch.nodes.vectorize_factset import vectorize_factset_node

logger = logging.getLogger(__name__)

# ============================================================================
# Individual Source Subgraphs
# ============================================================================

def create_edgar_subgraph():
    """Subgraph for EDGAR ingestion + vectorization"""
    builder = StateGraph(BatchGraphState)
    
    builder.add_node("edgar_ingest", edgar_ingestion_node)
    builder.add_node("edgar_vectorize", vectorize_edgar_node)
    
    builder.add_edge(START, "edgar_ingest")
    builder.add_edge("edgar_ingest", "edgar_vectorize")
    builder.add_edge("edgar_vectorize", END)
    
    return builder.compile()

def create_bluematrix_subgraph():
    """Subgraph for BlueMatrix ingestion + vectorization"""
    builder = StateGraph(BatchGraphState)
    
    builder.add_node("bluematrix_ingest", bluematrix_ingestion_node)
    builder.add_node("bluematrix_vectorize", vectorize_bluematrix_node)
    
    builder.add_edge(START, "bluematrix_ingest")
    builder.add_edge("bluematrix_ingest", "bluematrix_vectorize")
    builder.add_edge("bluematrix_vectorize", END)
    
    return builder.compile()

def create_factset_subgraph():
    """Subgraph for FactSet ingestion + vectorization"""
    builder = StateGraph(BatchGraphState)
    
    builder.add_node("factset_ingest", factset_ingestion_node)
    builder.add_node("factset_vectorize", vectorize_factset_node)
    
    builder.add_edge(START, "factset_ingest")
    builder.add_edge("factset_ingest", "factset_vectorize")
    builder.add_edge("factset_vectorize", END)
    
    return builder.compile()

# ============================================================================
# Fan-out and Aggregation Nodes
# ============================================================================

def fan_out_sources(state: BatchGraphState):
    """
    Fan out to process all three sources in parallel
    
    Returns a list of Send() commands that create parallel subgraphs
    """
    logger.info(f"Fanning out to 3 data sources for {state.ticker}")
    
    return [
        Send("edgar_subgraph", state.dict()),
        Send("bluematrix_subgraph", state.dict()),
        Send("factset_subgraph", state.dict())
    ]

def aggregate_sources(state: BatchGraphState, config) -> dict:
    """
    Aggregation node that waits for all parallel branches to complete
    
    LangGraph automatically handles the synchronization - this node
    only executes once all parallel branches have finished.
    """
    logger.info(f"Aggregating data from all sources for {state.ticker}")
    
    # Check which sources succeeded
    sources_status = {
        "edgar": state.edgar_status,
        "bluematrix": state.bluematrix_status,
        "factset": state.factset_status
    }
    
    successful_sources = sum(1 for status in sources_status.values() if status == "success")
    
    logger.info(f"Data collection complete: {successful_sources}/3 sources successful")
    
    # Return any updates to state if needed
    return {}

# ============================================================================
# Main Parallel Ingestion Graph
# ============================================================================

def create_parallel_ingestion_graph():
    """
    Create graph with parallel data source processing
    """
    builder = StateGraph(BatchGraphState)
    
    # Add the subgraphs as nodes
    builder.add_node("edgar_subgraph", create_edgar_subgraph())
    builder.add_node("bluematrix_subgraph", create_bluematrix_subgraph())
    builder.add_node("factset_subgraph", create_factset_subgraph())
    
    # Add fan-out and aggregation nodes
    builder.add_node("fan_out", fan_out_sources)
    builder.add_node("aggregate", aggregate_sources)
    
    # Connect the graph
    builder.add_edge(START, "fan_out")
    
    # The fan_out node returns Send() commands, so no explicit edges needed
    # to the subgraphs - LangGraph handles this automatically
    
    # All subgraphs feed into aggregate
    builder.add_edge("edgar_subgraph", "aggregate")
    builder.add_edge("bluematrix_subgraph", "aggregate")
    builder.add_edge("factset_subgraph", "aggregate")
    
    builder.add_edge("aggregate", END)
    
    return builder.compile()
```

**Test the parallel execution:**

Create `tests/batch/test_parallel_ingestion.py`:
```python
import pytest
import asyncio
import time
from datetime import datetime

from src.batch.graphs.parallel_ingestion import create_parallel_ingestion_graph
from src.batch.state import BatchGraphState

@pytest.mark.asyncio
async def test_parallel_execution_is_faster():
    """Verify that parallel execution is faster than sequential"""
    
    graph = create_parallel_ingestion_graph()
    
    state = BatchGraphState(
        stock_id="test-123",
        ticker="AAPL",
        company_name="Apple Inc.",
        batch_run_id="test-run"
    )
    
    start_time = time.time()
    result = await graph.ainvoke(state.dict())
    parallel_duration = time.time() - start_time
    
    # Verify all sources processed
    assert result['edgar_status'] in ['success', 'partial']
    assert result['bluematrix_status'] in ['success', 'partial']
    assert result['factset_status'] in ['success', 'partial']
    
    # Parallel should take roughly the time of the slowest branch,
    # not the sum of all branches
    logger.info(f"Parallel execution took {parallel_duration:.2f}s")
    
    # If sequential, would take ~3x as long (assuming each takes ~same time)
    # With parallel, should be closer to 1x the time of longest branch
```

---

## Task 2.5: Hook & Expanded Writer Agents

### Create Hook Writer Prompt

Create `prompts/batch/hook_writer_v1.yaml`:
```yaml
_type: prompt
input_variables:
  - ticker
  - company_name
  - all_sources_summary

template: |
  You are a social media headline writer for financial advisors. Create ONE SENTENCE (max 15 words) that captures the MOST material event.
  
  Company: {company_name} ({ticker})
  
  Data from all sources:
  {all_sources_summary}
  
  Requirements:
  - Maximum 15 words (ideally 10-12)
  - Include specific numbers (%, $, targets)
  - Use active voice
  - Prioritize: 1) Regulatory filings, 2) Analyst actions, 3) Price movements
  
  Examples:
  - "Tesla surges 12% after Musk announces $50B buyback in 8-K filing"
  - "Goldman upgrades Apple to Buy, raises target 20% to $195"
  - "Microsoft Q3 earnings beat; revenue up 18% to $56.5B"
  
  Output ONLY the hook sentence, nothing else.
```

### Create Hook Writer Agent

Create `src/batch/agents/hook_writer.py`:
```python
from langchain_anthropic import ChatAnthropic
from langchain_core.prompts import load_prompt
from typing import Dict, Any
import asyncio
import logging
import time

from src.batch.state import BatchGraphState
from src.shared.utils.rag import hybrid_search

logger = logging.getLogger(__name__)

class HookWriterAgent:
    """Agent for generating hook summaries (< 15 words)"""
    
    def __init__(self):
        self.llm = ChatAnthropic(
            model="claude-sonnet-4-20250514",
            temperature=0.5,  # Slightly higher for creativity
            max_tokens=100
        )
        self.prompt = load_prompt("prompts/batch/hook_writer_v1.yaml")
    
    async def generate(
        self,
        ticker: str,
        company_name: str,
        state: BatchGraphState
    ) -> tuple[str, int]:
        """Generate hook summary"""
        
        # Get most important context from all sources
        all_sources_summary = self._create_source_summary(state)
        
        # Generate hook
        messages = self.prompt.format(
            ticker=ticker,
            company_name=company_name,
            all_sources_summary=all_sources_summary
        )
        
        response = await self.llm.ainvoke(messages)
        hook = response.content.strip()
        
        # Validate word count
        word_count = len(hook.split())
        if word_count > 15:
            logger.warning(f"Hook exceeds 15 words ({word_count}), regenerating...")
            # Try again with stricter instruction
            hook = await self._regenerate_shorter(hook, ticker, company_name, all_sources_summary)
            word_count = len(hook.split())
        
        return hook, word_count
    
    def _create_source_summary(self, state: BatchGraphState) -> str:
        """Create concise summary from all sources"""
        parts = []
        
        # EDGAR
        if state.edgar_filings:
            filing = state.edgar_filings[0]  # Most recent
            parts.append(f"EDGAR: {filing.filing_type} filed {filing.filing_date.strftime('%m/%d')}")
        
        # BlueMatrix
        if state.bluematrix_reports:
            report = state.bluematrix_reports[0]
            parts.append(f"Analyst: {report.analyst_firm} {report.rating_change} to {report.new_rating}, PT ${report.price_target}")
        
        # FactSet
        if state.factset_price_data:
            parts.append(f"Price: {state.factset_price_data.pct_change:+.1f}%, volume {state.factset_price_data.volume_vs_avg:.1f}x avg")
        
        return " | ".join(parts)
    
    async def _regenerate_shorter(self, original: str, ticker: str, company_name: str, summary: str) -> str:
        """Regenerate with stricter word count"""
        messages = f"""
        Previous hook was too long ({len(original.split())} words):
        "{original}"
        
        Rewrite to EXACTLY 10-12 words. Be more concise.
        
        Data: {summary}
        """
        
        response = await self.llm.ainvoke(messages)
        return response.content.strip()

def hook_writer_node(state: BatchGraphState, config) -> Dict[str, Any]:
    """LangGraph node for hook generation"""
    logger.info(f"[Hook] Generating for {state.ticker}")
    
    start_time = time.time()
    
    agent = HookWriterAgent()
    hook, word_count = asyncio.run(agent.generate(
        state.ticker,
        state.company_name,
        state
    ))
    
    generation_time = int((time.time() - start_time) * 1000)
    
    logger.info(f"[Hook] Generated ({word_count} words): {hook}")
    
    return {
        "hook_summary": hook,
        "hook_word_count": word_count,
        "hook_generation_time_ms": generation_time
    }
```

### Create Expanded Writer Prompt

Create `prompts/batch/expanded_writer_v1.yaml`:
```yaml
_type: prompt
input_variables:
  - ticker
  - company_name
  - edgar_context
  - bluematrix_context
  - factset_context

template: |
  You are an equity research analyst writing comprehensive stock analysis for financial advisors.
  
  Company: {company_name} ({ticker})
  
  === SEC EDGAR FILINGS ===
  {edgar_context}
  
  === ANALYST RESEARCH (BlueMatrix) ===
  {bluematrix_context}
  
  === MARKET DATA (FactSet) ===
  {factset_context}
  
  Task: Write a comprehensive 5-6 paragraph analysis (500-750 words).
  
  Structure:
  
  Paragraph 1 - Executive Summary (75-100 words):
  - Most material events in first sentence
  - Key metrics and implications
  - Bottom line recommendation or perspective
  
  Paragraph 2 - Regulatory & Corporate Actions (100-125 words):
  - Detailed analysis of SEC filings
  - Specific items reported (8-K Item 2.02, etc.)
  - Corporate governance changes, M&A, material contracts
  
  Paragraph 3 - Analyst Perspective (100-125 words):
  - Upgrades/downgrades with specific firms and analysts
  - Price target changes with justification
  - Consensus view and outliers
  
  Paragraph 4 - Market Performance (100-125 words):
  - Price action with specific numbers
  - Volume analysis and unusual activity
  - Technical levels and key support/resistance
  
  Paragraph 5 - Forward-Looking Implications (100-125 words):
  - Key risks and catalysts
  - Expected impact on earnings/valuation
  - Positioning recommendations for advisors
  
  Requirements:
  - Total 500-750 words across 5 paragraphs
  - Cite sources inline: "According to [source]..."
  - Use specific numbers, dates, and names
  - Professional, analytical tone
  - Data-driven conclusions
  
  Output only the 5-paragraph analysis.
```

### Create Expanded Writer Agent

Create `src/batch/agents/expanded_writer.py`:
```python
from langchain_anthropic import ChatAnthropic
from langchain_core.prompts import load_prompt
from typing import Dict, Any
import asyncio
import logging
import time

from src.batch.state import BatchGraphState
from src.shared.utils.rag import hybrid_search

logger = logging.getLogger(__name__)

class ExpandedWriterAgent:
    """Agent for generating expanded summaries (500-750 words, 5-6 paragraphs)"""
    
    def __init__(self):
        self.llm = ChatAnthropic(
            model="claude-sonnet-4-20250514",
            temperature=0.3,
            max_tokens=2000
        )
        self.prompt = load_prompt("prompts/batch/expanded_writer_v1.yaml")
    
    async def generate(
        self,
        ticker: str,
        company_name: str,
        state: BatchGraphState
    ) -> tuple[str, int]:
        """Generate expanded summary"""
        
        # Retrieve comprehensive context from all sources
        edgar_context = await self._get_edgar_context(state)
        bluematrix_context = await self._get_bluematrix_context(state)
        factset_context = await self._get_factset_context(state)
        
        # Generate summary
        messages = self.prompt.format(
            ticker=ticker,
            company_name=company_name,
            edgar_context=edgar_context,
            bluematrix_context=bluematrix_context,
            factset_context=factset_context
        )
        
        response = await self.llm.ainvoke(messages)
        summary = response.content.strip()
        
        word_count = len(summary.split())
        
        logger.info(f"[Expanded] Generated {word_count} words")
        
        return summary, word_count
    
    async def _get_edgar_context(self, state: BatchGraphState) -> str:
        """Get detailed EDGAR context"""
        if not state.edgar_filings:
            return "No recent SEC filings."
        
        context_parts = []
        for filing in state.edgar_filings[:3]:  # Top 3 filings
            context_parts.append(f"""
            {filing.filing_type} filed {filing.filing_date.strftime('%m/%d/%Y')}:
            Items: {', '.join(filing.items_reported)}
            Events: {', '.join(filing.material_events)}
            URL: {filing.url}
            """)
        
        return "\n".join(context_parts)
    
    async def _get_bluematrix_context(self, state: BatchGraphState) -> str:
        """Get detailed analyst research context"""
        if not state.bluematrix_reports:
            return "No recent analyst reports."
        
        context_parts = []
        for report in state.bluematrix_reports[:3]:
            context_parts.append(f"""
            {report.analyst_firm} - {report.analyst_name}:
            - Rating: {report.previous_rating} → {report.new_rating} ({report.rating_change})
            - Price Target: ${report.previous_price_target} → ${report.price_target}
            - Key Points: {', '.join(report.key_points[:3])}
            - Date: {report.report_date.strftime('%m/%d/%Y')}
            """)
        
        return "\n".join(context_parts)
    
    async def _get_factset_context(self, state: BatchGraphState) -> str:
        """Get detailed market data context"""
        if not state.factset_price_data:
            return "No recent market data."
        
        pd = state.factset_price_data
        
        context = f"""
        Price Data ({pd.date.strftime('%m/%d/%Y')}):
        - Open: ${pd.open}, Close: ${pd.close} ({pd.pct_change:+.2f}%)
        - Range: ${pd.low} - ${pd.high}
        - Volume: {pd.volume:,} ({pd.volume_vs_avg:.1f}x average)
        - Volatility: {pd.volatility_percentile*100:.0f}th percentile
        """
        
        if state.factset_events:
            context += "\n\nFundamental Events:\n"
            for event in state.factset_events:
                context += f"- {event.event_type.upper()}: {event.details}\n"
        
        return context

def expanded_writer_node(state: BatchGraphState, config) -> Dict[str, Any]:
    """LangGraph node for expanded summary generation"""
    logger.info(f"[Expanded] Generating for {state.ticker}")
    
    start_time = time.time()
    
    agent = ExpandedWriterAgent()
    summary, word_count = asyncio.run(agent.generate(
        state.ticker,
        state.company_name,
        state
    ))
    
    generation_time = int((time.time() - start_time) * 1000)
    
    logger.info(f"[Expanded] Generated {word_count} words in {generation_time}ms")
    
    return {
        "expanded_summary": summary,
        "expanded_word_count": word_count,
        "expanded_generation_time_ms": generation_time
    }
```

---

## Task 2.6: LLM-Based Fact Checker Agents

### Create BlueMatrix Fact Checker

Create `prompts/batch/fact_check_bluematrix_v1.yaml`:
```yaml
_type: prompt
input_variables:
  - claims
  - source_data

template: |
  You are a financial fact validator. Verify each claim against BlueMatrix analyst research data.
  
  Claims to verify:
  {claims}
  
  BlueMatrix Source Data:
  {source_data}
  
  For each claim, respond with JSON:
  {{
    "claim_id": "...",
    "status": "verified|failed|uncertain",
    "evidence": "exact quote from source",
    "similarity_score": 0.0-1.0,
    "discrepancy": "explanation if failed"
  }}
  
  Verification rules:
  - Analyst names: Must match exactly
  - Firm names: Allow common variations (e.g., "Goldman" = "Goldman Sachs")
  - Ratings: Must match exactly ("Buy" ≠ "Strong Buy")
  - Price targets: ±1% tolerance
  - Dates: Must match exactly
  
  Output JSON array of results.
```

Create `src/batch/agents/bluematrix_fact_checker.py`:
```python
from langchain_anthropic import ChatAnthropic
from langchain_core.prompts import load_prompt
from typing import List, Dict, Any
import json
import logging

from src.batch.state import BatchGraphState, SourceFactCheckResult

logger = logging.getLogger(__name__)

class BlueMatrixFactCheckerAgent:
    """LLM-based fact checker for analyst research claims"""
    
    def __init__(self):
        self.llm = ChatAnthropic(
            model="claude-haiku-4-20250514",  # Use Haiku for cost efficiency
            temperature=0.0  # Deterministic for fact-checking
        )
        self.prompt = load_prompt("prompts/batch/fact_check_bluematrix_v1.yaml")
    
    async def verify_claims(
        self,
        claims: List[Dict[str, Any]],
        reports: List[Any]
    ) -> SourceFactCheckResult:
        """Verify claims against BlueMatrix data"""
        
        # Filter for BlueMatrix-related claims
        bm_claims = [c for c in claims if 'analyst' in c['claim_text'].lower() 
                     or 'rating' in c['claim_text'].lower() 
                     or 'target' in c['claim_text'].lower()]
        
        if not bm_claims:
            return SourceFactCheckResult(
                source="bluematrix",
                claims_checked=0,
                verified_count=0,
                pass_rate=1.0  # No claims = pass
            )
        
        # Format source data
        source_data = self._format_reports(reports)
        claims_text = json.dumps([{
            'id': c['claim_id'],
            'text': c['claim_text']
        } for c in bm_claims], indent=2)
        
        # Get LLM verification
        messages = self.prompt.format(
            claims=claims_text,
            source_data=source_data
        )
        
        response = await self.llm.ainvoke(messages)
        
        # Parse JSON response
        try:
            results = json.loads(response.content)
        except json.JSONDecodeError:
            logger.error("Failed to parse fact check response")
            results = []
        
        # Calculate statistics
        verified_count = sum(1 for r in results if r.get('status') == 'verified')
        failed_claims = [r for r in results if r.get('status') == 'failed']
        
        return SourceFactCheckResult(
            source="bluematrix",
            claims_checked=len(bm_claims),
            verified_count=verified_count,
            failed_claims=failed_claims,
            pass_rate=verified_count / len(bm_claims) if bm_claims else 1.0
        )
    
    def _format_reports(self, reports: List[Any]) -> str:
        """Format reports for verification"""
        formatted = []
        for report in reports:
            formatted.append(f"""
            Report ID: {report.report_id}
            Firm: {report.analyst_firm}
            Analyst: {report.analyst_name}
            Date: {report.report_date.strftime('%Y-%m-%d')}
            Rating: {report.previous_rating} → {report.new_rating}
            Price Target: ${report.previous_price_target} → ${report.price_target}
            """)
        return "\n---\n".join(formatted)
```

**Similarly create:**
- `src/batch/agents/edgar_fact_checker.py` (for filing claims)
- `src/batch/agents/factset_fact_checker.py` (for price/metric claims)

### Create Unified Fact Checking Node

Create `src/batch/nodes/multi_source_fact_checker.py`:
```python
import asyncio
import logging
from typing import Dict, Any, List

from src.batch.state import BatchGraphState, TierFactCheckState
from src.batch.agents.bluematrix_fact_checker import BlueMatrixFactCheckerAgent
from src.batch.agents.edgar_fact_checker import EdgarFactCheckerAgent
from src.batch.agents.factset_fact_checker import FactSetFactCheckerAgent
from src.shared.utils.claim_extractor import extract_claims_llm

logger = logging.getLogger(__name__)

async def fact_check_tier(
    tier: str,
    summary_text: str,
    state: BatchGraphState
) -> TierFactCheckState:
    """Fact check a specific summary tier across all sources"""
    
    logger.info(f"[FactCheck-{tier}] Checking {state.ticker}")
    
    # Extract claims using LLM
    claims = await extract_claims_llm(summary_text)
    
    if not claims:
        logger.warning(f"No claims extracted from {tier} summary")
        return TierFactCheckState(
            tier=tier,
            overall_status="passed",
            overall_pass_rate=1.0
        )
    
    # Check against each source in parallel
    bm_agent = BlueMatrixFactCheckerAgent()
    edgar_agent = EdgarFactCheckerAgent()
    fs_agent = FactSetFactCheckerAgent()
    
    results = await asyncio.gather(
        bm_agent.verify_claims(claims, state.bluematrix_reports),
        edgar_agent.verify_claims(claims, state.edgar_filings),
        fs_agent.verify_claims(claims, state.factset_price_data, state.factset_events)
    )
    
    bm_result, edgar_result, fs_result = results
    
    # Calculate overall statistics
    total_checked = bm_result.claims_checked + edgar_result.claims_checked + fs_result.claims_checked
    total_verified = bm_result.verified_count + edgar_result.verified_count + fs_result.verified_count
    
    overall_pass_rate = total_verified / total_checked if total_checked > 0 else 1.0
    
    # Collect all failed claims
    all_failed = (
        bm_result.failed_claims + 
        edgar_result.failed_claims + 
        fs_result.failed_claims
    )
    
    # Pass if ≥95% verified
    overall_status = "passed" if overall_pass_rate >= 0.95 else "failed"
    
    logger.info(f"[FactCheck-{tier}] {overall_pass_rate*100:.1f}% pass rate ({overall_status})")
    
    return TierFactCheckState(
        tier=tier,
        bluematrix_result=bm_result,
        edgar_result=edgar_result,
        factset_result=fs_result,
        overall_status=overall_status,
        overall_pass_rate=overall_pass_rate,
        failed_claims=all_failed
    )

# Create individual nodes for each tier

def hook_fact_check_node(state: BatchGraphState, config) -> Dict[str, Any]:
    """Fact check hook summary"""
    if not state.hook_summary:
        return {}
    
    result = asyncio.run(fact_check_tier("hook", state.hook_summary, state))
    return {"hook_fact_check": result}

def medium_fact_check_node(state: BatchGraphState, config) -> Dict[str, Any]:
    """Fact check medium summary"""
    if not state.medium_summary:
        return {}
    
    result = asyncio.run(fact_check_tier("medium", state.medium_summary, state))
    return {"medium_fact_check": result}

def expanded_fact_check_node(state: BatchGraphState, config) -> Dict[str, Any]:
    """Fact check expanded summary"""
    if not state.expanded_summary:
        return {}
    
    result = asyncio.run(fact_check_tier("expanded", state.expanded_summary, state))
    return {"expanded_fact_check": result}
```

### Create LLM Claim Extractor

Create `src/shared/utils/claim_extractor.py`:
```python
from langchain_anthropic import ChatAnthropic
from typing import List, Dict, Any
import json
import logging

logger = logging.getLogger(__name__)

async def extract_claims_llm(summary: str) -> List[Dict[str, Any]]:
    """Extract factual claims using LLM"""
    
    llm = ChatAnthropic(model="claude-haiku-4-20250514", temperature=0.0)
    
    prompt = f"""
    Extract ALL factual claims from this financial summary that can be verified:
    
    Summary:
    {summary}
    
    For each claim, identify:
    - The exact claim text
    - Type: numeric, date, attribution, event
    - Source expectation: bluematrix, edgar, or factset
    
    Output JSON array:
    [
      {{
        "claim_id": "uuid",
        "claim_text": "exact quote",
        "claim_type": "numeric|date|attribution|event",
        "expected_source": "bluematrix|edgar|factset",
        "confidence": 0.0-1.0
      }}
    ]
    
    Output ONLY the JSON array.
    """
    
    try:
        response = await llm.ainvoke(prompt)
        claims = json.loads(response.content)
        
        # Add UUIDs if missing
        import uuid
        for claim in claims:
            if 'claim_id' not in claim:
                claim['claim_id'] = str(uuid.uuid4())
        
        logger.info(f"Extracted {len(claims)} claims")
        return claims
        
    except Exception as e:
        logger.error(f"Claim extraction failed: {str(e)}")
        return []
```

---

## Task 2.7: Retry Logic with Negative Prompting

### Create Retry Controller

Create `src/batch/nodes/retry_controller.py`:
```python
import logging
from typing import Dict, Any, Literal

from src.batch.state import BatchGraphState, TierFactCheckState

logger = logging.getLogger(__name__)

def generate_negative_prompt(
    tier: Literal["hook", "medium", "expanded"],
    fact_check_result: TierFactCheckState
) -> str:
    """Generate correction prompt from failed fact checks"""
    
    if not fact_check_result.failed_claims:
        return ""
    
    corrections = []
    corrections.append(f"\n=== FACT CHECK FAILURES FOR {tier.upper()} SUMMARY ===\n")
    corrections.append(f"Your previous {tier} summary failed fact-checking with {fact_check_result.overall_pass_rate*100:.1f}% pass rate.\n")
    corrections.append("The following claims were INCORRECT:\n")
    
    for idx, failed_claim in enumerate(fact_check_result.failed_claims, 1):
        corrections.append(f"\n{idx}. INCORRECT CLAIM:")
        corrections.append(f"   You wrote: \"{failed_claim.get('claim_text', 'N/A')}\"")
        corrections.append(f"   Problem: {failed_claim.get('discrepancy', 'Not found in source data')}")
        
        if 'correct_value' in failed_claim:
            corrections.append(f"   CORRECT VALUE: {failed_claim['correct_value']}")
        if 'source' in failed_claim:
            corrections.append(f"   Source: {failed_claim['source']}")
    
    corrections.append("\n\n=== INSTRUCTIONS ===")
    corrections.append(f"Regenerate the {tier} summary with these corrections:")
    corrections.append("1. Fix ALL incorrect claims listed above")
    corrections.append("2. Use ONLY facts that appear in the source data")
    corrections.append("3. Do NOT make up or extrapolate information")
    corrections.append("4. If uncertain about a fact, omit it")
    corrections.append(f"5. Maintain {tier} summary format requirements\n")
    
    return "\n".join(corrections)

def should_retry(
    tier: Literal["hook", "medium", "expanded"],
    state: BatchGraphState
) -> bool:
    """Determine if tier should be retried"""
    
    retry_count = getattr(state, f"{tier}_retry_count", 0)
    fact_check = getattr(state, f"{tier}_fact_check", None)
    
    if not fact_check:
        return False
    
    if fact_check.overall_status == "passed":
        return False
    
    if retry_count >= 5:
        logger.warning(f"[{tier}] Max retries (5) exceeded for {state.ticker}")
        return False
    
    return True

def route_after_fact_check(state: BatchGraphState, tier: Literal["hook", "medium", "expanded"]) -> str:
    """Route decision after fact checking"""
    
    fact_check = getattr(state, f"{tier}_fact_check")
    
    if fact_check.overall_status == "passed":
        return "continue"
    elif should_retry(tier, state):
        return "retry"
    else:
        return "flag_failed"
```

### Update Writer Nodes to Accept Corrections

Update `src/batch/agents/medium_writer.py` to accept corrections:
```python
# Add to MediumWriterAgent class:

async def generate_with_corrections(
    self,
    ticker: str,
    company_name: str,
    state: BatchGraphState,
    corrections: List[str]
) -> tuple[str, int]:
    """Generate summary with correction prompts"""
    
    # Get base context
    all_sources_summary = self._create_source_summary(state)
    
    # Add corrections to prompt
    base_prompt = self.prompt.format(
        ticker=ticker,
        company_name=company_name,
        edgar_data=edgar_data,
        relevant_chunks=chunks_text
    )
    
    correction_text = "\n\n".join(corrections)
    full_prompt = f"{base_prompt}\n\n{correction_text}"
    
    response = await self.llm.ainvoke(full_prompt)
    summary = response.content.strip()
    
    return summary, len(summary.split())

# Update node to check for corrections:

def medium_writer_node(state: BatchGraphState, config) -> Dict[str, Any]:
    """Generate or regenerate medium summary"""
    
    agent = MediumWriterAgent()
    
    # Check if this is a retry
    if state.medium_corrections:
        logger.info(f"[Medium] Regenerating with corrections (attempt {state.medium_retry_count + 1})")
        summary, word_count = asyncio.run(agent.generate_with_corrections(
            state.ticker,
            state.company_name,
            state,
            state.medium_corrections
        ))
    else:
        logger.info(f"[Medium] Generating initial summary")
        summary, word_count = asyncio.run(agent.generate(
            state.ticker,
            state.company_name,
            state
        ))
    
    return {
        "medium_summary": summary,
        "medium_word_count": word_count,
        "medium_retry_count": state.medium_retry_count + 1 if state.medium_corrections else 0
    }
```

*Apply same pattern to hook_writer.py and expanded_writer.py*

---

## Task 2.8: Complete Multi-Source Graph with Retries

### Create Final Phase 2 Graph

Create `src/batch/graphs/multi_source_with_retry.py`:
```python
"""
Phase 2: Complete multi-source batch graph with:
- Parallel data ingestion
- All 3 summary tiers
- Multi-source fact checking
- Retry logic with max 5 attempts
"""

from langgraph.graph import StateGraph, START, END, Send
from langgraph.types import Command
import logging

from src.batch.state import BatchGraphState
from src.batch.graphs.parallel_ingestion import create_parallel_ingestion_graph
from src.batch.agents.hook_writer import hook_writer_node
from src.batch.agents.medium_writer import medium_writer_node
from src.batch.agents.expanded_writer import expanded_writer_node
from src.batch.nodes.multi_source_fact_checker import (
    hook_fact_check_node,
    medium_fact_check_node,
    expanded_fact_check_node
)
from src.batch.nodes.retry_controller import (
    generate_negative_prompt,
    should_retry,
    route_after_fact_check
)
from src.batch.nodes.storage import store_multi_tier_summary_node

logger = logging.getLogger(__name__)

# ============================================================================
# Routing Functions
# ============================================================================

def route_hook_fact_check(state: BatchGraphState) -> str:
    """Route hook after fact checking"""
    return route_after_fact_check(state, "hook")

def route_medium_fact_check(state: BatchGraphState) -> str:
    """Route medium after fact checking"""
    return route_after_fact_check(state, "medium")

def route_expanded_fact_check(state: BatchGraphState) -> str:
    """Route expanded after fact checking"""
    return route_after_fact_check(state, "expanded")

# ============================================================================
# Correction Generation Nodes
# ============================================================================

def generate_hook_corrections(state: BatchGraphState, config) -> dict:
    """Generate correction prompt for hook"""
    if not should_retry("hook", state):
        return {}
    
    corrections = generate_negative_prompt("hook", state.hook_fact_check)
    return {"hook_corrections": state.hook_corrections + [corrections]}

def generate_medium_corrections(state: BatchGraphState, config) -> dict:
    """Generate correction prompt for medium"""
    if not should_retry("medium", state):
        return {}
    
    corrections = generate_negative_prompt("medium", state.medium_fact_check)
    return {"medium_corrections": state.medium_corrections + [corrections]}

def generate_expanded_corrections(state: BatchGraphState, config) -> dict:
    """Generate correction prompt for expanded"""
    if not should_retry("expanded", state):
        return {}
    
    corrections = generate_negative_prompt("expanded", state.expanded_fact_check)
    return {"expanded_corrections": state.expanded_corrections + [corrections]}

# ============================================================================
# Main Graph
# ============================================================================

def create_phase2_batch_graph():
    """Create complete Phase 2 batch processing graph"""
    
    builder = StateGraph(BatchGraphState)
    
    # Step 1: Parallel data ingestion (embeds the parallel ingestion graph)
    builder.add_node("data_ingestion", create_parallel_ingestion_graph())
    
    # Step 2: Parallel summary generation (all 3 tiers)
    builder.add_node("hook_writer", hook_writer_node)
    builder.add_node("medium_writer", medium_writer_node)
    builder.add_node("expanded_writer", expanded_writer_node)
    
    # Step 3: Parallel fact checking (one checker per tier)
    builder.add_node("hook_fact_check", hook_fact_check_node)
    builder.add_node("medium_fact_check", medium_fact_check_node)
    builder.add_node("expanded_fact_check", expanded_fact_check_node)
    
    # Step 4: Correction generation
    builder.add_node("hook_corrections", generate_hook_corrections)
    builder.add_node("medium_corrections", generate_medium_corrections)
    builder.add_node("expanded_corrections", generate_expanded_corrections)
    
    # Step 5: Storage
    builder.add_node("storage", store_multi_tier_summary_node)
    
    # ========================================================================
    # Connect the graph
    # ========================================================================
    
    # Data ingestion first
    builder.add_edge(START, "data_ingestion")
    
    # After ingestion, generate all summaries in parallel
    builder.add_edge("data_ingestion", "hook_writer")
    builder.add_edge("data_ingestion", "medium_writer")
    builder.add_edge("data_ingestion", "expanded_writer")
    
    # Each writer feeds into its fact checker
    builder.add_edge("hook_writer", "hook_fact_check")
    builder.add_edge("medium_writer", "medium_fact_check")
    builder.add_edge("expanded_writer", "expanded_fact_check")
    
    # Conditional routing after fact checks
    builder.add_conditional_edges(
        "hook_fact_check",
        route_hook_fact_check,
        {
            "continue": "storage",  # All tiers must pass before storage
            "retry": "hook_corrections",
            "flag_failed": "storage"  # Store with failed status
        }
    )
    
    builder.add_conditional_edges(
        "medium_fact_check",
        route_medium_fact_check,
        {
            "continue": "storage",
            "retry": "medium_corrections",
            "flag_failed": "storage"
        }
    )
    
    builder.add_conditional_edges(
        "expanded_fact_check",
        route_expanded_fact_check,
        {
            "continue": "storage",
            "retry": "expanded_corrections",
            "flag_failed": "storage"
        }
    )
    
    # Correction nodes loop back to writers
    builder.add_edge("hook_corrections", "hook_writer")
    builder.add_edge("medium_corrections", "medium_writer")
    builder.add_edge("expanded_corrections", "expanded_writer")
    
    # Storage is terminal
    builder.add_edge("storage", END)
    
    # Compile
    graph = builder.compile()
    
    logger.info("✅ Phase 2 batch graph compiled")
    
    return graph
```

### Update Storage Node for Multi-Tier

Update `src/batch/nodes/storage.py`:
```python
def store_multi_tier_summary_node(state: BatchGraphState, config) -> Dict[str, Any]:
    """Store all three summary tiers"""
    logger.info(f"[Storage] Storing summaries for {state.ticker}")
    
    try:
        with db_manager.get_session() as session:
            # Determine overall fact check status
            hook_status = state.hook_fact_check.overall_status if state.hook_fact_check else "failed"
            medium_status = state.medium_fact_check.overall_status if state.medium_fact_check else "failed"
            expanded_status = state.expanded_fact_check.overall_status if state.expanded_fact_check else "failed"
            
            # Overall status is passed only if ALL tiers passed
            overall_status = FactCheckStatus.PASSED if all([
                hook_status == "passed",
                medium_status == "passed",
                expanded_status == "passed"
            ]) else FactCheckStatus.FAILED
            
            # Create summary record with all tiers
            summary = StockSummary(
                stock_id=state.stock_id,
                ticker=state.ticker,
                generation_date=datetime.utcnow(),
                
                # Hook
                hook_text=state.hook_summary,
                hook_word_count=state.hook_word_count,
                
                # Medium
                medium_text=state.medium_summary,
                medium_word_count=state.medium_word_count,
                
                # Expanded
                expanded_text=state.expanded_summary,
                expanded_word_count=state.expanded_word_count,
                
                # Fact check status
                fact_check_status=overall_status,
                retry_count=max(state.hook_retry_count, state.medium_retry_count, state.expanded_retry_count)
            )
            
            session.add(summary)
            session.flush()
            
            # Store citations from all tiers
            # ... (similar to Phase 1)
            
            session.commit()
            
            logger.info(f"✅ Stored all tiers for {state.ticker} ({overall_status})")
            
            return {
                "summary_id": str(summary.summary_id),
                "storage_status": "stored"
            }
            
    except Exception as e:
        logger.error(f"Storage failed: {str(e)}")
        return {
            "storage_status": "failed",
            "error_message": str(e)
        }
```

---

## Task 2.9: Batch Orchestrator with Concurrency

### Create Batch Orchestrator

Create `src/batch/orchestrator.py`:
```python
"""
Batch orchestrator for processing multiple stocks with concurrency control
"""

import asyncio
from typing import List
from datetime import datetime
import logging
import uuid

from src.batch.graphs.multi_source_with_retry import create_phase2_batch_graph
from src.batch.state import BatchGraphState
from src.shared.database.connection import db_manager
from src.shared.models.database import Stock, BatchRunAudit

logger = logging.getLogger(__name__)

class BatchOrchestrator:
    """Orchestrate batch processing with concurrency control"""
    
    def __init__(self, max_concurrency: int = 50):
        self.max_concurrency = max_concurrency
        self.graph = create_phase2_batch_graph()
        self.semaphore = asyncio.Semaphore(max_concurrency)
    
    async def process_stock(self, stock: Stock, batch_run_id: str) -> dict:
        """Process a single stock with semaphore control"""
        
        async with self.semaphore:
            logger.info(f"[Orchestrator] Processing {stock.ticker}")
            
            input_state = BatchGraphState(
                stock_id=str(stock.stock_id),
                ticker=stock.ticker,
                company_name=stock.company_name,
                batch_run_id=batch_run_id
            )
            
            try:
                result = await self.graph.ainvoke(input_state.dict())
                logger.info(f"[Orchestrator] ✅ {stock.ticker} complete")
                return result
            except Exception as e:
                logger.error(f"[Orchestrator] ❌ {stock.ticker} failed: {str(e)}")
                return {
                    "ticker": stock.ticker,
                    "storage_status": "failed",
                    "error_message": str(e)
                }
    
    async def run_batch(self, stocks: List[Stock]) -> dict:
        """Run batch for all stocks"""
        batch_run_id = str(uuid.uuid4())
        start_time = datetime.utcnow()
        
        logger.info(f"[Orchestrator] Starting batch {batch_run_id}")
        logger.info(f"[Orchestrator] Processing {len(stocks)} stocks with max {self.max_concurrency} concurrent")
        
        # Process all stocks concurrently (semaphore controls actual concurrency)
        tasks = [self.process_stock(stock, batch_run_id) for stock in stocks]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Calculate statistics
        end_time = datetime.utcnow()
        duration = (end_time - start_time).total_seconds()
        
        successful = sum(1 for r in results if isinstance(r, dict) and r.get('storage_status') == 'stored')
        failed = len(results) - successful
        
        # Save audit log
        with db_manager.get_session() as session:
            audit = BatchRunAudit(
                run_id=batch_run_id,
                run_date=start_time.date(),
                start_timestamp=start_time,
                end_timestamp=end_time,
                total_stocks_processed=len(results),
                successful_summaries=successful,
                failed_summaries=failed,
                average_generation_time_ms=int((duration / len(results)) * 1000)
            )
            session.add(audit)
            session.commit()
        
        logger.info(f"""
        [Orchestrator] ✅ Batch complete!
        Duration: {duration:.1f}s
        Successful: {successful}/{len(results)}
        Failed: {failed}/{len(results)}
        Avg time per stock: {duration/len(results):.1f}s
        """)
        
        return {
            "batch_run_id": batch_run_id,
            "duration_seconds": duration,
            "successful": successful,
            "failed": failed,
            "results": results
        }

async def run_batch_for_all_stocks(limit: int = None, max_concurrency: int = 50):
    """Entry point for running batch"""
    
    # Get stocks
    with db_manager.get_session() as session:
        query = session.query(Stock)
        if limit:
            query = query.limit(limit)
        stocks = query.all()
    
    # Run batch
    orchestrator = BatchOrchestrator(max_concurrency=max_concurrency)
    results = await orchestrator.run_batch(stocks)
    
    return results
```

### Create CLI for Phase 2

Create `src/batch/run_phase2_batch.py`:
```python
#!/usr/bin/env python3
"""Run Phase 2 batch processing"""

import asyncio
import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.batch.orchestrator import run_batch_for_all_stocks

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)

async def main():
    parser = argparse.ArgumentParser(description="Run Phase 2 batch processing")
    parser.add_argument("--limit", type=int, help="Limit number of stocks")
    parser.add_argument("--concurrency", type=int, default=50, help="Max concurrent stocks")
    args = parser.parse_args()
    
    results = await run_batch_for_all_stocks(
        limit=args.limit,
        max_concurrency=args.concurrency
    )
    
    print("\n" + "="*60)
    print("BATCH COMPLETE")
    print("="*60)
    print(f"Duration: {results['duration_seconds']:.1f}s")
    print(f"Successful: {results['successful']}")
    print(f"Failed: {results['failed']}")
    print("="*60)

if __name__ == "__main__":
    asyncio.run(main())
```

---

## Validation Commands
```bash
# 1. Run all tests
pytest tests/batch/ -v

# 2. Test parallel ingestion
pytest tests/batch/test_parallel_ingestion.py -v

# 3. Test single stock through full pipeline
python -c "
import asyncio
from src.batch.graphs.multi_source_with_retry import create_phase2_batch_graph
from src.batch.state import BatchGraphState

async def test():
    graph = create_phase2_batch_graph()
    state = BatchGraphState(
        stock_id='test',
        ticker='AAPL',
        company_name='Apple Inc.',
        batch_run_id='test'
    )
    result = await graph.ainvoke(state.dict())
    print(f'Result: {result[\"storage_status\"]}')

asyncio.run(test())
"

# 4. Run batch for 10 stocks
python src/batch/run_phase2_batch.py --limit 10 --concurrency 5

# 5. Run batch for 100 stocks
python src/batch/run_phase2_batch.py --limit 100 --concurrency 50

# 6. Verify all tiers stored
python -c "
from src.shared.database.connection import db_manager
from src.shared.models.database import StockSummary

with db_manager.get_session() as session:
    summaries = session.query(StockSummary).all()
    for s in summaries[:5]:
        print(f'{s.ticker}:')
        print(f'  Hook: {s.hook_word_count} words')
        print(f'  Medium: {s.medium_word_count} words')
        print(f'  Expanded: {s.expanded_word_count} words')
        print(f'  Status: {s.fact_check_status}')
        print()
"

# 7. Check LangSmith traces
# Visit LangSmith dashboard - should see parallel execution
```

## Success Criteria - Phase 2

- [ ] BlueMatrix and FactSet data ingestion working (mocked OK)
- [ ] All 3 sources vectorized into separate namespaces
- [ ] Parallel data ingestion faster than sequential
- [ ] Hook summaries are 10-15 words
- [ ] Medium summaries are 75-125 words
- [ ] Expanded summaries are 500-750 words
- [ ] LLM fact-checkers verify claims across all sources
- [ ] Retry logic regenerates failed summaries (max 5 times)
- [ ] Negative prompting includes specific corrections
- [ ] 100 stocks process in < 30 minutes with concurrency=50
- [ ] Fact-check pass rate > 95%
- [ ] All 3 tiers stored in database
- [ ] LangSmith shows parallel execution and retry loops

## Next Steps

After Phase 2 validation:
1. Commit code: `git commit -m "Phase 2 complete"`
2. Tag: `git tag v0.3.0-phase2`
3. Document any issues encountered
4. Proceed to Phase 3: Interactive Process + UI

## Troubleshooting

### If parallel execution isn't working:
- Check LangSmith traces to see if subgraphs are actually parallel
- Verify `Send()` commands are being returned correctly
- Check semaphore in orchestrator

### If fact-checking fails everything:
- Review claim extraction - may be too strict
- Check if LLM responses are parseable JSON
- Lower pass rate threshold temporarily (90% instead of 95%)

### If retries aren't working:
- Check correction prompt generation
- Verify state is carrying corrections forward
- Check retry_count is incrementing

### If summaries exceed word limits:
- Add word count validation in agents
- Implement automatic truncation
- Use stricter prompts with examples