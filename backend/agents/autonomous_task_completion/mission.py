"""
JARVIS OS — Phase 57: Autonomous Mission Lifecycle & State Machine
Governs mission state transitions, checkpoints, crash recovery, and cancellation.
"""

from __future__ import annotations

import time
import uuid
from typing import Any

from .models import (
    AutonomousMission,
    CompletionDecision,
    HumanReviewTicket,
    MissionCheckpointState,
    MissionHumanReviewReason,
    MissionState,
    TaskUnderstandingResult,
)


class MissionTransitionError(Exception):
    """Raised when an illegal mission state transition is attempted."""


class AutonomousMissionManager:
    """Manages the formal state machine and transitions of an AutonomousMission."""

    # Explicit permitted transitions
    VALID_TRANSITIONS: dict[MissionState, set[MissionState]] = {
        MissionState.CREATED: {MissionState.UNDERSTANDING, MissionState.BLOCKED, MissionState.HUMAN_REVIEW_REQUIRED, MissionState.CANCELLED, MissionState.FAILED},
        MissionState.UNDERSTANDING: {MissionState.PLANNING, MissionState.BLOCKED, MissionState.HUMAN_REVIEW_REQUIRED, MissionState.FAILED, MissionState.CANCELLED},
        MissionState.PLANNING: {MissionState.READY, MissionState.BLOCKED, MissionState.HUMAN_REVIEW_REQUIRED, MissionState.FAILED, MissionState.CANCELLED},
        MissionState.READY: {MissionState.EXECUTING, MissionState.BLOCKED, MissionState.CANCELLED},
        MissionState.EXECUTING: {MissionState.VERIFYING, MissionState.REPAIRING, MissionState.BLOCKED, MissionState.HUMAN_REVIEW_REQUIRED, MissionState.FAILED, MissionState.CANCELLED},
        MissionState.VERIFYING: {MissionState.PROVING, MissionState.REPAIRING, MissionState.CONVERGING, MissionState.BLOCKED, MissionState.HUMAN_REVIEW_REQUIRED, MissionState.FAILED, MissionState.CANCELLED},
        MissionState.REPAIRING: {MissionState.VERIFYING, MissionState.CONVERGING, MissionState.BLOCKED, MissionState.HUMAN_REVIEW_REQUIRED, MissionState.FAILED, MissionState.CANCELLED},
        MissionState.CONVERGING: {MissionState.PROVING, MissionState.REPAIRING, MissionState.BLOCKED, MissionState.HUMAN_REVIEW_REQUIRED, MissionState.FAILED, MissionState.CANCELLED},
        MissionState.PROVING: {MissionState.COMPLETED, MissionState.BLOCKED, MissionState.HUMAN_REVIEW_REQUIRED, MissionState.FAILED, MissionState.CANCELLED},
        MissionState.COMPLETED: set(),  # Terminal
        MissionState.BLOCKED: {MissionState.READY, MissionState.PLANNING, MissionState.EXECUTING, MissionState.CANCELLED, MissionState.FAILED},
        MissionState.HUMAN_REVIEW_REQUIRED: {MissionState.READY, MissionState.PLANNING, MissionState.EXECUTING, MissionState.CANCELLED, MissionState.FAILED},
        MissionState.FAILED: set(),     # Terminal
        MissionState.CANCELLED: set(),  # Terminal
    }

    @classmethod
    def create_mission(
        cls,
        task_understanding: TaskUnderstandingResult,
        mission_id: str | None = None,
    ) -> AutonomousMission:
        from .bridge import AutonomousTaskCompletionBridge
        mid = mission_id or f"msn_{uuid.uuid4().hex[:8]}"
        mission = AutonomousMission(
            mission_id=mid,
            task_id=task_understanding.task_id,
            objective=task_understanding.objective,
            original_objective=task_understanding.objective,
            requirements=task_understanding.requirements,
            acceptance_criteria=task_understanding.acceptance_criteria,
            state=MissionState.CREATED,
            risk=0.1 if task_understanding.risk_level == "LOW" else (0.4 if task_understanding.risk_level == "MEDIUM" else 0.8),
            provenance=task_understanding.provenance,
        )
        AutonomousTaskCompletionBridge._active_missions[mid] = mission
        return mission

    @classmethod
    def transition(
        cls,
        mission: AutonomousMission,
        target_state: MissionState,
        reason: str = "",
        checkpoint_type: MissionCheckpointState | None = None,
        checkpoint_data: dict[str, Any] | None = None,
    ) -> AutonomousMission:
        current = mission.state
        allowed = cls.VALID_TRANSITIONS.get(current, set())
        if target_state not in allowed:
            raise MissionTransitionError(
                f"Transição ilegal de {current.value} para {target_state.value}. Permitidas: {[s.value for s in allowed]}"
            )

        mission.state = target_state
        mission.metadata.setdefault("transition_history", []).append({
            "from": current.value,
            "to": target_state.value,
            "timestamp": time.time(),
            "reason": reason,
        })

        if checkpoint_type:
            mission.add_checkpoint(checkpoint_type, checkpoint_data)

        # Update running state hash
        mission.final_state_hash = mission.compute_current_state_hash()
        return mission

    @classmethod
    def escalate_human_review(
        cls,
        mission: AutonomousMission,
        reason: MissionHumanReviewReason,
        evidence: list[str],
        blocked_action: str,
        possible_next_actions: list[str],
    ) -> HumanReviewTicket:
        ticket = HumanReviewTicket(
            ticket_id=f"tkt_{uuid.uuid4().hex[:6]}",
            mission_id=mission.mission_id,
            reason=reason,
            evidence=evidence,
            blocked_action=blocked_action,
            possible_next_action=possible_next_actions,
            created_at=time.time(),
        )
        mission.human_tickets.append(ticket)
        if mission.state != MissionState.HUMAN_REVIEW_REQUIRED:
            cls.transition(
                mission,
                MissionState.HUMAN_REVIEW_REQUIRED,
                reason=f"Human escalation: {reason.value}",
            )
        return ticket

    @classmethod
    def resolve_human_ticket(
        cls,
        mission: AutonomousMission,
        ticket_id: str,
        resolution: str,
        resume_state: MissionState = MissionState.READY,
    ) -> bool:
        for t in mission.human_tickets:
            if t.ticket_id == ticket_id:
                t.resolved = True
                t.resolution = resolution
                cls.transition(
                    mission,
                    resume_state,
                    reason=f"Human ticket {ticket_id} resolved: {resolution}",
                )
                return True
        return False

    @classmethod
    def cancel_mission(cls, mission: AutonomousMission, reason: str = "User cancelled") -> AutonomousMission:
        if mission.state in (MissionState.COMPLETED, MissionState.FAILED, MissionState.CANCELLED):
            return mission
        mission.state = MissionState.CANCELLED
        mission.final_decision = CompletionDecision.MISSION_BLOCKED
        mission.metadata.setdefault("cancellation_reasons", []).append({
            "timestamp": time.time(),
            "reason": reason,
        })
        mission.final_state_hash = mission.compute_current_state_hash()
        return mission
