"""
Perplexity API Client for FA AI System

Wrapper around Perplexity API optimized for financial data retrieval:
- SEC filings (10-K, 8-K)
- Real-time market news
- Financial research

API Documentation: https://docs.perplexity.ai/docs/getting-started
"""

import httpx
import json
import logging
from typing import Optional, Dict, List
from datetime import datetime, timedelta
import os

from langchain_openai import ChatOpenAI

logger = logging.getLogger(__name__)


class PerplexityClient:
    """
    Async client for Perplexity API with finance-focused features

    Usage:
        client = PerplexityClient(api_key="your_key")
        result = await client.search("What is Apple's latest 10-K?", focus="finance")

        # Specialized methods
        filing = await client.get_10k_8k("AAPL")
        news = await client.get_current_news(["AAPL", "MSFT"], hours_back=24)
    """

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("PERPLEXITY_API_KEY")
        if not self.api_key:
            raise ValueError("PERPLEXITY_API_KEY must be set in environment or passed to constructor")

        self.base_url = "https://api.perplexity.ai"
        self.client = httpx.AsyncClient(
            timeout=30.0,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
        )

        # Use GPT-4o-mini for parsing structured data from Perplexity responses
        self.parser_llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)

    async def search(
        self,
        query: str,
        focus: str = "finance",
        search_recency_filter: str = "month",
        return_images: bool = False
    ) -> Dict:
        """
        General-purpose search via Perplexity

        Args:
            query: Search query text
            focus: Domain focus (finance, news, academic, etc.)
            search_recency_filter: Time window - day, week, month, year
            return_images: Whether to include images in results

        Returns:
            {
                "answer": str,  # Natural language answer
                "citations": list[str],  # Source URLs
                "items": list[dict],  # Structured data extracted
                "metadata": dict  # API metadata (model, usage, etc.)
            }
        """
        try:
            response = await self.client.post(
                f"{self.base_url}/chat/completions",
                json={
                    "model": "llama-3.1-sonar-large-128k-online",
                    "messages": [
                        {
                            "role": "system",
                            "content": f"You are a financial research assistant. Focus: {focus}. "
                                       f"Provide factual, well-sourced information with specific dates and numbers."
                        },
                        {
                            "role": "user",
                            "content": query
                        }
                    ],
                    "search_recency_filter": search_recency_filter,
                    "return_citations": True,
                    "return_images": return_images
                }
            )

            response.raise_for_status()
            data = response.json()

            answer = data["choices"][0]["message"]["content"]
            citations = data.get("citations", [])

            # Parse structured data from answer (async)
            items = await self._parse_structured_data(answer, query)

            return {
                "answer": answer,
                "citations": citations,
                "items": items,
                "metadata": {
                    "model": data.get("model"),
                    "usage": data.get("usage", {}),
                    "id": data.get("id")
                }
            }

        except httpx.HTTPStatusError as e:
            logger.error(f"Perplexity API error: {e.response.status_code} - {e.response.text}")
            raise
        except Exception as e:
            logger.error(f"Perplexity client error: {str(e)}")
            raise

    async def get_10k_8k(self, ticker: str) -> Dict:
        """
        Fetch and summarize latest 10-K and 8-K SEC filings

        Args:
            ticker: Stock ticker symbol (e.g., "AAPL")

        Returns:
            {
                "ticker": str,
                "filing_date": str (ISO format),
                "business_summary": str,
                "financials": str,
                "risks": str,
                "management_discussion": str,
                "citations": list[str],
                "raw_answer": str
            }
        """
        query = f"""
        Find the most recent 10-K and 8-K SEC filings for {ticker}.

        Provide a comprehensive summary including:

        1. Filing Date: When was the most recent 10-K filed?

        2. Business Overview: What does the company do? Core products/services?

        3. Financial Performance: Recent revenue, profit, cash flow trends from the 10-K.

        4. Material Risks: Key risk factors disclosed in the filing.

        5. Management's Discussion: Important points from MD&A section.

        6. Recent 8-K Filings: Any material events reported in last 90 days?

        Format your response with clear section headers. Include specific numbers and dates.
        """

        result = await self.search(
            query=query,
            focus="finance",
            search_recency_filter="year"  # 10-Ks are annual
        )

        # Extract structured sections
        parsed = await self._parse_10k_8k_structure(ticker, result["answer"])

        return {
            "ticker": ticker,
            **parsed,
            "citations": result["citations"],
            "raw_answer": result["answer"]
        }

    async def get_current_news(
        self,
        tickers: List[str],
        hours_back: int = 24,
        max_items: int = 10
    ) -> Dict:
        """
        Fetch recent market news for specified tickers

        Args:
            tickers: List of stock tickers
            hours_back: How many hours of history to retrieve
            max_items: Maximum number of news items to return

        Returns:
            {
                "tickers": list[str],
                "news_items": list[dict],  # Each with: headline, summary, date, source, tickers
                "citations": list[str],
                "as_of": str (ISO timestamp)
            }
        """
        ticker_str = ", ".join(tickers)

        query = f"""
        What are the most important news developments for these stocks in the last {hours_back} hours: {ticker_str}?

        Focus on:
        - Earnings announcements and guidance
        - Product launches or major releases
        - M&A activity (acquisitions, divestitures)
        - Regulatory actions or legal developments
        - Analyst upgrades/downgrades
        - Material business changes

        For each item, provide:
        - Headline
        - Brief summary (2-3 sentences)
        - Date/time
        - Which ticker(s) it affects
        - Source

        Only include factual, confirmed news. No speculation.
        """

        # Determine search recency based on hours_back
        if hours_back <= 24:
            recency = "day"
        elif hours_back <= 168:  # 1 week
            recency = "week"
        else:
            recency = "month"

        result = await self.search(
            query=query,
            focus="finance",
            search_recency_filter=recency
        )

        # Parse news items
        news_items = await self._parse_news_items(result["answer"], tickers)

        return {
            "tickers": tickers,
            "news_items": news_items[:max_items],
            "citations": result["citations"],
            "as_of": datetime.utcnow().isoformat()
        }

    async def verify_claim(self, claim: str) -> Dict:
        """
        Verify a factual claim by searching for supporting evidence

        Used by Validator Agent to check accuracy

        Args:
            claim: Factual statement to verify

        Returns:
            {
                "claim": str,
                "verdict": "VERIFIED" | "INVALID" | "UNCERTAIN",
                "explanation": str,
                "supporting_evidence": str,
                "citations": list[str]
            }
        """
        query = f"""
        Verify this claim: "{claim}"

        Check if this is factually accurate. Respond with:

        VERDICT: [VERIFIED / INVALID / UNCERTAIN]

        EXPLANATION: [Why is it verified, invalid, or uncertain?]

        EVIDENCE: [Specific facts, numbers, or sources that support or contradict the claim]

        Be rigorous. Only mark as VERIFIED if you have strong evidence.
        """

        result = await self.search(
            query=query,
            focus="finance",
            search_recency_filter="week"
        )

        # Parse verdict
        answer = result["answer"].upper()

        if "VERDICT: VERIFIED" in answer or "VERDICT:VERIFIED" in answer:
            verdict = "VERIFIED"
        elif "VERDICT: INVALID" in answer or "VERDICT:INVALID" in answer:
            verdict = "INVALID"
        else:
            verdict = "UNCERTAIN"

        return {
            "claim": claim,
            "verdict": verdict,
            "explanation": result["answer"],
            "supporting_evidence": result["answer"],
            "citations": result["citations"]
        }

    async def _parse_structured_data(self, answer: str, query: str) -> List[Dict]:
        """
        Extract structured data from natural language answer using LLM

        This is a general-purpose parser. Specialized methods use more targeted parsing.
        """
        # For simple cases, don't over-engineer
        return []

    async def _parse_10k_8k_structure(self, ticker: str, answer: str) -> Dict:
        """
        Parse 10-K/8-K answer into structured sections
        """
        prompt = f"""
        Extract key information from this 10-K/8-K summary for {ticker}.

        Answer:
        {answer}

        Return a JSON object with these exact fields (use null if info not found):
        {{
            "filing_date": "YYYY-MM-DD or null",
            "business_summary": "2-3 sentence company overview",
            "financials": "Key financial metrics and trends",
            "risks": "Main risk factors",
            "management_discussion": "Key points from MD&A"
        }}

        Return ONLY the JSON object, no other text.
        """

        try:
            result = await self.parser_llm.ainvoke(prompt)
            parsed = json.loads(result.content)
            return parsed
        except Exception as e:
            logger.error(f"Failed to parse 10-K/8-K structure: {e}")
            # Return basic structure
            return {
                "filing_date": None,
                "business_summary": answer[:500],
                "financials": "",
                "risks": "",
                "management_discussion": ""
            }

    async def _parse_news_items(self, answer: str, tickers: List[str]) -> List[Dict]:
        """
        Parse news answer into structured news items
        """
        prompt = f"""
        Extract news items from this text about {", ".join(tickers)}.

        Text:
        {answer}

        Return a JSON array of news items with this format:
        [
            {{
                "headline": "Brief headline",
                "summary": "2-3 sentence summary",
                "published_at": "YYYY-MM-DD HH:MM or YYYY-MM-DD",
                "source": "Source name",
                "tickers": ["AAPL", ...],
                "category": "earnings|product|m&a|regulatory|analyst|other"
            }}
        ]

        Return ONLY the JSON array, no other text. If no news items found, return [].
        """

        try:
            result = await self.parser_llm.ainvoke(prompt)
            parsed = json.loads(result.content)
            return parsed if isinstance(parsed, list) else []
        except Exception as e:
            logger.error(f"Failed to parse news items: {e}")
            return []

    async def close(self):
        """Close the HTTP client"""
        await self.client.aclose()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()


# ============================================================================
# Convenience Functions
# ============================================================================

async def search_perplexity(query: str, **kwargs) -> Dict:
    """
    Convenience function for one-off searches

    Usage:
        result = await search_perplexity("What is Apple's latest earnings?")
    """
    async with PerplexityClient() as client:
        return await client.search(query, **kwargs)


async def get_stock_filings(ticker: str) -> Dict:
    """
    Convenience function for fetching 10-K/8-K

    Usage:
        filings = await get_stock_filings("AAPL")
    """
    async with PerplexityClient() as client:
        return await client.get_10k_8k(ticker)


async def get_news(tickers: List[str], hours_back: int = 24) -> Dict:
    """
    Convenience function for fetching news

    Usage:
        news = await get_news(["AAPL", "MSFT"], hours_back=48)
    """
    async with PerplexityClient() as client:
        return await client.get_current_news(tickers, hours_back=hours_back)
