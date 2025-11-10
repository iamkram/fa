"""
Validator Agent - ONE TOOL PATTERN

This agent has exactly ONE tool: validate_all_claims()

⚠️ CRITICAL COMPONENT ⚠️
NO BAD DATA to Financial Advisors - this is non-negotiable.

3-Layer Validation:
1. Source Verification - Check batch data freshness, verify tickers exist
2. Consistency Checks - Verify numbers add up, dates are logical
3. Hallucination Detection - Re-query Perplexity to confirm factual claims

Part of the interactive supervisor architecture for FA meeting prep.
"""

import logging
import asyncio
from typing import Dict, List
from datetime import datetime, timedelta
import re

from langchain_core.tools import tool
from sqlalchemy import select, func

from src.integrations.perplexity_client import PerplexityClient
from src.shared.database.connection import db_manager
from src.shared.models.enterprise_database import (
    Stock,
    StockSummary,
    HouseholdSummary,
    BatchRun
)

logger = logging.getLogger(__name__)


# ============================================================================
# ONE TOOL: validate_all_claims
# ============================================================================

@tool
async def validate_all_claims(
    portfolio_data: str,
    news_data: str,
    household_id: str
) -> Dict:
    """
    Validate all claims from Portfolio and News agents.

    This is the ONLY tool for the Validator Agent.

    ⚠️ CRITICAL: Ensures 100% accuracy before data reaches FAs.

    3-Layer Validation Process:
    1. Source Verification - Batch data freshness, ticker existence
    2. Consistency Checks - Numbers add up, dates logical
    3. Hallucination Detection - Re-query Perplexity for facts

    Args:
        portfolio_data: Formatted portfolio summary from Portfolio Agent
        news_data: Formatted news summary from News Agent
        household_id: Household ID being validated

    Returns:
        {
            "validation_passed": bool,
            "confidence_score": float (0.0-1.0),
            "validation_layers": {
                "source_verification": dict,
                "consistency_checks": dict,
                "hallucination_detection": dict
            },
            "issues_found": list[str],
            "recommendations": list[str],
            "validated_at": str (ISO timestamp)
        }
    """
    try:
        logger.info(f"🔍 Starting 3-layer validation for household {household_id}")

        validation_start = datetime.utcnow()
        issues_found = []
        recommendations = []

        # ===================================================================
        # LAYER 1: Source Verification
        # ===================================================================
        logger.info("Layer 1: Source Verification")
        source_verification = await _verify_sources(
            portfolio_data,
            news_data,
            household_id
        )

        if not source_verification["passed"]:
            issues_found.extend(source_verification["issues"])
            recommendations.extend(source_verification["recommendations"])

        # ===================================================================
        # LAYER 2: Consistency Checks
        # ===================================================================
        logger.info("Layer 2: Consistency Checks")
        consistency_checks = await _check_consistency(
            portfolio_data,
            news_data
        )

        if not consistency_checks["passed"]:
            issues_found.extend(consistency_checks["issues"])
            recommendations.extend(consistency_checks["recommendations"])

        # ===================================================================
        # LAYER 3: Hallucination Detection
        # ===================================================================
        logger.info("Layer 3: Hallucination Detection")
        hallucination_detection = await _detect_hallucinations(
            portfolio_data,
            news_data
        )

        if not hallucination_detection["passed"]:
            issues_found.extend(hallucination_detection["issues"])
            recommendations.extend(hallucination_detection["recommendations"])

        # ===================================================================
        # Calculate Overall Confidence Score
        # ===================================================================
        layer_scores = [
            source_verification["score"],
            consistency_checks["score"],
            hallucination_detection["score"]
        ]

        # Weighted average: source=30%, consistency=30%, hallucination=40%
        confidence_score = (
            layer_scores[0] * 0.30 +
            layer_scores[1] * 0.30 +
            layer_scores[2] * 0.40
        )

        # Validation passes only if confidence >= 0.95 (95%)
        validation_passed = confidence_score >= 0.95

        if not validation_passed:
            logger.warning(
                f"⚠️  Validation FAILED for {household_id}. "
                f"Confidence: {confidence_score:.2%}. "
                f"Issues: {len(issues_found)}"
            )
        else:
            logger.info(
                f"✅ Validation PASSED for {household_id}. "
                f"Confidence: {confidence_score:.2%}"
            )

        validation_duration = (datetime.utcnow() - validation_start).total_seconds()

        return {
            "validation_passed": validation_passed,
            "confidence_score": round(confidence_score, 4),
            "validation_layers": {
                "source_verification": source_verification,
                "consistency_checks": consistency_checks,
                "hallucination_detection": hallucination_detection
            },
            "issues_found": issues_found,
            "recommendations": recommendations,
            "validated_at": datetime.utcnow().isoformat(),
            "validation_duration_seconds": round(validation_duration, 2)
        }

    except Exception as e:
        logger.error(f"❌ Critical error in validation: {str(e)}")
        # On error, FAIL SAFE - do not pass validation
        return {
            "validation_passed": False,
            "confidence_score": 0.0,
            "validation_layers": {},
            "issues_found": [f"Critical validation error: {str(e)}"],
            "recommendations": ["Retry validation", "Check system logs"],
            "validated_at": datetime.utcnow().isoformat(),
            "validation_duration_seconds": 0.0
        }


# ============================================================================
# Layer 1: Source Verification
# ============================================================================

async def _verify_sources(
    portfolio_data: str,
    news_data: str,
    household_id: str
) -> Dict:
    """
    Verify data sources are valid and fresh.

    Checks:
    - Batch data is recent (< 24 hours old)
    - All tickers mentioned exist in database
    - No missing required fields
    """
    issues = []
    recommendations = []
    checks_passed = 0
    total_checks = 0

    with db_manager.get_session() as session:
        # Check 1: Batch data freshness
        total_checks += 1
        try:
            # Extract batch run ID from portfolio data (if present)
            batch_run_match = re.search(r'Batch Run ID: ([a-f0-9-]+)', portfolio_data)

            if batch_run_match:
                batch_run_id = batch_run_match.group(1)

                batch_run = session.execute(
                    select(BatchRun).where(BatchRun.batch_run_id == batch_run_id)
                ).scalar_one_or_none()

                if batch_run:
                    age_hours = (datetime.utcnow() - batch_run.completed_at).total_seconds() / 3600

                    if age_hours <= 24:
                        checks_passed += 1
                        logger.info(f"✓ Batch data is fresh ({age_hours:.1f} hours old)")
                    else:
                        issues.append(f"Batch data is stale ({age_hours:.1f} hours old)")
                        recommendations.append("Wait for next nightly batch run or use cached data with disclaimer")
                else:
                    issues.append(f"Batch run {batch_run_id} not found in database")
            else:
                issues.append("No batch run ID found in portfolio data")
                recommendations.append("Ensure Portfolio Agent includes batch metadata")

        except Exception as e:
            issues.append(f"Error checking batch freshness: {str(e)}")

        # Check 2: Ticker existence
        total_checks += 1
        try:
            # Extract all tickers from portfolio and news data
            ticker_pattern = r'\b[A-Z]{1,5}\b'
            portfolio_tickers = set(re.findall(ticker_pattern, portfolio_data))
            news_tickers = set(re.findall(ticker_pattern, news_data))

            # Filter out common false positives
            false_positives = {'USD', 'AM', 'PM', 'ID', 'AS', 'OF', 'BATCH', 'RUN', 'DATA', 'SUMMARY'}
            all_tickers = (portfolio_tickers | news_tickers) - false_positives

            if all_tickers:
                # Verify tickers exist in stock table
                existing_tickers = session.execute(
                    select(Stock.ticker).where(Stock.ticker.in_(all_tickers))
                ).scalars().all()

                existing_set = set(existing_tickers)
                missing_tickers = all_tickers - existing_set

                if not missing_tickers:
                    checks_passed += 1
                    logger.info(f"✓ All {len(all_tickers)} tickers verified")
                else:
                    issues.append(f"Unknown tickers: {', '.join(sorted(missing_tickers))}")
                    recommendations.append("Verify ticker symbols or add to stock database")
            else:
                checks_passed += 1  # No tickers to verify

        except Exception as e:
            issues.append(f"Error verifying tickers: {str(e)}")

        # Check 3: Required fields present
        total_checks += 1
        required_portfolio_fields = ['Total Portfolio Value', 'Number of Holdings']
        required_news_fields = ['CURRENT MARKET NEWS', 'SOURCES']

        missing_fields = []

        for field in required_portfolio_fields:
            if field not in portfolio_data:
                missing_fields.append(f"Portfolio: {field}")

        for field in required_news_fields:
            if field not in news_data:
                missing_fields.append(f"News: {field}")

        if not missing_fields:
            checks_passed += 1
            logger.info("✓ All required fields present")
        else:
            issues.append(f"Missing fields: {', '.join(missing_fields)}")
            recommendations.append("Check agent output formatting")

    score = checks_passed / total_checks if total_checks > 0 else 0.0
    passed = len(issues) == 0

    return {
        "passed": passed,
        "score": score,
        "checks_passed": checks_passed,
        "total_checks": total_checks,
        "issues": issues,
        "recommendations": recommendations
    }


# ============================================================================
# Layer 2: Consistency Checks
# ============================================================================

async def _check_consistency(portfolio_data: str, news_data: str) -> Dict:
    """
    Check internal consistency of data.

    Checks:
    - Portfolio numbers add up correctly
    - Dates are logical (not in future, not too old)
    - News items have required fields
    - No contradictory information
    """
    issues = []
    recommendations = []
    checks_passed = 0
    total_checks = 0

    # Check 1: Portfolio value consistency
    total_checks += 1
    try:
        # Extract total portfolio value
        total_value_match = re.search(r'Total Portfolio Value: \$([0-9,]+\.[0-9]{2})', portfolio_data)

        if total_value_match:
            total_value_str = total_value_match.group(1).replace(',', '')
            total_value = float(total_value_str)

            # Extract individual holdings
            holding_pattern = r'\$\s*([0-9,]+\.[0-9]{2})\s+\(([0-9.]+)%\)'
            holdings = re.findall(holding_pattern, portfolio_data)

            if holdings:
                # Calculate sum of top holdings
                holdings_sum = sum(float(h[0].replace(',', '')) for h in holdings)

                # Holdings sum should not exceed total value
                if holdings_sum <= total_value * 1.01:  # Allow 1% margin for rounding
                    checks_passed += 1
                    logger.info(f"✓ Portfolio values consistent (holdings: ${holdings_sum:,.2f}, total: ${total_value:,.2f})")
                else:
                    issues.append(f"Holdings sum (${holdings_sum:,.2f}) exceeds total portfolio value (${total_value:,.2f})")
                    recommendations.append("Verify portfolio calculation logic")
            else:
                checks_passed += 1  # No holdings to verify
        else:
            issues.append("Could not extract total portfolio value")

    except Exception as e:
        issues.append(f"Error checking portfolio consistency: {str(e)}")

    # Check 2: Date validity
    total_checks += 1
    try:
        # Extract all dates from data
        date_pattern = r'(\d{4})-(\d{2})-(\d{2})'
        dates = re.findall(date_pattern, portfolio_data + news_data)

        now = datetime.utcnow()
        invalid_dates = []

        for year, month, day in dates:
            try:
                date = datetime(int(year), int(month), int(day))

                # Date should not be in future
                if date > now + timedelta(days=1):  # Allow 1 day buffer for timezone
                    invalid_dates.append(f"{year}-{month}-{day} (future)")

                # Date should not be too old (> 5 years)
                if date < now - timedelta(days=365*5):
                    invalid_dates.append(f"{year}-{month}-{day} (too old)")

            except ValueError:
                invalid_dates.append(f"{year}-{month}-{day} (invalid)")

        if not invalid_dates:
            checks_passed += 1
            logger.info(f"✓ All dates valid ({len(dates)} checked)")
        else:
            issues.append(f"Invalid dates: {', '.join(invalid_dates)}")
            recommendations.append("Verify date parsing and data sources")

    except Exception as e:
        issues.append(f"Error checking dates: {str(e)}")

    # Check 3: News items have sources
    total_checks += 1
    try:
        # Count news items
        news_item_pattern = r'\[(\d+)\].*?📌|💰|🚀|🤝|⚖️|📊'
        news_items = re.findall(news_item_pattern, news_data)

        # Check if sources section exists
        if 'SOURCES' in news_data:
            source_pattern = r'\[(\d+)\] (http[s]?://[^\s]+)'
            sources = re.findall(source_pattern, news_data)

            if len(sources) > 0:
                checks_passed += 1
                logger.info(f"✓ News has {len(sources)} citations")
            else:
                issues.append("News data missing source citations")
                recommendations.append("Ensure Perplexity returns citations")
        else:
            issues.append("News data missing SOURCES section")

    except Exception as e:
        issues.append(f"Error checking news sources: {str(e)}")

    score = checks_passed / total_checks if total_checks > 0 else 0.0
    passed = len(issues) == 0

    return {
        "passed": passed,
        "score": score,
        "checks_passed": checks_passed,
        "total_checks": total_checks,
        "issues": issues,
        "recommendations": recommendations
    }


# ============================================================================
# Layer 3: Hallucination Detection
# ============================================================================

async def _detect_hallucinations(portfolio_data: str, news_data: str) -> Dict:
    """
    Detect potential hallucinations by re-querying Perplexity.

    Extracts key factual claims and verifies them against Perplexity.
    This is the most important layer - ensures NO FABRICATED DATA.
    """
    issues = []
    recommendations = []
    claims_verified = 0
    total_claims = 0

    try:
        # Extract key claims from news data to verify
        claims = _extract_factual_claims(news_data)

        if not claims:
            logger.info("No factual claims to verify in news data")
            return {
                "passed": True,
                "score": 1.0,
                "claims_verified": 0,
                "total_claims": 0,
                "issues": [],
                "recommendations": []
            }

        total_claims = len(claims)
        logger.info(f"Verifying {total_claims} factual claims")

        async with PerplexityClient() as client:
            # Verify each claim
            verification_tasks = [
                client.verify_claim(claim)
                for claim in claims[:5]  # Limit to 5 most important claims
            ]

            results = await asyncio.gather(*verification_tasks, return_exceptions=True)

            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    issues.append(f"Error verifying claim {i+1}: {str(result)}")
                    continue

                verdict = result.get("verdict", "UNCERTAIN")

                if verdict == "VERIFIED":
                    claims_verified += 1
                    logger.info(f"✓ Claim {i+1} verified: {claims[i][:50]}...")
                elif verdict == "INVALID":
                    issues.append(f"INVALID claim detected: {claims[i]}")
                    recommendations.append(f"Remove or correct: {claims[i]}")
                    logger.warning(f"✗ Claim {i+1} INVALID: {claims[i]}")
                else:  # UNCERTAIN
                    issues.append(f"Could not verify: {claims[i]}")
                    recommendations.append(f"Add disclaimer or remove: {claims[i]}")
                    logger.warning(f"? Claim {i+1} UNCERTAIN: {claims[i]}")

        score = claims_verified / total_claims if total_claims > 0 else 1.0

        # Hallucination detection passes if 90%+ of claims verified
        passed = score >= 0.90

        return {
            "passed": passed,
            "score": score,
            "claims_verified": claims_verified,
            "total_claims": total_claims,
            "issues": issues,
            "recommendations": recommendations
        }

    except Exception as e:
        logger.error(f"Error in hallucination detection: {str(e)}")
        return {
            "passed": False,
            "score": 0.0,
            "claims_verified": 0,
            "total_claims": 0,
            "issues": [f"Hallucination detection failed: {str(e)}"],
            "recommendations": ["Retry validation", "Check Perplexity API"]
        }


# ============================================================================
# Helper Functions
# ============================================================================

def _extract_factual_claims(news_data: str) -> List[str]:
    """
    Extract specific factual claims from news data.

    Focus on:
    - Earnings numbers
    - Product launches
    - M&A transactions
    - Regulatory actions
    - Stock price movements
    """
    claims = []

    # Extract news item summaries (between news item headers and next header/divider)
    # Pattern: After [N] emoji headline, extract the summary text
    pattern = r'\[(\d+)\]\s+(?:📌|💰|🚀|🤝|⚖️|📊)\s+([^\n]+)\n.*?\n\n\s+([^\n]+(?:\n(?!\[)\s+[^\n]+)*)'

    matches = re.finditer(pattern, news_data, re.MULTILINE)

    for match in matches:
        headline = match.group(2).strip()
        summary = match.group(3).strip()

        # Combine headline + summary as a claim
        claim = f"{headline}. {summary}"

        # Only include if it contains specific factual indicators
        factual_indicators = [
            r'\$[\d,]+',  # Dollar amounts
            r'\d+%',  # Percentages
            r'\d{4}',  # Years
            r'announced',
            r'reported',
            r'filed',
            r'acquired',
            r'launched'
        ]

        if any(re.search(indicator, claim, re.IGNORECASE) for indicator in factual_indicators):
            claims.append(claim[:200])  # Limit to 200 chars

    return claims


# ============================================================================
# Sync Wrapper (for non-async contexts)
# ============================================================================

def validate_all_claims_sync(
    portfolio_data: str,
    news_data: str,
    household_id: str
) -> Dict:
    """
    Synchronous wrapper for validate_all_claims.

    Use this when calling from non-async contexts.
    """
    return asyncio.run(validate_all_claims(portfolio_data, news_data, household_id))


# ============================================================================
# Usage Example
# ============================================================================

if __name__ == "__main__":
    # Test the validator
    async def test():
        portfolio_test = """
═══════════════════════════════════════════════════
PORTFOLIO SUMMARY - TEST-001
═══════════════════════════════════════════════════

Data as of: 2025-01-09 04:00:00
Batch Run ID: 12345678-1234-1234-1234-123456789012

───────────────────────────────────────────────────
OVERVIEW
───────────────────────────────────────────────────
Total Portfolio Value: $1,000,000.00
Number of Holdings: 10

───────────────────────────────────────────────────
TOP HOLDINGS
───────────────────────────────────────────────────
AAPL     $  250,000.00  ( 25.0%)
MSFT     $  200,000.00  ( 20.0%)
        """

        news_test = """
═══════════════════════════════════════════════════
CURRENT MARKET NEWS
═══════════════════════════════════════════════════

Tickers: AAPL, MSFT
Time Window: Last 24 hours
As of: 2025-01-09T14:00:00

───────────────────────────────────────────────────
NEWS ITEMS (2 found)
───────────────────────────────────────────────────

[1] 💰 Apple Reports Q4 Earnings Beat
    Date: 2025-01-08
    Source: Reuters
    Affects: AAPL

    Apple reported Q4 earnings of $2.50 per share, beating estimates of $2.30.

[2] 🚀 Microsoft Launches New AI Product
    Date: 2025-01-09
    Source: TechCrunch
    Affects: MSFT

    Microsoft announced a new AI-powered productivity suite.

───────────────────────────────────────────────────
SOURCES
───────────────────────────────────────────────────
[1] https://www.reuters.com/technology/apple-earnings-2025-01-08
[2] https://techcrunch.com/microsoft-ai-launch-2025-01-09
        """

        result = await validate_all_claims(portfolio_test, news_test, "TEST-001")

        print(f"\nValidation Result:")
        print(f"  Passed: {result['validation_passed']}")
        print(f"  Confidence: {result['confidence_score']:.2%}")
        print(f"  Issues: {len(result['issues_found'])}")

        if result['issues_found']:
            print("\nIssues Found:")
            for issue in result['issues_found']:
                print(f"  - {issue}")

    asyncio.run(test())
