"""
PII (Personally Identifiable Information) Detection

Detects and redacts sensitive information from user queries.
"""

import re
from typing import List, Tuple
import logging

logger = logging.getLogger(__name__)


class PIIDetector:
    """Detect PII in text"""

    # Patterns
    SSN_PATTERN = r'\b\d{3}-\d{2}-\d{4}\b'
    CREDIT_CARD_PATTERN = r'\b\d{4}[- ]?\d{4}[- ]?\d{4}[- ]?\d{4}\b'
    PHONE_PATTERN = r'\b\d{3}[-.●]?\d{3}[-.●]?\d{4}\b'
    EMAIL_PATTERN = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    ACCOUNT_PATTERN = r'\b[Aa]ccount[:\s#]*\d{8,}\b'

    def detect(self, text: str) -> List[Tuple[str, str]]:
        """
        Detect PII in text

        Returns: List of (pii_type, matched_text) tuples
        """
        detected = []

        # SSN
        for match in re.finditer(self.SSN_PATTERN, text):
            detected.append(("ssn", match.group()))
            logger.warning("PII detected: SSN")

        # Credit Card
        for match in re.finditer(self.CREDIT_CARD_PATTERN, text):
            # Simple Luhn check
            if self._is_valid_cc(match.group()):
                detected.append(("credit_card", match.group()))
                logger.warning("PII detected: Credit Card")

        # Phone
        for match in re.finditer(self.PHONE_PATTERN, text):
            detected.append(("phone", match.group()))

        # Email
        for match in re.finditer(self.EMAIL_PATTERN, text):
            detected.append(("email", match.group()))

        # Account number
        for match in re.finditer(self.ACCOUNT_PATTERN, text):
            detected.append(("account_number", match.group()))
            logger.warning("PII detected: Account Number")

        return detected

    def redact(self, text: str, pii_type: str = None) -> str:
        """Redact PII from text"""
        redacted = text

        # Redact all or specific types
        if pii_type is None or pii_type == "ssn":
            redacted = re.sub(self.SSN_PATTERN, "[REDACTED-SSN]", redacted)

        if pii_type is None or pii_type == "credit_card":
            redacted = re.sub(self.CREDIT_CARD_PATTERN, "[REDACTED-CC]", redacted)

        if pii_type is None or pii_type == "account_number":
            redacted = re.sub(self.ACCOUNT_PATTERN, "[REDACTED-ACCOUNT]", redacted)

        # Don't redact phone and email by default (less sensitive in FA context)
        # Only redact if specifically requested
        if pii_type == "phone":
            redacted = re.sub(self.PHONE_PATTERN, "[REDACTED-PHONE]", redacted)

        if pii_type == "email":
            redacted = re.sub(self.EMAIL_PATTERN, "[REDACTED-EMAIL]", redacted)

        return redacted

    def _is_valid_cc(self, cc_number: str) -> bool:
        """Luhn algorithm for credit card validation"""
        cc_number = cc_number.replace("-", "").replace(" ", "")

        if not cc_number.isdigit() or len(cc_number) < 13:
            return False

        # Luhn check
        digits = [int(d) for d in cc_number]
        checksum = 0

        for i in range(len(digits) - 2, -1, -2):
            digits[i] *= 2
            if digits[i] > 9:
                digits[i] -= 9

        return sum(digits) % 10 == 0
