"""
EDO Database Models for Load Testing

Schema for Financial Advisors, Households, Accounts, and Holdings
"""

from sqlalchemy import Column, String, Integer, Float, DateTime, Text, ForeignKey, Enum, Index
from sqlalchemy.orm import relationship, declarative_base
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime
import uuid
import enum

Base = declarative_base()


class RiskTolerance(str, enum.Enum):
    CONSERVATIVE = "conservative"
    MODERATE = "moderate"
    MODERATE_AGGRESSIVE = "moderate_aggressive"
    AGGRESSIVE = "aggressive"


class AccountType(str, enum.Enum):
    INDIVIDUAL = "individual"
    JOINT = "joint"
    IRA = "ira"
    ROTH_IRA = "roth_ira"
    TRUST = "trust"


class FinancialAdvisor(Base):
    """Financial Advisor table"""
    __tablename__ = "financial_advisors"

    fa_id = Column(String(20), primary_key=True)  # FA-001, FA-002, etc.
    name = Column(String(255), nullable=False)
    email = Column(String(255), unique=True)
    region = Column(String(50), nullable=False, index=True)
    office_location = Column(String(100))
    total_aum = Column(Float, nullable=False)  # Total assets under management
    client_count = Column(Integer, nullable=False)
    specialization = Column(String(100))
    years_experience = Column(Integer)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    households = relationship("Household", back_populates="advisor")


class Household(Base):
    """Household/Client table"""
    __tablename__ = "households"

    household_id = Column(String(20), primary_key=True)  # HH-001, HH-002, etc.
    fa_id = Column(String(20), ForeignKey("financial_advisors.fa_id"), nullable=False, index=True)
    household_name = Column(String(255), nullable=False)
    primary_contact_name = Column(String(255))
    email = Column(String(255))
    phone = Column(String(20))
    total_aum = Column(Float, nullable=False, index=True)
    risk_tolerance = Column(Enum(RiskTolerance), nullable=False)
    client_since = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    advisor = relationship("FinancialAdvisor", back_populates="households")
    accounts = relationship("Account", back_populates="household")

    __table_args__ = (
        Index('idx_fa_aum', 'fa_id', 'total_aum'),
    )


class Account(Base):
    """Account table (each household has multiple accounts)"""
    __tablename__ = "accounts"

    account_id = Column(String(30), primary_key=True)  # ACC-HH001-001, etc.
    household_id = Column(String(20), ForeignKey("households.household_id"), nullable=False, index=True)
    account_number = Column(String(50), unique=True, nullable=False)
    account_type = Column(Enum(AccountType), nullable=False)
    account_name = Column(String(255))
    total_value = Column(Float, nullable=False, index=True)
    cash_balance = Column(Float, default=0.0)
    opened_date = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    household = relationship("Household", back_populates="accounts")
    holdings = relationship("Holding", back_populates="account")

    __table_args__ = (
        Index('idx_household_value', 'household_id', 'total_value'),
    )


class Holding(Base):
    """Holding table (each account has multiple stock holdings)"""
    __tablename__ = "holdings"

    holding_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    account_id = Column(String(30), ForeignKey("accounts.account_id"), nullable=False, index=True)
    ticker = Column(String(10), nullable=False, index=True)
    shares = Column(Float, nullable=False)
    cost_basis = Column(Float, nullable=False)
    current_price = Column(Float, nullable=False)
    current_value = Column(Float, nullable=False)
    unrealized_gain_loss = Column(Float)
    pct_of_account = Column(Float)  # Percentage of account
    purchase_date = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    account = relationship("Account", back_populates="holdings")

    __table_args__ = (
        Index('idx_account_ticker', 'account_id', 'ticker'),
        Index('idx_ticker_value', 'ticker', 'current_value'),
    )
