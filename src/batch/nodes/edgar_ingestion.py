from langchain_core.runnables import RunnableConfig
from typing import Dict, Any, List, Union
from datetime import datetime, timedelta
import logging

from src.batch.state import BatchGraphState, BatchGraphStatePhase2, EdgarFiling

logger = logging.getLogger(__name__)

# Mocked EDGAR filing data for MVP testing
MOCK_EDGAR_FILINGS = {
    "AAPL": [
        {
            "filing_type": "8-K",
            "accession_number": "0000320193-25-000045",
            "filing_date": "2025-11-06",
            "items_reported": ["Item 2.02", "Item 9.01"],
            "material_events": ["Results of Operations and Financial Condition", "Financial Statements and Exhibits"],
            "url": "https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=0000320193",
            "full_text": """Apple Inc. (the "Company") issued a press release on November 6, 2025 announcing financial results for its fiscal 2025 fourth quarter ended September 28, 2025. The Company reported quarterly revenue of $94.9 billion, up 6 percent year over year. iPhone revenue was $46.2 billion, up 8 percent. Services revenue reached a new all-time high of $25.0 billion, up 12 percent year over year. The Company returned nearly $29 billion to shareholders during the quarter through dividends and share repurchases."""
        }
    ],
    "MSFT": [
        {
            "filing_type": "10-Q",
            "accession_number": "0000789019-25-000089",
            "filing_date": "2025-11-05",
            "items_reported": ["Part I - Financial Information"],
            "material_events": ["Quarterly Financial Results"],
            "url": "https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=0000789019",
            "full_text": """Microsoft Corporation reported revenue of $56.5 billion for Q1 FY2025, representing a 13% increase year-over-year. Intelligent Cloud revenue was $24.1 billion and increased 20% driven by Azure growth of 29%. Productivity and Business Processes revenue was $19.3 billion and increased 13%. More Personal Computing revenue was $13.2 billion and increased 3%."""
        }
    ],
    "GOOGL": [
        {
            "filing_type": "8-K",
            "accession_number": "0001652044-25-000123",
            "filing_date": "2025-11-04",
            "items_reported": ["Item 2.02"],
            "material_events": ["Results of Operations"],
            "url": "https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=0001652044",
            "full_text": """Alphabet Inc. announced financial results for the quarter ended September 30, 2025. Revenues were $76.7 billion, an increase of 11% year over year. Google Search & other revenues were $44.0 billion, up 12%. YouTube ads revenues were $7.9 billion, up 13%. Google Cloud revenues were $8.4 billion, up 35%. Operating income was $21.3 billion."""
        }
    ],
    "TSLA": [
        {
            "filing_type": "8-K",
            "accession_number": "0001564590-25-000567",
            "filing_date": "2025-11-07",
            "items_reported": ["Item 8.01"],
            "material_events": ["Other Events"],
            "url": "https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=0001318605",
            "full_text": """Tesla, Inc. announced that vehicle deliveries for Q3 2025 reached 462,890 vehicles, representing a 6% increase year over year. Production totaled 469,796 vehicles. The company continues to ramp production of Cybertruck and expand capacity at Gigafactory Texas."""
        }
    ],
    "JPM": [
        {
            "filing_type": "10-Q",
            "accession_number": "0000019617-25-000234",
            "filing_date": "2025-11-03",
            "items_reported": ["Part I - Financial Information"],
            "material_events": ["Quarterly Financial Results"],
            "url": "https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=0000019617",
            "full_text": """JPMorgan Chase & Co. reported net income of $13.2 billion for Q3 2025, up 7% year-over-year. Total revenues were $42.7 billion, up 6%. Net interest income was $23.0 billion, up 3%. Investment banking fees were $1.8 billion, up 31% driven by debt underwriting and M&A activity."""
        }
    ]
}


async def fetch_edgar_filings(
    ticker: str,
    company_name: str,
    lookback_hours: int = 24
) -> List[EdgarFiling]:
    """Fetch EDGAR filings for a stock (MOCKED for MVP)

    Args:
        ticker: Stock ticker symbol
        company_name: Company name
        lookback_hours: Hours to look back for filings

    Returns:
        List of EdgarFiling objects
    """
    logger.info(f"Fetching EDGAR filings for {ticker} (last {lookback_hours}h)")

    # Return mocked data if available
    if ticker in MOCK_EDGAR_FILINGS:
        mock_filings = MOCK_EDGAR_FILINGS[ticker]

        filings = []
        for filing_data in mock_filings:
            filing = EdgarFiling(
                filing_type=filing_data["filing_type"],
                accession_number=filing_data["accession_number"],
                filing_date=datetime.strptime(filing_data["filing_date"], "%Y-%m-%d"),
                items_reported=filing_data["items_reported"],
                material_events=filing_data["material_events"],
                url=filing_data["url"],
                full_text=filing_data["full_text"]
            )
            filings.append(filing)

        logger.info(f"Retrieved {len(filings)} mocked filings for {ticker}")
        return filings
    else:
        logger.warning(f"No mocked data available for {ticker}")
        return []


def edgar_ingestion_node(state: Union[BatchGraphState, BatchGraphStatePhase2], config: RunnableConfig) -> Dict[str, Any]:
    """LangGraph node for EDGAR data ingestion

    Args:
        state: Current batch graph state
        config: Runnable configuration

    Returns:
        Updated state dict with edgar_filings and edgar_status
    """
    logger.info(f"[EDGAR INGESTION] Fetching filings for {state.ticker}")

    try:
        import asyncio

        filings = asyncio.run(fetch_edgar_filings(
            state.ticker,
            state.company_name,
            lookback_hours=24
        ))

        if filings:
            logger.info(f"✅ Successfully fetched {len(filings)} filings for {state.ticker}")
            return {
                "edgar_filings": filings,
                "edgar_status": "success"
            }
        else:
            logger.warning(f"⚠️  No filings found for {state.ticker}")
            return {
                "edgar_filings": [],
                "edgar_status": "partial"
            }

    except Exception as e:
        logger.error(f"❌ EDGAR ingestion failed for {state.ticker}: {str(e)}")
        return {
            "edgar_filings": [],
            "edgar_status": "failed",
            "error_message": str(e)
        }
