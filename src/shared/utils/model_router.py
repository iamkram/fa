"""
Model Router

Routes LLM tasks to appropriate models based on complexity and requirements.
Optimizes costs by using faster/cheaper models where appropriate.
"""

import logging
from typing import Literal, Optional
from enum import Enum

from src.shared.utils.cost_tracker import ModelType

logger = logging.getLogger(__name__)


class TaskComplexity(str, Enum):
    """Task complexity levels"""
    SIMPLE = "simple"          # Fast categorization, simple extractions
    MODERATE = "moderate"      # Standard summaries, fact-checking
    COMPLEX = "complex"        # Multi-step reasoning, deep analysis
    CRITICAL = "critical"      # High-stakes decisions, requires best model


class ModelRouter:
    """Route tasks to optimal models based on complexity and cost"""

    def __init__(
        self,
        default_model: str = ModelType.CLAUDE_SONNET_35,
        enable_haiku: bool = True,
        enable_cost_optimization: bool = True
    ):
        """Initialize model router

        Args:
            default_model: Default model to use
            enable_haiku: Whether to use Haiku for simple tasks
            enable_cost_optimization: Whether to optimize for cost
        """
        self.default_model = default_model
        self.enable_haiku = enable_haiku
        self.enable_cost_optimization = enable_cost_optimization

        # Task type to complexity mapping
        self.task_complexity_map = {
            # Batch operations
            "hook_summary": TaskComplexity.SIMPLE,       # Short hook (25-50w) - can use Haiku
            "medium_summary": TaskComplexity.MODERATE,   # Standard summary (100-150w) - Sonnet recommended
            "expanded_summary": TaskComplexity.COMPLEX,  # Detailed analysis (200-250w) - Sonnet required
            "fact_check": TaskComplexity.COMPLEX,        # Critical validation - Sonnet required
            "citation_extraction": TaskComplexity.MODERATE,
            "embedding_generation": TaskComplexity.SIMPLE,

            # Interactive operations
            "query_classification": TaskComplexity.SIMPLE,  # Fast routing - Haiku
            "quick_answer": TaskComplexity.SIMPLE,          # Simple questions - Haiku
            "standard_query": TaskComplexity.MODERATE,      # Standard FA queries - Sonnet
            "deep_research": TaskComplexity.COMPLEX,        # Complex analysis - Sonnet
            "multi_turn_conversation": TaskComplexity.MODERATE,

            # Guardrails
            "pii_detection": TaskComplexity.SIMPLE,        # Fast pattern matching - Haiku
            "injection_detection": TaskComplexity.SIMPLE,   # Security check - Haiku
            "hallucination_check": TaskComplexity.COMPLEX,  # Critical validation - Sonnet

            # Data ingestion
            "document_parsing": TaskComplexity.SIMPLE,
            "metadata_extraction": TaskComplexity.SIMPLE,
            "content_chunking": TaskComplexity.SIMPLE,
        }

        # Model selection rules
        self.complexity_to_model = {
            TaskComplexity.SIMPLE: ModelType.CLAUDE_HAIKU_35 if enable_haiku else ModelType.CLAUDE_SONNET_35,
            TaskComplexity.MODERATE: ModelType.CLAUDE_SONNET_35,
            TaskComplexity.COMPLEX: ModelType.CLAUDE_SONNET_35,
            TaskComplexity.CRITICAL: ModelType.CLAUDE_SONNET_35,  # Could use Opus for ultra-critical
        }

    def get_model_for_task(
        self,
        task_type: str,
        force_model: Optional[str] = None,
        context_size: Optional[int] = None
    ) -> str:
        """Get optimal model for a task

        Args:
            task_type: Type of task (e.g., "hook_summary", "fact_check")
            force_model: Force a specific model (overrides routing)
            context_size: Size of context in tokens (may influence routing)

        Returns:
            Model identifier string
        """
        # If model is forced, use that
        if force_model:
            logger.debug(f"Using forced model: {force_model} for {task_type}")
            return force_model

        # If cost optimization disabled, use default
        if not self.enable_cost_optimization:
            logger.debug(f"Cost optimization disabled, using default: {self.default_model}")
            return self.default_model

        # Get complexity for task type
        complexity = self.task_complexity_map.get(task_type, TaskComplexity.MODERATE)

        # Large contexts might need Sonnet even for simple tasks
        if context_size and context_size > 50000:
            logger.debug(f"Large context ({context_size} tokens), upgrading to Sonnet")
            complexity = TaskComplexity.MODERATE

        # Route to model
        model = self.complexity_to_model.get(complexity, self.default_model)

        logger.debug(f"Routed {task_type} (complexity: {complexity.value}) to {model}")
        return model

    def get_cost_estimate(
        self,
        task_type: str,
        estimated_input_tokens: int,
        estimated_output_tokens: int
    ) -> float:
        """Estimate cost for a task

        Args:
            task_type: Type of task
            estimated_input_tokens: Estimated input tokens
            estimated_output_tokens: Estimated output tokens

        Returns:
            Estimated cost in USD
        """
        from src.shared.utils.cost_tracker import MODEL_PRICING

        model = self.get_model_for_task(task_type)

        if model not in MODEL_PRICING:
            logger.warning(f"Unknown model for pricing: {model}")
            return 0.0

        pricing = MODEL_PRICING[model]
        input_cost = (estimated_input_tokens / 1_000_000) * pricing["input"]
        output_cost = (estimated_output_tokens / 1_000_000) * pricing["output"]

        return input_cost + output_cost

    def compare_models(
        self,
        task_type: str,
        estimated_input_tokens: int,
        estimated_output_tokens: int
    ) -> dict:
        """Compare cost across different models for a task

        Args:
            task_type: Type of task
            estimated_input_tokens: Estimated input tokens
            estimated_output_tokens: Estimated output tokens

        Returns:
            Dict with model comparisons
        """
        from src.shared.utils.cost_tracker import MODEL_PRICING

        comparisons = {}

        for model, pricing in MODEL_PRICING.items():
            input_cost = (estimated_input_tokens / 1_000_000) * pricing["input"]
            output_cost = (estimated_output_tokens / 1_000_000) * pricing["output"]
            total_cost = input_cost + output_cost

            comparisons[model] = {
                "cost": round(total_cost, 6),
                "input_cost": round(input_cost, 6),
                "output_cost": round(output_cost, 6)
            }

        # Add recommendation
        recommended_model = self.get_model_for_task(task_type)
        comparisons["recommended"] = recommended_model

        return comparisons

    def get_batch_model_recommendation(
        self,
        stock_count: int
    ) -> dict:
        """Get model recommendations for batch processing

        Args:
            stock_count: Number of stocks to process

        Returns:
            Dict with recommendations per summary tier
        """
        # Estimate tokens per stock
        # These are rough estimates based on typical usage
        estimates = {
            "hook_summary": {
                "input_tokens": 8000,  # Edgar + sources
                "output_tokens": 75,   # 25-50 words
                "model": self.get_model_for_task("hook_summary")
            },
            "medium_summary": {
                "input_tokens": 15000,
                "output_tokens": 200,  # 100-150 words
                "model": self.get_model_for_task("medium_summary")
            },
            "expanded_summary": {
                "input_tokens": 25000,
                "output_tokens": 350,  # 200-250 words
                "model": self.get_model_for_task("expanded_summary")
            },
            "fact_check": {
                "input_tokens": 10000,
                "output_tokens": 500,
                "model": self.get_model_for_task("fact_check")
            }
        }

        # Calculate total cost
        total_cost = 0.0
        for tier, est in estimates.items():
            cost = self.get_cost_estimate(
                tier,
                est["input_tokens"],
                est["output_tokens"]
            )
            est["cost_per_stock"] = round(cost, 4)
            est["total_cost"] = round(cost * stock_count, 2)
            total_cost += est["total_cost"]

        return {
            "stock_count": stock_count,
            "estimates": estimates,
            "total_cost_usd": round(total_cost, 2),
            "cost_per_stock": round(total_cost / stock_count, 4) if stock_count > 0 else 0.0,
            "optimization_enabled": self.enable_cost_optimization,
            "haiku_enabled": self.enable_haiku
        }


# Global instance with cost optimization enabled
model_router = ModelRouter(
    default_model=ModelType.CLAUDE_SONNET_35,
    enable_haiku=True,
    enable_cost_optimization=True
)
