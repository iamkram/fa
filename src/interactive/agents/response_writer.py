"""
Response Writer Agent

Generates personalized FA responses based on assembled context.
"""

from langchain_anthropic import ChatAnthropic
import logging
from typing import Dict, Any
import time

from src.interactive.state import InteractiveGraphState, AssembledContextState
from src.config.settings import settings

logger = logging.getLogger(__name__)


class ResponseWriterAgent:
    """Generate personalized responses for FAs"""

    def __init__(self):
        self.llm = ChatAnthropic(
            model="claude-sonnet-4-20250514",
            temperature=0.3,
            max_tokens=2000,
            anthropic_api_key=settings.anthropic_api_key
        )

    async def generate_response(
        self,
        query: str,
        assembled_context: AssembledContextState
    ) -> str:
        """Generate personalized FA response"""

        # Build context summary
        context_parts = []

        # FA context
        if assembled_context.fa_context and assembled_context.fa_context.fa_profile:
            fa = assembled_context.fa_context.fa_profile
            context_parts.append(f"FA Profile: {fa.name} ({fa.region}, {fa.client_count} clients, ${fa.aum/1e6:.1f}M AUM)")

            if assembled_context.fa_context.total_exposure:
                exposure_str = ", ".join([
                    f"{ticker}: ${value/1e3:.0f}K"
                    for ticker, value in list(assembled_context.fa_context.total_exposure.items())[:5]
                ])
                context_parts.append(f"Client Portfolio Exposure: {exposure_str}")

        # Batch summary
        if assembled_context.batch_summary:
            context_parts.append(f"Pre-generated Summary:\n{assembled_context.batch_summary.get('text', '')}")

        # Breaking news
        if assembled_context.breaking_news:
            news_str = "\n".join([
                f"- {item.headline} ({item.source})"
                for item in assembled_context.breaking_news[:3]
            ])
            context_parts.append(f"Breaking News:\n{news_str}")

        # Historical data
        if assembled_context.historical_data:
            chunks_str = "\n".join([
                f"- {chunk.text[:200]}..."
                for chunk in assembled_context.historical_data[:3]
            ])
            context_parts.append(f"Historical Data:\n{chunks_str}")

        context_text = "\n\n".join(context_parts)

        # Build prompt with enhanced citation requirements
        prompt = f"""You are a Financial Advisor AI Assistant providing personalized support with strict factual accuracy.

Query: {query}

Query Intent: {assembled_context.query_intent}

Context:
{context_text}

CRITICAL INSTRUCTIONS - FACT-GROUNDED RESPONSE:
1. Base EVERY factual claim on the provided context - do not make unsupported claims
2. When citing numbers or data, include source attribution (e.g., "according to the latest 10-Q", "based on portfolio analysis", "per recent news from [source]")
3. If household exposure is mentioned, be specific about impact with exact figures
4. Use phrases like "per", "according to", "based on", "from" when stating facts
5. If you cannot find specific information in the context, explicitly say "Based on available data..." or "While specific details on X aren't provided..."
6. Keep response concise but informative (200-400 words)
7. Use professional financial advisory tone
8. NEVER make guarantees, absolute predictions, or unsupported claims
9. Include appropriate disclaimers for forward-looking statements

CITATION REQUIREMENTS:
- For market data: Include source and date
- For financial metrics: Reference specific document (10-K, 10-Q, earnings report)
- For news items: Include publication and date
- For portfolio exposure: Reference portfolio analysis source

Generate your fact-grounded, properly cited response:"""

        response = await self.llm.ainvoke(prompt)

        return response.content


def response_writer_node(state: InteractiveGraphState, config) -> Dict[str, Any]:
    """Generate personalized response"""
    import asyncio

    logger.info(f"[ResponseWriter] Generating response for FA {state.fa_id}")

    start_time = time.time()

    try:
        agent = ResponseWriterAgent()

        response_text = asyncio.run(agent.generate_response(
            query=state.sanitized_query,
            assembled_context=state.assembled_context
        ))

        generation_time = int((time.time() - start_time) * 1000)

        logger.info(f"[ResponseWriter] Generated response ({len(response_text)} chars, {generation_time}ms)")

        return {
            "response_text": response_text,
            "response_tier": "medium",  # Default tier for deep research
            "total_processing_time_ms": generation_time
        }

    except Exception as e:
        logger.error(f"[ResponseWriter] Failed: {str(e)}")
        return {
            "response_text": "I apologize, but I encountered an error generating your response. Please try again.",
            "error_message": f"Response generation failed: {str(e)}"
        }
