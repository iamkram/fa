# MVP Features Implementation Specification

**Status**: Database layer complete, API and UI implementation needed
**Created**: 2025-01-09
**Estimated Total Time**: 15-20 hours

---

## ✅ COMPLETED WORK

### Database Models (src/shared/models/database.py:85-134)

Three new models successfully added and tables created:

```python
class Advisor(Base):
    # Stores FA profiles with preferences/watchlist
    advisor_id, fa_id, name, email, firm_name, preferences (JSON)

class Client(Base):
    # Stores client information linked to advisors
    client_id, advisor_id, account_id, name, email, phone
    last_meeting_date, next_meeting_date, notes, client_metadata (JSON)

class ClientHolding(Base):
    # Links clients to their stock holdings
    holding_id, client_id, stock_id, ticker, shares, cost_basis, purchase_date
    # Indexed for "Who owns AAPL?" queries
```

✅ Database tables created with `python3 scripts/setup_database.py`

---

## 🚧 REMAINING IMPLEMENTATION

## Feature 2: Advisor Name Display (PRIORITY 1 - Quick Win)

**Goal**: Display advisor name in Chat page header
**Time Estimate**: 2-3 hours
**Value**: Personalization, multi-advisor support

### Backend: Create Advisor API

**File**: `src/interactive/api/advisors.py` (NEW FILE)

```python
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from src.shared.database.connection import db_manager
from src.shared.models.database import Advisor
from sqlalchemy.orm import Session

router = APIRouter(prefix="/api/advisors", tags=["advisors"])

class AdvisorResponse(BaseModel):
    advisor_id: str
    fa_id: str
    name: str
    email: Optional[str]
    firm_name: Optional[str]
    preferences: Optional[dict]

class CreateAdvisorRequest(BaseModel):
    fa_id: str
    name: str
    email: Optional[str] = None
    firm_name: Optional[str] = None
    preferences: Optional[dict] = None

@router.get("/{fa_id}", response_model=AdvisorResponse)
def get_advisor(fa_id: str):
    """Get advisor by FA ID"""
    with db_manager.get_session() as session:
        advisor = session.query(Advisor).filter(Advisor.fa_id == fa_id).first()
        if not advisor:
            raise HTTPException(status_code=404, detail=f"Advisor {fa_id} not found")
        return AdvisorResponse(
            advisor_id=str(advisor.advisor_id),
            fa_id=advisor.fa_id,
            name=advisor.name,
            email=advisor.email,
            firm_name=advisor.firm_name,
            preferences=advisor.preferences or {}
        )

@router.post("/", response_model=AdvisorResponse)
def create_advisor(request: CreateAdvisorRequest):
    """Create new advisor"""
    with db_manager.get_session() as session:
        # Check if advisor already exists
        existing = session.query(Advisor).filter(Advisor.fa_id == request.fa_id).first()
        if existing:
            raise HTTPException(status_code=400, detail=f"Advisor {request.fa_id} already exists")

        advisor = Advisor(
            fa_id=request.fa_id,
            name=request.name,
            email=request.email,
            firm_name=request.firm_name,
            preferences=request.preferences or {"watchlist": []}
        )
        session.add(advisor)
        session.commit()
        session.refresh(advisor)

        return AdvisorResponse(
            advisor_id=str(advisor.advisor_id),
            fa_id=advisor.fa_id,
            name=advisor.name,
            email=advisor.email,
            firm_name=advisor.firm_name,
            preferences=advisor.preferences
        )

@router.put("/{fa_id}/preferences", response_model=AdvisorResponse)
def update_preferences(fa_id: str, preferences: dict):
    """Update advisor preferences (watchlist, etc.)"""
    with db_manager.get_session() as session:
        advisor = session.query(Advisor).filter(Advisor.fa_id == fa_id).first()
        if not advisor:
            raise HTTPException(status_code=404, detail=f"Advisor {fa_id} not found")

        advisor.preferences = preferences
        session.commit()
        session.refresh(advisor)

        return AdvisorResponse(
            advisor_id=str(advisor.advisor_id),
            fa_id=advisor.fa_id,
            name=advisor.name,
            email=advisor.email,
            firm_name=advisor.firm_name,
            preferences=advisor.preferences
        )
```

**Integration**: Add to `src/interactive/api/fastapi_server.py`

```python
# Add import
from src.interactive.api.advisors import router as advisors_router

# Add route
app.include_router(advisors_router)
```

### Frontend: Display Advisor Name

**File**: `ui/app/chat/page.tsx`

Add state and fetch logic:

```typescript
const [advisorName, setAdvisorName] = useState<string | null>(null);

useEffect(() => {
  // Fetch advisor info on mount
  const fetchAdvisor = async () => {
    try {
      const response = await fetch(`http://localhost:8000/api/advisors/FA-001`);
      if (response.ok) {
        const data = await response.json();
        setAdvisorName(data.name);
      }
    } catch (error) {
      console.error('Failed to fetch advisor:', error);
    }
  };
  fetchAdvisor();
}, []);
```

Update header UI (around line 200-250):

```typescript
<header className="flex items-center justify-between p-4 border-b">
  <div>
    <h1 className="text-2xl font-bold">FA AI Assistant</h1>
    {advisorName && (
      <p className="text-sm text-muted-foreground">Welcome, {advisorName}</p>
    )}
  </div>
  {/* ... rest of header ... */}
</header>
```

### Seed Sample Data

**File**: `scripts/seed_advisors.py` (NEW FILE)

```python
#!/usr/bin/env python3
"""Seed sample advisor data"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.shared.database.connection import db_manager
from src.shared.models.database import Advisor

def seed():
    with db_manager.get_session() as session:
        # Create sample advisors
        advisors = [
            Advisor(
                fa_id="FA-001",
                name="Sarah Thompson",
                email="sarah.thompson@example.com",
                firm_name="Thompson Wealth Management",
                preferences={"watchlist": ["AAPL", "MSFT", "GOOGL"]}
            ),
            Advisor(
                fa_id="FA-002",
                name="Michael Chen",
                email="michael.chen@example.com",
                firm_name="Chen Financial Advisors",
                preferences={"watchlist": ["TSLA", "NVDA"]}
            )
        ]

        for advisor in advisors:
            existing = session.query(Advisor).filter(Advisor.fa_id == advisor.fa_id).first()
            if not existing:
                session.add(advisor)
                print(f"✅ Created advisor: {advisor.name} ({advisor.fa_id})")
            else:
                print(f"⚠️  Advisor {advisor.fa_id} already exists")

        session.commit()
        print("✅ Seeding complete!")

if __name__ == "__main__":
    seed()
```

Run: `python3 scripts/seed_advisors.py`

---

## Feature 1: Client Management (PRIORITY 2)

**Goal**: Enable advisors to manage clients and their holdings
**Time Estimate**: 6-8 hours
**Value**: Core workflow enabler

### Backend: Client API

**File**: `src/interactive/api/clients.py` (NEW FILE)

```python
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
from src.shared.database.connection import db_manager
from src.shared.models.database import Client, ClientHolding, Stock, Advisor

router = APIRouter(prefix="/api/clients", tags=["clients"])

class HoldingResponse(BaseModel):
    holding_id: str
    ticker: str
    shares: float
    cost_basis: Optional[float]
    purchase_date: Optional[datetime]

class ClientResponse(BaseModel):
    client_id: str
    account_id: str
    name: str
    email: Optional[str]
    phone: Optional[str]
    last_meeting_date: Optional[datetime]
    next_meeting_date: Optional[datetime]
    holdings: List[HoldingResponse]

class CreateClientRequest(BaseModel):
    fa_id: str
    account_id: str
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    next_meeting_date: Optional[datetime] = None

class AddHoldingRequest(BaseModel):
    ticker: str
    shares: float
    cost_basis: Optional[float] = None
    purchase_date: Optional[datetime] = None

@router.get("/{fa_id}", response_model=List[ClientResponse])
def get_clients_by_advisor(fa_id: str):
    """Get all clients for an advisor"""
    with db_manager.get_session() as session:
        advisor = session.query(Advisor).filter(Advisor.fa_id == fa_id).first()
        if not advisor:
            raise HTTPException(status_code=404, detail=f"Advisor {fa_id} not found")

        clients = session.query(Client).filter(Client.advisor_id == advisor.advisor_id).all()

        result = []
        for client in clients:
            holdings = session.query(ClientHolding).filter(
                ClientHolding.client_id == client.client_id
            ).all()

            result.append(ClientResponse(
                client_id=str(client.client_id),
                account_id=client.account_id,
                name=client.name,
                email=client.email,
                phone=client.phone,
                last_meeting_date=client.last_meeting_date,
                next_meeting_date=client.next_meeting_date,
                holdings=[HoldingResponse(
                    holding_id=str(h.holding_id),
                    ticker=h.ticker,
                    shares=h.shares,
                    cost_basis=h.cost_basis,
                    purchase_date=h.purchase_date
                ) for h in holdings]
            ))

        return result

@router.post("/", response_model=ClientResponse)
def create_client(request: CreateClientRequest):
    """Create new client"""
    with db_manager.get_session() as session:
        advisor = session.query(Advisor).filter(Advisor.fa_id == request.fa_id).first()
        if not advisor:
            raise HTTPException(status_code=404, detail=f"Advisor {request.fa_id} not found")

        client = Client(
            advisor_id=advisor.advisor_id,
            account_id=request.account_id,
            name=request.name,
            email=request.email,
            phone=request.phone,
            next_meeting_date=request.next_meeting_date
        )
        session.add(client)
        session.commit()
        session.refresh(client)

        return ClientResponse(
            client_id=str(client.client_id),
            account_id=client.account_id,
            name=client.name,
            email=client.email,
            phone=client.phone,
            last_meeting_date=client.last_meeting_date,
            next_meeting_date=client.next_meeting_date,
            holdings=[]
        )

@router.post("/{client_id}/holdings")
def add_holding(client_id: str, request: AddHoldingRequest):
    """Add holding to client portfolio"""
    with db_manager.get_session() as session:
        client = session.query(Client).filter(Client.client_id == client_id).first()
        if not client:
            raise HTTPException(status_code=404, detail="Client not found")

        # Get or create stock
        stock = session.query(Stock).filter(Stock.ticker == request.ticker).first()
        if not stock:
            raise HTTPException(status_code=400, detail=f"Stock {request.ticker} not found in database")

        holding = ClientHolding(
            client_id=client.client_id,
            stock_id=stock.stock_id,
            ticker=request.ticker,
            shares=request.shares,
            cost_basis=request.cost_basis,
            purchase_date=request.purchase_date
        )
        session.add(holding)
        session.commit()

        return {"message": "Holding added successfully"}

@router.get("/search", response_model=List[ClientResponse])
def search_clients(
    fa_id: str = Query(...),
    name: Optional[str] = Query(None),
    ticker: Optional[str] = Query(None)
):
    """Search clients by name or by ticker ownership"""
    with db_manager.get_session() as session:
        advisor = session.query(Advisor).filter(Advisor.fa_id == fa_id).first()
        if not advisor:
            raise HTTPException(status_code=404, detail=f"Advisor {fa_id} not found")

        query = session.query(Client).filter(Client.advisor_id == advisor.advisor_id)

        if name:
            query = query.filter(Client.name.ilike(f"%{name}%"))

        if ticker:
            # Join with holdings to filter by ticker
            query = query.join(ClientHolding).filter(ClientHolding.ticker == ticker)

        clients = query.all()

        # ... (same response building as get_clients_by_advisor)
```

### Frontend: Client Management UI

**File**: `ui/components/ClientManager.tsx` (NEW FILE)

```typescript
'use client'

import { useState, useEffect } from 'react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card'

interface Client {
  client_id: string
  account_id: string
  name: string
  email?: string
  holdings: Holding[]
}

interface Holding {
  ticker: string
  shares: number
  cost_basis?: number
}

export function ClientManager({ faId }: { faId: string }) {
  const [clients, setClients] = useState<Client[]>([])
  const [searchQuery, setSearchQuery] = useState('')
  const [searchType, setSearchType] = useState<'name' | 'ticker'>('name')

  const fetchClients = async () => {
    const response = await fetch(`http://localhost:8000/api/clients/${faId}`)
    if (response.ok) {
      const data = await response.json()
      setClients(data)
    }
  }

  const searchClients = async () => {
    const params = new URLSearchParams({ fa_id: faId })
    if (searchType === 'name') {
      params.append('name', searchQuery)
    } else {
      params.append('ticker', searchQuery.toUpperCase())
    }

    const response = await fetch(`http://localhost:8000/api/clients/search?${params}`)
    if (response.ok) {
      const data = await response.json()
      setClients(data)
    }
  }

  useEffect(() => {
    fetchClients()
  }, [faId])

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <CardTitle>Client Search</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex gap-2">
            <Input
              placeholder={searchType === 'name' ? 'Search by name...' : 'Search by ticker...'}
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
            <Button onClick={searchClients}>Search</Button>
            <Button
              variant="outline"
              onClick={() => setSearchType(searchType === 'name' ? 'ticker' : 'name')}
            >
              {searchType === 'name' ? 'By Name' : 'By Ticker'}
            </Button>
          </div>
        </CardContent>
      </Card>

      <div className="grid gap-4">
        {clients.map((client) => (
          <Card key={client.client_id}>
            <CardHeader>
              <CardTitle>{client.name}</CardTitle>
              <p className="text-sm text-muted-foreground">{client.account_id}</p>
            </CardHeader>
            <CardContent>
              <h4 className="font-semibold mb-2">Holdings:</h4>
              <ul className="space-y-1">
                {client.holdings.map((holding, idx) => (
                  <li key={idx} className="text-sm">
                    {holding.ticker}: {holding.shares} shares
                    {holding.cost_basis && ` @ $${holding.cost_basis}`}
                  </li>
                ))}
              </ul>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  )
}
```

**Integration**: Add to sidebar or new route `/clients`

---

## Feature 3: Quick Stock Lookup (PRIORITY 3)

**Goal**: Fast ticker search with instant summary access
**Time Estimate**: 3-4 hours

### Backend: Quick Lookup API

**File**: `src/interactive/api/quick_lookup.py` (NEW FILE)

```python
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from src.shared.database.connection import db_manager
from src.shared.models.database import StockSummary, Stock

router = APIRouter(prefix="/api/quick-lookup", tags=["quick-lookup"])

class QuickSummaryResponse(BaseModel):
    ticker: str
    company_name: str
    hook_text: Optional[str]
    medium_text: Optional[str]
    expanded_text: Optional[str]
    generation_date: str

@router.get("/{ticker}", response_model=QuickSummaryResponse)
def quick_lookup(ticker: str):
    """Get latest summary for ticker"""
    with db_manager.get_session() as session:
        # Get stock info
        stock = session.query(Stock).filter(Stock.ticker == ticker.upper()).first()
        if not stock:
            raise HTTPException(status_code=404, detail=f"Stock {ticker} not found")

        # Get latest summary
        summary = session.query(StockSummary).filter(
            StockSummary.ticker == ticker.upper()
        ).order_by(StockSummary.generation_date.desc()).first()

        if not summary:
            raise HTTPException(status_code=404, detail=f"No summary found for {ticker}")

        return QuickSummaryResponse(
            ticker=stock.ticker,
            company_name=stock.company_name,
            hook_text=summary.hook_text,
            medium_text=summary.medium_text,
            expanded_text=summary.expanded_text,
            generation_date=summary.generation_date.isoformat()
        )
```

### Frontend: Ticker Search Component

**File**: `ui/components/TickerSearch.tsx` (NEW FILE)

Add to header with autocomplete and instant preview.

---

## Feature 4: Delta Summaries (PRIORITY 4)

**Goal**: Show what changed since last summary
**Time Estimate**: 4-5 hours

### Backend: Delta Comparison

**File**: `src/interactive/api/delta.py` (NEW FILE)

```python
from fastapi import APIRouter
from datetime import datetime, timedelta

router = APIRouter(prefix="/api/delta", tags=["delta"])

@router.get("/{ticker}")
def get_delta(ticker: str, days_ago: int = 7):
    """Compare current summary vs N days ago"""
    with db_manager.get_session() as session:
        # Get latest summary
        latest = session.query(StockSummary).filter(
            StockSummary.ticker == ticker.upper()
        ).order_by(StockSummary.generation_date.desc()).first()

        # Get summary from N days ago
        target_date = datetime.now() - timedelta(days=days_ago)
        previous = session.query(StockSummary).filter(
            StockSummary.ticker == ticker.upper(),
            StockSummary.generation_date <= target_date
        ).order_by(StockSummary.generation_date.desc()).first()

        if not latest or not previous:
            return {"message": "Insufficient data for comparison"}

        # TODO: Use LLM to generate delta summary
        # For MVP, return both summaries
        return {
            "ticker": ticker,
            "latest_date": latest.generation_date,
            "previous_date": previous.generation_date,
            "latest_summary": latest.medium_text,
            "previous_summary": previous.medium_text,
            "changes": "TODO: LLM-generated change highlights"
        }
```

---

## TESTING CHECKLIST

### Feature 2: Advisor Name
- [ ] Create advisor via POST /api/advisors
- [ ] Fetch advisor via GET /api/advisors/{fa_id}
- [ ] Verify name displays in UI header
- [ ] Test with multiple advisors (FA-001, FA-002)

### Feature 1: Client Management
- [ ] Create client for advisor
- [ ] Add holdings to client
- [ ] Search by client name
- [ ] Search by ticker ("Who owns AAPL?")
- [ ] Verify UI displays all clients correctly

### Feature 3: Quick Lookup
- [ ] Search for AAPL, MSFT, GOOGL
- [ ] Verify instant summary display
- [ ] Test ticker autocomplete

### Feature 4: Delta Summaries
- [ ] Generate delta for stock with multiple summaries
- [ ] Verify changes are highlighted
- [ ] Test "What's new?" query type

---

## DEPLOYMENT NOTES

1. **Database Migration**: Already complete (tables created)
2. **Backend Dependencies**: No new packages needed
3. **Frontend Dependencies**: May need date-picker library for meeting dates
4. **Environment Variables**: None required for MVP

---

## PRIORITY ORDER FOR IMPLEMENTATION

1. **Feature 2 (Advisor Name)** - 2-3 hours - Immediate value
2. **Feature 1 (Client Management)** - 6-8 hours - Core workflow
3. **Feature 3 (Quick Lookup)** - 3-4 hours - Efficiency boost
4. **Feature 4 (Delta Summaries)** - 4-5 hours - Differentiator

**Total**: 15-20 hours

---

## FILES TO CREATE

**Backend:**
- `src/interactive/api/advisors.py`
- `src/interactive/api/clients.py`
- `src/interactive/api/quick_lookup.py`
- `src/interactive/api/delta.py`
- `scripts/seed_advisors.py`
- `scripts/seed_clients.py` (optional)

**Frontend:**
- `ui/components/ClientManager.tsx`
- `ui/components/TickerSearch.tsx`
- `ui/components/DeltaSummary.tsx`
- `ui/app/clients/page.tsx` (optional dedicated page)

**Documentation:**
- Update USER_GUIDE.md with new features
- Add API documentation

---

## NEXT STEPS

1. Start with Feature 2 (quickest win)
2. Test with `curl` before building UI
3. Seed sample data for demo
4. Build UI components incrementally
5. Test end-to-end workflows
6. Gather advisor feedback before expanding

Good luck with implementation! 🚀
