from langchain_anthropic import ChatAnthropic
from langchain_core.prompts import load_prompt
from typing import Dict, Any, List, Literal
import asyncio
import logging
import json
import time

from src.batch.state import BatchGraphStatePhase2, SourceFactCheckResult
from src.config.settings import settings
from src.shared.utils.rag import hybrid_search

logger = logging.getLogger(__name__)


class FactCheckerAgent:
    """Agent for fact-checking summary claims against source documents"""

    def __init__(self):
        self.llm = ChatAnthropic(
            model="claude-sonnet-4-20250514",
            temperature=0.0,  # Deterministic for fact-checking
            max_tokens=4000,
            anthropic_api_key=settings.anthropic_api_key
        )
        self.prompt = load_prompt("prompts/batch/fact_checker_v1.yaml")

    async def verify_summary(
        self,
        ticker: str,
        company_name: str,
        summary_text: str,
        tier: Literal["hook", "medium", "expanded"],
        state: BatchGraphStatePhase2
    ) -> Dict[str, Any]:
        """Verify all claims in a summary against source documents

        Args:
            ticker: Stock ticker
            company_name: Company name
            summary_text: The summary to fact-check
            tier: Summary tier (hook, medium, expanded)
            state: Current batch state with source data

        Returns:
            Dict with claims, verification results, and pass rates
        """
        logger.info(f"[FactCheck-{tier}] Verifying summary for {ticker}")

        # Gather source context from all available sources
        source_context = await self._gather_source_context(ticker, company_name, state, summary_text)

        # Generate fact-check analysis
        messages = self.prompt.format(
            ticker=ticker,
            company_name=company_name,
            summary_text=summary_text,
            tier=tier,
            source_context=source_context
        )

        response = await self.llm.ainvoke(messages)

        try:
            # Parse JSON response
            result = json.loads(response.content.strip())

            verified_count = result.get('verified_count', 0)
            failed_count = result.get('failed_count', 0)
            uncertain_count = result.get('uncertain_count', 0)
            total_claims = verified_count + failed_count + uncertain_count

            pass_rate = verified_count / max(total_claims, 1)

            logger.info(
                f"[FactCheck-{tier}] {ticker}: {verified_count}/{total_claims} verified "
                f"(pass rate: {pass_rate:.1%})"
            )

            return result

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse fact-check JSON: {e}")
            logger.error(f"Response: {response.content[:500]}")
            return {
                "claims": [],
                "overall_pass_rate": 0.0,
                "verified_count": 0,
                "failed_count": 0,
                "uncertain_count": 0,
                "error": str(e)
            }

    async def _gather_source_context(
        self,
        ticker: str,
        company_name: str,
        state: BatchGraphStatePhase2,
        summary_text: str
    ) -> str:
        """Gather relevant context from all source documents"""

        context_parts = []

        # EDGAR context
        if state.edgar_filings:
            edgar_text = "\n\n".join([
                f"=== {filing.filing_type} filed {filing.filing_date.strftime('%Y-%m-%d')} ===\n"
                f"{filing.full_text[:2000]}"
                for filing in state.edgar_filings[:2]
            ])
            context_parts.append(f"EDGAR FILINGS:\n{edgar_text}")

        # BlueMatrix context
        if state.bluematrix_reports:
            bm_text = "\n\n".join([
                f"=== {report.analyst_firm} report {report.report_date.strftime('%Y-%m-%d')} ===\n"
                f"Rating: {report.rating_change} to {report.new_rating}\n"
                f"Price Target: ${report.price_target}\n"
                f"Analysis: {report.full_text[:1500]}"
                for report in state.bluematrix_reports[:2]
            ])
            context_parts.append(f"ANALYST REPORTS:\n{bm_text}")

        # FactSet context
        if state.factset_price_data:
            pd = state.factset_price_data
            fs_text = f"""PRICE DATA ({pd.date.strftime('%Y-%m-%d')}):
Open: ${pd.open:.2f}, Close: ${pd.close:.2f}
Change: {pd.pct_change:+.2f}%
Volume: {pd.volume:,} ({pd.volume_vs_avg:.1f}x average)"""

            if state.factset_events:
                events_text = "\n".join([
                    f"- {e.event_type}: {e.details}"
                    for e in state.factset_events[:3]
                ])
                fs_text += f"\n\nEVENTS:\n{events_text}"

            context_parts.append(f"MARKET DATA:\n{fs_text}")

        # RAG retrieval for additional context
        try:
            namespaces = []
            if state.edgar_vector_ids:
                namespaces.append("edgar_filings")
            if state.bluematrix_vector_ids:
                namespaces.append("bluematrix_reports")
            if state.factset_vector_ids:
                namespaces.append("factset_data")

            if namespaces:
                rag_results = await hybrid_search(
                    query=summary_text,
                    namespaces=namespaces,
                    stock_id=state.stock_id,
                    top_k=10
                )

                if rag_results:
                    rag_text = "\n".join([
                        f"- {r['text'][:300]}"
                        for r in rag_results[:5]
                    ])
                    context_parts.append(f"ADDITIONAL CONTEXT (RAG):\n{rag_text}")
        except Exception as e:
            logger.warning(f"RAG retrieval failed: {e}")

        if not context_parts:
            return "No source documents available for verification."

        return "\n\n" + "="*80 + "\n\n".join(context_parts)
