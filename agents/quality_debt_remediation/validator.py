"""
JARVIS OS — Phase 69: Autonomous Quality Debt Remediation
Validator and empirical invariant enforcer.
Enforces strict vocabulary and schema reconciliation rules.
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple


class Phase69Validator:
    """
    Validates data structures and enforces strict empirical language guidelines.
    Rejects forbidden claims of global perfection.
    """

    FORBIDDEN_PHRASES = [
        "all debt resolved",
        "zero technical debt globally",
        "guaranteed quality improvement",
        "perfect remediation",
        "zero regressions globally",
    ]

    ALLOWED_VOCABULARY = [
        "observed",
        "validated",
        "remediated within scope",
        "partially remediated",
        "deferred",
        "blocked",
        "rolled back",
        "quality debt remains",
        "insufficient evidence",
    ]

    def validate_report_vocabulary(self, text: str) -> Tuple[bool, List[str]]:
        violations = []
        lower_text = text.lower()
        for forbidden in self.FORBIDDEN_PHRASES:
            if forbidden in lower_text:
                violations.append(f"Forbidden claim detected: '{forbidden}'")
        return len(violations) == 0, violations

    def validate_regression_reconciliation(
        self, per_phase: Dict[str, int], computed_total: int, reported_total: int
    ) -> Tuple[bool, Dict[str, Any]]:
        sum_per_phase = sum(per_phase.values())
        delta = computed_total - reported_total
        valid = (sum_per_phase == computed_total == reported_total) and (delta == 0)

        result = {
            "sum_per_phase": sum_per_phase,
            "computed_total": computed_total,
            "reported_total": reported_total,
            "delta": delta,
            "valid": valid,
            "status": "VALID" if valid else "REGRESSION_REPORT_INVALID",
        }
        return valid, result
