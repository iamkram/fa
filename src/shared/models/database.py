from sqlalchemy import Column, String, Integer, Float, DateTime, Text, ForeignKey, Enum, Index, JSON
from sqlalchemy.orm import declarative_base
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime
import uuid
import enum

Base = declarative_base()

class FactCheckStatus(str, enum.Enum):
    PASSED = "passed"
    FAILED = "failed"
    UNVALIDATED = "unvalidated"

class Stock(Base):
    __tablename__ = "stocks"

    stock_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ticker = Column(String(10), unique=True, nullable=False, index=True)
    cusip = Column(String(9), unique=True)
    company_name = Column(String(255), nullable=False)
    sector = Column(String(100))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class StockSummary(Base):
    __tablename__ = "stock_summaries"

    summary_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    stock_id = Column(UUID(as_uuid=True), ForeignKey("stocks.stock_id"), nullable=False)
    ticker = Column(String(10), nullable=False, index=True)
    generation_date = Column(DateTime, nullable=False, index=True)
    generation_timestamp = Column(DateTime, default=datetime.utcnow)

    # Three tiers of summaries
    hook_text = Column(String(500))
    hook_word_count = Column(Integer)
    medium_text = Column(Text)
    medium_word_count = Column(Integer)
    expanded_text = Column(Text)
    expanded_word_count = Column(Integer)

    # Fact checking
    fact_check_status = Column(Enum(FactCheckStatus), nullable=False, index=True)
    retry_count = Column(Integer, default=0)

    # Change detection
    source_hash = Column(String(64))

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index('idx_ticker_date', 'ticker', 'generation_date'),
    )

class SummaryCitation(Base):
    __tablename__ = "summary_citations"

    citation_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    summary_id = Column(UUID(as_uuid=True), ForeignKey("stock_summaries.summary_id"), nullable=False, index=True)
    source_type = Column(Enum('bluematrix', 'edgar', 'factset', name='source_type_enum'), nullable=False)
    reference_id = Column(String(255))
    claim_text = Column(Text)
    evidence_text = Column(Text)
    similarity_score = Column(Float)
    created_at = Column(DateTime, default=datetime.utcnow)

class BatchRunAudit(Base):
    __tablename__ = "batch_run_audit"

    run_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_date = Column(DateTime, nullable=False, index=True)
    start_timestamp = Column(DateTime, nullable=False)
    end_timestamp = Column(DateTime)
    total_stocks_processed = Column(Integer, default=0)
    successful_summaries = Column(Integer, default=0)
    failed_summaries = Column(Integer, default=0)
    average_generation_time_ms = Column(Integer)
    total_fact_checks_performed = Column(Integer, default=0)
    fact_check_pass_rate = Column(Float)
    error_log = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)
