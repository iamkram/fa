"""
Report Writer Agent - ONE TOOL PATTERN

This agent has exactly ONE tool: generate_meeting_report()

Assembles validated portfolio data and news into a coherent meeting brief.
Uses Claude Sonnet 4.5 for high-quality narrative generation.

Part of the interactive supervisor architecture for FA meeting prep.
"""

import logging
from typing import Dict
from datetime import datetime

from langchain_core.tools import tool
from langchain_anthropic import ChatAnthropic

logger = logging.getLogger(__name__)


# ============================================================================
# ONE TOOL: generate_meeting_report
# ============================================================================

@tool
def generate_meeting_report(
    household_id: str,
    fa_id: str,
    portfolio_data: str,
    news_data: str,
    validation_result: Dict
) -> str:
    """
    Generate final meeting prep report using Claude Sonnet 4.5.

    This is the ONLY tool for the Report Writer Agent.

    Combines validated portfolio and news data into a coherent narrative
    that Financial Advisors can use for client meetings.

    Args:
        household_id: Household identifier
        fa_id: Financial Advisor identifier
        portfolio_data: Validated portfolio summary from Portfolio Agent
        news_data: Validated news summary from News Agent
        validation_result: Validation results from Validator Agent

    Returns:
        Formatted meeting prep report (markdown) with:
        - Executive summary
        - Portfolio overview
        - Market news highlights
        - Discussion topics
        - Validation confidence notice (if needed)
        - Metadata (timestamps, citations)
    """
    try:
        logger.info(f"📝 Generating meeting report for household {household_id}")

        # Extract validation details
        validation_passed = validation_result.get("validation_passed", False)
        confidence_score = validation_result.get("confidence_score", 0.0)
        issues_found = validation_result.get("issues_found", [])

        # Use Claude Sonnet 4.5 for report generation
        llm = ChatAnthropic(
            model="claude-sonnet-4-5-20250929",
            temperature=0.3,  # Some creativity, but mostly factual
            max_tokens=4000
        )

        # Build the prompt for Claude
        prompt = f"""You are a Financial Advisor AI Assistant generating a meeting preparation brief.

You will receive:
1. Portfolio data (from nightly batch processing)
2. Real-time market news
3. Validation results

Your task: Create a concise, professional meeting prep report that an FA can use to prepare for a client meeting.

CRITICAL REQUIREMENTS:
- Be factual and data-driven
- Use ONLY information provided (no hallucinations)
- Highlight key talking points
- Keep it concise (500-800 words)
- Use professional but accessible language
- Include specific numbers and dates
- Organize logically: Executive Summary → Portfolio → News → Discussion Topics

---

HOUSEHOLD: {household_id}
FA: {fa_id}

PORTFOLIO DATA:
{portfolio_data}

MARKET NEWS:
{news_data}

VALIDATION STATUS:
- Confidence Score: {confidence_score:.2%}
- Validation Passed: {"✅ YES" if validation_passed else "❌ NO"}
- Issues: {len(issues_found)}

---

Generate a meeting prep report in markdown format with these sections:

# Meeting Prep Brief - [Household Name]

## Executive Summary
[2-3 sentence overview of portfolio status and key market developments]

## Portfolio Overview
[Summarize current holdings, total value, top positions, sector allocation]

## Market News Highlights
[Key news affecting this portfolio's holdings - focus on actionable insights]

## Discussion Topics for Meeting
[3-5 specific topics the FA should discuss with the client]

## Data Quality & Sources
[Mention when batch data was generated, news recency, confidence level]

---

Remember:
- Be specific with numbers
- Cite dates
- Keep it professional
- Focus on what the FA needs to know for the meeting
"""

        # Generate the report
        logger.info("Invoking Claude Sonnet 4.5 for report generation...")
        response = llm.invoke(prompt)

        meeting_report = response.content

        # Add validation disclaimer if confidence is low
        if not validation_passed or confidence_score < 0.95:
            disclaimer = _generate_validation_disclaimer(
                confidence_score,
                issues_found,
                validation_result.get("recommendations", [])
            )

            meeting_report = f"{meeting_report}\n\n{disclaimer}"

        # Add metadata footer
        footer = _generate_report_footer(
            household_id,
            fa_id,
            validation_result
        )

        final_report = f"{meeting_report}\n\n{footer}"

        logger.info(f"✅ Generated meeting report ({len(final_report)} chars)")

        return final_report

    except Exception as e:
        logger.error(f"❌ Error generating meeting report: {str(e)}")

        # Fallback: return basic structured report
        return _generate_fallback_report(
            household_id,
            fa_id,
            portfolio_data,
            news_data,
            str(e)
        )


# ============================================================================
# Helper Functions
# ============================================================================

def _generate_validation_disclaimer(
    confidence_score: float,
    issues_found: list,
    recommendations: list
) -> str:
    """
    Generate a disclaimer when validation confidence is low.
    """
    disclaimer = f"""
---

## ⚠️ Data Quality Notice

**Validation Confidence: {confidence_score:.1%}**

This report's data validation did not meet the standard 95% confidence threshold.

**Issues Detected:**
"""

    for i, issue in enumerate(issues_found[:5], 1):  # Top 5 issues
        disclaimer += f"\n{i}. {issue}"

    if recommendations:
        disclaimer += "\n\n**Recommendations:**\n"
        for i, rec in enumerate(recommendations[:3], 1):  # Top 3 recommendations
            disclaimer += f"\n{i}. {rec}"

    disclaimer += """

**Action Required:**
- Verify critical data points before client meeting
- Use this report as a preliminary guide only
- Consider waiting for next batch run if issues are material
"""

    return disclaimer


def _generate_report_footer(
    household_id: str,
    fa_id: str,
    validation_result: Dict
) -> str:
    """
    Generate metadata footer for the report.
    """
    validated_at = validation_result.get("validated_at", datetime.utcnow().isoformat())
    validation_duration = validation_result.get("validation_duration_seconds", 0.0)

    footer = f"""
---

## Report Metadata

**Generated:** {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}
**Household ID:** {household_id}
**FA ID:** {fa_id}
**Validation Completed:** {validated_at}
**Validation Duration:** {validation_duration:.2f}s

**Data Sources:**
- Portfolio: Nightly batch processing (2-6 AM)
- Market News: Perplexity API (real-time)
- Validation: 3-layer verification (source, consistency, hallucination)

**Powered by:**
- LangGraph Supervisor Architecture
- Claude Sonnet 4.5 (Report Generation)
- GPT-4o (Data Processing)
- Perplexity Sonar (Market Intelligence)

---

*This report is generated by AI and should be reviewed by the Financial Advisor before client presentation.*
"""

    return footer


def _generate_fallback_report(
    household_id: str,
    fa_id: str,
    portfolio_data: str,
    news_data: str,
    error_message: str
) -> str:
    """
    Generate a basic fallback report if Claude generation fails.
    """
    return f"""
# Meeting Prep Brief - {household_id}

## ⚠️ Report Generation Error

An error occurred while generating the narrative report: {error_message}

Below is the raw data that was collected:

---

## Portfolio Data

{portfolio_data}

---

## Market News

{news_data}

---

## Report Metadata

**Generated:** {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}
**Household ID:** {household_id}
**FA ID:** {fa_id}
**Status:** Fallback report due to generation error

*Please review the raw data above and manually prepare meeting talking points.*
"""


# ============================================================================
# Usage Example
# ============================================================================

if __name__ == "__main__":
    # Test the report writer
    portfolio_test = """
═══════════════════════════════════════════════════
PORTFOLIO SUMMARY - JOHNSON-001
═══════════════════════════════════════════════════

Data as of: 2025-01-09 04:00:00
Batch Run ID: 12345678-1234-1234-1234-123456789012

───────────────────────────────────────────────────
OVERVIEW
───────────────────────────────────────────────────
Total Portfolio Value: $2,500,000.00
Number of Holdings: 15

───────────────────────────────────────────────────
TOP HOLDINGS
───────────────────────────────────────────────────
AAPL     $  625,000.00  ( 25.0%)
MSFT     $  500,000.00  ( 20.0%)
GOOGL    $  375,000.00  ( 15.0%)

───────────────────────────────────────────────────
SECTOR ALLOCATION
───────────────────────────────────────────────────
Technology           ████████████████████  60.0%
Healthcare           ████████              20.0%
Finance              ████                  10.0%
    """

    news_test = """
═══════════════════════════════════════════════════
CURRENT MARKET NEWS
═══════════════════════════════════════════════════

Tickers: AAPL, MSFT, GOOGL
Time Window: Last 24 hours
As of: 2025-01-09T14:00:00

───────────────────────────────────────────────────
NEWS ITEMS (3 found)
───────────────────────────────────────────────────

[1] 💰 Apple Reports Q4 Earnings Beat
    Date: 2025-01-08
    Source: Reuters
    Affects: AAPL

    Apple reported Q4 earnings of $2.50 per share, beating estimates.

[2] 🚀 Microsoft Launches New AI Product
    Date: 2025-01-09
    Source: TechCrunch
    Affects: MSFT

    Microsoft announced a new AI-powered productivity suite.

[3] 📊 Google Stock Upgraded by Analyst
    Date: 2025-01-09
    Source: Bloomberg
    Affects: GOOGL

    JPMorgan upgraded Google to Overweight with $180 target.
    """

    validation_test = {
        "validation_passed": True,
        "confidence_score": 0.98,
        "issues_found": [],
        "recommendations": [],
        "validated_at": datetime.utcnow().isoformat(),
        "validation_duration_seconds": 2.5
    }

    report = generate_meeting_report(
        household_id="JOHNSON-001",
        fa_id="FA-001",
        portfolio_data=portfolio_test,
        news_data=news_test,
        validation_result=validation_test
    )

    print(report)
