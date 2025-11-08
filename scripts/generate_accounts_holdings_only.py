#!/usr/bin/env python3
"""
Generate Only Accounts and Holdings for Existing Households

This script loads existing households and generates:
- 5 Accounts per existing Household
- Holdings for each account
"""

import sys
import random
from pathlib import Path
from datetime import datetime, timedelta
import logging

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.shared.models.edo_database import (
    Base, Household, Account, Holding, AccountType
)
from src.config.settings import settings

# Import from main script
sys.path.insert(0, str(Path(__file__).parent))
from generate_load_test_data import generate_accounts, generate_holdings, TOP_500_STOCKS

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main():
    """Generate accounts and holdings for existing households"""
    logger.info("=" * 80)
    logger.info("Generating Accounts and Holdings for Existing Households")
    logger.info("=" * 80)

    # Create database engine
    engine = create_engine(settings.database_url)
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        from sqlalchemy import func

        # Load households that don't have accounts yet (resume capability)
        logger.info("\n1. Loading households that need accounts...")

        # Find households that don't have accounts yet
        households_with_accounts = session.query(Household.household_id).join(Account).distinct()

        households = session.query(Household).filter(
            ~Household.household_id.in_(households_with_accounts)
        ).all()

        total_households = session.query(Household).count()
        existing_account_count = session.query(Account).count()

        logger.info(f"   Total households: {total_households:,}")
        logger.info(f"   Existing accounts: {existing_account_count:,}")
        logger.info(f"   Households needing accounts: {len(households):,}")

        if not households:
            logger.info("   ✅ All households already have accounts!")
            if existing_account_count == 0:
                logger.error("No households found! Run generate_load_test_data.py first.")
            return

        # Generate Accounts
        logger.info(f"\n2. Generating 5 Accounts per Household...")
        all_accounts = []
        for idx, hh in enumerate(households):
            if idx % 1000 == 0 and idx > 0:
                logger.info(f"   Progress: {idx}/{len(households)} households")

            accounts = generate_accounts(hh, 5)
            all_accounts.extend(accounts)

            # Batch insert for performance
            if len(all_accounts) >= 5000:
                session.add_all(all_accounts)
                session.commit()
                all_accounts = []

        # Insert remaining
        if all_accounts:
            session.add_all(all_accounts)
            session.commit()

        logger.info(f"   ✅ Created {len(households) * 5:,} accounts")

        # Re-query accounts to get IDs
        all_accounts = session.query(Account).all()

        # Generate Holdings
        logger.info(f"\n3. Generating Holdings for all Accounts...")
        logger.info(f"   Using {len(TOP_500_STOCKS)} stocks from top NYSE list")

        all_holdings = []
        for idx, account in enumerate(all_accounts):
            if idx % 1000 == 0:
                logger.info(f"   Progress: {idx}/{len(all_accounts)} accounts")

            holdings = generate_holdings(account, TOP_500_STOCKS)
            all_holdings.extend(holdings)

            # Batch insert for performance
            if len(all_holdings) >= 10000:
                session.add_all(all_holdings)
                session.commit()
                all_holdings = []

        # Insert remaining
        if all_holdings:
            session.add_all(all_holdings)
            session.commit()

        total_holdings = session.query(Holding).count()
        logger.info(f"   ✅ Created {total_holdings:,} holdings")

        # Summary
        logger.info("\n" + "=" * 80)
        logger.info("GENERATION COMPLETE")
        logger.info("=" * 80)
        logger.info(f"Households: {len(households):,}")
        logger.info(f"Accounts: {len(all_accounts):,}")
        logger.info(f"Holdings: {total_holdings:,}")
        logger.info("=" * 80)

    except Exception as e:
        logger.error(f"Error during generation: {str(e)}")
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
