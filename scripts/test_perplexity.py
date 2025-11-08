#!/usr/bin/env python3
"""
Test script for Perplexity API integration

Tests the PerplexityClient with both real API and mock fallback.
"""

import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.shared.utils.perplexity_client import PerplexityClient
from src.config.settings import settings


async def test_perplexity():
    """Test Perplexity client"""
    print("=" * 80)
    print("Testing Perplexity API Integration")
    print("=" * 80)

    # Test with real API key
    print("\n1. Testing with REAL Perplexity API (from .env)")
    print(f"   API Key configured: {'Yes' if settings.perplexity_api_key else 'No'}")

    if settings.perplexity_api_key:
        print(f"   API Key: {settings.perplexity_api_key[:10]}...")

    client = PerplexityClient(api_key=settings.perplexity_api_key)

    # Test query
    query = "AAPL Apple earnings latest news"
    print(f"\n2. Searching for: {query}")
    print(f"   Lookback: 4 hours")

    try:
        news_items = await client.search_news(query, lookback_hours=4)

        print(f"\n3. Results: Found {len(news_items)} news items\n")

        for idx, item in enumerate(news_items, 1):
            print(f"   {idx}. {item['headline']}")
            print(f"      Source: {item['source']}")
            print(f"      URL: {item['url']}")
            print(f"      Published: {item['published_at']}")
            print(f"      Relevance: {item['relevance_score']:.2f}")
            print(f"      Summary: {item['summary'][:150]}...")
            print()

    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()

    print("=" * 80)


async def test_mock_mode():
    """Test mock mode (no API key)"""
    print("\n" + "=" * 80)
    print("Testing MOCK Mode (no API key)")
    print("=" * 80)

    client = PerplexityClient(api_key=None)

    query = "NVDA semiconductor news"
    print(f"\n1. Searching for: {query}")

    news_items = await client.search_news(query, lookback_hours=24)

    print(f"\n2. Results: Found {len(news_items)} news items\n")

    for idx, item in enumerate(news_items, 1):
        print(f"   {idx}. {item['headline']}")
        print(f"      Source: {item['source']}")
        print(f"      Relevance: {item['relevance_score']:.2f}")
        print()

    print("=" * 80)


async def main():
    """Run all tests"""
    await test_perplexity()
    await test_mock_mode()


if __name__ == "__main__":
    asyncio.run(main())
