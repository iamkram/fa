"""
Cost Tracker

Tracks LLM token usage and costs across all agents and operations.
Provides per-agent breakdown and cost monitoring for batch and interactive workloads.
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class ModelType(str, Enum):
    """LLM model types with pricing"""
    CLAUDE_SONNET_35 = "claude-3-5-sonnet-20241022"
    CLAUDE_HAIKU_35 = "claude-3-5-haiku-20241022"
    CLAUDE_OPUS_3 = "claude-3-opus-20240229"
    GPT_4O = "gpt-4o"
    GPT_4O_MINI = "gpt-4o-mini"


# Pricing per million tokens (as of Phase 4 - January 2025)
MODEL_PRICING = {
    ModelType.CLAUDE_SONNET_35: {"input": 3.00, "output": 15.00},  # $3/$15 per MTok
    ModelType.CLAUDE_HAIKU_35: {"input": 0.80, "output": 4.00},    # $0.80/$4 per MTok
    ModelType.CLAUDE_OPUS_3: {"input": 15.00, "output": 75.00},    # $15/$75 per MTok
    ModelType.GPT_4O: {"input": 2.50, "output": 10.00},            # $2.50/$10 per MTok
    ModelType.GPT_4O_MINI: {"input": 0.15, "output": 0.60},        # $0.15/$0.60 per MTok
}


@dataclass
class TokenUsage:
    """Token usage for a single LLM call"""
    input_tokens: int
    output_tokens: int
    model: str
    agent_name: Optional[str] = None
    operation: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def calculate_cost(self) -> float:
        """Calculate cost in USD for this token usage

        Returns:
            Cost in USD (e.g., 0.005 = half a cent)
        """
        if self.model not in MODEL_PRICING:
            logger.warning(f"Unknown model for pricing: {self.model}")
            return 0.0

        pricing = MODEL_PRICING[self.model]
        input_cost = (self.input_tokens / 1_000_000) * pricing["input"]
        output_cost = (self.output_tokens / 1_000_000) * pricing["output"]

        return input_cost + output_cost


@dataclass
class CostSummary:
    """Summary of costs for a workload"""
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_cost_usd: float = 0.0
    call_count: int = 0
    by_agent: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    by_model: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None

    def add_usage(self, usage: TokenUsage):
        """Add token usage to summary

        Args:
            usage: TokenUsage instance to add
        """
        cost = usage.calculate_cost()

        # Update totals
        self.total_input_tokens += usage.input_tokens
        self.total_output_tokens += usage.output_tokens
        self.total_cost_usd += cost
        self.call_count += 1

        # Update timestamps
        if self.start_time is None:
            self.start_time = usage.timestamp
        self.end_time = usage.timestamp

        # Update by_agent breakdown
        if usage.agent_name:
            if usage.agent_name not in self.by_agent:
                self.by_agent[usage.agent_name] = {
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "cost_usd": 0.0,
                    "calls": 0
                }

            self.by_agent[usage.agent_name]["input_tokens"] += usage.input_tokens
            self.by_agent[usage.agent_name]["output_tokens"] += usage.output_tokens
            self.by_agent[usage.agent_name]["cost_usd"] += cost
            self.by_agent[usage.agent_name]["calls"] += 1

        # Update by_model breakdown
        if usage.model not in self.by_model:
            self.by_model[usage.model] = {
                "input_tokens": 0,
                "output_tokens": 0,
                "cost_usd": 0.0,
                "calls": 0
            }

        self.by_model[usage.model]["input_tokens"] += usage.input_tokens
        self.by_model[usage.model]["output_tokens"] += usage.output_tokens
        self.by_model[usage.model]["cost_usd"] += cost
        self.by_model[usage.model]["calls"] += 1

    def get_cost_per_unit(self, unit_count: int) -> float:
        """Calculate cost per unit (e.g., per stock, per query)

        Args:
            unit_count: Number of units processed

        Returns:
            Cost per unit in USD
        """
        if unit_count == 0:
            return 0.0
        return self.total_cost_usd / unit_count

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for logging/storage"""
        return {
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "total_cost_usd": round(self.total_cost_usd, 4),
            "call_count": self.call_count,
            "by_agent": {
                agent: {
                    **stats,
                    "cost_usd": round(stats["cost_usd"], 4)
                }
                for agent, stats in self.by_agent.items()
            },
            "by_model": {
                model: {
                    **stats,
                    "cost_usd": round(stats["cost_usd"], 4)
                }
                for model, stats in self.by_model.items()
            },
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None
        }


class CostTracker:
    """Track LLM costs across operations"""

    def __init__(self):
        """Initialize cost tracker"""
        self.current_summary = CostSummary()
        self.history: list[CostSummary] = []

    def track_usage(
        self,
        input_tokens: int,
        output_tokens: int,
        model: str,
        agent_name: Optional[str] = None,
        operation: Optional[str] = None
    ):
        """Track token usage for an LLM call

        Args:
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
            model: Model identifier
            agent_name: Name of agent making the call
            operation: Operation being performed
        """
        usage = TokenUsage(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            model=model,
            agent_name=agent_name,
            operation=operation
        )

        self.current_summary.add_usage(usage)

        # Log the usage
        cost = usage.calculate_cost()
        logger.debug(
            f"Cost tracking: {agent_name or 'unknown'} | "
            f"{model} | {input_tokens}in/{output_tokens}out | "
            f"${cost:.4f}"
        )

    def get_summary(self) -> CostSummary:
        """Get current cost summary

        Returns:
            Current CostSummary instance
        """
        return self.current_summary

    def reset(self):
        """Reset current summary and archive to history"""
        if self.current_summary.call_count > 0:
            self.history.append(self.current_summary)

        self.current_summary = CostSummary()

    def log_summary(self, unit_count: Optional[int] = None, unit_name: str = "unit"):
        """Log formatted cost summary

        Args:
            unit_count: Number of units processed (e.g., stocks, queries)
            unit_name: Name of unit (e.g., "stock", "query")
        """
        summary = self.current_summary

        logger.info("\n" + "="*60)
        logger.info("COST TRACKING SUMMARY")
        logger.info("="*60)
        logger.info(f"Total Calls: {summary.call_count}")
        logger.info(f"Total Tokens: {summary.total_input_tokens:,} in / {summary.total_output_tokens:,} out")
        logger.info(f"Total Cost: ${summary.total_cost_usd:.4f}")

        if unit_count:
            cost_per_unit = summary.get_cost_per_unit(unit_count)
            logger.info(f"Cost per {unit_name}: ${cost_per_unit:.4f}")

        logger.info("\nBy Agent:")
        for agent, stats in sorted(summary.by_agent.items()):
            logger.info(
                f"  {agent}: {stats['calls']} calls | "
                f"{stats['input_tokens']:,} in / {stats['output_tokens']:,} out | "
                f"${stats['cost_usd']:.4f}"
            )

        logger.info("\nBy Model:")
        for model, stats in sorted(summary.by_model.items()):
            logger.info(
                f"  {model}: {stats['calls']} calls | "
                f"{stats['input_tokens']:,} in / {stats['output_tokens']:,} out | "
                f"${stats['cost_usd']:.4f}"
            )

        logger.info("="*60 + "\n")


# Global instance
cost_tracker = CostTracker()
