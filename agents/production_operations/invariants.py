"""
Phase 71 — Operational Audit Invariants
Formal assertions safeguarding system truth against false claims, ungrounded promotions, and unverified transitions.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from .models import (
    HealthStatus,
    ObservationProvenance,
    ObservationStatus,
    OperationalState,
    RecoveryVerification,
    RemediationExecution,
    RollbackCertificate,
    RuntimeObservation,
    VerificationStatus,
)


class InvariantViolationError(AssertionError):
    """Raised when an immutable operational governance invariant is breached."""
    pass


class OperationalInvariantAuditor:
    """
    Evaluates formal assertions across the production operations lifecycle.
    """

    @staticmethod
    def assert_no_false_real_deployment(
        observation: RuntimeObservation,
        physical_infra_present: bool,
    ) -> None:
        """Asserts that REAL_RUNTIME_OBSERVATION is never declared for non-existent physical infrastructure."""
        if not physical_infra_present and observation.provenance == ObservationProvenance.REAL_RUNTIME_OBSERVATION:
            if observation.environment in {"production", "prod", "k8s", "cloud"}:
                raise InvariantViolationError(
                    f"False real deployment detected: Environment '{observation.environment}' claimed "
                    "REAL_RUNTIME_OBSERVATION but physical cloud infrastructure is absent."
                )

    @staticmethod
    def assert_no_false_recovery(
        verification: RecoveryVerification,
    ) -> None:
        """Asserts that RECOVERY_VERIFIED cannot be declared with 0 checks or insufficient stability."""
        if verification.status == VerificationStatus.RECOVERY_VERIFIED:
            if verification.healthchecks_passed < 1:
                raise InvariantViolationError("False recovery invariant breached: RECOVERY_VERIFIED declared with 0 passed healthchecks.")
            if verification.healthchecks_failed > 0:
                raise InvariantViolationError(
                    f"False recovery invariant breached: RECOVERY_VERIFIED declared with {verification.healthchecks_failed} active failures."
                )

    @staticmethod
    def assert_no_unknown_promotion(status: HealthStatus, promoted_to: HealthStatus) -> None:
        """Asserts that UNKNOWN healthcheck results are never promoted automatically to HEALTHY."""
        if status == HealthStatus.UNKNOWN and promoted_to == HealthStatus.HEALTHY:
            raise InvariantViolationError("Auto-promotion invariant breached: UNKNOWN status cannot be converted to HEALTHY.")

    @staticmethod
    def assert_rollback_target_known(
        target_release: str,
        known_checkpoints: List[str],
    ) -> None:
        """Asserts that rollback is never directed to an unregistered or unknown release."""
        if target_release not in known_checkpoints:
            raise InvariantViolationError(
                f"Rollback invariant breached: Target release '{target_release}' is unknown."
            )

    @staticmethod
    def assert_remediation_evidence_present(execution: RemediationExecution) -> None:
        """Asserts that autonomous remediation recorded concrete execution evidence."""
        if execution.success and not execution.actions_executed:
            raise InvariantViolationError("Remediation invariant breached: Success claimed with 0 recorded actions.")

    @staticmethod
    def assert_regression_arithmetic(
        per_phase_passes: Dict[str, int],
        reported_total: int,
    ) -> None:
        """Asserts that sum(per_phase) == computed_total == reported_total."""
        computed = sum(per_phase_passes.values())
        if computed != reported_total:
            raise InvariantViolationError(
                f"Regression arithmetic mismatch: sum(per_phase)={computed} != reported_total={reported_total} (delta={reported_total - computed})."
            )
