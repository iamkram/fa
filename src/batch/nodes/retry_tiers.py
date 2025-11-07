"""Retry nodes with negative prompting for failed fact-checks"""

from typing import Dict, Any
import asyncio
import logging
import time

from src.batch.state import BatchGraphStatePhase2
from src.batch.agents.hook_writer import HookWriterAgent
from src.batch.agents.medium_writer import MediumWriterAgent
from src.batch.agents.expanded_writer import ExpandedWriterAgent
from langchain_anthropic import ChatAnthropic
from src.config.settings import settings

logger = logging.getLogger(__name__)


def retry_hook_node(state: BatchGraphStatePhase2, config) -> Dict[str, Any]:
    """Retry hook generation with negative prompting for failed claims

    Args:
        state: Current batch graph state
        config: Runnable configuration

    Returns:
        Updated state dict with regenerated hook_summary
    """
    logger.info(f"[Retry-Hook] Regenerating for {state.ticker} (attempt {state.hook_retry_count + 1})")

    if not state.hook_fact_check or state.hook_fact_check.overall_status == "passed":
        logger.info(f"[Retry-Hook] No retry needed for {state.ticker}")
        return {}

    if state.hook_retry_count >= 2:
        logger.warning(f"[Retry-Hook] Max retries reached for {state.ticker}")
        return {}

    start_time = time.time()

    try:
        # Build negative prompting from failed claims
        corrections = [
            f"- INCORRECT: '{claim['claim_text']}' - {claim['discrepancy']}"
            for claim in state.hook_fact_check.failed_claims
        ]

        corrections_text = "\n".join(corrections)

        # Create negative prompt
        llm = ChatAnthropic(
            model="claude-sonnet-4-20250514",
            temperature=0.5,
            max_tokens=100,
            anthropic_api_key=settings.anthropic_api_key
        )

        prompt = f"""The previous hook summary for {state.company_name} ({state.ticker}) contained factual errors:

PREVIOUS (INCORRECT):
{state.hook_summary}

ERRORS FOUND:
{corrections_text}

Generate a NEW hook summary (<15 words) that:
1. Avoids the errors listed above
2. Uses only facts verified in source documents
3. Includes specific numbers, dates, and proper attributions
4. Is concise and compelling for social media

Output ONLY the new hook sentence, nothing else."""

        response = asyncio.run(llm.ainvoke(prompt))
        new_hook = response.content.strip()
        word_count = len(new_hook.split())

        generation_time = int((time.time() - start_time) * 1000)
        logger.info(
            f"[Retry-Hook] {state.ticker}: Regenerated ({word_count} words, {generation_time}ms)"
        )

        return {
            "hook_summary": new_hook,
            "hook_word_count": word_count,
            "hook_retry_count": state.hook_retry_count + 1,
            "hook_corrections": [corrections_text]
        }

    except Exception as e:
        logger.error(f"❌ Hook retry failed for {state.ticker}: {str(e)}")
        return {
            "hook_retry_count": state.hook_retry_count + 1
        }


def retry_medium_node(state: BatchGraphStatePhase2, config) -> Dict[str, Any]:
    """Retry medium generation with negative prompting for failed claims

    Args:
        state: Current batch graph state
        config: Runnable configuration

    Returns:
        Updated state dict with regenerated medium_summary
    """
    logger.info(f"[Retry-Medium] Regenerating for {state.ticker} (attempt {state.medium_retry_count + 1})")

    if not state.medium_fact_check or state.medium_fact_check.overall_status == "passed":
        logger.info(f"[Retry-Medium] No retry needed for {state.ticker}")
        return {}

    if state.medium_retry_count >= 2:
        logger.warning(f"[Retry-Medium] Max retries reached for {state.ticker}")
        return {}

    start_time = time.time()

    try:
        # Build negative prompting from failed claims
        corrections = [
            f"- INCORRECT: '{claim['claim_text']}' - {claim['discrepancy']}"
            for claim in state.medium_fact_check.failed_claims
        ]

        corrections_text = "\n".join(corrections)

        # Create negative prompt
        llm = ChatAnthropic(
            model="claude-sonnet-4-20250514",
            temperature=0.3,
            max_tokens=500,
            anthropic_api_key=settings.anthropic_api_key
        )

        prompt = f"""The previous medium summary for {state.company_name} ({state.ticker}) contained factual errors:

PREVIOUS (INCORRECT):
{state.medium_summary}

ERRORS FOUND:
{corrections_text}

Generate a NEW medium summary (75-125 words) that:
1. Avoids ALL errors listed above
2. Uses only facts verified in source documents
3. Includes specific numbers, dates, and proper attributions
4. Maintains professional, factual tone
5. Synthesizes information from multiple sources

Output ONLY the new summary paragraph, nothing else."""

        response = asyncio.run(llm.ainvoke(prompt))
        new_summary = response.content.strip()
        word_count = len(new_summary.split())

        generation_time = int((time.time() - start_time) * 1000)
        logger.info(
            f"[Retry-Medium] {state.ticker}: Regenerated ({word_count} words, {generation_time}ms)"
        )

        return {
            "medium_summary": new_summary,
            "medium_word_count": word_count,
            "medium_retry_count": state.medium_retry_count + 1,
            "medium_corrections": [corrections_text]
        }

    except Exception as e:
        logger.error(f"❌ Medium retry failed for {state.ticker}: {str(e)}")
        return {
            "medium_retry_count": state.medium_retry_count + 1
        }


def retry_expanded_node(state: BatchGraphStatePhase2, config) -> Dict[str, Any]:
    """Retry expanded generation with negative prompting for failed claims

    Args:
        state: Current batch graph state
        config: Runnable configuration

    Returns:
        Updated state dict with regenerated expanded_summary
    """
    logger.info(f"[Retry-Expanded] Regenerating for {state.ticker} (attempt {state.expanded_retry_count + 1})")

    if not state.expanded_fact_check or state.expanded_fact_check.overall_status == "passed":
        logger.info(f"[Retry-Expanded] No retry needed for {state.ticker}")
        return {}

    if state.expanded_retry_count >= 2:
        logger.warning(f"[Retry-Expanded] Max retries reached for {state.ticker}")
        return {}

    start_time = time.time()

    try:
        # Build negative prompting from failed claims
        corrections = [
            f"- INCORRECT: '{claim['claim_text']}' - {claim['discrepancy']}"
            for claim in state.expanded_fact_check.failed_claims
        ]

        corrections_text = "\n".join(corrections)

        # Create negative prompt
        llm = ChatAnthropic(
            model="claude-sonnet-4-20250514",
            temperature=0.3,
            max_tokens=2000,
            anthropic_api_key=settings.anthropic_api_key
        )

        prompt = f"""The previous expanded summary for {state.company_name} ({state.ticker}) contained factual errors:

ERRORS FOUND:
{corrections_text}

Generate a NEW expanded summary (500-750 words, 5 paragraphs) that:
1. Avoids ALL errors listed above
2. Uses only facts verified in source documents
3. Maintains the 5-paragraph structure:
   - Executive Summary
   - Regulatory Developments
   - Analyst Perspective
   - Market Performance
   - Forward-Looking Implications
4. Includes specific numbers, dates, and proper attributions
5. Maintains professional, analytical tone

IMPORTANT: Do NOT include claims that cannot be verified from source documents.

Output ONLY the new expanded summary, nothing else."""

        response = asyncio.run(llm.ainvoke(prompt))
        new_summary = response.content.strip()
        word_count = len(new_summary.split())

        generation_time = int((time.time() - start_time) * 1000)
        logger.info(
            f"[Retry-Expanded] {state.ticker}: Regenerated ({word_count} words, {generation_time}ms)"
        )

        return {
            "expanded_summary": new_summary,
            "expanded_word_count": word_count,
            "expanded_retry_count": state.expanded_retry_count + 1,
            "expanded_corrections": [corrections_text]
        }

    except Exception as e:
        logger.error(f"❌ Expanded retry failed for {state.ticker}: {str(e)}")
        return {
            "expanded_retry_count": state.expanded_retry_count + 1
        }
