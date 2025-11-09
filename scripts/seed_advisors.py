#!/usr/bin/env python3
"""Seed database with test advisor and client data"""

import sys
from pathlib import Path
from datetime import datetime, timedelta

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.shared.database.connection import db_manager
from src.shared.models.database import Advisor, Client, ClientHolding, Stock
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def seed():
    """Add test advisors, clients, and holdings"""

    with db_manager.get_session() as session:
        logger.info("Seeding test advisors and clients...")

        # Create test advisor
        advisor = Advisor(
            fa_id="FA-001",
            name="John Smith",
            email="john.smith@example.com",
            firm_name="Smith Wealth Management",
            preferences={
                "watchlist": ["AAPL", "MSFT", "GOOGL"],
                "notification_settings": {
                    "email_alerts": True,
                    "price_change_threshold": 5.0
                }
            }
        )
        session.add(advisor)
        session.commit()
        session.refresh(advisor)
        logger.info(f"✅ Added advisor: {advisor.name} (FA-001)")

        # Create test clients
        client1 = Client(
            advisor_id=advisor.advisor_id,
            account_id="ACC-001",
            name="Robert Johnson",
            email="robert.johnson@example.com",
            phone="555-0101",
            last_meeting_date=datetime.utcnow() - timedelta(days=30),
            next_meeting_date=datetime.utcnow() + timedelta(days=7),
            notes="Conservative investor, retirement focused",
            client_metadata={
                "risk_tolerance": "conservative",
                "investment_goal": "retirement",
                "age": 58
            }
        )

        client2 = Client(
            advisor_id=advisor.advisor_id,
            account_id="ACC-002",
            name="Emily Davis",
            email="emily.davis@example.com",
            phone="555-0102",
            last_meeting_date=datetime.utcnow() - timedelta(days=14),
            next_meeting_date=datetime.utcnow() + timedelta(days=14),
            notes="Growth investor, tech sector focus",
            client_metadata={
                "risk_tolerance": "aggressive",
                "investment_goal": "growth",
                "age": 35
            }
        )

        client3 = Client(
            advisor_id=advisor.advisor_id,
            account_id="ACC-003",
            name="Michael Chen",
            email="michael.chen@example.com",
            phone="555-0103",
            last_meeting_date=datetime.utcnow() - timedelta(days=45),
            next_meeting_date=datetime.utcnow() + timedelta(days=2),
            notes="Balanced portfolio, dividend income strategy",
            client_metadata={
                "risk_tolerance": "moderate",
                "investment_goal": "income",
                "age": 52
            }
        )

        session.add_all([client1, client2, client3])
        session.commit()
        session.refresh(client1)
        session.refresh(client2)
        session.refresh(client3)
        logger.info(f"✅ Added 3 clients for advisor FA-001")

        # Get stock references for holdings
        aapl = session.query(Stock).filter_by(ticker="AAPL").first()
        msft = session.query(Stock).filter_by(ticker="MSFT").first()
        googl = session.query(Stock).filter_by(ticker="GOOGL").first()
        tsla = session.query(Stock).filter_by(ticker="TSLA").first()
        jpm = session.query(Stock).filter_by(ticker="JPM").first()

        if not all([aapl, msft, googl, tsla, jpm]):
            logger.warning("⚠️ Some stocks not found. Run seed_test_data.py first to create stock data.")
            return

        # Add holdings for client1 (Conservative - diversified)
        holdings_client1 = [
            ClientHolding(
                client_id=client1.client_id,
                stock_id=aapl.stock_id,
                ticker="AAPL",
                shares=150.0,
                cost_basis=145.50,
                purchase_date=datetime.utcnow() - timedelta(days=365),
                notes="Core holding"
            ),
            ClientHolding(
                client_id=client1.client_id,
                stock_id=jpm.stock_id,
                ticker="JPM",
                shares=200.0,
                cost_basis=135.25,
                purchase_date=datetime.utcnow() - timedelta(days=180),
                notes="Financial sector exposure"
            )
        ]

        # Add holdings for client2 (Aggressive - tech focused)
        holdings_client2 = [
            ClientHolding(
                client_id=client2.client_id,
                stock_id=aapl.stock_id,
                ticker="AAPL",
                shares=100.0,
                cost_basis=155.00,
                purchase_date=datetime.utcnow() - timedelta(days=90),
                notes="Tech portfolio core"
            ),
            ClientHolding(
                client_id=client2.client_id,
                stock_id=msft.stock_id,
                ticker="MSFT",
                shares=75.0,
                cost_basis=320.00,
                purchase_date=datetime.utcnow() - timedelta(days=120),
                notes="Cloud computing exposure"
            ),
            ClientHolding(
                client_id=client2.client_id,
                stock_id=googl.stock_id,
                ticker="GOOGL",
                shares=50.0,
                cost_basis=125.00,
                purchase_date=datetime.utcnow() - timedelta(days=60),
                notes="AI and search leader"
            ),
            ClientHolding(
                client_id=client2.client_id,
                stock_id=tsla.stock_id,
                ticker="TSLA",
                shares=80.0,
                cost_basis=210.00,
                purchase_date=datetime.utcnow() - timedelta(days=30),
                notes="EV sector bet"
            )
        ]

        # Add holdings for client3 (Moderate - balanced)
        holdings_client3 = [
            ClientHolding(
                client_id=client3.client_id,
                stock_id=aapl.stock_id,
                ticker="AAPL",
                shares=120.0,
                cost_basis=140.00,
                purchase_date=datetime.utcnow() - timedelta(days=200),
                notes="Dividend growth"
            ),
            ClientHolding(
                client_id=client3.client_id,
                stock_id=msft.stock_id,
                ticker="MSFT",
                shares=100.0,
                cost_basis=310.00,
                purchase_date=datetime.utcnow() - timedelta(days=150),
                notes="Stable dividend payer"
            ),
            ClientHolding(
                client_id=client3.client_id,
                stock_id=jpm.stock_id,
                ticker="JPM",
                shares=150.0,
                cost_basis=140.00,
                purchase_date=datetime.utcnow() - timedelta(days=100),
                notes="Financial dividend income"
            )
        ]

        all_holdings = holdings_client1 + holdings_client2 + holdings_client3
        session.add_all(all_holdings)
        session.commit()
        logger.info(f"✅ Added {len(all_holdings)} client holdings")

        logger.info("\n📊 Summary:")
        logger.info(f"   - 1 advisor created (FA-001)")
        logger.info(f"   - 3 clients created")
        logger.info(f"   - {len(all_holdings)} holdings created")
        logger.info(f"\n💡 Test with: curl http://localhost:8000/api/advisors/FA-001")

if __name__ == "__main__":
    seed()
