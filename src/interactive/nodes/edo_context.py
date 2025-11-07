"""
EDO Context Node

Retrieves Financial Advisor and Household context from EDO database via MCP.
Provides personalization data for response generation.
"""

import logging
from typing import Dict, Any
from datetime import datetime, timedelta
import random

from src.interactive.state import (
    InteractiveGraphState,
    EdoContextState,
    FAProfile,
    Household,
    HouseholdHolding,
    HouseholdInteraction
)
from mcp_servers.edo_sql_server import edo_mcp_server

logger = logging.getLogger(__name__)


def edo_context_node(state: InteractiveGraphState, config) -> Dict[str, Any]:
    """Retrieve FA and household context from EDO via MCP"""
    logger.info(f"[EDO] Fetching context for FA {state.fa_id}")

    try:
        # Get FA profile
        fa_data = edo_mcp_server.mock_data["fas"].get(state.fa_id, {
            "name": "Unknown FA",
            "region": "Unknown",
            "aum": 0,
            "client_count": 0
        })

        fa_profile = FAProfile(**fa_data, fa_id=state.fa_id)

        # Get households for this FA
        households_data = edo_mcp_server.execute_query(
            f"SELECT * FROM Households WHERE fa_id = '{state.fa_id}'",
            state.fa_id
        )

        households = []
        total_exposure = {}

        for hh_data in households_data:
            # Convert holdings
            holdings = []
            for holding_data in hh_data.get("holdings", []):
                ticker = holding_data["ticker"]
                current_value = holding_data["current_value"]
                cost_basis = holding_data["cost_basis"] * holding_data["shares"]

                holding = HouseholdHolding(
                    ticker=ticker,
                    shares=holding_data["shares"],
                    cost_basis=cost_basis,
                    current_value=current_value,
                    pct_of_portfolio=(current_value / hh_data["total_aum"]) * 100,
                    unrealized_gain_loss=current_value - cost_basis
                )
                holdings.append(holding)

                # Track total exposure
                total_exposure[ticker] = total_exposure.get(ticker, 0) + current_value

            # Generate mock recent interactions
            interactions = [
                HouseholdInteraction(
                    date=datetime.utcnow() - timedelta(days=random.randint(1, 30)),
                    interaction_type=random.choice(["call", "email", "meeting"]),
                    summary=f"Discussed portfolio performance and {random.choice(['rebalancing', 'tax strategy', 'market outlook'])}",
                    sentiment=random.choice(["positive", "neutral"])
                )
                for _ in range(random.randint(1, 3))
            ]

            household = Household(
                household_id=hh_data.get("household_id", "HH-UNKNOWN"),
                household_name=hh_data["household_name"],
                total_aum=hh_data["total_aum"],
                risk_tolerance=hh_data.get("risk_tolerance"),
                holdings=holdings,
                recent_interactions=interactions
            )
            households.append(household)

        edo_context = EdoContextState(
            fa_profile=fa_profile,
            relevant_households=households,
            total_exposure=total_exposure
        )

        logger.info(f"[EDO] Retrieved context: {len(households)} households, {len(total_exposure)} unique holdings")

        return {"edo_context": edo_context}

    except Exception as e:
        logger.error(f"[EDO] Context retrieval failed: {str(e)}")
        return {
            "edo_context": None,
            "error_message": f"EDO context retrieval failed: {str(e)}"
        }
