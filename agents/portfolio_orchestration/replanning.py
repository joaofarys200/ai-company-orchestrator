"""
JARVIS OS — Phase 75: Autonomous Engineering Strategy & Portfolio Orchestration
Module: replanning.py
Dynamic portfolio replanning, completed work preservation, evidence invalidation,
and loop-bounded recovery.
"""

from __future__ import annotations

import time
import uuid
from typing import Dict, List, Optional, Set, Tuple

from .dependency_graph import DependencyGraphEngine
from .evaluator import PortfolioEvaluator
from .models import (
    EngineeringInitiative,
    InitiativeState,
    PortfolioRoadmap,
    ReplanningEvent,
    ReplanningLoopError,
    ReplanningTriggerType,
)
from .roadmap import RoadmapGenerator
from .scheduler import CapacityScheduler


class PortfolioReplanningEngine:
    """
    Manages replanning when an initiative fails, costs deviate, or evidence is invalidated.
    Guarantees that completed work is preserved, stale downstream evidence is invalidated,
    and replanning attempts are strictly bounded to prevent infinite cycles.
    """

    def __init__(
        self,
        evaluator: Optional[PortfolioEvaluator] = None,
        scheduler: Optional[CapacityScheduler] = None,
        roadmap_gen: Optional[RoadmapGenerator] = None,
        graph_engine: Optional[DependencyGraphEngine] = None,
        max_replan_attempts: int = 3,
    ):
        self.evaluator = evaluator or PortfolioEvaluator()
        self.scheduler = scheduler or CapacityScheduler()
        self.roadmap_gen = roadmap_gen or RoadmapGenerator()
        self.graph_engine = graph_engine or DependencyGraphEngine()
        self.max_replan_attempts = max_replan_attempts
        self.replan_history: List[ReplanningEvent] = []

    def replan_on_failure(
        self,
        current_roadmap: PortfolioRoadmap,
        failed_initiative_id: str,
        initiatives: Dict[str, EngineeringInitiative],
        total_budget: float,
        total_effort: float,
        error_reason: str = "Execution failed",
    ) -> Tuple[PortfolioRoadmap, ReplanningEvent]:
        """
        Handle execution failure of an initiative:
        1. Bounded attempt guard check.
        2. Preserve COMPLETED initiatives.
        3. Mark failed initiative as FAILED.
        4. Invalidate and defer dependent downstream initiatives.
        5. Re-evaluate and re-schedule remaining candidates with remaining budget.
        6. Produce new versioned roadmap.
        """
        if len(self.replan_history) >= self.max_replan_attempts:
            raise ReplanningLoopError(
                f"Maximum replanning limit ({self.max_replan_attempts}) reached for roadmap '{current_roadmap.roadmap_id}'."
            )

        # 1. Identify completed vs failed vs remaining
        completed_ids = [
            i_id for i_id in current_roadmap.selected_initiatives
            if initiatives.get(i_id) and initiatives[i_id].state == InitiativeState.COMPLETED
        ]

        if failed_initiative_id in initiatives:
            initiatives[failed_initiative_id].state = InitiativeState.FAILED
            initiatives[failed_initiative_id].error_message = error_reason

        # 2. Invalidate downstream dependents of the failed initiative
        downstream_affected = set()
        stack = [failed_initiative_id]
        while stack:
            curr = stack.pop()
            for dep in self.graph_engine._dependents.get(curr, set()):
                if dep not in downstream_affected:
                    downstream_affected.add(dep)
                    stack.append(dep)

        for aff_id in downstream_affected:
            if aff_id in initiatives and initiatives[aff_id].state != InitiativeState.COMPLETED:
                initiatives[aff_id].state = InitiativeState.DEFERRED
                initiatives[aff_id].error_message = f"Deferred due to upstream failure of '{failed_initiative_id}'"
                if initiatives[aff_id].evidence:
                    initiatives[aff_id].evidence.is_valid = False

        # 3. Compute remaining budget
        spent_cost = sum(initiatives[c].actual_cost or initiatives[c].budget_cost for c in completed_ids)
        spent_effort = sum(initiatives[c].effort_units for c in completed_ids)
        remaining_budget = max(0.0, total_budget - spent_cost)
        remaining_effort = max(0.0, total_effort - spent_effort)

        # 4. Filter unexecuted viable candidates
        unexecuted_candidates = [
            init for init in initiatives.values()
            if init.id not in completed_ids
            and init.id != failed_initiative_id
            and init.id not in downstream_affected
            and init.state not in (InitiativeState.FAILED, InitiativeState.CANCELLED)
        ]

        # 5. Re-evaluate remaining portfolio
        eval_result = self.evaluator.select_optimal_portfolio(
            candidates=unexecuted_candidates,
            max_cost=remaining_budget,
            max_effort=remaining_effort,
        )

        # Combine preserved completed work with newly selected remaining initiatives
        new_selected = completed_ids + eval_result.selected_initiatives
        new_rejected = sorted(list(
            (set(current_roadmap.selected_initiatives) | set(current_roadmap.rejected_initiatives))
            - set(new_selected)
        ))

        # 6. Re-schedule remaining work (completed work is not re-executed)
        active_remaining = eval_result.selected_initiatives
        new_schedule = self.scheduler.build_schedule(
            portfolio_id=current_roadmap.portfolio_id,
            selected_ids=active_remaining,
            initiatives=initiatives,
        )

        # 7. Generate incremented roadmap version
        major, minor, patch = self._parse_version(current_roadmap.version)
        new_version = f"v{major}.{minor + 1}.0"

        new_roadmap = self.roadmap_gen.generate_roadmap(
            portfolio_id=current_roadmap.portfolio_id,
            version=new_version,
            selected_initiatives=new_selected,
            rejected_initiatives=new_rejected,
            schedule=new_schedule,
            initiatives=initiatives,
            rationale=(
                f"Replanned after failure of '{failed_initiative_id}'. "
                f"Preserved {len(completed_ids)} completed initiatives. "
                f"Deferred {len(downstream_affected)} dependent initiatives. "
                f"Re-scheduled {len(active_remaining)} viable initiatives under remaining budget ${remaining_budget:.1f}."
            ),
        )

        event = ReplanningEvent(
            event_id=f"replan_{uuid.uuid4().hex[:8]}",
            roadmap_id=current_roadmap.roadmap_id,
            trigger_type=ReplanningTriggerType.INITIATIVE_FAILURE,
            failed_initiative_id=failed_initiative_id,
            affected_initiatives=sorted(list(downstream_affected)),
            previous_version=current_roadmap.version,
            new_version=new_version,
            preserved_initiatives=completed_ids,
            reason=error_reason,
            timestamp=time.time(),
        )
        self.replan_history.append(event)
        return new_roadmap, event

    def _parse_version(self, v_str: str) -> Tuple[int, int, int]:
        """Parse version string like 'v1.0.0'."""
        clean = v_str.lstrip("v")
        parts = clean.split(".")
        try:
            return int(parts[0]), int(parts[1]), int(parts[2])
        except (ValueError, IndexError):
            return 1, 0, 0
