"""
Batch Assistant Graph - Scheduled nightly processing of stock summaries

This graph orchestrates the nightly batch job that processes all stocks
and generates 3-tier summaries with multi-source data integration.

Trigger: 2 AM local time daily
"""

from langgraph.graph import StateGraph, START, END
from typing import TypedDict, Annotated
import logging
from datetime import datetime
import asyncio

from src.batch.state import BatchGraphStatePhase2
from src.batch.graphs.phase2_with_validation import phase2_validation_graph
from src.shared.database.connection import db_manager
from src.shared.models.database import Stock, BatchRunAudit
import uuid

logger = logging.getLogger(__name__)


class BatchAssistantState(TypedDict):
    """State for batch assistant orchestrator"""
    trigger_time: str
    stocks_to_process: list[str]
    processed_count: int
    failed_count: int
    batch_run_id: str
    status: str
    error_message: str | None


async def initialize_batch_run(state: BatchAssistantState) -> BatchAssistantState:
    """Initialize the batch run and fetch stocks to process"""
    logger.info("🚀 Initializing nightly batch run at 2 AM")

    batch_run_id = str(uuid.uuid4())

    # Get all stocks from database
    with db_manager.get_session() as session:
        stocks = session.query(Stock).all()
        stock_tickers = [stock.ticker for stock in stocks]

        # Create batch run audit record
        batch_audit = BatchRunAudit(
            batch_run_id=batch_run_id,
            run_date=datetime.now(),
            status="RUNNING",
            total_stocks=len(stock_tickers)
        )
        session.add(batch_audit)
        session.commit()

    logger.info(f"📊 Found {len(stock_tickers)} stocks to process")

    return {
        **state,
        "batch_run_id": batch_run_id,
        "stocks_to_process": stock_tickers,
        "processed_count": 0,
        "failed_count": 0,
        "status": "RUNNING"
    }


async def process_all_stocks(state: BatchAssistantState) -> BatchAssistantState:
    """Process all stocks through the Phase 2 pipeline with validation"""
    from src.batch.orchestrator.concurrent_batch import ConcurrentBatchOrchestrator

    logger.info(f"⚙️ Processing {len(state['stocks_to_process'])} stocks concurrently")

    try:
        # Use concurrent orchestrator for parallel processing
        orchestrator = ConcurrentBatchOrchestrator(
            graph=phase2_validation_graph,
            max_workers=5  # Process 5 stocks at a time
        )

        with db_manager.get_session() as session:
            stocks = session.query(Stock).filter(
                Stock.ticker.in_(state['stocks_to_process'])
            ).all()

            results = await orchestrator.run_batch(
                stocks=stocks,
                batch_run_id=state['batch_run_id']
            )

            processed = sum(1 for r in results if r.get("status") == "success")
            failed = sum(1 for r in results if r.get("status") == "failed")

        logger.info(f"✅ Batch complete: {processed} succeeded, {failed} failed")

        return {
            **state,
            "processed_count": processed,
            "failed_count": failed,
            "status": "COMPLETED"
        }

    except Exception as e:
        logger.error(f"❌ Batch processing failed: {e}")
        return {
            **state,
            "status": "FAILED",
            "error_message": str(e)
        }


async def finalize_batch_run(state: BatchAssistantState) -> BatchAssistantState:
    """Finalize the batch run and update audit records"""
    logger.info("📝 Finalizing batch run")

    with db_manager.get_session() as session:
        batch_audit = session.query(BatchRunAudit).filter(
            BatchRunAudit.batch_run_id == state['batch_run_id']
        ).first()

        if batch_audit:
            batch_audit.status = state['status']
            batch_audit.stocks_processed = state['processed_count']
            batch_audit.stocks_failed = state['failed_count']
            batch_audit.end_time = datetime.now()
            if state.get('error_message'):
                batch_audit.error_message = state['error_message']
            session.commit()

    logger.info(f"🎉 Batch run {state['batch_run_id']} finalized with status: {state['status']}")

    return state


def create_batch_assistant_graph():
    """
    Create the batch assistant graph for scheduled nightly processing

    This graph runs daily at 2 AM and:
    1. Initializes a new batch run
    2. Processes all stocks with Phase 2 pipeline (with validation)
    3. Finalizes and logs the batch run results
    """
    builder = StateGraph(BatchAssistantState)

    # Add nodes
    builder.add_node("initialize", initialize_batch_run)
    builder.add_node("process_stocks", process_all_stocks)
    builder.add_node("finalize", finalize_batch_run)

    # Define flow
    builder.add_edge(START, "initialize")
    builder.add_edge("initialize", "process_stocks")
    builder.add_edge("process_stocks", "finalize")
    builder.add_edge("finalize", END)

    graph = builder.compile()

    logger.info("✅ Batch assistant graph compiled and ready for scheduled execution")

    return graph


# Export the compiled graph
batch_assistant_graph = create_batch_assistant_graph()
