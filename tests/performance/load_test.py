#!/usr/bin/env python3
"""
Load Testing for FA AI System

Simulates production load to validate performance and scalability.
"""

import asyncio
import logging
import sys
import time
from pathlib import Path
from typing import List, Dict, Any
from datetime import datetime, timedelta
from dataclasses import dataclass, field
import statistics

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.batch.orchestrator.concurrent_batch import ConcurrentBatchOrchestrator
from src.batch.graphs.phase2_with_validation import phase2_validation_graph
from src.batch.state import BatchGraphStatePhase2
from src.config.settings import settings

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# ============================================================================
# Load Test Configuration
# ============================================================================

@dataclass
class LoadTestConfig:
    """Load test configuration"""
    total_stocks: int = 100
    concurrent_limit: int = 100
    duration_minutes: int = 60
    target_throughput: float = 250.0  # stocks per hour

    # Performance targets
    max_latency_p95_ms: float = 60000  # 60s for full stock processing
    max_error_rate_pct: float = 5.0
    min_success_rate_pct: float = 95.0


@dataclass
class LoadTestMetrics:
    """Load test metrics collection"""
    total_processed: int = 0
    total_successful: int = 0
    total_failed: int = 0
    latencies_ms: List[float] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    costs: List[float] = field(default_factory=list)
    start_time: datetime = field(default_factory=datetime.utcnow)
    end_time: datetime = None

    def add_result(self, success: bool, latency_ms: float, cost: float = 0.0, error: str = None):
        """Add a test result"""
        self.total_processed += 1
        if success:
            self.total_successful += 1
        else:
            self.total_failed += 1
            if error:
                self.errors.append(error)

        self.latencies_ms.append(latency_ms)
        if cost > 0:
            self.costs.append(cost)

    def calculate_percentile(self, percentile: float) -> float:
        """Calculate latency percentile"""
        if not self.latencies_ms:
            return 0.0
        sorted_latencies = sorted(self.latencies_ms)
        index = int(len(sorted_latencies) * (percentile / 100.0))
        return sorted_latencies[min(index, len(sorted_latencies) - 1)]

    def get_summary(self) -> Dict[str, Any]:
        """Get summary metrics"""
        if not self.end_time:
            self.end_time = datetime.utcnow()

        duration_s = (self.end_time - self.start_time).total_seconds()

        return {
            "duration_seconds": duration_s,
            "total_processed": self.total_processed,
            "successful": self.total_successful,
            "failed": self.total_failed,
            "success_rate_pct": (self.total_successful / self.total_processed * 100) if self.total_processed > 0 else 0,
            "error_rate_pct": (self.total_failed / self.total_processed * 100) if self.total_processed > 0 else 0,
            "throughput_per_hour": (self.total_processed / duration_s * 3600) if duration_s > 0 else 0,
            "latency_p50_ms": self.calculate_percentile(50),
            "latency_p95_ms": self.calculate_percentile(95),
            "latency_p99_ms": self.calculate_percentile(99),
            "latency_max_ms": max(self.latencies_ms) if self.latencies_ms else 0,
            "latency_avg_ms": statistics.mean(self.latencies_ms) if self.latencies_ms else 0,
            "total_cost": sum(self.costs),
            "avg_cost_per_stock": statistics.mean(self.costs) if self.costs else 0,
        }


# ============================================================================
# Load Test Scenarios
# ============================================================================

class LoadTester:
    """Load testing orchestrator"""

    def __init__(self, config: LoadTestConfig):
        self.config = config
        self.metrics = LoadTestMetrics()
        self.orchestrator = ConcurrentBatchOrchestrator(
            graph=phase2_validation_graph,
            batch_size=config.concurrent_limit,
            max_concurrent=config.concurrent_limit
        )

    async def run_batch_load_test(self, stock_tickers: List[str]) -> LoadTestMetrics:
        """Run load test simulating batch processing"""
        logger.info("=" * 80)
        logger.info("Batch Processing Load Test")
        logger.info("=" * 80)
        logger.info(f"Total stocks: {self.config.total_stocks}")
        logger.info(f"Concurrent limit: {self.config.concurrent_limit}")
        logger.info(f"Target throughput: {self.config.target_throughput} stocks/hour")
        logger.info("=" * 80)

        batch_run_id = f"load-test-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}"

        # Create states for all stocks
        states = []
        for i, ticker in enumerate(stock_tickers[:self.config.total_stocks]):
            state = BatchGraphStatePhase2(
                stock_id=f"load-test-{i:04d}",
                ticker=ticker,
                company_name=f"Company {ticker}",
                batch_run_id=batch_run_id
            )
            states.append(state)

        # Process with concurrent orchestrator
        logger.info(f"Starting batch processing of {len(states)} stocks...")
        self.metrics.start_time = datetime.utcnow()

        try:
            results = await self.orchestrator.run(states)

            self.metrics.end_time = datetime.utcnow()

            # Collect metrics
            for result in results:
                success = result.get("storage_status") == "success"
                latency_ms = result.get("total_processing_time_ms", 0)
                cost = result.get("total_cost", 0.0)
                error = result.get("error") if not success else None

                self.metrics.add_result(success, latency_ms, cost, error)

                # Progress logging every 10 stocks
                if self.metrics.total_processed % 10 == 0:
                    logger.info(f"Progress: {self.metrics.total_processed}/{len(states)} stocks processed")

        except Exception as e:
            logger.error(f"Load test failed: {e}")
            self.metrics.end_time = datetime.utcnow()
            raise

        return self.metrics

    async def run_sustained_load_test(self, stock_tickers: List[str]) -> LoadTestMetrics:
        """Run sustained load over time period"""
        logger.info("=" * 80)
        logger.info("Sustained Load Test")
        logger.info("=" * 80)
        logger.info(f"Duration: {self.config.duration_minutes} minutes")
        logger.info(f"Concurrent limit: {self.config.concurrent_limit}")
        logger.info("=" * 80)

        batch_run_id = f"sustained-load-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}"
        end_time = datetime.utcnow() + timedelta(minutes=self.config.duration_minutes)

        self.metrics.start_time = datetime.utcnow()
        stock_idx = 0

        while datetime.utcnow() < end_time:
            # Get next batch of stocks
            batch_tickers = []
            for _ in range(self.config.concurrent_limit):
                batch_tickers.append(stock_tickers[stock_idx % len(stock_tickers)])
                stock_idx += 1

            # Process batch
            states = []
            for i, ticker in enumerate(batch_tickers):
                state = BatchGraphStatePhase2(
                    stock_id=f"sustained-test-{stock_idx - len(batch_tickers) + i:04d}",
                    ticker=ticker,
                    company_name=f"Company {ticker}",
                    batch_run_id=batch_run_id
                )
                states.append(state)

            try:
                results = await self.orchestrator.run(states)

                for result in results:
                    success = result.get("storage_status") == "success"
                    latency_ms = result.get("total_processing_time_ms", 0)
                    cost = result.get("total_cost", 0.0)
                    error = result.get("error") if not success else None

                    self.metrics.add_result(success, latency_ms, cost, error)

            except Exception as e:
                logger.error(f"Batch failed: {e}")
                self.metrics.total_failed += len(states)

            # Progress update
            elapsed_min = (datetime.utcnow() - self.metrics.start_time).total_seconds() / 60
            logger.info(f"Time: {elapsed_min:.1f}/{self.config.duration_minutes} min | "
                       f"Processed: {self.metrics.total_processed} | "
                       f"Success rate: {self.metrics.total_successful / max(1, self.metrics.total_processed) * 100:.1f}%")

        self.metrics.end_time = datetime.utcnow()
        return self.metrics

    def validate_against_targets(self, metrics: LoadTestMetrics) -> bool:
        """Validate metrics against performance targets"""
        logger.info("\n" + "=" * 80)
        logger.info("Performance Validation")
        logger.info("=" * 80)

        summary = metrics.get_summary()
        all_passed = True

        # Success rate
        success_rate = summary["success_rate_pct"]
        target_success = self.config.min_success_rate_pct
        passed = success_rate >= target_success
        all_passed = all_passed and passed
        logger.info(f"Success Rate: {success_rate:.1f}% (target: >= {target_success}%) {'✅' if passed else '❌'}")

        # Error rate
        error_rate = summary["error_rate_pct"]
        target_error = self.config.max_error_rate_pct
        passed = error_rate <= target_error
        all_passed = all_passed and passed
        logger.info(f"Error Rate: {error_rate:.1f}% (target: <= {target_error}%) {'✅' if passed else '❌'}")

        # P95 latency
        p95_latency = summary["latency_p95_ms"]
        target_latency = self.config.max_latency_p95_ms
        passed = p95_latency <= target_latency
        all_passed = all_passed and passed
        logger.info(f"P95 Latency: {p95_latency:.0f}ms (target: <= {target_latency:.0f}ms) {'✅' if passed else '❌'}")

        # Throughput
        throughput = summary["throughput_per_hour"]
        target_throughput = self.config.target_throughput
        passed = throughput >= target_throughput
        all_passed = all_passed and passed
        logger.info(f"Throughput: {throughput:.1f} stocks/hour (target: >= {target_throughput}) {'✅' if passed else '❌'}")

        logger.info("=" * 80)
        logger.info(f"Overall: {'✅ PASSED' if all_passed else '❌ FAILED'}")
        logger.info("=" * 80)

        return all_passed


# ============================================================================
# Test Runner
# ============================================================================

async def main():
    """Run load tests"""
    logger.info("=" * 80)
    logger.info("FA AI System - Load Testing Suite")
    logger.info("=" * 80)

    # Sample stock tickers for testing
    stock_tickers = [
        "AAPL", "MSFT", "GOOGL", "AMZN", "META",
        "TSLA", "NVDA", "JPM", "V", "WMT",
        "JNJ", "PG", "MA", "HD", "DIS",
        "BAC", "XOM", "CSCO", "PFE", "INTC"
    ]

    # Run batch load test (100 stocks)
    logger.info("\n🚀 Running Batch Load Test...")
    config = LoadTestConfig(
        total_stocks=100,
        concurrent_limit=100,
        target_throughput=250.0,
        max_latency_p95_ms=60000,  # 60s per stock
        min_success_rate_pct=95.0
    )

    tester = LoadTester(config)
    metrics = await tester.run_batch_load_test(stock_tickers)

    # Display results
    summary = metrics.get_summary()
    logger.info("\n" + "=" * 80)
    logger.info("Load Test Results")
    logger.info("=" * 80)
    logger.info(f"Duration: {summary['duration_seconds']:.1f}s")
    logger.info(f"Total Processed: {summary['total_processed']}")
    logger.info(f"Successful: {summary['successful']} ({summary['success_rate_pct']:.1f}%)")
    logger.info(f"Failed: {summary['failed']} ({summary['error_rate_pct']:.1f}%)")
    logger.info(f"Throughput: {summary['throughput_per_hour']:.1f} stocks/hour")
    logger.info(f"")
    logger.info(f"Latency P50: {summary['latency_p50_ms']:.0f}ms")
    logger.info(f"Latency P95: {summary['latency_p95_ms']:.0f}ms")
    logger.info(f"Latency P99: {summary['latency_p99_ms']:.0f}ms")
    logger.info(f"Latency Max: {summary['latency_max_ms']:.0f}ms")
    logger.info(f"Latency Avg: {summary['latency_avg_ms']:.0f}ms")
    logger.info(f"")
    logger.info(f"Total Cost: ${summary['total_cost']:.2f}")
    logger.info(f"Avg Cost/Stock: ${summary['avg_cost_per_stock']:.4f}")
    logger.info("=" * 80)

    # Validate against targets
    passed = tester.validate_against_targets(metrics)

    # Exit code
    return 0 if passed else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
