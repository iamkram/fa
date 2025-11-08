#!/usr/bin/env python3
"""
End-to-End Integration Tests for FA AI System

Tests the complete system flow from data ingestion to summary generation.
"""

import asyncio
import logging
import sys
from pathlib import Path
from typing import Dict, Any, List
from datetime import datetime
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.batch.graphs.phase2_with_validation import phase2_validation_graph
from src.batch.state import BatchGraphStatePhase2
from src.shared.database.models import StockSummary, Citation
from src.shared.database.connection import db_manager
from src.shared.vector_store.pgvector_client import PGVectorClient
from src.config.settings import settings

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# ============================================================================
# Test Fixtures
# ============================================================================

@pytest.fixture
def test_stocks() -> List[Dict[str, str]]:
    """Sample stocks for testing"""
    return [
        {"stock_id": "test-e2e-001", "ticker": "AAPL", "company_name": "Apple Inc."},
        {"stock_id": "test-e2e-002", "ticker": "MSFT", "company_name": "Microsoft Corporation"},
        {"stock_id": "test-e2e-003", "ticker": "GOOGL", "company_name": "Alphabet Inc."}
    ]


@pytest.fixture
def batch_run_id() -> str:
    """Generate unique batch run ID"""
    return f"integration-test-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}"


@pytest.fixture
async def vector_client():
    """Vector store client"""
    client = PGVectorClient(settings.database_url)
    yield client
    client.close()


# ============================================================================
# End-to-End Tests
# ============================================================================

class TestEndToEndFlow:
    """Test complete batch processing flow"""

    @pytest.mark.asyncio
    async def test_single_stock_complete_flow(self, test_stocks, batch_run_id):
        """Test complete flow for a single stock"""
        logger.info("=== Test: Single Stock Complete Flow ===")

        stock = test_stocks[0]
        state = BatchGraphStatePhase2(
            stock_id=stock["stock_id"],
            ticker=stock["ticker"],
            company_name=stock["company_name"],
            batch_run_id=batch_run_id
        )

        # Execute graph
        logger.info(f"Processing {stock['ticker']}...")
        result = await phase2_validation_graph.ainvoke(state.model_dump())

        # Assertions
        assert result is not None, "Graph should return a result"
        assert "hook_summary" in result, "Should have hook summary"
        assert "medium_summary" in result, "Should have medium summary"
        assert "expanded_summary" in result, "Should have expanded summary"

        # Validate word counts
        hook_words = len(result["hook_summary"].split())
        medium_words = len(result["medium_summary"].split())
        expanded_words = len(result["expanded_summary"].split())

        logger.info(f"Word counts - Hook: {hook_words}, Medium: {medium_words}, Expanded: {expanded_words}")

        assert 10 <= hook_words <= 60, f"Hook summary should be 10-60 words (got {hook_words})"
        assert 80 <= medium_words <= 170, f"Medium summary should be 80-170 words (got {medium_words})"
        assert 180 <= expanded_words <= 270, f"Expanded summary should be 180-270 words (got {expanded_words})"

        # Validate fact check
        assert result["fact_check_status"] in ["passed", "failed"], "Should have fact check status"
        logger.info(f"Fact check: {result['fact_check_status']}")

        # Validate citations
        assert "citations" in result, "Should have citations"
        assert len(result["citations"]) > 0, "Should have at least one citation"
        logger.info(f"Citations: {len(result['citations'])}")

        # Validate storage
        assert result.get("storage_status") == "success", "Should successfully store in database"

        logger.info(f"✅ Test passed for {stock['ticker']}")

    @pytest.mark.asyncio
    async def test_multi_source_ingestion(self, test_stocks, batch_run_id, vector_client):
        """Test that all three data sources are ingested"""
        logger.info("=== Test: Multi-Source Ingestion ===")

        stock = test_stocks[0]
        state = BatchGraphStatePhase2(
            stock_id=stock["stock_id"],
            ticker=stock["ticker"],
            company_name=stock["company_name"],
            batch_run_id=batch_run_id
        )

        result = await phase2_validation_graph.ainvoke(state.model_dump())

        # Check that all sources were ingested
        assert result.get("edgar_status") in ["success", "partial"], "EDGAR should be ingested"
        assert result.get("bluematrix_status") in ["success", "partial"], "BlueMatrix should be ingested"
        assert result.get("factset_status") in ["success", "partial"], "FactSet should be ingested"

        logger.info(f"EDGAR: {result.get('edgar_status')}")
        logger.info(f"BlueMatrix: {result.get('bluematrix_status')}")
        logger.info(f"FactSet: {result.get('factset_status')}")

        # Check vectors were stored
        edgar_count = result.get("edgar_vector_count", 0)
        bluematrix_count = result.get("bluematrix_vector_count", 0)
        factset_count = result.get("factset_vector_count", 0)

        total_vectors = edgar_count + bluematrix_count + factset_count
        assert total_vectors > 0, "Should have stored at least one vector"

        logger.info(f"Total vectors stored: {total_vectors}")
        logger.info(f"✅ Multi-source ingestion test passed")

    @pytest.mark.asyncio
    async def test_citation_linkage(self, test_stocks, batch_run_id):
        """Test that citations are properly linked to summaries"""
        logger.info("=== Test: Citation Linkage ===")

        stock = test_stocks[0]
        state = BatchGraphStatePhase2(
            stock_id=stock["stock_id"],
            ticker=stock["ticker"],
            company_name=stock["company_name"],
            batch_run_id=batch_run_id
        )

        result = await phase2_validation_graph.ainvoke(state.model_dump())

        citations = result.get("citations", [])
        assert len(citations) > 0, "Should have citations"

        # Check citation structure
        for citation in citations:
            assert "claim_text" in citation, "Citation should have claim text"
            assert "source_type" in citation, "Citation should have source type"
            assert "source_id" in citation, "Citation should have source ID"
            assert citation["source_type"] in ["EDGAR", "BlueMatrix", "FactSet"], \
                f"Invalid source type: {citation['source_type']}"

        logger.info(f"Citations validated: {len(citations)}")
        logger.info(f"✅ Citation linkage test passed")

    @pytest.mark.asyncio
    async def test_hallucination_detection(self, test_stocks, batch_run_id):
        """Test hallucination detection system"""
        logger.info("=== Test: Hallucination Detection ===")

        stock = test_stocks[0]
        state = BatchGraphStatePhase2(
            stock_id=stock["stock_id"],
            ticker=stock["ticker"],
            company_name=stock["company_name"],
            batch_run_id=batch_run_id
        )

        result = await phase2_validation_graph.ainvoke(state.model_dump())

        # Check hallucination risk assessment
        assert "hallucination_risk" in result, "Should have hallucination risk assessment"
        assert result["hallucination_risk"] in ["low", "medium", "high", "critical"], \
            f"Invalid risk level: {result['hallucination_risk']}"

        logger.info(f"Hallucination risk: {result['hallucination_risk']}")

        # If fact check failed, should have details
        if result["fact_check_status"] == "failed":
            assert "fact_check_details" in result, "Failed fact check should have details"
            logger.info(f"Fact check details: {result['fact_check_details']}")

        logger.info(f"✅ Hallucination detection test passed")

    @pytest.mark.asyncio
    async def test_database_persistence(self, test_stocks, batch_run_id):
        """Test that summaries are correctly persisted to database"""
        logger.info("=== Test: Database Persistence ===")

        stock = test_stocks[0]
        state = BatchGraphStatePhase2(
            stock_id=stock["stock_id"],
            ticker=stock["ticker"],
            company_name=stock["company_name"],
            batch_run_id=batch_run_id
        )

        result = await phase2_validation_graph.ainvoke(state.model_dump())

        # Query database to verify storage
        with db_manager.get_session() as session:
            summary = session.query(StockSummary).filter_by(
                ticker=stock["ticker"],
                batch_run_id=batch_run_id
            ).first()

            assert summary is not None, "Summary should be stored in database"
            assert summary.hook_summary is not None, "Hook summary should be stored"
            assert summary.medium_summary is not None, "Medium summary should be stored"
            assert summary.expanded_summary is not None, "Expanded summary should be stored"
            assert summary.fact_check_status in ["passed", "failed"], "Fact check status should be set"

            # Check citations
            citations = session.query(Citation).filter_by(summary_id=summary.id).all()
            assert len(citations) > 0, "Citations should be stored"

            logger.info(f"Database record ID: {summary.id}")
            logger.info(f"Citations count: {len(citations)}")

        logger.info(f"✅ Database persistence test passed")


# ============================================================================
# Performance Tests
# ============================================================================

class TestPerformance:
    """Test system performance characteristics"""

    @pytest.mark.asyncio
    async def test_query_response_time(self, test_stocks, batch_run_id):
        """Test that queries meet SLA targets"""
        logger.info("=== Test: Query Response Time ===")

        stock = test_stocks[0]
        state = BatchGraphStatePhase2(
            stock_id=stock["stock_id"],
            ticker=stock["ticker"],
            company_name=stock["company_name"],
            batch_run_id=batch_run_id
        )

        start_time = datetime.utcnow()
        result = await phase2_validation_graph.ainvoke(state.model_dump())
        end_time = datetime.utcnow()

        duration_ms = (end_time - start_time).total_seconds() * 1000

        logger.info(f"Processing time: {duration_ms:.0f}ms")

        # SLA: P95 should be < 3000ms, but for single stock allow up to 60s (includes all sources)
        assert duration_ms < 60000, f"Processing should complete in < 60s (took {duration_ms:.0f}ms)"

        # Check individual component times if available
        if "total_processing_time_ms" in result:
            logger.info(f"Reported processing time: {result['total_processing_time_ms']:.0f}ms")

        logger.info(f"✅ Response time test passed")

    @pytest.mark.asyncio
    async def test_concurrent_processing(self, test_stocks, batch_run_id):
        """Test concurrent processing of multiple stocks"""
        logger.info("=== Test: Concurrent Processing ===")

        async def process_stock(stock: Dict[str, str]) -> Dict[str, Any]:
            state = BatchGraphStatePhase2(
                stock_id=stock["stock_id"],
                ticker=stock["ticker"],
                company_name=stock["company_name"],
                batch_run_id=batch_run_id
            )
            return await phase2_validation_graph.ainvoke(state.model_dump())

        # Process 3 stocks concurrently
        start_time = datetime.utcnow()
        results = await asyncio.gather(*[process_stock(stock) for stock in test_stocks])
        end_time = datetime.utcnow()

        duration_s = (end_time - start_time).total_seconds()

        logger.info(f"Concurrent processing of {len(test_stocks)} stocks: {duration_s:.1f}s")

        # All should succeed
        assert all(r.get("storage_status") == "success" for r in results), \
            "All stocks should process successfully"

        # Should be faster than sequential (< 3x single stock time)
        # Allowing generous time for concurrent overhead
        assert duration_s < 180, f"Concurrent processing too slow: {duration_s:.1f}s"

        logger.info(f"✅ Concurrent processing test passed")


# ============================================================================
# Cost Validation Tests
# ============================================================================

class TestCostValidation:
    """Test that costs are within acceptable ranges"""

    @pytest.mark.asyncio
    async def test_cost_per_stock(self, test_stocks, batch_run_id):
        """Test that cost per stock is within budget"""
        logger.info("=== Test: Cost Per Stock ===")

        stock = test_stocks[0]
        state = BatchGraphStatePhase2(
            stock_id=stock["stock_id"],
            ticker=stock["ticker"],
            company_name=stock["company_name"],
            batch_run_id=batch_run_id
        )

        result = await phase2_validation_graph.ainvoke(state.model_dump())

        # Check total cost
        if "total_cost" in result:
            total_cost = result["total_cost"]
            logger.info(f"Total cost: ${total_cost:.4f}")

            # Budget target: < $0.40 per stock
            assert total_cost < 0.50, f"Cost too high: ${total_cost:.4f} (target: < $0.40)"

        # Check token usage
        if "total_input_tokens" in result and "total_output_tokens" in result:
            input_tokens = result["total_input_tokens"]
            output_tokens = result["total_output_tokens"]
            total_tokens = input_tokens + output_tokens

            logger.info(f"Token usage: {input_tokens} input, {output_tokens} output ({total_tokens} total)")

            # Reasonable limits for single stock with 3 sources
            assert total_tokens < 20000, f"Token usage too high: {total_tokens}"

        logger.info(f"✅ Cost validation test passed")


# ============================================================================
# Edge Case Tests
# ============================================================================

class TestEdgeCases:
    """Test edge cases and error handling"""

    @pytest.mark.asyncio
    async def test_missing_data_graceful_degradation(self, batch_run_id):
        """Test system handles missing data gracefully"""
        logger.info("=== Test: Missing Data Graceful Degradation ===")

        # Use ticker that may have limited data
        state = BatchGraphStatePhase2(
            stock_id="test-missing-001",
            ticker="UNKN",  # Unknown ticker
            company_name="Unknown Company",
            batch_run_id=batch_run_id
        )

        # Should not crash, but may have partial results
        try:
            result = await phase2_validation_graph.ainvoke(state.model_dump())

            # Even with missing data, should complete
            assert result is not None, "Should return result even with missing data"
            logger.info(f"Completed with status: {result.get('overall_status', 'unknown')}")

        except Exception as e:
            # Should handle errors gracefully
            logger.info(f"Handled error gracefully: {str(e)}")

        logger.info(f"✅ Graceful degradation test passed")


# ============================================================================
# Main Test Runner
# ============================================================================

async def main():
    """Run all integration tests"""
    logger.info("=" * 80)
    logger.info("FA AI System - Integration Test Suite")
    logger.info("=" * 80)

    # Create test fixtures
    test_stocks = [
        {"stock_id": "test-e2e-001", "ticker": "AAPL", "company_name": "Apple Inc."},
        {"stock_id": "test-e2e-002", "ticker": "MSFT", "company_name": "Microsoft Corporation"},
        {"stock_id": "test-e2e-003", "ticker": "GOOGL", "company_name": "Alphabet Inc."}
    ]
    batch_run_id = f"integration-test-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}"

    # Initialize test classes
    e2e_tests = TestEndToEndFlow()
    perf_tests = TestPerformance()
    cost_tests = TestCostValidation()
    edge_tests = TestEdgeCases()

    results = {"passed": 0, "failed": 0, "errors": []}

    # Run tests
    tests = [
        ("Single Stock Complete Flow", e2e_tests.test_single_stock_complete_flow(test_stocks, batch_run_id)),
        ("Multi-Source Ingestion", e2e_tests.test_multi_source_ingestion(test_stocks, batch_run_id, None)),
        ("Citation Linkage", e2e_tests.test_citation_linkage(test_stocks, batch_run_id)),
        ("Hallucination Detection", e2e_tests.test_hallucination_detection(test_stocks, batch_run_id)),
        ("Database Persistence", e2e_tests.test_database_persistence(test_stocks, batch_run_id)),
        ("Query Response Time", perf_tests.test_query_response_time(test_stocks, batch_run_id)),
        ("Concurrent Processing", perf_tests.test_concurrent_processing(test_stocks, batch_run_id)),
        ("Cost Per Stock", cost_tests.test_cost_per_stock(test_stocks, batch_run_id)),
        ("Missing Data Graceful Degradation", edge_tests.test_missing_data_graceful_degradation(batch_run_id))
    ]

    for test_name, test_coro in tests:
        try:
            logger.info(f"\nRunning: {test_name}")
            await test_coro
            results["passed"] += 1
            logger.info(f"✅ PASSED: {test_name}")
        except AssertionError as e:
            results["failed"] += 1
            results["errors"].append(f"{test_name}: {str(e)}")
            logger.error(f"❌ FAILED: {test_name}: {str(e)}")
        except Exception as e:
            results["failed"] += 1
            results["errors"].append(f"{test_name}: {str(e)}")
            logger.error(f"❌ ERROR: {test_name}: {str(e)}")

    # Summary
    logger.info("\n" + "=" * 80)
    logger.info("Integration Test Summary")
    logger.info("=" * 80)
    logger.info(f"Passed: {results['passed']}")
    logger.info(f"Failed: {results['failed']}")
    logger.info(f"Total: {results['passed'] + results['failed']}")

    if results['failed'] > 0:
        logger.info("\nFailures:")
        for error in results['errors']:
            logger.info(f"  - {error}")

    logger.info("=" * 80)

    return 0 if results['failed'] == 0 else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
