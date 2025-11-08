"""
Input Guardrails Node

Screens user input for safety issues:
- PII detection and redaction (regex + LLM)
- Prompt injection attempts (regex + LLM)
- Off-topic queries (keyword + LLM)
- Compliance keywords

Uses hybrid approach: fast regex checks + LLM validation for edge cases.
"""

import logging
import asyncio
import time
from typing import Dict, Any

from src.interactive.state import InteractiveGraphState, GuardrailFlag
from src.shared.utils.pii_detector import PIIDetector
from src.shared.utils.injection_detector import PromptInjectionDetector
from src.interactive.guardrails import (
    validate_input_pii,
    detect_prompt_injection,
    classify_topic
)
from src.shared.monitoring.guardrail_metrics import guardrail_metrics

logger = logging.getLogger(__name__)


async def _run_llm_validations(query: str, sanitized: str, pii_found: bool) -> Dict[str, Any]:
    """Run LLM validations in parallel for efficiency"""
    llm_results = {}

    try:
        # Determine which LLM validations to run
        tasks = []
        task_names = []

        # 1. PII validation: Run if query mentions client/household but no regex match
        query_lower = query.lower()
        if not pii_found and ("client" in query_lower or "household" in query_lower):
            tasks.append(validate_input_pii(query))
            task_names.append("pii")

        # 2. Topic classification: Always run (fast)
        tasks.append(classify_topic(query))
        task_names.append("topic")

        # 3. Injection detection: Run if query is long or has suspicious patterns
        if len(query) > 100 or any(word in query_lower for word in ["ignore", "system", "prompt", "instructions"]):
            tasks.append(detect_prompt_injection(query))
            task_names.append("injection")

        # Run all LLM validations in parallel
        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)

            for name, result in zip(task_names, results):
                if isinstance(result, Exception):
                    logger.warning(f"LLM validation failed for {name}: {result}")
                else:
                    llm_results[name] = result

    except Exception as e:
        logger.error(f"Failed to run LLM validations: {e}")

    return llm_results


def input_guardrail_node(state: InteractiveGraphState, config) -> Dict[str, Any]:
    """Screen user input for safety issues (hybrid regex + LLM)"""
    logger.info(f"[Guardrails-Input] Checking query for FA {state.fa_id}")

    start_time = time.time()
    query = state.query_text
    flags = []
    llm_performed = False

    # ========================================================================
    # STAGE 1: Fast Regex/Keyword Checks
    # ========================================================================

    # 1. PII Detection (regex)
    pii_detector = PIIDetector()
    pii_found = pii_detector.detect(query)
    regex_pii_detected = bool(pii_found)

    if pii_found:
        for pii_type, pii_text in pii_found:
            flags.append(GuardrailFlag(
                flag_type="pii",
                severity="high" if pii_type in ["ssn", "credit_card", "account_number"] else "medium",
                detail=f"PII detected (regex): {pii_type}",
                action_taken="redact"
            ))

        # Redact from query
        sanitized = pii_detector.redact(query)
        logger.warning(f"[Guardrails-Input] PII detected and redacted (regex)")
    else:
        sanitized = query

    # 2. Prompt Injection Detection (regex)
    injection_detector = PromptInjectionDetector()
    regex_injection_detected = injection_detector.detect(query)

    if regex_injection_detected:
        patterns = injection_detector.get_matched_patterns(query)
        flags.append(GuardrailFlag(
            flag_type="injection",
            severity="high",
            detail=f"Prompt injection detected (regex): {patterns[0]}",
            action_taken="block"
        ))
        logger.error(f"[Guardrails-Input] BLOCKED - Prompt injection detected (regex)")

        return {
            "input_safe": False,
            "input_flags": flags,
            "sanitized_query": sanitized,
            "response_text": "I cannot process that request. Please rephrase your question about financial markets or portfolios.",
            "output_safe": False  # Skip processing
        }

    # 3. Off-Topic Detection (keyword)
    financial_keywords = [
        "stock", "portfolio", "holding", "market", "earnings", "price",
        "investment", "trade", "fund", "share", "dividend", "analyst",
        "filing", "sec", "revenue", "quarter", "household", "client",
        "equity", "bond", "asset", "risk", "return", "valuation"
    ]

    query_lower = query.lower()
    has_financial_keyword = any(kw in query_lower for kw in financial_keywords)

    if not has_financial_keyword and len(query.split()) > 3:
        flags.append(GuardrailFlag(
            flag_type="off_topic",
            severity="low",
            detail="Query may not be finance-related (keyword check)",
            action_taken="flag"
        ))
        logger.info(f"[Guardrails-Input] Possible off-topic query (keyword)")

    # 4. Compliance Keywords
    compliance_keywords = ["insider", "manipulation", "pump", "dump", "guaranteed"]

    for keyword in compliance_keywords:
        if keyword in query_lower:
            flags.append(GuardrailFlag(
                flag_type="compliance",
                severity="medium",
                detail=f"Compliance keyword detected: {keyword}",
                action_taken="flag"
            ))
            logger.warning(f"[Guardrails-Input] Compliance keyword: {keyword}")

    # ========================================================================
    # STAGE 2: LLM Validation (for edge cases)
    # ========================================================================

    try:
        # Run LLM validations (async)
        llm_results = asyncio.run(_run_llm_validations(query, sanitized, regex_pii_detected))
        llm_performed = bool(llm_results)  # Mark LLM as performed if we got results

        # Process LLM PII results
        if "pii" in llm_results:
            pii_result = llm_results["pii"]
            if pii_result.get("pii_detected") and pii_result.get("risk_level") in ["medium", "high"]:
                for item in pii_result.get("pii_items", []):
                    flags.append(GuardrailFlag(
                        flag_type="pii",
                        severity=pii_result["risk_level"],
                        detail=f"PII detected (LLM): {item.get('type')} - {item.get('text', 'redacted')}",
                        action_taken="flag"
                    ))
                logger.warning(f"[Guardrails-Input] PII detected by LLM: {pii_result['risk_level']}")

        # Process LLM injection results
        if "injection" in llm_results:
            injection_result = llm_results["injection"]
            if injection_result.get("injection_detected") and injection_result.get("confidence", 0) > 0.7:
                flags.append(GuardrailFlag(
                    flag_type="injection",
                    severity="high",
                    detail=f"Prompt injection detected (LLM): {injection_result.get('injection_type')}",
                    action_taken="block"
                ))
                logger.error(f"[Guardrails-Input] BLOCKED - Prompt injection detected (LLM)")

                return {
                    "input_safe": False,
                    "input_flags": flags,
                    "sanitized_query": sanitized,
                    "response_text": "I cannot process that request. Please rephrase your question about financial markets or portfolios.",
                    "output_safe": False  # Skip processing
                }

        # Process LLM topic results
        if "topic" in llm_results:
            topic_result = llm_results["topic"]
            if not topic_result.get("on_topic") and topic_result.get("confidence", 0) > 0.7:
                flags.append(GuardrailFlag(
                    flag_type="off_topic",
                    severity="medium",
                    detail=f"Off-topic query (LLM): {topic_result.get('topic_category')}",
                    action_taken="flag"
                ))
                logger.warning(f"[Guardrails-Input] Off-topic query detected (LLM): {topic_result.get('reasoning')}")

    except Exception as e:
        logger.error(f"LLM validation failed: {e}")
        # Continue with regex results only

    # ========================================================================
    # Determine Overall Safety
    # ========================================================================

    high_severity_flags = [f for f in flags if f.severity == "high" and f.action_taken == "block"]
    input_safe = len(high_severity_flags) == 0

    logger.info(f"[Guardrails-Input] Result: {'✅ SAFE' if input_safe else '🚫 BLOCKED'} (regex + LLM)")

    # Track metrics
    processing_time_ms = int((time.time() - start_time) * 1000)
    guardrail_metrics.track_input_guardrail(
        session_id=state.session_id,
        query_id=state.query_id if hasattr(state, 'query_id') else state.session_id,
        flags=flags,
        input_safe=input_safe,
        llm_performed=llm_performed,
        processing_time_ms=processing_time_ms
    )

    return {
        "input_safe": input_safe,
        "input_flags": flags,
        "sanitized_query": sanitized
    }
