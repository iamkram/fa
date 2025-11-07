"""
Memory Integration Node

Integrates:
1. Conversation history from Redis
2. Vector search across batch data sources (RAG)
"""

import asyncio
import logging
from typing import Dict, Any, List

from src.interactive.state import (
    InteractiveGraphState,
    MemoryState,
    ConversationTurn,
    RetrievedChunk
)
from src.shared.utils.redis_client import redis_session_manager
from src.shared.utils.rag import hybrid_search

logger = logging.getLogger(__name__)


async def retrieve_relevant_chunks(
    query: str,
    stock_id: str = None,
    top_k: int = 10
) -> List[RetrievedChunk]:
    """Retrieve relevant chunks via hybrid RAG"""

    # Search across all namespaces
    raw_chunks = await hybrid_search(
        query=query,
        namespaces=["bluematrix_reports", "edgar_filings", "factset_data"],
        stock_id=stock_id,
        top_k=top_k,
        threshold=0.70
    )

    # Convert to RetrievedChunk objects
    chunks = []
    for idx, chunk in enumerate(raw_chunks, 1):
        chunks.append(RetrievedChunk(
            chunk_id=chunk['id'],
            namespace=chunk['metadata'].get('source', 'unknown'),
            text=chunk['text'],
            metadata=chunk['metadata'],
            similarity_score=chunk['similarity'],
            rank=idx
        ))

    return chunks


def memory_node(state: InteractiveGraphState, config) -> Dict[str, Any]:
    """Integrate conversation memory and vector search"""
    logger.info(f"[Memory] Retrieving context for session {state.session_id}")

    try:
        # 1. Get conversation history from Redis
        conversation_history = redis_session_manager.get_conversation_history(
            session_id=state.session_id,
            limit=10
        )

        conv_turns = [ConversationTurn(**turn) for turn in conversation_history]

        logger.info(f"[Memory] Retrieved {len(conv_turns)} conversation turns")

        # 2. Perform hybrid RAG search
        # Build search query from current query + recent context
        search_query = state.sanitized_query
        if conv_turns:
            # Include last user message for context
            last_user_turns = [t for t in conv_turns if t.role == "user"]
            if last_user_turns:
                search_query = f"{last_user_turns[-1].content} {search_query}"

        # Determine stock_id if available
        stock_id = None
        if state.batch_summary:
            stock_id = state.batch_summary.get("ticker")
        elif state.edo_context and state.edo_context.total_exposure:
            # Use most held stock
            stock_id = max(
                state.edo_context.total_exposure.items(),
                key=lambda x: x[1]
            )[0]

        retrieved_chunks = asyncio.run(retrieve_relevant_chunks(
            query=search_query,
            stock_id=stock_id,
            top_k=10
        ))

        logger.info(f"[Memory] Retrieved {len(retrieved_chunks)} relevant chunks")

        memory_state = MemoryState(
            conversation_context=conv_turns,
            retrieved_chunks=retrieved_chunks
        )

        return {
            "conversation_history": conv_turns,
            "retrieved_chunks": retrieved_chunks
        }

    except Exception as e:
        logger.error(f"[Memory] Failed: {str(e)}")
        return {
            "conversation_history": [],
            "retrieved_chunks": [],
            "error_message": f"Memory retrieval failed: {str(e)}"
        }
