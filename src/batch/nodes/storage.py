import logging
from datetime import datetime
from typing import Dict, Any
from langchain_core.runnables import RunnableConfig

from src.shared.database.connection import db_manager
from src.shared.models.database import StockSummary, FactCheckStatus, SummaryCitation
from src.batch.state import BatchGraphState

logger = logging.getLogger(__name__)


def store_summary_node(state: BatchGraphState, config: RunnableConfig) -> Dict[str, Any]:
    """Store validated summary in Postgres

    Args:
        state: Current batch graph state
        config: Runnable configuration

    Returns:
        Updated state dict with summary_id and storage_status
    """
    logger.info(f"[STORAGE] Storing summary for {state.ticker}")

    if not state.medium_summary:
        logger.warning(f"No summary to store for {state.ticker}")
        return {
            "storage_status": "failed",
            "error_message": "No summary to store"
        }

    try:
        with db_manager.get_session() as session:
            # Create summary record
            summary = StockSummary(
                stock_id=state.stock_id,
                ticker=state.ticker,
                generation_date=datetime.utcnow(),
                medium_text=state.medium_summary,
                medium_word_count=state.word_count,
                fact_check_status=(
                    FactCheckStatus.PASSED if state.fact_check_status == "passed"
                    else FactCheckStatus.FAILED
                ),
                retry_count=state.retry_count
            )

            session.add(summary)
            session.flush()  # Get summary_id before commit

            # Create citation records for verified claims
            if state.fact_check_results:
                for result in state.fact_check_results:
                    if result.validation_status == "verified":
                        citation = SummaryCitation(
                            summary_id=summary.summary_id,
                            source_type='edgar',
                            claim_text=result.claim_text,
                            evidence_text=result.evidence_text,
                            similarity_score=result.similarity_score
                        )
                        session.add(citation)

            session.commit()

            summary_id = str(summary.summary_id)
            logger.info(
                f"✅ Stored summary {summary_id} for {state.ticker} "
                f"(status: {summary.fact_check_status.value})"
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
