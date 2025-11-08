"""
Load Test Orchestrator - Manages Concurrent Load Testing

Simulates multiple concurrent financial advisors making queries to test system
performance and capacity. Tracks metrics and provides real-time progress updates.
"""

import asyncio
import httpx
import logging
import time
import statistics
from typing import Optional, Dict, Any, List, Callable
from datetime import datetime
from dataclasses import dataclass
from sqlalchemy import text

from src.config.settings import settings
from src.shared.database.connection import db_manager

logger = logging.getLogger(__name__)


@dataclass
class LoadTestConfig:
    """Configuration for a load test run"""
    test_name: str
    concurrent_users: int
    total_requests: int
    duration_seconds: Optional[int] = None
    query_type: str = "chat"
    initiated_by: str = "system"
    base_url: str = "http://localhost:8000"
    queries: Optional[List[str]] = None


@dataclass
class RequestMetric:
    """Metrics for a single request"""
    fa_id: str
    session_id: str
    query_text: str
    status_code: int
    success: bool
    response_time_ms: float
    error_message: Optional[str] = None
    langsmith_url: Optional[str] = None  # LangSmith trace URL for debugging
    sent_at: datetime = None
    completed_at: datetime = None


class LoadTestOrchestrator:
    """
    Orchestrates load testing with concurrent simulated users

    Features:
    - Concurrent request execution with asyncio
    - Real-time metrics collection
    - Database persistence of results
    - Progress callbacks for WebSocket streaming
    """

    def __init__(self):
        self.active_tests: Dict[int, asyncio.Task] = {}
        self.progress_callbacks: Dict[int, List[Callable]] = {}

    async def start_load_test(
        self,
        config: LoadTestConfig,
        progress_callback: Optional[Callable] = None
    ) -> int:
        """
        Start a new load test run

        Args:
            config: Load test configuration
            progress_callback: Optional callback for real-time updates

        Returns:
            run_id: ID of the created load test run
        """
        # Create database record
        run_id = self._create_run_record(config)

        # Register callback if provided
        if progress_callback:
            self.progress_callbacks[run_id] = [progress_callback]

        # Start test in background
        task = asyncio.create_task(self._execute_load_test(run_id, config))
        self.active_tests[run_id] = task

        logger.info(f"Started load test run {run_id}: {config.test_name}")
        return run_id

    async def stop_load_test(self, run_id: int):
        """Cancel a running load test"""
        if run_id in self.active_tests:
            self.active_tests[run_id].cancel()
            self._update_run_status(run_id, "cancelled")
            logger.info(f"Cancelled load test run {run_id}")

    def _create_run_record(self, config: LoadTestConfig) -> int:
        """Create initial database record for load test run"""
        with db_manager.get_session() as session:
            result = session.execute(
                text("""
                    INSERT INTO load_test_runs
                    (test_name, status, concurrent_users, total_requests,
                     duration_seconds, query_type, initiated_by, configuration)
                    VALUES (:name, 'pending', :users, :requests, :duration, :type, :by, :config)
                    RETURNING id
                """),
                {
                    "name": config.test_name,
                    "users": config.concurrent_users,
                    "requests": config.total_requests,
                    "duration": config.duration_seconds,
                    "type": config.query_type,
                    "by": config.initiated_by,
                    "config": "{}"
                }
            )
            run_id = result.fetchone()[0]
            session.commit()
            return run_id

    async def _execute_load_test(self, run_id: int, config: LoadTestConfig):
        """Execute the actual load test"""
        try:
            # Update status to running
            self._update_run_status(run_id, "running", started_at=datetime.utcnow())

            # Prepare queries
            queries = config.queries or [
                "What is the current stock price of Apple?",
                "Give me a summary of Tesla's recent performance",
                "What are the top tech stocks to watch?",
                "Analyze Microsoft's financial health",
                "What is the outlook for the S&P 500?"
            ]

            # Execute concurrent requests
            metrics: List[RequestMetric] = []

            # Divide total requests among concurrent users
            requests_per_user = config.total_requests // config.concurrent_users
            remainder = config.total_requests % config.concurrent_users

            # Create tasks for each simulated user
            user_tasks = []
            for user_idx in range(config.concurrent_users):
                user_requests = requests_per_user + (1 if user_idx < remainder else 0)
                task = self._simulate_user(
                    run_id=run_id,
                    user_idx=user_idx,
                    num_requests=user_requests,
                    queries=queries,
                    base_url=config.base_url,
                    query_type=config.query_type
                )
                user_tasks.append(task)

            # Execute all users concurrently
            results = await asyncio.gather(*user_tasks, return_exceptions=True)

            # Collect all metrics
            for result in results:
                if isinstance(result, list):
                    metrics.extend(result)
                elif isinstance(result, Exception):
                    logger.error(f"User simulation failed: {result}")

            # Calculate aggregate metrics
            await self._calculate_and_save_metrics(run_id, metrics)

            # Update status to completed
            self._update_run_status(run_id, "completed")

            # Notify via callback
            await self._notify_progress(run_id, {
                "status": "completed",
                "total_requests": len(metrics),
                "requests_completed": sum(1 for m in metrics if m.success),
                "requests_failed": sum(1 for m in metrics if not m.success)
            })

            logger.info(f"Load test {run_id} completed: {len(metrics)} requests")

        except asyncio.CancelledError:
            self._update_run_status(run_id, "cancelled")
            logger.info(f"Load test {run_id} was cancelled")
            raise
        except Exception as e:
            logger.error(f"Load test {run_id} failed: {e}")
            self._update_run_status(run_id, "failed")
            await self._notify_progress(run_id, {"status": "failed", "error": str(e)})
        finally:
            # Cleanup
            if run_id in self.active_tests:
                del self.active_tests[run_id]
            if run_id in self.progress_callbacks:
                del self.progress_callbacks[run_id]

    async def _simulate_user(
        self,
        run_id: int,
        user_idx: int,
        num_requests: int,
        queries: List[str],
        base_url: str,
        query_type: str
    ) -> List[RequestMetric]:
        """Simulate a single user making multiple requests"""
        metrics = []
        fa_id = f"FA-LOAD-{user_idx:04d}"
        session_id = f"load-test-{run_id}-user-{user_idx}"

        async with httpx.AsyncClient(timeout=120.0) as client:
            for req_idx in range(num_requests):
                query_text = queries[req_idx % len(queries)]

                metric = await self._make_request(
                    client=client,
                    base_url=base_url,
                    fa_id=fa_id,
                    session_id=session_id,
                    query_text=query_text,
                    query_type=query_type
                )

                metrics.append(metric)

                # Save to database immediately
                self._save_request_metric(run_id, metric)

                # Notify progress every 10 requests
                if len(metrics) % 10 == 0:
                    await self._notify_progress(run_id, {
                        "user_id": fa_id,
                        "requests_completed": len(metrics)
                    })

                # Small delay to avoid overwhelming the system
                await asyncio.sleep(0.1)

        return metrics

    async def _make_request(
        self,
        client: httpx.AsyncClient,
        base_url: str,
        fa_id: str,
        session_id: str,
        query_text: str,
        query_type: str
    ) -> RequestMetric:
        """Make a single HTTP request and measure performance"""
        sent_at = datetime.utcnow()
        start_time = time.perf_counter()

        try:
            response = await client.post(
                f"{base_url}/query",
                json={
                    "fa_id": fa_id,
                    "session_id": session_id,
                    "query_text": query_text,
                    "query_type": query_type
                },
                headers={"Content-Type": "application/json"}
            )

            end_time = time.perf_counter()
            response_time_ms = (end_time - start_time) * 1000

            # Extract LangSmith URL from response if available
            langsmith_url = None
            if response.status_code == 200:
                try:
                    response_data = response.json()
                    run_id = response_data.get("run_id")
                    if run_id:
                        # LangSmith URL format: use project filter to find the run
                        # Users can search for the run_id in their fa-ai-dev project
                        langsmith_url = f"https://smith.langchain.com/public/{run_id}/r"
                        # Alternative: Direct link (requires knowing org, but more reliable)
                        # For now, store the run_id so users can find it in LangSmith
                except Exception:
                    pass

            return RequestMetric(
                fa_id=fa_id,
                session_id=session_id,
                query_text=query_text,
                status_code=response.status_code,
                success=response.status_code == 200,
                response_time_ms=response_time_ms,
                langsmith_url=langsmith_url,
                sent_at=sent_at,
                completed_at=datetime.utcnow()
            )

        except Exception as e:
            end_time = time.perf_counter()
            response_time_ms = (end_time - start_time) * 1000

            return RequestMetric(
                fa_id=fa_id,
                session_id=session_id,
                query_text=query_text,
                status_code=0,
                success=False,
                response_time_ms=response_time_ms,
                error_message=str(e),
                sent_at=sent_at,
                completed_at=datetime.utcnow()
            )

    def _save_request_metric(self, run_id: int, metric: RequestMetric):
        """Save individual request metric to database"""
        try:
            with db_manager.get_session() as session:
                session.execute(
                    text("""
                        INSERT INTO load_test_requests
                        (run_id, fa_id, session_id, query_text, query_type,
                         status_code, success, response_time_ms, error_message, langsmith_url,
                         sent_at, completed_at)
                        VALUES (:run_id, :fa_id, :session_id, :query, :type,
                                :status, :success, :time, :error, :langsmith, :sent, :completed)
                    """),
                    {
                        "run_id": run_id,
                        "fa_id": metric.fa_id,
                        "session_id": metric.session_id,
                        "query": metric.query_text,
                        "type": "chat",
                        "status": metric.status_code,
                        "success": metric.success,
                        "time": metric.response_time_ms,
                        "error": metric.error_message,
                        "langsmith": metric.langsmith_url,
                        "sent": metric.sent_at,
                        "completed": metric.completed_at
                    }
                )
                session.commit()
        except Exception as e:
            logger.error(f"Failed to save request metric: {e}")

    async def _calculate_and_save_metrics(self, run_id: int, metrics: List[RequestMetric]):
        """Calculate aggregate metrics and update run record"""
        if not metrics:
            return

        response_times = [m.response_time_ms for m in metrics]
        successful_requests = sum(1 for m in metrics if m.success)
        failed_requests = len(metrics) - successful_requests

        # Calculate percentiles
        sorted_times = sorted(response_times)
        p50 = statistics.median(sorted_times)
        p95 = sorted_times[int(len(sorted_times) * 0.95)] if len(sorted_times) > 1 else sorted_times[0]
        p99 = sorted_times[int(len(sorted_times) * 0.99)] if len(sorted_times) > 1 else sorted_times[0]

        # Calculate duration and RPS
        start_time = min(m.sent_at for m in metrics)
        end_time = max(m.completed_at for m in metrics)
        duration_seconds = (end_time - start_time).total_seconds()
        rps = len(metrics) / duration_seconds if duration_seconds > 0 else 0

        with db_manager.get_session() as session:
            session.execute(
                text("""
                    UPDATE load_test_runs SET
                        requests_completed = :completed,
                        requests_failed = :failed,
                        avg_response_time_ms = :avg,
                        min_response_time_ms = :min,
                        max_response_time_ms = :max,
                        p50_response_time_ms = :p50,
                        p95_response_time_ms = :p95,
                        p99_response_time_ms = :p99,
                        requests_per_second = :rps
                    WHERE id = :run_id
                """),
                {
                    "run_id": run_id,
                    "completed": successful_requests,
                    "failed": failed_requests,
                    "avg": statistics.mean(response_times),
                    "min": min(response_times),
                    "max": max(response_times),
                    "p50": p50,
                    "p95": p95,
                    "p99": p99,
                    "rps": rps
                }
            )
            session.commit()

    def _update_run_status(
        self,
        run_id: int,
        status: str,
        started_at: Optional[datetime] = None
    ):
        """Update the status of a load test run"""
        with db_manager.get_session() as session:
            if started_at:
                session.execute(
                    text("UPDATE load_test_runs SET status = :status, started_at = :started WHERE id = :id"),
                    {"id": run_id, "status": status, "started": started_at}
                )
            else:
                session.execute(
                    text("UPDATE load_test_runs SET status = :status WHERE id = :id"),
                    {"id": run_id, "status": status}
                )
            session.commit()

    async def _notify_progress(self, run_id: int, data: Dict[str, Any]):
        """Notify registered callbacks of progress updates"""
        if run_id in self.progress_callbacks:
            for callback in self.progress_callbacks[run_id]:
                try:
                    if asyncio.iscoroutinefunction(callback):
                        await callback(data)
                    else:
                        callback(data)
                except Exception as e:
                    logger.error(f"Progress callback failed: {e}")

    def get_run_status(self, run_id: int) -> Optional[Dict[str, Any]]:
        """Get current status of a load test run"""
        with db_manager.get_session() as session:
            result = session.execute(
                text("SELECT * FROM load_test_runs WHERE id = :id"),
                {"id": run_id}
            ).fetchone()

            if not result:
                return None

            return {
                "id": result.id,
                "test_name": result.test_name,
                "status": result.status,
                "concurrent_users": result.concurrent_users,
                "total_requests": result.total_requests,
                "requests_completed": result.requests_completed,
                "requests_failed": result.requests_failed,
                "avg_response_time_ms": result.avg_response_time_ms,
                "p50_response_time_ms": result.p50_response_time_ms,
                "p95_response_time_ms": result.p95_response_time_ms,
                "p99_response_time_ms": result.p99_response_time_ms,
                "requests_per_second": result.requests_per_second,
                "started_at": result.started_at.isoformat() if result.started_at else None,
                "completed_at": result.completed_at.isoformat() if result.completed_at else None
            }

    def list_runs(self, limit: int = 20) -> List[Dict[str, Any]]:
        """List recent load test runs"""
        with db_manager.get_session() as session:
            results = session.execute(
                text("""
                    SELECT id, test_name, status, concurrent_users, total_requests,
                           requests_completed, requests_failed, requests_per_second,
                           started_at, completed_at, created_at
                    FROM load_test_runs
                    ORDER BY created_at DESC
                    LIMIT :limit
                """),
                {"limit": limit}
            ).fetchall()

            return [
                {
                    "id": r.id,
                    "test_name": r.test_name,
                    "status": r.status,
                    "concurrent_users": r.concurrent_users,
                    "total_requests": r.total_requests,
                    "requests_completed": r.requests_completed or 0,
                    "requests_failed": r.requests_failed or 0,
                    "requests_per_second": r.requests_per_second,
                    "started_at": r.started_at.isoformat() if r.started_at else None,
                    "completed_at": r.completed_at.isoformat() if r.completed_at else None,
                    "created_at": r.created_at.isoformat()
                }
                for r in results
            ]


# Global orchestrator instance
load_test_orchestrator = LoadTestOrchestrator()
