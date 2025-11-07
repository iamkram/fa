import pytest
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.shared.models.database import Base, Stock, StockSummary, FactCheckStatus

@pytest.fixture
def test_db():
    """Create test database"""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()

def test_stock_creation(test_db):
    """Test creating a stock record"""
    stock = Stock(
        ticker="TEST",
        cusip="123456789",
        company_name="Test Company",
        sector="Technology"
    )
    test_db.add(stock)
    test_db.commit()

    retrieved = test_db.query(Stock).filter_by(ticker="TEST").first()
    assert retrieved is not None
    assert retrieved.company_name == "Test Company"

def test_summary_creation(test_db):
    """Test creating a summary with fact check status"""
    stock = Stock(ticker="TEST", company_name="Test Co", sector="Tech")
    test_db.add(stock)
    test_db.commit()

    summary = StockSummary(
        stock_id=stock.stock_id,
        ticker="TEST",
        generation_date=datetime.utcnow(),
        hook_text="Test hook",
        hook_word_count=2,
        fact_check_status=FactCheckStatus.PASSED
    )
    test_db.add(summary)
    test_db.commit()

    retrieved = test_db.query(StockSummary).first()
    assert retrieved is not None
    assert retrieved.fact_check_status == FactCheckStatus.PASSED
