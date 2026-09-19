"""
JARVIS OS — Phase 69: Autonomous Quality Debt Remediation
Convergence detection engine (Phase 56).
Monitors remediation retry attempts, rollback repetitions, metric oscillations, and cycles.
Halts autonomously when oscillations or divergence are detected.
"""

from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

from .models import ConvergenceState


@dataclass
class ConvergenceReport:
    report_id: str
    debt_id: str
    state: ConvergenceState
    attempt_count: int
    rollback_count: int
    oscillation_detected: bool
    halt_required: bool
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "report_id": self.report_id,
            "debt_id": self.debt_id,
            "state": self.state.value if isinstance(self.state, ConvergenceState) else str(self.state),
            "attempt_count": self.attempt_count,
            "rollback_count": self.rollback_count,
            "oscillation_detected": self.oscillation_detected,
            "halt_required": self.halt_required,
            "details": self.details,
        }


class RemediationConvergenceDetector:
    """
    Monitors repeated remediation attempts to prevent endless loops and degradation cycles.
    """

    def __init__(self, max_attempts: int = 3, max_rollbacks: int = 2):
        self.max_attempts = max_attempts
        self.max_rollbacks = max_rollbacks
        self._history: Dict[str, List[str]] = {}

    def record_event(self, debt_id: str, event_type: str) -> None:
        if debt_id not in self._history:
            self._history[debt_id] = []
        self._history[debt_id].append(event_type)

    def evaluate(
        self,
        debt_id: str,
        attempt_count: int,
        rollback_count: int,
        metric_series: Optional[List[float]] = None,
    ) -> ConvergenceReport:
        report_id = f"cnv_{uuid.uuid4().hex[:8]}"

        # Check for repeated rollbacks
        if rollback_count >= self.max_rollbacks:
            return ConvergenceReport(
                report_id=report_id,
                debt_id=debt_id,
                state=ConvergenceState.BLOCKED,
                attempt_count=attempt_count,
                rollback_count=rollback_count,
                oscillation_detected=True,
                halt_required=True,
                details={"reason": f"Exceeded maximum rollback limit ({self.max_rollbacks}). Hard stop."},
            )

        # Check for attempt exhaustion
        if attempt_count >= self.max_attempts:
            return ConvergenceReport(
                report_id=report_id,
                debt_id=debt_id,
                state=ConvergenceState.HUMAN_REVIEW,
                attempt_count=attempt_count,
                rollback_count=rollback_count,
                oscillation_detected=False,
                halt_required=True,
                details={"reason": f"Maximum remediation attempts ({self.max_attempts}) reached without resolution."},
            )

        # Check metric oscillations
        oscillation = False
        if metric_series and len(metric_series) >= 4:
            # Check for up-down-up-down pattern
            diffs = [metric_series[i + 1] - metric_series[i] for i in range(len(metric_series) - 1)]
            sign_flips = sum(1 for i in range(len(diffs) - 1) if (diffs[i] * diffs[i + 1]) < 0)
            if sign_flips >= 2:
                oscillation = True
                return ConvergenceReport(
                    report_id=report_id,
                    debt_id=debt_id,
                    state=ConvergenceState.OSCILLATING,
                    attempt_count=attempt_count,
                    rollback_count=rollback_count,
                    oscillation_detected=True,
                    halt_required=True,
                    details={"reason": "Quality metric oscillation pattern detected across iterations."},
                )

        if attempt_count == 0:
            state = ConvergenceState.STABLE
        elif rollback_count == 0:
            state = ConvergenceState.CONVERGING
        else:
            state = ConvergenceState.STALLED

        return ConvergenceReport(
            report_id=report_id,
            debt_id=debt_id,
            state=state,
            attempt_count=attempt_count,
            rollback_count=rollback_count,
            oscillation_detected=False,
            halt_required=False,
            details={"reason": "Remediation progress within acceptable convergence thresholds."},
        )
