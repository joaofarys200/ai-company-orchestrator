"""
JARVIS OS — Phase 46: Contract Governance Security Sentinel
Enforces strict passive-data policies on contract baselines, drift metadata,
approval tokens, and schema definitions.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Set, Tuple

from agents.contract_governance.models import ContractBaseline


# Patterns indicating malicious attempts inside contract metadata or payloads
MALICIOUS_INJECTION_PATTERNS = [
    re.compile(r"ignore\s+(all\s+)?(previous\s+)?instructions", re.IGNORECASE),
    re.compile(r"system\s*:\s*override", re.IGNORECASE),
    re.compile(r"<script.*?>.*?</script>", re.IGNORECASE | re.DOTALL),
    re.compile(r"(rm\s+-rf|curl\s+https?://|wget\s+https?://)", re.IGNORECASE),
    re.compile(r"(;\s*drop\s+table|\bunion\s+select\b)", re.IGNORECASE),
    re.compile(r"(__proto__|constructor\.prototype)", re.IGNORECASE),
    re.compile(r"(exec\(|eval\(|os\.system\(|subprocess\.)", re.IGNORECASE),
]

FORBIDDEN_OPERATORS = {"anonymous", "unauthorized", "bot_auto_approve", "null", "none", ""}


class ContractGovernanceSecurity:
    """Security sentinel ensuring contract drift data remains passive data and tamper-proof."""

    @classmethod
    def inspect_metadata(cls, data: Any) -> Tuple[bool, List[str]]:
        """Deeply inspects any dictionary, string, or list structure for injection attacks."""
        violations: List[str] = []
        cls._recursive_inspect(data, violations, path="root")
        is_safe = len(violations) == 0
        return is_safe, violations

    @classmethod
    def _recursive_inspect(cls, val: Any, violations: List[str], path: str) -> None:
        if isinstance(val, str):
            for pattern in MALICIOUS_INJECTION_PATTERNS:
                if pattern.search(val):
                    violations.append(f"Security violation at '{path}': detected suspicious pattern '{pattern.pattern}'")
        elif isinstance(val, dict):
            for k, v in val.items():
                if isinstance(k, str):
                    for pattern in MALICIOUS_INJECTION_PATTERNS:
                        if pattern.search(k):
                            violations.append(f"Security violation in key '{path}.{k}'")
                cls._recursive_inspect(v, violations, f"{path}.{k}")
        elif isinstance(val, (list, tuple, set)):
            for i, item in enumerate(val):
                cls._recursive_inspect(item, violations, f"{path}[{i}]")

    @classmethod
    def neutralize_data(cls, data: Any) -> Any:
        """Sanitizes strings and structures by stripping shell control chars and script tags."""
        if isinstance(data, str):
            cleaned = data.replace("\x00", "").replace("\r", "")
            cleaned = re.sub(r"<script.*?>.*?</script>", "[REMOVED_SCRIPT]", cleaned, flags=re.IGNORECASE | re.DOTALL)
            return cleaned
        elif isinstance(data, dict):
            return {cls.neutralize_data(k): cls.neutralize_data(v) for k, v in data.items()}
        elif isinstance(data, list):
            return [cls.neutralize_data(x) for x in data]
        return data

    @classmethod
    def verify_baseline_integrity(cls, baseline: ContractBaseline) -> bool:
        """Verifies that the immutable baseline's schema_hash matches its content."""
        computed = ContractBaseline.compute_schema_hash(
            request_schema=baseline.request_schema,
            response_schema=baseline.response_schema,
            error_contract=baseline.error_contract,
        )
        return computed == baseline.schema_hash

    @classmethod
    def validate_operator_authorization(cls, operator_id: str, is_breaking: bool = False) -> bool:
        """Validates that the operator approving changes is authorized."""
        cleaned_op = (operator_id or "").strip().lower()
        if cleaned_op in FORBIDDEN_OPERATORS:
            return False
        if is_breaking and cleaned_op.startswith("auto_"):
            return False  # Breaking changes cannot be approved by automated bots
        return True
