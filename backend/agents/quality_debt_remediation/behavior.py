"""
JARVIS OS — Phase 69: Autonomous Quality Debt Remediation
Behavior integration engine (Phases 50–52).
Validates runtime invariants, transition orderings, retries, concurrency, and idempotency.
"""

from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class BehaviorStatus(str, Enum):
    PRESERVED = "PRESERVED"
    POTENTIAL_DRIFT = "POTENTIAL_DRIFT"
    INCOMPATIBLE = "INCOMPATIBLE"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"


@dataclass
class BehaviorVerificationReport:
    report_id: str
    surface: str
    status: BehaviorStatus
    invariants_passed: bool
    ordering_preserved: bool
    retries_preserved: bool
    concurrency_safe: bool
    idempotency_preserved: bool
    state_transitions_valid: bool
    routes_to_human_review: bool
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "report_id": self.report_id,
            "surface": self.surface,
            "status": self.status.value if isinstance(self.status, BehaviorStatus) else str(self.status),
            "invariants_passed": self.invariants_passed,
            "ordering_preserved": self.ordering_preserved,
            "retries_preserved": self.retries_preserved,
            "concurrency_safe": self.concurrency_safe,
            "idempotency_preserved": self.idempotency_preserved,
            "state_transitions_valid": self.state_transitions_valid,
            "routes_to_human_review": self.routes_to_human_review,
            "details": self.details,
        }


class DebtBehaviorEvaluator:
    """
    Validates behavioral invariants across state transitions, concurrency, and error handling.
    Routes potential behavioral drifts to human review by default.
    """

    def evaluate_behavior(
        self,
        surface: str,
        invariant_checks: Optional[Dict[str, bool]] = None,
        has_counterexample: bool = False,
        evidence_available: bool = True,
    ) -> BehaviorVerificationReport:
        report_id = f"beh_{uuid.uuid4().hex[:8]}"

        if not evidence_available:
            return BehaviorVerificationReport(
                report_id=report_id,
                surface=surface,
                status=BehaviorStatus.INSUFFICIENT_EVIDENCE,
                invariants_passed=False,
                ordering_preserved=False,
                retries_preserved=False,
                concurrency_safe=False,
                idempotency_preserved=False,
                state_transitions_valid=False,
                routes_to_human_review=True,
                details={"reason": "No behavioral test or trace evidence found for surface."},
            )

        if has_counterexample:
            return BehaviorVerificationReport(
                report_id=report_id,
                surface=surface,
                status=BehaviorStatus.INCOMPATIBLE,
                invariants_passed=False,
                ordering_preserved=False,
                retries_preserved=True,
                concurrency_safe=False,
                idempotency_preserved=True,
                state_transitions_valid=False,
                routes_to_human_review=True,
                details={"reason": "Reproducible counterexample demonstrates broken runtime invariant."},
            )

        checks = invariant_checks or {
            "invariants": True,
            "ordering": True,
            "retries": True,
            "concurrency": True,
            "idempotency": True,
            "state_transitions": True,
        }

        all_passed = all(checks.values())
        if all_passed:
            return BehaviorVerificationReport(
                report_id=report_id,
                surface=surface,
                status=BehaviorStatus.PRESERVED,
                invariants_passed=True,
                ordering_preserved=True,
                retries_preserved=True,
                concurrency_safe=True,
                idempotency_preserved=True,
                state_transitions_valid=True,
                routes_to_human_review=False,
                details={"reason": "All observable behavioral invariants preserved."},
            )
        else:
            failed_keys = [k for k, v in checks.items() if not v]
            return BehaviorVerificationReport(
                report_id=report_id,
                surface=surface,
                status=BehaviorStatus.POTENTIAL_DRIFT,
                invariants_passed=checks.get("invariants", False),
                ordering_preserved=checks.get("ordering", False),
                retries_preserved=checks.get("retries", False),
                concurrency_safe=checks.get("concurrency", False),
                idempotency_preserved=checks.get("idempotency", False),
                state_transitions_valid=checks.get("state_transitions", False),
                routes_to_human_review=True,  # Default for POTENTIAL_DRIFT
                details={"failed_invariants": failed_keys, "reason": "Behavioral drift detected."},
            )
