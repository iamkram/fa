"""
Bulk Storage Node

Efficiently stores multiple stock summaries to the database using bulk operations.
Optimized for high-throughput batch processing (1,000+ stocks).
"""

import logging
from datetime import datetime
from typing import List, Dict, Any, Union
from langchain_core.runnables import RunnableConfig

from src.shared.database.connection import db_manager
from src.shared.models.database import StockSummary, FactCheckStatus, SummaryCitation
from src.batch.state import BatchGraphState, BatchGraphStatePhase2

logger = logging.getLogger(__name__)


def bulk_storage_node(
    states: List[Union[BatchGraphState, BatchGraphStatePhase2]],
    config: RunnableConfig
) -> List[Dict[str, Any]]:
    """Store multiple validated summaries in Postgres using bulk operations

    Uses SQLAlchemy's bulk_save_objects for optimal performance with large batches.
    Processes summaries in chunks of 50 to balance memory and performance.

    Args:
        states: List of batch graph states to store
        config: Runnable configuration

    Returns:
        List of updated state dicts with summary_id and storage_status
    """
    logger.info(f"[Bulk Storage] Storing {len(states)} summaries")

    # Filter states that have summaries to store
    valid_states = []
    for state in states:
        is_phase2 = isinstance(state, BatchGraphStatePhase2)
        has_summaries = False

        if is_phase2:
            has_summaries = bool(
                state.hook_summary or state.medium_summary or state.expanded_summary
            )
        else:
            has_summaries = bool(state.medium_summary)

        if has_summaries:
            valid_states.append(state)
        else:
            logger.warning(f"No summaries to store for {state.ticker}")

    if not valid_states:
        logger.warning("No valid summaries to store")
        return [
            {"storage_status": "failed", "error_message": "No summaries to store"}
            for _ in states
        ]

    # Process in chunks
    chunk_size = 50
    results = []

    try:
        with db_manager.get_session() as session:
            for i in range(0, len(valid_states), chunk_size):
                chunk = valid_states[i:i + chunk_size]
                chunk_results = _process_chunk(chunk, session)
                results.extend(chunk_results)

            session.commit()
            logger.info(f"✅ Bulk storage complete: {len(results)} summaries stored")

    except Exception as e:
        logger.error(f"❌ Bulk storage failed: {str(e)}", exc_info=True)
        return [
            {
                "storage_status": "failed",
                "error_message": f"Bulk storage error: {str(e)}"
            }
            for _ in valid_states
        ]

    return results


def _process_chunk(
    states: List[Union[BatchGraphState, BatchGraphStatePhase2]],
    session
) -> List[Dict[str, Any]]:
    """Process a chunk of states for bulk storage

    Args:
        states: Chunk of states to process
        session: Database session

    Returns:
        List of result dictionaries
    """
    summaries = []
    citations_by_summary_idx = {}

    # Build summary objects
    for idx, state in enumerate(states):
        is_phase2 = isinstance(state, BatchGraphStatePhase2)

        # Determine fact check status
        if hasattr(state, 'fact_check_status') and state.fact_check_status:
            fact_check_status = (
                FactCheckStatus.PASSED if state.fact_check_status == "passed"
                else FactCheckStatus.FAILED
            )
        else:
            fact_check_status = FactCheckStatus.UNVALIDATED

        # Build summary data
        summary_data = {
            "stock_id": state.stock_id,
            "ticker": state.ticker,
            "generation_date": datetime.utcnow(),
            "fact_check_status": fact_check_status,
            "retry_count": getattr(state, 'retry_count', 0)
        }

        # Add Phase 2 tiers if available
        if is_phase2:
            if state.hook_summary:
                summary_data["hook_text"] = state.hook_summary
                summary_data["hook_word_count"] = state.hook_word_count
            if state.medium_summary:
                summary_data["medium_text"] = state.medium_summary
                summary_data["medium_word_count"] = state.medium_word_count
            if state.expanded_summary:
                summary_data["expanded_text"] = state.expanded_summary
                summary_data["expanded_word_count"] = state.expanded_word_count
        else:
            # Phase 1: Only medium tier
            summary_data["medium_text"] = state.medium_summary
            summary_data["medium_word_count"] = getattr(state, 'word_count', 0)

        summary = StockSummary(**summary_data)
        summaries.append(summary)

        # Track citations for later insertion
        if hasattr(state, 'fact_check_results') and state.fact_check_results:
            citations_by_summary_idx[idx] = state.fact_check_results

    # Bulk insert summaries
    session.bulk_save_objects(summaries, return_defaults=True)
    session.flush()  # Ensure IDs are generated

    # Build results
    results = []
    for idx, (state, summary) in enumerate(zip(states, summaries)):
        is_phase2 = isinstance(state, BatchGraphStatePhase2)

        # Insert citations if any
        if idx in citations_by_summary_idx:
            for result in citations_by_summary_idx[idx]:
                if result.validation_status == "verified":
                    source_type = getattr(result, 'source_type', 'edgar')

                    citation = SummaryCitation(
                        summary_id=summary.summary_id,
                        source_type=source_type,
                        claim_text=result.claim_text,
                        evidence_text=result.evidence_text,
                        similarity_score=result.similarity_score
                    )
                    session.add(citation)

        # Build result dict
        tiers_stored = []
        if is_phase2:
            if state.hook_summary:
                tiers_stored.append(f"hook({state.hook_word_count}w)")
            if state.medium_summary:
                tiers_stored.append(f"medium({state.medium_word_count}w)")
            if state.expanded_summary:
                tiers_stored.append(f"expanded({state.expanded_word_count}w)")
        else:
            tiers_stored.append(f"medium({getattr(state, 'word_count', 0)}w)")

        logger.debug(
            f"✅ Stored summary {summary.summary_id} for {state.ticker}: "
            f"{', '.join(tiers_stored)}"
        )

        results.append({
            "summary_id": str(summary.summary_id),
            "storage_status": "stored"
        })

    return results


async def bulk_storage_node_async(
    states: List[Union[BatchGraphState, BatchGraphStatePhase2]],
    config: RunnableConfig
) -> List[Dict[str, Any]]:
    """Async wrapper for bulk storage node

    Args:
        states: List of batch graph states to store
        config: Runnable configuration

    Returns:
        List of updated state dicts
    """
    # For now, just call the sync version
    # In future, could implement true async database operations
    return bulk_storage_node(states, config)
