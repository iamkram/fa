from langchain_anthropic import ChatAnthropic
from langchain_core.prompts import load_prompt
from langchain_core.runnables import RunnableConfig
from src.shared.utils.rag import hybrid_search
from src.batch.state import BatchGraphState
from src.config.settings import settings
import logging
import asyncio
import time
from typing import Dict, Any

logger = logging.getLogger(__name__)


class MediumWriterAgent:
    """Agent for generating medium-tier summaries"""

    def __init__(self):
        self.llm = ChatAnthropic(
            model="claude-sonnet-4-20250514",
            temperature=0.3,
            anthropic_api_key=settings.anthropic_api_key
        )
        self.prompt = load_prompt("prompts/batch/medium_writer_v1.yaml")

    async def generate(
        self,
        ticker: str,
        company_name: str,
        edgar_data: str,
        stock_id: str
    ) -> str:
        """Generate medium summary

        Args:
            ticker: Stock ticker
            company_name: Company name
            edgar_data: Formatted EDGAR filing summary
            stock_id: Stock ID for RAG filtering

        Returns:
            Generated summary text
        """
        logger.info(f"Generating medium summary for {ticker}")

        # Retrieve relevant chunks via hybrid RAG
        relevant_chunks = await hybrid_search(
            query=f"material events for {ticker} {company_name}",
            namespaces=["edgar_filings"],
            stock_id=stock_id,
            top_k=10
        )

        # Format chunks
        if relevant_chunks:
            chunks_text = "\n".join([
                f"- {chunk['text'][:200]}..."
                for chunk in relevant_chunks
            ])
        else:
            chunks_text = "No additional context available."

        # Generate summary
        prompt_text = self.prompt.format(
            ticker=ticker,
            company_name=company_name,
            edgar_data=edgar_data,
            relevant_chunks=chunks_text
        )

        response = await self.llm.ainvoke(prompt_text)
        summary = response.content

        logger.info(f"Generated {len(summary.split())} word summary for {ticker}")

        return summary


def medium_writer_node(state: BatchGraphState, config: RunnableConfig) -> Dict[str, Any]:
    """LangGraph node for medium summary generation

    Args:
        state: Current batch graph state
        config: Runnable configuration

    Returns:
        Updated state dict with medium_summary and word_count
    """
    logger.info(f"[MEDIUM WRITER] Generating summary for {state.ticker}")

    if not state.edgar_filings:
        logger.warning(f"No EDGAR filings available for {state.ticker}")
        return {
            "medium_summary": None,
            "word_count": 0,
            "error_message": "No EDGAR data to summarize"
        }

    start_time = time.time()

    try:
        # Format EDGAR data
        edgar_summary = "\n".join([
            f"- {f.filing_type} filed {f.filing_date.strftime('%m/%d/%Y')}: {', '.join(f.material_events)}"
            for f in state.edgar_filings
        ])

        # Generate summary
        agent = MediumWriterAgent()
        summary = asyncio.run(agent.generate(
            ticker=state.ticker,
            company_name=state.company_name,
            edgar_data=edgar_summary,
            stock_id=state.stock_id
        ))

        # Count words
        word_count = len(summary.split())
        generation_time = int((time.time() - start_time) * 1000)

        logger.info(f"✅ Generated {word_count}-word summary for {state.ticker} in {generation_time}ms")

        return {
            "medium_summary": summary,
            "word_count": word_count
        }

    except Exception as e:
        logger.error(f"❌ Summary generation failed for {state.ticker}: {str(e)}")
        return {
            "medium_summary": None,
            "word_count": 0,
            "error_message": f"Summary generation error: {str(e)}"
        }
