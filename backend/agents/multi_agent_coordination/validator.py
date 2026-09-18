"""
JARVIS OS — Phase 66: Multi-Agent Engineering Coordination & Conflict Arbitration
Module: validator.py
CoordinationGateValidator evaluating multi-criteria commit readiness across concurrent agent changes.
Never relies on an isolated boolean.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from .models import AgentChangeSet, MergeResult


class CoordinationGateValidator:
    """Evaluates comprehensive commit readiness for multi-agent coordinated waves."""

    def __init__(self):
        pass

    def evaluate_commit_eligibility(
        self,
        intents_count: int,
        conflicts_count: int,
        arbitrations_count: int,
        merge_results: List[MergeResult],
        shared_verification_passed: bool,
        security_passed: bool,
        provenance_verified: bool,
    ) -> Dict[str, Any]:
        """Verify that all coordinated criteria are satisfied before commit."""
        criteria: Dict[str, bool] = {
            "intents_processed": intents_count > 0,
            "conflicts_arbitrated": conflicts_count == arbitrations_count,
            "merges_successful": all(m.success for m in merge_results) if merge_results else True,
            "shared_verification_passed": shared_verification_passed,
            "security_passed": security_passed,
            "provenance_verified": provenance_verified,
        }

        all_passed = all(criteria.values())
        status = "COMMIT_ELIGIBLE" if all_passed else ("BLOCKED" if not security_passed else "HUMAN_REVIEW")

        return {
            "status": status,
            "is_eligible": all_passed,
            "criteria": criteria,
            "failed_criteria": [k for k, v in criteria.items() if not v],
        }

    def reconcile_denominators(
        self,
        per_phase: Dict[str, int],
        total_declared: int,
    ) -> Dict[str, Any]:
        """Validate sum of per-phase counts against total declared with delta reconciliation check."""
        computed_total = sum(per_phase.values())
        delta = computed_total - total_declared
        valid = (delta == 0)
        return {
            "per_phase": per_phase,
            "computed_total": computed_total,
            "reported_total": total_declared,
            "delta": delta,
            "valid": valid,
            "status": "VALID" if valid else "REGRESSION_REPORT_INVALID",
        }
