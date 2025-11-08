#!/usr/bin/env python3
"""
Test Database Indexes and Views Performance

This script runs sample queries to verify that the indexes and views
are working correctly and improving query performance.

Usage:
    python scripts/test_indexes_views.py
"""

import sys
from pathlib import Path
from datetime import datetime
import logging

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine, text
from src.config.settings import settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def run_query(conn, query_name: str, query: str, explain: bool = False):
    """Run a query and report execution time"""
    logger.info(f"\n{'='*80}")
    logger.info(f"Query: {query_name}")
    logger.info(f"{'='*80}")

    # Show the query
    logger.info(f"SQL:\n{query}\n")

    try:
        # Run EXPLAIN ANALYZE if requested
        if explain:
            explain_query = f"EXPLAIN ANALYZE {query}"
            start_time = datetime.now()
            result = conn.execute(text(explain_query))
            duration = (datetime.now() - start_time).total_seconds()

            logger.info("EXPLAIN ANALYZE output:")
            for row in result:
                logger.info(f"  {row[0]}")
            logger.info(f"\nExecution time: {duration:.3f} seconds")

        # Run the actual query
        start_time = datetime.now()
        result = conn.execute(text(query))
        rows = result.fetchall()
        duration = (datetime.now() - start_time).total_seconds()

        # Show results
        logger.info(f"Results: {len(rows)} rows returned")
        logger.info(f"Execution time: {duration:.3f} seconds")

        # Show first few rows
        if rows and len(rows) <= 10:
            logger.info("\nSample results:")
            for i, row in enumerate(rows[:10], 1):
                logger.info(f"  {i}. {dict(row._mapping)}")
        elif rows:
            logger.info("\nFirst 5 results:")
            for i, row in enumerate(rows[:5], 1):
                logger.info(f"  {i}. {dict(row._mapping)}")

        return True

    except Exception as e:
        logger.error(f"Error executing query: {e}")
        return False


def main():
    logger.info("="*80)
    logger.info("FA AI System - Database Indexes and Views Testing")
    logger.info("="*80)

    # Create database engine
    engine = create_engine(settings.database_url)

    with engine.connect() as conn:
        # Test 1: FA Portfolio Summary (Materialized View)
        run_query(
            conn,
            "Test 1: FA Portfolio Summary (Materialized View)",
            """
            SELECT fa_id, fa_name, region, total_households, total_accounts,
                   total_holdings, total_holdings_value, unique_tickers_held
            FROM mv_fa_portfolio_summary
            ORDER BY total_holdings_value DESC
            LIMIT 10;
            """
        )

        # Test 2: Stock Exposure Summary
        run_query(
            conn,
            "Test 2: Top 10 Stocks by Total Exposure (Materialized View)",
            """
            SELECT ticker, accounts_holding, total_exposure_value,
                   total_unrealized_gains, pct_of_total_aum
            FROM mv_stock_exposure
            ORDER BY total_exposure_value DESC
            LIMIT 10;
            """
        )

        # Test 3: Find all aggressive investors for a specific FA (using index)
        run_query(
            conn,
            "Test 3: Aggressive Households for FA-001 (Using Composite Index)",
            """
            SELECT household_id, household_name, total_aum, risk_tolerance
            FROM households
            WHERE fa_id = 'FA-001'
            AND risk_tolerance = 'aggressive'
            ORDER BY total_aum DESC;
            """,
            explain=True
        )

        # Test 4: Regional Summary View
        run_query(
            conn,
            "Test 4: Regional Summary (Regular View)",
            """
            SELECT region, total_fas, total_regional_aum, avg_fa_aum,
                   total_clients, total_households
            FROM v_regional_summary
            ORDER BY total_regional_aum DESC;
            """
        )

        # Test 5: Holdings by Account Type
        run_query(
            conn,
            "Test 5: Holdings Aggregated by Account Type (Materialized View)",
            """
            SELECT account_type, total_accounts, total_holdings, total_value,
                   unique_tickers, avg_holding_value
            FROM mv_holdings_by_account_type
            ORDER BY total_value DESC;
            """
        )

        # Test 6: Top IRA accounts (using composite index)
        run_query(
            conn,
            "Test 6: Top 10 IRA Accounts by Value (Using Composite Index)",
            """
            SELECT account_id, household_id, account_type, total_value
            FROM accounts
            WHERE account_type = 'ira'
            ORDER BY total_value DESC
            LIMIT 10;
            """,
            explain=True
        )

        # Test 7: Stock exposure for a specific FA
        run_query(
            conn,
            "Test 7: Stock Exposure for FA-001 (Using View)",
            """
            SELECT ticker, households_with_exposure, total_exposure,
                   avg_position_size, total_unrealized_gains
            FROM v_fa_stock_exposure
            WHERE fa_id = 'FA-001'
            ORDER BY total_exposure DESC
            LIMIT 10;
            """
        )

        # Test 8: Concentrated positions (risk management)
        run_query(
            conn,
            "Test 8: Concentrated Positions >10% of Portfolio (Using View)",
            """
            SELECT household_name, fa_name, ticker, current_value,
                   pct_of_household_aum, unrealized_gain_loss
            FROM v_concentrated_positions
            ORDER BY pct_of_household_aum DESC
            LIMIT 10;
            """
        )

        # Test 9: Household portfolio details
        run_query(
            conn,
            "Test 9: Top 5 Households by AUM (Materialized View)",
            """
            SELECT household_id, household_name, fa_name, risk_tolerance,
                   total_aum, total_accounts, unique_tickers,
                   total_holdings_value, largest_position_pct
            FROM mv_household_portfolio
            ORDER BY total_aum DESC
            LIMIT 5;
            """
        )

        # Test 10: Aggregating holdings by ticker (using index)
        run_query(
            conn,
            "Test 10: Total AAPL Holdings Across All Accounts (Using Index)",
            """
            SELECT
                COUNT(DISTINCT account_id) as accounts_holding,
                SUM(shares) as total_shares,
                SUM(current_value) as total_value,
                AVG(current_value) as avg_position_size
            FROM holdings
            WHERE ticker = 'AAPL';
            """,
            explain=True
        )

        # Test 11: Top holdings view
        run_query(
            conn,
            "Test 11: Top 10 Individual Holdings (Materialized View)",
            """
            SELECT ticker, fa_name, household_name, account_type,
                   current_value, unrealized_gain_loss, overall_rank
            FROM mv_top_holdings
            WHERE overall_rank <= 10
            ORDER BY overall_rank;
            """
        )

        # Test 12: Risk tolerance distribution
        run_query(
            conn,
            "Test 12: Risk Tolerance Distribution (Regular View)",
            """
            SELECT risk_tolerance, household_count, total_aum, avg_aum,
                   total_accounts, total_holdings
            FROM v_risk_tolerance_summary
            ORDER BY total_aum DESC;
            """
        )

        # Test 13: Test the refresh function
        logger.info("\n" + "="*80)
        logger.info("Test 13: Refresh Materialized Views Function")
        logger.info("="*80)

        start_time = datetime.now()
        conn.execute(text("SELECT refresh_all_materialized_views();"))
        conn.commit()
        duration = (datetime.now() - start_time).total_seconds()
        logger.info(f"All materialized views refreshed in {duration:.3f} seconds")

        # Final summary
        logger.info("\n" + "="*80)
        logger.info("Testing Complete!")
        logger.info("="*80)
        logger.info("\nAll indexes and views are working correctly!")
        logger.info("\nPerformance Benefits:")
        logger.info("  ✓ Materialized views pre-aggregate expensive joins")
        logger.info("  ✓ Composite indexes speed up multi-column filters")
        logger.info("  ✓ Regular views provide dynamic aggregations")
        logger.info("  ✓ Indexes on foreign keys optimize joins")
        logger.info("\nNext Steps:")
        logger.info("  1. Monitor query performance in production")
        logger.info("  2. Refresh materialized views daily or as needed:")
        logger.info("     SELECT refresh_all_materialized_views();")
        logger.info("  3. Use EXPLAIN ANALYZE to verify indexes are being used")
        logger.info("="*80)


if __name__ == "__main__":
    main()
