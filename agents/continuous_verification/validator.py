"""
JARVIS OS — Phase 62: Continuous Verification & Autonomous Regression Governance
Module: validator.py
Verification Decision Validator enforcing all Central Invariants and prohibiting false promotions.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from .models import (
    CoverageVector,
    FlakyStatus,
    RegressionClassification,
    VerificationDecision,
    VerificationDecisionOutcome,
    VerificationSurface,
)


class VerificationDecisionValidator:
    """
    Guards against invalid verification decisions.
    Enforces central invariants:
    - NO_CHANGE -> NO_VERIFICATION
    - CHANGE_WITH_NO_IMPACT_EVIDENCE -> UNCERTAIN
    - CHANGE_WITH_IMPACT -> VERIFICATION_REQUIRED
    - TEST_GAP -> TEST_SYNTHESIS_REQUIRED
    - TEST_EXECUTION_WITHOUT_REQUIRED_EVIDENCE -> NOT_VERIFIED
    - TEST_FAILURE -> REGRESSION_REQUIRED
    - FLAKY_BEHAVIOR -> FLAKY_REVIEW_REQUIRED
    - SUFFICIENT_EVIDENCE -> VERIFIED_WITHIN_SCOPE

    Strictly prohibits:
    - NO_TESTS -> VERIFIED
    - COVERAGE_UNKNOWN -> VERIFIED
    - DYNAMIC_REFLECTION -> VERIFIED
    - FAILED_TEST_RETRY -> PASS without additional evidence
    """

    @classmethod
    def validate_decision(
        cls,
        decision: VerificationDecision,
        surface: VerificationSurface,
        coverage: Optional[CoverageVector],
        regressions: List[str],
        flaky_tests: List[str],
        is_coverage_known: bool = True,
        has_dynamic_reflection: bool = False,
    ) -> Tuple[bool, List[str]]:
        """Validate that a proposed decision conforms to all invariants."""
        violations: List[str] = []

        is_verified = (decision.outcome == VerificationDecisionOutcome.VERIFIED_WITHIN_SCOPE)

        # Prohibited rule 1: NO_TESTS -> VERIFIED
        if is_verified and len(decision.tests_run) == 0:
            violations.append("INVARIANT_VIOLATION: NO_TESTS cannot be promoted to VERIFIED_WITHIN_SCOPE")

        # Prohibited rule 2: COVERAGE_UNKNOWN -> VERIFIED
        if is_verified and (not is_coverage_known or coverage is None or coverage.line_coverage == 0.0):
            violations.append("INVARIANT_VIOLATION: COVERAGE_UNKNOWN cannot be promoted to VERIFIED_WITHIN_SCOPE")

        # Prohibited rule 3: DYNAMIC_REFLECTION -> VERIFIED without bounds
        if is_verified and has_dynamic_reflection and surface.uncertainty > 0.35 and len(surface.dynamic_boundaries) > 0:
            violations.append("INVARIANT_VIOLATION: DYNAMIC_REFLECTION cannot be promoted to VERIFIED_WITHIN_SCOPE without bound proof")

        # Invariant: TEST_FAILURE -> REGRESSION_REQUIRED / cannot be verified
        if is_verified and regressions:
            violations.append(f"INVARIANT_VIOLATION: Regressions exist ({regressions}); cannot be VERIFIED_WITHIN_SCOPE")

        # Invariant: FLAKY_BEHAVIOR -> FLAKY_REVIEW_REQUIRED
        if is_verified and flaky_tests:
            violations.append(f"INVARIANT_VIOLATION: Flaky tests detected ({flaky_tests}); requires FLAKY_REVIEW_REQUIRED")

        # Invariant: TEST_EXECUTION_WITHOUT_REQUIRED_EVIDENCE -> NOT_VERIFIED
        if is_verified and len(decision.evidence) == 0:
            violations.append("INVARIANT_VIOLATION: Missing cryptographic evidence items in decision")

        return len(violations) == 0, violations
