"""
News Research Node

Fetches real-time breaking news via Perplexity API.
In production, this would use actual Perplexity API for up-to-date news.
"""

import asyncio
import logging
from typing import Dict, Any

from src.interactive.state import InteractiveGraphState, NewsItem
from src.shared.utils.perplexity_client import PerplexityClient
from src.config.settings import settings

logger = logging.getLogger(__name__)


def news_research_node(state: InteractiveGraphState, config) -> Dict[str, Any]:
    """Fetch real-time news via Perplexity"""
    logger.info(f"[News] Researching for query: {state.sanitized_query[:50]}...")

    client = PerplexityClient(api_key=getattr(settings, 'perplexity_api_key', None))

    try:
        # Extract tickers from query or edo context
        tickers = []
        if state.edo_context and state.edo_context.total_exposure:
            tickers = list(state.edo_context.total_exposure.keys())[:3]  # Top 3 holdings

        # Build search query
        if tickers:
            search_query = f"breaking news last 4 hours {' '.join(tickers)}"
        else:
            search_query = state.sanitized_query

        # Fetch news
        news_data = asyncio.run(client.search_news(
            query=search_query,
            lookback_hours=4
        ))

        # Convert to NewsItem objects
        news_items = []
        for item in news_data:
            news_items.append(NewsItem(**item))

        logger.info(f"[News] Found {len(news_items)} relevant news items")

        return {"news_items": news_items}

    except Exception as e:
        logger.error(f"[News] Research failed: {str(e)}")
        return {
            "news_items": [],
            "error_message": f"News research failed: {str(e)}"
        }
