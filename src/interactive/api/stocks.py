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
