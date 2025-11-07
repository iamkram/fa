import pytest
from datetime import datetime

from src.batch.state import (
    AnalystReport,
    PriceData,
    FundamentalEvent,
    SourceFactCheckResult,
    TierFactCheckState,
    BatchGraphStatePhase2
)


def test_analyst_report_creation():
    """Test BlueMatrix analyst report model"""
    report = AnalystReport(
        report_id="BM-12345",
        analyst_firm="Goldman Sachs",
        analyst_name="John Doe",
        report_date=datetime.utcnow(),
        rating_change="upgrade",
        previous_rating="Hold",
        new_rating="Buy",
        price_target=150.0,
        previous_price_target=120.0,
        key_points=["Strong earnings", "Market expansion"],
        full_text="Full report text..."
    )

    assert report.report_id == "BM-12345"
    assert report.rating_change == "upgrade"
    assert report.price_target == 150.0
    assert len(report.key_points) == 2


def test_price_data_creation():
    """Test FactSet price data model"""
    price_data = PriceData(
        date=datetime.utcnow(),
        open=100.0,
        close=105.0,
        high=107.0,
        low=99.0,
        volume=10000000,
        pct_change=5.0,
        volume_vs_avg=1.5,
        volatility_percentile=0.75
    )

    assert price_data.pct_change == 5.0
    assert price_data.volume_vs_avg == 1.5
    assert price_data.volatility_percentile == 0.75


def test_fundamental_event_creation():
    """Test FactSet fundamental event model"""
    event = FundamentalEvent(
        event_type="earnings",
        timestamp=datetime.utcnow(),
        details="Q3 earnings: EPS $2.50, Revenue $10B"
    )

    assert event.event_type == "earnings"
    assert "EPS $2.50" in event.details


def test_source_fact_check_result():
    """Test multi-source fact checking result"""
    result = SourceFactCheckResult(
        source="bluematrix",
        claims_checked=10,
        verified_count=9,
        failed_claims=[{"claim": "test", "issue": "not found"}],
        pass_rate=0.9
    )

    assert result.source == "bluematrix"
    assert result.pass_rate == 0.9
    assert len(result.failed_claims) == 1


def test_tier_fact_check_state():
    """Test multi-source fact checking state for a tier"""
    fact_check = TierFactCheckState(
        tier="medium",
        bluematrix_result=SourceFactCheckResult(
            source="bluematrix",
            claims_checked=5,
            verified_count=5,
            pass_rate=1.0
        ),
        edgar_result=SourceFactCheckResult(
            source="edgar",
            claims_checked=3,
            verified_count=3,
            pass_rate=1.0
        ),
        overall_status="passed",
        overall_pass_rate=1.0
    )

    assert fact_check.tier == "medium"
    assert fact_check.overall_status == "passed"
    assert fact_check.bluematrix_result.pass_rate == 1.0


def test_batch_graph_state_phase2_creation():
    """Test complete Phase 2 state with all sources"""
    state = BatchGraphStatePhase2(
        stock_id="test-123",
        ticker="AAPL",
        company_name="Apple Inc.",
        batch_run_id="test-run"
    )

    assert state.ticker == "AAPL"
    assert len(state.edgar_filings) == 0
    assert len(state.bluematrix_reports) == 0
    assert state.factset_price_data is None
    assert state.hook_summary is None
    assert state.medium_summary is None
    assert state.expanded_summary is None
    assert state.hook_retry_count == 0


def test_batch_graph_state_phase2_with_data():
    """Test Phase 2 state with populated data"""
    report = AnalystReport(
        report_id="BM-001",
        analyst_firm="Goldman",
        analyst_name="Analyst",
        report_date=datetime.utcnow(),
        rating_change="upgrade",
        new_rating="Buy",
        price_target=200.0,
        key_points=["Strong quarter"],
        full_text="Report text"
    )

    price_data = PriceData(
        date=datetime.utcnow(),
        open=100.0,
        close=105.0,
        high=106.0,
        low=99.0,
        volume=5000000,
        pct_change=5.0,
        volume_vs_avg=1.2,
        volatility_percentile=0.6
    )

    state = BatchGraphStatePhase2(
        stock_id="test-456",
        ticker="MSFT",
        company_name="Microsoft",
        batch_run_id="test-run",
        bluematrix_reports=[report],
        bluematrix_status="success",
        factset_price_data=price_data,
        factset_status="success",
        hook_summary="MSFT upgraded to Buy",
        hook_word_count=4,
        medium_summary="Microsoft upgraded by Goldman...",
        medium_word_count=95,
        expanded_summary="Full analysis...",
        expanded_word_count=650
    )

    assert len(state.bluematrix_reports) == 1
    assert state.factset_price_data.close == 105.0
    assert state.hook_word_count == 4
    assert state.medium_word_count == 95
    assert state.expanded_word_count == 650
