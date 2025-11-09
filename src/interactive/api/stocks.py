"""Stock lookup and search API endpoints"""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from src.shared.database.connection import db_manager
from src.shared.models.database import Stock, StockSummary, Client, ClientHolding
from sqlalchemy import func, or_

router = APIRouter(prefix="/api/stocks", tags=["stocks"])

class StockResponse(BaseModel):
    stock_id: str
    ticker: str
    company_name: str
    cusip: Optional[str]
    sector: Optional[str]

class StockOwnerResponse(BaseModel):
    client_id: str
    account_id: str
    client_name: str
    shares: float
    cost_basis: Optional[float]
    total_value: Optional[float]

class StockSummaryResponse(BaseModel):
    summary_id: str
    summary_text: str
    generation_date: str

class StockDetailResponse(BaseModel):
    stock: StockResponse
    recent_summary: Optional[StockSummaryResponse]
    owners: List[StockOwnerResponse]
    total_owners: int
    total_shares_held: float

@router.get("/search", response_model=List[StockResponse])
def search_stocks(q: str = Query(..., min_length=1, description="Search query (ticker or company name)")):
    """
    Search for stocks by ticker symbol or company name

    Example: GET /api/stocks/search?q=AAPL
    Example: GET /api/stocks/search?q=Apple
    """
    with db_manager.get_session() as session:
        # Search by ticker (exact or partial) or company name (partial)
        search_pattern = f"%{q.upper()}%"

        stocks = session.query(Stock).filter(
            or_(
                Stock.ticker.ilike(search_pattern),
                Stock.company_name.ilike(search_pattern)
            )
        ).order_by(Stock.ticker).limit(20).all()

        return [
            StockResponse(
                stock_id=str(stock.stock_id),
                ticker=stock.ticker,
                company_name=stock.company_name,
                cusip=stock.cusip,
                sector=stock.sector,
            )
            for stock in stocks
        ]

@router.get("/{ticker}", response_model=StockDetailResponse)
def get_stock_details(ticker: str, advisor_id: Optional[str] = Query(None, description="Filter owners by advisor FA ID")):
    """
    Get detailed stock information including recent summary and ownership

    Example: GET /api/stocks/AAPL
    Example: GET /api/stocks/AAPL?advisor_id=FA-001
    """
    with db_manager.get_session() as session:
        # Get stock
        stock = session.query(Stock).filter(Stock.ticker == ticker.upper()).first()

        if not stock:
            raise HTTPException(status_code=404, detail=f"Stock {ticker} not found")

        # Get most recent summary
        recent_summary = session.query(StockSummary).filter(
            StockSummary.stock_id == stock.stock_id
        ).order_by(StockSummary.generation_date.desc()).first()

        summary_response = None
        if recent_summary:
            summary_response = StockSummaryResponse(
                summary_id=str(recent_summary.summary_id),
                summary_text=recent_summary.medium_text or "",
                generation_date=recent_summary.generation_date.isoformat()
            )

        # Get owners (clients who hold this stock)
        owners_query = session.query(
            Client,
            ClientHolding
        ).join(
            ClientHolding, Client.client_id == ClientHolding.client_id
        ).filter(
            ClientHolding.stock_id == stock.stock_id
        )

        # Filter by advisor if specified
        if advisor_id:
            from src.shared.models.database import Advisor
            advisor = session.query(Advisor).filter(Advisor.fa_id == advisor_id).first()
            if advisor:
                owners_query = owners_query.filter(Client.advisor_id == advisor.advisor_id)

        owners = owners_query.all()

        owners_response = []
        total_shares = 0.0

        for client, holding in owners:
            total_value = None
            if holding.cost_basis is not None:
                total_value = holding.shares * holding.cost_basis

            owners_response.append(StockOwnerResponse(
                client_id=str(client.client_id),
                account_id=client.account_id,
                client_name=client.name,
                shares=holding.shares,
                cost_basis=holding.cost_basis,
                total_value=total_value
            ))
            total_shares += holding.shares

        return StockDetailResponse(
            stock=StockResponse(
                stock_id=str(stock.stock_id),
                ticker=stock.ticker,
                company_name=stock.company_name,
                cusip=stock.cusip,
                sector=stock.sector,
            ),
            recent_summary=summary_response,
            owners=owners_response,
            total_owners=len(owners_response),
            total_shares_held=total_shares
        )

@router.get("/", response_model=List[StockResponse])
def list_stocks(limit: int = Query(50, le=200), offset: int = Query(0, ge=0)):
    """
    List all stocks in the database

    Example: GET /api/stocks?limit=10&offset=0
    """
    with db_manager.get_session() as session:
        stocks = session.query(Stock).order_by(Stock.ticker).offset(offset).limit(limit).all()

        return [
            StockResponse(
                stock_id=str(stock.stock_id),
                ticker=stock.ticker,
                company_name=stock.company_name,
                cusip=stock.cusip,
                sector=stock.sector,
            )
            for stock in stocks
        ]

class SummaryHistoryItem(BaseModel):
    summary_id: str
    generation_date: str
    hook_text: Optional[str]
    medium_text: Optional[str]
    expanded_text: Optional[str]
    word_count: int

@router.get("/{ticker}/summaries/history", response_model=List[SummaryHistoryItem])
def get_summary_history(ticker: str, limit: int = Query(10, le=50, description="Number of summaries to return")):
    """
    Get summary history for a stock (most recent first)

    Example: GET /api/stocks/AAPL/summaries/history?limit=10
    """
    with db_manager.get_session() as session:
        stock = session.query(Stock).filter(Stock.ticker == ticker.upper()).first()

        if not stock:
            raise HTTPException(status_code=404, detail=f"Stock {ticker} not found")

        summaries = session.query(StockSummary).filter(
            StockSummary.stock_id == stock.stock_id
        ).order_by(StockSummary.generation_date.desc()).limit(limit).all()

        return [
            SummaryHistoryItem(
                summary_id=str(summary.summary_id),
                generation_date=summary.generation_date.isoformat(),
                hook_text=summary.hook_text,
                medium_text=summary.medium_text,
                expanded_text=summary.expanded_text,
                word_count=summary.medium_word_count or 0
            )
            for summary in summaries
        ]

class SummaryDiff(BaseModel):
    added_sentences: List[str]
    removed_sentences: List[str]
    summary1: SummaryHistoryItem
    summary2: SummaryHistoryItem

@router.get("/{ticker}/summaries/compare", response_model=SummaryDiff)
def compare_summaries(
    ticker: str,
    summary1_id: str = Query(..., description="First summary ID (older)"),
    summary2_id: str = Query(..., description="Second summary ID (newer)")
):
    """
    Compare two summaries and return the differences

    Example: GET /api/stocks/AAPL/summaries/compare?summary1_id=xxx&summary2_id=yyy
    """
    with db_manager.get_session() as session:
        stock = session.query(Stock).filter(Stock.ticker == ticker.upper()).first()

        if not stock:
            raise HTTPException(status_code=404, detail=f"Stock {ticker} not found")

        summary1 = session.query(StockSummary).filter(
            StockSummary.summary_id == summary1_id
        ).first()

        summary2 = session.query(StockSummary).filter(
            StockSummary.summary_id == summary2_id
        ).first()

        if not summary1 or not summary2:
            raise HTTPException(status_code=404, detail="One or both summaries not found")

        # Simple sentence-level diff
        import re

        def split_sentences(text: str) -> List[str]:
            if not text:
                return []
            # Split on periods, exclamation marks, or question marks followed by space or end
            sentences = re.split(r'[.!?]\s+|\[.!?]$', text)
            return [s.strip() for s in sentences if s.strip()]

        sentences1 = set(split_sentences(summary1.medium_text or ""))
        sentences2 = set(split_sentences(summary2.medium_text or ""))

        added = list(sentences2 - sentences1)
        removed = list(sentences1 - sentences2)

        return SummaryDiff(
            added_sentences=added,
            removed_sentences=removed,
            summary1=SummaryHistoryItem(
                summary_id=str(summary1.summary_id),
                generation_date=summary1.generation_date.isoformat(),
                hook_text=summary1.hook_text,
                medium_text=summary1.medium_text,
                expanded_text=summary1.expanded_text,
                word_count=summary1.medium_word_count or 0
            ),
            summary2=SummaryHistoryItem(
                summary_id=str(summary2.summary_id),
                generation_date=summary2.generation_date.isoformat(),
                hook_text=summary2.hook_text,
                medium_text=summary2.medium_text,
                expanded_text=summary2.expanded_text,
                word_count=summary2.medium_word_count or 0
            )
        )
