"""
Parallel data ingestion using LangGraph parallel edges

This graph processes EDGAR, BlueMatrix, and FactSet data sources in parallel,
then aggregates results before continuing to summary generation.
"""

from langgraph.graph import StateGraph, START, END
from typing import Dict, Any
import logging

from src.batch.state import BatchGraphStatePhase2
from src.batch.nodes.edgar_ingestion import edgar_ingestion_node
from src.batch.nodes.vectorize_edgar import vectorize_edgar_node
from src.batch.nodes.bluematrix_ingestion import bluematrix_ingestion_node
from src.batch.nodes.vectorize_bluematrix import vectorize_bluematrix_node
from src.batch.nodes.factset_ingestion import factset_ingestion_node
from src.batch.nodes.vectorize_factset import vectorize_factset_node

logger = logging.getLogger(__name__)


# ============================================================================
# Aggregation Node
# ============================================================================

def aggregate_sources(state: BatchGraphStatePhase2, config) -> Dict[str, Any]:
    """
    Aggregation node that waits for all parallel branches to complete

    LangGraph automatically handles the synchronization - this node
    only executes once all parallel branches have finished.
    """
    logger.info(f"[Aggregate] Collecting data from all sources for {state.ticker}")

    # Check which sources succeeded
    sources_status = {
        "edgar": state.edgar_status,
        "bluematrix": state.bluematrix_status,
        "factset": state.factset_status
    }

    successful_sources = sum(1 for status in sources_status.values() if status == "success")

    logger.info(f"[Aggregate] Data collection complete: {successful_sources}/3 sources successful")
    logger.info(f"  - EDGAR: {state.edgar_status} ({len(state.edgar_filings)} filings, {len(state.edgar_vector_ids)} vectors)")
    logger.info(f"  - BlueMatrix: {state.bluematrix_status} ({len(state.bluematrix_reports)} reports, {len(state.bluematrix_vector_ids)} vectors)")
    logger.info(f"  - FactSet: {state.factset_status} ({len(state.factset_vector_ids)} vectors)")

    # Return empty dict - no state updates needed
    return {}


# ============================================================================
# Main Parallel Ingestion Graph
# ============================================================================

def create_parallel_ingestion_graph():
    """
    Create graph with parallel data source processing

    Architecture:
    START → [EDGAR ingest, BlueMatrix ingest, FactSet ingest] (parallel)
         → [EDGAR vectorize, BlueMatrix vectorize, FactSet vectorize] (parallel)
         → Aggregate
         → END

    Parallel execution using multiple edges from START.
    """
    builder = StateGraph(BatchGraphStatePhase2)

    # Add individual ingestion nodes
    builder.add_node("edgar_ingest", edgar_ingestion_node)
    builder.add_node("bluematrix_ingest", bluematrix_ingestion_node)
    builder.add_node("factset_ingest", factset_ingestion_node)

    # Add individual vectorization nodes
    builder.add_node("edgar_vectorize", vectorize_edgar_node)
    builder.add_node("bluematrix_vectorize", vectorize_bluematrix_node)
    builder.add_node("factset_vectorize", vectorize_factset_node)

    # Add aggregation node
    builder.add_node("aggregate", aggregate_sources)

    # Parallel ingestion from START
    builder.add_edge(START, "edgar_ingest")
    builder.add_edge(START, "bluematrix_ingest")
    builder.add_edge(START, "factset_ingest")

    # Sequential within each pipeline
    builder.add_edge("edgar_ingest", "edgar_vectorize")
    builder.add_edge("bluematrix_ingest", "bluematrix_vectorize")
    builder.add_edge("factset_ingest", "factset_vectorize")

    # All vectorization nodes feed into aggregate
    builder.add_edge("edgar_vectorize", "aggregate")
    builder.add_edge("bluematrix_vectorize", "aggregate")
    builder.add_edge("factset_vectorize", "aggregate")

    builder.add_edge("aggregate", END)

    graph = builder.compile()

    logger.info("✅ Parallel ingestion graph compiled")

    return graph


# Export the graph
parallel_ingestion_graph = create_parallel_ingestion_graph()
