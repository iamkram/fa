import pytest
from datetime import datetime

from src.batch.graphs.single_source_batch import batch_graph
from src.batch.state import BatchGraphState
from src.shared.database.connection import db_manager
from src.shared.models.database import Stock, StockSummary


@pytest.mark.asyncio
async def test_full_pipeline_aapl():
    """Test complete batch pipeline for AAPL"""

    # Get AAPL test stock
    with db_manager.get_session() as session:
        stock = session.query(Stock).filter_by(ticker="AAPL").first()
        assert stock is not None, "AAPL stock not found in database"

        # Extract attributes while still in session
        stock_id = str(stock.stock_id)
        ticker = stock.ticker
        company_name = stock.company_name

    # Create input state
    input_state = BatchGraphState(
        stock_id=stock_id,
        ticker=ticker,
        company_name=company_name,
        batch_run_id="test-run-aapl"
    )

    # Run graph
    result = await batch_graph.ainvoke(input_state.model_dump())

    # Verify result structure
    assert 'storage_status' in result
    assert 'summary_id' in result
    assert 'fact_check_status' in result

    # Verify storage succeeded
    assert result['storage_status'] == 'stored'
    assert result['summary_id'] is not None

    # Verify fact check ran
    assert result['fact_check_status'] in ['passed', 'failed']

    # Verify database record
    with db_manager.get_session() as session:
        summary = session.query(StockSummary).filter_by(
            summary_id=result['summary_id']
        ).first()

        assert summary is not None
        assert summary.medium_text is not None
        assert len(summary.medium_text) > 0
        # Allow some flexibility in word count
        assert 50 <= summary.medium_word_count <= 150


@pytest.mark.asyncio
async def test_full_pipeline_msft():
    """Test complete batch pipeline for MSFT"""

    # Get MSFT test stock
    with db_manager.get_session() as session:
        stock = session.query(Stock).filter_by(ticker="MSFT").first()
        assert stock is not None, "MSFT stock not found in database"

        # Extract attributes while still in session
        stock_id = str(stock.stock_id)
        ticker = stock.ticker
        company_name = stock.company_name

    # Create input state
    input_state = BatchGraphState(
        stock_id=stock_id,
        ticker=ticker,
        company_name=company_name,
        batch_run_id="test-run-msft"
    )

    # Run graph
    result = await batch_graph.ainvoke(input_state.model_dump())

    # Verify successful completion
    assert result['storage_status'] == 'stored'
    assert result['summary_id'] is not None


@pytest.mark.asyncio
async def test_no_edgar_data():
    """Test pipeline handles stocks with no EDGAR data gracefully"""

    # Create a fake stock that won't have mocked data
    input_state = BatchGraphState(
        stock_id="fake-id",
        ticker="NODATA",
        company_name="No Data Corp",
        batch_run_id="test-no-data"
    )

    # Run graph
    result = await batch_graph.ainvoke(input_state.model_dump())

    # Should complete but may have errors
    assert 'storage_status' in result
    # With no data, summary generation should fail
    assert result.get('medium_summary') is None or result.get('error_message') is not None


def test_graph_compilation():
    """Test that the batch graph compiles without errors"""
    from src.batch.graphs.single_source_batch import batch_graph

    assert batch_graph is not None
    assert hasattr(batch_graph, 'ainvoke')
    assert hasattr(batch_graph, 'invoke')
