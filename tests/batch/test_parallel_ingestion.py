"""Tests for Phase 2 parallel ingestion graph"""

import pytest
from datetime import datetime

from src.batch.state import BatchGraphStatePhase2
from src.batch.graphs.parallel_ingestion import parallel_ingestion_graph


@pytest.mark.asyncio
async def test_parallel_ingestion_graph_compilation():
    """Test that parallel ingestion graph compiles successfully"""
    assert parallel_ingestion_graph is not None
    # Graph should have nodes for all 3 sources
    assert "edgar_ingest" in parallel_ingestion_graph.nodes
    assert "bluematrix_ingest" in parallel_ingestion_graph.nodes
    assert "factset_ingest" in parallel_ingestion_graph.nodes


@pytest.mark.asyncio
async def test_parallel_ingestion_aapl():
    """Test parallel ingestion for AAPL with all 3 sources"""

    input_state = BatchGraphStatePhase2(
        stock_id="test-stock-id",
        ticker="AAPL",
        company_name="Apple Inc.",
        batch_run_id="test-parallel-run"
    )

    # Run the parallel ingestion graph
    result = await parallel_ingestion_graph.ainvoke(input_state.model_dump())

    # Verify all sources were processed
    assert result["edgar_status"] in ["success", "partial"]
    assert result["bluematrix_status"] in ["success", "partial"]
    assert result["factset_status"] in ["success", "partial"]

    # Verify EDGAR data (should have mocked data for AAPL)
    assert "edgar_filings" in result
    assert len(result["edgar_filings"]) > 0
    assert result["edgar_filings"][0].filing_type == "8-K"

    # Verify vector IDs were created
    assert "edgar_vector_ids" in result
    assert len(result["edgar_vector_ids"]) > 0


@pytest.mark.asyncio
async def test_parallel_ingestion_msft():
    """Test parallel ingestion for MSFT"""

    input_state = BatchGraphStatePhase2(
        stock_id="test-stock-id-2",
        ticker="MSFT",
        company_name="Microsoft Corporation",
        batch_run_id="test-parallel-run-2"
    )

    result = await parallel_ingestion_graph.ainvoke(input_state.model_dump())

    # MSFT should have mocked 10-Q filing
    assert result["edgar_status"] == "success"
    assert len(result["edgar_filings"]) > 0
    assert result["edgar_filings"][0].filing_type == "10-Q"


@pytest.mark.asyncio
async def test_parallel_ingestion_unknown_ticker():
    """Test parallel ingestion with unknown ticker"""

    input_state = BatchGraphStatePhase2(
        stock_id="test-stock-id-3",
        ticker="UNKNOWN",
        company_name="Unknown Company",
        batch_run_id="test-parallel-run-3"
    )

    result = await parallel_ingestion_graph.ainvoke(input_state.model_dump())

    # Unknown ticker should return partial/failed status
    assert result["edgar_status"] in ["partial", "failed"]
    # But graph should complete without errors
    assert "edgar_filings" in result


@pytest.mark.asyncio
async def test_parallel_ingestion_state_accumulation():
    """Test that parallel branches properly accumulate state"""

    input_state = BatchGraphStatePhase2(
        stock_id="test-stock-id-4",
        ticker="AAPL",
        company_name="Apple Inc.",
        batch_run_id="test-accumulation"
    )

    result = await parallel_ingestion_graph.ainvoke(input_state.model_dump())

    # Verify state accumulated from all parallel branches
    # EDGAR
    assert isinstance(result["edgar_filings"], list)
    assert isinstance(result["edgar_vector_ids"], list)

    # BlueMatrix
    assert isinstance(result["bluematrix_reports"], list)
    assert isinstance(result["bluematrix_vector_ids"], list)

    # FactSet
    assert isinstance(result["factset_events"], list)
    assert isinstance(result["factset_vector_ids"], list)

    # All should be from same stock
    assert result["ticker"] == "AAPL"
    assert result["stock_id"] == "test-stock-id-4"


@pytest.mark.asyncio
async def test_parallel_ingestion_vectorization():
    """Test that vectorization happens after ingestion for all sources"""

    input_state = BatchGraphStatePhase2(
        stock_id="test-stock-id-5",
        ticker="GOOGL",
        company_name="Alphabet Inc.",
        batch_run_id="test-vectorization"
    )

    result = await parallel_ingestion_graph.ainvoke(input_state.model_dump())

    # If we have filings, we should have vectors
    if len(result["edgar_filings"]) > 0:
        assert len(result["edgar_vector_ids"]) > 0, "EDGAR vectors should be created"

    # If we have reports, we should have vectors
    if len(result["bluematrix_reports"]) > 0:
        assert len(result["bluematrix_vector_ids"]) > 0, "BlueMatrix vectors should be created"

    # FactSet always creates at least one vector for price data
    if result["factset_price_data"] is not None:
        assert len(result["factset_vector_ids"]) > 0, "FactSet vectors should be created"
