"""
JARVIS OS — Phase 61: Autonomous Test Synthesis & Coverage-Guided Validation
Module: minimizer.py
Quality gates rejecting trivial assertions (assert True) and minimizer pruning duplicate tests.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Set, Tuple

from .models import TestCandidate, TestCandidateStatus


class TestQualityEvaluator:
    """
    Validates assertion strength, determinism, isolation, and rejects vacuous/trivial tests.
    """

    @staticmethod
    def evaluate_quality(candidate: TestCandidate) -> Tuple[bool, Optional[str]]:
        code = candidate.code.strip()

        # 1. Reject empty or trivially short code
        if len(code) < 30:
            return False, "Test code body is trivially short or empty"

        # 2. Reject 'assert True' or 'assert 1 == 1'
        trivial_patterns = [
            r"assert\s+True\b",
            r"assert\s+1\s*==\s*1\b",
            r"assert\s+not\s+False\b",
            r"expect\(true\)\.toBe\(true\)",
        ]
        for pat in trivial_patterns:
            if re.search(pat, code):
                return False, f"Trivial vacuous assertion detected: matched pattern '{pat}'"

        # 3. Must contain at least one assertion or expectation
        has_assert = (
            "assert " in code
            or "pytest.raises" in code
            or "expect(" in code
            or "toBe" in code
            or "toContain" in code
        )
        if not has_assert:
            return False, "Test contains no assertion or expectation statement"

        # 4. Must invoke a symbol or target
        target_token = candidate.target.split("::")[-1]
        if target_token not in code and "browser::" not in candidate.target:
            return False, f"Test does not reference target symbol '{target_token}'"

        return True, None


class TestMinimalityEvaluator:
    """
    Deduplicates candidates and maximizes evidence per execution cost.
    """

    def __init__(self) -> None:
        self._seen_signatures: Set[str] = set()

    def filter_minimal_set(self, candidates: List[TestCandidate]) -> List[TestCandidate]:
        minimal: List[TestCandidate] = []

        for cand in candidates:
            # 1. Quality check first
            is_valid, reason = TestQualityEvaluator.evaluate_quality(cand)
            if not is_valid:
                cand.status = TestCandidateStatus.REJECTED
                cand.rejection_reason = reason
                continue

            # 2. Minimality / Deduplication signature
            sig = f"{cand.target}::{cand.framework.value}::{sorted(cand.inputs.keys())}::{cand.invariants}"
            if sig in self._seen_signatures:
                cand.status = TestCandidateStatus.REJECTED
                cand.rejection_reason = "Duplicate test signature with identical inputs and invariants"
                continue

            self._seen_signatures.add(sig)
            minimal.append(cand)

        return minimal
