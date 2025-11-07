"""
Phase 2 Batch Processing Graph with Fact-Checking and Retry Logic

Complete pipeline with LLM-based fact-checking and negative prompting retries.

Pipeline Flow:
START → Parallel Ingestion
      → Hook Writer → Fact Check → [Retry if failed, max 2x]
      → Medium Writer → Fact Check → [Retry if failed, max 2x]
      → Expanded Writer → Fact Check → [Retry if failed, max 2x]
      → Storage
      → END
"""

from langgraph.graph import StateGraph, START, END
from typing import Literal
import logging

from src.batch.state import BatchGraphStatePhase2
from src.batch.graphs.parallel_ingestion import parallel_ingestion_graph
from src.batch.agents.hook_writer import hook_writer_node
from src.batch.agents.medium_writer import medium_writer_node
from src.batch.agents.expanded_writer import expanded_writer_node
from src.batch.nodes.fact_check_tiers import (
    fact_check_hook_node,
    fact_check_medium_node,
    fact_check_expanded_node
)
from src.batch.nodes.retry_tiers import (
    retry_hook_node,
    retry_medium_node,
    retry_expanded_node
)
from src.batch.nodes.storage import store_summary_node

logger = logging.getLogger(__name__)


# ============================================================================
# Conditional Edge Functions
# ============================================================================

def should_retry_hook(state: BatchGraphStatePhase2) -> Literal["retry_hook", "medium_writer"]:
    """Decide whether to retry hook generation or proceed to medium"""
    if (
        state.hook_fact_check and
        state.hook_fact_check.overall_status == "failed" and
        state.hook_retry_count < 2
    ):
        return "retry_hook"
    return "medium_writer"


def should_retry_medium(state: BatchGraphStatePhase2) -> Literal["retry_medium", "expanded_writer"]:
    """Decide whether to retry medium generation or proceed to expanded"""
    if (
        state.medium_fact_check and
        state.medium_fact_check.overall_status == "failed" and
        state.medium_retry_count < 2
    ):
        return "retry_medium"
    return "expanded_writer"


def should_retry_expanded(state: BatchGraphStatePhase2) -> Literal["retry_expanded", "storage"]:
    """Decide whether to retry expanded generation or proceed to storage"""
    if (
        state.expanded_fact_check and
        state.expanded_fact_check.overall_status == "failed" and
        state.expanded_retry_count < 2
    ):
        return "retry_expanded"
    return "storage"


# ============================================================================
# Main Graph
# ============================================================================

def create_phase2_validation_graph():
    """
    Create Phase 2 graph with fact-checking and retry logic

    Architecture:
    1. Parallel Ingestion (EDGAR, BlueMatrix, FactSet)
    2. For each tier (Hook → Medium → Expanded):
       - Generate summary
       - Fact-check against sources
       - If failed and retries < 2: Retry with negative prompting
       - Else: Proceed to next tier
    3. Storage (save all 3 tiers with fact-check results)

    Retry logic uses negative prompting to avoid previous errors.
    """
    builder = StateGraph(BatchGraphStatePhase2)

    # Add all nodes
    builder.add_node("parallel_ingestion", parallel_ingestion_graph)

    # Hook tier
    builder.add_node("hook_writer", hook_writer_node)
    builder.add_node("fact_check_hook", fact_check_hook_node)
    builder.add_node("retry_hook", retry_hook_node)

    # Medium tier
    builder.add_node("medium_writer", medium_writer_node)
    builder.add_node("fact_check_medium", fact_check_medium_node)
    builder.add_node("retry_medium", retry_medium_node)

    # Expanded tier
    builder.add_node("expanded_writer", expanded_writer_node)
    builder.add_node("fact_check_expanded", fact_check_expanded_node)
    builder.add_node("retry_expanded", retry_expanded_node)

    # Storage
    builder.add_node("storage", store_summary_node)

    # Define flow
    builder.add_edge(START, "parallel_ingestion")
    builder.add_edge("parallel_ingestion", "hook_writer")

    # Hook tier flow with retry
    builder.add_edge("hook_writer", "fact_check_hook")
    builder.add_conditional_edges(
        "fact_check_hook",
        should_retry_hook,
        {
            "retry_hook": "retry_hook",
            "medium_writer": "medium_writer"
        }
    )
    builder.add_edge("retry_hook", "fact_check_hook")  # Loop back to fact-check

    # Medium tier flow with retry
    builder.add_edge("medium_writer", "fact_check_medium")
    builder.add_conditional_edges(
        "fact_check_medium",
        should_retry_medium,
        {
            "retry_medium": "retry_medium",
            "expanded_writer": "expanded_writer"
        }
    )
    builder.add_edge("retry_medium", "fact_check_medium")  # Loop back to fact-check

    # Expanded tier flow with retry
    builder.add_edge("expanded_writer", "fact_check_expanded")
    builder.add_conditional_edges(
        "fact_check_expanded",
        should_retry_expanded,
        {
            "retry_expanded": "retry_expanded",
            "storage": "storage"
        }
    )
    builder.add_edge("retry_expanded", "fact_check_expanded")  # Loop back to fact-check

    builder.add_edge("storage", END)

    graph = builder.compile()

    logger.info("✅ Phase 2 validation graph compiled (with fact-checking and retries)")

    return graph


# Export the compiled graph
phase2_validation_graph = create_phase2_validation_graph()
