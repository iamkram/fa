"""
CloudWatch Metrics Publisher

Publishes custom metrics to AWS CloudWatch for monitoring and alerting.
Tracks batch processing, interactive queries, and system health.
"""

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)

# Note: In production, import boto3 for actual CloudWatch publishing
# For development, we'll log metrics locally
try:
    import boto3
    CLOUDWATCH_AVAILABLE = True
except ImportError:
    CLOUDWATCH_AVAILABLE = False
    logger.warning("boto3 not available - CloudWatch metrics will be logged locally only")


class MetricUnit(str, Enum):
    """CloudWatch metric units"""
    SECONDS = "Seconds"
    MICROSECONDS = "Microseconds"
    MILLISECONDS = "Milliseconds"
    BYTES = "Bytes"
    KILOBYTES = "Kilobytes"
    MEGABYTES = "Megabytes"
    GIGABYTES = "Gigabytes"
    COUNT = "Count"
    PERCENT = "Percent"
    NONE = "None"


@dataclass
class Metric:
    """CloudWatch metric data"""
    name: str
    value: float
    unit: MetricUnit
    dimensions: Dict[str, str]
    timestamp: datetime


class MetricsPublisher:
    """Publish custom metrics to CloudWatch"""

    def __init__(
        self,
        namespace: str = "FA-AI-System",
        region: str = "us-east-1",
        enabled: bool = True
    ):
        """Initialize metrics publisher

        Args:
            namespace: CloudWatch namespace for metrics
            region: AWS region
            enabled: Whether to actually publish metrics
        """
        self.namespace = namespace
        self.region = region
        self.enabled = enabled
        self.buffer: List[Metric] = []

        # Initialize CloudWatch client if available
        self.cloudwatch_client = None
        if CLOUDWATCH_AVAILABLE and enabled:
            try:
                self.cloudwatch_client = boto3.client('cloudwatch', region_name=region)
                logger.info(f"CloudWatch metrics publisher initialized: {namespace}")
            except Exception as e:
                logger.error(f"Failed to initialize CloudWatch client: {e}")
                self.cloudwatch_client = None

    def publish_metric(
        self,
        name: str,
        value: float,
        unit: MetricUnit = MetricUnit.COUNT,
        dimensions: Optional[Dict[str, str]] = None,
        timestamp: Optional[datetime] = None
    ):
        """Publish a single metric

        Args:
            name: Metric name
            value: Metric value
            unit: Metric unit
            dimensions: Metric dimensions (tags)
            timestamp: Metric timestamp (defaults to now)
        """
        if not self.enabled:
            return

        if timestamp is None:
            timestamp = datetime.utcnow()

        if dimensions is None:
            dimensions = {}

        metric = Metric(
            name=name,
            value=value,
            unit=unit,
            dimensions=dimensions,
            timestamp=timestamp
        )

        # Add to buffer
        self.buffer.append(metric)

        # Log locally
        dims_str = ", ".join(f"{k}={v}" for k, v in dimensions.items())
        logger.debug(
            f"Metric: {name}={value} {unit.value} [{dims_str}]"
        )

        # Flush if buffer is large
        if len(self.buffer) >= 20:
            self.flush()

    def publish_batch_metric(
        self,
        stock_count: int,
        successful_count: int,
        failed_count: int,
        duration_seconds: float,
        total_cost: float
    ):
        """Publish batch processing metrics

        Args:
            stock_count: Total stocks processed
            successful_count: Successful summaries
            failed_count: Failed summaries
            duration_seconds: Total batch duration
            total_cost: Total cost in USD
        """
        dimensions = {"WorkloadType": "Batch"}

        self.publish_metric(
            "StocksProcessed",
            stock_count,
            MetricUnit.COUNT,
            dimensions
        )

        self.publish_metric(
            "SuccessfulSummaries",
            successful_count,
            MetricUnit.COUNT,
            dimensions
        )

        self.publish_metric(
            "FailedSummaries",
            failed_count,
            MetricUnit.COUNT,
            dimensions
        )

        self.publish_metric(
            "BatchDuration",
            duration_seconds,
            MetricUnit.SECONDS,
            dimensions
        )

        self.publish_metric(
            "BatchSuccessRate",
            (successful_count / stock_count * 100) if stock_count > 0 else 0,
            MetricUnit.PERCENT,
            dimensions
        )

        self.publish_metric(
            "BatchCost",
            total_cost,
            MetricUnit.NONE,
            dimensions
        )

        self.publish_metric(
            "CostPerStock",
            (total_cost / stock_count) if stock_count > 0 else 0,
            MetricUnit.NONE,
            dimensions
        )

    def publish_query_metric(
        self,
        fa_id: str,
        response_time_ms: int,
        response_tier: str,
        guardrail_passed: bool
    ):
        """Publish interactive query metrics

        Args:
            fa_id: Financial advisor ID
            response_time_ms: Response time in milliseconds
            response_tier: Response tier (quick/standard/deep)
            guardrail_passed: Whether guardrails passed
        """
        dimensions = {
            "WorkloadType": "Interactive",
            "ResponseTier": response_tier
        }

        self.publish_metric(
            "QueryCount",
            1,
            MetricUnit.COUNT,
            dimensions
        )

        self.publish_metric(
            "QueryResponseTime",
            response_time_ms,
            MetricUnit.MILLISECONDS,
            dimensions
        )

        self.publish_metric(
            "GuardrailPassed",
            1 if guardrail_passed else 0,
            MetricUnit.COUNT,
            dimensions
        )

    def publish_error_metric(
        self,
        error_type: str,
        component: str,
        severity: str = "ERROR"
    ):
        """Publish error metric

        Args:
            error_type: Type of error
            component: Component where error occurred
            severity: Error severity (INFO/WARNING/ERROR/CRITICAL)
        """
        dimensions = {
            "ErrorType": error_type,
            "Component": component,
            "Severity": severity
        }

        self.publish_metric(
            "ErrorCount",
            1,
            MetricUnit.COUNT,
            dimensions
        )

    def publish_cost_metric(
        self,
        operation: str,
        input_tokens: int,
        output_tokens: int,
        cost_usd: float,
        model: str
    ):
        """Publish cost tracking metric

        Args:
            operation: Operation name
            input_tokens: Input token count
            output_tokens: Output token count
            cost_usd: Cost in USD
            model: Model used
        """
        dimensions = {
            "Operation": operation,
            "Model": model
        }

        self.publish_metric(
            "InputTokens",
            input_tokens,
            MetricUnit.COUNT,
            dimensions
        )

        self.publish_metric(
            "OutputTokens",
            output_tokens,
            MetricUnit.COUNT,
            dimensions
        )

        self.publish_metric(
            "LLMCost",
            cost_usd,
            MetricUnit.NONE,
            dimensions
        )

    def publish_system_health(
        self,
        cpu_usage_pct: float,
        memory_usage_pct: float,
        active_connections: int
    ):
        """Publish system health metrics

        Args:
            cpu_usage_pct: CPU usage percentage
            memory_usage_pct: Memory usage percentage
            active_connections: Number of active connections
        """
        dimensions = {"Component": "System"}

        self.publish_metric(
            "CPUUsage",
            cpu_usage_pct,
            MetricUnit.PERCENT,
            dimensions
        )

        self.publish_metric(
            "MemoryUsage",
            memory_usage_pct,
            MetricUnit.PERCENT,
            dimensions
        )

        self.publish_metric(
            "ActiveConnections",
            active_connections,
            MetricUnit.COUNT,
            dimensions
        )

    def flush(self):
        """Flush buffered metrics to CloudWatch"""
        if not self.buffer:
            return

        if self.cloudwatch_client is None:
            # Just log if CloudWatch not available
            logger.info(f"Flushing {len(self.buffer)} metrics (CloudWatch not available)")
            self.buffer.clear()
            return

        try:
            # Prepare metric data for CloudWatch
            metric_data = []

            for metric in self.buffer:
                metric_datum = {
                    'MetricName': metric.name,
                    'Value': metric.value,
                    'Unit': metric.unit.value,
                    'Timestamp': metric.timestamp,
                    'Dimensions': [
                        {'Name': k, 'Value': v}
                        for k, v in metric.dimensions.items()
                    ]
                }
                metric_data.append(metric_datum)

            # Publish to CloudWatch (max 20 metrics per request)
            for i in range(0, len(metric_data), 20):
                batch = metric_data[i:i+20]
                self.cloudwatch_client.put_metric_data(
                    Namespace=self.namespace,
                    MetricData=batch
                )

            logger.info(f"Published {len(self.buffer)} metrics to CloudWatch")
            self.buffer.clear()

        except Exception as e:
            logger.error(f"Failed to publish metrics to CloudWatch: {e}")
            # Keep buffer for retry
            if len(self.buffer) > 100:
                # Prevent buffer from growing too large
                self.buffer = self.buffer[-50:]

    def __del__(self):
        """Flush remaining metrics on cleanup"""
        self.flush()


# Global instance
metrics_publisher = MetricsPublisher(
    namespace="FA-AI-System",
    enabled=True
)
