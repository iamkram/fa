#!/usr/bin/env python3
"""
Generate Load Test Data for FA AI System

Generates:
- 100 Financial Advisors
- 200 Households per FA (20,000 total)
- 5 Accounts per Household (100,000 total)
- Holdings per account (50-90% allocation from top 500 NYSE stocks)

Usage:
    python scripts/generate_load_test_data.py
    python scripts/generate_load_test_data.py --fas 100 --households-per-fa 200
"""

import sys
import random
import argparse
from pathlib import Path
from datetime import datetime, timedelta
from decimal import Decimal
import logging

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.shared.models.edo_database import (
    Base, FinancialAdvisor, Household, Account, Holding,
    RiskTolerance, AccountType
)
from src.config.settings import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Top 500 NYSE stocks (representative sample)
TOP_500_STOCKS = [
    # Mega-cap (Top 50)
    "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA", "BRK.B", "V", "UNH",
    "JNJ", "WMT", "JPM", "MA", "PG", "HD", "CVX", "MRK", "ABBV", "PEP",
    "KO", "COST", "AVGO", "TMO", "MCD", "CSCO", "ACN", "ABT", "ADBE", "NKE",
    "DHR", "VZ", "CMCSA", "INTC", "TXN", "PM", "NEE", "CRM", "DIS", "UPS",
    "QCOM", "HON", "AMGN", "INTU", "SBUX", "IBM", "BA", "GE", "AMD", "CAT",

    # Large-cap (50-150)
    "NOW", "SPGI", "AXP", "ISRG", "BLK", "RTX", "LOW", "BKNG", "DE", "GS",
    "LMT", "ADP", "EL", "TJX", "MMC", "SYK", "CI", "PLD", "ZTS", "GILD",
    "MDLZ", "C", "REGN", "CB", "DUK", "SO", "VRTX", "AON", "BMY", "EQIX",
    "PNC", "USB", "MS", "APD", "MO", "LRCX", "SHW", "TGT", "MCO", "CL",
    "NSC", "MMM", "KLAC", "ITW", "BSX", "EW", "HUM", "ICE", "ETN", "CME",
    "WM", "PGR", "D", "APH", "MU", "SNPS", "NXPI", "ADI", "EL", "CMG",
    "MCK", "ORLY", "PSA", "F", "MCHP", "MSCI", "MSI", "ECL", "SLB", "ROP",
    "GM", "ADSK", "FIS", "CDNS", "PAYX", "AJG", "AEP", "TEL", "TFC", "FI",
    "EMR", "AFL", "CARR", "NOC", "ROST", "AMT", "DG", "WELL", "DOW", "XEL",
    "PSX", "KMI", "COF", "CCI", "HCA", "OKE", "FDX", "WMB", "TT", "PPG",

    # Mid-cap (150-300)
    "CTVA", "BK", "DHI", "IQV", "GIS", "HSY", "SRE", "A", "SPG", "MNST",
    "HLT", "AIG", "YUM", "IFF", "SYY", "CTAS", "BIIB", "IDXX", "AZO", "CMI",
    "GPN", "PRU", "FTNT", "NEM", "APTV", "DD", "DFS", "VRSK", "PH", "VICI",
    "KMB", "AWK", "ED", "FAST", "EXC", "LHX", "GLW", "VMC", "EXR", "IR",
    "MTD", "WEC", "FTV", "CNC", "WAB", "TSCO", "RMD", "KEYS", "RSG", "WBA",
    "LVS", "VLO", "STZ", "FANG", "CPRT", "DLTR", "AVB", "DTE", "CHD", "EIX",
    "LH", "ANSS", "EFX", "MLM", "HAL", "AMP", "ROK", "OTIS", "DOV", "WY",
    "EBAY", "XYL", "CAH", "URI", "PKG", "LYB", "AEE", "TROW", "BKR", "HIG",
    "PWR", "WAT", "EXPD", "SWK", "HES", "FITB", "TDY", "CMS", "FE", "NTRS",
    "ACGL", "WBD", "BBY", "HPQ", "GWW", "TDG", "ULTA", "DRI", "HBAN", "LUV",
    "J", "VTR", "ES", "CBRE", "PTC", "RF", "MKC", "STT", "BALL", "MTB",
    "MAS", "HOLX", "LKQ", "ATO", "CFG", "OMC", "POOL", "NTAP", "CINF", "ALB",
    "WST", "TXT", "ETR", "KIM", "SBAC", "MAA", "CLX", "STE", "EXPE", "NVR",
    "TTWO", "AKAM", "TSN", "K", "LNT", "NDAQ", "CAG", "HRL", "EVRG", "HSIC",
    "COO", "FLT", "ZBRA", "DGX", "ENPH", "EPAM", "TER", "BXP", "CE", "IPG",

    # Additional stocks (300-500)
    "PNR", "TECH", "JBHT", "JKHY", "CHRW", "NI", "ALLE", "MKTX", "IEX", "PEAK",
    "REG", "RJF", "CTLT", "SWKS", "L", "MOS", "BIO", "AIZ", "PKI", "FFIV",
    "GL", "TFX", "FDS", "UDR", "CPT", "BF.B", "APA", "EMN", "TPR", "WYNN",
    "MPWR", "LW", "VTRS", "LDOS", "HST", "AAP", "ALGN", "WRB", "TAP", "HAS",
    "KMX", "LYV", "UAL", "SNA", "WHR", "NRG", "HII", "GNRC", "UHS", "IVZ",
    "PNW", "ARE", "FRT", "CRL", "PAYC", "MGM", "NWSA", "BWA", "CPB", "SEE",
    "FOXA", "BEN", "XRAY", "PHM", "FOX", "DVA", "CMA", "RL", "NCLH", "VNO",
    "AAL", "HWM", "ZION", "AIV", "MHK", "IRM", "DXC", "RHI", "PVH", "GPS",
    "PARA", "FMC", "AOS", "NWL", "LEG", "OGN", "WHR", "OMC", "IPG", "HBI",
]

# US Regions
REGIONS = ["Northeast", "Southeast", "Midwest", "Southwest", "West", "Northwest", "Mid-Atlantic", "Mountain", "Pacific"]

# Office Locations
OFFICES = [
    "New York, NY", "Los Angeles, CA", "Chicago, IL", "Houston, TX", "Phoenix, AZ",
    "Philadelphia, PA", "San Antonio, TX", "San Diego, CA", "Dallas, TX", "San Jose, CA",
    "Austin, TX", "Jacksonville, FL", "Fort Worth, TX", "Columbus, OH", "Charlotte, NC",
    "San Francisco, CA", "Indianapolis, IN", "Seattle, WA", "Denver, CO", "Washington, DC",
    "Boston, MA", "Nashville, TN", "Detroit, MI", "Portland, OR", "Memphis, TN",
    "Louisville, KY", "Baltimore, MD", "Milwaukee, WI", "Albuquerque, NM", "Tucson, AZ"
]

# Specializations
SPECIALIZATIONS = [
    "High Net Worth", "Tech Executives", "Corporate Executives", "Entrepreneurs",
    "Retirees", "Medical Professionals", "Legal Professionals", "Real Estate Investors",
    "Family Offices", "Institutional Clients", "Small Business Owners", "Athletes & Entertainers"
]

# First and Last Names for variety
FIRST_NAMES = [
    "James", "Mary", "John", "Patricia", "Robert", "Jennifer", "Michael", "Linda",
    "William", "Barbara", "David", "Elizabeth", "Richard", "Susan", "Joseph", "Jessica",
    "Thomas", "Sarah", "Charles", "Karen", "Christopher", "Nancy", "Daniel", "Lisa",
    "Matthew", "Betty", "Anthony", "Margaret", "Mark", "Sandra", "Donald", "Ashley",
    "Steven", "Kimberly", "Paul", "Emily", "Andrew", "Donna", "Joshua", "Michelle",
    "Kenneth", "Dorothy", "Kevin", "Carol", "Brian", "Amanda", "George", "Melissa",
    "Edward", "Deborah", "Ronald", "Stephanie", "Timothy", "Rebecca", "Jason", "Sharon",
    "Jeffrey", "Laura", "Ryan", "Cynthia", "Jacob", "Kathleen", "Gary", "Amy"
]

LAST_NAMES = [
    "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis",
    "Rodriguez", "Martinez", "Hernandez", "Lopez", "Gonzalez", "Wilson", "Anderson", "Thomas",
    "Taylor", "Moore", "Jackson", "Martin", "Lee", "Perez", "Thompson", "White",
    "Harris", "Sanchez", "Clark", "Ramirez", "Lewis", "Robinson", "Walker", "Young",
    "Allen", "King", "Wright", "Scott", "Torres", "Nguyen", "Hill", "Flores",
    "Green", "Adams", "Nelson", "Baker", "Hall", "Rivera", "Campbell", "Mitchell",
    "Carter", "Roberts", "Gomez", "Phillips", "Evans", "Turner", "Diaz", "Parker",
    "Cruz", "Edwards", "Collins", "Reyes", "Stewart", "Morris", "Morales", "Murphy"
]

HOUSEHOLD_SUFFIXES = [
    "Family Trust", "Investment Account", "Retirement Portfolio", "Growth Fund",
    "Foundation", "Living Trust", "Estate", "Holdings", "Wealth Management", "Capital",
    "Family Office", "Revocable Trust", "Joint Account", "Legacy Fund", "Portfolio"
]


def generate_fa_name():
    """Generate a random FA name"""
    return f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}"


def generate_household_name():
    """Generate a random household name"""
    last_name = random.choice(LAST_NAMES)
    suffix = random.choice(HOUSEHOLD_SUFFIXES)
    return f"{last_name} {suffix}"


def generate_financial_advisors(n=100):
    """Generate N financial advisors"""
    logger.info(f"Generating {n} financial advisors...")

    advisors = []
    for i in range(1, n + 1):
        fa_id = f"FA-{i:05d}"
        name = generate_fa_name()

        # Realistic AUM distribution (log-normal)
        # Mean: $200M, Range: $50M - $1B
        aum = random.lognormvariate(18.8, 0.6)  # ln(200M) ≈ 19.1
        aum = max(50_000_000, min(1_000_000_000, aum))

        # Client count based on AUM (typically $3-5M per client)
        avg_per_client = random.uniform(3_000_000, 5_000_000)
        client_count = int(aum / avg_per_client)

        advisor = FinancialAdvisor(
            fa_id=fa_id,
            name=name,
            email=f"{name.lower().replace(' ', '.')}@wealthadvisors.com",
            region=random.choice(REGIONS),
            office_location=random.choice(OFFICES),
            total_aum=aum,
            client_count=client_count,
            specialization=random.choice(SPECIALIZATIONS),
            years_experience=random.randint(5, 35)
        )
        advisors.append(advisor)

    return advisors


def generate_households(fa, n=200):
    """Generate N households for a given FA"""
    logger.info(f"  Generating {n} households for {fa.name}...")

    households = []
    for i in range(1, n + 1):
        hh_id = f"HH-{fa.fa_id.split('-')[1]}-{i:05d}"

        # AUM distribution (log-normal)
        # Mean: $1M, Range: $100K - $50M
        aum = random.lognormvariate(13.8, 1.2)  # ln(1M) ≈ 13.8
        aum = max(100_000, min(50_000_000, aum))

        # Client since date (1-20 years ago)
        years_ago = random.randint(1, 20)
        client_since = datetime.utcnow() - timedelta(days=365 * years_ago)

        household = Household(
            household_id=hh_id,
            fa_id=fa.fa_id,
            household_name=generate_household_name(),
            primary_contact_name=generate_fa_name(),
            email=f"client{hh_id.replace('-', '')}@email.com",
            phone=f"({random.randint(200, 999)}) {random.randint(200, 999)}-{random.randint(1000, 9999)}",
            total_aum=aum,
            risk_tolerance=random.choice(list(RiskTolerance)),
            client_since=client_since
        )
        households.append(household)

    return households


def generate_accounts(household, n=5):
    """Generate N accounts for a given household"""
    logger.info(f"    Generating {n} accounts for {household.household_name}...")

    accounts = []
    total_aum = household.total_aum

    # Distribute AUM across accounts (Dirichlet distribution approximation)
    weights = [random.random() for _ in range(n)]
    total_weight = sum(weights)
    weights = [w / total_weight for w in weights]

    for i in range(1, n + 1):
        account_id = f"ACC-{household.household_id.split('-')[1]}-{household.household_id.split('-')[2]}-{i:02d}"
        account_value = total_aum * weights[i - 1]

        # Cash balance (1-10% of account value)
        cash_balance = account_value * random.uniform(0.01, 0.10)

        # Opened date (same or later than household client_since)
        days_after = random.randint(0, 365 * 5)
        opened_date = household.client_since + timedelta(days=days_after)

        # Generate unique account number from account_id components
        fa_num = int(household.household_id.split('-')[1])
        hh_num = int(household.household_id.split('-')[2])
        unique_account_num = f"{fa_num:03d}{hh_num:03d}{i:03d}"

        account = Account(
            account_id=account_id,
            household_id=household.household_id,
            account_number=unique_account_num,
            account_type=random.choice(list(AccountType)),
            account_name=f"{household.household_name} - Account {i}",
            total_value=account_value,
            cash_balance=cash_balance,
            opened_date=opened_date
        )
        accounts.append(account)

    return accounts


def generate_holdings(account, stocks):
    """Generate holdings for an account (50-90% allocation from top stocks)"""
    logger.info(f"      Generating holdings for {account.account_id}...")

    holdings = []
    investable_value = account.total_value - account.cash_balance

    # Allocate 50-90% to stocks, rest to cash
    stock_allocation_pct = random.uniform(0.50, 0.90)
    stock_value = investable_value * stock_allocation_pct

    # Number of holdings (5-30 positions)
    num_positions = random.randint(5, 30)

    # Select random stocks
    selected_stocks = random.sample(stocks, min(num_positions, len(stocks)))

    # Distribute value across holdings (power law distribution - few large positions, many small)
    weights = [random.random() ** 2 for _ in range(num_positions)]  # Power law
    total_weight = sum(weights)
    weights = [w / total_weight for w in weights]

    for idx, ticker in enumerate(selected_stocks):
        position_value = stock_value * weights[idx]

        if position_value < 100:  # Skip very small positions
            continue

        # Simulated stock price (realistic range $10 - $500)
        current_price = random.uniform(10, 500)
        shares = position_value / current_price

        # Cost basis (simulate gain/loss: -30% to +150%)
        gain_loss_factor = random.uniform(0.70, 2.50)
        cost_basis = current_price / gain_loss_factor

        unrealized_gl = (current_price - cost_basis) * shares
        pct_of_account = (position_value / account.total_value) * 100

        # Purchase date (within account's lifetime)
        days_since_open = max(0, (datetime.utcnow() - account.opened_date).days)
        if days_since_open > 0:
            days_after_open = random.randint(0, days_since_open)
            purchase_date = account.opened_date + timedelta(days=days_after_open)
        else:
            purchase_date = account.opened_date

        holding = Holding(
            account_id=account.account_id,
            ticker=ticker,
            shares=shares,
            cost_basis=cost_basis,
            current_price=current_price,
            current_value=position_value,
            unrealized_gain_loss=unrealized_gl,
            pct_of_account=pct_of_account,
            purchase_date=purchase_date
        )
        holdings.append(holding)

    return holdings


def main(args):
    """Main data generation function"""
    logger.info("=" * 80)
    logger.info("FA AI System - Load Test Data Generation")
    logger.info("=" * 80)

    # Create database engine
    engine = create_engine(settings.database_url)

    # Create tables
    logger.info("\n1. Creating database tables...")
    Base.metadata.create_all(engine)
    logger.info("   ✅ Tables created")

    # Create session
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        # Generate Financial Advisors
        logger.info(f"\n2. Generating {args.fas} Financial Advisors...")
        advisors = generate_financial_advisors(args.fas)
        session.add_all(advisors)
        session.commit()
        logger.info(f"   ✅ Created {len(advisors)} financial advisors")

        # Generate Households
        logger.info(f"\n3. Generating {args.households_per_fa} Households per FA...")
        all_households = []
        for fa in advisors:
            households = generate_households(fa, args.households_per_fa)
            all_households.extend(households)

        session.add_all(all_households)
        session.commit()
        logger.info(f"   ✅ Created {len(all_households)} households")

        # Generate Accounts
        logger.info(f"\n4. Generating {args.accounts_per_household} Accounts per Household...")
        all_accounts = []
        for hh in all_households:
            accounts = generate_accounts(hh, args.accounts_per_household)
            all_accounts.extend(accounts)

        session.add_all(all_accounts)
        session.commit()
        logger.info(f"   ✅ Created {len(all_accounts)} accounts")

        # Generate Holdings
        logger.info(f"\n5. Generating Holdings for all Accounts...")
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

        logger.info(f"   ✅ Created holdings")

        # Summary
        logger.info("\n" + "=" * 80)
        logger.info("GENERATION COMPLETE")
        logger.info("=" * 80)
        logger.info(f"Financial Advisors: {len(advisors):,}")
        logger.info(f"Households: {len(all_households):,}")
        logger.info(f"Accounts: {len(all_accounts):,}")
        logger.info(f"Total Holdings: {session.query(Holding).count():,}")

        # Calculate totals
        total_aum = session.query(FinancialAdvisor).with_entities(
            func.sum(FinancialAdvisor.total_aum)
        ).scalar()
        logger.info(f"Total AUM: ${total_aum/1_000_000_000:.2f}B")
        logger.info("=" * 80)

    except Exception as e:
        logger.error(f"Error during generation: {str(e)}")
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    from sqlalchemy import func

    parser = argparse.ArgumentParser(description="Generate load test data for FA AI System")
    parser.add_argument("--fas", type=int, default=100, help="Number of financial advisors")
    parser.add_argument("--households-per-fa", type=int, default=200, help="Households per FA")
    parser.add_argument("--accounts-per-household", type=int, default=5, help="Accounts per household")

    args = parser.parse_args()

    logger.info(f"Configuration:")
    logger.info(f"  FAs: {args.fas}")
    logger.info(f"  Households per FA: {args.households_per_fa}")
    logger.info(f"  Accounts per Household: {args.accounts_per_household}")
    logger.info(f"  Total Households: {args.fas * args.households_per_fa:,}")
    logger.info(f"  Total Accounts: {args.fas * args.households_per_fa * args.accounts_per_household:,}")
    logger.info("")

    main(args)
