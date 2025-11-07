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
