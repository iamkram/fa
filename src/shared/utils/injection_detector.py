"""
Prompt Injection Detection

Detects attempts to override system prompts or manipulate LLM behavior.
"""

import re
from typing import List
import logging

logger = logging.getLogger(__name__)


class PromptInjectionDetector:
    """Detect attempts to override system prompts"""

    # Suspicious patterns
    PATTERNS = [
        r"ignore\s+.*(previous|all|above|prior).*\s+instructions",
        r"disregard\s+.*(previous|all|above|prior).*\s+instructions",
        r"forget\s+.*(everything|all|your).*\s+instructions",
        r"new\s+instructions?:",
        r"system\s+prompt:",
        r"you\s+are\s+now\s+a",
        r"act\s+as\s+a\s+(?!financial|advisor)",
        r"roleplay\s+as",
        r"pretend\s+to\s+be",
        r"\[SYSTEM\]",
        r"\[INST\]",
        r"<\|im_start\|>",
        r"jailbreak",
        r"DAN\s+mode",
        r"developer\s+mode",
        r"bypass\s+restrictions"
    ]

    def detect(self, text: str) -> bool:
        """
        Check if text contains prompt injection attempts

        Returns: True if suspicious patterns found
        """
        text_lower = text.lower()

        for pattern in self.PATTERNS:
            if re.search(pattern, text_lower):
                logger.warning(f"Prompt injection detected: {pattern}")
                return True

        return False

    def get_matched_patterns(self, text: str) -> List[str]:
        """Get list of matched suspicious patterns"""
        text_lower = text.lower()
        matched = []

        for pattern in self.PATTERNS:
            if re.search(pattern, text_lower):
                matched.append(pattern)

        return matched
