"""
Interactive Query Processing Graph

Complete Phase 3 pipeline:
1. Input Guardrails → 2. Query Classifier → 3. Route (Simple | Deep) → 4. Response → 5. Output Guardrails

Simple Path: Batch Data Retrieval → Output Guardrails
Deep Path: EDO Context + News + Memory → Assemble → Response Writer → Fact Verify → Output Guardrails
"""

from langgraph.graph import StateGraph, START, END
from typing import Literal
import logging

from src.interactive.state import InteractiveGraphState
from src.interactive.nodes.input_guardrails import input_guardrail_node
from src.interactive.nodes.query_classifier import query_classifier_node, route_query
from src.interactive.nodes.batch_data_retrieval import batch_data_retrieval_node
from src.interactive.nodes.edo_context import edo_context_node
from src.interactive.nodes.news_research import news_research_node
from src.interactive.nodes.memory import memory_node
from src.interactive.nodes.assemble_context import assemble_context_node
from src.interactive.agents.response_writer import response_writer_node
from src.interactive.nodes.fact_verification import fact_verification_node
from src.interactive.nodes.output_guardrails import output_guardrail_node

logger = logging.getLogger(__name__)


# ============================================================================
# Conditional Edge Functions
# ============================================================================

def should_process_query(state: InteractiveGraphState) -> Literal["classify", "end"]:
    """Check if input passed guardrails"""
    if not state.input_safe:
        return "end"  # Blocked by input guardrails
    return "classify"


def route_after_classification(state: InteractiveGraphState) -> Literal["simple", "deep"]:
    """Route between simple retrieval and deep research"""
    return route_query(state)


def should_generate_response(state: InteractiveGraphState) -> Literal["response_writer", "output_guardrails"]:
    """Check if deep research completed successfully"""
    # If we have assembled context, generate response
    # Otherwise skip to output guardrails (batch data already set response_text)
    if state.assembled_context:
        return "response_writer"
    return "output_guardrails"


# ============================================================================
# Main Graph
# ============================================================================

def create_interactive_graph():
    """
    Create the complete interactive query processing graph

    Flow:
    START → Input Guardrails → Query Classifier → [Simple | Deep] → Output Guardrails → END

    Simple Path:
        Classifier → Batch Data Retrieval → Output Guardrails → END

    Deep Path:
        Classifier → [EDO Context, News Research, Memory] (parallel)
                  → Assemble Context → Response Writer → Fact Verify → Output Guardrails → END
    """
    builder = StateGraph(InteractiveGraphState)

    # Add all nodes
    builder.add_node("input_guardrails", input_guardrail_node)
    builder.add_node("classify_query", query_classifier_node)

    # Simple path
    builder.add_node("batch_data", batch_data_retrieval_node)

    # Deep research path
    builder.add_node("edo_context", edo_context_node)
    builder.add_node("news_research", news_research_node)
    builder.add_node("memory", memory_node)
    builder.add_node("assemble_context", assemble_context_node)
    builder.add_node("response_writer", response_writer_node)
    builder.add_node("fact_verify", fact_verification_node)

    # Output
    builder.add_node("output_guardrails", output_guardrail_node)

    # Define flow
    builder.add_edge(START, "input_guardrails")

    # Input guardrails → classifier or end
    builder.add_conditional_edges(
        "input_guardrails",
        should_process_query,
        {
            "classify": "classify_query",
            "end": END
        }
    )

    # Classifier → route to simple or deep
    builder.add_conditional_edges(
        "classify_query",
        route_after_classification,
        {
            "simple": "batch_data",
            "deep": "edo_context"  # Start deep research path
        }
    )

    # Simple path: batch data → output guardrails → end
    builder.add_edge("batch_data", "output_guardrails")

    # Deep research path (parallel data gathering)
    # EDO context is entry point, then run news and memory in parallel
    builder.add_edge("edo_context", "news_research")
    builder.add_edge("news_research", "memory")
    builder.add_edge("memory", "assemble_context")
    builder.add_edge("assemble_context", "response_writer")
    builder.add_edge("response_writer", "fact_verify")
    builder.add_edge("fact_verify", "output_guardrails")

    # Output guardrails → end
    builder.add_edge("output_guardrails", END)

    graph = builder.compile()

    logger.info("✅ Interactive query graph compiled")

    return graph


# Export the compiled graph
interactive_graph = create_interactive_graph()
