"""
Context Assembly Node

Synthesizes all research outputs into structured context for response generation.
"""

import logging
from typing import Dict, Any
from datetime import datetime

from src.interactive.state import InteractiveGraphState, AssembledContextState

logger = logging.getLogger(__name__)


def count_tokens_approximate(text: str) -> int:
    """Approximate token count (1 token ≈ 4 chars)"""
    return len(text) // 4


def assemble_context_node(state: InteractiveGraphState, config) -> Dict[str, Any]:
    """Synthesize all research outputs into structured context"""
    logger.info(f"[Assembly] Assembling context for FA {state.fa_id}")

    # Determine query intent
    query_intent = _infer_intent(state.sanitized_query, state.edo_context)

    # Collect all context
    assembled = AssembledContextState(
        query_intent=query_intent,
        fa_context=state.edo_context,
        batch_summary=state.batch_summary,
        breaking_news=state.news_items,
        historical_data=state.retrieved_chunks,
        conversation_history=state.conversation_history,
        assembly_timestamp=datetime.utcnow()
    )

    # Calculate token count
    total_tokens = 0

    if assembled.fa_context:
        fa_text = f"{assembled.fa_context.fa_profile.name if assembled.fa_context.fa_profile else ''}"
        for hh in assembled.fa_context.relevant_households:
            fa_text += f"{hh.household_name} {len(hh.holdings)} holdings "
        total_tokens += count_tokens_approximate(fa_text)

    if assembled.batch_summary:
        total_tokens += count_tokens_approximate(assembled.batch_summary.get("text", ""))

    for news in assembled.breaking_news:
        total_tokens += count_tokens_approximate(news.headline + news.summary)

    for chunk in assembled.historical_data:
        total_tokens += count_tokens_approximate(chunk.text)

    for turn in assembled.conversation_history:
        total_tokens += count_tokens_approximate(turn.content)

    assembled.total_token_count = total_tokens

    logger.info(f"[Assembly] Context assembled: ~{total_tokens} tokens")

    # Warn if approaching context limit
    if total_tokens > 50000:
        logger.warning(f"[Assembly] Context very large ({total_tokens} tokens), may need truncation")

    return {"assembled_context": assembled}


def _infer_intent(query: str, edo_context) -> str:
    """Infer high-level intent from query"""
    query_lower = query.lower()

    if "impact" in query_lower or "affect" in query_lower:
        return "Assess impact on holdings"
    elif "compare" in query_lower:
        return "Compare stocks or metrics"
    elif "recommend" in query_lower or "suggest" in query_lower:
        return "Provide recommendations"
    elif "risk" in query_lower:
        return "Assess risk exposure"
    elif "household" in query_lower or "client" in query_lower:
        return "Household-specific analysis"
    else:
        return "General inquiry"
