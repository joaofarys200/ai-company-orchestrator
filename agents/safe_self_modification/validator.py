"""
JARVIS OS — Phase 65: Safe Self-Modification & Transactional Architecture Implementation
Module: validator.py
Commit Gate validator evaluating the 11 mandatory criteria before declaring COMMIT_ELIGIBLE.
Never uses a solitary boolean; produces structured multi-criteria evaluations.
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

from .models import CommitEligibility


class CommitGateValidator:
    """Evaluates all 11 mandatory invariants required to authorize a permanent commit."""

    MANDATORY_CRITERIA = [
        "governance_valid",
        "patch_scope_valid",
        "build_pass",
        "required_tests_pass",
        "contract_validation_pass",
        "behavior_within_scope",
        "continuous_verification_pass",
        "architecture_rescan_complete",
        "security_pass",
        "rollback_checkpoint_valid",
        "evidence_ledger_complete",
    ]

    def evaluate_commit_eligibility(
        self,
        checks: Dict[str, bool],
        evidence_data: Dict[str, Any],
    ) -> Tuple[CommitEligibility, List[str]]:
        """Evaluate whether transaction meets all 11 non-negotiable commit criteria."""
        logs: List[str] = []
        failed_criteria: List[str] = []

        for criterion in self.MANDATORY_CRITERIA:
            passed = checks.get(criterion, False)
            if not passed:
                failed_criteria.append(criterion)
                logs.append(f"COMMIT_CRITERION_FAILED: '{criterion}' is not satisfied.")
            else:
                logs.append(f"COMMIT_CRITERION_PASSED: '{criterion}' verified.")

        if not failed_criteria:
            logs.append("COMMIT_GATE_PASSED: All 11 criteria fulfilled. Status: COMMIT_ELIGIBLE.")
            return CommitEligibility.COMMIT_ELIGIBLE, logs

        # Check if failure warrants human review vs outright block
        if "security_pass" in failed_criteria or "patch_scope_valid" in failed_criteria:
            logs.append("COMMIT_GATE_BLOCKED: Security or scope violation detected. Status: COMMIT_BLOCKED.")
            return CommitEligibility.COMMIT_BLOCKED, logs

        logs.append(f"COMMIT_GATE_REVIEW: {len(failed_criteria)} non-critical criteria require review. Status: HUMAN_REVIEW.")
        return CommitEligibility.HUMAN_REVIEW, logs
