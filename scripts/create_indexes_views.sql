-- ================================================================================
-- FA AI System - Database Optimization: Indexes and Views
-- ================================================================================
-- Purpose: Optimize query performance for the EDO load testing database
-- Created: 2025-01-08
-- Tables: financial_advisors, households, accounts, holdings
-- Data Size: 100 FAs, 20K households, 100K accounts, 1.56M holdings
-- ================================================================================

-- ================================================================================
-- SECTION 1: Additional Indexes for Query Optimization
-- ================================================================================

-- Index for filtering households by risk_tolerance
-- Use case: Finding all conservative/aggressive households for targeted communications
CREATE INDEX IF NOT EXISTS idx_households_risk_tolerance
ON households(risk_tolerance);

-- Index for filtering accounts by account_type
-- Use case: Finding all IRA accounts, trust accounts, etc. for compliance or reporting
CREATE INDEX IF NOT EXISTS idx_accounts_account_type
ON accounts(account_type);

-- Composite index for FA region filtering with AUM sorting
-- Use case: Finding top FAs by AUM in a specific region
CREATE INDEX IF NOT EXISTS idx_fa_region_aum
ON financial_advisors(region, total_aum DESC);

-- Index for sorting FAs by client count
-- Use case: Finding FAs with capacity for new clients or top performers
CREATE INDEX IF NOT EXISTS idx_fa_client_count
ON financial_advisors(client_count DESC);

-- Composite index for filtering households by FA and risk tolerance
-- Use case: Finding all aggressive investors for a specific FA
CREATE INDEX IF NOT EXISTS idx_households_fa_risk
ON households(fa_id, risk_tolerance);

-- Composite index for account type filtering with value sorting
-- Use case: Finding highest value IRA accounts across all households
CREATE INDEX IF NOT EXISTS idx_accounts_type_value
ON accounts(account_type, total_value DESC);

-- Index for date-based household filtering
-- Use case: Finding new clients, filtering by onboarding date
CREATE INDEX IF NOT EXISTS idx_households_client_since
ON households(client_since);

-- Composite index for ticker aggregation with value
-- Use case: Summing total exposure to a specific ticker across all holdings
-- Note: idx_ticker_value already exists but this adds account_id for join efficiency
CREATE INDEX IF NOT EXISTS idx_holdings_ticker_account_value
ON holdings(ticker, account_id, current_value);

-- Index for unrealized gain/loss analysis
-- Use case: Finding holdings with large unrealized gains or losses
CREATE INDEX IF NOT EXISTS idx_holdings_gain_loss
ON holdings(unrealized_gain_loss DESC);

-- Composite index for FA-level aggregations via households and accounts
-- Use case: Efficiently joining from FA -> households -> accounts
CREATE INDEX IF NOT EXISTS idx_accounts_household_type
ON accounts(household_id, account_type, total_value DESC);

-- ================================================================================
-- SECTION 2: Materialized Views for Common Aggregations
-- ================================================================================

-- View 1: FA Portfolio Summary
-- Purpose: Quick overview of each FA's book of business
DROP MATERIALIZED VIEW IF EXISTS mv_fa_portfolio_summary CASCADE;
CREATE MATERIALIZED VIEW mv_fa_portfolio_summary AS
SELECT
    fa.fa_id,
    fa.name AS fa_name,
    fa.region,
    fa.specialization,
    fa.total_aum AS fa_total_aum,
    fa.client_count,
    COUNT(DISTINCT h.household_id) AS total_households,
    COUNT(DISTINCT a.account_id) AS total_accounts,
    COUNT(ho.holding_id) AS total_holdings,
    COALESCE(SUM(ho.current_value), 0) AS total_holdings_value,
    COALESCE(SUM(ho.unrealized_gain_loss), 0) AS total_unrealized_gains,
    COALESCE(AVG(h.total_aum), 0) AS avg_household_aum,
    COALESCE(MAX(h.total_aum), 0) AS largest_household_aum,
    COUNT(DISTINCT ho.ticker) AS unique_tickers_held
FROM financial_advisors fa
LEFT JOIN households h ON fa.fa_id = h.fa_id
LEFT JOIN accounts a ON h.household_id = a.household_id
LEFT JOIN holdings ho ON a.account_id = ho.account_id
GROUP BY fa.fa_id, fa.name, fa.region, fa.specialization, fa.total_aum, fa.client_count;

-- Index on materialized view for fast FA lookup
CREATE INDEX idx_mv_fa_portfolio_fa_id ON mv_fa_portfolio_summary(fa_id);
CREATE INDEX idx_mv_fa_portfolio_region ON mv_fa_portfolio_summary(region);
CREATE INDEX idx_mv_fa_portfolio_aum ON mv_fa_portfolio_summary(fa_total_aum DESC);

-- View 2: Stock Exposure Summary
-- Purpose: Aggregate exposure to each stock across entire platform
DROP MATERIALIZED VIEW IF EXISTS mv_stock_exposure CASCADE;
CREATE MATERIALIZED VIEW mv_stock_exposure AS
SELECT
    h.ticker,
    COUNT(DISTINCT h.account_id) AS accounts_holding,
    COUNT(DISTINCT a.household_id) AS households_holding,
    COUNT(DISTINCT hh.fa_id) AS fas_with_exposure,
    SUM(h.shares) AS total_shares,
    SUM(h.current_value) AS total_exposure_value,
    AVG(h.current_value) AS avg_position_size,
    SUM(h.unrealized_gain_loss) AS total_unrealized_gains,
    MAX(h.current_value) AS largest_position_value,
    MIN(h.current_value) AS smallest_position_value,
    SUM(h.current_value) / NULLIF((SELECT SUM(current_value) FROM holdings), 0) * 100 AS pct_of_total_aum
FROM holdings h
JOIN accounts a ON h.account_id = a.account_id
JOIN households hh ON a.household_id = hh.household_id
GROUP BY h.ticker;

-- Index on materialized view for fast ticker lookup and sorting
CREATE INDEX idx_mv_stock_exposure_ticker ON mv_stock_exposure(ticker);
CREATE INDEX idx_mv_stock_exposure_value ON mv_stock_exposure(total_exposure_value DESC);
CREATE INDEX idx_mv_stock_exposure_accounts ON mv_stock_exposure(accounts_holding DESC);

-- View 3: Holdings by Account Type
-- Purpose: Analyze portfolio composition by account type (IRA, taxable, etc.)
DROP MATERIALIZED VIEW IF EXISTS mv_holdings_by_account_type CASCADE;
CREATE MATERIALIZED VIEW mv_holdings_by_account_type AS
SELECT
    a.account_type,
    COUNT(DISTINCT a.account_id) AS total_accounts,
    COUNT(h.holding_id) AS total_holdings,
    COUNT(DISTINCT h.ticker) AS unique_tickers,
    SUM(h.current_value) AS total_value,
    AVG(h.current_value) AS avg_holding_value,
    SUM(h.unrealized_gain_loss) AS total_unrealized_gains,
    AVG(h.unrealized_gain_loss) AS avg_unrealized_gains,
    SUM(a.cash_balance) AS total_cash_balance
FROM accounts a
LEFT JOIN holdings h ON a.account_id = h.account_id
GROUP BY a.account_type;

-- Index on materialized view
CREATE INDEX idx_mv_holdings_account_type ON mv_holdings_by_account_type(account_type);

-- View 4: Household Portfolio Details
-- Purpose: Detailed view of each household's portfolio with aggregated metrics
DROP MATERIALIZED VIEW IF EXISTS mv_household_portfolio CASCADE;
CREATE MATERIALIZED VIEW mv_household_portfolio AS
SELECT
    h.household_id,
    h.household_name,
    h.fa_id,
    fa.name AS fa_name,
    fa.region AS fa_region,
    h.total_aum,
    h.risk_tolerance,
    h.client_since,
    COUNT(DISTINCT a.account_id) AS total_accounts,
    COUNT(ho.holding_id) AS total_holdings,
    COUNT(DISTINCT ho.ticker) AS unique_tickers,
    COALESCE(SUM(ho.current_value), 0) AS total_holdings_value,
    COALESCE(SUM(ho.unrealized_gain_loss), 0) AS total_unrealized_gains,
    COALESCE(SUM(a.cash_balance), 0) AS total_cash_balance,
    COALESCE(AVG(ho.current_value), 0) AS avg_holding_value,
    -- Portfolio concentration (largest holding as % of portfolio)
    CASE
        WHEN SUM(ho.current_value) > 0 THEN
            (MAX(ho.current_value) / SUM(ho.current_value) * 100)
        ELSE 0
    END AS largest_position_pct
FROM households h
JOIN financial_advisors fa ON h.fa_id = fa.fa_id
LEFT JOIN accounts a ON h.household_id = a.household_id
LEFT JOIN holdings ho ON a.account_id = ho.account_id
GROUP BY h.household_id, h.household_name, h.fa_id, fa.name, fa.region,
         h.total_aum, h.risk_tolerance, h.client_since;

-- Indexes on household portfolio view
CREATE INDEX idx_mv_household_fa ON mv_household_portfolio(fa_id);
CREATE INDEX idx_mv_household_risk ON mv_household_portfolio(risk_tolerance);
CREATE INDEX idx_mv_household_aum ON mv_household_portfolio(total_aum DESC);
CREATE INDEX idx_mv_household_region ON mv_household_portfolio(fa_region);

-- View 5: Top Holdings by Ticker
-- Purpose: Identify largest individual positions for risk management
DROP MATERIALIZED VIEW IF EXISTS mv_top_holdings CASCADE;
CREATE MATERIALIZED VIEW mv_top_holdings AS
SELECT
    h.ticker,
    h.account_id,
    a.household_id,
    hh.fa_id,
    fa.name AS fa_name,
    hh.household_name,
    h.shares,
    h.current_value,
    h.unrealized_gain_loss,
    h.pct_of_account,
    a.account_type,
    RANK() OVER (PARTITION BY h.ticker ORDER BY h.current_value DESC) AS ticker_rank,
    RANK() OVER (ORDER BY h.current_value DESC) AS overall_rank
FROM holdings h
JOIN accounts a ON h.account_id = a.account_id
JOIN households hh ON a.household_id = hh.household_id
JOIN financial_advisors fa ON hh.fa_id = fa.fa_id
WHERE h.current_value > 0;

-- Indexes for top holdings view
CREATE INDEX idx_mv_top_holdings_ticker ON mv_top_holdings(ticker);
CREATE INDEX idx_mv_top_holdings_value ON mv_top_holdings(current_value DESC);
CREATE INDEX idx_mv_top_holdings_fa ON mv_top_holdings(fa_id);

-- ================================================================================
-- SECTION 3: Regular Views (Non-Materialized) for Dynamic Queries
-- ================================================================================

-- View 6: FA Regional Summary
-- Purpose: Aggregate metrics by region for management reporting
CREATE OR REPLACE VIEW v_regional_summary AS
SELECT
    fa.region,
    COUNT(DISTINCT fa.fa_id) AS total_fas,
    SUM(fa.total_aum) AS total_regional_aum,
    AVG(fa.total_aum) AS avg_fa_aum,
    SUM(fa.client_count) AS total_clients,
    AVG(fa.client_count) AS avg_clients_per_fa,
    COUNT(DISTINCT h.household_id) AS total_households,
    COUNT(DISTINCT a.account_id) AS total_accounts,
    COUNT(ho.holding_id) AS total_holdings
FROM financial_advisors fa
LEFT JOIN households h ON fa.fa_id = h.fa_id
LEFT JOIN accounts a ON h.household_id = a.household_id
LEFT JOIN holdings ho ON a.account_id = ho.account_id
GROUP BY fa.region;

-- View 7: Risk Tolerance Distribution
-- Purpose: Analyze distribution of risk profiles for marketing/product development
CREATE OR REPLACE VIEW v_risk_tolerance_summary AS
SELECT
    h.risk_tolerance,
    COUNT(h.household_id) AS household_count,
    SUM(h.total_aum) AS total_aum,
    AVG(h.total_aum) AS avg_aum,
    COUNT(DISTINCT a.account_id) AS total_accounts,
    COUNT(ho.holding_id) AS total_holdings,
    AVG(ho.current_value) AS avg_holding_value
FROM households h
LEFT JOIN accounts a ON h.household_id = a.household_id
LEFT JOIN holdings ho ON a.account_id = ho.account_id
GROUP BY h.risk_tolerance;

-- View 8: Account Type Distribution
-- Purpose: Understand account mix for tax planning and product recommendations
CREATE OR REPLACE VIEW v_account_type_summary AS
SELECT
    a.account_type,
    COUNT(a.account_id) AS account_count,
    SUM(a.total_value) AS total_value,
    AVG(a.total_value) AS avg_account_value,
    SUM(a.cash_balance) AS total_cash,
    COUNT(DISTINCT a.household_id) AS households_with_type,
    COUNT(h.holding_id) AS total_holdings,
    COUNT(DISTINCT h.ticker) AS unique_tickers
FROM accounts a
LEFT JOIN holdings h ON a.account_id = h.account_id
GROUP BY a.account_type;

-- View 9: FA Stock Exposure (for specific FA queries)
-- Purpose: Show what stocks a specific FA's clients are exposed to
CREATE OR REPLACE VIEW v_fa_stock_exposure AS
SELECT
    fa.fa_id,
    fa.name AS fa_name,
    h.ticker,
    COUNT(DISTINCT hh.household_id) AS households_with_exposure,
    COUNT(DISTINCT a.account_id) AS accounts_with_exposure,
    SUM(h.shares) AS total_shares,
    SUM(h.current_value) AS total_exposure,
    AVG(h.current_value) AS avg_position_size,
    SUM(h.unrealized_gain_loss) AS total_unrealized_gains
FROM financial_advisors fa
JOIN households hh ON fa.fa_id = hh.fa_id
JOIN accounts a ON hh.household_id = a.household_id
JOIN holdings h ON a.account_id = h.account_id
GROUP BY fa.fa_id, fa.name, h.ticker;

-- View 10: Concentrated Positions (Risk Management)
-- Purpose: Identify positions that represent >10% of a household's portfolio
CREATE OR REPLACE VIEW v_concentrated_positions AS
SELECT
    hh.household_id,
    hh.household_name,
    hh.fa_id,
    fa.name AS fa_name,
    a.account_id,
    a.account_type,
    h.ticker,
    h.current_value,
    hh.total_aum AS household_aum,
    (h.current_value / NULLIF(hh.total_aum, 0) * 100) AS pct_of_household_aum,
    h.pct_of_account,
    h.unrealized_gain_loss
FROM holdings h
JOIN accounts a ON h.account_id = a.account_id
JOIN households hh ON a.household_id = hh.household_id
JOIN financial_advisors fa ON hh.fa_id = fa.fa_id
WHERE (h.current_value / NULLIF(hh.total_aum, 0) * 100) > 10;

-- ================================================================================
-- SECTION 4: Utility Functions
-- ================================================================================

-- Function to refresh all materialized views
CREATE OR REPLACE FUNCTION refresh_all_materialized_views()
RETURNS void AS $$
BEGIN
    REFRESH MATERIALIZED VIEW mv_fa_portfolio_summary;
    REFRESH MATERIALIZED VIEW mv_stock_exposure;
    REFRESH MATERIALIZED VIEW mv_holdings_by_account_type;
    REFRESH MATERIALIZED VIEW mv_household_portfolio;
    REFRESH MATERIALIZED VIEW mv_top_holdings;
END;
$$ LANGUAGE plpgsql;

-- ================================================================================
-- SECTION 5: Comments and Documentation
-- ================================================================================

COMMENT ON MATERIALIZED VIEW mv_fa_portfolio_summary IS
'Pre-aggregated summary of each FA''s book of business including total households, accounts, holdings, and AUM metrics';

COMMENT ON MATERIALIZED VIEW mv_stock_exposure IS
'Platform-wide exposure to each stock ticker with total value, number of accounts, and unrealized gains';

COMMENT ON MATERIALIZED VIEW mv_holdings_by_account_type IS
'Aggregated metrics for each account type showing total holdings, value, and unrealized gains';

COMMENT ON MATERIALIZED VIEW mv_household_portfolio IS
'Detailed portfolio view for each household including concentration metrics and aggregated holdings data';

COMMENT ON MATERIALIZED VIEW mv_top_holdings IS
'Individual holdings ranked by size with ticker-specific and overall rankings for risk analysis';

COMMENT ON VIEW v_regional_summary IS
'Dynamic aggregation of FA and portfolio metrics by region';

COMMENT ON VIEW v_risk_tolerance_summary IS
'Distribution of households and AUM by risk tolerance profile';

COMMENT ON VIEW v_account_type_summary IS
'Account type distribution with value and holdings metrics';

COMMENT ON VIEW v_fa_stock_exposure IS
'Per-FA stock exposure showing what tickers each FA''s clients hold';

COMMENT ON VIEW v_concentrated_positions IS
'Positions representing >10% of household AUM for risk management monitoring';

COMMENT ON FUNCTION refresh_all_materialized_views() IS
'Convenience function to refresh all materialized views in correct order';

-- ================================================================================
-- SECTION 6: Initial Materialized View Refresh
-- ================================================================================

-- Refresh all materialized views to populate them with data
SELECT refresh_all_materialized_views();

-- ================================================================================
-- SECTION 7: Index and View Statistics
-- ================================================================================

-- Print summary of indexes created
DO $$
DECLARE
    index_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO index_count
    FROM pg_indexes
    WHERE schemaname = 'public'
    AND indexname LIKE 'idx_%';

    RAISE NOTICE '===============================================';
    RAISE NOTICE 'Database Optimization Complete!';
    RAISE NOTICE '===============================================';
    RAISE NOTICE 'Total indexes created: %', index_count;
    RAISE NOTICE 'Materialized views: 5';
    RAISE NOTICE 'Regular views: 5';
    RAISE NOTICE 'Utility functions: 1';
    RAISE NOTICE '===============================================';
END $$;
