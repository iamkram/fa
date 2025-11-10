"""
News Agent - ONE TOOL PATTERN

This agent has exactly ONE tool: fetch_current_news()

Fetches real-time market news via Perplexity API.
Part of the interactive supervisor architecture for FA meeting prep.
"""

import logging
import asyncio
from typing import List
from datetime import datetime

from langchain_core.tools import tool

from src.integrations.perplexity_client import PerplexityClient

logger = logging.getLogger(__name__)


# ============================================================================
# ONE TOOL: fetch_current_news
# ============================================================================

@tool
async def fetch_current_news(tickers: List[str], hours_back: int = 24) -> str:
    """
    Fetch real-time market news for specified tickers via Perplexity.

    This is the ONLY tool for the News Agent.

    Args:
        tickers: List of stock tickers (e.g., ["AAPL", "MSFT", "GOOGL"])
        hours_back: How many hours of news to retrieve (default 24)

    Returns:
        Formatted news summary with:
        - Recent headlines
        - Brief summaries
        - Dates and sources
        - Citations
    """
    try:
        logger.info(f"📰 Fetching news for {len(tickers)} tickers: {', '.join(tickers[:5])}...")

        async with PerplexityClient() as client:
            result = await client.get_current_news(
                tickers=tickers,
                hours_back=hours_back,
                max_items=15  # Limit to most important
            )

        news_items = result.get("news_items", [])
        citations = result.get("citations", [])
        as_of = result.get("as_of", datetime.utcnow().isoformat())

        # Format news items
        formatted_news = f"""
═══════════════════════════════════════════════════
CURRENT MARKET NEWS
═══════════════════════════════════════════════════

Tickers: {', '.join(tickers)}
Time Window: Last {hours_back} hours
As of: {as_of}

───────────────────────────────────────────────────
NEWS ITEMS ({len(news_items)} found)
───────────────────────────────────────────────────

{_format_news_items(news_items)}

───────────────────────────────────────────────────
SOURCES
───────────────────────────────────────────────────
{_format_citations(citations)}

═══════════════════════════════════════════════════
        """.strip()

        logger.info(f"✅ Retrieved {len(news_items)} news items")
        return formatted_news

    except Exception as e:
        logger.error(f"❌ Error fetching news: {str(e)}")
        return f"Error fetching news: {str(e)}"


# ============================================================================
# Helper Functions
# ============================================================================

def _format_news_items(news_items: List[dict]) -> str:
    """
    Format news items into readable text.

    Expected format per item:
    {
        "headline": str,
        "summary": str,
        "published_at": str,
        "source": str,
        "tickers": list[str],
        "category": str
    }
    """
    if not news_items:
        return "No recent news found for these tickers."

    lines = []

    for i, item in enumerate(news_items, 1):
        headline = item.get("headline", "No headline")
        summary = item.get("summary", "No summary available")
        published_at = item.get("published_at", "Unknown date")
        source = item.get("source", "Unknown source")
        affected_tickers = item.get("tickers", [])
        category = item.get("category", "other")

        # Category emoji
        category_emoji = {
            "earnings": "💰",
            "product": "🚀",
            "m&a": "🤝",
            "regulatory": "⚖️",
            "analyst": "📊",
            "other": "📌"
        }.get(category, "📌")

        lines.append(f"""
[{i}] {category_emoji} {headline}
    Date: {published_at}
    Source: {source}
    Affects: {', '.join(affected_tickers) if affected_tickers else 'General'}

    {summary}
        """.strip())

    return "\n\n".join(lines)


def _format_citations(citations: List[str]) -> str:
    """Format citation URLs"""
    if not citations:
        return "No citations available"

    lines = []
    for i, citation in enumerate(citations[:10], 1):  # Top 10 sources
        lines.append(f"[{i}] {citation}")

    return "\n".join(lines)


# ============================================================================
# Sync Wrapper (for non-async contexts)
# ============================================================================

def fetch_current_news_sync(tickers: List[str], hours_back: int = 24) -> str:
    """
    Synchronous wrapper for fetch_current_news.

    Use this when calling from non-async contexts.
    """
    return asyncio.run(fetch_current_news(tickers, hours_back))


# ============================================================================
# Usage Example
# ============================================================================

if __name__ == "__main__":
    # Test the agent
    async def test():
        result = await fetch_current_news(["AAPL", "MSFT", "GOOGL"], hours_back=48)
        print(result)

    asyncio.run(test())
