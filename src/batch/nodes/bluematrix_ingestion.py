from typing import Dict, Any, List
import asyncio
import logging

from src.batch.state import BatchGraphStatePhase2, AnalystReport
from src.shared.utils.bluematrix_client import BlueMatrixClient
from src.config.settings import settings

logger = logging.getLogger(__name__)


async def fetch_bluematrix_data(ticker: str) -> List[AnalystReport]:
    """Fetch and parse BlueMatrix analyst reports"""
    client = BlueMatrixClient(api_key=settings.bluematrix_api_key if hasattr(settings, 'bluematrix_api_key') else None)

    try:
        reports_data = await client.fetch_analyst_reports(ticker, lookback_hours=24)

        reports = []
        for report_data in reports_data:
            report = AnalystReport(**report_data)
            reports.append(report)

        logger.info(f"✅ Fetched {len(reports)} BlueMatrix reports for {ticker}")
        return reports

    except Exception as e:
        logger.error(f"❌ BlueMatrix fetch failed for {ticker}: {str(e)}")
        return []


def bluematrix_ingestion_node(state: BatchGraphStatePhase2, config) -> Dict[str, Any]:
    """LangGraph node for BlueMatrix data ingestion"""
    logger.info(f"[BlueMatrix] Fetching data for {state.ticker}")

    try:
        reports = asyncio.run(fetch_bluematrix_data(state.ticker))

        status = "success" if reports else "partial"

        logger.info(f"[BlueMatrix] Status: {status} ({len(reports)} reports)")

        return {
            "bluematrix_reports": reports,
            "bluematrix_status": status
        }
    except Exception as e:
        logger.error(f"❌ BlueMatrix ingestion failed: {str(e)}")
        return {
            "bluematrix_reports": [],
            "bluematrix_status": "failed",
            "error_message": str(e)
        }
