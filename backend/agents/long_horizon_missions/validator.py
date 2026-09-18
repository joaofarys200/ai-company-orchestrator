"""
JARVIS OS — Phase 67: Long-Horizon Autonomous Engineering Missions
Mission & Plan Integrity Validator.
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

from backend.agents.long_horizon_missions.models import (
    LongHorizonMission,
    Milestone,
    MissionObjective,
    MissionPlan,
    ObjectiveCategory,
)


class MissionValidationError(Exception):
    """Raised when mission validation fails."""
    pass


class MissionValidator:
    """Validates structural and semantic invariants of missions and plans."""

    @staticmethod
    def validate_mission_creation(
        objective: str,
        success_criteria: List[str],
        objectives: List[MissionObjective],
    ) -> Tuple[bool, List[str]]:
        errors: List[str] = []
        if not objective or not objective.strip():
            errors.append("MISSING_OBJECTIVE_DESCRIPTION")
        if not success_criteria:
            errors.append("EMPTY_SUCCESS_CRITERIA")

        primaries = [o for o in objectives if o.category == ObjectiveCategory.PRIMARY_OBJECTIVES]
        if not primaries:
            errors.append("NO_PRIMARY_OBJECTIVES_DEFINED")

        return len(errors) == 0, errors

    @staticmethod
    def validate_plan_dag(plan: MissionPlan) -> Tuple[bool, List[str]]:
        errors: List[str] = []
        if not plan.milestones:
            errors.append("PLAN_HAS_NO_MILESTONES")

        # Verify all dependencies exist in plan
        for m_id, m in plan.milestones.items():
            for dep in m.dependencies:
                if dep not in plan.milestones:
                    errors.append(f"MISSING_DEPENDENCY: Milestone '{m_id}' depends on nonexistent '{dep}'")

        # Verify topological order contains all milestones
        if len(plan.topological_order) != len(plan.milestones):
            errors.append("TOPOLOGICAL_ORDER_MISMATCH")

        return len(errors) == 0, errors
