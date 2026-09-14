"""
JARVIS OS — Phase 49: Build Contract Security Sentinel
Hardens build-time contract extraction against schema poisoning, auth downgrades, and false evidence elevation.
"""

from __future__ import annotations

import re
from typing import Any, List, Optional, Tuple

from agents.build_contract_extraction.models import (
    ContractEndpoint,
    ContractType,
    EvidenceState,
)


class BuildContractSecurityViolation(Exception):
    """Raised when an operation violates Phase 49 security and invariant policies."""
    pass


class BuildContractSecuritySentinel:
    """
    Authoritative security sentinel for build-time contract extraction and dynamic consumer resolution.
    """

    FORBIDDEN_SCHEMA_INJECTIONS = [
        re.compile(r"<script.*?>.*?</script>", re.IGNORECASE | re.DOTALL),
        re.compile(r"javascript\s*:", re.IGNORECASE),
        re.compile(r"__proto__", re.IGNORECASE),
        re.compile(r"constructor\s*\[\s*['\"]prototype['\"]\s*\]", re.IGNORECASE),
        re.compile(r"\bSYSTEM\s+PROMPT\s+OVERRIDE\b", re.IGNORECASE),
        re.compile(r"\bIGNORE\s+ALL\s+INSTRUCTIONS\b", re.IGNORECASE),
    ]

    ECONOMIC_PROTECTED_ROUTES = [
        "/api/v1/payments",
        "/api/v2/payments",
        "/api/v1/billing",
        "/api/v1/checkout",
        "/api/v1/subscriptions",
    ]

    @classmethod
    def sanitize_schema_content(cls, content: str, source_label: str = "schema") -> None:
        """Inspects raw schema string content to ensure no prompt injections or XSS payloads exist."""
        for pat in cls.FORBIDDEN_SCHEMA_INJECTIONS:
            if pat.search(content):
                raise BuildContractSecurityViolation(
                    f"Security Sentinel BLOCKED: Malicious injection pattern '{pat.pattern}' in {source_label}."
                )

    @classmethod
    def verify_auth_invariants(cls, endpoint: ContractEndpoint) -> None:
        """
        Enforces that contract extraction never silently weakens security.
        If an endpoint path is authenticated, generated schemas cannot claim auth is disabled.
        """
        is_economic = any(endpoint.path.startswith(route) for route in cls.ECONOMIC_PROTECTED_ROUTES)
        if is_economic and not endpoint.auth.requires_auth:
            raise BuildContractSecurityViolation(
                f"Security Sentinel BLOCKED: Attempted to disable authentication on protected economic route '{endpoint.path}'."
            )

    @classmethod
    def verify_evidence_elevation(cls, from_state: EvidenceState, to_state: EvidenceState) -> None:
        """
        Enforces epistemic rules:
        STATIC != VERIFIED, GENERATED != VERIFIED, UNCERTAIN cannot silently become VERIFIED without proof.
        """
        if to_state == EvidenceState.VERIFIED and from_state not in (EvidenceState.RUNTIME_OBSERVED, EvidenceState.VERIFIED):
            raise BuildContractSecurityViolation(
                f"Epistemic violation: Cannot directly promote state '{from_state.value}' to 'VERIFIED' without runtime execution and browser QA evidence."
            )

    @classmethod
    def is_safe(cls, endpoint: ContractEndpoint) -> Tuple[bool, Optional[str]]:
        """Safe non-throwing check returning (is_safe, error_reason)."""
        try:
            cls.verify_auth_invariants(endpoint)
            return True, None
        except BuildContractSecurityViolation as exc:
            return False, str(exc)
