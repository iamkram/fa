from langchain_anthropic import ChatAnthropic
from langchain_core.prompts import load_prompt
from typing import Dict, Any
import asyncio
import logging
import time

from src.batch.state import BatchGraphStatePhase2
from src.config.settings import settings

logger = logging.getLogger(__name__)


class HookWriterAgent:
    """Agent for generating hook summaries (< 15 words)"""

    def __init__(self):
        self.llm = ChatAnthropic(
            model="claude-sonnet-4-20250514",
            temperature=0.5,  # Slightly higher for creativity
            max_tokens=100,
            anthropic_api_key=settings.anthropic_api_key
        )
        self.prompt = load_prompt("prompts/batch/hook_writer_v1.yaml")

    async def generate(
        self,
        ticker: str,
        company_name: str,
        state: BatchGraphStatePhase2
    ) -> tuple[str, int]:
        """Generate hook summary"""

        # Get most important context from all sources
        all_sources_summary = self._create_source_summary(state)

        # Generate hook
        messages = self.prompt.format(
            ticker=ticker,
            company_name=company_name,
            all_sources_summary=all_sources_summary
        )

        response = await self.llm.ainvoke(messages)
        hook = response.content.strip()

        # Validate word count
        word_count = len(hook.split())
        if word_count > 15:
            logger.warning(f"Hook exceeds 15 words ({word_count}), regenerating...")
            # Try again with stricter instruction
            hook = await self._regenerate_shorter(hook, ticker, company_name, all_sources_summary)
            word_count = len(hook.split())

        return hook, word_count

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
