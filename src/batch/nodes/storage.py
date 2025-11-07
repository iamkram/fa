import logging
from datetime import datetime
from typing import Dict, Any, Union
from langchain_core.runnables import RunnableConfig

from src.shared.database.connection import db_manager
from src.shared.models.database import StockSummary, FactCheckStatus, SummaryCitation
from src.batch.state import BatchGraphState, BatchGraphStatePhase2

logger = logging.getLogger(__name__)


def store_summary_node(state: Union[BatchGraphState, BatchGraphStatePhase2], config: RunnableConfig) -> Dict[str, Any]:
    """Store validated summary in Postgres

    Args:
        state: Current batch graph state (Phase 1 or Phase 2)
        config: Runnable configuration

    Returns:
        Updated state dict with summary_id and storage_status
    """
    logger.info(f"[Storage] Storing summary for {state.ticker}")

    # Phase 2: Check if we have any summary tiers
    is_phase2 = isinstance(state, BatchGraphStatePhase2)
    has_summaries = False

    if is_phase2:
        has_summaries = bool(state.hook_summary or state.medium_summary or state.expanded_summary)
    else:
        # Phase 1: Only medium summary
        has_summaries = bool(state.medium_summary)

    if not has_summaries:
        logger.warning(f"No summaries to store for {state.ticker}")
        return {
            "storage_status": "failed",
            "error_message": "No summaries to store"
        }

    try:
        with db_manager.get_session() as session:
            # Determine fact check status
            if hasattr(state, 'fact_check_status') and state.fact_check_status:
                fact_check_status = (
                    FactCheckStatus.PASSED if state.fact_check_status == "passed"
                    else FactCheckStatus.FAILED
                )
            else:
                fact_check_status = FactCheckStatus.UNVALIDATED

            # Create summary record with all 3 tiers
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
            session.add(summary)
            session.flush()  # Get summary_id before commit

            # Create citation records for verified claims
            if hasattr(state, 'fact_check_results') and state.fact_check_results:
                for result in state.fact_check_results:
                    if result.validation_status == "verified":
                        # Determine source type
                        source_type = getattr(result, 'source_type', 'edgar')

                        citation = SummaryCitation(
                            summary_id=summary.summary_id,
                            source_type=source_type,
                            claim_text=result.claim_text,
                            evidence_text=result.evidence_text,
                            similarity_score=result.similarity_score
                        )
                        session.add(citation)

            session.commit()

            summary_id = str(summary.summary_id)

            # Log what was stored
            tiers_stored = []
            if summary_data.get("hook_text"):
                tiers_stored.append(f"hook({summary_data['hook_word_count']}w)")
            if summary_data.get("medium_text"):
                tiers_stored.append(f"medium({summary_data['medium_word_count']}w)")
            if summary_data.get("expanded_text"):
                tiers_stored.append(f"expanded({summary_data['expanded_word_count']}w)")

            logger.info(
                f"✅ Stored summary {summary_id} for {state.ticker}: "
                f"{', '.join(tiers_stored)} (status: {fact_check_status.value})"
            )

            return {
                "summary_id": summary_id,
                "storage_status": "stored"
            }

    except Exception as e:
        logger.error(f"❌ Storage failed for {state.ticker}: {str(e)}")
        return {
            "storage_status": "failed",
            "error_message": f"Storage error: {str(e)}"
        }
