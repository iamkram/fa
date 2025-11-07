"""
Concurrent Batch Orchestrator

Processes multiple stocks in parallel with configurable concurrency limits.
Handles rate limiting, error recovery, and progress tracking.
"""

import asyncio
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from dataclasses import dataclass
import uuid

from src.batch.state import BatchGraphStatePhase2
from src.shared.database.connection import db_manager
from src.shared.models.database import Stock

logger = logging.getLogger(__name__)


@dataclass
class StockTask:
    """Single stock processing task"""
    stock_id: str
    ticker: str
    company_name: str
    batch_run_id: str


@dataclass
class BatchResult:
    """Result of processing a single stock"""
    ticker: str
    success: bool
    storage_status: Optional[str] = None
    hook_wc: int = 0
    medium_wc: int = 0
    expanded_wc: int = 0
    hook_fact_check: Optional[str] = None
    medium_fact_check: Optional[str] = None
    expanded_fact_check: Optional[str] = None
    hook_retries: int = 0
    medium_retries: int = 0
    expanded_retries: int = 0
    error_message: Optional[str] = None
    processing_time_ms: int = 0


class ConcurrentBatchOrchestrator:
    """Orchestrates parallel processing of multiple stocks"""

    def __init__(
        self,
        graph,
        max_concurrent: int = 5,
        retry_on_error: bool = True
    ):
        """
        Initialize orchestrator

        Args:
            graph: The LangGraph graph to execute for each stock
            max_concurrent: Maximum number of stocks to process concurrently
            retry_on_error: Whether to retry failed stocks once
        """
        self.graph = graph
        self.max_concurrent = max_concurrent
        self.retry_on_error = retry_on_error

        # Semaphore to limit concurrency
        self.semaphore = asyncio.Semaphore(max_concurrent)

        # Track results
        self.results: List[BatchResult] = []
        self.failed_tasks: List[StockTask] = []

    async def process_stock(self, task: StockTask) -> BatchResult:
        """Process a single stock through the graph

        Args:
            task: Stock task to process

        Returns:
            BatchResult with processing outcome
        """
        start_time = datetime.utcnow()

        async with self.semaphore:
            logger.info(f"[Concurrent] Processing {task.ticker}")

            input_state = BatchGraphStatePhase2(
                stock_id=task.stock_id,
                ticker=task.ticker,
                company_name=task.company_name,
                batch_run_id=task.batch_run_id
            )

            try:
                # Run the graph
                result = await self.graph.ainvoke(input_state.model_dump())

                # Extract results
                end_time = datetime.utcnow()
                processing_time = int((end_time - start_time).total_seconds() * 1000)

                batch_result = BatchResult(
                    ticker=task.ticker,
                    success=result.get('storage_status') == 'stored',
                    storage_status=result.get('storage_status'),
                    hook_wc=result.get('hook_word_count', 0),
                    medium_wc=result.get('medium_word_count', 0),
                    expanded_wc=result.get('expanded_word_count', 0),
                    hook_fact_check=result.get('hook_fact_check', {}).get('overall_status') if result.get('hook_fact_check') else None,
                    medium_fact_check=result.get('medium_fact_check', {}).get('overall_status') if result.get('medium_fact_check') else None,
                    expanded_fact_check=result.get('expanded_fact_check', {}).get('overall_status') if result.get('expanded_fact_check') else None,
                    hook_retries=result.get('hook_retry_count', 0),
                    medium_retries=result.get('medium_retry_count', 0),
                    expanded_retries=result.get('expanded_retry_count', 0),
                    processing_time_ms=processing_time
                )

                logger.info(
                    f"✅ {task.ticker}: {batch_result.storage_status} "
                    f"(Hook:{batch_result.hook_wc}w, Medium:{batch_result.medium_wc}w, "
                    f"Expanded:{batch_result.expanded_wc}w, {processing_time}ms)"
                )

                return batch_result

            except Exception as e:
                logger.error(f"❌ {task.ticker} failed: {str(e)}")

                end_time = datetime.utcnow()
                processing_time = int((end_time - start_time).total_seconds() * 1000)

                return BatchResult(
                    ticker=task.ticker,
                    success=False,
                    error_message=str(e),
                    processing_time_ms=processing_time
                )

    async def process_batch(
        self,
        tasks: List[StockTask],
        batch_num: int,
        total_batches: int
    ) -> List[BatchResult]:
        """Process a batch of stocks concurrently

        Args:
            tasks: List of stock tasks to process
            batch_num: Current batch number (1-indexed)
            total_batches: Total number of batches

        Returns:
            List of batch results
        """
        logger.info(
            f"\n[Batch {batch_num}/{total_batches}] Processing {len(tasks)} stocks "
            f"(max {self.max_concurrent} concurrent)"
        )

        # Create tasks for all stocks in batch
        coroutines = [self.process_stock(task) for task in tasks]

        # Execute concurrently
        results = await asyncio.gather(*coroutines, return_exceptions=True)

        # Handle any exceptions
        batch_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Task exception for {tasks[i].ticker}: {result}")
                batch_results.append(BatchResult(
                    ticker=tasks[i].ticker,
                    success=False,
                    error_message=str(result)
                ))
            else:
                batch_results.append(result)

        # Log batch summary
        successful = sum(1 for r in batch_results if r.success)
        logger.info(
            f"[Batch {batch_num}/{total_batches}] Complete: "
            f"{successful}/{len(batch_results)} successful"
        )

        return batch_results

    async def run(
        self,
        stocks: List[Dict[str, str]],
        batch_run_id: str,
        batch_size: Optional[int] = None
    ) -> Dict[str, Any]:
        """Run concurrent batch processing for all stocks

        Args:
            stocks: List of dicts with stock_id, ticker, company_name
            batch_run_id: Unique ID for this batch run
            batch_size: Size of each processing batch (default: max_concurrent)

        Returns:
            Dict with summary statistics
        """
        if batch_size is None:
            batch_size = self.max_concurrent

        # Create tasks
        tasks = [
            StockTask(
                stock_id=stock['stock_id'],
                ticker=stock['ticker'],
                company_name=stock['company_name'],
                batch_run_id=batch_run_id
            )
            for stock in stocks
        ]

        # Divide into batches
        batches = [
            tasks[i:i + batch_size]
            for i in range(0, len(tasks), batch_size)
        ]

        total_batches = len(batches)
        logger.info(
            f"\n{'='*80}\n"
            f"CONCURRENT BATCH PROCESSING\n"
            f"Total stocks: {len(tasks)}\n"
            f"Batch size: {batch_size}\n"
            f"Max concurrent: {self.max_concurrent}\n"
            f"Total batches: {total_batches}\n"
            f"{'='*80}\n"
        )

        # Process all batches
        all_results = []
        for batch_num, batch in enumerate(batches, 1):
            batch_results = await self.process_batch(batch, batch_num, total_batches)
            all_results.extend(batch_results)

        # Calculate statistics
        successful = sum(1 for r in all_results if r.success)
        failed = len(all_results) - successful

        hook_avg = sum(r.hook_wc for r in all_results if r.hook_wc > 0) / max(successful, 1)
        medium_avg = sum(r.medium_wc for r in all_results if r.medium_wc > 0) / max(successful, 1)
        expanded_avg = sum(r.expanded_wc for r in all_results if r.expanded_wc > 0) / max(successful, 1)

        hook_retries_total = sum(r.hook_retries for r in all_results)
        medium_retries_total = sum(r.medium_retries for r in all_results)
        expanded_retries_total = sum(r.expanded_retries for r in all_results)

        # Fact-check pass rates
        hook_passed = sum(1 for r in all_results if r.hook_fact_check == "passed")
        medium_passed = sum(1 for r in all_results if r.medium_fact_check == "passed")
        expanded_passed = sum(1 for r in all_results if r.expanded_fact_check == "passed")

        avg_time = sum(r.processing_time_ms for r in all_results) / len(all_results)

        summary = {
            "total_stocks": len(all_results),
            "successful": successful,
            "failed": failed,
            "success_rate": successful / len(all_results) if all_results else 0,
            "avg_hook_words": hook_avg,
            "avg_medium_words": medium_avg,
            "avg_expanded_words": expanded_avg,
            "hook_retries": hook_retries_total,
            "medium_retries": medium_retries_total,
            "expanded_retries": expanded_retries_total,
            "hook_fact_check_pass_rate": hook_passed / max(successful, 1),
            "medium_fact_check_pass_rate": medium_passed / max(successful, 1),
            "expanded_fact_check_pass_rate": expanded_passed / max(successful, 1),
            "avg_processing_time_ms": avg_time,
            "results": all_results
        }

        logger.info(
            f"\n{'='*80}\n"
            f"BATCH PROCESSING COMPLETE\n"
            f"{'='*80}\n"
            f"Successful: {successful}/{len(all_results)} ({summary['success_rate']:.1%})\n"
            f"Failed: {failed}\n"
            f"\nWord Counts:\n"
            f"  Hook: {hook_avg:.0f} words (avg)\n"
            f"  Medium: {medium_avg:.0f} words (avg)\n"
            f"  Expanded: {expanded_avg:.0f} words (avg)\n"
            f"\nRetries:\n"
            f"  Hook: {hook_retries_total} total\n"
            f"  Medium: {medium_retries_total} total\n"
            f"  Expanded: {expanded_retries_total} total\n"
            f"\nFact-Check Pass Rates:\n"
            f"  Hook: {summary['hook_fact_check_pass_rate']:.1%}\n"
            f"  Medium: {summary['medium_fact_check_pass_rate']:.1%}\n"
            f"  Expanded: {summary['expanded_fact_check_pass_rate']:.1%}\n"
            f"\nPerformance:\n"
            f"  Avg time per stock: {avg_time:.0f}ms\n"
            f"{'='*80}\n"
        )

        return summary
