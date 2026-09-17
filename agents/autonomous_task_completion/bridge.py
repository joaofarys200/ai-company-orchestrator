"""
JARVIS OS — Phase 57: Autonomous Task Completion Bridge
Provides the primary facade connecting WebSocket handlers, Mission Control Center,
and background orchestration engines to the Autonomous Task Completion Layer.
"""

from __future__ import annotations

from typing import Any

from .executor import AutonomousMissionExecutor
from .mission import AutonomousMissionManager
from .models import AutonomousMission, CompletionDecision, MissionCheckpointState, MissionState


class AutonomousTaskCompletionBridge:
    """Central interface for Autonomous Task Completion & Mission Closure."""

    _active_missions: dict[str, AutonomousMission] = {}

    @classmethod
    def run_intent_to_completion(
        cls,
        raw_intent: str,
        mission_id: str | None = None,
        force_browser: bool = False,
        **kwargs: Any,
    ) -> AutonomousMission:
        mission = AutonomousMissionExecutor.run_mission(
            raw_intent=raw_intent,
            mission_id=mission_id,
            force_browser=force_browser,
            **kwargs,
        )
        cls._active_missions[mission.mission_id] = mission
        return mission

    @classmethod
    def get_mission(cls, mission_id: str) -> AutonomousMission | None:
        return cls._active_missions.get(mission_id)

    @classmethod
    def list_missions(cls) -> list[dict[str, Any]]:
        return [m.to_dict() for m in cls._active_missions.values()]

    @classmethod
    def respond_human_ticket(
        cls,
        mission_id: str,
        ticket_id: str,
        resolution: str,
    ) -> bool:
        mission = cls.get_mission(mission_id)
        if not mission:
            return False
        return AutonomousMissionManager.resolve_human_ticket(
            mission=mission,
            ticket_id=ticket_id,
            resolution=resolution,
        )

    @classmethod
    def cancel_mission(cls, mission_id: str, reason: str = "User manual cancel") -> bool:
        mission = cls.get_mission(mission_id)
        if not mission:
            return False
        AutonomousMissionManager.cancel_mission(mission, reason=reason)
        return True

    @classmethod
    def restore_checkpoint(
        cls,
        mission_id: str,
        checkpoint_id: str,
    ) -> bool:
        mission = cls.get_mission(mission_id)
        if not mission:
            return False
        target_cp = next((c for c in mission.checkpoints if c.checkpoint_id == checkpoint_id), None)
        if not target_cp:
            return False

        # Restore state to last safe checkpoint
        mission.final_state_hash = target_cp.state_hash
        mission.metadata["restored_from_checkpoint"] = checkpoint_id
        return True
