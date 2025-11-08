# Load Testing Data Generation

Comprehensive system for generating realistic financial advisor, household, and account data for load testing the FA AI System.

## Overview

This system generates:
- **Financial Advisors**: Realistic FAs with AUM, client counts, regions, and specializations
- **Households**: Client households with holdings and risk profiles
- **Accounts**: Multiple accounts per household (Individual, Joint, IRA, Trust, etc.)
- **Holdings**: Stock positions allocated across top 500 NYSE stocks

## Database Schema

### Tables

#### 1. `financial_advisors`
Financial advisors managing client portfolios

| Column | Type | Description |
|--------|------|-------------|
| fa_id | VARCHAR(20) | Primary key (FA-00001, FA-00002, ...) |
| name | VARCHAR(255) | FA full name |
| email | VARCHAR(255) | Email address |
| region | VARCHAR(50) | US region (Northeast, West, etc.) |
| office_location | VARCHAR(100) | City, State |
| total_aum | FLOAT | Total assets under management |
| client_count | INTEGER | Number of client households |
| specialization | VARCHAR(100) | Advisor specialty |
| years_experience | INTEGER | Years in the industry |

**Generated Distribution**:
- AUM: Log-normal ($50M - $1B, mean ~$200M)
- Client count: Based on AUM ($3-5M average per client)

#### 2. `households`
Client households managed by FAs

| Column | Type | Description |
|--------|------|-------------|
| household_id | VARCHAR(20) | Primary key (HH-{FA}-00001, ...) |
| fa_id | VARCHAR(20) | Foreign key to financial_advisors |
| household_name | VARCHAR(255) | Household name |
| primary_contact_name | VARCHAR(255) | Main contact |
| email | VARCHAR(255) | Contact email |
| phone | VARCHAR(20) | Phone number |
| total_aum | FLOAT | Total household assets |
| risk_tolerance | ENUM | conservative, moderate, moderate_aggressive, aggressive |
| client_since | DATETIME | Relationship start date |

**Generated Distribution**:
- AUM: Log-normal ($100K - $50M, mean ~$1M)
- Risk tolerance: Random distribution
- Client since: 1-20 years ago

#### 3. `accounts`
Investment accounts within households

| Column | Type | Description |
|--------|------|-------------|
| account_id | VARCHAR(30) | Primary key (ACC-{HH}-01, ...) |
| household_id | VARCHAR(20) | Foreign key to households |
| account_number | VARCHAR(50) | Account number |
| account_type | ENUM | individual, joint, ira, roth_ira, trust |
| account_name | VARCHAR(255) | Descriptive name |
| total_value | FLOAT | Current account value |
| cash_balance | FLOAT | Cash portion (1-10% of value) |
| opened_date | DATETIME | Account opening date |

**Generated Distribution**:
- Accounts per household: 5 (configurable)
- Value distribution: Dirichlet-like distribution across accounts
- Cash: 1-10% of account value

#### 4. `holdings`
Stock positions within accounts

| Column | Type | Description |
|--------|------|-------------|
| holding_id | UUID | Primary key |
| account_id | VARCHAR(30) | Foreign key to accounts |
| ticker | VARCHAR(10) | Stock ticker symbol |
| shares | FLOAT | Number of shares |
| cost_basis | FLOAT | Purchase price per share |
| current_price | FLOAT | Current market price |
| current_value | FLOAT | shares × current_price |
| unrealized_gain_loss | FLOAT | (current_price - cost_basis) × shares |
| pct_of_account | FLOAT | Percentage of account value |
| purchase_date | DATETIME | Purchase date |

**Generated Distribution**:
- Holdings per account: 5-30 positions
- Stock allocation: 50-90% of investable value
- Ticker selection: Random from top 500 NYSE stocks
- Position sizes: Power law distribution (few large, many small)
- Gain/loss: -30% to +150%

## Stock Universe

390 stocks from top 500 NYSE, including:

**Mega-cap**: AAPL, MSFT, GOOGL, AMZN, NVDA, META, TSLA, etc.
**Large-cap**: NOW, SPGI, ISRG, BLK, BKNG, etc.
**Mid-cap**: BIIB, YUM, CTAS, VMC, etc.

Full list in `scripts/generate_load_test_data.py:TOP_500_STOCKS`

## Usage

### Generate Full Load Test Data

Generate 100 FAs, 200 households each, 5 accounts per household:

```bash
python scripts/generate_load_test_data.py
```

This creates:
- **100 Financial Advisors**
- **20,000 Households** (200 per FA)
- **100,000 Accounts** (5 per household)
- **~500,000-1,000,000 Holdings** (varies per account)

**Estimated time**: 30-60 minutes depending on hardware
**Database size**: ~2-4 GB

### Custom Configuration

Adjust parameters:

```bash
# Smaller test set
python scripts/generate_load_test_data.py --fas 10 --households-per-fa 50

# Larger accounts per household
python scripts/generate_load_test_data.py --accounts-per-household 10
```

### Clean and Regenerate

Drop and recreate tables:

```bash
python scripts/clean_edo_tables.py
python scripts/generate_load_test_data.py
```

## Data Characteristics

### Realistic Distributions

**Financial Advisor AUM**:
- Distribution: Log-normal
- Mean: $200M
- Range: $50M - $1B
- Typical book: 30-50 clients

**Household Wealth**:
- Distribution: Log-normal
- Mean: $1M
- Range: $100K - $50M
- Mirrors wealth distribution in US

**Account Sizes**:
- Distributed proportionally within household
- Cash buffer: 1-10% (realistic for invested accounts)

**Holdings**:
- Power law distribution (Pareto principle)
- Few large positions (10-30% of account)
- Many small positions (1-5% of account)
- Total allocation: 50-90% in stocks

### Realistic Metadata

**Names**: Random but realistic (100+ first/last name combinations)
**Regions**: 9 US regions with appropriate office locations
**Dates**: Reasonable historical dates (accounts opened after household onboarding)
**Risk Profiles**: Distributed across conservative to aggressive

## Performance Metrics

### Generation Performance

Test run (2 FAs, 10 households, 30 accounts):
- **FAs**: Instant
- **Households**: ~1 second
- **Accounts**: ~1 second
- **Holdings**: ~5 seconds (488 holdings)

Estimated full run (100 FAs, 20K households, 100K accounts):
- **Total time**: 30-60 minutes
- **Bottleneck**: Holdings generation (batch insert optimized)

### Query Performance

With proper indexes on:
- `fa_id` (households, accounts)
- `ticker` (holdings)
- `total_aum` (advisors, households)

Expected query performance:
- FA lookup: < 1ms
- Household + accounts: < 10ms
- Holdings for account: < 5ms
- Aggregate by ticker: < 100ms

## Load Testing Scenarios

### Scenario 1: Individual Query Load

Simulate 1000 concurrent users querying FA data:

```python
# Example load test with locust
from locust import HttpUser, task, between

class FAQueryUser(HttpUser):
    wait_time = between(1, 3)

    @task
    def query_fa_holdings(self):
        fa_id = f"FA-{random.randint(1, 100):05d}"
        self.client.post("/query", json={
            "question": f"What are the holdings for {fa_id}?",
            "session_id": self.user_id
        })
```

### Scenario 2: Aggregate Analysis

Query total exposure across all accounts:

```sql
SELECT ticker, SUM(current_value) as total_exposure
FROM holdings
GROUP BY ticker
ORDER BY total_exposure DESC
LIMIT 100;
```

### Scenario 3: FA Dashboard

Load all data for a single FA:

```sql
SELECT
    fa.name,
    COUNT(DISTINCT h.household_id) as num_households,
    COUNT(DISTINCT a.account_id) as num_accounts,
    SUM(h.total_aum) as total_aum
FROM financial_advisors fa
JOIN households h ON fa.fa_id = h.fa_id
JOIN accounts a ON h.household_id = a.household_id
WHERE fa.fa_id = 'FA-00001'
GROUP BY fa.fa_id, fa.name;
```

## Files

### Core Files

- `src/shared/models/edo_database.py`: SQLAlchemy models for all tables
- `scripts/generate_load_test_data.py`: Main data generation script
- `scripts/clean_edo_tables.py`: Table cleanup utility

### Configuration

Data generation uses environment variables from `.env`:
- `DATABASE_URL`: PostgreSQL connection string

## Troubleshooting

### Issue: Tables already exist

```bash
python scripts/clean_edo_tables.py
```

### Issue: Generation too slow

Reduce batch size or adjust parameters:

```bash
python scripts/generate_load_test_data.py --fas 10 --households-per-fa 100
```

### Issue: Out of memory

Generate in stages:

```bash
# Stage 1: First 50 FAs
python scripts/generate_load_test_data.py --fas 50

# Stage 2: Manually update script to start at FA-00051
```

## Future Enhancements

1. **Real stock prices**: Integrate with market data API
2. **Historical trades**: Generate transaction history
3. **Performance attribution**: Calculate returns over time
4. **Tax lots**: Track purchase lots for tax reporting
5. **Asset allocation**: Generate bonds, ETFs, mutual funds
6. **Rebalancing**: Simulate periodic rebalancing

## Database Indexes

The schema includes optimal indexes for common queries:

```sql
CREATE INDEX idx_fa_aum ON households(fa_id, total_aum);
CREATE INDEX idx_household_value ON accounts(household_id, total_value);
CREATE INDEX idx_account_ticker ON holdings(account_id, ticker);
CREATE INDEX idx_ticker_value ON holdings(ticker, current_value);
```

## Data Quality

All generated data includes:
- ✅ Referential integrity (foreign keys)
- ✅ Realistic distributions (log-normal for wealth)
- ✅ Proper date relationships (accounts after households)
- ✅ Valid enums (risk tolerance, account types)
- ✅ Reasonable ranges (AUM, holdings, etc.)
- ✅ No duplicate tickers per account
- ✅ Cash reserves (1-10% per account)
- ✅ Gain/loss realism (-30% to +150%)

## License

Proprietary - Internal Use Only
