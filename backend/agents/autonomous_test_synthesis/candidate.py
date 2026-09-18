"""
JARVIS OS — Phase 61: Autonomous Test Synthesis & Coverage-Guided Validation
Module: candidate.py
Manages TestCandidate instances, deterministic hashing, state lifecycle, and provenance.
"""

from __future__ import annotations

import hashlib
from typing import Any, Dict, List, Optional

from .models import (
    CostEstimate,
    TestCandidate,
    TestCandidateStatus,
    TestFramework,
)


class TestCandidateManager:
    """Tracks test candidates through their lifecycle: GENERATED -> RANKED -> EXECUTING -> ACCEPTED / REJECTED."""

    def __init__(self) -> None:
        self._candidates: Dict[str, TestCandidate] = {}

    def create_candidate(
        self,
        requirement_id: str,
        target: str,
        framework: TestFramework,
        language: str,
        files: List[str],
        inputs: Dict[str, Any],
        expected_outputs: Dict[str, Any],
        invariants: List[str],
        code: str,
        risk: float = 0.5,
        estimated_cost: Optional[CostEstimate] = None,
        predicted_coverage_gain: float = 0.1,
        provenance: str = "autonomous_generator",
    ) -> TestCandidate:
        """Create a candidate with deterministic test_id."""
        test_id = self.generate_deterministic_id(requirement_id, target, code)
        candidate = TestCandidate(
            test_id=test_id,
            requirement_id=requirement_id,
            target=target,
            framework=framework,
            language=language,
            files=files,
            inputs=inputs,
            expected_outputs=expected_outputs,
            invariants=invariants,
            risk=risk,
            estimated_cost=estimated_cost or CostEstimate(),
            predicted_coverage_gain=predicted_coverage_gain,
            provenance=provenance,
            code=code,
            status=TestCandidateStatus.GENERATED,
        )
        self._candidates[test_id] = candidate
        return candidate

    def get_candidate(self, test_id: str) -> Optional[TestCandidate]:
        return self._candidates.get(test_id)

    def list_candidates(
        self, status: Optional[TestCandidateStatus] = None
    ) -> List[TestCandidate]:
        if status:
            return [c for c in self._candidates.values() if c.status == status]
        return list(self._candidates.values())

    def update_status(
        self,
        test_id: str,
        status: TestCandidateStatus,
        rejection_reason: Optional[str] = None,
    ) -> bool:
        c = self._candidates.get(test_id)
        if not c:
            return False
        c.status = status
        if rejection_reason:
            c.rejection_reason = rejection_reason
        return True

    @staticmethod
    def generate_deterministic_id(requirement_id: str, target: str, code: str) -> str:
        payload = f"{requirement_id}::{target}::{code.strip()}"
        digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:12]
        return f"TEST_{digest}"
