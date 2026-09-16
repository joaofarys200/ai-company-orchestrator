"""
JARVIS OS — Phase 56: Convergence Security Sentinel
Sovereign security authority blocking spoofing attempts, memory poisoning, and unauthorized perimeter mutations.
"""

from __future__ import annotations

from typing import Dict, Any, List, Optional, Set, Tuple
from agents.repair_convergence_governance.models import (
    ProgressDelta,
    ProgressVector,
    RepairStepSnapshot,
    TerminationBudget,
)


class ConvergenceSecuritySentinel:
    """Enforces sovereign defense against progress/cycle/risk spoofing and memory poisoning."""

    def __init__(self):
        self.security_violations: List[Dict[str, Any]] = []

    def validate_progress_vector(
        self,
        p_before: ProgressVector,
        p_after: ProgressVector,
        delta: ProgressDelta,
        actual_active_failures: List[str],
    ) -> Tuple[bool, Optional[str]]:
        """Detects progress spoofing (e.g. claiming resolved failures that are still active)."""
        # 1. Check if resolved count claimed exceeds actual resolved
        if p_after.resolved_failures > len(actual_active_failures) + p_before.resolved_failures + 10:
            msg = "Progress spoofing detected: claimed resolved failures exceed maximum possible target domain."
            self._record_violation("PROGRESS_SPOOFING", msg)
            return False, msg

        # 2. Check if positive delta claimed when failure count actually grew
        if delta.score > 0 and len(actual_active_failures) > (p_before.new_failures + len(actual_active_failures)):
            msg = "Progress spoofing detected: positive delta asserted while failure count grew."
            self._record_violation("PROGRESS_SPOOFING", msg)
            return False, msg

        return True, None

    def validate_cycle_integrity(
        self,
        recorded_hashes: List[str],
        verified_history: List[RepairStepSnapshot],
    ) -> Tuple[bool, Optional[str]]:
        """Detects cycle spoofing (erasing or manipulating past state hashes)."""
        if len(recorded_hashes) != len(verified_history):
            msg = f"Cycle spoofing detected: history count {len(verified_history)} != hash record count {len(recorded_hashes)}."
            self._record_violation("CYCLE_SPOOFING", msg)
            return False, msg

        for i, (h, snap) in enumerate(zip(recorded_hashes, verified_history)):
            if snap.state_hash != h:
                msg = f"Cycle spoofing detected: state hash at index {i} altered from {snap.state_hash} to {h}."
                self._record_violation("CYCLE_SPOOFING", msg)
                return False, msg

        return True, None

    def validate_risk_assessment(
        self,
        claimed_risk: float,
        empirical_failure_count: int,
        has_critical_failures: bool,
    ) -> Tuple[bool, Optional[str]]:
        """Detects risk spoofing (arbitrarily claiming zero risk when critical errors persist)."""
        if has_critical_failures and claimed_risk <= 0.05:
            msg = f"Risk spoofing detected: claimed minimal risk {claimed_risk} while critical failures remain active."
            self._record_violation("RISK_SPOOFING", msg)
            return False, msg

        if empirical_failure_count >= 5 and claimed_risk < 0.20:
            msg = f"Risk spoofing detected: claimed risk {claimed_risk} inconsistent with {empirical_failure_count} active failures."
            self._record_violation("RISK_SPOOFING", msg)
            return False, msg

        return True, None

    def validate_budget_integrity(
        self,
        current_budget: TerminationBudget,
        claimed_consumption: int,
    ) -> Tuple[bool, Optional[str]]:
        """Detects budget spoofing (resetting or underreporting consumed steps)."""
        if claimed_consumption < current_budget.consumed_repairs:
            msg = f"Budget spoofing detected: claimed consumption {claimed_consumption} < verified {current_budget.consumed_repairs}."
            self._record_violation("BUDGET_SPOOFING", msg)
            return False, msg

        return True, None

    def _record_violation(self, violation_type: str, detail: str) -> None:
        self.security_violations.append({
            "violation_type": violation_type,
            "detail": detail,
        })
