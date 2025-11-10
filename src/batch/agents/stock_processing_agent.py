"""
Stock Processing Agent - ONE TOOL PATTERN

This agent has exactly ONE tool: fetch_10k_8k_via_perplexity()

Used in Phase 2 of nightly batch processing to:
- Fetch latest 10-K and 8-K SEC filings via Perplexity
- Summarize key business information
- Save to stock_summaries table

Part of enterprise supervisor architecture.
"""

import logging
import asyncio
from typing import Dict, List
from datetime import datetime
import uuid

from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from sqlalchemy import select

from src.integrations.perplexity_client import PerplexityClient
from src.shared.database.connection import db_manager
from src.shared.models.enterprise_database import Stock, StockSummary, BatchRun

logger = logging.getLogger(__name__)


# ============================================================================
# ONE TOOL: fetch_10k_8k_via_perplexity
# ============================================================================

@tool
async def fetch_10k_8k_via_perplexity(ticker: str, batch_run_id: str) -> Dict:
    """
    Fetch and summarize latest 10-K and 8-K SEC filings via Perplexity.

    This is the ONLY tool for the Stock Processing Agent.

    Args:
        ticker: Stock ticker symbol (e.g., "AAPL")
        batch_run_id: UUID of current batch run for tracking

    Returns:
        {
            "ticker": str,
            "summary": str,  # 200-word summary
            "filing_date": str,
            "citations": list[str],
            "success": bool,
            "error": str | None
        }
    """
    try:
        logger.info(f"🔍 Fetching 10-K/8-K for {ticker} via Perplexity...")

        # Use Perplexity to fetch SEC filings
        async with PerplexityClient() as client:
            result = await client.get_10k_8k(ticker)

        # Extract summary components
        filing_date = result.get("filing_date")
        business_summary = result.get("business_summary", "")
        financials = result.get("financials", "")
        risks = result.get("risks", "")

        # Combine into 200-word summary
        full_summary = f"""
{business_summary}

Recent Financials: {financials}

Key Risks: {risks}
        """.strip()

        # Ensure it's concise (target 200 words)
        llm = ChatOpenAI(model="gpt-4o", temperature=0)
        condensed_summary = await llm.ainvoke(
            f"Condense this to exactly 200 words, keeping all key facts:\n\n{full_summary}"
        )

        summary_text = condensed_summary.content

        # Save to database
        with db_manager.get_session() as session:
            # Check if stock exists, create if not
            stock = session.execute(
                select(Stock).where(Stock.ticker == ticker)
            ).scalar_one_or_none()

            if not stock:
                logger.warning(f"Stock {ticker} not found in database, skipping summary save")
                # In production, you might want to create the stock here

            # Create stock summary
            stock_summary = StockSummary(
                summary_id=uuid.uuid4(),
                ticker=ticker,
                batch_run_id=batch_run_id,
                summary=summary_text,
                filing_date=datetime.fromisoformat(filing_date) if filing_date else None,
                perplexity_citations={"citations": result.get("citations", [])},
                created_at=datetime.utcnow()
            )

            session.add(stock_summary)
            session.commit()

            logger.info(f"✅ Saved stock summary for {ticker}")

        return {
            "ticker": ticker,
            "summary": summary_text,
            "filing_date": filing_date,
            "citations": result.get("citations", []),
            "success": True,
            "error": None
        }

    except Exception as e:
        logger.error(f"❌ Error processing {ticker}: {str(e)}")
        return {
            "ticker": ticker,
            "summary": "",
            "filing_date": None,
            "citations": [],
            "success": False,
            "error": str(e)
        }


# ============================================================================
# Parallel Processing Helper (for Batch Assistant Graph)
# ============================================================================

async def process_stocks_parallel(
    batch_run_id: str,
    tickers: List[str] = None,
    max_workers: int = 100
) -> Dict:
    """
    Process multiple stocks in parallel using the stock processing agent.

    This function is called by the Batch Assistant Graph during Phase 2.

    Args:
        batch_run_id: UUID of current batch run
        tickers: List of tickers to process (if None, fetch from database)
        max_workers: Maximum parallel workers (default 100 for ~5,000 stocks)

    Returns:
        {
            "count": int,  # Number processed
            "errors": list[str],  # Any errors encountered
            "duration_seconds": float
        }
    """
    start_time = datetime.utcnow()

    # Get tickers if not provided
    if tickers is None:
        with db_manager.get_session() as session:
            # Get all unique tickers from holdings
            result = session.execute("""
                SELECT DISTINCT ticker
                FROM holdings
                WHERE is_active = true
            """)
            tickers = [row[0] for row in result]

    logger.info(f"📊 Processing {len(tickers)} stocks with {max_workers} parallel workers")

    # Process in batches to respect max_workers
    processed_count = 0
    errors = []

    # Split into batches of max_workers
    ticker_batches = [
        tickers[i:i + max_workers]
        for i in range(0, len(tickers), max_workers)
    ]

    for batch_num, ticker_batch in enumerate(ticker_batches, 1):
        logger.info(f"Processing batch {batch_num}/{len(ticker_batches)}")

        # Create tasks for this batch
        tasks = [
            fetch_10k_8k_via_perplexity(ticker, batch_run_id)
            for ticker in ticker_batch
        ]

        # Execute in parallel
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Count successes and errors
        for result in results:
            if isinstance(result, Exception):
                errors.append(str(result))
            elif result.get("success"):
                processed_count += 1
            else:
                errors.append(f"{result['ticker']}: {result.get('error', 'Unknown error')}")

    duration = (datetime.utcnow() - start_time).total_seconds()

    logger.info(f"✅ Completed stock processing: {processed_count}/{len(tickers)} successful in {duration:.1f}s")

    return {
        "count": processed_count,
        "errors": errors,
        "duration_seconds": duration
    }


# ============================================================================
# Usage Example
# ============================================================================

if __name__ == "__main__":
    # Test the agent with a single stock
    async def test():
        batch_run_id = str(uuid.uuid4())
        result = await fetch_10k_8k_via_perplexity("AAPL", batch_run_id)
        print(f"Result: {result}")

    asyncio.run(test())
