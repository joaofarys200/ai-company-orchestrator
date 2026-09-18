"""
JARVIS OS — Phase 63: Cross-Project Engineering Learning & Verification Transfer
Module: security.py
CrossProjectSecurityFilter enforces quarantine on external knowledge.
Treats all external knowledge as untrusted and sanitizes against prompt injection,
secrets exfiltration, destructive shell calls, payment primitives, and privilege leaks.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

from .models import EngineeringKnowledgeItem


class CrossProjectSecurityFilter:
    """Multi-layer security sentinel filtering out malicious, destructive, or confidential payloads."""

    SECRET_PATTERNS = [
        re.compile(r"api[_-]?key\s*[:=]\s*['\"][A-Za-z0-9_\-]{16,}['\"]", re.IGNORECASE),
        re.compile(r"(AWS_SECRET_ACCESS_KEY|PRIVATE_KEY|id_rsa|API_SECRET)", re.IGNORECASE),
        re.compile(r"bearer\s+[A-Za-z0-9\-\._~\+\/]+=*", re.IGNORECASE),
        re.compile(r"(password|passwd)\s*[:=]\s*['\"][^'\"]{6,}['\"]", re.IGNORECASE),
        re.compile(r"-----BEGIN (RSA|EC|OPENSSH) PRIVATE KEY-----", re.IGNORECASE),
    ]

    DESTRUCTIVE_PATTERNS = [
        re.compile(r"(rm\s+-rf|rmdir\s+/s|format\s+[a-z]:|del\s+/[fF])", re.IGNORECASE),
        re.compile(r"(shutil\.)?rmtree\b", re.IGNORECASE),
        re.compile(r"os\.system\b", re.IGNORECASE),
        re.compile(r"subprocess\.(Popen|run|call)\b", re.IGNORECASE),
        re.compile(r"DROP\s+TABLE|DELETE\s+FROM\s+(users|credentials|tokens)", re.IGNORECASE),
        re.compile(r"(curl|wget|Invoke-WebRequest)\s+.*(https?|ftp)", re.IGNORECASE),
        re.compile(r"eval\(|exec\(", re.IGNORECASE),
    ]

    FINANCIAL_PATTERNS = [
        re.compile(r"(stripe|paypal|braintree)\.(Charge|Payment|Transfer|Refund)\b", re.IGNORECASE),
        re.compile(r"send_payment\b|process_live_transaction\b", re.IGNORECASE),
        re.compile(r"credit_card_number|cvv2?|card_exp", re.IGNORECASE),
    ]

    INJECTION_PATTERNS = [
        re.compile(r"ignore\s+(all\s+)?(previous|prior)\s+instructions", re.IGNORECASE),
        re.compile(r"<\s*(/?\s*(?:system|admin|eval|exec)[^>]*)>", re.IGNORECASE),
        re.compile(r"bypass\s+(security|sentinel|gate)", re.IGNORECASE),
    ]

    @classmethod
    def inspect_text(cls, text: str) -> Tuple[bool, Optional[str]]:
        """Inspect a string for prohibited or confidential content."""
        if not text:
            return True, None

        for pat in cls.SECRET_PATTERNS:
            if pat.search(text):
                return False, "Confidential credential or token detected"

        for pat in cls.DESTRUCTIVE_PATTERNS:
            if pat.search(text):
                return False, "Destructive system or filesystem command detected"

        for pat in cls.FINANCIAL_PATTERNS:
            if pat.search(text):
                return False, "Live financial or payment processing primitive detected"

        for pat in cls.INJECTION_PATTERNS:
            if pat.search(text):
                return False, "Prompt injection or authority bypass pattern detected"

        return True, None

    @classmethod
    def sanitize_item(cls, item: EngineeringKnowledgeItem) -> Tuple[bool, Optional[str]]:
        """
        Scan all serialized properties of an EngineeringKnowledgeItem.
        Returns (is_clean, failure_reason).
        """
        # Serialize fields to inspect
        texts_to_check = [
            str(item.pattern),
            str(item.context),
            " ".join(item.preconditions),
            str(item.observed_effect),
            str(item.evidence_scope),
        ]

        for text in texts_to_check:
            is_clean, reason = cls.inspect_text(text)
            if not is_clean:
                return False, f"SECURITY_QUARANTINE_TRIGGERED: {reason}"

        return True, None

    @classmethod
    def sanitize_string_value(cls, text: str) -> str:
        """Sanitizes text by masking potential secrets or injection markup."""
        if not text:
            return ""
        clean = text
        for pat in cls.INJECTION_PATTERNS:
            clean = pat.sub("[INJECTION_NEUTRALIZED]", clean)
        for pat in cls.SECRET_PATTERNS:
            clean = pat.sub("[SECRET_REDACTED]", clean)
        return clean
