#!/usr/bin/env python3
"""
Simple Test for Database Indexes and Views

Runs basic queries to verify indexes and views are working.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine, text
from src.config.settings import settings

def test_query(conn, name, sql):
    """Run a test query and print results"""
    print(f"\n{'='*80}")
    print(f"Test: {name}")
    print(f"{'='*80}")
    try:
        result = conn.execute(text(sql))
        rows = result.fetchall()
        print(f"✓ Success: {len(rows)} rows returned")

        # Show first few results
        for i, row in enumerate(rows[:5], 1):
            print(f"  {i}. {dict(row._mapping)}")

        return True
    except Exception as e:
        print(f"✗ Error: {e}")
        return False

def main():
    print("="*80)
    print("FA AI System - Database Indexes and Views Testing")
    print("="*80)

    engine = create_engine(settings.database_url)

    tests_passed = 0
    tests_failed = 0

    with engine.connect() as conn:
        # Test 1: FA Portfolio Summary
        if test_query(conn, "FA Portfolio Summary (Materialized View)",
            """SELECT fa_id, fa_name, region, total_households, total_accounts,
                      total_holdings_value, unique_tickers_held
               FROM mv_fa_portfolio_summary
               ORDER BY total_holdings_value DESC LIMIT 5;"""):
            tests_passed += 1
        else:
            tests_failed += 1

        # Test 2: Stock Exposure
        conn.rollback()  # Reset any failed transaction
        if test_query(conn, "Stock Exposure Summary (Materialized View)",
            """SELECT ticker, accounts_holding, total_exposure_value,
                      total_unrealized_gains
               FROM mv_stock_exposure
               ORDER BY total_exposure_value DESC LIMIT 5;"""):
            tests_passed += 1
        else:
            tests_failed += 1

        # Test 3: Using Composite Index
        conn.rollback()
        if test_query(conn, "Aggressive Households for FA-00001 (Using Index)",
            """SELECT household_id, household_name, total_aum, risk_tolerance
               FROM households
               WHERE fa_id = 'FA-00001' AND risk_tolerance = 'AGGRESSIVE'
               ORDER BY total_aum DESC LIMIT 5;"""):
            tests_passed += 1
        else:
            tests_failed += 1

        # Test 4: Regional Summary
        conn.rollback()
        if test_query(conn, "Regional Summary (View)",
            """SELECT region, total_fas, total_regional_aum, total_households
               FROM v_regional_summary
               ORDER BY total_regional_aum DESC;"""):
            tests_passed += 1
        else:
            tests_failed += 1

        # Test 5: Holdings by Account Type
        conn.rollback()
        if test_query(conn, "Holdings by Account Type (Materialized View)",
            """SELECT account_type, total_accounts, total_holdings,
                      total_value, unique_tickers
               FROM mv_holdings_by_account_type
               ORDER BY total_value DESC;"""):
            tests_passed += 1
        else:
            tests_failed += 1

        # Test 6: Top IRA Accounts
        conn.rollback()
        if test_query(conn, "Top IRA Accounts (Using Index)",
            """SELECT account_id, household_id, account_type, total_value
               FROM accounts
               WHERE account_type = 'IRA'
               ORDER BY total_value DESC LIMIT 5;"""):
            tests_passed += 1
        else:
            tests_failed += 1

        # Test 7: FA Stock Exposure
        conn.rollback()
        if test_query(conn, "Stock Exposure for FA-00001 (View)",
            """SELECT ticker, households_with_exposure, total_exposure,
                      total_unrealized_gains
               FROM v_fa_stock_exposure
               WHERE fa_id = 'FA-00001'
               ORDER BY total_exposure DESC LIMIT 5;"""):
            tests_passed += 1
        else:
            tests_failed += 1

        # Test 8: Concentrated Positions
        conn.rollback()
        if test_query(conn, "Concentrated Positions >10% (View)",
            """SELECT household_name, fa_name, ticker, current_value,
                      pct_of_household_aum
               FROM v_concentrated_positions
               ORDER BY pct_of_household_aum DESC LIMIT 5;"""):
            tests_passed += 1
        else:
            tests_failed += 1

        # Test 9: Household Portfolio
        conn.rollback()
        if test_query(conn, "Top Households by AUM (Materialized View)",
            """SELECT household_id, household_name, fa_name, total_aum,
                      total_accounts, unique_tickers, largest_position_pct
               FROM mv_household_portfolio
               ORDER BY total_aum DESC LIMIT 5;"""):
            tests_passed += 1
        else:
            tests_failed += 1

        # Test 10: Aggregating by Ticker
        conn.rollback()
        if test_query(conn, "Total AAPL Holdings (Using Index)",
            """SELECT COUNT(DISTINCT account_id) as accounts,
                      SUM(shares) as total_shares,
                      SUM(current_value) as total_value
               FROM holdings WHERE ticker = 'AAPL';"""):
            tests_passed += 1
        else:
            tests_failed += 1

        # Test 11: Top Holdings
        conn.rollback()
        if test_query(conn, "Top Individual Holdings (Materialized View)",
            """SELECT ticker, fa_name, household_name, current_value,
                      unrealized_gain_loss, overall_rank
               FROM mv_top_holdings
               WHERE overall_rank <= 5 ORDER BY overall_rank;"""):
            tests_passed += 1
        else:
            tests_failed += 1

        # Test 12: Risk Tolerance Distribution
        conn.rollback()
        if test_query(conn, "Risk Tolerance Distribution (View)",
            """SELECT risk_tolerance, household_count, total_aum,
                      total_accounts
               FROM v_risk_tolerance_summary
               ORDER BY total_aum DESC;"""):
            tests_passed += 1
        else:
            tests_failed += 1

        # Test 13: Refresh Materialized Views
        conn.rollback()
        print(f"\n{'='*80}")
        print("Test: Refresh All Materialized Views")
        print(f"{'='*80}")
        try:
            conn.execute(text("SELECT refresh_all_materialized_views();"))
            conn.commit()
            print("✓ All materialized views refreshed successfully")
            tests_passed += 1
        except Exception as e:
            print(f"✗ Error: {e}")
            tests_failed += 1

    # Final Summary
    print(f"\n{'='*80}")
    print("TESTING SUMMARY")
    print(f"{'='*80}")
    print(f"Tests Passed: {tests_passed}")
    print(f"Tests Failed: {tests_failed}")
    print(f"Total Tests: {tests_passed + tests_failed}")
    print(f"{'='*80}")

    if tests_failed == 0:
        print("\n✓ All tests passed! Indexes and views are working correctly.")
    else:
        print(f"\n✗ {tests_failed} test(s) failed. See errors above.")

if __name__ == "__main__":
    main()
