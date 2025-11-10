"""
Enterprise-scale database models for FA AI System

Supports:
- 4,000 Financial Advisors
- 800,000 Households (200 per FA avg)
- 5,600,000 Accounts (7 per household avg)
- 840,000,000 Holdings (150 per account avg)

Key design decisions:
- Partitioning for household_summaries and stock_summaries (monthly)
- JSONB for flexible metadata
- Strategic indexing for fast lookups
- 90-day rolling window for summaries
"""

from sqlalchemy import Column, String, Integer, Float, DateTime, Text, ForeignKey, Boolean, Numeric, Index
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB
from datetime import datetime
import uuid

Base = declarative_base()

# ============================================================================
# Core Entities (Financial Advisors, Households, Accounts, Holdings)
# ============================================================================

class FinancialAdvisor(Base):
    """Financial Advisors (4,000 total)"""
    __tablename__ = "financial_advisors"

    fa_id = Column(String(50), primary_key=True)  # e.g., "FA-001"
    name = Column(String(255), nullable=False)
    firm = Column(String(255))
    email = Column(String(255))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    households = relationship("Household", back_populates="advisor")


class Household(Base):
    """Households (800,000 total, ~200 per FA)"""
    __tablename__ = "households"

    household_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    household_name = Column(String(255), nullable=False)
    fa_id = Column(String(50), ForeignKey("financial_advisors.fa_id"), nullable=False, index=True)

    # Portfolio metrics (denormalized for speed)
    total_aum = Column(Numeric(15, 2))  # Total assets under management
    relationship_tier = Column(String(50))  # e.g., "Platinum", "Gold", "Silver"
    client_since = Column(DateTime)
    last_meeting_date = Column(DateTime, index=True)
    next_meeting_date = Column(DateTime, index=True)

    notes = Column(Text)
    metadata = Column(JSONB)  # Flexible additional data

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    advisor = relationship("FinancialAdvisor", back_populates="households")
    accounts = relationship("Account", back_populates="household")

    __table_args__ = (
        Index('idx_fa_household', 'fa_id', 'household_id'),
    )


class Account(Base):
    """Accounts (5.6M total, ~7 per household)"""
    __tablename__ = "accounts"

    account_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    household_id = Column(UUID(as_uuid=True), ForeignKey("households.household_id"), nullable=False, index=True)
    account_name = Column(String(255), nullable=False)  # e.g., "Joint Brokerage", "IRA - John"
    account_type = Column(String(50))  # e.g., "Taxable", "IRA", "401k", "Trust"
    account_number = Column(String(50))
    custodian = Column(String(255))  # e.g., "Schwab", "Fidelity"

    # Account metrics (denormalized)
    current_value = Column(Numeric(15, 2))
    is_active = Column(Boolean, default=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    household = relationship("Household", back_populates="accounts")
    holdings = relationship("Holding", back_populates="account")

    __table_args__ = (
        Index('idx_household_account', 'household_id', 'account_id'),
    )


class Holding(Base):
    """Holdings (840M total, ~150 per account)

    This is the largest table. Optimizations:
    - Index on ticker for batch processing
    - Index on account_id for household queries
    - Keep only active holdings (archived separately)
    """
    __tablename__ = "holdings"

    holding_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    account_id = Column(UUID(as_uuid=True), ForeignKey("accounts.account_id"), nullable=False, index=True)
    ticker = Column(String(10), nullable=False, index=True)

    # Position details
    shares = Column(Numeric(15, 4), nullable=False)
    cost_basis = Column(Numeric(15, 2))  # Total cost basis
    current_price = Column(Numeric(15, 2))  # Cached from latest batch
    current_value = Column(Numeric(15, 2))  # shares * current_price

    # Dates
    purchase_date = Column(DateTime)
    last_updated = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    is_active = Column(Boolean, default=True, index=True)

    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    account = relationship("Account", back_populates="holdings")

    __table_args__ = (
        Index('idx_account_ticker', 'account_id', 'ticker'),
        Index('idx_ticker_active', 'ticker', 'is_active'),  # For batch processing
    )


# ============================================================================
# Stock Reference Data
# ============================================================================

class Stock(Base):
    """Stock master data (~5,000 unique tickers)"""
    __tablename__ = "stocks"

    ticker = Column(String(10), primary_key=True)
    cusip = Column(String(9), unique=True, index=True)
    company_name = Column(String(255), nullable=False)
    sector = Column(String(100), index=True)
    industry = Column(String(100))
    market_cap = Column(String(50))  # e.g., "Large", "Mid", "Small"

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# ============================================================================
# Batch Processing Tables
# ============================================================================

class BatchRun(Base):
    """Batch run tracking (nightly at 2 AM)"""
    __tablename__ = "batch_runs"

    batch_run_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_date = Column(DateTime, nullable=False, index=True)
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime)
    status = Column(String(50), nullable=False, index=True)  # RUNNING, COMPLETED, FAILED

    # Phase statistics
    stocks_processed = Column(Integer, default=0)
    households_processed = Column(Integer, default=0)
    holdings_ingested = Column(Integer, default=0)

    # Error tracking
    errors = Column(JSONB)

    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime)

    # Relationships
    stock_summaries = relationship("StockSummary", back_populates="batch_run")
    household_summaries = relationship("HouseholdSummary", back_populates="batch_run")

    __table_args__ = (
        Index('idx_run_date_status', 'run_date', 'status'),
    )


class StockSummary(Base):
    """Stock-level summaries from batch processing

    Generated during Phase 2 of batch run (10-K/8-K via Perplexity)
    ~5,000 stocks × 365 days = 1.8M rows/year
    Keep 90-day rolling window = ~450K rows
    """
    __tablename__ = "stock_summaries"

    summary_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ticker = Column(String(10), nullable=False, index=True)
    batch_run_id = Column(UUID(as_uuid=True), ForeignKey("batch_runs.batch_run_id"), nullable=False, index=True)

    # Summary content
    summary = Column(Text, nullable=False)  # 200-word summary from Perplexity
    filing_date = Column(DateTime)  # Date of latest 10-K/8-K

    # Perplexity metadata
    perplexity_citations = Column(JSONB)  # Store citations for validation

    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    # Relationships
    batch_run = relationship("BatchRun", back_populates="stock_summaries")

    __table_args__ = (
        Index('idx_ticker_batch', 'ticker', 'batch_run_id'),
        Index('idx_created_at', 'created_at'),  # For partition cleanup
    )


class HouseholdSummary(Base):
    """Household-level summaries from batch processing

    Generated during Phase 3 of batch run
    800,000 households × 365 days = 292M rows/year
    Keep 90-day rolling window = ~72M rows (370 GB with compression)
    """
    __tablename__ = "household_summaries"

    summary_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    household_id = Column(UUID(as_uuid=True), ForeignKey("households.household_id"), nullable=False, index=True)
    batch_run_id = Column(UUID(as_uuid=True), ForeignKey("batch_runs.batch_run_id"), nullable=False, index=True)

    # Summary content
    summary = Column(Text, nullable=False)  # 300-word household portfolio summary

    # Portfolio metrics (denormalized for quick access)
    total_value = Column(Numeric(15, 2), nullable=False)
    holdings_count = Column(Integer, nullable=False)
    top_holdings = Column(JSONB)  # Top 10 holdings with percentages

    # Sector allocation
    sector_allocation = Column(JSONB)  # Breakdown by sector

    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    # Relationships
    batch_run = relationship("BatchRun", back_populates="household_summaries")
    household = relationship("Household")

    __table_args__ = (
        Index('idx_household_batch', 'household_id', 'batch_run_id'),
        Index('idx_batch_household', 'batch_run_id', 'household_id'),
        Index('idx_created_at', 'created_at'),  # For partition cleanup
    )


# ============================================================================
# Validation & Citations
# ============================================================================

class ValidationResult(Base):
    """Track validation results from Validator Agent"""
    __tablename__ = "validation_results"

    validation_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    request_id = Column(String(100), nullable=False, index=True)  # From interactive request

    # Validation results
    passed = Column(Boolean, nullable=False, index=True)
    confidence_score = Column(Float, nullable=False)
    issues_found = Column(JSONB)  # List of validation issues
    validated_claims = Column(JSONB)  # List of validated claims

    # Performance metrics
    validation_time_ms = Column(Integer)

    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    __table_args__ = (
        Index('idx_request_created', 'request_id', 'created_at'),
    )


# ============================================================================
# Partitioning Setup (for production)
# ============================================================================

# Note: Partitioning is done via SQL migrations, not SQLAlchemy
# See: scripts/setup_partitioning.sql
#
# stock_summaries: partitioned by created_at (monthly)
# household_summaries: partitioned by created_at (monthly)
#
# Retention: 90 days
# Automated cleanup: DROP OLD PARTITIONS monthly
