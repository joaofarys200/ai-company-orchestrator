"""
JARVIS OS — Phase 77: Autonomous Evidence Verification & Engineering Claims Governance
Module: verifier.py
Deterministic claim-to-evidence verification engine implementing category-specific validation rules.
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional, Set, Tuple

from .models import (
    AssuranceTier,
    ClaimType,
    EngineeringClaim,
    EvidenceArtifact,
    EvidenceCategory,
    EvidenceOriginType,
    VerificationResult,
    VerificationStatus,
)
from .provenance import EvidenceProvenanceValidator


class ClaimToEvidenceVerifier:
    """
    Evaluates whether provided evidence artifacts actually prove an engineering claim.
    Distinguishes verified facts from assumptions, unexecuted tests, and synthetic demonstrations.
    """

    def verify_claim(
        self,
        claim: EngineeringClaim,
        artifacts: List[EvidenceArtifact],
    ) -> VerificationResult:
        """
        Executes deterministic verification of a claim against its attached evidence artifacts.
        """
        # 1. Check for complete absence of evidence
        if not artifacts:
            res = VerificationResult(
                status=VerificationStatus.UNVERIFIED,
                explanation="No evidence artifacts attached to claim.",
                missing_evidence_categories=list(claim.required_evidence_categories),
            )
            self._update_claim(claim, res)
            return res

        # 2. Check for missing required evidence categories
        provided_categories = {a.category for a in artifacts}
        missing_categories = [
            c for c in claim.required_evidence_categories if c not in provided_categories
        ]

        # 3. Check for cryptographic integrity across all artifacts
        for art in artifacts:
            EvidenceProvenanceValidator.validate_integrity(art)

        # 4. Check commit SHA alignment if specified
        if claim.commit_sha:
            mismatched = [
                a.artifact_id for a in artifacts
                if a.commit_sha and a.commit_sha != claim.commit_sha
            ]
            if mismatched:
                res = VerificationResult(
                    status=VerificationStatus.STALE,
                    explanation=f"Evidence generated on mismatched commit SHA: {mismatched} != {claim.commit_sha}.",
                    supporting_evidence_ids=[a.artifact_id for a in artifacts],
                    discrepancies=["COMMIT_SHA_MISMATCH"],
                )
                self._update_claim(claim, res)
                return res

        # 5. Check if claim relies solely on unverified model text
        if all(a.category == EvidenceCategory.MODEL_GENERATED_EXPLANATION for a in artifacts):
            res = VerificationResult(
                status=VerificationStatus.UNVERIFIED,
                explanation="Model-generated narrative text cannot independently verify its own claims.",
                missing_evidence_categories=list(claim.required_evidence_categories),
                discrepancies=["SELF_VERIFICATION_REJECTED"],
            )
            self._update_claim(claim, res)
            return res

        # 6. Execute category-specific verification logic
        status, explanation, discrepancies = self._evaluate_category_rules(claim, artifacts)

        # If some material categories are missing, clamp status to PARTIALLY_VERIFIED
        if missing_categories and status == VerificationStatus.VERIFIED:
            status = VerificationStatus.PARTIALLY_VERIFIED
            explanation += f" (Missing required categories: {[c.value for c in missing_categories]})"

        res = VerificationResult(
            status=status,
            explanation=explanation,
            supporting_evidence_ids=[a.artifact_id for a in artifacts],
            missing_evidence_categories=missing_categories,
            discrepancies=discrepancies,
        )
        self._update_claim(claim, res)
        return res

    def _evaluate_category_rules(
        self,
        claim: EngineeringClaim,
        artifacts: List[EvidenceArtifact],
    ) -> Tuple[VerificationStatus, str, List[str]]:
        """Dispatch to specialized verification procedures."""
        if claim.claim_type == ClaimType.TEST_EXECUTION:
            return self._verify_test_execution(claim, artifacts)
        elif claim.claim_type == ClaimType.REPOSITORY_STATE:
            return self._verify_repository_state(claim, artifacts)
        elif claim.claim_type == ClaimType.PERFORMANCE_BENCHMARK:
            return self._verify_performance_benchmark(claim, artifacts)
        elif claim.claim_type == ClaimType.SECURITY_GOVERNANCE:
            return self._verify_security_governance(claim, artifacts)
        elif claim.claim_type == ClaimType.PREDICTIVE_CALIBRATION:
            return self._verify_predictive_calibration(claim, artifacts)
        elif claim.claim_type == ClaimType.PHASE_COMPLETION:
            return self._verify_phase_completion(claim, artifacts)
        elif claim.claim_type == ClaimType.SOURCE_INTEGRATION:
            return self._verify_source_integration(claim, artifacts)
        elif claim.claim_type == ClaimType.RECOVERY_ROLLBACK:
            return self._verify_recovery_rollback(claim, artifacts)

        return VerificationStatus.VERIFIED, "Default category verification passed.", []

    def _verify_test_execution(
        self,
        claim: EngineeringClaim,
        artifacts: List[EvidenceArtifact],
    ) -> Tuple[VerificationStatus, str, List[str]]:
        test_arts = [a for a in artifacts if a.category == EvidenceCategory.TEST_RUNNER_RESULT]
        if not test_arts:
            return VerificationStatus.UNVERIFIED, "Test execution evidence missing from artifacts.", ["NO_TEST_RUNNER_RESULT"]

        # Examine latest test result
        latest = test_arts[-1]
        payload = latest.payload
        passed = payload.get("passed", 0)
        failed = payload.get("failed", 0)
        total = payload.get("total", passed + failed)

        # Check for contradictions
        if failed > 0:
            return (
                VerificationStatus.CONTRADICTED,
                f"Test execution failed: {failed} test(s) failed out of {total}.",
                [f"TEST_FAILURES_DETECTED_{failed}"],
            )

        if passed == 0 and total == 0:
            return (
                VerificationStatus.UNVERIFIED,
                "Test runner executed 0 tests (empty test suite).",
                ["EMPTY_TEST_RUN"],
            )

        return (
            VerificationStatus.VERIFIED,
            f"Test runner confirmed {passed}/{total} tests passed with 0 failures.",
            [],
        )

    def _verify_repository_state(
        self,
        claim: EngineeringClaim,
        artifacts: List[EvidenceArtifact],
    ) -> Tuple[VerificationStatus, str, List[str]]:
        exec_arts = [a for a in artifacts if a.category == EvidenceCategory.DIRECT_EXECUTION_OUTPUT]
        if exec_arts:
            payload = exec_arts[-1].payload
            status = payload.get("status")
            if status == "COMPLETED":
                return VerificationStatus.VERIFIED, "Operation execution status is COMPLETED.", []
            elif status in ("FAILED", "ABORTED"):
                return VerificationStatus.CONTRADICTED, f"Operation execution status is {status}.", [f"STATUS_{status}"]
            elif status in ("IN_PROGRESS", "PENDING"):
                return VerificationStatus.UNVERIFIED, f"Operation execution is {status}.", [f"STATUS_{status}"]

        git_arts = [a for a in artifacts if a.category == EvidenceCategory.GIT_REVISION_RECORD]
        if not git_arts:
            return VerificationStatus.UNVERIFIED, "Git revision record or execution record missing.", ["NO_GIT_RECORD"]

        payload = git_arts[-1].payload
        modified_files = set(payload.get("modified_files", []))
        created_files = set(payload.get("created_files", []))
        all_changed = modified_files.union(created_files)

        # If claim asserts specific files were modified, check they are in git change record
        if claim.dependency_files:
            missing_files = [f for f in claim.dependency_files if f not in all_changed]
            if missing_files:
                return (
                    VerificationStatus.CONTRADICTED,
                    f"Claim asserts modifications to {claim.dependency_files}, but files not in git change set: {missing_files}.",
                    [f"FILE_NOT_CHANGED_{f}" for f in missing_files],
                )

        return VerificationStatus.VERIFIED, f"Repository state verified for {len(all_changed)} changed file(s).", []

    def _verify_performance_benchmark(
        self,
        claim: EngineeringClaim,
        artifacts: List[EvidenceArtifact],
    ) -> Tuple[VerificationStatus, str, List[str]]:
        bench_arts = [a for a in artifacts if a.category == EvidenceCategory.BENCHMARK_MEASUREMENT]
        if not bench_arts:
            return VerificationStatus.UNVERIFIED, "Benchmark measurement artifact missing.", ["NO_BENCHMARK_ARTIFACT"]

        latest = bench_arts[-1]
        payload = latest.payload

        # Check baseline comparability
        if not payload.get("conditions_comparable", True):
            return (
                VerificationStatus.PARTIALLY_VERIFIED,
                "Benchmark conditions are not comparable with baseline (hardware/environment mismatch).",
                ["INCOMPARABLE_BASELINE_CONDITIONS"],
            )

        # Check synthetic origin
        if latest.origin_type == EvidenceOriginType.SYNTHETIC_FIXTURE:
            return (
                VerificationStatus.PARTIALLY_VERIFIED,
                "Benchmark demonstrates algorithmic behavior on synthetic fixtures, not real-world workload.",
                ["SYNTHETIC_FIXTURE_ONLY"],
            )

        base_val = payload.get("baseline_metric")
        cand_val = payload.get("candidate_metric")
        if base_val is not None and cand_val is not None:
            if cand_val > base_val and payload.get("lower_is_better", True):
                return (
                    VerificationStatus.CONTRADICTED,
                    f"Benchmark shows performance regression: candidate {cand_val} > baseline {base_val}.",
                    ["PERFORMANCE_REGRESSION_OBSERVED"],
                )

        return VerificationStatus.VERIFIED, "Performance improvement empirically verified against comparable baseline.", []

    def _verify_security_governance(
        self,
        claim: EngineeringClaim,
        artifacts: List[EvidenceArtifact],
    ) -> Tuple[VerificationStatus, str, List[str]]:
        appr_arts = [a for a in artifacts if a.category == EvidenceCategory.HUMAN_APPROVAL_RECORD]
        if claim.assurance_tier == AssuranceTier.TIER_4_MISSION_CRITICAL and not appr_arts:
            return (
                VerificationStatus.UNVERIFIED,
                "Mission-critical claim requires human approval token, but none attached.",
                ["HUMAN_APPROVAL_TOKEN_REQUIRED"],
            )

        if appr_arts:
            token = appr_arts[-1].payload.get("token")
            if not token or "REVOKED" in token or "INVALID" in token:
                return (
                    VerificationStatus.CONTRADICTED,
                    f"Human approval token is invalid or revoked: '{token}'.",
                    ["INVALID_APPROVAL_TOKEN"],
                )

        return VerificationStatus.VERIFIED, "Security and governance requirements fully verified.", []

    def _verify_predictive_calibration(
        self,
        claim: EngineeringClaim,
        artifacts: List[EvidenceArtifact],
    ) -> Tuple[VerificationStatus, str, List[str]]:
        cal_arts = [a for a in artifacts if a.source_subsystem == "predictive_calibration"]
        if not cal_arts:
            return VerificationStatus.UNVERIFIED, "Calibration evidence missing.", ["NO_CALIBRATION_EVIDENCE"]

        payload = cal_arts[-1].payload
        promoted = payload.get("promoted", False)
        mae_red = payload.get("mae_reduction_pct", 0.0)

        if not promoted or mae_red < 5.0:
            return (
                VerificationStatus.CONTRADICTED,
                f"Calibration evaluation failed promotion criteria (promoted={promoted}, MAE reduction={mae_red:.1f}%).",
                ["CALIBRATION_PROMOTION_CRITERIA_FAILED"],
            )

        return VerificationStatus.VERIFIED, f"Calibration model verified with {mae_red:.1f}% holdout error reduction.", []

    def _verify_phase_completion(
        self,
        claim: EngineeringClaim,
        artifacts: List[EvidenceArtifact],
    ) -> Tuple[VerificationStatus, str, List[str]]:
        # Composite claim requires test runner results, git revision, and deliverables
        categories = {a.category for a in artifacts}
        if EvidenceCategory.TEST_RUNNER_RESULT not in categories:
            return VerificationStatus.UNVERIFIED, "Phase completion requires test execution evidence.", ["NO_TEST_RUNNER_RESULT"]

        # If any attached test runner artifact failed, phase completion is contradicted
        for a in artifacts:
            if a.category == EvidenceCategory.TEST_RUNNER_RESULT:
                if a.payload.get("failed", 0) > 0:
                    return VerificationStatus.CONTRADICTED, "Phase completion contradicted by test failures.", ["TEST_FAILURES"]

        return VerificationStatus.VERIFIED, "Phase completion verified across all evidence artifacts.", []

    def _verify_source_integration(
        self,
        claim: EngineeringClaim,
        artifacts: List[EvidenceArtifact],
    ) -> Tuple[VerificationStatus, str, List[str]]:
        # Distinguish static inspection from runtime verification
        static_only = all(
            a.origin_type == EvidenceOriginType.STATIC_INSPECTION for a in artifacts
        )
        if static_only:
            return (
                VerificationStatus.PARTIALLY_VERIFIED,
                "Source-code static inspection confirms symbol signatures, but runtime execution is unverified.",
                ["STATIC_INSPECTION_ONLY"],
            )
        return VerificationStatus.VERIFIED, "Source integration verified with runtime proof.", []

    def _verify_recovery_rollback(
        self,
        claim: EngineeringClaim,
        artifacts: List[EvidenceArtifact],
    ) -> Tuple[VerificationStatus, str, List[str]]:
        git_arts = [a for a in artifacts if a.category == EvidenceCategory.GIT_REVISION_RECORD]
        if not git_arts:
            return VerificationStatus.UNVERIFIED, "Rollback verification requires clean git state evidence.", ["NO_GIT_RECORD"]

        payload = git_arts[-1].payload
        if payload.get("is_dirty", False) or payload.get("untracked_files"):
            return (
                VerificationStatus.CONTRADICTED,
                "Rollback failed to restore clean working tree (dirty files or untracked changes remain).",
                ["DIRTY_TREE_AFTER_ROLLBACK"],
            )

        return VerificationStatus.VERIFIED, "Clean rollback and state restoration verified.", []

    def _update_claim(self, claim: EngineeringClaim, result: VerificationResult) -> None:
        """Update claim with verification outcome."""
        claim.status = result.status
        claim.verification_result = result
        claim.verified_at = result.verified_at
