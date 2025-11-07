from langgraph.graph import StateGraph, START, END
import logging

from src.batch.state import BatchGraphState
from src.batch.nodes.edgar_ingestion import edgar_ingestion_node
from src.batch.nodes.vectorize_edgar import vectorize_edgar_node
from src.batch.agents.medium_writer import medium_writer_node
from src.batch.nodes.fact_checker import fact_check_node
from src.batch.nodes.storage import store_summary_node

logger = logging.getLogger(__name__)


def create_batch_graph():
    """Create the Phase 1 batch processing graph

    Graph flow:
    START → edgar_ingestion → vectorize → medium_writer → fact_checker → storage → END

    Returns:
        Compiled LangGraph StateGraph
    """
    logger.info("Creating batch processing graph...")

    # Initialize graph with BatchGraphState
    builder = StateGraph(BatchGraphState)

    # Add nodes
    builder.add_node("edgar_ingestion", edgar_ingestion_node)
    builder.add_node("vectorize", vectorize_edgar_node)
    builder.add_node("medium_writer", medium_writer_node)
    builder.add_node("fact_checker", fact_check_node)
    builder.add_node("storage", store_summary_node)

    # Add edges (linear flow for Phase 1)
    builder.add_edge(START, "edgar_ingestion")
    builder.add_edge("edgar_ingestion", "vectorize")
    builder.add_edge("vectorize", "medium_writer")
    builder.add_edge("medium_writer", "fact_checker")

    # Conditional edge: store regardless of fact check status
    # (In Phase 1, we store both passed and failed summaries)
    def route_after_fact_check(state: BatchGraphState):
        """Route to storage regardless of fact check result"""
        return "storage"

    builder.add_conditional_edges(
        "fact_checker",
        route_after_fact_check,
        ["storage"]
    )

    builder.add_edge("storage", END)

    # Compile graph
    graph = builder.compile()

    logger.info("✅ Batch graph compiled successfully")

    return graph


# Create and export graph instance
batch_graph = create_batch_graph()
