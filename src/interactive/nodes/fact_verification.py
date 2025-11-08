"""
Fact Verification Node

Enhanced LLM-based fact-checking on generated responses.
Uses hallucination detection to verify claims against source documents.
"""

import logging
import asyncio
import time
from typing import Dict, Any, List
import re

from src.interactive.state import InteractiveGraphState
from src.interactive.guardrails import detect_hallucinations

logger = logging.getLogger(__name__)


def extract_sources_from_context(state: InteractiveGraphState) -> List[Dict[str, Any]]:
    """Extract source documents from assembled context for verification"""
    sources = []

    if not state.assembled_context:
        return sources

    # Extract from batch summary
    if state.assembled_context.batch_summary:
        summary = state.assembled_context.batch_summary
        sources.append({
            "type": "batch_summary",
            "content": summary.get("text", ""),
            "metadata": {
                "source": summary.get("source_type", "unknown"),
                "ticker": summary.get("ticker")
            }
        })

    # Extract from historical data chunks
    if state.assembled_context.historical_data:
        for i, chunk in enumerate(state.assembled_context.historical_data[:5]):  # Limit to 5 chunks
            sources.append({
                "type": "historical_data",
                "content": chunk.text,
                "metadata": {
                    "source": chunk.metadata.get("source", "unknown"),
                    "chunk_index": i
                }
            })

    # Extract from breaking news
    if state.assembled_context.breaking_news:
        for i, news in enumerate(state.assembled_context.breaking_news[:3]):  # Limit to 3 news items
            sources.append({
                "type": "breaking_news",
                "content": f"{news.headline}: {news.summary}",
                "metadata": {
                    "source": news.source,
                    "published_at": str(news.published_at)
                }
            })

    # Extract from FA context exposure data
    if state.assembled_context.fa_context and state.assembled_context.fa_context.total_exposure:
        exposure_str = ", ".join([
            f"{ticker}: ${value/1e3:.0f}K"
            for ticker, value in list(state.assembled_context.fa_context.total_exposure.items())[:10]
        ])
        sources.append({
            "type": "fa_exposure",
            "content": f"Client portfolio exposure data: {exposure_str}",
            "metadata": {
                "source": "fa_portfolio_analysis"
            }
        })

    return sources


async def _run_llm_fact_verification(response: str, sources: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Run LLM-based hallucination detection"""
    try:
        result = await detect_hallucinations(response, sources)
        return result
    except Exception as e:
        logger.error(f"LLM fact verification failed: {e}")
        return {
            "hallucinations_detected": False,
            "hallucination_items": [],
            "confidence": 0.5
        }


def fact_verification_node(state: InteractiveGraphState, config) -> Dict[str, Any]:
    """
    Enhanced fact verification with hybrid approach:
    - Stage 1: Fast keyword checks for obvious issues
    - Stage 2: LLM-based hallucination detection against sources
    """
    logger.info(f"[FactVerify] Checking response for FA {state.fa_id}")

    start_time = time.time()

    response = state.response_text
    if not response:
        return {"confidence_score": 1.0}

    flags = []
    confidence_penalties = []

    # ========================================================================
    # STAGE 1: Fast Keyword Checks
    # ========================================================================

    # 1. Check for unsupported claims (keywords)
    unsupported_phrases = [
        "guarantee",
        "will definitely",
        "cannot fail",
        "risk-free",
        "always",
        "never",
        "100% certain"
    ]

    for phrase in unsupported_phrases:
        if phrase in response.lower():
            logger.warning(f"[FactVerify] Unsupported claim (keyword): {phrase}")
            flags.append(f"unsupported_claim_{phrase}")
            confidence_penalties.append(0.1)

    # 2. Check for excessive specific numbers without citations
    numbers = re.findall(r'\$[\d,]+(?:\.\d{1,2})?[BMK]?', response)
    citation_markers = len(re.findall(r'(?:per|according to|from|source:|based on)', response, re.IGNORECASE))

    if len(numbers) > 3 and citation_markers == 0:
        logger.warning(f"[FactVerify] {len(numbers)} numbers with no citation markers")
        confidence_penalties.append(0.05)

    # ========================================================================
    # STAGE 2: LLM-Based Hallucination Detection
    # ========================================================================

    llm_verification_performed = False
    hallucination_details = []

    try:
        # Extract sources from assembled context
        sources = extract_sources_from_context(state)

        if sources:
            logger.info(f"[FactVerify] Running LLM verification against {len(sources)} sources")

            # Run LLM hallucination detection
            llm_result = asyncio.run(_run_llm_fact_verification(response, sources))
            llm_verification_performed = True

            # Process LLM results
            if llm_result.get("hallucinations_detected"):
                hallucination_items = llm_result.get("hallucination_items", [])
                logger.warning(f"[FactVerify] LLM detected {len(hallucination_items)} potential hallucinations")

                for item in hallucination_items:
                    claim = item.get("claim", "")
                    reason = item.get("reason", "")
                    severity = item.get("severity", "medium")

                    hallucination_details.append({
                        "claim": claim,
                        "reason": reason,
                        "severity": severity
                    })

                    # Apply confidence penalties based on severity
                    if severity == "high":
                        confidence_penalties.append(0.2)
                    elif severity == "medium":
                        confidence_penalties.append(0.1)
                    else:  # low
                        confidence_penalties.append(0.05)

                    flags.append(f"hallucination_{severity}")

            # LLM confidence score
            llm_confidence = llm_result.get("confidence", 0.8)
            if llm_confidence < 0.7:
                confidence_penalties.append(0.1)

        else:
            logger.info(f"[FactVerify] No sources available for LLM verification, using keyword checks only")

    except Exception as e:
        logger.error(f"[FactVerify] LLM verification failed: {e}")
        # Continue with keyword results only

    # ========================================================================
    # Calculate Final Confidence Score
    # ========================================================================

    # Start with base confidence
    base_confidence = 0.95

    # Apply penalties
    total_penalty = sum(confidence_penalties)
    final_confidence = max(0.5, base_confidence - total_penalty)

    # Determine verification status
    verification_passed = final_confidence >= 0.8 and not any(
        "high" in flag for flag in flags
    )

    verification_time = int((time.time() - start_time) * 1000)

    logger.info(
        f"[FactVerify] Result: {'✅ PASSED' if verification_passed else '⚠️ FLAGGED'} "
        f"(confidence: {final_confidence:.2f}, {verification_time}ms, "
        f"LLM: {'yes' if llm_verification_performed else 'no'})"
    )

    # Prepare detailed verification report
    verification_report = {
        "confidence_score": final_confidence,
        "verification_passed": verification_passed,
        "llm_verification_performed": llm_verification_performed,
        "flags": flags,
        "hallucination_details": hallucination_details if hallucination_details else None,
        "source_count": len(sources) if 'sources' in locals() else 0,
        "verification_time_ms": verification_time
    }

    return verification_report
