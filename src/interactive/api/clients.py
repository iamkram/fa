"""Client management API endpoints"""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from src.shared.database.connection import db_manager
from src.shared.models.database import Client, ClientHolding, Stock, Advisor

router = APIRouter(prefix="/api/clients", tags=["clients"])

class ClientResponse(BaseModel):
    client_id: str
    account_id: str
    name: str
    email: Optional[str]
    phone: Optional[str]
    last_meeting_date: Optional[str]
    next_meeting_date: Optional[str]
    notes: Optional[str]
    client_metadata: Optional[dict]

class ClientHoldingResponse(BaseModel):
    holding_id: str
    ticker: str
    company_name: str
    shares: float
    cost_basis: Optional[float]
    purchase_date: Optional[str]
    notes: Optional[str]
    current_value: Optional[float]  # Can be populated from market data later

class ClientDetailResponse(BaseModel):
    client: ClientResponse
    holdings: List[ClientHoldingResponse]
    total_holdings: int
    advisor_name: str

@router.get("/", response_model=List[ClientResponse])
def list_clients(advisor_id: Optional[str] = Query(None, description="Filter by advisor FA ID")):
    """
    List all clients, optionally filtered by advisor

    Example: GET /api/clients?advisor_id=FA-001
    """
    with db_manager.get_session() as session:
        query = session.query(Client)

        if advisor_id:
            # Get advisor by fa_id
            advisor = session.query(Advisor).filter(Advisor.fa_id == advisor_id).first()
            if not advisor:
                raise HTTPException(status_code=404, detail=f"Advisor {advisor_id} not found")
            query = query.filter(Client.advisor_id == advisor.advisor_id)

        clients = query.order_by(Client.name).all()

        return [
            ClientResponse(
                client_id=str(client.client_id),
                account_id=client.account_id,
                name=client.name,
                email=client.email,
                phone=client.phone,
                last_meeting_date=client.last_meeting_date.isoformat() if client.last_meeting_date else None,
                next_meeting_date=client.next_meeting_date.isoformat() if client.next_meeting_date else None,
                notes=client.notes,
                client_metadata=client.client_metadata or {}
            )
            for client in clients
        ]

@router.get("/{client_id}", response_model=ClientDetailResponse)
def get_client_details(client_id: str):
    """
    Get detailed information about a specific client including their holdings

    Example: GET /api/clients/ACC-001
    """
    with db_manager.get_session() as session:
        # Query by account_id (which is the user-facing ID)
        client = session.query(Client).filter(Client.account_id == client_id).first()

        if not client:
            raise HTTPException(status_code=404, detail=f"Client {client_id} not found")

        # Get advisor name
        advisor = session.query(Advisor).filter(Advisor.advisor_id == client.advisor_id).first()
        advisor_name = advisor.name if advisor else "Unknown"

        # Get client holdings with stock details
        holdings = session.query(ClientHolding, Stock).join(
            Stock, ClientHolding.stock_id == Stock.stock_id
        ).filter(
            ClientHolding.client_id == client.client_id
        ).all()

        holdings_response = [
            ClientHoldingResponse(
                holding_id=str(holding.holding_id),
                ticker=holding.ticker,
                company_name=stock.company_name,
                shares=holding.shares,
                cost_basis=holding.cost_basis,
                purchase_date=holding.purchase_date.isoformat() if holding.purchase_date else None,
                notes=holding.notes,
                current_value=None  # TODO: Add market data integration
            )
            for holding, stock in holdings
        ]

        return ClientDetailResponse(
            client=ClientResponse(
                client_id=str(client.client_id),
                account_id=client.account_id,
                name=client.name,
                email=client.email,
                phone=client.phone,
                last_meeting_date=client.last_meeting_date.isoformat() if client.last_meeting_date else None,
                next_meeting_date=client.next_meeting_date.isoformat() if client.next_meeting_date else None,
                notes=client.notes,
                client_metadata=client.client_metadata or {}
            ),
            holdings=holdings_response,
            total_holdings=len(holdings_response),
            advisor_name=advisor_name
        )

@router.get("/{client_id}/holdings", response_model=List[ClientHoldingResponse])
def get_client_holdings(client_id: str):
    """
    Get just the holdings for a specific client

    Example: GET /api/clients/ACC-001/holdings
    """
    with db_manager.get_session() as session:
        client = session.query(Client).filter(Client.account_id == client_id).first()

        if not client:
            raise HTTPException(status_code=404, detail=f"Client {client_id} not found")

        holdings = session.query(ClientHolding, Stock).join(
            Stock, ClientHolding.stock_id == Stock.stock_id
        ).filter(
            ClientHolding.client_id == client.client_id
        ).all()

        return [
            ClientHoldingResponse(
                holding_id=str(holding.holding_id),
                ticker=holding.ticker,
                company_name=stock.company_name,
                shares=holding.shares,
                cost_basis=holding.cost_basis,
                purchase_date=holding.purchase_date.isoformat() if holding.purchase_date else None,
                notes=holding.notes,
                current_value=None
            )
            for holding, stock in holdings
        ]

@router.get("/ticker/{ticker}/owners", response_model=List[ClientResponse])
def get_ticker_owners(ticker: str, advisor_id: Optional[str] = Query(None)):
    """
    Reverse lookup: Find all clients who own a specific ticker

    Useful for "Who owns AAPL?" queries
    Example: GET /api/clients/ticker/AAPL/owners?advisor_id=FA-001
    """
    with db_manager.get_session() as session:
        query = session.query(Client).join(
            ClientHolding, Client.client_id == ClientHolding.client_id
        ).filter(
            ClientHolding.ticker == ticker.upper()
        )

        if advisor_id:
            advisor = session.query(Advisor).filter(Advisor.fa_id == advisor_id).first()
            if not advisor:
                raise HTTPException(status_code=404, detail=f"Advisor {advisor_id} not found")
            query = query.filter(Client.advisor_id == advisor.advisor_id)

        clients = query.order_by(Client.name).all()

        return [
            ClientResponse(
                client_id=str(client.client_id),
                account_id=client.account_id,
                name=client.name,
                email=client.email,
                phone=client.phone,
                last_meeting_date=client.last_meeting_date.isoformat() if client.last_meeting_date else None,
                next_meeting_date=client.next_meeting_date.isoformat() if client.next_meeting_date else None,
                notes=client.notes,
                client_metadata=client.client_metadata or {}
            )
            for client in clients
        ]
