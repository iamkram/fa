from typing import List, Dict, Any, Optional, Literal, Annotated
from pydantic import BaseModel, Field
from datetime import datetime
import uuid
import operator

# ============================================================================
# Phase 1: EDGAR Models
# ============================================================================

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

# ============================================================================
# Phase 2: BlueMatrix Models
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
    key_points: List[str] = Field(default_factory=list)
    full_text: str

# ============================================================================
# Phase 2: FactSet Models
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

# ============================================================================
# Phase 2: Multi-Source Fact-Checking Models
# ============================================================================

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
    overall_status: Literal["passed", "failed", "pending"] = "pending"
    overall_pass_rate: float = 0.0
    failed_claims: List[Dict[str, Any]] = Field(default_factory=list)

# ============================================================================
# Phase 2: Enhanced BatchGraphState with Multi-Source Support
# ============================================================================

class BatchGraphStatePhase2(BaseModel):
    """Complete state for Phase 2 batch processing with multi-source data"""
    # Input
    stock_id: str
    ticker: str
    company_name: str
    batch_run_id: str
    processing_date: datetime = Field(default_factory=datetime.utcnow)

    # Data from all sources (Annotated for parallel updates)
    edgar_filings: Annotated[List[EdgarFiling], operator.add] = Field(default_factory=list)
    edgar_status: Optional[str] = None

    bluematrix_reports: Annotated[List[AnalystReport], operator.add] = Field(default_factory=list)
    bluematrix_status: Optional[str] = None

    factset_price_data: Optional[PriceData] = None
    factset_events: Annotated[List[FundamentalEvent], operator.add] = Field(default_factory=list)
    factset_status: Optional[str] = None

    # Vectorization (separate namespaces per source, Annotated for parallel updates)
    edgar_vector_ids: Annotated[List[str], operator.add] = Field(default_factory=list)
    bluematrix_vector_ids: Annotated[List[str], operator.add] = Field(default_factory=list)
    factset_vector_ids: Annotated[List[str], operator.add] = Field(default_factory=list)

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

    # Retry tracking (for future phase 2b)
    hook_retry_count: int = 0
    medium_retry_count: int = 0
    expanded_retry_count: int = 0

    hook_corrections: Annotated[List[str], operator.add] = Field(default_factory=list)
    medium_corrections: Annotated[List[str], operator.add] = Field(default_factory=list)
    expanded_corrections: Annotated[List[str], operator.add] = Field(default_factory=list)

    # Output
    summary_id: Optional[str] = None
    storage_status: Optional[str] = None
    error_message: Optional[str] = None
    total_processing_time_ms: int = 0
