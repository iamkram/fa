from langchain_anthropic import ChatAnthropic
from langchain_core.prompts import load_prompt
from typing import Dict, Any
import asyncio
import logging
import time

from src.batch.state import BatchGraphStatePhase2
from src.config.settings import settings

logger = logging.getLogger(__name__)


class ExpandedWriterAgent:
    """Agent for generating expanded summaries (500-750 words)"""

    def __init__(self):
        self.llm = ChatAnthropic(
            model="claude-sonnet-4-20250514",
            temperature=0.3,  # Lower for factual accuracy
            max_tokens=2000,
            anthropic_api_key=settings.anthropic_api_key
        )
        self.prompt = load_prompt("prompts/batch/expanded_writer_v1.yaml")

    async def generate(
        self,
        ticker: str,
        company_name: str,
        state: BatchGraphStatePhase2
    ) -> tuple[str, int]:
        """Generate expanded summary"""

        # Extract detailed context from each source
        edgar_context = self._extract_edgar_context(state)
        bluematrix_context = self._extract_bluematrix_context(state)
        factset_context = self._extract_factset_context(state)

        # Generate expanded summary
        messages = self.prompt.format(
            ticker=ticker,
            company_name=company_name,
            edgar_context=edgar_context,
            bluematrix_context=bluematrix_context,
            factset_context=factset_context
        )

        response = await self.llm.ainvoke(messages)
        summary = response.content.strip()

        # Validate word count
        word_count = len(summary.split())

        if word_count < 500:
            logger.warning(f"Summary too short ({word_count} words), regenerating...")
            summary = await self._regenerate_longer(summary, ticker, company_name, edgar_context, bluematrix_context, factset_context)
            word_count = len(summary.split())
        elif word_count > 750:
            logger.warning(f"Summary too long ({word_count} words), regenerating...")
            summary = await self._regenerate_shorter(summary, ticker, company_name, edgar_context, bluematrix_context, factset_context)
            word_count = len(summary.split())

        return summary, word_count

    def _extract_edgar_context(self, state: BatchGraphStatePhase2) -> str:
        """Extract detailed EDGAR filing information"""
        if not state.edgar_filings:
            return "No SEC filings available in the review period."

        parts = []
        for filing in state.edgar_filings[:3]:  # Up to 3 most recent
            filing_summary = f"""
Filing Type: {filing.filing_type}
Accession Number: {filing.accession_number}
Filed: {filing.filing_date.strftime('%Y-%m-%d')}
Items Reported: {', '.join(filing.items_reported)}
Material Events: {', '.join(filing.material_events)}

Key Content:
{filing.full_text[:1000]}...
            """.strip()
            parts.append(filing_summary)

        return "\n\n---\n\n".join(parts)

    def _extract_bluematrix_context(self, state: BatchGraphStatePhase2) -> str:
        """Extract detailed analyst report information"""
        if not state.bluematrix_reports:
            return "No analyst research reports available in the review period."

        parts = []
        for report in state.bluematrix_reports[:5]:  # Up to 5 most recent
            # Build rating change string
            rating_change_str = "N/A"
            if report.rating_change and report.previous_rating and report.new_rating:
                rating_change_str = f"{report.rating_change} from {report.previous_rating} to {report.new_rating}"
            elif report.new_rating:
                rating_change_str = f"Maintained at {report.new_rating}"

            # Build price target string
            pt_str = "N/A"
            if report.price_target:
                if report.previous_price_target:
                    pt_change = ((report.price_target - report.previous_price_target) / report.previous_price_target) * 100
                    pt_str = f"${report.price_target} (prev: ${report.previous_price_target}, {pt_change:+.1f}%)"
                else:
                    pt_str = f"${report.price_target}"

            report_summary = f"""
Analyst Firm: {report.analyst_firm}
Analyst: {report.analyst_name}
Report Date: {report.report_date.strftime('%Y-%m-%d')}
Rating Action: {rating_change_str}
Price Target: {pt_str}

Key Points:
{chr(10).join(f'- {point}' for point in report.key_points[:5])}

Analysis Excerpt:
{report.full_text[:800]}...
            """.strip()
            parts.append(report_summary)

        return "\n\n---\n\n".join(parts)

    def _extract_factset_context(self, state: BatchGraphStatePhase2) -> str:
        """Extract detailed market data information"""
        parts = []

        # Price data
        if state.factset_price_data:
            pd = state.factset_price_data
            price_summary = f"""
PRICE & VOLUME DATA ({pd.date.strftime('%Y-%m-%d')}):
- Open: ${pd.open:.2f}
- Close: ${pd.close:.2f}
- High: ${pd.high:.2f}
- Low: ${pd.low:.2f}
- Daily Change: {pd.pct_change:+.2f}%
- Volume: {pd.volume:,} shares ({pd.volume_vs_avg:.2f}x average)
- Volatility Percentile: {pd.volatility_percentile:.0%} (measures recent volatility vs. historical range)
            """.strip()
            parts.append(price_summary)

        # Fundamental events
        if state.factset_events:
            events_list = []
            for event in state.factset_events[:5]:  # Up to 5 most recent
                event_str = f"- {event.event_type} on {event.timestamp.strftime('%Y-%m-%d')}: {event.details}"
                events_list.append(event_str)

            events_summary = "FUNDAMENTAL EVENTS:\n" + "\n".join(events_list)
            parts.append(events_summary)

        if not parts:
            return "No market data or fundamental events available in the review period."

        return "\n\n".join(parts)

    async def _regenerate_longer(
        self,
        original: str,
        ticker: str,
        company_name: str,
        edgar_context: str,
        bluematrix_context: str,
        factset_context: str
    ) -> str:
        """Regenerate with instruction to expand"""
        messages = f"""
Previous summary was too short ({len(original.split())} words). Target is 500-750 words.

Please expand each section with more detail:
- Add specific financial metrics and percentages
- Include more context about implications
- Expand forward-looking analysis
- Ensure each paragraph meets word count targets

Original summary:
{original}

Data sources remain the same. Generate a longer, more comprehensive version.
        """.strip()

        response = await self.llm.ainvoke(messages)
        return response.content.strip()

    async def _regenerate_shorter(
        self,
        original: str,
        ticker: str,
        company_name: str,
        edgar_context: str,
        bluematrix_context: str,
        factset_context: str
    ) -> str:
        """Regenerate with instruction to condense"""
        messages = f"""
Previous summary was too long ({len(original.split())} words). Target is 500-750 words.

Please condense while retaining key information:
- Remove redundant phrases
- Tighten language
- Focus on most material points
- Maintain 5-paragraph structure

Original summary:
{original}

Generate a more concise version.
        """.strip()

        response = await self.llm.ainvoke(messages)
        return response.content.strip()


def expanded_writer_node(state: BatchGraphStatePhase2, config) -> Dict[str, Any]:
    """LangGraph node for expanded summary generation"""
    logger.info(f"[Expanded] Generating for {state.ticker}")

    start_time = time.time()

    agent = ExpandedWriterAgent()
    summary, word_count = asyncio.run(agent.generate(
        state.ticker,
        state.company_name,
        state
    ))

    generation_time = int((time.time() - start_time) * 1000)

    logger.info(f"[Expanded] Generated ({word_count} words, {generation_time}ms)")
    logger.info(f"[Expanded] Preview: {summary[:200]}...")

    return {
        "expanded_summary": summary,
        "expanded_word_count": word_count
    }
