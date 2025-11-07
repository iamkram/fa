"""Fact-checking nodes for all three summary tiers"""

from typing import Dict, Any
import asyncio
import logging
import time

from src.batch.state import BatchGraphStatePhase2, TierFactCheckState, SourceFactCheckResult
from src.batch.agents.fact_checker import FactCheckerAgent

logger = logging.getLogger(__name__)


def fact_check_hook_node(state: BatchGraphStatePhase2, config) -> Dict[str, Any]:
    """Fact-check hook summary against source documents

    Args:
        state: Current batch graph state
        config: Runnable configuration

    Returns:
        Updated state dict with hook_fact_check
    """
    logger.info(f"[FactCheck-Hook] Verifying {state.ticker}")

    if not state.hook_summary:
        logger.warning(f"No hook summary to verify for {state.ticker}")
        return {"hook_fact_check": None}

    start_time = time.time()

    try:
        agent = FactCheckerAgent()
        result = asyncio.run(agent.verify_summary(
            ticker=state.ticker,
            company_name=state.company_name,
            summary_text=state.hook_summary,
            tier="hook",
            state=state
        ))

        # Determine overall status (pass if >= 80% verified)
        pass_rate = result.get('overall_pass_rate', 0.0)
        overall_status = "passed" if pass_rate >= 0.8 else "failed"

        # Extract failed claims
        failed_claims = [
            {
                "claim_text": claim["claim_text"],
                "discrepancy": claim.get("discrepancy_detail", "")
            }
            for claim in result.get("claims", [])
            if claim["validation_status"] == "failed"
        ]

        fact_check_state = TierFactCheckState(
            tier="hook",
            overall_status=overall_status,
            overall_pass_rate=pass_rate,
            failed_claims=failed_claims
        )

        generation_time = int((time.time() - start_time) * 1000)
        logger.info(
            f"[FactCheck-Hook] {state.ticker}: {overall_status} "
            f"({pass_rate:.1%} pass rate, {generation_time}ms)"
        )

        return {"hook_fact_check": fact_check_state}

    except Exception as e:
        logger.error(f"❌ Hook fact-check failed for {state.ticker}: {str(e)}")
        return {
            "hook_fact_check": TierFactCheckState(
                tier="hook",
                overall_status="failed",
                overall_pass_rate=0.0,
                failed_claims=[{"claim_text": "ERROR", "discrepancy": str(e)}]
            )
        }


def fact_check_medium_node(state: BatchGraphStatePhase2, config) -> Dict[str, Any]:
    """Fact-check medium summary against source documents

    Args:
        state: Current batch graph state
        config: Runnable configuration

    Returns:
        Updated state dict with medium_fact_check
    """
    logger.info(f"[FactCheck-Medium] Verifying {state.ticker}")

    if not state.medium_summary:
        logger.warning(f"No medium summary to verify for {state.ticker}")
        return {"medium_fact_check": None}

    start_time = time.time()

    try:
        agent = FactCheckerAgent()
        result = asyncio.run(agent.verify_summary(
            ticker=state.ticker,
            company_name=state.company_name,
            summary_text=state.medium_summary,
            tier="medium",
            state=state
        ))

        # Determine overall status (pass if >= 80% verified)
        pass_rate = result.get('overall_pass_rate', 0.0)
        overall_status = "passed" if pass_rate >= 0.8 else "failed"

        # Extract failed claims
        failed_claims = [
            {
                "claim_text": claim["claim_text"],
                "discrepancy": claim.get("discrepancy_detail", "")
            }
            for claim in result.get("claims", [])
            if claim["validation_status"] == "failed"
        ]

        fact_check_state = TierFactCheckState(
            tier="medium",
            overall_status=overall_status,
            overall_pass_rate=pass_rate,
            failed_claims=failed_claims
        )

        generation_time = int((time.time() - start_time) * 1000)
        logger.info(
            f"[FactCheck-Medium] {state.ticker}: {overall_status} "
            f"({pass_rate:.1%} pass rate, {generation_time}ms)"
        )

        return {"medium_fact_check": fact_check_state}

    except Exception as e:
        logger.error(f"❌ Medium fact-check failed for {state.ticker}: {str(e)}")
        return {
            "medium_fact_check": TierFactCheckState(
                tier="medium",
                overall_status="failed",
                overall_pass_rate=0.0,
                failed_claims=[{"claim_text": "ERROR", "discrepancy": str(e)}]
            )
        }


def fact_check_expanded_node(state: BatchGraphStatePhase2, config) -> Dict[str, Any]:
    """Fact-check expanded summary against source documents

    Args:
        state: Current batch graph state
        config: Runnable configuration

    Returns:
        Updated state dict with expanded_fact_check
    """
    logger.info(f"[FactCheck-Expanded] Verifying {state.ticker}")

    if not state.expanded_summary:
        logger.warning(f"No expanded summary to verify for {state.ticker}")
        return {"expanded_fact_check": None}

    start_time = time.time()

    try:
        agent = FactCheckerAgent()
        result = asyncio.run(agent.verify_summary(
            ticker=state.ticker,
            company_name=state.company_name,
            summary_text=state.expanded_summary,
            tier="expanded",
            state=state
        ))

        # Determine overall status (pass if >= 80% verified)
        pass_rate = result.get('overall_pass_rate', 0.0)
        overall_status = "passed" if pass_rate >= 0.8 else "failed"

        # Extract failed claims
        failed_claims = [
            {
                "claim_text": claim["claim_text"],
                "discrepancy": claim.get("discrepancy_detail", "")
            }
            for claim in result.get("claims", [])
            if claim["validation_status"] == "failed"
        ]

        fact_check_state = TierFactCheckState(
            tier="expanded",
            overall_status=overall_status,
            overall_pass_rate=pass_rate,
            failed_claims=failed_claims
        )

        generation_time = int((time.time() - start_time) * 1000)
        logger.info(
            f"[FactCheck-Expanded] {state.ticker}: {overall_status} "
            f"({pass_rate:.1%} pass rate, {generation_time}ms)"
        )

        return {"expanded_fact_check": fact_check_state}

    except Exception as e:
        logger.error(f"❌ Expanded fact-check failed for {state.ticker}: {str(e)}")
        return {
            "expanded_fact_check": TierFactCheckState(
                tier="expanded",
                overall_status="failed",
                overall_pass_rate=0.0,
                failed_claims=[{"claim_text": "ERROR", "discrepancy": str(e)}]
            )
        }
