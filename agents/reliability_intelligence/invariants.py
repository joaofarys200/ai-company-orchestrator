"""
Phase 72 — Audit Invariants and Integrity Verification
Enforces architectural rules and prevents invalid state promotions or unverified actions.
"""

from __future__ import annotations

from .models import (
    AnomalyStatus,
    BaselineStatus,
    GovernanceDecision,
    PreventiveAction,
    PreventivePlan,
    RiskLevel,
    RiskPrediction,
)


class InvariantViolationError(RuntimeError):
    """Raised when an architectural invariant is violated."""
    pass


class ReliabilityInvariantAuditor:
    """Audits system state to ensure strict compliance with Phase 72 axioms."""

    @staticmethod
    def assert_no_unknown_promotion(status: AnomalyStatus, baseline_status: BaselineStatus) -> None:
        """Rule: An UNKNOWN anomaly cannot be converted to NORMAL or ANOMALOUS if baseline has insufficient evidence."""
        if baseline_status == BaselineStatus.INSUFFICIENT_EVIDENCE and status != AnomalyStatus.UNKNOWN:
            raise InvariantViolationError(
                f"Invariant violation: Cannot declare status '{status.value}' when baseline has INSUFFICIENT_EVIDENCE."
            )

    @staticmethod
    def assert_safe_autonomous_execution(action: PreventiveAction, plan: PreventivePlan) -> None:
        """Rule: Actions marked HIGH_RISK or UNKNOWN must not be executed without governance approval."""
        if action.risk_level in (RiskLevel.HIGH, RiskLevel.UNKNOWN, RiskLevel.INSUFFICIENT_EVIDENCE):
            if plan.governance_decision != GovernanceDecision.APPROVED:
                raise InvariantViolationError(
                    f"Invariant violation: Cannot execute action '{action.action_type.value}' "
                    f"with risk '{action.risk_level.value}' without explicit APPROVED decision."
                )

    @staticmethod
    def assert_prediction_action_separation(prediction: RiskPrediction, plan: PreventivePlan) -> None:
        """Rule: A high predicted risk must not be automatically assumed to be an active incident."""
        # Risk prediction creates a plan, but does NOT assert service is currently crashed or in recovery
        if prediction.risk_level == RiskLevel.HIGH and not plan.actions:
            raise InvariantViolationError(
                "Invariant violation: High risk prediction generated with no associated preventive contingency plan."
            )
