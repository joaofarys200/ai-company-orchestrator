"""
JARVIS OS — Phase 67: Long-Horizon Autonomous Engineering Missions
Mission State Machine & Transition Rules.
Enforces the 19 valid states and strictly forbids illegal state leaps (e.g. CREATED -> COMPLETED).
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional, Set, Tuple

from backend.agents.long_horizon_missions.models import (
    LongHorizonMission,
    MissionState,
)


class InvalidStateTransitionError(Exception):
    """Raised when an illegal mission state transition is attempted."""
    pass


class MissionStateMachine:
    """
    Guards mission state transitions according to the bounded pipeline:
    START (CREATED) -> PLAN -> EXECUTE -> WAIT -> COLLECT -> VERIFY -> CHECKPOINT -> ADAPT -> CONTINUE -> FINISH -> COMPLETED.
    """

    VALID_TRANSITIONS: Dict[MissionState, Set[MissionState]] = {
        MissionState.CREATED: {
            MissionState.PLANNING,
            MissionState.CANCELLED,
        },
        MissionState.PLANNING: {
            MissionState.READY,
            MissionState.BLOCKED,
            MissionState.FAILED,
            MissionState.HUMAN_REVIEW,
            MissionState.CANCELLED,
        },
        MissionState.READY: {
            MissionState.EXECUTING,
            MissionState.PAUSED,
            MissionState.CANCELLED,
            MissionState.BLOCKED,
        },
        MissionState.EXECUTING: {
            MissionState.WAITING,
            MissionState.COLLECTING,
            MissionState.VERIFYING,
            MissionState.ADAPTING,
            MissionState.CHECKPOINTING,
            MissionState.PAUSED,
            MissionState.BLOCKED,
            MissionState.HUMAN_REVIEW,
            MissionState.RECOVERING,
            MissionState.FINISHING,
            MissionState.FAILED,
            MissionState.CANCELLED,
        },
        MissionState.WAITING: {
            MissionState.COLLECTING,
            MissionState.EXECUTING,
            MissionState.BLOCKED,
            MissionState.HUMAN_REVIEW,
            MissionState.FAILED,
            MissionState.PAUSED,
        },
        MissionState.COLLECTING: {
            MissionState.VERIFYING,
            MissionState.EXECUTING,
            MissionState.BLOCKED,
            MissionState.FAILED,
        },
        MissionState.VERIFYING: {
            MissionState.ADAPTING,
            MissionState.CHECKPOINTING,
            MissionState.FINISHING,
            MissionState.BLOCKED,
            MissionState.HUMAN_REVIEW,
            MissionState.RECOVERING,
            MissionState.FAILED,
        },
        MissionState.ADAPTING: {
            MissionState.PLANNING,
            MissionState.EXECUTING,
            MissionState.CHECKPOINTING,
            MissionState.BLOCKED,
            MissionState.HUMAN_REVIEW,
            MissionState.FAILED,
        },
        MissionState.CHECKPOINTING: {
            MissionState.EXECUTING,
            MissionState.FINISHING,
            MissionState.READY,
            MissionState.PAUSED,
            MissionState.BLOCKED,
        },
        MissionState.PAUSED: {
            MissionState.READY,
            MissionState.EXECUTING,
            MissionState.CANCELLED,
        },
        MissionState.BLOCKED: {
            MissionState.HUMAN_REVIEW,
            MissionState.RECOVERING,
            MissionState.CANCELLED,
            MissionState.FAILED,
        },
        MissionState.HUMAN_REVIEW: {
            MissionState.READY,
            MissionState.EXECUTING,
            MissionState.ADAPTING,
            MissionState.BLOCKED,
            MissionState.CANCELLED,
            MissionState.FAILED,
        },
        MissionState.RECOVERING: {
            MissionState.READY,
            MissionState.EXECUTING,
            MissionState.ROLLED_BACK,
            MissionState.BLOCKED,
            MissionState.HUMAN_REVIEW,
            MissionState.FAILED,
        },
        MissionState.FINISHING: {
            MissionState.COMPLETED,
            MissionState.INCONCLUSIVE,
            MissionState.FAILED,
            MissionState.ROLLED_BACK,
        },
        MissionState.COMPLETED: set(),
        MissionState.FAILED: set(),
        MissionState.CANCELLED: set(),
        MissionState.ROLLED_BACK: set(),
        MissionState.INCONCLUSIVE: set(),
    }

    @classmethod
    def can_transition(cls, from_state: MissionState, to_state: MissionState) -> bool:
        allowed = cls.VALID_TRANSITIONS.get(from_state, set())
        return to_state in allowed

    @classmethod
    def transition(
        cls,
        mission: LongHorizonMission,
        target_state: MissionState,
        reason: Optional[str] = None,
    ) -> MissionState:
        """
        Executes a validated state transition on the mission.
        Throws InvalidStateTransitionError if forbidden (e.g. CREATED -> COMPLETED).
        """
        current = mission.current_state
        if not cls.can_transition(current, target_state):
            raise InvalidStateTransitionError(
                f"Forbidden state transition: cannot jump directly from {current.value} -> {target_state.value}. "
                f"Reason: {reason or 'Invalid mission state machine sequence'}"
            )

        now = time.time()
        mission.current_state = target_state
        mission.updated_at = now
        mission.state_history.append((target_state.value, now))
        return target_state
