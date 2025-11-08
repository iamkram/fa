#!/usr/bin/env python3
"""Run Phase 2 batch processing with multi-source data and 3-tier summaries

Supports:
- Multi-source data ingestion (EDGAR, BlueMatrix, FactSet)
- 3-tier summary generation (Hook, Medium, Expanded)
- LLM-based fact-checking (--validate flag)
- Retry logic with negative prompting (--validate flag)
- Concurrent processing (--concurrent flag)
"""

import asyncio
import sys
from pathlib import Path
import argparse
import logging
from datetime import datetime
import uuid
import os

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.config.settings import settings
from src.batch.graphs.phase2_graph import phase2_graph
from src.batch.graphs.phase2_with_validation import phase2_validation_graph
from src.batch.orchestrator.concurrent_batch import ConcurrentBatchOrchestrator
from src.batch.state import BatchGraphStatePhase2
from src.shared.database.connection import db_manager
from src.shared.models.database import Stock, BatchRunAudit

# Set LangSmith environment variables for tracing
os.environ["LANGCHAIN_TRACING_V2"] = str(settings.langsmith_tracing_v2)
os.environ["LANGCHAIN_API_KEY"] = settings.langsmith_api_key
# Use batch-specific project for better organization
os.environ["LANGCHAIN_PROJECT"] = f"{settings.langsmith_project}-batch"

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def process_stock(stock: Stock, batch_run_id: str, graph):
    """Process a single stock through the Phase 2 pipeline

    Args:
        stock: Stock model instance
        batch_run_id: Unique ID for this batch run
        graph: The LangGraph graph to execute (with or without validation)

    Returns:
        Result dictionary from graph execution
    """
    logger.info(f"{'='*60}")
    logger.info(f"Processing {stock.ticker} - {stock.company_name}")
    logger.info(f"{'='*60}")

    input_state = BatchGraphStatePhase2(
        stock_id=str(stock.stock_id),
        ticker=stock.ticker,
        company_name=stock.company_name,
        batch_run_id=batch_run_id
    )

    try:
        # Run the graph with LangSmith tracing configuration
        result = await graph.ainvoke(
            input_state.model_dump(),
            config={
                "run_name": f"batch_{stock.ticker}_{batch_run_id[:8]}",
                "metadata": {
                    "batch_run_id": batch_run_id,
                    "ticker": stock.ticker,
                    "company_name": stock.company_name,
                    "stock_id": str(stock.stock_id),
                    "mode": "batch",
                    "timestamp": datetime.utcnow().isoformat()
                },
                "tags": [
                    "batch-processing",
                    f"ticker:{stock.ticker}",
                    f"batch:{batch_run_id[:8]}",
                    "phase2"
                ]
            }
        )

        status = result.get('storage_status', 'unknown')

        # Log summary details
        hook_wc = result.get('hook_word_count', 0)
        medium_wc = result.get('medium_word_count', 0)
        expanded_wc = result.get('expanded_word_count', 0)

        logger.info(f"✅ Completed {stock.ticker}: {status}")
        logger.info(f"   Summaries: Hook({hook_wc}w), Medium({medium_wc}w), Expanded({expanded_wc}w)")

        # Log source status
        edgar_status = result.get('edgar_status', 'unknown')
        bluematrix_status = result.get('bluematrix_status', 'unknown')
        factset_status = result.get('factset_status', 'unknown')
        logger.info(f"   Sources: EDGAR={edgar_status}, BlueMatrix={bluematrix_status}, FactSet={factset_status}")

        return result

    except Exception as e:
        logger.error(f"❌ Failed {stock.ticker}: {str(e)}", exc_info=True)
        return {
            "storage_status": "failed",
            "error_message": str(e)
        }


async def run_batch(
    limit: int = None,
    ticker: str = None,
    validate: bool = False,
    concurrent: bool = False,
    max_concurrent: int = 5
):
    """Run Phase 2 batch process for stocks

    Args:
        limit: Optional limit on number of stocks to process
        ticker: Optional single ticker to process (for testing)
        validate: Enable fact-checking and retry logic
        concurrent: Enable concurrent processing
        max_concurrent: Maximum concurrent stocks (only if concurrent=True)
    """
    batch_run_id = str(uuid.uuid4())
    start_time = datetime.utcnow()

    # Configure LangSmith metadata for this batch run
    batch_metadata = {
        "batch_run_id": batch_run_id,
        "start_time": start_time.isoformat(),
        "limit": limit,
        "ticker": ticker,
        "validate": validate,
        "concurrent": concurrent,
        "max_concurrent": max_concurrent,
        "mode": "batch",
        "environment": os.environ.get("ENVIRONMENT", "development")
    }

    # Select graph based on validation flag
    graph = phase2_validation_graph if validate else phase2_graph

    features = ["Multi-source ingestion", "3-tier summaries"]
    if validate:
        features.append("Fact-checking")
        features.append("Retry logic")
    if concurrent:
        features.append(f"Concurrent ({max_concurrent} max)")

    logger.info(f"\n{'#'*60}")
    logger.info(f"PHASE 2 BATCH RUN: {batch_run_id}")
    logger.info(f"Time: {start_time}")
    logger.info(f"Features: {', '.join(features)}")
    logger.info(f"{'#'*60}\n")

    # Get stocks to process
    with db_manager.get_session() as session:
        query = session.query(Stock)

        if ticker:
            query = query.filter(Stock.ticker == ticker.upper())
        elif limit:
            query = query.limit(limit)

        stocks = query.all()

        # Extract stock data while still in session
        stock_data = [
            {
                "stock_id": str(s.stock_id),
                "ticker": s.ticker,
                "company_name": s.company_name
            }
            for s in stocks
        ]

    logger.info(f"Processing {len(stock_data)} stocks\n")

    if not stock_data:
        logger.warning("No stocks found in database!")
        return

    # Process stocks: concurrent or sequential
    if concurrent:
        # Use concurrent orchestrator
        orchestrator = ConcurrentBatchOrchestrator(
            graph=graph,
            max_concurrent=max_concurrent
        )

        # Add LangSmith metadata to orchestrator
        logger.info(f"LangSmith Tracing: Enabled")
        logger.info(f"LangSmith Project: {os.environ.get('LANGCHAIN_PROJECT')}")
        logger.info(f"Batch Run ID: {batch_run_id}")

        summary = await orchestrator.run(
            stocks=stock_data,
            batch_run_id=batch_run_id,
            batch_size=max_concurrent,
            metadata=batch_metadata
        )

        results = [
            {
                "storage_status": r.storage_status,
                "hook_word_count": r.hook_wc,
                "medium_word_count": r.medium_wc,
                "expanded_word_count": r.expanded_wc,
                "hook_fact_check": {"overall_status": r.hook_fact_check} if r.hook_fact_check else None,
                "medium_fact_check": {"overall_status": r.medium_fact_check} if r.medium_fact_check else None,
                "expanded_fact_check": {"overall_status": r.expanded_fact_check} if r.expanded_fact_check else None,
                "hook_retry_count": r.hook_retries,
                "medium_retry_count": r.medium_retries,
                "expanded_retry_count": r.expanded_retries
            }
            for r in summary["results"]
        ]

    else:
        # Sequential processing
        results = []
        for i, stock_info in enumerate(stock_data, 1):
            logger.info(f"\n[{i}/{len(stock_data)}] Starting {stock_info['ticker']}...")

            # Create Stock-like object for process_stock
            from types import SimpleNamespace
            stock = SimpleNamespace(**stock_info)

            result = await process_stock(stock, batch_run_id, graph)
            results.append(result)

    # Calculate statistics
    end_time = datetime.utcnow()
    successful = sum(1 for r in results if r.get('storage_status') == 'stored')
    failed = len(results) - successful
    duration = (end_time - start_time).total_seconds()

    # Calculate average word counts
    hook_avg = sum(r.get('hook_word_count', 0) for r in results if r.get('hook_word_count')) / max(successful, 1)
    medium_avg = sum(r.get('medium_word_count', 0) for r in results if r.get('medium_word_count')) / max(successful, 1)
    expanded_avg = sum(r.get('expanded_word_count', 0) for r in results if r.get('expanded_word_count')) / max(successful, 1)

    # Update audit log
    try:
        with db_manager.get_session() as session:
            audit = BatchRunAudit(
                run_id=batch_run_id,
                run_date=start_time.date(),
                start_timestamp=start_time,
                end_timestamp=end_time,
                total_stocks_processed=len(results),
                successful_summaries=successful,
                failed_summaries=failed
            )
            session.add(audit)
            session.commit()
            logger.info(f"✅ Audit record saved: {batch_run_id}")
    except Exception as e:
        logger.error(f"Failed to save audit record: {e}")

    # Print summary
    logger.info(f"\n{'#'*60}")
    logger.info(f"PHASE 2 BATCH RUN COMPLETE")
    logger.info(f"{'#'*60}")
    logger.info(f"Run ID: {batch_run_id}")
    logger.info(f"Duration: {duration:.1f}s")
    logger.info(f"Successful: {successful}/{len(results)}")
    logger.info(f"Failed: {failed}/{len(results)}")
    logger.info(f"Success Rate: {(successful/len(results)*100):.1f}%")
    logger.info(f"\nAverage Word Counts:")
    logger.info(f"  Hook: {hook_avg:.0f} words")
    logger.info(f"  Medium: {medium_avg:.0f} words")
    logger.info(f"  Expanded: {expanded_avg:.0f} words")
    logger.info(f"{'#'*60}\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Run Phase 2 batch stock processing",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic: Process first 5 stocks (no validation)
  python3 src/batch/run_batch_phase2.py --limit 5

  # With validation: Fact-checking and retry logic
  python3 src/batch/run_batch_phase2.py --limit 5 --validate

  # Concurrent: Process 5 stocks with 3 max concurrent
  python3 src/batch/run_batch_phase2.py --limit 5 --concurrent --max-concurrent 3

  # Full power: Validation + concurrency
  python3 src/batch/run_batch_phase2.py --limit 10 --validate --concurrent --max-concurrent 5

  # Test single stock with all features
  python3 src/batch/run_batch_phase2.py --ticker AAPL --validate
        """
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Limit number of stocks to process (default: all)"
    )
    parser.add_argument(
        "--ticker",
        type=str,
        help="Process a single ticker (e.g., AAPL)"
    )
    parser.add_argument(
        "--validate",
        action="store_true",
        help="Enable fact-checking and retry logic with negative prompting"
    )
    parser.add_argument(
        "--concurrent",
        action="store_true",
        help="Enable concurrent processing of stocks"
    )
    parser.add_argument(
        "--max-concurrent",
        type=int,
        default=100,
        help="Maximum number of concurrent stocks (default: 100 for Phase 4 production scaling)"
    )
    args = parser.parse_args()

    asyncio.run(run_batch(
        limit=args.limit,
        ticker=args.ticker,
        validate=args.validate,
        concurrent=args.concurrent,
        max_concurrent=args.max_concurrent
    ))
