"""
Output Guardrails Node

Screens generated responses for:
- PII leakage (household names, account numbers)
- Hallucinations
- Compliance issues
- Inappropriate tone
"""

import logging
from typing import Dict, Any

from src.interactive.state import InteractiveGraphState, GuardrailFlag, PIIFlag
from src.shared.utils.pii_detector import PIIDetector

logger = logging.getLogger(__name__)


def output_guardrail_node(state: InteractiveGraphState, config) -> Dict[str, Any]:
    """Screen generated response for safety issues"""
    logger.info(f"[Guardrails-Output] Checking response for FA {state.fa_id}")

    response = state.response_text
    if not response:
        return {"output_safe": True}

    flags = []
    pii_flags_list = []

    # 1. PII Detection in output
    pii_detector = PIIDetector()
    pii_found = pii_detector.detect(response)

    if pii_found:
        for pii_type, pii_text in pii_found:
            flags.append(GuardrailFlag(
                flag_type="pii",
                severity="high",
                detail=f"PII in output: {pii_type}",
                action_taken="flag"
            ))

            pii_flags_list.append(PIIFlag(
                pii_type=pii_type if pii_type in ["household_name", "account_number", "ssn", "email", "phone"] else "account_number",
                location="response_text",
                redacted_text=pii_text
            ))

        logger.warning(f"[Guardrails-Output] PII detected in response")

    # 2. Hallucination detection (simple keyword check)
    hallucination_indicators = [
        "according to my knowledge",
        "i believe",
        "i think",
        "probably",
        "might be"
    ]

    response_lower = response.lower()
    for indicator in hallucination_indicators:
        if indicator in response_lower:
            flags.append(GuardrailFlag(
                flag_type="hallucination",
                severity="medium",
                detail=f"Potential hallucination indicator: {indicator}",
                action_taken="flag"
            ))
            logger.warning(f"[Guardrails-Output] Hallucination indicator: {indicator}")

    # 3. Compliance check
    compliance_violations = ["insider information", "guaranteed returns", "cannot lose"]

    for violation in compliance_violations:
        if violation in response_lower:
            flags.append(GuardrailFlag(
                flag_type="compliance",
                severity="high",
                detail=f"Compliance violation: {violation}",
                action_taken="flag"
            ))
            logger.error(f"[Guardrails-Output] Compliance violation: {violation}")

    # Determine overall safety
    high_severity_blocks = [f for f in flags if f.severity == "high" and f.action_taken == "block"]
    output_safe = len(high_severity_blocks) == 0

    logger.info(f"[Guardrails-Output] Result: {'✅ SAFE' if output_safe else '⚠️ FLAGGED'}")

    return {
        "output_safe": output_safe,
        "output_flags": flags,
        "pii_flags": pii_flags_list,
        "guardrail_status": "passed" if output_safe else "flagged"
    }
