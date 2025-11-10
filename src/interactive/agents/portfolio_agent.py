"""
Portfolio Agent - ONE TOOL PATTERN

This agent has exactly ONE tool: get_batch_portfolio_data()

Retrieves pre-generated portfolio summaries from nightly batch runs.
Part of the interactive supervisor architecture for FA meeting prep.
"""

import logging
from typing import Dict
from datetime import datetime

from langchain_core.tools import tool
from sqlalchemy import select, desc

from src.shared.database.connection import db_manager
from src.shared.models.enterprise_database import (
    Household,
    HouseholdSummary,
    BatchRun
)

logger = logging.getLogger(__name__)


# ============================================================================
# ONE TOOL: get_batch_portfolio_data
# ============================================================================

@tool
def get_batch_portfolio_data(household_id: str) -> str:
    """
    Retrieve pre-generated portfolio summary from nightly batch processing.

    This is the ONLY tool for the Portfolio Agent.

    This tool reads the household summary created during the 2 AM batch run.
    Returns formatted portfolio overview with holdings and stock insights.

    Args:
        household_id: Unique identifier for the household (e.g., "JOHNSON-001")

    Returns:
        Formatted portfolio summary (text) including:
        - Total portfolio value
        - Number of holdings
        - Top holdings breakdown
        - Sector allocation
        - Batch data timestamp
    """
    try:
        logger.info(f"📊 Fetching batch portfolio data for household {household_id}")

        with db_manager.get_session() as session:
            # Get latest household summary from most recent batch run
            result = session.execute(
                select(
                    HouseholdSummary,
                    BatchRun.completed_at.label('batch_completed_at')
                )
                .join(BatchRun, HouseholdSummary.batch_run_id == BatchRun.batch_run_id)
                .join(Household, HouseholdSummary.household_id == Household.household_id)
                .where(Household.household_id == household_id)
                .where(BatchRun.status == 'COMPLETED')
                .order_by(desc(BatchRun.completed_at))
                .limit(1)
            ).first()

            if not result:
                logger.warning(f"⚠️  No batch data found for household {household_id}")
                return f"""
No batch data available for household {household_id}.

This may indicate:
- The household is newly created
- The nightly batch has not run yet
- There was an error in the last batch run

Please check batch run status or wait for the next nightly update (2 AM).
                """.strip()

            household_summary, batch_completed_at = result

            # Format as comprehensive text summary
            summary_text = f"""
═══════════════════════════════════════════════════
PORTFOLIO SUMMARY - {household_id}
═══════════════════════════════════════════════════

Data as of: {batch_completed_at.strftime('%Y-%m-%d %H:%M:%S')}
Batch Run ID: {household_summary.batch_run_id}

───────────────────────────────────────────────────
OVERVIEW
───────────────────────────────────────────────────
Total Portfolio Value: ${household_summary.total_value:,.2f}
Number of Holdings: {household_summary.holdings_count}

───────────────────────────────────────────────────
TOP HOLDINGS
───────────────────────────────────────────────────
{_format_top_holdings(household_summary.top_holdings)}

───────────────────────────────────────────────────
SECTOR ALLOCATION
───────────────────────────────────────────────────
{_format_sector_allocation(household_summary.sector_allocation)}

───────────────────────────────────────────────────
DETAILED SUMMARY
───────────────────────────────────────────────────
{household_summary.summary}

═══════════════════════════════════════════════════
            """.strip()

            logger.info(f"✅ Retrieved portfolio data for {household_id}")
            return summary_text

    except Exception as e:
        logger.error(f"❌ Error retrieving portfolio data for {household_id}: {str(e)}")
        return f"Error retrieving portfolio data: {str(e)}"


# ============================================================================
# Helper Functions
# ============================================================================

def _format_top_holdings(top_holdings_json: dict) -> str:
    """
    Format top holdings JSON into readable text.

    Expected format:
    {
        "holdings": [
            {"ticker": "AAPL", "value": 50000, "percentage": 25.0},
            ...
        ]
    }
    """
    if not top_holdings_json or "holdings" not in top_holdings_json:
        return "No holdings data available"

    holdings = top_holdings_json["holdings"]

    lines = []
    for holding in holdings[:10]:  # Top 10
        ticker = holding.get("ticker", "N/A")
        value = holding.get("value", 0)
        percentage = holding.get("percentage", 0)

        lines.append(f"{ticker:8} ${value:>12,.2f}  ({percentage:>5.1f}%)")

    return "\n".join(lines) if lines else "No holdings to display"


def _format_sector_allocation(sector_allocation_json: dict) -> str:
    """
    Format sector allocation JSON into readable text.

    Expected format:
    {
        "sectors": [
            {"name": "Technology", "percentage": 45.0},
            ...
        ]
    }
    """
    if not sector_allocation_json or "sectors" not in sector_allocation_json:
        return "No sector data available"

    sectors = sector_allocation_json["sectors"]

    lines = []
    for sector in sectors:
        name = sector.get("name", "N/A")
        percentage = sector.get("percentage", 0)

        # Create a simple text bar chart
        bar_length = int(percentage / 2)  # Scale to fit
        bar = "█" * bar_length

        lines.append(f"{name:20} {bar:25} {percentage:>5.1f}%")

    return "\n".join(lines) if lines else "No sector data to display"


# ============================================================================
# Usage Example
# ============================================================================

if __name__ == "__main__":
    # Test the agent
    result = get_batch_portfolio_data("JOHNSON-001")
    print(result)
