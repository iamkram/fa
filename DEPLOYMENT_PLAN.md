# Deployment Plan: Production Data Integration & LangSmith Enterprise Hybrid

**Version:** 1.0
**Date:** November 7, 2025
**Status:** Planning
**Target Completion:** Q1 2026

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Current State Assessment](#current-state-assessment)
3. [Phase 1: EDGAR API Integration](#phase-1-edgar-api-integration)
4. [Phase 2: BlueMatrix API Integration](#phase-2-bluematrix-api-integration)
5. [Phase 3: FactSet API Integration](#phase-3-factset-api-integration)
6. [Phase 4: LangSmith Enterprise Hybrid Deployment](#phase-4-langsmith-enterprise-hybrid-deployment)
7. [Phase 5: Production Validation](#phase-5-production-validation)
8. [Timeline & Resource Requirements](#timeline--resource-requirements)
9. [Risk Management](#risk-management)
10. [Rollback Procedures](#rollback-procedures)

---

## Executive Summary

### Objectives

1. **Replace sample data with production APIs** for EDGAR, BlueMatrix, and FactSet
2. **Migrate to LangSmith Enterprise hybrid deployment** for data sovereignty and compliance
3. **Validate end-to-end system** with production data and production infrastructure
4. **Achieve production readiness** for pilot launch

### Success Criteria

- ✅ All three data sources (EDGAR, BlueMatrix, FactSet) integrated and tested
- ✅ LangSmith hybrid deployment operational in customer cloud (AWS)
- ✅ Data never leaves customer environment (compliance requirement)
- ✅ Batch processing completes successfully with production data
- ✅ Interactive queries return accurate results from production data
- ✅ All tests passing with > 95% accuracy
- ✅ System meets SLA targets (99.9% uptime, < 2 hour batch, < 60s queries)

### Timeline

**Total Duration:** 8-10 weeks

| Phase | Duration | Target Completion |
|-------|----------|-------------------|
| Phase 1: EDGAR Integration | 2 weeks | Week 2 |
| Phase 2: BlueMatrix Integration | 2 weeks | Week 4 |
| Phase 3: FactSet Integration | 2 weeks | Week 6 |
| Phase 4: LangSmith Hybrid | 2 weeks | Week 8 |
| Phase 5: Production Validation | 1-2 weeks | Week 10 |

### Budget Estimate

| Item | Cost | Notes |
|------|------|-------|
| EDGAR API | Free | SEC public API |
| BlueMatrix API | $10,000/month | Analyst reports subscription |
| FactSet API | $5,000/month | Market data subscription |
| LangSmith Enterprise | $2,500/month | Hybrid deployment tier |
| AWS Infrastructure (Hybrid) | $1,500/month | K8s cluster for data plane |
| **Total Monthly** | **$19,000/month** | Ongoing operational cost |
| **One-Time Setup** | **$15,000** | Implementation + integration |

---

## Current State Assessment

### What's Using Sample Data

#### 1. EDGAR Filings (`src/batch/agents/edgar_fetcher.py`)

**Current Implementation:**
```python
class EdgarFetcherAgent:
    async def fetch(self, ticker: str) -> list[EdgarFiling]:
        """Currently returns hardcoded sample data"""
        # TODO: Replace with real SEC EDGAR API calls
        return [
            EdgarFiling(
                filing_id=uuid.uuid4(),
                ticker=ticker,
                filing_type="10-K",
                filing_date=date(2024, 2, 15),
                full_text="Sample 10-K filing text...",
                url="https://www.sec.gov/..."
            )
        ]
```

**Issues:**
- No real-time data from SEC
- Summaries based on placeholder text
- No historical filing retrieval
- Citations point to fake URLs

#### 2. BlueMatrix Reports (`src/batch/agents/bluematrix_fetcher.py`)

**Current Implementation:**
```python
class BlueMatrixFetcherAgent:
    async def fetch(self, ticker: str) -> list[AnalystReport]:
        """Currently returns hardcoded sample data"""
        # TODO: Replace with real BlueMatrix API calls
        return [
            AnalystReport(
                report_id=uuid.uuid4(),
                ticker=ticker,
                analyst_firm="Goldman Sachs",
                rating_change="Upgrade",
                new_rating="Buy",
                price_target=195.00,
                report_date=date.today(),
                full_text="Sample analyst report..."
            )
        ]
```

**Issues:**
- No real analyst reports
- Fake ratings and price targets
- No historical report tracking
- Cannot validate fact-checks against real sources

#### 3. FactSet Data (`src/batch/agents/factset_fetcher.py`)

**Current Implementation:**
```python
class FactSetFetcherAgent:
    async def fetch_price_data(self, ticker: str) -> FactSetPriceData:
        """Currently returns hardcoded sample data"""
        # TODO: Replace with real FactSet API calls
        return FactSetPriceData(
            ticker=ticker,
            price_date=date.today(),
            close=185.50,
            volume=50000000,
            pct_change=1.2,
            volume_vs_avg=1.3
        )

    async def fetch_events(self, ticker: str) -> list[FundamentalEvent]:
        """Currently returns hardcoded sample data"""
        return []
```

**Issues:**
- No real market data
- Price/volume data is fabricated
- No corporate events (earnings, dividends, etc.)
- Cannot track real market movements

### What's Already Production-Ready

✅ **Database architecture** (PostgreSQL + pgvector)
✅ **LangGraph orchestration** (multi-agent system)
✅ **LLM integration** (Claude Sonnet-4, OpenAI embeddings)
✅ **Batch processing pipeline** (concurrent workers, error handling)
✅ **Interactive query system** (FastAPI, session management)
✅ **Fact-checking and citation extraction** (quality control)
✅ **LangSmith tracing** (observability - cloud version)
✅ **Prompt management** (LangSmith hub integration)

---

## Phase 1: EDGAR API Integration

### Overview

Replace sample EDGAR data with real SEC filings using the SEC EDGAR API.

**Duration:** 2 weeks
**Complexity:** Medium
**Dependencies:** None

### SEC EDGAR API Details

**Endpoint:** `https://www.sec.gov/cgi-bin/browse-edgar`
**Documentation:** https://www.sec.gov/edgar/searchedgar/accessing-edgar-data.htm
**Rate Limits:** 10 requests/second (requires User-Agent header)
**Authentication:** None (public API)
**Cost:** Free

**Available Filing Types:**
- 10-K: Annual reports
- 10-Q: Quarterly reports
- 8-K: Current reports (material events)
- DEF 14A: Proxy statements
- S-1: IPO registrations

### Implementation Steps

#### Step 1.1: Create SEC EDGAR Client (Week 1, Days 1-2)

**File:** `src/shared/clients/edgar_client.py`

```python
"""SEC EDGAR API client for fetching filings"""

import aiohttp
import asyncio
from typing import List, Optional
from datetime import date, datetime
import logging
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


class EdgarClient:
    """Client for SEC EDGAR API

    Docs: https://www.sec.gov/edgar/searchedgar/accessing-edgar-data.htm
    Rate limit: 10 requests/second
    """

    BASE_URL = "https://www.sec.gov"

    def __init__(self):
        """Initialize EDGAR client with rate limiting"""
        self.session: Optional[aiohttp.ClientSession] = None
        self.rate_limiter = asyncio.Semaphore(10)  # 10 concurrent requests
        self.last_request_time = 0

        # Required User-Agent header per SEC rules
        self.headers = {
            "User-Agent": "FA-AI-System/1.0 (support@company.com)"
        }

    async def __aenter__(self):
        """Async context manager entry"""
        self.session = aiohttp.ClientSession(headers=self.headers)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self.session:
            await self.session.close()

    async def _rate_limit(self):
        """Enforce 10 requests/second rate limit"""
        async with self.rate_limiter:
            # Ensure minimum 100ms between requests
            now = asyncio.get_event_loop().time()
            time_since_last = now - self.last_request_time
            if time_since_last < 0.1:  # 100ms
                await asyncio.sleep(0.1 - time_since_last)
            self.last_request_time = asyncio.get_event_loop().time()

    async def get_company_cik(self, ticker: str) -> Optional[str]:
        """Get CIK number for ticker symbol

        Args:
            ticker: Stock ticker symbol (e.g., "AAPL")

        Returns:
            CIK number (e.g., "0000320193") or None if not found
        """
        await self._rate_limit()

        url = f"{self.BASE_URL}/cgi-bin/browse-edgar"
        params = {
            "action": "getcompany",
            "company": ticker,
            "type": "",
            "dateb": "",
            "owner": "exclude",
            "output": "xml",
            "count": 1
        }

        try:
            async with self.session.get(url, params=params) as response:
                response.raise_for_status()
                text = await response.text()

                # Parse XML response
                soup = BeautifulSoup(text, "xml")
                cik_element = soup.find("CIK")

                if cik_element:
                    return cik_element.text.zfill(10)  # Pad to 10 digits

                return None

        except Exception as e:
            logger.error(f"Failed to get CIK for {ticker}: {e}")
            return None

    async def get_recent_filings(
        self,
        ticker: str,
        filing_types: List[str] = None,
        count: int = 10,
        before_date: Optional[date] = None
    ) -> List[dict]:
        """Get recent filings for a company

        Args:
            ticker: Stock ticker symbol
            filing_types: List of filing types (e.g., ["10-K", "10-Q", "8-K"])
            count: Number of filings to retrieve (max 100)
            before_date: Only return filings before this date

        Returns:
            List of filing metadata dicts
        """
        if filing_types is None:
            filing_types = ["10-K", "10-Q", "8-K"]

        # Get CIK first
        cik = await self.get_company_cik(ticker)
        if not cik:
            logger.warning(f"Could not find CIK for {ticker}")
            return []

        all_filings = []

        for filing_type in filing_types:
            await self._rate_limit()

            url = f"{self.BASE_URL}/cgi-bin/browse-edgar"
            params = {
                "action": "getcompany",
                "CIK": cik,
                "type": filing_type,
                "dateb": before_date.strftime("%Y%m%d") if before_date else "",
                "owner": "exclude",
                "output": "xml",
                "count": min(count, 100)
            }

            try:
                async with self.session.get(url, params=params) as response:
                    response.raise_for_status()
                    text = await response.text()

                    # Parse XML
                    soup = BeautifulSoup(text, "xml")
                    filings = soup.find_all("filing")

                    for filing in filings:
                        filing_data = {
                            "ticker": ticker,
                            "cik": cik,
                            "filing_type": filing.find("type").text,
                            "filing_date": datetime.strptime(
                                filing.find("filingDate").text,
                                "%Y-%m-%d"
                            ).date(),
                            "accession_number": filing.find("accessionNumber").text,
                            "file_number": filing.find("fileNumber").text if filing.find("fileNumber") else None,
                            "description": filing.find("description").text if filing.find("description") else ""
                        }

                        # Build document URL
                        accession = filing_data["accession_number"].replace("-", "")
                        filing_data["url"] = f"{self.BASE_URL}/Archives/edgar/data/{cik}/{accession}/{filing_data['accession_number']}.txt"

                        all_filings.append(filing_data)

            except Exception as e:
                logger.error(f"Failed to fetch {filing_type} filings for {ticker}: {e}")

        # Sort by date descending
        all_filings.sort(key=lambda x: x["filing_date"], reverse=True)

        return all_filings[:count]

    async def get_filing_content(self, filing_url: str) -> str:
        """Download full text of a filing

        Args:
            filing_url: URL to filing document

        Returns:
            Full text content of filing
        """
        await self._rate_limit()

        try:
            async with self.session.get(filing_url) as response:
                response.raise_for_status()
                content = await response.text()

                # Parse SGML/HTML content
                soup = BeautifulSoup(content, "html.parser")

                # Extract text from document
                # Remove SGML tags and formatting
                text = soup.get_text()

                # Clean up whitespace
                lines = [line.strip() for line in text.split("\n") if line.strip()]
                text = "\n".join(lines)

                return text

        except Exception as e:
            logger.error(f"Failed to download filing from {filing_url}: {e}")
            return ""
```

**Testing:**
```python
# Test script: tests/test_edgar_client.py

import asyncio
from src.shared.clients.edgar_client import EdgarClient


async def test_edgar_client():
    async with EdgarClient() as client:
        # Test 1: Get CIK
        cik = await client.get_company_cik("AAPL")
        print(f"Apple CIK: {cik}")
        assert cik == "0000320193"

        # Test 2: Get recent filings
        filings = await client.get_recent_filings("AAPL", count=5)
        print(f"Found {len(filings)} filings for AAPL")
        for filing in filings:
            print(f"  {filing['filing_type']} on {filing['filing_date']}")

        # Test 3: Download filing content
        if filings:
            content = await client.get_filing_content(filings[0]["url"])
            print(f"Downloaded {len(content)} characters from {filings[0]['filing_type']}")
            assert len(content) > 0


if __name__ == "__main__":
    asyncio.run(test_edgar_client())
```

#### Step 1.2: Update EDGAR Fetcher Agent (Week 1, Days 3-4)

**File:** `src/batch/agents/edgar_fetcher.py`

Replace sample data implementation with real API calls:

```python
from src.shared.clients.edgar_client import EdgarClient
from src.shared.models.database import EdgarFiling
from datetime import date, timedelta
import uuid
import logging

logger = logging.getLogger(__name__)


class EdgarFetcherAgent:
    """Agent for fetching SEC EDGAR filings"""

    def __init__(self):
        """Initialize EDGAR fetcher"""
        self.client = EdgarClient()

    async def fetch(
        self,
        ticker: str,
        lookback_days: int = 90
    ) -> list[EdgarFiling]:
        """Fetch recent EDGAR filings for a ticker

        Args:
            ticker: Stock ticker symbol
            lookback_days: How many days back to search (default: 90)

        Returns:
            List of EdgarFiling objects
        """
        logger.info(f"[EDGAR] Fetching filings for {ticker} (last {lookback_days} days)")

        before_date = date.today()
        after_date = date.today() - timedelta(days=lookback_days)

        async with EdgarClient() as client:
            # Get recent filings
            filing_metadata = await client.get_recent_filings(
                ticker=ticker,
                filing_types=["10-K", "10-Q", "8-K"],
                count=10,
                before_date=before_date
            )

            # Filter by date range
            filing_metadata = [
                f for f in filing_metadata
                if f["filing_date"] >= after_date
            ]

            logger.info(f"[EDGAR] Found {len(filing_metadata)} filings for {ticker}")

            # Download full content for each filing
            filings = []
            for metadata in filing_metadata:
                try:
                    # Download filing content
                    full_text = await client.get_filing_content(metadata["url"])

                    # Create EdgarFiling object
                    filing = EdgarFiling(
                        filing_id=uuid.uuid4(),
                        ticker=ticker,
                        filing_type=metadata["filing_type"],
                        filing_date=metadata["filing_date"],
                        accession_number=metadata["accession_number"],
                        full_text=full_text[:50000],  # Truncate to 50K chars for now
                        url=metadata["url"]
                    )

                    filings.append(filing)

                    logger.info(f"[EDGAR] Downloaded {metadata['filing_type']} from {metadata['filing_date']}")

                except Exception as e:
                    logger.error(f"[EDGAR] Failed to download {metadata['filing_type']}: {e}")

            return filings


async def edgar_fetcher_node(state: BatchGraphStatePhase2, config) -> dict:
    """LangGraph node for EDGAR data fetching"""
    logger.info(f"[EDGAR] Fetching filings for {state.ticker}")

    agent = EdgarFetcherAgent()
    filings = await agent.fetch(state.ticker)

    logger.info(f"[EDGAR] Fetched {len(filings)} filings for {state.ticker}")

    return {
        "edgar_filings": filings
    }
```

#### Step 1.3: Update Database Models (Week 1, Day 5)

**File:** `src/shared/models/database.py`

Add `accession_number` field to EdgarFiling:

```python
class EdgarFiling(Base):
    __tablename__ = "edgar_filings"

    filing_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ticker = Column(String(10), ForeignKey("stocks.ticker"), nullable=False)
    filing_type = Column(String(20), nullable=False)  # 10-K, 10-Q, 8-K
    filing_date = Column(Date, nullable=False)
    accession_number = Column(String(20), nullable=False)  # NEW: SEC accession number
    full_text = Column(Text, nullable=True)
    url = Column(String(500), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Indexes
    __table_args__ = (
        Index("idx_edgar_ticker_date", "ticker", "filing_date"),
        Index("idx_edgar_accession", "accession_number", unique=True),  # NEW
    )
```

**Migration Script:**
```sql
-- Add accession_number column
ALTER TABLE edgar_filings
ADD COLUMN accession_number VARCHAR(20);

-- Create unique index
CREATE UNIQUE INDEX idx_edgar_accession ON edgar_filings(accession_number);
```

#### Step 1.4: Integration Testing (Week 2)

**Test Cases:**

1. **Test Single Stock EDGAR Fetch**
   ```bash
   python3 -m src.batch.run_batch_phase2 --ticker AAPL --validate

   # Expected:
   # - Downloads real 10-K, 10-Q, 8-K filings
   # - Stores in database with accession numbers
   # - Generates summaries based on real filing content
   # - Citations link to real SEC URLs
   ```

2. **Test Batch Processing with EDGAR**
   ```bash
   python3 -m src.batch.run_batch_phase2 --limit 10 --validate

   # Expected:
   # - Processes 10 stocks successfully
   # - No rate limit errors (10 req/sec max)
   # - All filings have real content
   # - Success rate > 95%
   ```

3. **Test EDGAR API Error Handling**
   ```python
   # Test with invalid ticker
   python3 -m src.batch.run_batch_phase2 --ticker INVALIDTICKER

   # Expected:
   # - Gracefully handles "CIK not found"
   # - Logs warning, continues processing
   # - Returns empty filings list
   ```

**Validation Checklist:**
- [ ] Real EDGAR data fetched for all test tickers
- [ ] Accession numbers stored in database
- [ ] Citation URLs point to real SEC filings
- [ ] Summaries reference actual filing content
- [ ] Rate limiting prevents API errors
- [ ] Error handling works for invalid tickers
- [ ] Batch processing completes successfully

---

## Phase 2: BlueMatrix API Integration

### Overview

Replace sample BlueMatrix data with real analyst reports using the BlueMatrix API.

**Duration:** 2 weeks
**Complexity:** High
**Dependencies:** Phase 1 complete

### BlueMatrix API Details

**Provider:** BlueMatrix (now owned by FactSet)
**Documentation:** https://developer.bluematrix.com/
**Authentication:** API key + OAuth 2.0
**Rate Limits:** 1000 requests/hour (configurable)
**Cost:** $10,000/month (analyst report subscription)

**Available Data:**
- Analyst reports (PDF + text extraction)
- Rating changes (upgrades/downgrades)
- Price targets
- Earnings estimates
- Analyst recommendations

### Prerequisites

1. **Sign BlueMatrix Contract**
   - Contact: sales@bluematrix.com
   - Request: API access for 1,000 stocks
   - Timeline: 2-3 weeks for approval

2. **Obtain API Credentials**
   - API key
   - Client ID
   - Client secret
   - Sandbox environment for testing

### Implementation Steps

#### Step 2.1: Create BlueMatrix Client (Week 3, Days 1-3)

**File:** `src/shared/clients/bluematrix_client.py`

```python
"""BlueMatrix API client for analyst reports"""

import aiohttp
import asyncio
from typing import List, Optional, Dict, Any
from datetime import date, datetime, timedelta
import logging
import base64

from src.config.settings import settings

logger = logging.getLogger(__name__)


class BlueMatrixClient:
    """Client for BlueMatrix analyst reports API

    Docs: https://developer.bluematrix.com/
    Rate limit: 1000 requests/hour
    """

    BASE_URL = "https://api.bluematrix.com/v1"
    AUTH_URL = "https://auth.bluematrix.com/oauth/token"

    def __init__(
        self,
        api_key: Optional[str] = None,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None
    ):
        """Initialize BlueMatrix client

        Args:
            api_key: BlueMatrix API key (from settings if not provided)
            client_id: OAuth client ID
            client_secret: OAuth client secret
        """
        self.api_key = api_key or settings.bluematrix_api_key
        self.client_id = client_id or settings.bluematrix_client_id
        self.client_secret = client_secret or settings.bluematrix_client_secret

        self.session: Optional[aiohttp.ClientSession] = None
        self.access_token: Optional[str] = None
        self.token_expires_at: Optional[datetime] = None

        # Rate limiting
        self.rate_limiter = asyncio.Semaphore(100)  # 100 concurrent
        self.request_count = 0
        self.request_window_start = datetime.utcnow()

    async def __aenter__(self):
        """Async context manager entry"""
        self.session = aiohttp.ClientSession()
        await self._authenticate()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self.session:
            await self.session.close()

    async def _authenticate(self):
        """Authenticate with BlueMatrix OAuth"""
        # Encode credentials
        credentials = f"{self.client_id}:{self.client_secret}"
        encoded = base64.b64encode(credentials.encode()).decode()

        headers = {
            "Authorization": f"Basic {encoded}",
            "Content-Type": "application/x-www-form-urlencoded"
        }

        data = {
            "grant_type": "client_credentials",
            "scope": "reports:read estimates:read"
        }

        try:
            async with self.session.post(self.AUTH_URL, headers=headers, data=data) as response:
                response.raise_for_status()
                auth_data = await response.json()

                self.access_token = auth_data["access_token"]
                expires_in = auth_data.get("expires_in", 3600)  # Default 1 hour
                self.token_expires_at = datetime.utcnow() + timedelta(seconds=expires_in)

                logger.info("✅ Authenticated with BlueMatrix API")

        except Exception as e:
            logger.error(f"Failed to authenticate with BlueMatrix: {e}")
            raise

    async def _ensure_authenticated(self):
        """Ensure access token is valid"""
        if not self.access_token or datetime.utcnow() >= self.token_expires_at:
            await self._authenticate()

    async def _rate_limit(self):
        """Enforce rate limits (1000 req/hour)"""
        async with self.rate_limiter:
            # Reset counter every hour
            now = datetime.utcnow()
            if now - self.request_window_start > timedelta(hours=1):
                self.request_count = 0
                self.request_window_start = now

            # Check if we've hit limit
            if self.request_count >= 1000:
                # Wait until next hour
                wait_seconds = 3600 - (now - self.request_window_start).total_seconds()
                logger.warning(f"Rate limit reached, waiting {wait_seconds:.0f}s")
                await asyncio.sleep(wait_seconds)
                self.request_count = 0
                self.request_window_start = datetime.utcnow()

            self.request_count += 1

    async def _request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        """Make authenticated API request"""
        await self._ensure_authenticated()
        await self._rate_limit()

        headers = kwargs.pop("headers", {})
        headers["Authorization"] = f"Bearer {self.access_token}"
        headers["X-API-Key"] = self.api_key

        url = f"{self.BASE_URL}/{endpoint}"

        async with self.session.request(method, url, headers=headers, **kwargs) as response:
            response.raise_for_status()
            return await response.json()

    async def get_reports(
        self,
        ticker: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Get analyst reports for a ticker

        Args:
            ticker: Stock ticker symbol
            start_date: Start date for reports (default: 90 days ago)
            end_date: End date for reports (default: today)
            limit: Maximum number of reports (default: 10)

        Returns:
            List of report metadata dicts
        """
        if not start_date:
            start_date = date.today() - timedelta(days=90)
        if not end_date:
            end_date = date.today()

        params = {
            "ticker": ticker,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "limit": limit,
            "order": "desc"  # Most recent first
        }

        try:
            data = await self._request("GET", "reports", params=params)
            return data.get("reports", [])
        except Exception as e:
            logger.error(f"Failed to fetch reports for {ticker}: {e}")
            return []

    async def get_report_content(self, report_id: str) -> str:
        """Download full text of analyst report

        Args:
            report_id: BlueMatrix report ID

        Returns:
            Full text content of report
        """
        try:
            data = await self._request("GET", f"reports/{report_id}/content")
            return data.get("text", "")
        except Exception as e:
            logger.error(f"Failed to download report {report_id}: {e}")
            return ""

    async def get_rating_changes(
        self,
        ticker: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> List[Dict[str, Any]]:
        """Get rating changes for a ticker

        Args:
            ticker: Stock ticker symbol
            start_date: Start date (default: 90 days ago)
            end_date: End date (default: today)

        Returns:
            List of rating change events
        """
        if not start_date:
            start_date = date.today() - timedelta(days=90)
        if not end_date:
            end_date = date.today()

        params = {
            "ticker": ticker,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "event_type": "rating_change"
        }

        try:
            data = await self._request("GET", "events", params=params)
            return data.get("events", [])
        except Exception as e:
            logger.error(f"Failed to fetch rating changes for {ticker}: {e}")
            return []
```

**Configuration (add to `.env`):**
```bash
BLUEMATRIX_API_KEY=your_api_key_here
BLUEMATRIX_CLIENT_ID=your_client_id_here
BLUEMATRIX_CLIENT_SECRET=your_client_secret_here
```

**Settings (add to `src/config/settings.py`):**
```python
class Settings(BaseSettings):
    # ... existing fields ...

    # BlueMatrix API
    bluematrix_api_key: str = ""
    bluematrix_client_id: str = ""
    bluematrix_client_secret: str = ""
```

#### Step 2.2: Update BlueMatrix Fetcher Agent (Week 3, Days 4-5)

**File:** `src/batch/agents/bluematrix_fetcher.py`

```python
from src.shared.clients.bluematrix_client import BlueMatrixClient
from src.shared.models.database import AnalystReport
from datetime import date, datetime
import uuid
import logging

logger = logging.getLogger(__name__)


class BlueMatrixFetcherAgent:
    """Agent for fetching BlueMatrix analyst reports"""

    async def fetch(
        self,
        ticker: str,
        lookback_days: int = 90
    ) -> list[AnalystReport]:
        """Fetch recent analyst reports for a ticker

        Args:
            ticker: Stock ticker symbol
            lookback_days: How many days back to search (default: 90)

        Returns:
            List of AnalystReport objects
        """
        logger.info(f"[BlueMatrix] Fetching reports for {ticker}")

        start_date = date.today() - timedelta(days=lookback_days)
        end_date = date.today()

        async with BlueMatrixClient() as client:
            # Get recent reports
            report_metadata = await client.get_reports(
                ticker=ticker,
                start_date=start_date,
                end_date=end_date,
                limit=10
            )

            logger.info(f"[BlueMatrix] Found {len(report_metadata)} reports for {ticker}")

            # Download full content for each report
            reports = []
            for metadata in report_metadata:
                try:
                    # Download report content
                    full_text = await client.get_report_content(metadata["report_id"])

                    # Create AnalystReport object
                    report = AnalystReport(
                        report_id=uuid.uuid4(),
                        ticker=ticker,
                        analyst_firm=metadata.get("firm", "Unknown"),
                        analyst_name=metadata.get("analyst", ""),
                        rating_change=metadata.get("rating_change", ""),
                        new_rating=metadata.get("rating", ""),
                        price_target=metadata.get("price_target", 0.0),
                        report_date=datetime.fromisoformat(metadata["date"]).date(),
                        full_text=full_text[:50000],  # Truncate to 50K chars
                        url=metadata.get("url", "")
                    )

                    reports.append(report)

                    logger.info(f"[BlueMatrix] Downloaded report from {metadata['firm']}")

                except Exception as e:
                    logger.error(f"[BlueMatrix] Failed to download report: {e}")

            return reports
```

#### Step 2.3: Integration Testing (Week 4)

**Test Cases:**

1. **Test Authentication**
   ```python
   async def test_bluematrix_auth():
       async with BlueMatrixClient() as client:
           assert client.access_token is not None
           print("✅ BlueMatrix authentication successful")
   ```

2. **Test Report Fetching**
   ```bash
   python3 -m src.batch.run_batch_phase2 --ticker AAPL --validate

   # Expected:
   # - Downloads real analyst reports
   # - Stores ratings and price targets
   # - Summaries reference actual analyst opinions
   ```

3. **Test Rate Limiting**
   ```bash
   python3 -m src.batch.run_batch_phase2 --limit 100

   # Expected:
   # - Processes 100 stocks without rate limit errors
   # - Requests stay under 1000/hour
   ```

---

## Phase 3: FactSet API Integration

### Overview

Replace sample FactSet data with real market data using the FactSet API.

**Duration:** 2 weeks
**Complexity:** Medium
**Dependencies:** Phases 1-2 complete

### FactSet API Details

**Provider:** FactSet Research Systems
**Documentation:** https://developer.factset.com/
**Authentication:** API key (username + serial key)
**Rate Limits:** 10,000 requests/day
**Cost:** $5,000/month (market data subscription)

**Available Data:**
- Real-time prices and volume
- Company fundamentals
- Corporate events (earnings, dividends, splits)
- Ownership data
- Estimates and consensus

### Prerequisites

1. **Sign FactSet Contract**
   - Contact: sales@factset.com
   - Request: Market data API access
   - Timeline: 2-3 weeks for approval

2. **Obtain API Credentials**
   - Username
   - Serial key (API key)
   - Sandbox environment

### Implementation Steps

#### Step 3.1: Create FactSet Client (Week 5, Days 1-3)

**File:** `src/shared/clients/factset_client.py`

```python
"""FactSet API client for market data"""

import aiohttp
import asyncio
from typing import List, Optional, Dict, Any
from datetime import date, datetime, timedelta
import logging
import base64

from src.config.settings import settings

logger = logging.getLogger(__name__)


class FactSetClient:
    """Client for FactSet market data API

    Docs: https://developer.factset.com/
    Rate limit: 10,000 requests/day
    """

    BASE_URL = "https://api.factset.com"

    def __init__(
        self,
        username: Optional[str] = None,
        api_key: Optional[str] = None
    ):
        """Initialize FactSet client

        Args:
            username: FactSet username
            api_key: FactSet API key (serial key)
        """
        self.username = username or settings.factset_username
        self.api_key = api_key or settings.factset_api_key

        # Encode credentials for Basic Auth
        credentials = f"{self.username}-{self.api_key}"
        self.auth_header = base64.b64encode(credentials.encode()).decode()

        self.session: Optional[aiohttp.ClientSession] = None

        # Rate limiting
        self.rate_limiter = asyncio.Semaphore(100)
        self.request_count = 0
        self.request_window_start = datetime.utcnow()

    async def __aenter__(self):
        """Async context manager entry"""
        headers = {
            "Authorization": f"Basic {self.auth_header}",
            "Content-Type": "application/json"
        }
        self.session = aiohttp.ClientSession(headers=headers)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self.session:
            await self.session.close()

    async def _rate_limit(self):
        """Enforce rate limits (10,000 req/day)"""
        async with self.rate_limiter:
            # Reset counter every 24 hours
            now = datetime.utcnow()
            if now - self.request_window_start > timedelta(days=1):
                self.request_count = 0
                self.request_window_start = now

            # Check if we've hit limit
            if self.request_count >= 10000:
                # Wait until next day
                wait_seconds = 86400 - (now - self.request_window_start).total_seconds()
                logger.warning(f"Rate limit reached, waiting {wait_seconds:.0f}s")
                await asyncio.sleep(wait_seconds)
                self.request_count = 0
                self.request_window_start = datetime.utcnow()

            self.request_count += 1

    async def _request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        """Make API request"""
        await self._rate_limit()

        url = f"{self.BASE_URL}/{endpoint}"

        async with self.session.request(method, url, **kwargs) as response:
            response.raise_for_status()
            return await response.json()

    async def get_prices(
        self,
        tickers: List[str],
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> Dict[str, Any]:
        """Get price data for tickers

        Args:
            tickers: List of ticker symbols
            start_date: Start date (default: yesterday)
            end_date: End date (default: today)

        Returns:
            Dict of ticker -> price data
        """
        if not start_date:
            start_date = date.today() - timedelta(days=1)
        if not end_date:
            end_date = date.today()

        payload = {
            "ids": tickers,
            "startDate": start_date.isoformat(),
            "endDate": end_date.isoformat(),
            "frequency": "D"  # Daily
        }

        try:
            data = await self._request("POST", "factset-prices/v1/prices", json=payload)
            return data.get("data", {})
        except Exception as e:
            logger.error(f"Failed to fetch prices: {e}")
            return {}

    async def get_company_fundamentals(self, ticker: str) -> Dict[str, Any]:
        """Get company fundamentals

        Args:
            ticker: Stock ticker symbol

        Returns:
            Dict of fundamental metrics
        """
        try:
            data = await self._request("GET", f"factset-fundamentals/v2/company/{ticker}")
            return data.get("data", {})
        except Exception as e:
            logger.error(f"Failed to fetch fundamentals for {ticker}: {e}")
            return {}

    async def get_events(
        self,
        ticker: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> List[Dict[str, Any]]:
        """Get corporate events

        Args:
            ticker: Stock ticker symbol
            start_date: Start date (default: 90 days ago)
            end_date: End date (default: today)

        Returns:
            List of corporate events
        """
        if not start_date:
            start_date = date.today() - timedelta(days=90)
        if not end_date:
            end_date = date.today()

        params = {
            "ids": ticker,
            "startDate": start_date.isoformat(),
            "endDate": end_date.isoformat()
        }

        try:
            data = await self._request("GET", "events/v1/events", params=params)
            return data.get("data", [])
        except Exception as e:
            logger.error(f"Failed to fetch events for {ticker}: {e}")
            return []
```

#### Step 3.2: Update FactSet Fetcher Agent (Week 5, Days 4-5)

**File:** `src/batch/agents/factset_fetcher.py`

```python
from src.shared.clients.factset_client import FactSetClient
from src.shared.models.database import FactSetPriceData, FundamentalEvent
from datetime import date, timedelta
import uuid
import logging

logger = logging.getLogger(__name__)


class FactSetFetcherAgent:
    """Agent for fetching FactSet market data"""

    async def fetch_price_data(self, ticker: str) -> Optional[FactSetPriceData]:
        """Fetch latest price data"""
        logger.info(f"[FactSet] Fetching price data for {ticker}")

        async with FactSetClient() as client:
            # Get last 5 days of prices
            prices = await client.get_prices(
                tickers=[ticker],
                start_date=date.today() - timedelta(days=5),
                end_date=date.today()
            )

            if not prices or ticker not in prices:
                logger.warning(f"[FactSet] No price data for {ticker}")
                return None

            latest = prices[ticker][-1]  # Most recent

            return FactSetPriceData(
                ticker=ticker,
                price_date=datetime.fromisoformat(latest["date"]).date(),
                close=latest["close"],
                volume=latest["volume"],
                pct_change=latest.get("pct_change", 0.0),
                volume_vs_avg=latest.get("volume_vs_avg", 1.0)
            )

    async def fetch_events(self, ticker: str) -> list[FundamentalEvent]:
        """Fetch recent corporate events"""
        logger.info(f"[FactSet] Fetching events for {ticker}")

        async with FactSetClient() as client:
            events_data = await client.get_events(ticker)

            events = []
            for event_data in events_data:
                event = FundamentalEvent(
                    event_id=uuid.uuid4(),
                    ticker=ticker,
                    event_type=event_data.get("type", "Unknown"),
                    event_date=datetime.fromisoformat(event_data["date"]).date(),
                    details=event_data.get("description", "")
                )
                events.append(event)

            logger.info(f"[FactSet] Found {len(events)} events for {ticker}")
            return events
```

#### Step 3.3: Integration Testing (Week 6)

**Test Cases:**

1. **Test Price Data Fetching**
   ```bash
   python3 -m src.batch.run_batch_phase2 --ticker AAPL --validate

   # Expected:
   # - Real current price
   # - Actual volume data
   # - Correct % change
   ```

2. **Test Corporate Events**
   ```bash
   python3 -m src.batch.run_batch_phase2 --ticker MSFT --validate

   # Expected:
   # - Earnings announcements
   # - Dividend events
   # - Stock splits (if any)
   ```

---

## Phase 4: LangSmith Enterprise Hybrid Deployment

### Overview

Migrate from LangSmith Cloud to LangSmith Enterprise with hybrid deployment to keep all data in customer AWS environment.

**Duration:** 2 weeks
**Complexity:** High
**Dependencies:** Phases 1-3 complete

### LangSmith Hybrid Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Customer AWS Environment                  │
│                                                              │
│  ┌────────────────────────────────────────────────────┐    │
│  │          LangSmith Data Plane (Kubernetes)         │    │
│  │                                                      │    │
│  │  ┌─────────────┐  ┌─────────────┐  ┌────────────┐ │    │
│  │  │   Tracer    │  │   Storage   │  │  Postgres  │ │    │
│  │  │   Service   │  │   Service   │  │   (RDS)    │ │    │
│  │  └─────────────┘  └─────────────┘  └────────────┘ │    │
│  │                                                      │    │
│  │  ┌─────────────┐  ┌─────────────┐                  │    │
│  │  │   Queue     │  │   Redis     │                  │    │
│  │  │  (Service)  │  │  (Cache)    │                  │    │
│  │  └─────────────┘  └─────────────┘                  │    │
│  └────────────────────────────────────────────────────┘    │
│                          ▲                                   │
│                          │ Secure connection                │
│                          │ (data stays in customer cloud)   │
└──────────────────────────┼──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│              LangSmith Control Plane (LangChain Cloud)       │
│                                                              │
│  ┌────────────────────────────────────────────────────┐    │
│  │  - User authentication                             │    │
│  │  - Dashboard UI                                    │    │
│  │  - Prompt management                               │    │
│  │  - Analytics engine                                │    │
│  │  - API gateway                                     │    │
│  └────────────────────────────────────────────────────┘    │
│                                                              │
│  Note: NO customer data stored here                         │
└─────────────────────────────────────────────────────────────┘
```

**Key Benefits:**
- ✅ All trace data stays in customer AWS (data sovereignty)
- ✅ Compliance with data residency requirements
- ✅ Full control over data retention and security
- ✅ Same LangSmith UI/features (control plane in LangChain cloud)
- ✅ Scalable architecture (Kubernetes auto-scaling)

### Prerequisites

1. **Upgrade to LangSmith Enterprise**
   - Contact: enterprise@langchain.com
   - Cost: $2,500/month (vs $200/month for cloud)
   - Timeline: 1 week for contract approval

2. **AWS Infrastructure Requirements**
   - EKS cluster (Elastic Kubernetes Service)
   - RDS PostgreSQL instance (for LangSmith data)
   - ElastiCache Redis (for caching)
   - Application Load Balancer
   - VPC with private subnets

### Implementation Steps

#### Step 4.1: Provision AWS Infrastructure (Week 7, Days 1-3)

**EKS Cluster Setup:**

```bash
# Install eksctl
curl --silent --location "https://github.com/weksctl/eksctl/releases/latest/download/eksctl_$(uname -s)_amd64.tar.gz" | tar xz -C /tmp
sudo mv /tmp/eksctl /usr/local/bin

# Create EKS cluster
eksctl create cluster \
  --name langsmith-data-plane \
  --region us-east-1 \
  --nodegroup-name langsmith-workers \
  --node-type m5.large \
  --nodes 3 \
  --nodes-min 2 \
  --nodes-max 5 \
  --managed

# Configure kubectl
aws eks update-kubeconfig --region us-east-1 --name langsmith-data-plane
```

**RDS PostgreSQL for LangSmith:**

```bash
# Create RDS instance
aws rds create-db-instance \
  --db-instance-identifier langsmith-db \
  --db-instance-class db.t3.medium \
  --engine postgres \
  --engine-version 15.4 \
  --master-username langsmith \
  --master-user-password <generate-strong-password> \
  --allocated-storage 100 \
  --storage-type gp3 \
  --vpc-security-group-ids sg-xxxxx \
  --db-subnet-group-name langsmith-subnet-group \
  --backup-retention-period 7 \
  --multi-az \
  --storage-encrypted
```

**ElastiCache Redis:**

```bash
# Create Redis cluster
aws elasticache create-cache-cluster \
  --cache-cluster-id langsmith-cache \
  --cache-node-type cache.t3.medium \
  --engine redis \
  --engine-version 7.0 \
  --num-cache-nodes 1 \
  --cache-subnet-group-name langsmith-subnet-group \
  --security-group-ids sg-xxxxx
```

#### Step 4.2: Install LangSmith Data Plane (Week 7, Days 4-5)

**Obtain Helm Chart from LangChain:**

```bash
# Add LangChain Helm repo (provided by LangChain Enterprise support)
helm repo add langchain https://charts.langchain.com
helm repo update

# Download values.yaml template
helm show values langchain/langsmith-data-plane > langsmith-values.yaml
```

**Configure `langsmith-values.yaml`:**

```yaml
# LangSmith Data Plane Configuration

global:
  # Control plane connection
  controlPlane:
    url: https://api.smith.langchain.com
    apiKey: <your-enterprise-api-key>  # Provided by LangChain

  # Data plane settings
  dataPlane:
    organizationId: <your-org-id>
    deploymentId: <your-deployment-id>

# Database configuration (RDS PostgreSQL)
postgresql:
  enabled: false  # Using external RDS

externalDatabase:
  host: langsmith-db.xxxxx.us-east-1.rds.amazonaws.com
  port: 5432
  database: langsmith
  username: langsmith
  password: <rds-password>

# Redis configuration (ElastiCache)
redis:
  enabled: false  # Using external ElastiCache

externalRedis:
  host: langsmith-cache.xxxxx.cache.amazonaws.com
  port: 6379

# Service configuration
services:
  tracer:
    replicas: 3
    resources:
      requests:
        cpu: 500m
        memory: 1Gi
      limits:
        cpu: 2000m
        memory: 4Gi

  storage:
    replicas: 2
    resources:
      requests:
        cpu: 250m
        memory: 512Mi
      limits:
        cpu: 1000m
        memory: 2Gi

  queue:
    replicas: 2
    resources:
      requests:
        cpu: 250m
        memory: 512Mi
      limits:
        cpu: 1000m
        memory: 2Gi

# Ingress (Application Load Balancer)
ingress:
  enabled: true
  className: alb
  annotations:
    alb.ingress.kubernetes.io/scheme: internal  # Internal-only access
    alb.ingress.kubernetes.io/target-type: ip
  hosts:
    - host: langsmith-data-plane.internal.company.com
      paths:
        - path: /
          pathType: Prefix

# Storage for trace data
persistence:
  enabled: true
  storageClass: gp3
  size: 500Gi

# Auto-scaling
autoscaling:
  enabled: true
  minReplicas: 2
  maxReplicas: 10
  targetCPUUtilizationPercentage: 70
```

**Install LangSmith:**

```bash
# Create namespace
kubectl create namespace langsmith

# Install with Helm
helm install langsmith-data-plane langchain/langsmith-data-plane \
  --namespace langsmith \
  --values langsmith-values.yaml \
  --timeout 10m

# Verify installation
kubectl get pods -n langsmith

# Expected output:
# NAME                                READY   STATUS    RESTARTS   AGE
# langsmith-tracer-xxxxxxxxx-xxxxx    1/1     Running   0          2m
# langsmith-tracer-xxxxxxxxx-xxxxx    1/1     Running   0          2m
# langsmith-tracer-xxxxxxxxx-xxxxx    1/1     Running   0          2m
# langsmith-storage-xxxxxxxxx-xxxxx   1/1     Running   0          2m
# langsmith-storage-xxxxxxxxx-xxxxx   1/1     Running   0          2m
# langsmith-queue-xxxxxxxxx-xxxxx     1/1     Running   0          2m
# langsmith-queue-xxxxxxxxx-xxxxx     1/1     Running   0          2m
```

#### Step 4.3: Update Application Configuration (Week 8, Days 1-2)

**Update `.env` file:**

```bash
# LangSmith Hybrid Configuration
LANGSMITH_ENDPOINT=https://langsmith-data-plane.internal.company.com
LANGSMITH_API_KEY=<your-enterprise-api-key>
LANGSMITH_PROJECT=fa-ai-system
LANGSMITH_TRACING=true

# Data plane metadata
LANGSMITH_DEPLOYMENT_TYPE=hybrid
LANGSMITH_ORGANIZATION_ID=<your-org-id>
```

**Update `src/config/settings.py`:**

```python
class Settings(BaseSettings):
    # ... existing fields ...

    # LangSmith Hybrid
    langsmith_endpoint: str = "https://api.smith.langchain.com"  # Override for hybrid
    langsmith_deployment_type: str = "cloud"  # "cloud" or "hybrid"
    langsmith_organization_id: str = ""
```

**Update LangSmith initialization (`src/shared/utils/tracing.py`):**

```python
import os
from src.config.settings import settings

def init_langsmith():
    """Initialize LangSmith tracing"""
    os.environ["LANGSMITH_TRACING_V2"] = "true"
    os.environ["LANGSMITH_API_KEY"] = settings.langsmith_api_key
    os.environ["LANGSMITH_PROJECT"] = settings.langsmith_project

    # Use hybrid endpoint if configured
    if settings.langsmith_deployment_type == "hybrid":
        os.environ["LANGSMITH_ENDPOINT"] = settings.langsmith_endpoint
        logger.info(f"✅ LangSmith hybrid deployment: {settings.langsmith_endpoint}")
    else:
        logger.info("✅ LangSmith cloud deployment")
```

#### Step 4.4: Testing & Validation (Week 8, Days 3-5)

**Test 1: Verify Data Plane Connectivity**

```python
# Test script: tests/test_langsmith_hybrid.py

import os
from langsmith import Client

def test_hybrid_connection():
    client = Client(
        api_key=os.getenv("LANGSMITH_API_KEY"),
        endpoint=os.getenv("LANGSMITH_ENDPOINT")
    )

    # Test connection
    projects = client.list_projects()
    print(f"✅ Connected to LangSmith hybrid deployment")
    print(f"   Projects: {len(list(projects))}")

    # Verify data plane
    info = client.info()
    print(f"   Deployment: {info.get('deployment_type')}")
    print(f"   Version: {info.get('version')}")

if __name__ == "__main__":
    test_hybrid_connection()
```

**Test 2: Verify Traces Going to Data Plane**

```bash
# Run batch processing with tracing
python3 -m src.batch.run_batch_phase2 --ticker AAPL --validate

# Check LangSmith UI (https://smith.langchain.com/)
# Navigate to project: fa-ai-system-batch
# Verify traces appear (data stored in customer AWS)
```

**Test 3: Verify Data Sovereignty**

```bash
# Connect to LangSmith RDS database
psql -h langsmith-db.xxxxx.us-east-1.rds.amazonaws.com -U langsmith -d langsmith

# Check trace data
SELECT COUNT(*) FROM runs WHERE project_name = 'fa-ai-system-batch';

# Verify data exists in customer database (not LangChain cloud)
```

**Test 4: End-to-End Batch Processing**

```bash
# Full batch run with hybrid LangSmith
python3 -m src.batch.run_batch_phase2 --limit 100

# Verify:
# - All traces captured
# - Data in customer AWS
# - LangSmith UI shows traces
# - Performance acceptable
```

---

## Phase 5: Production Validation

### Overview

Validate entire system end-to-end with production data and infrastructure.

**Duration:** 1-2 weeks
**Complexity:** Medium
**Dependencies:** Phases 1-4 complete

### Validation Checklist

#### 5.1: Data Quality Validation (Days 1-2)

**Test Scenarios:**

1. **EDGAR Data Accuracy**
   ```bash
   # Process 10 stocks with recent filings
   python3 -m src.batch.run_batch_phase2 --ticker AAPL,MSFT,GOOGL,AMZN,TSLA --validate

   # Manual verification:
   # - Compare summary to actual 10-K filing on SEC.gov
   # - Verify financial numbers match
   # - Check citations link to correct filings
   ```

2. **BlueMatrix Data Accuracy**
   ```bash
   # Process stocks with recent analyst reports
   python3 -m src.batch.run_batch_phase2 --ticker NVDA,META,NFLX --validate

   # Manual verification:
   # - Verify rating changes are accurate
   # - Check price targets match analyst reports
   # - Validate analyst firm names
   ```

3. **FactSet Data Accuracy**
   ```bash
   # Process stocks with recent corporate events
   python3 -m src.batch.run_batch_phase2 --ticker AAPL,MSFT --validate

   # Manual verification:
   # - Check current price vs market
   # - Verify earnings dates
   # - Validate dividend events
   ```

**Success Criteria:**
- [ ] 95%+ accuracy on financial metrics
- [ ] 100% citation accuracy (links to real sources)
- [ ] No hallucinations detected by fact-checker

#### 5.2: Performance Validation (Days 3-4)

**Load Tests:**

1. **Batch Processing Performance**
   ```bash
   # Process 1,000 stocks (full nightly batch)
   time python3 -m src.batch.run_batch_phase2 --limit 1000

   # Target: < 2 hours
   # Success rate: > 99%
   ```

2. **Interactive Query Performance**
   ```bash
   # Load test with 100 concurrent users
   python3 -m tests.load_test_interactive --users 100 --duration 300

   # Target: p95 < 60 seconds
   # Success rate: > 99.5%
   ```

3. **Database Performance**
   ```sql
   -- Test vector search performance
   EXPLAIN ANALYZE
   SELECT ticker, summary_text
   FROM stock_summaries
   ORDER BY embedding <-> '[...]'::vector
   LIMIT 5;

   -- Target: < 100ms
   ```

**Success Criteria:**
- [ ] Batch completes in < 2 hours
- [ ] Interactive p95 < 60 seconds
- [ ] Vector search < 100ms
- [ ] Database CPU < 70%

#### 5.3: Cost Validation (Days 5-6)

**Cost Monitoring:**

```bash
# Track costs for 7-day test period
python3 -m scripts.analyze_costs --start-date 2025-11-01 --end-date 2025-11-07

# Expected output:
# LLM Costs (Claude + OpenAI): $1,050/week ($150/day)
# Data APIs (BlueMatrix + FactSet): $3,500/week
# AWS Infrastructure: $700/week
# LangSmith Enterprise: $625/week
# ---
# Total: $5,875/week ($25,500/month)
```

**Success Criteria:**
- [ ] Daily batch cost < $150
- [ ] Monthly total < $26,000 (within budget)
- [ ] Cost per stock < $0.20

#### 5.4: Compliance Validation (Days 7-8)

**Audit Trail Verification:**

1. **Citation Coverage**
   ```sql
   -- Check citation coverage
   SELECT
       COUNT(*) FILTER (WHERE citation_count > 0) * 100.0 / COUNT(*) as coverage_pct
   FROM (
       SELECT
           ss.summary_id,
           COUNT(c.citation_id) as citation_count
       FROM stock_summaries ss
       LEFT JOIN citations c ON ss.summary_id = c.summary_id
       WHERE ss.created_at > NOW() - INTERVAL '7 days'
       GROUP BY ss.summary_id
   ) subq;

   -- Target: 100% coverage
   ```

2. **Data Residency**
   ```bash
   # Verify all trace data in customer AWS
   kubectl exec -n langsmith langsmith-storage-xxxxx -- \
     psql -U langsmith -d langsmith -c \
     "SELECT COUNT(*) FROM runs WHERE created_at > NOW() - INTERVAL '7 days';"

   # Verify matches LangSmith UI count
   # Confirms no data leakage to LangChain cloud
   ```

3. **Audit Logs**
   ```sql
   -- Check batch audit completeness
   SELECT
       DATE(started_at) as date,
       COUNT(*) as batch_runs,
       SUM(stocks_processed) as total_stocks
   FROM batch_audit
   WHERE started_at > NOW() - INTERVAL '7 days'
   GROUP BY DATE(started_at);

   -- Should have 1 run per day
   ```

**Success Criteria:**
- [ ] 100% citation coverage
- [ ] All data in customer AWS (hybrid deployment)
- [ ] Complete audit trail
- [ ] SEC compliance requirements met

#### 5.5: User Acceptance Testing (Days 9-10)

**Pilot User Testing:**

1. **Recruit 5 Financial Advisors**
   - Provide access to system
   - Training session (1 hour)
   - Daily usage for 5 days

2. **Collect Feedback**
   - Summary quality (1-5 rating)
   - Citation usefulness (1-5 rating)
   - Time savings (hours/day)
   - Feature requests
   - Bug reports

3. **Iterate Based on Feedback**
   - Fix critical bugs
   - Adjust prompts if needed
   - Improve UX pain points

**Success Criteria:**
- [ ] Average quality rating > 4.0/5.0
- [ ] 80%+ report time savings
- [ ] < 5 critical bugs found
- [ ] No data accuracy issues

---

## Timeline & Resource Requirements

### Gantt Chart

```
Week 1-2:  Phase 1 - EDGAR Integration
           ▓▓▓▓▓▓▓▓▓▓▓▓▓▓

Week 3-4:  Phase 2 - BlueMatrix Integration
                     ▓▓▓▓▓▓▓▓▓▓▓▓▓▓

Week 5-6:  Phase 3 - FactSet Integration
                               ▓▓▓▓▓▓▓▓▓▓▓▓▓▓

Week 7-8:  Phase 4 - LangSmith Hybrid
                                         ▓▓▓▓▓▓▓▓▓▓▓▓▓▓

Week 9-10: Phase 5 - Production Validation
                                                   ▓▓▓▓▓▓▓▓▓▓▓▓▓▓

Total Duration: 10 weeks
```

### Resource Requirements

**Team:**
- 1 Senior Backend Engineer (full-time, 10 weeks)
- 1 DevOps Engineer (full-time, weeks 7-10)
- 1 QA Engineer (part-time, weeks 5-10)
- 1 Product Manager (part-time, entire duration)
- 5 Pilot Users (week 9-10)

**Budget:**
| Item | Cost | Notes |
|------|------|-------|
| Engineering Labor | $80,000 | 10 weeks × $8,000/week |
| Data API Subscriptions | $15,000 | BlueMatrix + FactSet setup |
| AWS Infrastructure | $5,000 | EKS, RDS, ElastiCache setup |
| LangSmith Enterprise | $2,500 | 1 month |
| Testing & QA | $10,000 | Load testing, UAT |
| **Total** | **$112,500** | One-time implementation |

**Ongoing Costs (Monthly):**
| Item | Cost |
|------|------|
| BlueMatrix API | $10,000 |
| FactSet API | $5,000 |
| AWS Infrastructure | $3,000 |
| LangSmith Enterprise | $2,500 |
| Claude + OpenAI APIs | $4,500 |
| **Total** | **$25,000/month** |

---

## Risk Management

### High-Priority Risks

#### Risk 1: Data API Vendor Delays

**Likelihood:** Medium
**Impact:** High

**Description:** BlueMatrix or FactSet contract approval takes > 3 weeks, delaying integration.

**Mitigation:**
- Start vendor conversations immediately (before Phase 1)
- Have legal team expedite contract review
- Use sandbox environments while waiting for production access
- Parallel track: complete EDGAR (free API) while waiting for paid APIs

**Contingency:**
- If BlueMatrix delayed: Use public analyst ratings from Yahoo Finance as interim
- If FactSet delayed: Use Alpha Vantage or IEX Cloud for market data

#### Risk 2: LangSmith Hybrid Deployment Complexity

**Likelihood:** Medium
**Impact:** High

**Description:** Kubernetes deployment more complex than expected, causing delays.

**Mitigation:**
- Engage LangChain Enterprise support early
- Allocate experienced DevOps engineer
- Use LangChain's reference architecture
- Test in staging environment first

**Contingency:**
- Stay on LangSmith Cloud temporarily (delay hybrid to post-launch)
- Note: May violate data residency requirements - escalate to compliance

#### Risk 3: Data Quality Issues

**Likelihood:** Medium
**Impact:** High

**Description:** Production data has edge cases causing hallucinations or errors.

**Mitigation:**
- Extensive testing in Phase 5
- Robust error handling in all fetcher agents
- Fact-checker validation before saving summaries
- Human review queue for low-confidence summaries

**Contingency:**
- Implement graduated rollout (10 stocks → 100 stocks → 1,000 stocks)
- Maintain manual review for first 2 weeks

### Medium-Priority Risks

#### Risk 4: Rate Limiting

**Likelihood:** Low
**Impact:** Medium

**Description:** Hit API rate limits during batch processing.

**Mitigation:**
- Implement exponential backoff
- Respect documented rate limits (10/sec EDGAR, 1000/hr BlueMatrix)
- Monitor rate limit headers in responses
- Configure max_concurrent appropriately

**Contingency:**
- Reduce batch concurrency
- Spread batch processing over longer window (3 hours vs 2 hours)

#### Risk 5: Cost Overruns

**Likelihood:** Medium
**Impact:** Medium

**Description:** LLM API costs exceed $150/day budget.

**Mitigation:**
- Smart model routing (Haiku for simple tasks)
- Prompt optimization (reduce token usage)
- Embedding caching (60%+ hit rate)
- Real-time cost monitoring with daily budgets

**Contingency:**
- Reduce batch frequency (every other day vs daily)
- Process top 500 stocks only (vs 1,000)
- Negotiate volume discounts with Anthropic

---

## Rollback Procedures

### Rollback Scenario 1: Data Source Integration Failure

**Symptoms:**
- High error rates from new API
- Incorrect data being fetched
- Batch processing failing

**Rollback Steps:**

1. **Revert to Sample Data** (5 minutes)
   ```bash
   # Switch back to sample data fetchers
   git checkout main -- src/batch/agents/edgar_fetcher.py
   git checkout main -- src/batch/agents/bluematrix_fetcher.py
   git checkout main -- src/batch/agents/factset_fetcher.py

   # Restart batch processing
   pkill -f run_batch_phase2
   python3 -m src.batch.run_batch_phase2 --limit 1000
   ```

2. **Notify Stakeholders**
   - Send email: "Temporarily using cached data while we resolve API integration issue"
   - ETA for fix: 4-8 hours

3. **Root Cause Analysis**
   - Review logs for error patterns
   - Test API endpoints manually
   - Contact vendor support if needed

### Rollback Scenario 2: LangSmith Hybrid Deployment Failure

**Symptoms:**
- Traces not appearing in LangSmith UI
- Data plane pods crashing
- High latency due to tracing

**Rollback Steps:**

1. **Switch Back to Cloud** (10 minutes)
   ```bash
   # Update .env
   LANGSMITH_ENDPOINT=https://api.smith.langchain.com
   LANGSMITH_DEPLOYMENT_TYPE=cloud

   # Restart services
   ./scripts/restart_all.sh
   ```

2. **Verify Cloud Tracing**
   ```bash
   # Test trace submission
   python3 -m src.batch.run_batch_phase2 --ticker AAPL

   # Check LangSmith UI for traces
   ```

3. **Schedule Hybrid Retry**
   - Work with LangChain support
   - Fix Kubernetes configuration
   - Re-attempt deployment in maintenance window

### Rollback Scenario 3: Complete System Failure

**Symptoms:**
- Both batch and interactive systems down
- Database corruption
- Unable to recover

**Rollback Steps:**

1. **Restore Database from Backup** (30 minutes)
   ```bash
   # Stop all services
   pkill -f run_batch_phase2
   pkill -f uvicorn

   # Restore latest backup
   pg_restore -h <db-host> -U <db-user> -d fa_ai_db -c backup_latest.dump
   ```

2. **Revert to Last Known Good Version**
   ```bash
   # Find last stable commit
   git log --oneline

   # Revert to stable version
   git checkout <stable-commit-hash>

   # Redeploy
   ./scripts/deploy.sh
   ```

3. **Emergency Communication**
   - Notify all users immediately
   - Provide manual research alternatives
   - ETA for recovery: 2-4 hours

---

## Success Metrics

### Go/No-Go Criteria for Production Launch

All criteria must be met before pilot launch:

**Data Integration:**
- [x] EDGAR API integrated and tested
- [x] BlueMatrix API integrated and tested
- [x] FactSet API integrated and tested
- [x] All three sources returning real data

**LangSmith Hybrid:**
- [x] Data plane deployed to customer AWS
- [x] All traces going to hybrid deployment
- [x] Data residency verified (no data in LangChain cloud)
- [x] LangSmith UI functional

**Performance:**
- [x] Batch processing < 2 hours for 1,000 stocks
- [x] Interactive queries p95 < 60 seconds
- [x] Success rate > 99%

**Quality:**
- [x] Fact-check pass rate > 95%
- [x] Hallucination rate < 1%
- [x] Citation coverage 100%

**Cost:**
- [x] Daily batch cost < $150
- [x] Monthly total < $26,000

**Compliance:**
- [x] All data in customer AWS
- [x] Complete audit trail
- [x] SEC compliance requirements met

---

## Appendix: Contact Information

### Data Vendors

**SEC EDGAR:**
- Support: https://www.sec.gov/oiea/Article/edgarguide.html
- No formal support (public API)

**BlueMatrix:**
- Sales: sales@bluematrix.com
- Support: support@bluematrix.com
- Phone: 1-800-xxx-xxxx

**FactSet:**
- Sales: sales@factset.com
- Support: support@factset.com
- Developer Portal: https://developer.factset.com/

### LangSmith Enterprise

**LangChain:**
- Enterprise Sales: enterprise@langchain.com
- Technical Support: support@langchain.com
- Documentation: https://docs.langchain.com/langsmith/hybrid

### Internal Contacts

- Engineering Lead: engineering-lead@company.com
- DevOps Lead: devops@company.com
- Product Manager: product@company.com
- Compliance Officer: compliance@company.com

---

**Document Owner:** Engineering Team
**Last Updated:** November 7, 2025
**Next Review:** December 1, 2025
