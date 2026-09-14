"""
JARVIS OS — Phase 48: Contract-Aware Autonomous Change Management
ContractChangeSecuritySentinel: Defends contract change pipelines against prompt injection,
shell command injection, fake approvals, and security contract downgrades.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple


class ContractChangeSecuritySentinel:
    """
    Guards contract change management operations against malicious payload injection,
    prohibited privilege escalation, and security weakening attempts.
    """

    PROMPT_INJECTION_PATTERNS: list[str] = [
        r"ignore\s+previous\s+instructions",
        r"system\s+prompt\s+override",
        r"bypass\s+contract\s+gate",
        r"allow\s+all\s+breaking\s+changes",
        r"disable\s+auth",
        r"skip\s+approval",
        r"you\s+are\s+now\s+in\s+unrestricted\s+mode",
        r"as\s+an\s+ai\s+without\s+restrictions",
    ]

    COMMAND_INJECTION_PATTERNS: list[str] = [
        r"\$\([^)]+\)",
        r"`[^`]+`",
        r";\s*rm\s+-rf",
        r";\s*del\s+.*",
        r"&&\s*curl",
        r"\|\s*bash",
        r"\|\s*sh",
        r"&&\s*cat\s+/etc/passwd",
    ]

    VALID_OPERATOR_SIGNATURE_PREFIX = "VALID_OPERATOR_SIGNATURE"

    @classmethod
    def sanitize_text(cls, text: str) -> str:
        """Sanitizes text by stripping control characters and trimming."""
        if not text:
            return ""
        return re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text).strip()

    @classmethod
    def detect_prompt_injection(cls, text: str) -> tuple[bool, str]:
        """Scans for prompt injection attempts in contract/migration metadata."""
        if not text:
            return False, ""
        lower = text.lower()
        for pattern in cls.PROMPT_INJECTION_PATTERNS:
            if re.search(pattern, lower):
                return True, f"Prompt injection signature detected: '{pattern}'"
        return False, ""

    @classmethod
    def detect_command_injection(cls, text: str) -> tuple[bool, str]:
        """Scans for shell command injection patterns."""
        if not text:
            return False, ""
        for pattern in cls.COMMAND_INJECTION_PATTERNS:
            if re.search(pattern, text):
                return True, f"Shell command injection pattern detected: '{pattern}'"
        return False, ""

    @classmethod
    def validate_approval_signature(cls, signature: Optional[str]) -> bool:
        """Validates operator signature for contract migration approval."""
        if not signature:
            return False
        return signature.startswith(cls.VALID_OPERATOR_SIGNATURE_PREFIX)

    @classmethod
    def audit_security_invariants(
        cls,
        contract_diffs: list[dict[str, Any]],
    ) -> tuple[bool, str]:
        """
        Ensures a contract change does not downgrade authentication or remove security protections.
        """
        for diff in contract_diffs:
            field_name = str(diff.get("field", "")).lower()
            change_type = str(diff.get("type", "")).upper()

            if "auth" in field_name or "security" in field_name or "jwt" in field_name:
                if change_type in ("REMOVE_FIELD", "CHANGE_AUTH"):
                    new_val = diff.get("new")
                    if new_val is None or new_val == "None" or new_val == "DISABLED":
                        return (
                            False,
                            f"Security contract violation: prohibited removal or disabling of '{field_name}'.",
                        )

        return True, "Security invariants verified."

    @classmethod
    def verify_memory_authorization(cls, source: str) -> bool:
        """
        Enforces Invariant 12: Experience Memory cannot authorize a migration on its own
        without human operator approval.
        """
        if "experience_memory" in source.lower() or "memory" in source.lower():
            return False  # Memory cannot authorize
        return True
