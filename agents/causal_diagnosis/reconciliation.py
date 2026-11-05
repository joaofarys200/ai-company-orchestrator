"""
JARVIS OS — Phase 78: Autonomous Causal Diagnosis & Root-Cause Analysis
Module: reconciliation.py
Post-remediation outcome reconciliation verifying that the corrective intervention
successfully mitigated the identified root cause.
"""

from __future__ import annotations

from typing import Any, Dict, Tuple

from .models import CorrectiveAction, DiagnosisReport, DiagnosticOutcome


class OutcomeReconciler:
    """
    Compares post-action observed outcomes with predicted effects to close the diagnosis loop.
    """

    @staticmethod
    def reconcile_post_remediation(
        report: DiagnosisReport,
        action: CorrectiveAction,
        post_remediation_telemetry: Dict[str, Any],
    ) -> Tuple[bool, str]:
        """
        Reconciles the outcome of an applied corrective action.
        Returns (resolved: bool, explanation: str).
        """
        # Check if error rate is 0 or test suite passed
        failed_count = post_remediation_telemetry.get("failed_tests", 0)
        has_error = post_remediation_telemetry.get("has_active_incidents", False)

        if failed_count == 0 and not has_error:
            explanation = (
                f"Action '{action.action_id}' successfully eliminated root cause "
                f"'{action.target_root_cause_id}'. Telemetry restored to normal."
            )
            report.audit_trail.append(f"OUTCOME_RECONCILED_SUCCESS: {explanation}")
            return True, explanation

        explanation = (
            f"Action '{action.action_id}' did NOT resolve the incident. "
            f"Active errors remain: failed_tests={failed_count}, has_incidents={has_error}."
        )
        report.audit_trail.append(f"OUTCOME_RECONCILED_FAILURE: {explanation}")
        return False, explanation
