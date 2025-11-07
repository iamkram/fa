"""
FactSet API Client (Mocked for Development)

In production, replace with actual FactSet API calls.
"""

from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
import random
import logging

logger = logging.getLogger(__name__)


class FactSetClient:
    """Mock FactSet API client"""

    def __init__(self, api_key: str = None):
        self.api_key = api_key
        logger.info("FactSet client initialized (MOCK MODE)")

    async def fetch_price_data(self, ticker: str) -> Dict[str, Any]:
        """
        Fetch price and volume data

        In production: GET https://api.factset.com/price/v1/prices?ids={ticker}
        """
        logger.info(f"Fetching FactSet price data for {ticker} (MOCK)")

        # Generate realistic mock data
        base_price = random.uniform(50, 500)
        pct_change = random.uniform(-5, 5)

        return {
            "date": datetime.utcnow(),
            "open": round(base_price, 2),
            "close": round(base_price * (1 + pct_change/100), 2),
            "high": round(base_price * (1 + abs(pct_change)/100), 2),
            "low": round(base_price * (1 - abs(pct_change)/100), 2),
            "volume": random.randint(1000000, 50000000),
            "pct_change": round(pct_change, 2),
            "volume_vs_avg": round(random.uniform(0.5, 2.5), 2),
            "volatility_percentile": round(random.uniform(0.3, 0.9), 2)
        }

    async def fetch_fundamental_events(self, ticker: str) -> List[Dict[str, Any]]:
        """
        Fetch earnings, guidance, dividend events

        In production: GET https://api.factset.com/events/v1/events?ids={ticker}
        """
        logger.info(f"Fetching FactSet fundamental events for {ticker} (MOCK)")

        events = []

        # 40% chance of earnings event
        if random.random() > 0.6:
            quarter = f"Q{random.randint(1,4)}"
            eps = random.uniform(1, 5)
            revenue = random.randint(1, 50)
            events.append({
                "event_type": "earnings",
                "timestamp": datetime.utcnow() - timedelta(hours=random.randint(1, 23)),
                "details": f"{quarter} earnings: EPS ${eps:.2f}, Revenue ${revenue}B"
            })

        # 20% chance of guidance event
        if random.random() > 0.8:
            fy_eps = random.uniform(10, 20)
            fy_revenue = random.randint(50, 200)
            events.append({
                "event_type": "guidance",
                "timestamp": datetime.utcnow() - timedelta(hours=random.randint(1, 23)),
                "details": f"Raised FY guidance: EPS ${fy_eps:.2f}, Revenue ${fy_revenue}B"
            })

        # 15% chance of dividend event
        if random.random() > 0.85:
            div_amount = random.uniform(0.50, 2.0)
            events.append({
                "event_type": "dividend",
                "timestamp": datetime.utcnow() - timedelta(hours=random.randint(1, 23)),
                "details": f"Declared quarterly dividend of ${div_amount:.2f} per share"
            })

        return events
