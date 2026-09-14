"""
JARVIS OS — Phase 50: Behavioral Contract Preservation & Migration Proof
Behavioral Security Sentinel & Cryptographic Tamper Defense.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Set

from agents.behavioral_contract_proof.baseline import compute_baseline_hash
from agents.behavioral_contract_proof.models import BehaviorBaseline, RuntimeTrace
from agents.behavioral_contract_proof.trace import compute_trace_hash


class SecurityBaselineTamperedError(SecurityError if "SecurityError" in globals() else RuntimeError):
    """Raised when a baseline hash does not match computed content."""
    pass


class SecurityTraceTamperedError(RuntimeError):
    """Raised when a runtime trace hash does not match its contents."""
    pass


class SecuritySecretLeakageError(RuntimeError):
    """Raised when raw secrets are found unredacted in execution traces."""
    pass


class SecurityAuthDowngradeError(RuntimeError):
    """Raised when authentication is downgraded on a protected route."""
    pass


PROMPT_INJECTION_PATTERNS: List[re.Pattern] = [
    re.compile(r"ignore\s+previous\s+instructions", re.IGNORECASE),
    re.compile(r"grant\s+admin\s+access", re.IGNORECASE),
    re.compile(r"bypass\s+security\s+check", re.IGNORECASE),
    re.compile(r"system\s*:\s*you\s+are", re.IGNORECASE),
    re.compile(r"<script.*?>.*?</script>", re.IGNORECASE | re.DOTALL),
]


class BehavioralSecuritySentinel:
    """
    Sovereign security authority validating cryptographic integrity,
    poisoning defenses, secret leaks, and auth state transitions.
    """

    @classmethod
    def validate_baseline_integrity(cls, baseline: BehaviorBaseline) -> None:
        """Verifies baseline cryptographic hash against its contents."""
        recalculated = compute_baseline_hash(baseline)
        if baseline.baseline_hash != recalculated:
            raise SecurityBaselineTamperedError(
                f"Security Alert: Forged baseline detected for '{baseline.contract_id}'. "
                f"Expected hash '{recalculated}', got '{baseline.baseline_hash}'"
            )

    @classmethod
    def validate_trace_integrity(cls, trace: RuntimeTrace) -> None:
        """Verifies runtime trace cryptographic hash."""
        recalculated = compute_trace_hash(trace)
        if trace.trace_hash != recalculated:
            raise SecurityTraceTamperedError(
                f"Security Alert: Tampered trace detected for '{trace.trace_id}'. "
                f"Expected hash '{recalculated}', got '{trace.trace_hash}'"
            )

    @classmethod
    def check_secret_leakage(cls, payload: Any, path: str = "") -> None:
        """Ensures raw passwords or API keys do not leak into traces."""
        sensitive_substrings = ["password", "secret", "api_key", "token", "private_key"]

        if isinstance(payload, dict):
            for k, v in payload.items():
                curr = f"{path}.{k}" if path else str(k)
                k_lower = str(k).lower()
                if any(s in k_lower for s in sensitive_substrings):
                    # Value must be redacted placeholder
                    if isinstance(v, str) and not (v.startswith("<REDACTED_") and v.endswith(">")):
                        raise SecuritySecretLeakageError(
                            f"Security Alert: Unredacted secret detected in payload at '{curr}'"
                        )
                cls.check_secret_leakage(v, curr)

        elif isinstance(payload, (list, tuple)):
            for idx, item in enumerate(payload):
                cls.check_secret_leakage(item, f"{path}[{idx}]")

    @classmethod
    def check_prompt_injection(cls, payload: Any) -> Optional[str]:
        """Detects adversarial injection attacks inside payloads."""
        text_repr = str(payload)
        for pattern in PROMPT_INJECTION_PATTERNS:
            if pattern.search(text_repr):
                return f"Adversarial prompt injection pattern detected: '{pattern.pattern}'"
        return None

    @classmethod
    def validate_auth_transition(
        cls, baseline_auth: Dict[str, Any], observed_auth: Dict[str, Any], is_economic: bool = False
    ) -> None:
        """Prevents unauthorized auth downgrades, especially on economic operations."""
        was_required = baseline_auth.get("requires_auth", False)
        now_required = observed_auth.get("requires_auth", False)

        if was_required and not now_required:
            if is_economic:
                raise SecurityAuthDowngradeError(
                    "CRITICAL: Unacceptable authentication downgrade on an economic/payment route!"
                )
