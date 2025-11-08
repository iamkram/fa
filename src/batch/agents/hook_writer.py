from langchain_anthropic import ChatAnthropic
from typing import Dict, Any, Optional
import asyncio
import logging
import time

from src.batch.state import BatchGraphStatePhase2
from src.config.settings import settings
from src.shared.utils.prompt_manager import get_prompt

logger = logging.getLogger(__name__)


class HookWriterAgent:
    """Agent for generating hook summaries (25-50 words)

    Uses LangSmith prompt hub for centralized prompt management.
    Prompts can be versioned and A/B tested without code changes.
    """

    def __init__(self, prompt_version: Optional[str] = None):
        """
        Initialize hook writer agent

        Args:
            prompt_version: Optional prompt version from LangSmith hub
                          (default: latest version)
        """
        self.llm = ChatAnthropic(
            model="claude-sonnet-4-20250514",
            temperature=0.5,  # Slightly higher for creativity
            max_tokens=150,  # Increased for 25-50 word target
            anthropic_api_key=settings.anthropic_api_key
        )

        # Load prompt from LangSmith hub
        try:
            self.prompt = get_prompt("hook_summary_writer", version=prompt_version)
            logger.info(f"Loaded prompt from LangSmith: hook_summary_writer{f':{prompt_version}' if prompt_version else ''}")
        except Exception as e:
            logger.warning(f"Failed to load prompt from LangSmith: {e}")
            logger.info("Using fallback prompt")
            # Fallback is handled by get_prompt()

    async def generate(
        self,
        ticker: str,
        company_name: str,
        state: BatchGraphStatePhase2
    ) -> tuple[str, int]:
        """Generate hook summary (25-50 words)"""

        # Generate summaries from raw source data
        edgar_summary = self._summarize_edgar(state.edgar_filings)
        bluematrix_summary = self._summarize_bluematrix(state.bluematrix_reports)
        factset_summary = self._summarize_factset(state.factset_price_data, state.factset_events)

        # Generate hook using LangSmith prompt
        messages = self.prompt.invoke({
            "ticker": ticker,
            "edgar_summary": edgar_summary,
            "bluematrix_summary": bluematrix_summary,
            "factset_summary": factset_summary
        })

        response = await self.llm.ainvoke(messages)
        hook = response.content.strip()

        # Validate word count (25-50 words target)
        word_count = len(hook.split())
        if word_count < 20 or word_count > 60:
            logger.warning(f"Hook word count outside target ({word_count} words, target: 25-50)")
            # Try again with stricter instruction
            summary = f"EDGAR: {edgar_summary[:200]}... | BlueMatrix: {bluematrix_summary[:200]}... | FactSet: {factset_summary[:200]}..."
            hook = await self._regenerate_shorter(hook, ticker, company_name, summary)
            word_count = len(hook.split())

        return hook, word_count

    def _summarize_edgar(self, filings: list) -> str:
        """Create summary from EDGAR filings"""
        if not filings:
            return "No recent EDGAR filings"

        filing = filings[0]  # Most recent
        return f"{filing.filing_type} filed on {filing.filing_date.strftime('%Y-%m-%d')}: {filing.full_text[:200] if filing.full_text else 'No content'}"

    def _summarize_bluematrix(self, reports: list) -> str:
        """Create summary from BlueMatrix reports"""
        if not reports:
            return "No recent analyst reports"

        report = reports[0]  # Most recent
        rating_info = f"{report.rating_change} to {report.new_rating}" if report.rating_change else report.new_rating
        return f"{report.analyst_firm} {rating_info}, PT ${report.price_target}: {report.full_text[:200] if report.full_text else 'No content'}"

    def _summarize_factset(self, price_data, events: list) -> str:
        """Create summary from FactSet data"""
        parts = []

        if price_data:
            parts.append(f"Price ${price_data.close:.2f} ({price_data.pct_change:+.1f}%)")

        if events:
            event = events[0]
            parts.append(f"{event.event_type}: {event.details[:100]}")

        return " | ".join(parts) if parts else "No recent FactSet data"

    def _create_source_summary(self, state: BatchGraphStatePhase2) -> str:
        """Create concise summary from all sources"""
        parts = []

        # EDGAR
        if state.edgar_filings:
            filing = state.edgar_filings[0]  # Most recent
            parts.append(f"EDGAR: {filing.filing_type} filed {filing.filing_date.strftime('%m/%d')}")

        # BlueMatrix
        if state.bluematrix_reports:
            report = state.bluematrix_reports[0]
            parts.append(f"Analyst: {report.analyst_firm} {report.rating_change} to {report.new_rating}, PT ${report.price_target}")

        # FactSet
        if state.factset_price_data:
            parts.append(f"Price: {state.factset_price_data.pct_change:+.1f}%, volume {state.factset_price_data.volume_vs_avg:.1f}x avg")

        if not parts:
            return "No recent data available"

        return " | ".join(parts)

    async def _regenerate_shorter(self, original: str, ticker: str, company_name: str, summary: str) -> str:
        """Regenerate with stricter word count"""
        messages = f"""
Previous hook was too long ({len(original.split())} words):
"{original}"

Rewrite to EXACTLY 10-12 words. Be more concise.

Data: {summary}
        """.strip()

        response = await self.llm.ainvoke(messages)
        return response.content.strip()


def hook_writer_node(state: BatchGraphStatePhase2, config) -> Dict[str, Any]:
    """LangGraph node for hook generation"""
    logger.info(f"[Hook] Generating for {state.ticker}")

    start_time = time.time()

    agent = HookWriterAgent()
    hook, word_count = asyncio.run(agent.generate(
        state.ticker,
        state.company_name,
        state
    ))

    generation_time = int((time.time() - start_time) * 1000)

    logger.info(f"[Hook] Generated ({word_count} words): {hook}")

    return {
        "hook_summary": hook,
        "hook_word_count": word_count
    }
