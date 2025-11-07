"""
Fact Verification Node

Performs lightweight fact-checking on generated responses.
For interactive queries, we use lighter verification than batch processing.
"""

import logging
from typing import Dict, Any

from src.interactive.state import InteractiveGraphState

logger = logging.getLogger(__name__)


def fact_verification_node(state: InteractiveGraphState, config) -> Dict[str, Any]:
    """Verify facts in response against source context"""
    logger.info(f"[FactVerify] Checking response for FA {state.fa_id}")

    # For MVP: Simple validation checks
    # In production: Use LLM-based verification like batch process

    response = state.response_text
    flags = []

    # 1. Check for unsupported claims
    unsupported_phrases = [
        "guarantee",
        "will definitely",
        "cannot fail",
        "risk-free",
        "always"
    ]

    for phrase in unsupported_phrases:
        if phrase in response.lower():
            logger.warning(f"[FactVerify] Unsupported claim: {phrase}")
            flags.append(f"unsupported_claim_{phrase}")

    # 2. Check for specific numbers without context
    import re
    numbers = re.findall(r'\$[\d,]+', response)
    if len(numbers) > 5:
        logger.warning(f"[FactVerify] Many specific numbers without source citations")

    # For interactive MVP, we pass unless critical issues found
    verification_passed = len(flags) == 0

    logger.info(f"[FactVerify] Result: {'✅ PASSED' if verification_passed else '⚠️ FLAGGED'}")

    return {
        "confidence_score": 0.9 if verification_passed else 0.7
    }
