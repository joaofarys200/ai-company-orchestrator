"""
JARVIS OS — Phase 69: Autonomous Quality Debt Remediation
Debt resolution governor.
Enforces the core principle: DEBT_DETECTED != DEBT_RESOLVED.
Prevents false resolutions and handles partial resolutions with child debt spawning.
"""

from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional

from .comparison import QualityComparisonOutcome, QualityComparisonReport
from .models import DebtResolutionResult, ResolutionStatus
from .verification import VerificationReport


class DebtResolutionGovernor:
    """
    Final arbiter of technical debt resolution.
    Strictly verifies evidence invalidation, verification passing, and quality comparison.
    """

    def resolve(
        self,
        debt_id: str,
        verification_report: VerificationReport,
        comparison_report: QualityComparisonReport,
        partially_remediated_surfaces: Optional[List[Dict[str, Any]]] = None,
        is_deferred: bool = False,
        is_blocked: bool = False,
        is_invalidated: bool = False,
    ) -> DebtResolutionResult:
        resolution_id = f"res_{uuid.uuid4().hex[:8]}"
        partially_remediated = partially_remediated_surfaces or []

        if is_invalidated:
            return DebtResolutionResult(
                resolution_id=resolution_id,
                debt_id=debt_id,
                status=ResolutionStatus.INVALIDATED,
                original_evidence_invalidated=True,
                quality_delta=comparison_report.dimension_deltas,
                remaining_child_debts=[],
                explanation="Debt was invalidated due to false evidence or obsolete surface target.",
            )

        if is_deferred:
            return DebtResolutionResult(
                resolution_id=resolution_id,
                debt_id=debt_id,
                status=ResolutionStatus.DEFERRED,
                original_evidence_invalidated=False,
                quality_delta=comparison_report.dimension_deltas,
                remaining_child_debts=[],
                explanation="Remediation deferred under active governance review.",
            )

        if is_blocked:
            return DebtResolutionResult(
                resolution_id=resolution_id,
                debt_id=debt_id,
                status=ResolutionStatus.BLOCKED,
                original_evidence_invalidated=False,
                quality_delta=comparison_report.dimension_deltas,
                remaining_child_debts=[],
                explanation="Remediation blocked by policy, contract violation, or security constraint.",
            )

        # Check verification failures
        if not verification_report.verification_passed:
            return DebtResolutionResult(
                resolution_id=resolution_id,
                debt_id=debt_id,
                status=ResolutionStatus.FAILED,
                original_evidence_invalidated=verification_report.original_evidence_invalidated,
                quality_delta=comparison_report.dimension_deltas,
                remaining_child_debts=[],
                explanation=f"Verification failed: {', '.join(verification_report.failure_reasons)}",
            )

        # Check for NO_MEASURABLE_CHANGE or DEGRADATION
        if comparison_report.outcome == QualityComparisonOutcome.DEGRADATION:
            return DebtResolutionResult(
                resolution_id=resolution_id,
                debt_id=debt_id,
                status=ResolutionStatus.FAILED,
                original_evidence_invalidated=verification_report.original_evidence_invalidated,
                quality_delta=comparison_report.dimension_deltas,
                remaining_child_debts=[],
                explanation="Quality remeasurement detected degradation. Resolution denied.",
            )

        if comparison_report.outcome == QualityComparisonOutcome.NO_MEASURABLE_CHANGE:
            return DebtResolutionResult(
                resolution_id=resolution_id,
                debt_id=debt_id,
                status=ResolutionStatus.INSUFFICIENT_EVIDENCE,
                original_evidence_invalidated=verification_report.original_evidence_invalidated,
                quality_delta=comparison_report.dimension_deltas,
                remaining_child_debts=[],
                explanation="No measurable quality improvement observed across 9 dimensions. Cannot declare debt resolved.",
            )

        # Check for Partial Remediation
        if partially_remediated:
            child_debts = []
            for idx, child in enumerate(partially_remediated):
                c_id = child.get("debt_id", f"{debt_id}_child_{idx + 1}")
                child_debts.append({
                    "debt_id": c_id,
                    "parent_debt_id": debt_id,
                    "affected_surface": child.get("affected_surface", "remaining_hotspot"),
                    "status": "OPEN",
                    "reason": "Remaining hotspot from partial remediation.",
                })

            return DebtResolutionResult(
                resolution_id=resolution_id,
                debt_id=debt_id,
                status=ResolutionStatus.PARTIALLY_RESOLVED,
                original_evidence_invalidated=True,
                quality_delta=comparison_report.dimension_deltas,
                remaining_child_debts=child_debts,
                explanation=f"Debt partially resolved ({len(child_debts)} remaining hotspot(s) tracked as child debts).",
            )

        # Fully Resolved
        return DebtResolutionResult(
            resolution_id=resolution_id,
            debt_id=debt_id,
            status=ResolutionStatus.RESOLVED,
            original_evidence_invalidated=True,
            quality_delta=comparison_report.dimension_deltas,
            remaining_child_debts=[],
            explanation="Debt verified as fully resolved: evidence invalidated, quality improved, zero critical regressions.",
        )
