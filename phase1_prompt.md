# Phase 1: Batch Process MVP - EDGAR Only

## Context

You have completed Phase 0 with:
- Project structure in place
- Database models defined
- pgvector client working
- LangSmith configured

Now you will build a working batch pipeline that:
- Fetches SEC EDGAR filings for stocks
- Generates medium-tier summaries (1 paragraph, 75-125 words)
- Performs basic rule-based fact-checking
- Stores validated summaries in Postgres

## Technical Requirements

### LangGraph 1.0 Specifics
- Use `StateGraph` from `langgraph.graph`
- Define state classes with Pydantic
- Use `add_node()` and `add_edge()` for graph construction
- Use `Command` pattern for explicit routing
- Implement proper state reducers for merging parallel results

### State Management
All state classes must:
- Inherit from `TypedDict` or use Pydantic `BaseModel`
- Include proper type hints
- Have clear field documentation
- Support serialization to JSON

## Task 1.1: State Schema Definition

Create `src/batch/state.py` with these exact state classes:
```python
from typing import List, Dict, Any, Optional, Literal
from pydantic import BaseModel, Field
from datetime import datetime
import uuid

class EdgarFiling(BaseModel):
    """Single EDGAR filing"""
    filing_type: str
    accession_number: str
    filing_date: datetime
    items_reported: List[str]
    material_events: List[str]
    url: str
    full_text: str

class BatchInputState(BaseModel):
    """Input state for batch processing"""
    stock_id: str
    ticker: str
    company_name: str
    batch_run_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    processing_date: datetime = Field(default_factory=datetime.utcnow)

class EdgarDataState(BaseModel):
    """State after EDGAR data ingestion"""
    stock_id: str
    ticker: str
    filings: List[EdgarFiling]
    processing_status: Literal["success", "partial", "failed"]
    error_message: Optional[str] = None

class VectorizationState(BaseModel):
    """State after vectorization"""
    stock_id: str
    ticker: str
    vector_ids: List[str]
    chunk_count: int
    namespace: str = "edgar_filings"

class SummaryGenerationState(BaseModel):
    """State after summary generation"""
    stock_id: str
    ticker: str
    medium_summary: Optional[str] = None
    word_count: int = 0
    generation_time_ms: int = 0
    source_citations: List[Dict[str, Any]] = Field(default_factory=list)
    status: Literal["pending_fact_check", "failed", "complete"] = "pending_fact_check"

class FactCheckClaim(BaseModel):
    """Single factual claim to verify"""
    claim_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    claim_text: str
    claim_type: Literal["numeric", "date", "attribution", "event"]
    expected_source: str
    confidence: float

class FactCheckResult(BaseModel):
    """Result of fact-checking a single claim"""
    claim_id: str
    claim_text: str
    validation_status: Literal["verified", "failed", "uncertain"]
    evidence_text: Optional[str] = None
    similarity_score: Optional[float] = None
    discrepancy_detail: Optional[str] = None

class FactCheckState(BaseModel):
    """State after fact-checking"""
    stock_id: str
    ticker: str
    summary_tier: str = "medium"
    fact_check_results: List[FactCheckResult]
    overall_status: Literal["passed", "failed"]
    pass_rate: float
    retry_count: int = 0

class BatchOutputState(BaseModel):
    """Final output state"""
    stock_id: str
    ticker: str
    summary_id: Optional[str] = None
    storage_status: Literal["stored", "failed"]
    error_message: Optional[str] = None
    total_processing_time_ms: int = 0

# Combined state for full graph
class BatchGraphState(BaseModel):
    """Complete state for batch processing graph"""
    # Input
    stock_id: str
    ticker: str
    company_name: str
    batch_run_id: str
    
    # EDGAR data
    edgar_filings: List[EdgarFiling] = Field(default_factory=list)
    edgar_status: Optional[str] = None
    
    # Vectorization
    vector_ids: List[str] = Field(default_factory=list)
    
    # Summary
    medium_summary: Optional[str] = None
    word_count: int = 0
    
    # Fact checking
    fact_check_results: List[FactCheckResult] = Field(default_factory=list)
    fact_check_status: Optional[str] = None
    retry_count: int = 0
    
    # Output
    summary_id: Optional[str] = None
    storage_status: Optional[str] = None
    error_message: Optional[str] = None
```

Create comprehensive tests in `tests/batch/test_state.py`.

## Task 1.2: EDGAR Data Ingestion Node

Create `src/batch/nodes/edgar_ingestion.py`:

### Requirements:
1. Query SEC EDGAR API for filings in last 24 hours
2. Focus on: 8-K, 10-Q, 10-K, Form 4, 13D, 13G
3. Parse filing XML/HTML to extract material events
4. Handle rate limiting (10 requests/second max)
5. Implement exponential backoff on failures (3 retries)
6. Return structured `EdgarDataState`

### SEC EDGAR API Details:
- Endpoint: `https://data.sec.gov/submissions/CIK{cik}.json`
- Filings endpoint: `https://efts.sec.gov/LATEST/search-index`
- User-Agent required: "YourCompany contact@email.com"
- Rate limit: 10 requests/second

### Example Implementation Structure:
```python
from langchain_core.runnables import RunnableConfig
from typing import Dict, Any
import httpx
import asyncio
import logging

logger = logging.getLogger(__name__)

async def fetch_edgar_filings(
    ticker: str,
    company_name: str,
    lookback_hours: int = 24
) -> List[EdgarFiling]:
    """Fetch EDGAR filings for a stock"""
    # Implementation here
    pass

def edgar_ingestion_node(state: BatchGraphState, config: RunnableConfig) -> Dict[str, Any]:
    """LangGraph node for EDGAR data ingestion"""
    logger.info(f"Fetching EDGAR filings for {state.ticker}")
    
    try:
        filings = asyncio.run(fetch_edgar_filings(
            state.ticker,
            state.company_name,
            lookback_hours=24
        ))
        
        return {
            "edgar_filings": filings,
            "edgar_status": "success" if filings else "partial"
        }
    except Exception as e:
        logger.error(f"EDGAR ingestion failed for {state.ticker}: {str(e)}")
        return {
            "edgar_filings": [],
            "edgar_status": "failed",
            "error_message": str(e)
        }
```

Create tests in `tests/batch/nodes/test_edgar_ingestion.py` with mocked API responses.

## Task 1.3: Text Chunking & Embedding Pipeline

Create `src/shared/utils/chunking.py`:

### Requirements:
1. Chunk filing text with 1000 token chunks, 100 token overlap
2. Use `langchain_text_splitters.RecursiveCharacterTextSplitter`
3. Generate embeddings with OpenAI `text-embedding-3-large` (3072 dimensions)
4. Batch embedding generation (max 100 texts per API call)
5. Store in pgvector `edgar_filings` namespace

### Implementation:
```python
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from typing import List, Dict, Any
import tiktoken

def count_tokens(text: str, model: str = "gpt-4") -> int:
    """Count tokens in text"""
    encoding = tiktoken.encoding_for_model(model)
    return len(encoding.encode(text))

def chunk_text(text: str, chunk_size: int = 1000, chunk_overlap: int = 100) -> List[str]:
    """Chunk text into overlapping segments"""
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        length_function=count_tokens,
        separators=["\n\n", "\n", ".", " ", ""]
    )
    return splitter.split_text(text)

async def generate_embeddings(texts: List[str], batch_size: int = 100) -> List[List[float]]:
    """Generate embeddings in batches"""
    embeddings_model = OpenAIEmbeddings(model="text-embedding-3-large")
    
    all_embeddings = []
    for i in range(0, len(texts), batch_size):
        batch = texts[i:i+batch_size]
        batch_embeddings = await embeddings_model.aembed_documents(batch)
        all_embeddings.extend(batch_embeddings)
    
    return all_embeddings
```

Create `src/batch/nodes/vectorize_edgar.py`:
```python
from src.shared.utils.chunking import chunk_text, generate_embeddings
from src.shared.vector_store.pgvector_client import PgVectorClient
import asyncio
import uuid
import logging

logger = logging.getLogger(__name__)

def vectorize_edgar_node(state: BatchGraphState, config: RunnableConfig) -> Dict[str, Any]:
    """Vectorize EDGAR filings and store in pgvector"""
    logger.info(f"Vectorizing EDGAR filings for {state.ticker}")
    
    pgvector = PgVectorClient()
    vector_ids = []
    
    try:
        for filing in state.edgar_filings:
            # Chunk the filing text
            chunks = chunk_text(filing.full_text)
            
            # Generate embeddings
            embeddings = asyncio.run(generate_embeddings(chunks))
            
            # Prepare vectors for bulk insert
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
                        'filing_type': filing.filing_type,
                        'accession_number': filing.accession_number,
                        'filing_date': filing.filing_date.isoformat(),
                        'chunk_index': idx
                    }
                })
                vector_ids.append(vector_id)
            
            # Bulk insert
            pgvector.bulk_insert('edgar_filings', vectors)
        
        return {
            "vector_ids": vector_ids
        }
        
    except Exception as e:
        logger.error(f"Vectorization failed for {state.ticker}: {str(e)}")
        return {
            "vector_ids": [],
            "error_message": str(e)
        }
    finally:
        pgvector.close()
```

## Task 1.4: Medium Summary Writer Agent

Create `prompts/batch/medium_writer_v1.yaml`:
```yaml
_type: prompt
input_variables:
  - ticker
  - company_name
  - edgar_data
  - relevant_chunks

template: |
  You are a financial advisor briefing writer creating summaries for professional advisors.
  
  Company: {company_name} ({ticker})
  
  SEC EDGAR Filings (Last 24 Hours):
  {edgar_data}
  
  Additional Context:
  {relevant_chunks}
  
  Task: Write ONE paragraph (75-125 words) summarizing key developments.
  
  Structure:
  - Lead sentence: Most material event with specific details
  - 2-3 supporting sentences: Context, impact, and implications
  - Closing sentence: Key takeaway or analyst perspective
  
  Requirements:
  - Use active voice and specific numbers/dates
  - Include filing types and specific items (e.g., "8-K Item 2.02")
  - Cite sources inline: "According to 8-K filed 11/6/2025..."
  - Professional, factual tone
  - Exactly 75-125 words
  
  Output only the paragraph text, no commentary.
```

Create `src/batch/agents/medium_writer.py`:
```python
from langchain_anthropic import ChatAnthropic
from langchain_core.prompts import load_prompt
from src.shared.utils.rag import hybrid_search
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

class MediumWriterAgent:
    """Agent for generating medium-tier summaries"""
    
    def __init__(self):
        self.llm = ChatAnthropic(model="claude-sonnet-4-20250514", temperature=0.3)
        self.prompt = load_prompt("prompts/batch/medium_writer_v1.yaml")
        
    async def generate(
        self,
        ticker: str,
        company_name: str,
        edgar_data: str,
        stock_id: str
    ) -> str:
        """Generate medium summary"""
        
        # Retrieve relevant chunks via hybrid RAG
        relevant_chunks = await hybrid_search(
            query=f"material events for {ticker} {company_name}",
            namespaces=["edgar_filings"],
            stock_id=stock_id,
            top_k=10
        )
        
        # Format chunks
        chunks_text = "\n".join([
            f"- {chunk['text'][:200]}..." 
            for chunk in relevant_chunks
        ])
        
        # Generate summary
        messages = self.prompt.format(
            ticker=ticker,
            company_name=company_name,
            edgar_data=edgar_data,
            relevant_chunks=chunks_text
        )
        
        response = await self.llm.ainvoke(messages)
        return response.content

def medium_writer_node(state: BatchGraphState, config: RunnableConfig) -> Dict[str, Any]:
    """LangGraph node for medium summary generation"""
    import asyncio
    import time
    
    logger.info(f"Generating medium summary for {state.ticker}")
    
    start_time = time.time()
    
    # Format EDGAR data
    edgar_summary = "\n".join([
        f"- {f.filing_type} filed {f.filing_date.strftime('%m/%d/%Y')}: {', '.join(f.material_events)}"
        for f in state.edgar_filings
    ])
    
    agent = MediumWriterAgent()
    summary = asyncio.run(agent.generate(
        ticker=state.ticker,
        company_name=state.company_name,
        edgar_data=edgar_summary,
        stock_id=state.stock_id
    ))
    
    # Count words
    word_count = len(summary.split())
    generation_time = int((time.time() - start_time) * 1000)
    
    return {
        "medium_summary": summary,
        "word_count": word_count,
        "generation_time_ms": generation_time
    }
```

Create `src/shared/utils/rag.py` for hybrid search:
```python
from src.shared.vector_store.pgvector_client import PgVectorClient
from langchain_openai import OpenAIEmbeddings
from typing import List, Dict, Any
import asyncio

async def hybrid_search(
    query: str,
    namespaces: List[str],
    stock_id: str,
    top_k: int = 10,
    threshold: float = 0.75
) -> List[Dict[str, Any]]:
    """Hybrid dense + sparse search"""
    
    # Generate query embedding
    embeddings = OpenAIEmbeddings(model="text-embedding-3-large")
    query_embedding = await embeddings.aembed_query(query)
    
    # Dense search via pgvector
    pgvector = PgVectorClient()
    all_results = []
    
    for namespace in namespaces:
        results = pgvector.similarity_search(
            namespace=namespace,
            query_embedding=query_embedding,
            top_k=top_k,
            threshold=threshold,
            filter_metadata={"stock_id": stock_id}
        )
        all_results.extend(results)
    
    pgvector.close()
    
    # Sort by similarity
    all_results.sort(key=lambda x: x['similarity'], reverse=True)
    
    return all_results[:top_k]
```

## Task 1.5: Rule-Based Fact Checker

Create `src/batch/nodes/fact_checker.py`:
```python
import re
from datetime import datetime
from typing import List, Dict, Any
import logging

from src.batch.state import BatchGraphState, FactCheckClaim, FactCheckResult

logger = logging.getLogger(__name__)

def extract_claims(summary: str) -> List[FactCheckClaim]:
    """Extract verifiable claims from summary"""
    claims = []
    
    # Extract numeric claims (percentages, prices, counts)
    numeric_pattern = r'\b\d+\.?\d*%?\b|\$\d+\.?\d*[BMK]?\b'
    for match in re.finditer(numeric_pattern, summary):
        claims.append(FactCheckClaim(
            claim_text=match.group(),
            claim_type="numeric",
            expected_source="edgar",
            confidence=0.9
        ))
    
    # Extract date claims
    date_pattern = r'\b\d{1,2}/\d{1,2}/\d{4}\b'
    for match in re.finditer(date_pattern, summary):
        claims.append(FactCheckClaim(
            claim_text=match.group(),
            claim_type="date",
            expected_source="edgar",
            confidence=0.95
        ))
    
    # Extract filing type claims
    filing_pattern = r'\b(8-K|10-K|10-Q|Form 4|13D|13G)\b'
    for match in re.finditer(filing_pattern, summary):
        claims.append(FactCheckClaim(
            claim_text=match.group(),
            claim_type="event",
            expected_source="edgar",
            confidence=1.0
        ))
    
    return claims

def validate_claim(claim: FactCheckClaim, edgar_filings: List) -> FactCheckResult:
    """Validate a single claim against EDGAR data"""
    
    if claim.claim_type == "numeric":
        # For MVP, just check if number exists in any filing
        for filing in edgar_filings:
            if claim.claim_text in filing.full_text:
                return FactCheckResult(
                    claim_id=claim.claim_id,
                    claim_text=claim.claim_text,
                    validation_status="verified",
                    evidence_text=f"Found in {filing.filing_type}",
                    similarity_score=1.0
                )
        return FactCheckResult(
            claim_id=claim.claim_id,
            claim_text=claim.claim_text,
            validation_status="failed",
            discrepancy_detail="Numeric value not found in filings"
        )
    
    elif claim.claim_type == "date":
        # Check if date matches any filing date
        try:
            claim_date = datetime.strptime(claim.claim_text, "%m/%d/%Y")
            for filing in edgar_filings:
                if filing.filing_date.date() == claim_date.date():
                    return FactCheckResult(
                        claim_id=claim.claim_id,
                        claim_text=claim.claim_text,
                        validation_status="verified",
                        evidence_text=f"Matches {filing.filing_type} filing date",
                        similarity_score=1.0
                    )
        except ValueError:
            pass
        
        return FactCheckResult(
            claim_id=claim.claim_id,
            claim_text=claim.claim_text,
            validation_status="failed",
            discrepancy_detail="Date does not match any filing"
        )
    
    elif claim.claim_type == "event":
        # Check if filing type exists
        for filing in edgar_filings:
            if claim.claim_text in filing.filing_type:
                return FactCheckResult(
                    claim_id=claim.claim_id,
                    claim_text=claim.claim_text,
                    validation_status="verified",
                    evidence_text=f"Filing type confirmed: {filing.filing_type}",
                    similarity_score=1.0
                )
        
        return FactCheckResult(
            claim_id=claim.claim_id,
            claim_text=claim.claim_text,
            validation_status="failed",
            discrepancy_detail=f"Filing type {claim.claim_text} not found"
        )
    
    return FactCheckResult(
        claim_id=claim.claim_id,
        claim_text=claim.claim_text,
        validation_status="uncertain",
        discrepancy_detail="Unable to verify"
    )

def fact_check_node(state: BatchGraphState, config: RunnableConfig) -> Dict[str, Any]:
    """Fact-check the generated summary"""
    logger.info(f"Fact-checking summary for {state.ticker}")
    
    if not state.medium_summary:
        return {
            "fact_check_status": "failed",
            "error_message": "No summary to fact-check"
        }
    
    # Extract claims
    claims = extract_claims(state.medium_summary)
    
    # Validate each claim
    results = []
    for claim in claims:
        result = validate_claim(claim, state.edgar_filings)
        results.append(result)
    
    # Calculate pass rate
    verified_count = sum(1 for r in results if r.validation_status == "verified")
    pass_rate = verified_count / len(results) if results else 0
    
    overall_status = "passed" if pass_rate >= 0.95 else "failed"
    
    return {
        "fact_check_results": results,
        "fact_check_status": overall_status,
        "pass_rate": pass_rate
    }
```

## Task 1.6: Postgres Storage Node

Create `src/batch/nodes/storage.py`:
```python
import logging
from datetime import datetime
from typing import Dict, Any

from src.shared.database.connection import db_manager
from src.shared.models.database import StockSummary, FactCheckStatus, SummaryCitation
from src.batch.state import BatchGraphState

logger = logging.getLogger(__name__)

def store_summary_node(state: BatchGraphState, config: RunnableConfig) -> Dict[str, Any]:
    """Store validated summary in Postgres"""
    logger.info(f"Storing summary for {state.ticker}")
    
    try:
        with db_manager.get_session() as session:
            # Create summary record
            summary = StockSummary(
                stock_id=state.stock_id,
                ticker=state.ticker,
                generation_date=datetime.utcnow(),
                medium_text=state.medium_summary,
                medium_word_count=state.word_count,
                fact_check_status=(
                    FactCheckStatus.PASSED if state.fact_check_status == "passed"
                    else FactCheckStatus.FAILED
                ),
                retry_count=state.retry_count
            )
            
            session.add(summary)
            session.flush()  # Get summary_id
            
            # Create citation records
            for result in state.fact_check_results:
                if result.validation_status == "verified":
                    citation = SummaryCitation(
                        summary_id=summary.summary_id,
                        source_type='edgar',
                        claim_text=result.claim_text,
                        evidence_text=result.evidence_text,
                        similarity_score=result.similarity_score
                    )
                    session.add(citation)
            
            session.commit()
            
            logger.info(f"✅ Stored summary {summary.summary_id} for {state.ticker}")
            
            return {
                "summary_id": str(summary.summary_id),
                "storage_status": "stored"
            }
            
    except Exception as e:
        logger.error(f"Storage failed for {state.ticker}: {str(e)}")
        return {
            "storage_status": "failed",
            "error_message": str(e)
        }
```

## Task 1.7: Batch Graph Assembly

Create `src/batch/graphs/single_source_batch.py`:
```python
from langgraph.graph import StateGraph, START, END
from langgraph.types import Command
import logging

from src.batch.state import BatchGraphState
from src.batch.nodes.edgar_ingestion import edgar_ingestion_node
from src.batch.nodes.vectorize_edgar import vectorize_edgar_node
from src.batch.agents.medium_writer import medium_writer_node
from src.batch.nodes.fact_checker import fact_check_node
from src.batch.nodes.storage import store_summary_node

logger = logging.getLogger(__name__)

def create_batch_graph():
    """Create the Phase 1 batch processing graph"""
    
    # Initialize graph
    builder = StateGraph(BatchGraphState)
    
    # Add nodes
    builder.add_node("edgar_ingestion", edgar_ingestion_node)
    builder.add_node("vectorize", vectorize_edgar_node)
    builder.add_node("medium_writer", medium_writer_node)
    builder.add_node("fact_checker", fact_check_node)
    builder.add_node("storage", store_summary_node)
    
    # Add edges
    builder.add_edge(START, "edgar_ingestion")
    builder.add_edge("edgar_ingestion", "vectorize")
    builder.add_edge("vectorize", "medium_writer")
    builder.add_edge("medium_writer", "fact_checker")
    
    # Conditional edge: only store if fact check passed
    # In Phase 1, we don't retry - just flag as failed
    def route_after_fact_check(state: BatchGraphState):
        if state.fact_check_status == "passed":
            return "storage"
        else:
            # Still store but with failed status
            return "storage"
    
    builder.add_conditional_edges(
        "fact_checker",
        route_after_fact_check,
        ["storage"]
    )
    
    builder.add_edge("storage", END)
    
    # Compile graph
    graph = builder.compile()
    
    logger.info("✅ Batch graph compiled successfully")
    
    return graph

# Create and export graph
batch_graph = create_batch_graph()
```

Create `src/batch/run_batch.py` CLI script:
```python
#!/usr/bin/env python3
"""Run batch processing for stocks"""

import asyncio
import sys
from pathlib import Path
import argparse
import logging
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.batch.graphs.single_source_batch import batch_graph
from src.batch.state import BatchGraphState
from src.shared.database.connection import db_manager
from src.shared.models.database import Stock, BatchRunAudit
import uuid

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def process_stock(stock: Stock, batch_run_id: str):
    """Process a single stock"""
    logger.info(f"Processing {stock.ticker}...")
    
    input_state = BatchGraphState(
        stock_id=str(stock.stock_id),
        ticker=stock.ticker,
        company_name=stock.company_name,
        batch_run_id=batch_run_id
    )
    
    try:
        result = await batch_graph.ainvoke(input_state.dict())
        logger.info(f"✅ Completed {stock.ticker}: {result.get('storage_status')}")
        return result
    except Exception as e:
        logger.error(f"❌ Failed {stock.ticker}: {str(e)}")
        return {"storage_status": "failed", "error_message": str(e)}

async def run_batch(limit: int = None):
    """Run batch process for all stocks"""
    batch_run_id = str(uuid.uuid4())
    start_time = datetime.utcnow()
    
    logger.info(f"Starting batch run {batch_run_id}")
    
    # Get stocks to process
    with db_manager.get_session() as session:
        query = session.query(Stock)
        if limit:
            query = query.limit(limit)
        stocks = query.all()
    
    logger.info(f"Processing {len(stocks)} stocks")
    
    # Process stocks (sequential for Phase 1, parallel in Phase 2)
    results = []
    for stock in stocks:
        result = await process_stock(stock, batch_run_id)
        results.append(result)
    
    # Update audit log
    end_time = datetime.utcnow()
    successful = sum(1 for r in results if r.get('storage_status') == 'stored')
    failed = len(results) - successful
    
    with db_manager.get_session() as session:
        audit = BatchRunAudit(
            run_id=batch_run_id,
            run_date=start_time.date(),
            start_timestamp=start_time,
            end_timestamp=end_time,
            total_stocks_processed=len(results),
            successful_summaries=successful,
            failed_summaries=failed
        )
        session.add(audit)
        session.commit()
    
    duration = (end_time - start_time).total_seconds()
    logger.info(f"""
    ✅ Batch complete!
    Duration: {duration:.1f}s
    Successful: {successful}/{len(results)}
    Failed: {failed}/{len(results)}
    """)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, help="Limit number of stocks to process")
    args = parser.parse_args()
    
    asyncio.run(run_batch(limit=args.limit))
```

## Task 1.8: Testing & Validation

Create `tests/batch/integration/test_end_to_end.py`:
```python
import pytest
import asyncio
from datetime import datetime

from src.batch.graphs.single_source_batch import batch_graph
from src.batch.state import BatchGraphState
from src.shared.database.connection import db_manager
from src.shared.models.database import Stock, StockSummary

@pytest.mark.asyncio
async def test_full_pipeline():
    """Test complete batch pipeline for one stock"""
    
    # Get test stock
    with db_manager.get_session() as session:
        stock = session.query(Stock).filter_by(ticker="AAPL").first()
        assert stock is not None
    
    # Create input state
    input_state = BatchGraphState(
        stock_id=str(stock.stock_id),
        ticker=stock.ticker,
        company_name=stock.company_name,
        batch_run_id="test-run"
    )
    
    # Run graph
    result = await batch_graph.ainvoke(input_state.dict())
    
    # Verify result
    assert result['storage_status'] == 'stored'
    assert result['summary_id'] is not None
    assert result['fact_check_status'] in ['passed', 'failed']
    
    # Verify database
    with db_manager.get_session() as session:
        summary = session.query(StockSummary).filter_by(
            summary_id=result['summary_id']
        ).first()
        assert summary is not None
        assert summary.medium_text is not None
        assert 75 <= summary.medium_word_count <= 125

@pytest.mark.asyncio  
async def test_fact_check_failure():
    """Test that intentionally wrong summary fails fact check"""
    # Implementation: Modify summary to include wrong date, verify fact check catches it
    pass
```

## Validation Commands

Run these commands to validate Phase 1:
```bash
# 1. Run unit tests
pytest tests/batch/nodes/ -v

# 2. Test graph compilation
python -c "from src.batch.graphs.single_source_batch import batch_graph; print('✅ Graph compiled')"

# 3. Run batch for 5 test stocks
python src/batch/run_batch.py --limit 5

# 4. Verify summaries in database
python -c "
from src.shared.database.connection import db_manager
from src.shared.models.database import StockSummary
with db_manager.get_session() as session:
    count = session.query(StockSummary).count()
    print(f'✅ {count} summaries stored')
"

# 5. Run integration tests
pytest tests/batch/integration/test_end_to_end.py -v

# 6. Check LangSmith traces
# Visit LangSmith dashboard to see traces
```

## Success Criteria

- [ ] All state classes defined with proper types
- [ ] EDGAR ingestion fetches filings (mocked or real)
- [ ] Text chunking produces 1000-token chunks
- [ ] Embeddings generated and stored in pgvector
- [ ] Medium summaries are 75-125 words
- [ ] Fact checker validates claims
- [ ] Summaries stored in Postgres with citations
- [ ] 5 test stocks process in < 5 minutes
- [ ] LangSmith traces visible for all nodes
- [ ] Integration tests pass

## Troubleshooting

### If EDGAR API fails:
- Use mocked responses for testing
- Check User-Agent header
- Verify rate limiting logic

### If embeddings fail:
- Check OpenAI API key
- Verify network connectivity
- Use smaller batch sizes

### If fact checker fails everything:
- Review claim extraction regex
- Add logging to see what claims are being extracted
- Relax pass rate threshold for testing

## Next Steps

After Phase 1 validation:
1. Tag code as `v0.2.0-phase1-complete`
2. Document any issues or learnings
3. Proceed to Phase 2 prompt