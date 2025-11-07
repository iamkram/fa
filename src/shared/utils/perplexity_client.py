"""
Perplexity API Client (Mocked for Development)

In production, this would use the Perplexity API to fetch real-time
breaking news for stocks and financial markets.
"""

from typing import List, Dict, Any
from datetime import datetime, timedelta
import random
import logging

logger = logging.getLogger(__name__)


class PerplexityClient:
    """Mock Perplexity API client for real-time news"""

    def __init__(self, api_key: str = None):
        self.api_key = api_key
        logger.info("Perplexity client initialized (MOCK MODE)")

    async def search_news(
        self,
        query: str,
        lookback_hours: int = 4
    ) -> List[Dict[str, Any]]:
        """
        Search for breaking news

        In production:
        POST https://api.perplexity.ai/chat/completions
        """
        logger.info(f"Fetching Perplexity news for: {query} (MOCK)")

        # Generate mock news items
        mock_news = self._generate_mock_news(query)

        return mock_news

    def _generate_mock_news(self, query: str) -> List[Dict[str, Any]]:
        """Generate realistic mock news"""

        # Extract ticker if present
        import re
        ticker_match = re.search(r'([A-Z]{1,5})', query)
        ticker = ticker_match.group(1) if ticker_match else "STOCK"

        # 60% chance of having breaking news
        if random.random() > 0.4:
            news_types = [
                {
                    "headline": f"{ticker} announces major product launch, shares surge",
                    "summary": f"{ticker} unveiled its latest innovation at a press event, exceeding analyst expectations. The market reacted positively with shares gaining in after-hours trading."
                },
                {
                    "headline": f"Regulatory scrutiny intensifies for {ticker} amid market concerns",
                    "summary": f"Federal regulators announced increased oversight of {ticker}'s business practices, citing consumer protection concerns. The company stated it will cooperate fully."
                },
                {
                    "headline": f"{ticker} beats earnings estimates, raises guidance",
                    "summary": f"{ticker} reported better-than-expected quarterly results with revenue up significantly year-over-year. Management raised full-year guidance citing strong demand."
                },
                {
                    "headline": f"Analyst upgrades {ticker} citing strong fundamentals",
                    "summary": f"A major investment bank upgraded {ticker} to 'Buy' from 'Hold', citing improved market position and strong revenue growth prospects."
                }
            ]

            selected = random.choice(news_types)

            return [{
                "headline": selected["headline"],
                "source": random.choice(["Bloomberg", "Reuters", "CNBC", "WSJ", "Financial Times"]),
                "url": f"https://example.com/news/{random.randint(1000, 9999)}",
                "published_at": datetime.utcnow() - timedelta(hours=random.randint(1, 3)),
                "summary": selected["summary"],
                "relevance_score": random.uniform(0.8, 1.0)
            }]

        return []
