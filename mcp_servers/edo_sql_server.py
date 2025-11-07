"""
Mock MCP Server for EDO SQL Queries

In production, this would be a Model Context Protocol (MCP) server
that connects to the actual EDO database and performs text-to-SQL
queries to retrieve FA and household data.

For development, we provide mock data.
"""

from typing import Dict, Any, List
import json
import random
from datetime import datetime, timedelta


class EdoMCPServer:
    """Mock MCP server for text-to-SQL on EDO data"""

    def __init__(self):
        self.mock_data = self._generate_mock_data()

    def _generate_mock_data(self) -> Dict:
        """Generate realistic mock EDO data"""
        return {
            "fas": {
                "FA-001": {
                    "name": "John Smith",
                    "region": "Northeast",
                    "aum": 250_000_000,
                    "client_count": 45,
                    "specialization": "High Net Worth"
                },
                "FA-002": {
                    "name": "Sarah Johnson",
                    "region": "West",
                    "aum": 180_000_000,
                    "client_count": 38,
                    "specialization": "Tech Executives"
                },
                "FA-003": {
                    "name": "Michael Chen",
                    "region": "West",
                    "aum": 320_000_000,
                    "client_count": 52,
                    "specialization": "Corporate Executives"
                }
            },
            "households": {
                "HH-001": {
                    "household_id": "HH-001",
                    "household_name": "Miller Family Trust",
                    "fa_id": "FA-001",
                    "total_aum": 5_500_000,
                    "risk_tolerance": "moderate",
                    "holdings": [
                        {"ticker": "AAPL", "shares": 5000, "cost_basis": 120.00, "current_value": 900000},
                        {"ticker": "MSFT", "shares": 3000, "cost_basis": 250.00, "current_value": 1200000},
                        {"ticker": "GOOGL", "shares": 1000, "cost_basis": 100.00, "current_value": 150000}
                    ]
                },
                "HH-002": {
                    "household_id": "HH-002",
                    "household_name": "Chen Retirement Account",
                    "fa_id": "FA-001",
                    "total_aum": 3_200_000,
                    "risk_tolerance": "conservative",
                    "holdings": [
                        {"ticker": "JPM", "shares": 2000, "cost_basis": 140.00, "current_value": 320000},
                        {"ticker": "AAPL", "shares": 2000, "cost_basis": 130.00, "current_value": 360000}
                    ]
                },
                "HH-003": {
                    "household_id": "HH-003",
                    "household_name": "Anderson Growth Portfolio",
                    "fa_id": "FA-001",
                    "total_aum": 8_500_000,
                    "risk_tolerance": "aggressive",
                    "holdings": [
                        {"ticker": "TSLA", "shares": 10000, "cost_basis": 200.00, "current_value": 2500000},
                        {"ticker": "NVDA", "shares": 5000, "cost_basis": 400.00, "current_value": 2200000},
                        {"ticker": "AAPL", "shares": 3000, "cost_basis": 150.00, "current_value": 540000}
                    ]
                },
                "HH-004": {
                    "household_id": "HH-004",
                    "household_name": "Thompson Foundation",
                    "fa_id": "FA-002",
                    "total_aum": 12_000_000,
                    "risk_tolerance": "moderate",
                    "holdings": [
                        {"ticker": "AAPL", "shares": 8000, "cost_basis": 110.00, "current_value": 1440000},
                        {"ticker": "AMZN", "shares": 4000, "cost_basis": 3000.00, "current_value": 600000},
                        {"ticker": "META", "shares": 6000, "cost_basis": 280.00, "current_value": 3000000}
                    ]
                }
            }
        }

    def text_to_sql(self, natural_language_query: str, fa_id: str) -> str:
        """Convert natural language to SQL (mocked)"""
        query_lower = natural_language_query.lower()

        # Simple pattern matching for common queries
        if "top households" in query_lower or "largest households" in query_lower:
            return f"SELECT * FROM Households WHERE fa_id = '{fa_id}' ORDER BY total_aum DESC LIMIT 10"

        if "holding" in query_lower and "ticker" in query_lower:
            # Extract ticker
            import re
            ticker_match = re.search(r'([A-Z]{1,5})', natural_language_query)
            ticker = ticker_match.group(1) if ticker_match else "AAPL"
            return f"SELECT * FROM Holdings WHERE fa_id = '{fa_id}' AND ticker = '{ticker}'"

        # Default
        return f"SELECT * FROM Households WHERE fa_id = '{fa_id}'"

    def execute_query(self, sql: str, fa_id: str) -> List[Dict[str, Any]]:
        """Execute SQL query (mocked with fake data)"""
        # Return mock households for this FA
        households = [
            hh for hh_id, hh in self.mock_data["households"].items()
            if hh.get("fa_id") == fa_id
        ]

        return households


# Global instance
edo_mcp_server = EdoMCPServer()
