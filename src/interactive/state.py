"""
Interactive Query System State Schema

Defines all state models for the interactive query processing pipeline.
"""

from typing import List, Dict, Any, Optional, Literal
from pydantic import BaseModel, Field
from datetime import datetime
import uuid


# ============================================================================
# Input State
# ============================================================================

class ConversationTurn(BaseModel):
    """Single turn in conversation history"""
    role: Literal["user", "assistant"]
    content: str
    timestamp: datetime


class InteractiveInputState(BaseModel):
    """Initial input from user"""
    query_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    fa_id: str
    session_id: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    query_text: str
    query_type: Literal["dashboard_load", "stock_detail", "deep_dive", "chat"]
    context: Dict[str, Any] = Field(default_factory=dict)  # Current ticker, household_id, etc.
    conversation_history: List[ConversationTurn] = Field(default_factory=list)


# ============================================================================
# Guardrail States
# ============================================================================

class GuardrailFlag(BaseModel):
    """Single guardrail flag"""
    flag_type: Literal["pii", "injection", "off_topic", "compliance", "hallucination", "tone"]
    severity: Literal["low", "medium", "high"]
    detail: str
    action_taken: Literal["proceed", "block", "redact", "flag"]


class GuardrailState(BaseModel):
    """State after guardrail checks"""
    input_safe: bool
    flags: List[GuardrailFlag] = Field(default_factory=list)
    sanitized_query: str
    redacted_content: List[str] = Field(default_factory=list)


# ============================================================================
# Query Classification
# ============================================================================

class QueryClassificationState(BaseModel):
    """State after query classification"""
    classification: Literal["simple_retrieval", "deep_research"]
    confidence: float
    reasoning: str


# ============================================================================
# EDO Context State (MCP)
# ============================================================================

class FAProfile(BaseModel):
    """Financial Advisor profile"""
    fa_id: str
    name: str
    region: str
    aum: float
    client_count: int
    specialization: Optional[str] = None


class HouseholdHolding(BaseModel):
    """Single stock holding"""
    ticker: str
    shares: int
    cost_basis: float
    current_value: float
    pct_of_portfolio: float
    unrealized_gain_loss: float


class HouseholdInteraction(BaseModel):
    """Recent interaction with household"""
    date: datetime
    interaction_type: Literal["call", "email", "meeting", "note"]
    summary: str
    sentiment: Literal["positive", "neutral", "negative"]


class Household(BaseModel):
    """Household information"""
    household_id: str
    household_name: str
    total_aum: float
    risk_tolerance: Optional[str] = None
    holdings: List[HouseholdHolding] = Field(default_factory=list)
    recent_interactions: List[HouseholdInteraction] = Field(default_factory=list)


class EdoContextState(BaseModel):
    """State after EDO context retrieval"""
    fa_profile: Optional[FAProfile] = None
    relevant_households: List[Household] = Field(default_factory=list)
    total_exposure: Dict[str, float] = Field(default_factory=dict)  # ticker -> total value across households


# ============================================================================
# News Research State
# ============================================================================

class NewsItem(BaseModel):
    """Single news item"""
    headline: str
    source: str
    url: str
    published_at: datetime
    summary: str
    relevance_score: float


class NewsResearchState(BaseModel):
    """State after news research"""
    news_items: List[NewsItem] = Field(default_factory=list)
    query_timestamp: datetime = Field(default_factory=datetime.utcnow)


# ============================================================================
# Memory State
# ============================================================================

class RetrievedChunk(BaseModel):
    """Vector search result chunk"""
    chunk_id: str
    namespace: Literal["bluematrix_reports", "edgar_filings", "factset_data"]
    text: str
    metadata: Dict[str, Any]
    similarity_score: float
    rank: int


class MemoryState(BaseModel):
    """State after memory integration"""
    conversation_context: List[ConversationTurn] = Field(default_factory=list)
    retrieved_chunks: List[RetrievedChunk] = Field(default_factory=list)


# ============================================================================
# Assembled Context State
# ============================================================================

class AssembledContextState(BaseModel):
    """Complete context for response generation"""
    query_intent: str
    fa_context: Optional[EdoContextState] = None
    batch_summary: Optional[Dict[str, Any]] = None  # Pre-generated summary if available
    breaking_news: List[NewsItem] = Field(default_factory=list)
    historical_data: List[RetrievedChunk] = Field(default_factory=list)
    conversation_history: List[ConversationTurn] = Field(default_factory=list)
    total_token_count: int = 0
    assembly_timestamp: datetime = Field(default_factory=datetime.utcnow)


# ============================================================================
# Response State
# ============================================================================

class PIIFlag(BaseModel):
    """PII detected in response"""
    pii_type: Literal["household_name", "account_number", "ssn", "email", "phone"]
    location: str
    redacted_text: str


class ResponseCitation(BaseModel):
    """Citation for a claim in response"""
    claim: str
    source: str
    reference_id: str


class InteractiveOutputState(BaseModel):
    """Final response state"""
    response_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    response_text: str
    response_tier: Literal["hook", "medium", "expanded"]
    pii_flags: List[PIIFlag] = Field(default_factory=list)
    citations: List[ResponseCitation] = Field(default_factory=list)
    confidence_score: float = 1.0
    generation_time_ms: int = 0
    guardrail_status: str = "passed"


# ============================================================================
# Combined Interactive Graph State
# ============================================================================

class InteractiveGraphState(BaseModel):
    """Complete state for interactive query processing"""
    # Input
    query_id: str
    fa_id: str
    session_id: str
    query_text: str
    query_type: str
    context: Dict[str, Any] = Field(default_factory=dict)
    conversation_history: List[ConversationTurn] = Field(default_factory=list)

    # Guardrails
    input_safe: bool = True
    input_flags: List[GuardrailFlag] = Field(default_factory=list)
    sanitized_query: str = ""

    # Classification
    classification: Optional[str] = None
    classification_confidence: float = 0.0

    # Research data
    edo_context: Optional[EdoContextState] = None
    news_items: List[NewsItem] = Field(default_factory=list)
    retrieved_chunks: List[RetrievedChunk] = Field(default_factory=list)
    batch_summary: Optional[Dict[str, Any]] = None

    # Assembled context
    assembled_context: Optional[AssembledContextState] = None

    # Response
    response_text: Optional[str] = None
    response_tier: Optional[str] = None
    pii_flags: List[PIIFlag] = Field(default_factory=list)
    citations: List[ResponseCitation] = Field(default_factory=list)

    # Output guardrails
    output_safe: bool = True
    output_flags: List[GuardrailFlag] = Field(default_factory=list)

    # Retry tracking
    retry_count: int = 0
    max_retries: int = 5

    # Metadata
    total_processing_time_ms: int = 0
    error_message: Optional[str] = None
