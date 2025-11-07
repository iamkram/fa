"""
Input Guardrails Node

Screens user input for safety issues:
- PII detection and redaction
- Prompt injection attempts
- Off-topic queries
- Compliance keywords
"""

import logging
from typing import Dict, Any

from src.interactive.state import InteractiveGraphState, GuardrailFlag
from src.shared.utils.pii_detector import PIIDetector
from src.shared.utils.injection_detector import PromptInjectionDetector

logger = logging.getLogger(__name__)


def input_guardrail_node(state: InteractiveGraphState, config) -> Dict[str, Any]:
    """Screen user input for safety issues"""
    logger.info(f"[Guardrails-Input] Checking query for FA {state.fa_id}")

    query = state.query_text
    flags = []

    # 1. PII Detection
    pii_detector = PIIDetector()
    pii_found = pii_detector.detect(query)

    if pii_found:
        for pii_type, pii_text in pii_found:
            flags.append(GuardrailFlag(
                flag_type="pii",
                severity="high" if pii_type in ["ssn", "credit_card", "account_number"] else "medium",
                detail=f"PII detected: {pii_type}",
                action_taken="redact"
            ))

        # Redact from query
        sanitized = pii_detector.redact(query)
        logger.warning(f"[Guardrails-Input] PII detected and redacted")
    else:
        sanitized = query

    # 2. Prompt Injection Detection
    injection_detector = PromptInjectionDetector()

    if injection_detector.detect(query):
        patterns = injection_detector.get_matched_patterns(query)
        flags.append(GuardrailFlag(
            flag_type="injection",
            severity="high",
            detail=f"Prompt injection attempt detected: {patterns[0]}",
            action_taken="block"
        ))
        logger.error(f"[Guardrails-Input] BLOCKED - Prompt injection detected")

        return {
            "input_safe": False,
            "input_flags": flags,
            "sanitized_query": sanitized,
            "response_text": "I cannot process that request. Please rephrase your question about financial markets or portfolios.",
            "output_safe": False  # Skip processing
        }

    # 3. Off-Topic Detection (simple keyword check)
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
            detail="Query may not be finance-related",
            action_taken="flag"
        ))
        logger.info(f"[Guardrails-Input] Possible off-topic query")

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

    # Determine overall safety
    high_severity_flags = [f for f in flags if f.severity == "high" and f.action_taken == "block"]
    input_safe = len(high_severity_flags) == 0

    logger.info(f"[Guardrails-Input] Result: {'✅ SAFE' if input_safe else '🚫 BLOCKED'}")

    return {
        "input_safe": input_safe,
        "input_flags": flags,
        "sanitized_query": sanitized
    }
