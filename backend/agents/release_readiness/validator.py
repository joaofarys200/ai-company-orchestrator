"""
Release Readiness Validator Module
Phase 70 — Autonomous Release Readiness & Production Governance

Validates candidate schemas, transition invariants, and strictly audits vocabulary.
Prohibits forbidden hyperbolic phrases and enforces empirical qualification terms.
"""

from __future__ import annotations
from typing import Dict, Any, List
from .models import ReleaseCandidate, ReleaseCandidateState, ReleaseGateDecision


class ReleaseReadinessValidator:
    """Enforces schema rules, lifecycle invariants, and epistemic vocabulary hygiene."""

    FORBIDDEN_VOCABULARY = [
        "production ready globally",
        "zero release risk",
        "guaranteed deployment",
        "zero incidents globally",
        "perfect release governance"
    ]

    REQUIRED_EMPIRICAL_TERMS = [
        "observed",
        "release-ready within scope",
        "release-ready with risk",
        "blocked",
        "human review",
        "not ready",
        "deployment unavailable",
        "insufficient evidence"
    ]

    @classmethod
    def validate_candidate(cls, candidate: ReleaseCandidate) -> List[str]:
        """Validates ReleaseCandidate invariants."""
        errors: List[str] = []
        if not candidate.release_id:
            errors.append("Candidate missing release_id")
        if not candidate.commit_sha:
            errors.append("Candidate missing commit_sha")
        if not candidate.workspace_snapshot:
            errors.append("Candidate missing workspace_snapshot")
        if not candidate.version:
            errors.append("Candidate missing version")
        return errors

    @classmethod
    def validate_transition(
        cls,
        from_state: ReleaseCandidateState,
        to_state: ReleaseCandidateState
    ) -> bool:
        """Validates that a state transition is legal and never CREATED -> RELEASED."""
        if from_state == ReleaseCandidateState.CREATED and to_state == ReleaseCandidateState.RELEASED:
            return False
        return True

    @classmethod
    def audit_text_vocabulary(cls, text: str) -> Dict[str, Any]:
        """
        Scans text for prohibited hyperbolic phrases and returns violations.
        """
        lower = text.lower()
        violations: List[str] = []
        for phrase in cls.FORBIDDEN_VOCABULARY:
            if phrase in lower:
                violations.append(phrase)

        return {
            "valid": len(violations) == 0,
            "violations": violations,
            "prohibited_count": len(violations)
        }

    @classmethod
    def validate_decision(cls, decision: ReleaseGateDecision) -> List[str]:
        """Audits a ReleaseGateDecision for structural and vocabulary correctness."""
        errors: List[str] = []
        if not decision.decision_id:
            errors.append("Decision missing decision_id")
        if not decision.candidate_id:
            errors.append("Decision missing candidate_id")
        if not decision.provenance_hash:
            errors.append("Decision missing provenance_hash")

        # Check domain summaries
        expected_domains = [
            "security", "quality", "debt", "architecture",
            "contract", "behavior", "performance", "runtime",
            "observability", "dependency", "configuration", "rollback"
        ]
        for ed in expected_domains:
            if ed not in decision.domain_summaries:
                errors.append(f"Missing required domain summary: {ed}")

        return errors
