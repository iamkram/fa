from langchain_anthropic import ChatAnthropic
from langchain_core.prompts import load_prompt
from langchain_core.runnables import RunnableConfig
from src.shared.utils.rag import hybrid_search
from src.batch.state import BatchGraphState, BatchGraphStatePhase2
from src.config.settings import settings
import logging
import asyncio
import time
from typing import Dict, Any, Union

logger = logging.getLogger(__name__)


class MediumWriterAgent:
    """Agent for generating medium-tier summaries (75-125 words)"""

    def __init__(self):
        self.llm = ChatAnthropic(
            model="claude-sonnet-4-20250514",
            temperature=0.3,
            max_tokens=500,
            anthropic_api_key=settings.anthropic_api_key
        )
        self.prompt = load_prompt("prompts/batch/medium_writer_v1.yaml")

    async def generate(
        self,
        ticker: str,
        company_name: str,
        state: Union[BatchGraphState, BatchGraphStatePhase2],
        stock_id: str
    ) -> tuple[str, int]:
        """Generate medium summary

        Args:
            ticker: Stock ticker
            company_name: Company name
            state: Batch graph state (Phase 1 or Phase 2)
            stock_id: Stock ID for RAG filtering

        Returns:
            Tuple of (summary text, word count)
        """
        logger.info(f"Generating medium summary for {ticker}")

        # Extract summaries from all sources
        edgar_summary = self._extract_edgar_summary(state)
        bluematrix_summary = self._extract_bluematrix_summary(state)
        factset_summary = self._extract_factset_summary(state)

        # Determine which namespaces to search
        namespaces = ["edgar_filings"]
        if isinstance(state, BatchGraphStatePhase2):
            namespaces.extend(["bluematrix_reports", "factset_data"])

        # Retrieve relevant chunks via hybrid RAG
        relevant_chunks = await hybrid_search(
            query=f"material events and developments for {ticker} {company_name}",
            namespaces=namespaces,
            stock_id=stock_id,
            top_k=15
        )

        # Format chunks
        if relevant_chunks:
            chunks_text = "\n".join([
                f"- {chunk['text'][:200]}..."
                for chunk in relevant_chunks[:10]
            ])
        else:
            chunks_text = "No additional context available."

        # Generate summary
        prompt_text = self.prompt.format(
            ticker=ticker,
            company_name=company_name,
            edgar_summary=edgar_summary,
            bluematrix_summary=bluematrix_summary,
            factset_summary=factset_summary,
            relevant_chunks=chunks_text
        )

        response = await self.llm.ainvoke(prompt_text)
        summary = response.content.strip()

        # Validate word count
        word_count = len(summary.split())
        if word_count < 75:
            logger.warning(f"Summary too short ({word_count} words), regenerating...")
            summary = await self._regenerate_longer(summary, ticker, company_name)
            word_count = len(summary.split())
        elif word_count > 125:
            logger.warning(f"Summary too long ({word_count} words), regenerating...")
            summary = await self._regenerate_shorter(summary, ticker, company_name)
            word_count = len(summary.split())

        logger.info(f"Generated {word_count} word summary for {ticker}")

        return summary, word_count

    def _extract_edgar_summary(self, state: Union[BatchGraphState, BatchGraphStatePhase2]) -> str:
        """Extract concise EDGAR filing summary"""
        if not state.edgar_filings:
            return "No SEC filings in review period."

        parts = []
        for filing in state.edgar_filings[:3]:
            parts.append(
                f"{filing.filing_type} filed {filing.filing_date.strftime('%m/%d')}: "
                f"{', '.join(filing.material_events[:2])}"
            )

        return " | ".join(parts)

    def _extract_bluematrix_summary(self, state: Union[BatchGraphState, BatchGraphStatePhase2]) -> str:
        """Extract concise analyst report summary"""
        # Phase 1 doesn't have bluematrix data
        if isinstance(state, BatchGraphState):
            return "N/A"

        if not state.bluematrix_reports:
            return "No analyst reports in review period."

        parts = []
        for report in state.bluematrix_reports[:2]:
            rating_str = f"{report.analyst_firm}: {report.rating_change or 'Maintained'}"
            if report.new_rating:
                rating_str += f" at {report.new_rating}"
            if report.price_target:
                rating_str += f", PT ${report.price_target}"
            parts.append(rating_str)

        return " | ".join(parts)

    def _extract_factset_summary(self, state: Union[BatchGraphState, BatchGraphStatePhase2]) -> str:
        """Extract concise market data summary"""
        # Phase 1 doesn't have factset data
        if isinstance(state, BatchGraphState):
            return "N/A"

        if not state.factset_price_data:
            return "No market data in review period."

        pd = state.factset_price_data
        summary = f"Price {pd.pct_change:+.1f}% to ${pd.close:.2f}, volume {pd.volume_vs_avg:.1f}x avg"

        # Add significant events
        if state.factset_events:
            event_types = [e.event_type for e in state.factset_events[:2]]
            summary += f" | Events: {', '.join(event_types)}"

        return summary

    async def _regenerate_longer(self, original: str, ticker: str, company_name: str) -> str:
        """Regenerate with instruction to expand"""
        messages = f"""
Previous summary was too short ({len(original.split())} words). Target is 75-125 words.

Add more specific details, metrics, and context while maintaining the single-paragraph format.

Original: {original}

Generate a longer version (75-125 words).
        """.strip()

        response = await self.llm.ainvoke(messages)
        return response.content.strip()

    async def _regenerate_shorter(self, original: str, ticker: str, company_name: str) -> str:
        """Regenerate with instruction to condense"""
        messages = f"""
Previous summary was too long ({len(original.split())} words). Target is 75-125 words.

Condense while retaining key information. Remove less material details.

Original: {original}

Generate a shorter version (75-125 words).
        """.strip()

        response = await self.llm.ainvoke(messages)
        return response.content.strip()


def medium_writer_node(state: Union[BatchGraphState, BatchGraphStatePhase2], config: RunnableConfig) -> Dict[str, Any]:
    """LangGraph node for medium summary generation

    Args:
        state: Current batch graph state (Phase 1 or Phase 2)
        config: Runnable configuration

    Returns:
        Updated state dict with medium_summary and medium_word_count
    """
    logger.info(f"[Medium] Generating summary for {state.ticker}")

    # Check if we have any data to summarize
    has_data = (
        state.edgar_filings or
        (isinstance(state, BatchGraphStatePhase2) and (state.bluematrix_reports or state.factset_price_data))
    )

    if not has_data:
        logger.warning(f"No data available for {state.ticker}")
        return {
            "medium_summary": None,
            "medium_word_count": 0,
            "error_message": "No data to summarize"
        }

    start_time = time.time()

    try:
        # Generate summary
        agent = MediumWriterAgent()
        summary, word_count = asyncio.run(agent.generate(
            ticker=state.ticker,
            company_name=state.company_name,
            state=state,
            stock_id=state.stock_id
        ))

        generation_time = int((time.time() - start_time) * 1000)

        logger.info(f"[Medium] Generated ({word_count} words, {generation_time}ms)")

        return {
            "medium_summary": summary,
            "medium_word_count": word_count
        }

    except Exception as e:
        logger.error(f"❌ Medium summary generation failed for {state.ticker}: {str(e)}")
        return {
            "medium_summary": None,
            "medium_word_count": 0,
            "error_message": f"Summary generation error: {str(e)}"
        }
