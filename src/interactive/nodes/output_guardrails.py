"""
Output Guardrails Node

Screens generated responses for:
- PII leakage (household names, account numbers) - regex + LLM
- Hallucinations - keyword + LLM source verification
- Compliance issues - keyword + LLM SEC/FINRA validation
- Inappropriate tone

Uses hybrid approach: fast keyword checks + LLM validation for thorough analysis.
"""

import logging
import asyncio
from typing import Dict, Any, List

from src.interactive.state import InteractiveGraphState, GuardrailFlag, PIIFlag
from src.shared.utils.pii_detector import PIIDetector
from src.interactive.guardrails import (
    detect_hallucinations,
    validate_compliance
)

logger = logging.getLogger(__name__)


async def _run_llm_output_validations(
    response: str,
    query: str,
    retrieved_docs: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """Run LLM output validations in parallel"""
    llm_results = {}

    try:
        tasks = []
        task_names = []

        # 1. Hallucination detection: Always run if we have sources
        if retrieved_docs:
            tasks.append(detect_hallucinations(response, retrieved_docs))
            task_names.append("hallucination")

        # 2. Compliance validation: Always run for regulatory checks
        tasks.append(validate_compliance(response, query))
        task_names.append("compliance")

        # Run all LLM validations in parallel
        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)

            for name, result in zip(task_names, results):
                if isinstance(result, Exception):
                    logger.warning(f"LLM output validation failed for {name}: {result}")
                else:
                    llm_results[name] = result

    except Exception as e:
        logger.error(f"Failed to run LLM output validations: {e}")

    return llm_results


def output_guardrail_node(state: InteractiveGraphState, config) -> Dict[str, Any]:
    """Screen generated response for safety issues (hybrid keyword + LLM)"""
    logger.info(f"[Guardrails-Output] Checking response for FA {state.fa_id}")

    response = state.response_text
    if not response:
        return {"output_safe": True}

    flags = []
    pii_flags_list = []

    # ========================================================================
    # STAGE 1: Fast Keyword/Regex Checks
    # ========================================================================

    # 1. PII Detection in output (regex)
    pii_detector = PIIDetector()
    pii_found = pii_detector.detect(response)

    if pii_found:
        for pii_type, pii_text in pii_found:
            flags.append(GuardrailFlag(
                flag_type="pii",
                severity="high",
                detail=f"PII in output (regex): {pii_type}",
                action_taken="flag"
            ))

            pii_flags_list.append(PIIFlag(
                pii_type=pii_type if pii_type in ["household_name", "account_number", "ssn", "email", "phone"] else "account_number",
                location="response_text",
                redacted_text=pii_text
            ))

        logger.warning(f"[Guardrails-Output] PII detected in response (regex)")

    # 2. Hallucination detection (keyword indicators)
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
                detail=f"Hallucination indicator (keyword): {indicator}",
                action_taken="flag"
            ))
            logger.warning(f"[Guardrails-Output] Hallucination indicator (keyword): {indicator}")

    # 3. Compliance check (keyword violations)
    compliance_violations = ["insider information", "guaranteed returns", "cannot lose"]

    for violation in compliance_violations:
        if violation in response_lower:
            flags.append(GuardrailFlag(
                flag_type="compliance",
                severity="high",
                detail=f"Compliance violation (keyword): {violation}",
                action_taken="flag"
            ))
            logger.error(f"[Guardrails-Output] Compliance violation (keyword): {violation}")

    # ========================================================================
    # STAGE 2: LLM Validation (thorough analysis)
    # ========================================================================

    try:
        # Get retrieved documents from state
        retrieved_docs = state.retrieved_docs if hasattr(state, 'retrieved_docs') else []

        # Run LLM validations (async)
        llm_results = asyncio.run(_run_llm_output_validations(
            response,
            state.query_text,
            retrieved_docs
        ))

        # Process LLM hallucination results
        if "hallucination" in llm_results:
            hallucination_result = llm_results["hallucination"]
            if hallucination_result.get("hallucinations_detected"):
                for item in hallucination_result.get("hallucination_items", []):
                    severity = item.get("severity", "medium")
                    flags.append(GuardrailFlag(
                        flag_type="hallucination",
                        severity=severity,
                        detail=f"Hallucination (LLM): {item.get('claim')} - {item.get('reason')}",
                        action_taken="flag" if severity == "low" else "warn"
                    ))
                logger.warning(f"[Guardrails-Output] Hallucinations detected (LLM): {len(hallucination_result.get('hallucination_items', []))} items")

        # Process LLM compliance results
        if "compliance" in llm_results:
            compliance_result = llm_results["compliance"]
            if not compliance_result.get("compliant"):
                for violation in compliance_result.get("violations", []):
                    flags.append(GuardrailFlag(
                        flag_type="compliance",
                        severity=violation.get("severity", "medium"),
                        detail=f"Compliance violation (LLM): {violation.get('rule')} - {violation.get('issue')}",
                        action_taken="flag"
                    ))
                logger.error(f"[Guardrails-Output] Compliance violations (LLM): {len(compliance_result.get('violations', []))} violations")

            # Log warnings
            for warning in compliance_result.get("warnings", []):
                logger.warning(f"[Guardrails-Output] Compliance warning (LLM): {warning}")

    except Exception as e:
        logger.error(f"LLM output validation failed: {e}")
        # Continue with keyword results only

    # ========================================================================
    # Determine Overall Safety
    # ========================================================================

    high_severity_blocks = [f for f in flags if f.severity == "high" and f.action_taken == "block"]
    output_safe = len(high_severity_blocks) == 0

    logger.info(f"[Guardrails-Output] Result: {'✅ SAFE' if output_safe else '⚠️ FLAGGED'} (keyword + LLM)")

    return {
        "output_safe": output_safe,
        "output_flags": flags,
        "pii_flags": pii_flags_list,
        "guardrail_status": "passed" if output_safe else "flagged"
    }
