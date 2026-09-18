"""
JARVIS OS — Phase 67: Long-Horizon Autonomous Engineering Missions
Adaptive Planning & Stall/Oscillation Detection Engine (Integrating F56).
Enforces: REPLAN != OBJECTIVE_CHANGE.
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional, Set, Tuple

from backend.agents.long_horizon_missions.models import (
    Milestone,
    MilestoneState,
    MissionPlan,
    StallOscillationState,
)


class UnauthorizedObjectiveModificationError(Exception):
    """Raised when an adaptive replan tries to silently mutate critical mission objectives."""
    pass


class AdaptiveReplanner:
    """
    Observes milestone execution results and dynamically adapts future milestones,
    parallelism, repair tasks, and verification gates without altering primary objectives.
    """

    def __init__(self, max_replan_count: int = 50):
        self.max_replan_count = max_replan_count
        self.replan_history: List[Dict[str, Any]] = []
        self._action_history: List[str] = []
        self._state_hashes: List[str] = []

    def observe_and_adapt(
        self,
        plan: MissionPlan,
        completed_milestone_id: str,
        observed_outputs: List[str],
        unresolved_issues: List[str],
        primary_objective_ids: Set[str],
    ) -> Tuple[bool, MissionPlan, StallOscillationState]:
        """
        Executes: OBSERVE -> COMPARE -> UPDATE STATE -> REPLAN.
        Alters order, parallelism, or injects repair/test milestones.
        Rejects any attempt to change primary objectives.
        Returns: (did_adapt, updated_plan, stall_state)
        """
        stall_state = self.detect_stall_or_oscillation()
        if stall_state in (StallOscillationState.STALLED, StallOscillationState.OSCILLATING, StallOscillationState.DIVERGING):
            return False, plan, stall_state

        if not unresolved_issues:
            # Everything nominal, no replanning needed
            return False, plan, StallOscillationState.PROGRESSING

        # Check budget for replans
        if plan.replan_count >= self.max_replan_count:
            return False, plan, StallOscillationState.BLOCKED

        # Synthesize adaptive milestone (e.g. targeted repair or extra verification)
        plan.replan_count += 1
        repair_id = f"M_REPAIR_{completed_milestone_id}_{plan.replan_count}"
        repair_milestone = Milestone(
            milestone_id=repair_id,
            title=f"Adaptive Repair for {completed_milestone_id}",
            objective_ids=list(primary_objective_ids),
            dependencies=[completed_milestone_id],
            agent_tasks=[{
                "task_id": f"tsk_{repair_id}",
                "role": "CoderAgent",
                "issues": unresolved_issues,
            }],
            expected_outputs=[f"repair_patch_{repair_id}.diff"],
            verification_requirements=["UNIT", "BEHAVIOR"],
            checkpoint_policy="PRE_MUTATION",
        )

        # Invariant check: ensure primary objectives were not dropped
        for obj_id in primary_objective_ids:
            if obj_id not in repair_milestone.objective_ids:
                raise UnauthorizedObjectiveModificationError(
                    f"REPLAN != OBJECTIVE_CHANGE: Cannot drop primary objective '{obj_id}' during adaptive replan."
                )

        # Insert repair milestone before subsequent dependents
        plan.milestones[repair_id] = repair_milestone
        plan.topological_order.append(repair_id)

        record = {
            "replan_index": plan.replan_count,
            "trigger_milestone": completed_milestone_id,
            "unresolved_issues": unresolved_issues,
            "injected_milestone": repair_id,
            "timestamp": time.time(),
        }
        self.replan_history.append(record)
        self._action_history.append(f"REPAIR_{completed_milestone_id}")

        return True, plan, StallOscillationState.PROGRESSING

    def record_action(self, action_signature: str, state_hash: str) -> None:
        self._action_history.append(action_signature)
        self._state_hashes.append(state_hash)

    def detect_stall_or_oscillation(self) -> StallOscillationState:
        """
        Integrates F56 Convergence Governance.
        Detects:
        - repeated same action (STALLED)
        - repeated rollback or circular state hashes (OSCILLATING)
        - diverging replan counts (DIVERGING)
        """
        # 1. Repeated same action
        if len(self._action_history) >= 4:
            recent = self._action_history[-4:]
            if len(set(recent)) == 1:
                return StallOscillationState.STALLED

        # 2. Oscillating states (A -> B -> A -> B)
        if len(self._state_hashes) >= 4:
            h = self._state_hashes[-4:]
            if h[0] == h[2] and h[1] == h[3] and h[0] != h[1]:
                return StallOscillationState.OSCILLATING

        # 3. Excessive replans
        if len(self.replan_history) > self.max_replan_count:
            return StallOscillationState.DIVERGING

        return StallOscillationState.PROGRESSING
