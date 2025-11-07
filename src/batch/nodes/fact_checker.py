import re
from datetime import datetime
from typing import List, Dict, Any
from langchain_core.runnables import RunnableConfig
import logging

from src.batch.state import BatchGraphState, FactCheckClaim, FactCheckResult

logger = logging.getLogger(__name__)


def extract_claims(summary: str) -> List[FactCheckClaim]:
    """Extract verifiable claims from summary

    Args:
        summary: Summary text to extract claims from

    Returns:
        List of FactCheckClaim objects
    """
    claims = []

    # Extract numeric claims (percentages, prices, counts)
    numeric_pattern = r'\b\d+\.?\d*%?|\$\d+\.?\d*[BMK]?'
    for match in re.finditer(numeric_pattern, summary):
        claims.append(FactCheckClaim(
            claim_text=match.group(),
            claim_type="numeric",
            expected_source="edgar",
            confidence=0.9
        ))

    # Extract date claims
    date_pattern = r'\b\d{1,2}/\d{1,2}/\d{4}\b'
    for match in re.finditer(date_pattern, summary):
        claims.append(FactCheckClaim(
            claim_text=match.group(),
            claim_type="date",
            expected_source="edgar",
            confidence=0.95
        ))

    # Extract filing type claims
    filing_pattern = r'\b(8-K|10-K|10-Q|Form 4|13D|13G)\b'
    for match in re.finditer(filing_pattern, summary):
        claims.append(FactCheckClaim(
            claim_text=match.group(),
            claim_type="event",
            expected_source="edgar",
            confidence=1.0
        ))

    logger.info(f"Extracted {len(claims)} claims from summary")
    return claims


def validate_claim(claim: FactCheckClaim, edgar_filings: List) -> FactCheckResult:
    """Validate a single claim against EDGAR data

    Args:
        claim: Claim to validate
        edgar_filings: List of EdgarFiling objects

    Returns:
        FactCheckResult with validation status
    """
    if claim.claim_type == "numeric":
        # Check if number exists in any filing
        for filing in edgar_filings:
            if claim.claim_text in filing.full_text:
                return FactCheckResult(
                    claim_id=claim.claim_id,
                    claim_text=claim.claim_text,
                    validation_status="verified",
                    evidence_text=f"Found in {filing.filing_type}",
                    similarity_score=1.0
                )

        return FactCheckResult(
            claim_id=claim.claim_id,
            claim_text=claim.claim_text,
            validation_status="failed",
            discrepancy_detail="Numeric value not found in filings"
        )

    elif claim.claim_type == "date":
        # Check if date matches any filing date
        try:
            claim_date = datetime.strptime(claim.claim_text, "%m/%d/%Y")
            for filing in edgar_filings:
                if filing.filing_date.date() == claim_date.date():
                    return FactCheckResult(
                        claim_id=claim.claim_id,
                        claim_text=claim.claim_text,
                        validation_status="verified",
                        evidence_text=f"Matches {filing.filing_type} filing date",
                        similarity_score=1.0
                    )
        except ValueError:
            pass

        return FactCheckResult(
            claim_id=claim.claim_id,
            claim_text=claim.claim_text,
            validation_status="failed",
            discrepancy_detail="Date does not match any filing"
        )

    elif claim.claim_type == "event":
        # Check if filing type exists
        for filing in edgar_filings:
            if claim.claim_text in filing.filing_type:
                return FactCheckResult(
                    claim_id=claim.claim_id,
                    claim_text=claim.claim_text,
                    validation_status="verified",
                    evidence_text=f"Filing type confirmed: {filing.filing_type}",
                    similarity_score=1.0
                )

        return FactCheckResult(
            claim_id=claim.claim_id,
            claim_text=claim.claim_text,
            validation_status="failed",
            discrepancy_detail=f"Filing type {claim.claim_text} not found"
        )

    return FactCheckResult(
        claim_id=claim.claim_id,
        claim_text=claim.claim_text,
        validation_status="uncertain",
        discrepancy_detail="Unable to verify"
    )


def fact_check_node(state: BatchGraphState, config: RunnableConfig) -> Dict[str, Any]:
    """Fact-check the generated summary

    Args:
        state: Current batch graph state
        config: Runnable configuration

    Returns:
        Updated state dict with fact_check_results and fact_check_status
    """
    logger.info(f"[FACT CHECKER] Validating summary for {state.ticker}")

    if not state.medium_summary:
        logger.warning(f"No summary to fact-check for {state.ticker}")
        return {
            "fact_check_status": "failed",
            "fact_check_results": [],
            "error_message": "No summary to fact-check"
        }

    try:
        # Extract claims
        claims = extract_claims(state.medium_summary)

        if not claims:
            logger.warning(f"No verifiable claims extracted from summary for {state.ticker}")
            # No claims means we can't verify, but also no false information
            return {
                "fact_check_results": [],
                "fact_check_status": "passed",
                "pass_rate": 1.0
            }

        # Validate each claim
        results = []
        for claim in claims:
            result = validate_claim(claim, state.edgar_filings)
            results.append(result)
            logger.debug(f"Claim '{claim.claim_text}': {result.validation_status}")

        # Calculate pass rate
        verified_count = sum(1 for r in results if r.validation_status == "verified")
        pass_rate = verified_count / len(results) if results else 0

        # Overall status: require 95% pass rate
        overall_status = "passed" if pass_rate >= 0.95 else "failed"

        logger.info(
            f"✅ Fact check complete for {state.ticker}: "
            f"{verified_count}/{len(results)} verified ({pass_rate:.1%})"
        )

        return {
            "fact_check_results": results,
            "fact_check_status": overall_status
        }

    except Exception as e:
        logger.error(f"❌ Fact checking failed for {state.ticker}: {str(e)}")
        return {
            "fact_check_results": [],
            "fact_check_status": "failed",
            "error_message": f"Fact check error: {str(e)}"
        }
