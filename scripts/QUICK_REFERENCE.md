# Database Optimization - Quick Reference Guide

## Quick Start

### Apply Migration
```bash
cd /Users/markkenyon/fa-ai-system
python3 scripts/apply_indexes_views.py
```

### Test Indexes and Views
```bash
python3 scripts/test_indexes_views_simple.py
```

### Refresh Materialized Views
```sql
SELECT refresh_all_materialized_views();
```

---

## Most Useful Queries

### 1. Top FAs by Portfolio Value
```sql
SELECT fa_id, fa_name, region, total_holdings_value, total_households
FROM mv_fa_portfolio_summary
ORDER BY total_holdings_value DESC
LIMIT 10;
```

### 2. Top Stock Exposures Platform-Wide
```sql
SELECT ticker, accounts_holding, total_exposure_value, pct_of_total_aum
FROM mv_stock_exposure
ORDER BY total_exposure_value DESC
LIMIT 20;
```

### 3. Get FA's Top Stock Exposures
```sql
SELECT ticker, households_with_exposure, total_exposure, total_unrealized_gains
FROM v_fa_stock_exposure
WHERE fa_id = 'FA-00001'
ORDER BY total_exposure DESC
LIMIT 10;
```

### 4. Find Concentrated Positions (Risk Alert)
```sql
SELECT household_name, fa_name, ticker, current_value, pct_of_household_aum
FROM v_concentrated_positions
WHERE pct_of_household_aum > 15
ORDER BY pct_of_household_aum DESC;
```

### 5. Top Households by AUM
```sql
SELECT household_name, fa_name, total_aum, unique_tickers, largest_position_pct
FROM mv_household_portfolio
ORDER BY total_aum DESC
LIMIT 10;
```

### 6. Regional Performance Summary
```sql
SELECT region, total_fas, total_regional_aum, total_households
FROM v_regional_summary
ORDER BY total_regional_aum DESC;
```

### 7. Find Aggressive Investors for an FA
```sql
SELECT household_id, household_name, total_aum
FROM households
WHERE fa_id = 'FA-00001' AND risk_tolerance = 'AGGRESSIVE'
ORDER BY total_aum DESC;
```

### 8. Top IRA Accounts
```sql
SELECT account_id, household_id, total_value
FROM accounts
WHERE account_type = 'IRA'
ORDER BY total_value DESC
LIMIT 10;
```

### 9. Holdings by Account Type
```sql
SELECT account_type, total_accounts, total_value, unique_tickers
FROM mv_holdings_by_account_type
ORDER BY total_value DESC;
```

### 10. Total Exposure to a Specific Stock
```sql
-- Platform-wide
SELECT * FROM mv_stock_exposure WHERE ticker = 'AAPL';

-- Per FA
SELECT fa_name, total_exposure
FROM v_fa_stock_exposure
WHERE ticker = 'AAPL'
ORDER BY total_exposure DESC;
```

---

## Materialized Views Quick Reference

| View Name | Purpose | Refresh Time | Typical Query Time |
|-----------|---------|--------------|-------------------|
| mv_fa_portfolio_summary | FA metrics and totals | ~500ms | ~2ms |
| mv_stock_exposure | Platform-wide stock exposure | ~800ms | ~1ms |
| mv_holdings_by_account_type | Account type aggregations | ~300ms | ~1ms |
| mv_household_portfolio | Household details with metrics | ~600ms | ~5ms |
| mv_top_holdings | Ranked individual positions | ~900ms | ~5ms |

**Total refresh time for all views:** ~2 seconds

---

## Indexes Quick Reference

| Index Name | Table | Columns | Use Case |
|------------|-------|---------|----------|
| idx_fa_region_aum | financial_advisors | region, total_aum | Top FAs by region |
| idx_fa_client_count | financial_advisors | client_count | FA capacity analysis |
| idx_households_risk_tolerance | households | risk_tolerance | Risk profile filtering |
| idx_households_fa_risk | households | fa_id, risk_tolerance | FA-specific risk filtering |
| idx_households_client_since | households | client_since | New client queries |
| idx_accounts_account_type | accounts | account_type | Account type filtering |
| idx_accounts_type_value | accounts | account_type, total_value | Top accounts by type |
| idx_accounts_household_type | accounts | household_id, account_type, total_value | Complex joins |
| idx_holdings_ticker_account_value | holdings | ticker, account_id, current_value | Ticker aggregations |
| idx_holdings_gain_loss | holdings | unrealized_gain_loss | Gain/loss analysis |

---

## Maintenance Commands

### Refresh All Materialized Views
```sql
SELECT refresh_all_materialized_views();
```

### Refresh Individual View
```sql
REFRESH MATERIALIZED VIEW mv_stock_exposure;
```

### Check Index Usage
```sql
SELECT tablename, indexname, idx_scan, idx_tup_read
FROM pg_stat_user_indexes
WHERE schemaname = 'public' AND indexname LIKE 'idx_%'
ORDER BY idx_scan DESC;
```

### Check View Sizes
```sql
SELECT matviewname,
       pg_size_pretty(pg_total_relation_size('public.'||matviewname)) AS size
FROM pg_matviews
WHERE schemaname = 'public';
```

### Update Statistics
```sql
ANALYZE;
```

### Verify Query Plan
```sql
EXPLAIN ANALYZE
SELECT * FROM households WHERE fa_id = 'FA-00001' AND risk_tolerance = 'AGGRESSIVE';
```

---

## Files Location

| File | Path | Purpose |
|------|------|---------|
| SQL Migration | scripts/create_indexes_views.sql | DDL for all indexes and views |
| Apply Script | scripts/apply_indexes_views.py | Python script to apply migration |
| Test Script | scripts/test_indexes_views_simple.py | Test suite for validation |
| Full Summary | scripts/INDEXES_VIEWS_SUMMARY.md | Complete documentation |
| Quick Reference | scripts/QUICK_REFERENCE.md | This file |

---

## Common Patterns

### Pattern 1: FA Dashboard Query
```sql
-- Get FA overview with top holdings
SELECT fa_id, fa_name, total_households, total_holdings_value
FROM mv_fa_portfolio_summary
WHERE fa_id = 'FA-00001';

-- Get FA's top stock exposures
SELECT ticker, total_exposure, households_with_exposure
FROM v_fa_stock_exposure
WHERE fa_id = 'FA-00001'
ORDER BY total_exposure DESC
LIMIT 10;
```

### Pattern 2: Risk Analysis
```sql
-- Find concentrated positions
SELECT * FROM v_concentrated_positions
WHERE fa_id = 'FA-00001'
ORDER BY pct_of_household_aum DESC;

-- Check aggressive investors
SELECT household_name, total_aum, largest_position_pct
FROM mv_household_portfolio
WHERE fa_id = 'FA-00001' AND risk_tolerance = 'AGGRESSIVE'
ORDER BY total_aum DESC;
```

### Pattern 3: Portfolio Composition
```sql
-- By account type
SELECT * FROM mv_holdings_by_account_type;

-- By risk tolerance
SELECT * FROM v_risk_tolerance_summary;

-- By region
SELECT * FROM v_regional_summary;
```

---

## Performance Tips

1. **Always use materialized views for aggregations** (FA summaries, stock exposure)
2. **Use composite indexes for multi-column filters** (fa_id + risk_tolerance)
3. **Refresh materialized views daily or after bulk updates**
4. **Use EXPLAIN ANALYZE to verify index usage**
5. **Keep statistics updated with ANALYZE**

---

## Troubleshooting

### Slow Query?
1. Run EXPLAIN ANALYZE to see query plan
2. Check if indexes are being used (look for "Index Scan")
3. Ensure materialized views are refreshed
4. Run ANALYZE to update statistics

### Materialized View Out of Date?
```sql
SELECT refresh_all_materialized_views();
```

### Index Not Being Used?
```sql
-- Check if index exists
SELECT * FROM pg_indexes WHERE tablename = 'households';

-- Update statistics
ANALYZE households;

-- Verify with EXPLAIN
EXPLAIN SELECT * FROM households WHERE fa_id = 'FA-00001';
```

### Query Still Slow After Indexing?
- Consider a materialized view for complex aggregations
- Check for missing WHERE clause filters
- Look for functions on indexed columns (prevents index usage)
- Consider partial indexes for common filters

---

## Daily Operations Checklist

- [ ] Refresh materialized views (daily at 2 AM recommended)
- [ ] Monitor slow query logs
- [ ] Check index usage statistics (weekly)
- [ ] Run VACUUM ANALYZE (weekly)
- [ ] Review concentrated positions report
- [ ] Verify query performance metrics

---

**Last Updated:** 2025-01-08
**Version:** 1.0
