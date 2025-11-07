import pytest
from datetime import datetime

from src.batch.nodes.edgar_ingestion import edgar_ingestion_node, fetch_edgar_filings
from src.batch.state import BatchGraphState


@pytest.mark.asyncio
async def test_fetch_edgar_filings_aapl():
    """Test fetching mocked EDGAR filings for AAPL"""
    filings = await fetch_edgar_filings("AAPL", "Apple Inc.", lookback_hours=24)

    assert len(filings) > 0
    assert filings[0].filing_type == "8-K"
    assert "Apple" in filings[0].full_text
    assert "revenue" in filings[0].full_text.lower()


@pytest.mark.asyncio
async def test_fetch_edgar_filings_unknown_ticker():
    """Test fetching filings for unknown ticker returns empty"""
    filings = await fetch_edgar_filings("UNKNOWN", "Unknown Co.", lookback_hours=24)

    assert filings == []


def test_edgar_ingestion_node_success():
    """Test EDGAR ingestion node with successful fetch"""
    state = BatchGraphState(
        stock_id="test-id",
        ticker="MSFT",
        company_name="Microsoft Corporation",
        batch_run_id="test-batch"
    )

    result = edgar_ingestion_node(state, config=None)

    assert result["edgar_status"] == "success"
    assert len(result["edgar_filings"]) > 0
    assert result["edgar_filings"][0].filing_type in ["8-K", "10-Q", "10-K"]


def test_edgar_ingestion_node_no_data():
    """Test EDGAR ingestion node with no available data"""
    state = BatchGraphState(
        stock_id="test-id",
        ticker="NODATA",
        company_name="No Data Corp",
        batch_run_id="test-batch"
    )

    result = edgar_ingestion_node(state, config=None)

    assert result["edgar_status"] == "partial"
    assert result["edgar_filings"] == []
