"""
Phase 71 — Deterministic Operational State Machine
Enforces legal operational state transitions and rejects illegal skips or promotions.
"""

from __future__ import annotations

from typing import Dict, Optional, Set
from .models import OperationalState


class InvalidStateTransitionError(ValueError):
    """Raised when an illegal transition is attempted in the operational state machine."""
    pass


class OperationalStateMachine:
    """
    Deterministic finite state machine governing production operations lifecycle.
    """

    ALLOWED_TRANSITIONS: Dict[OperationalState, Set[OperationalState]] = {
        OperationalState.READY_FOR_OPERATIONS: {
            OperationalState.STARTING,
            OperationalState.DEPLOYMENT_NOT_AVAILABLE,
            OperationalState.OPERATIONS_BLOCKED,
        },
        OperationalState.STARTING: {
            OperationalState.HEALTHY,
            OperationalState.DEGRADED,
            OperationalState.INCIDENT_DETECTED,
            OperationalState.OPERATIONS_BLOCKED,
            OperationalState.TERMINATED,
        },
        OperationalState.HEALTHY: {
            OperationalState.DEGRADED,
            OperationalState.INCIDENT_DETECTED,
            OperationalState.TERMINATED,
        },
        OperationalState.DEGRADED: {
            OperationalState.HEALTHY,
            OperationalState.INCIDENT_DETECTED,
            OperationalState.DIAGNOSING,
            OperationalState.ESCALATED,
            OperationalState.TERMINATED,
        },
        OperationalState.INCIDENT_DETECTED: {
            OperationalState.DIAGNOSING,
            OperationalState.ESCALATED,
            OperationalState.OPERATIONS_BLOCKED,
        },
        OperationalState.DIAGNOSING: {
            OperationalState.RECOVERY_PLANNED,
            OperationalState.ROLLBACK_PLANNED,
            OperationalState.ESCALATED,
            OperationalState.OPERATIONS_BLOCKED,
        },
        OperationalState.RECOVERY_PLANNED: {
            OperationalState.RECOVERING,
            OperationalState.ESCALATED,
            OperationalState.OPERATIONS_BLOCKED,
        },
        OperationalState.RECOVERING: {
            OperationalState.VERIFYING_RECOVERY,
            OperationalState.ESCALATED,
            OperationalState.OPERATIONS_BLOCKED,
        },
        OperationalState.VERIFYING_RECOVERY: {
            OperationalState.RECOVERED,
            OperationalState.ROLLBACK_PLANNED,
            OperationalState.ESCALATED,
            OperationalState.RECOVERING,
        },
        OperationalState.RECOVERED: {
            OperationalState.HEALTHY,
            OperationalState.DEGRADED,
            OperationalState.INCIDENT_DETECTED,
        },
        OperationalState.ROLLBACK_PLANNED: {
            OperationalState.ROLLING_BACK,
            OperationalState.ESCALATED,
            OperationalState.OPERATIONS_BLOCKED,
        },
        OperationalState.ROLLING_BACK: {
            OperationalState.VERIFYING_ROLLBACK,
            OperationalState.ESCALATED,
            OperationalState.OPERATIONS_BLOCKED,
        },
        OperationalState.VERIFYING_ROLLBACK: {
            OperationalState.ROLLED_BACK,
            OperationalState.ESCALATED,
            OperationalState.ROLLING_BACK,
        },
        OperationalState.ROLLED_BACK: {
            OperationalState.HEALTHY,
            OperationalState.DEGRADED,
            OperationalState.INCIDENT_DETECTED,
            OperationalState.OPERATIONS_BLOCKED,
            OperationalState.TERMINATED,
        },
        OperationalState.ESCALATED: {
            OperationalState.DIAGNOSING,
            OperationalState.RECOVERY_PLANNED,
            OperationalState.ROLLBACK_PLANNED,
            OperationalState.OPERATIONS_BLOCKED,
            OperationalState.TERMINATED,
        },
        OperationalState.OPERATIONS_BLOCKED: {
            OperationalState.DIAGNOSING,
            OperationalState.ESCALATED,
            OperationalState.TERMINATED,
        },
        OperationalState.DEPLOYMENT_NOT_AVAILABLE: {
            OperationalState.READY_FOR_OPERATIONS,
            OperationalState.TERMINATED,
        },
        OperationalState.TERMINATED: set(),
    }

    # Explicitly forbidden transitions for fast detection and descriptive audit
    FORBIDDEN_RULES = [
        (OperationalState.HEALTHY, OperationalState.RECOVERED, "HEALTHY cannot transition to RECOVERED without an incident cycle"),
        (OperationalState.HEALTHY, OperationalState.ROLLED_BACK, "HEALTHY cannot transition directly to ROLLED_BACK"),
        (OperationalState.INCIDENT_DETECTED, OperationalState.HEALTHY, "INCIDENT_DETECTED cannot jump directly to HEALTHY without diagnosis/verification"),
        (OperationalState.DEPLOYMENT_NOT_AVAILABLE, OperationalState.HEALTHY, "DEPLOYMENT_NOT_AVAILABLE cannot declare HEALTHY without observed runtime environment"),
    ]

    def __init__(self, initial_state: OperationalState = OperationalState.READY_FOR_OPERATIONS):
        self._current_state: OperationalState = initial_state
        self._transition_history: list[tuple[OperationalState, OperationalState, str]] = []

    @property
    def current_state(self) -> OperationalState:
        return self._current_state

    def can_transition_to(self, target_state: OperationalState) -> bool:
        allowed = self.ALLOWED_TRANSITIONS.get(self._current_state, set())
        return target_state in allowed

    def transition_to(self, target_state: OperationalState, reason: str = "") -> OperationalState:
        if not self.can_transition_to(target_state):
            # Check if it violates an explicit invariant rule
            for src, dst, rule_msg in self.FORBIDDEN_RULES:
                if self._current_state == src and target_state == dst:
                    raise InvalidStateTransitionError(
                        f"Illegal transition: {self._current_state.value} -> {target_state.value}. Rule: {rule_msg}"
                    )
            raise InvalidStateTransitionError(
                f"Illegal transition from {self._current_state.value} to {target_state.value}. "
                f"Allowed transitions: {[s.value for s in self.ALLOWED_TRANSITIONS.get(self._current_state, set())]}"
            )

        prev = self._current_state
        self._current_state = target_state
        self._transition_history.append((prev, target_state, reason))
        return self._current_state

    def get_history(self) -> list[tuple[OperationalState, OperationalState, str]]:
        return list(self._transition_history)
