"""
Batch Data Retrieval Node

For simple retrieval path: fetch pre-generated summaries from Postgres
instead of running expensive deep research.
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime

from src.interactive.state import InteractiveGraphState
from src.shared.database.connection import db_manager
from src.shared.models.database import StockSummary

logger = logging.getLogger(__name__)


def extract_ticker_from_query(query: str) -> Optional[str]:
    """Extract ticker symbol from query"""
    import re

    # Look for common ticker patterns
    # Format: 1-5 uppercase letters optionally preceded by $
    pattern = r'\$?([A-Z]{1,5})\b'
    matches = re.findall(pattern, query)

    if matches:
        return matches[0]

    return None


def get_requested_tier(state: InteractiveGraphState) -> str:
    """Determine which tier to return based on query type"""
    if state.query_type == "dashboard_load":
        return "hook"
    elif state.query_type == "stock_detail":
        return "medium"
    elif state.query_type == "deep_dive":
        return "expanded"
    else:
        # Chat - default to medium
        return "medium"


def batch_data_retrieval_node(state: InteractiveGraphState, config) -> Dict[str, Any]:
    """Fetch pre-generated summary from Postgres"""
    logger.info(f"[BatchData] Retrieving summary for FA {state.fa_id}")

    # Extract ticker from query or context
    ticker = state.context.get("current_stock_ticker")
    if not ticker:
        ticker = extract_ticker_from_query(state.sanitized_query)

    if not ticker:
        logger.warning("[BatchData] No ticker found in query")
        error_message = "I couldn't identify a specific stock ticker in your question. Please include a ticker symbol (e.g., AAPL, MSFT) or rephrase your question with the company name."
        return {
            "batch_summary": None,
            "response_text": error_message,
            "response_tier": "error"
        }

    # Determine tier
    tier = get_requested_tier(state)

    # Query database - fetch most recent summary regardless of date
    with db_manager.get_session() as session:
        summary = session.query(StockSummary).filter(
            StockSummary.ticker == ticker,
            StockSummary.fact_check_status == 'passed'
        ).order_by(StockSummary.generation_timestamp.desc()).first()

        if not summary:
            logger.warning(f"[BatchData] No summary found for {ticker}")
            error_message = f"I don't have any pre-generated analysis available for {ticker} yet. This data may be coming soon in the next batch update. Please try asking about a different stock, or rephrase your question for a more general analysis."
            return {
                "batch_summary": None,
                "response_text": error_message,
                "response_tier": "error"
            }

        # Extract requested tier
        if tier == "hook":
            text = summary.hook_text
            word_count = summary.hook_word_count
        elif tier == "medium":
            text = summary.medium_text
            word_count = summary.medium_word_count
        else:  # expanded
            text = summary.expanded_text
            word_count = summary.expanded_word_count

        logger.info(f"[BatchData] Retrieved {tier} summary for {ticker} ({word_count} words)")

        return {
            "batch_summary": {
                "summary_id": str(summary.summary_id),
                "ticker": ticker,
                "tier": tier,
                "text": text,
                "word_count": word_count,
                "generation_date": summary.generation_date.isoformat()
            },
            "response_text": text,
            "response_tier": tier
        }
