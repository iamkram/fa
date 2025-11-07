"""
Phase 2 Batch Processing Graph

Complete pipeline for Phase 2 with multi-source data ingestion and 3-tier summary generation.

Pipeline Flow:
START → Parallel Ingestion → Hook Writer → Medium Writer → Expanded Writer → Storage → END

Components:
- Parallel Ingestion: EDGAR + BlueMatrix + FactSet (concurrent)
- Hook Writer: <15 word social media hook
- Medium Writer: 75-125 word advisor brief
- Expanded Writer: 500-750 word research report
- Storage: Save all 3 tiers to PostgreSQL
"""

from langgraph.graph import StateGraph, START, END
import logging

from src.batch.state import BatchGraphStatePhase2
from src.batch.graphs.parallel_ingestion import parallel_ingestion_graph
from src.batch.agents.hook_writer import hook_writer_node
from src.batch.agents.medium_writer import medium_writer_node
from src.batch.agents.expanded_writer import expanded_writer_node
from src.batch.nodes.storage import store_summary_node

logger = logging.getLogger(__name__)


def create_phase2_graph():
    """
    Create Phase 2 batch processing graph with multi-source data and 3-tier summaries

    Architecture:
    1. Parallel Ingestion (EDGAR, BlueMatrix, FactSet) - runs concurrently
    2. Hook Writer - generates <15 word hook
    3. Medium Writer - generates 75-125 word summary
    4. Expanded Writer - generates 500-750 word summary
    5. Storage - saves all 3 tiers to database

    Note: This is the basic version without fact-checking or retry logic.
    Those will be added in later phases.
    """
    builder = StateGraph(BatchGraphStatePhase2)

    # Add nodes
    builder.add_node("parallel_ingestion", parallel_ingestion_graph)
    builder.add_node("hook_writer", hook_writer_node)
    builder.add_node("medium_writer", medium_writer_node)
    builder.add_node("expanded_writer", expanded_writer_node)
    builder.add_node("storage", store_summary_node)

    # Define flow - sequential after ingestion
    builder.add_edge(START, "parallel_ingestion")
    builder.add_edge("parallel_ingestion", "hook_writer")
    builder.add_edge("hook_writer", "medium_writer")
    builder.add_edge("medium_writer", "expanded_writer")
    builder.add_edge("expanded_writer", "storage")
    builder.add_edge("storage", END)

    graph = builder.compile()

    logger.info("✅ Phase 2 batch processing graph compiled")

    return graph


# Export the compiled graph
phase2_graph = create_phase2_graph()
