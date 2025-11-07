#!/usr/bin/env python3
"""Seed database with test data"""

import sys
from pathlib import Path
from datetime import datetime
import uuid

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.shared.database.connection import db_manager
from src.shared.models.database import Stock, StockSummary, FactCheckStatus
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def seed():
    """Add test stocks and summaries"""
    test_stocks = [
        {"ticker": "AAPL", "cusip": "037833100", "company_name": "Apple Inc.", "sector": "Technology"},
        {"ticker": "MSFT", "cusip": "594918104", "company_name": "Microsoft Corporation", "sector": "Technology"},
        {"ticker": "GOOGL", "cusip": "02079K305", "company_name": "Alphabet Inc.", "sector": "Technology"},
        {"ticker": "TSLA", "cusip": "88160R101", "company_name": "Tesla Inc.", "sector": "Automotive"},
        {"ticker": "JPM", "cusip": "46625H100", "company_name": "JPMorgan Chase & Co.", "sector": "Financial"},
    ]

    with db_manager.get_session() as session:
        logger.info("Seeding test stocks...")

        for stock_data in test_stocks:
            stock = Stock(**stock_data)
            session.add(stock)

        session.commit()
        logger.info(f"✅ Added {len(test_stocks)} test stocks")

        # Add a test summary for AAPL
        aapl = session.query(Stock).filter_by(ticker="AAPL").first()
        if aapl:
            summary = StockSummary(
                stock_id=aapl.stock_id,
                ticker="AAPL",
                generation_date=datetime.utcnow(),
                hook_text="Apple surges 3% on strong iPhone sales in China",
                hook_word_count=9,
                medium_text="Apple Inc. stock rose 3.2% following reports of stronger-than-expected iPhone 15 sales in China. The company's renewed focus on the Chinese market, combined with aggressive pricing strategies, has resonated with consumers despite economic headwinds. Analysts from Goldman Sachs raised their price target to $195, citing improved supply chain efficiency and sustained demand for premium devices.",
                medium_word_count=85,
                expanded_text="[Placeholder for expanded summary - to be generated in Phase 1]",
                expanded_word_count=500,
                fact_check_status=FactCheckStatus.PASSED,
                retry_count=0,
                source_hash="test_hash_12345"
            )
            session.add(summary)
            session.commit()
            logger.info("✅ Added test summary for AAPL")

if __name__ == "__main__":
    seed()
