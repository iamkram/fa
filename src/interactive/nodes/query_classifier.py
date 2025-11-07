"""
Query Classifier Node

Routes queries between:
- Simple Retrieval: Use pre-generated batch summaries
- Deep Research: Multi-agent research with EDO, news, and memory
"""

from langchain_anthropic import ChatAnthropic
from langchain_core.prompts import load_prompt
import json
import logging
from typing import Dict, Any, Literal

from src.interactive.state import InteractiveGraphState
from src.config.settings import settings

logger = logging.getLogger(__name__)


class QueryClassifierAgent:
    """Classify queries as simple retrieval vs deep research"""

    def __init__(self):
        self.llm = ChatAnthropic(
            model="claude-3-5-haiku-20241022",  # Fast and cheap for classification
            temperature=0.0,
            anthropic_api_key=settings.anthropic_api_key
        )
        self.prompt = load_prompt("prompts/interactive/query_classifier_v1.yaml")

    async def classify(self, query: str, fa_context: Dict[str, Any]) -> Dict[str, Any]:
        """Classify query"""

        # Format FA context
        fa_context_str = f"FA ID: {fa_context.get('fa_id', 'unknown')}"

        messages = self.prompt.format(
            query=query,
            fa_context=fa_context_str
        )

        response = await self.llm.ainvoke(messages)

        try:
            result = json.loads(response.content)
            return result
        except json.JSONDecodeError:
            # Default to deep research if parsing fails
            logger.warning("Failed to parse classifier response, defaulting to deep_research")
            return {
                "classification": "deep_research",
                "confidence": 0.5,
                "reasoning": "Parse error - defaulting to deep research"
            }


def query_classifier_node(state: InteractiveGraphState, config) -> Dict[str, Any]:
    """Classify query for routing"""
    import asyncio

    logger.info(f"[Classifier] Classifying query for FA {state.fa_id}")

    agent = QueryClassifierAgent()
    result = asyncio.run(agent.classify(
        state.sanitized_query or state.query_text,
        {"fa_id": state.fa_id}
    ))

    logger.info(f"[Classifier] Result: {result['classification']} (confidence: {result['confidence']:.2f})")

    return {
        "classification": result["classification"],
        "classification_confidence": result["confidence"]
    }


def route_query(state: InteractiveGraphState) -> Literal["simple", "deep"]:
    """Router function for conditional edge"""
    if state.classification == "simple_retrieval" and state.classification_confidence > 0.8:
        return "simple"
    else:
        return "deep"
