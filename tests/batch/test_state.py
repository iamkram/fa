import pytest
from datetime import datetime
import uuid

from src.batch.state import (
    EdgarFiling,
    BatchInputState,
    BatchGraphState,
    FactCheckClaim,
    FactCheckResult,
)


def test_edgar_filing_creation():
    """Test creating an EDGAR filing"""
    filing = EdgarFiling(
        filing_type="8-K",
        accession_number="0001234567-25-000001",
        filing_date=datetime(2025, 11, 7),
        items_reported=["Item 2.02", "Item 7.01"],
        material_events=["Earnings release"],
        url="https://www.sec.gov/test",
        full_text="Test filing content"
    )

    assert filing.filing_type == "8-K"
    assert len(filing.items_reported) == 2
    assert filing.full_text == "Test filing content"


def test_batch_input_state_defaults():
    """Test BatchInputState generates default values"""
    state = BatchInputState(
        stock_id="test-stock-id",
        ticker="AAPL",
        company_name="Apple Inc."
    )

    assert state.ticker == "AAPL"
    assert state.batch_run_id is not None
    assert isinstance(state.processing_date, datetime)


def test_batch_graph_state_creation():
    """Test creating complete batch graph state"""
    state = BatchGraphState(
        stock_id="test-id",
        ticker="MSFT",
        company_name="Microsoft Corporation",
        batch_run_id="batch-123"
    )

    assert state.ticker == "MSFT"
    assert state.edgar_filings == []
    assert state.vector_ids == []
    assert state.fact_check_results == []
    assert state.retry_count == 0


def test_fact_check_claim_generation():
    """Test fact check claim with auto-generated ID"""
    claim = FactCheckClaim(
        claim_text="8-K filed on 11/07/2025",
        claim_type="date",
        expected_source="edgar",
        confidence=0.95
    )

    assert claim.claim_id is not None
    assert claim.claim_type == "date"
    assert claim.confidence == 0.95


def test_fact_check_result():
    """Test fact check result validation"""
    result = FactCheckResult(
        claim_id="claim-123",
        claim_text="Revenue increased 15%",
        validation_status="verified",
        evidence_text="Found in 10-Q filing",
        similarity_score=0.98
    )

    assert result.validation_status == "verified"
    assert result.similarity_score == 0.98


def test_state_serialization():
    """Test state can be serialized to dict"""
    state = BatchGraphState(
        stock_id="test",
        ticker="GOOGL",
        company_name="Alphabet Inc.",
        batch_run_id="test-batch"
    )

    state_dict = state.model_dump()
    assert isinstance(state_dict, dict)
    assert state_dict["ticker"] == "GOOGL"
    assert state_dict["edgar_filings"] == []
