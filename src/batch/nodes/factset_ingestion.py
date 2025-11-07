import asyncio
import logging
from typing import Dict, Any

from src.batch.state import BatchGraphStatePhase2, PriceData, FundamentalEvent
from src.shared.utils.factset_client import FactSetClient
from src.config.settings import settings

logger = logging.getLogger(__name__)


async def fetch_factset_data(ticker: str):
    """Fetch FactSet price and fundamental data"""
    client = FactSetClient(api_key=settings.factset_api_key if hasattr(settings, 'factset_api_key') else None)

    # Fetch price data
    price_data_dict = await client.fetch_price_data(ticker)
    price_data = PriceData(**price_data_dict)

    # Fetch fundamental events
    events_data = await client.fetch_fundamental_events(ticker)
    events = [FundamentalEvent(**event) for event in events_data]

    return price_data, events


def factset_ingestion_node(state: BatchGraphStatePhase2, config) -> Dict[str, Any]:
    """LangGraph node for FactSet data ingestion"""
    logger.info(f"[FactSet] Fetching data for {state.ticker}")

    try:
        price_data, events = asyncio.run(fetch_factset_data(state.ticker))

        logger.info(f"✅ FactSet data fetched: price_data={price_data.close}, events={len(events)}")

        return {
            "factset_price_data": price_data,
            "factset_events": events,
            "factset_status": "success"
        }
    except Exception as e:
        logger.error(f"❌ FactSet ingestion failed: {str(e)}")
        return {
            "factset_price_data": None,
            "factset_events": [],
            "factset_status": "failed",
            "error_message": str(e)
        }
