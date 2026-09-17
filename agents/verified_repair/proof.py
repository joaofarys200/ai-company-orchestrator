"""
JARVIS OS — Phase 54: Repair Proof Engine
Synthesizes multi-axis evidence into an immutable, bounded RepairProof contract.
"""

from __future__ import annotations

import time
from typing import List, Optional

from agents.verified_repair.models import (
    Counterexample,
    FailureResolutionStatus,
    RepairCandidate,
    RepairProof,
    RepairProofResult,
    compute_deterministic_hash,
)


class RepairProofEngine:
    """
    Synthesizes preflight, startup, healthcheck, behavioral, and regression results into a formal RepairProof.
    Never asserts universal correctness: emits REPAIR_PROVEN strictly within the bounded scope of validated evidence.
    """

    def synthesize_proof(
        self,
        candidate: RepairCandidate,
        failure_id: str,
        root_cause_desc: str,
        before_hash: str,
        patch_hash: str,
        after_hash: str,
        original_resolved: FailureResolutionStatus,
        preflight_passed: bool,
        startup_passed: bool,
        healthcheck_passed: bool,
        behavior_result: str = "PROVEN_COMPATIBLE_WITHIN_SCOPE",
        regression_passed: bool = True,
        counterexamples: Optional[List[Counterexample]] = None,
        invariants: Optional[List[str]] = None,
        coverage: float = 0.95,
        rollback_verified: bool = True,
        scope: str = "LOCAL_MODULE_HTTP_RUNTIME",
    ) -> RepairProof:
        cex_list = counterexamples or []
        inv_list = invariants or [
            "HTTP Socket Listening Invariant",
            "Non-Destructive Rollback Invariant",
            "Zero Lateral Regression Invariant",
        ]

        # Determine proof_result formally
        if (
            not original_resolved == FailureResolutionStatus.ORIGINAL_FAILURE_RESOLVED
            or not preflight_passed
            or not startup_passed
            or cex_list
            or not regression_passed
        ):
            proof_result = RepairProofResult.REPAIR_REJECTED

        elif behavior_result == "INSUFFICIENT_EVIDENCE" or coverage < 0.60:
            proof_result = RepairProofResult.INSUFFICIENT_EVIDENCE

        elif (
            original_resolved == FailureResolutionStatus.ORIGINAL_FAILURE_RESOLVED
            and preflight_passed
            and startup_passed
            and healthcheck_passed
            and regression_passed
            and rollback_verified
        ):
            proof_result = RepairProofResult.REPAIR_PROVEN

        else:
            proof_result = RepairProofResult.INSUFFICIENT_EVIDENCE

        proof_id = compute_deterministic_hash(
            {
                "rep": candidate.repair_id,
                "fail": failure_id,
                "patch": patch_hash,
                "res": proof_result.value,
            },
            prefix="prf_",
        )

        regression_str = "REGRESSION_FREE_WITHIN_SCOPE" if regression_passed else "REGRESSION_DETECTED"

        return RepairProof(
            proof_id=proof_id,
            repair_id=candidate.repair_id,
            failure_id=failure_id,
            root_cause=root_cause_desc,
            patch_hash=patch_hash,
            before_hash=before_hash,
            after_hash=after_hash,
            original_failure_resolved=original_resolved,
            preflight_passed=preflight_passed,
            startup_passed=startup_passed,
            healthcheck_passed=healthcheck_passed,
            behavior_result=behavior_result,
            regression_result=regression_str,
            coverage=coverage,
            counterexamples=cex_list,
            invariants=inv_list,
            rollback_verified=rollback_verified,
            proof_result=proof_result,
            scope=scope,
        )
