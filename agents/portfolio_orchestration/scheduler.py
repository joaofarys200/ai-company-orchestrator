"""
JARVIS OS — Phase 75: Autonomous Engineering Strategy & Portfolio Orchestration
Module: scheduler.py
Capacity, dependency, and resource-aware roadmap scheduling integrating with Phase 66 claims.
"""

from __future__ import annotations

import time
import uuid
from typing import Dict, List, Optional, Set, Tuple

try:
    from agents.multi_agent_coordination.claims import ClaimManager
    from agents.multi_agent_coordination.models import (
        ClaimType,
        ResourceClaim,
        ResourceGranularity,
    )
    _HAS_PHASE_66 = True
except ImportError:
    try:
        from agents.multi_agent_coordination.claims import ClaimManager
        from agents.multi_agent_coordination.models import (
            ClaimType,
            ResourceClaim,
            ResourceGranularity,
        )
        _HAS_PHASE_66 = True
    except ImportError:
        _HAS_PHASE_66 = False
        ClaimManager = None  # type: ignore

from .dependency_graph import DependencyGraphEngine
from .models import (
    EngineeringInitiative,
    ExecutionSchedule,
    ExecutionScheduleItem,
)


class CapacityScheduler:
    """
    Schedules selected portfolio initiatives into discrete execution waves respecting
    hard dependencies, agent concurrency bounds, and resource claim compatibility.
    """

    def __init__(
        self,
        graph_engine: Optional[DependencyGraphEngine] = None,
        max_concurrency: int = 2,
        claim_manager: Optional[Any] = None,
    ):
        self.graph_engine = graph_engine or DependencyGraphEngine()
        self.max_concurrency = max_concurrency
        if claim_manager is not None:
            self.claim_manager = claim_manager
        elif _HAS_PHASE_66 and ClaimManager is not None:
            self.claim_manager = ClaimManager(default_ttl_seconds=3600.0)
        else:
            self.claim_manager = None

    def build_schedule(
        self,
        portfolio_id: str,
        selected_ids: List[str],
        initiatives: Dict[str, EngineeringInitiative],
    ) -> ExecutionSchedule:
        """
        Produce a wave-based execution schedule.
        Enforces:
        1. Hard prerequisite ordering (dependencies must be in earlier waves).
        2. Non-concurrency between initiatives modifying overlapping files.
        3. Maximum concurrency limit per wave.
        4. Critical-path calculation.
        """
        if not selected_ids:
            return ExecutionSchedule(
                schedule_id=f"sched_{uuid.uuid4().hex[:8]}",
                portfolio_id=portfolio_id,
                items=[],
                total_waves=0,
                critical_path=[],
            )

        selected_set = set(selected_ids)
        # Verify cycles
        self.graph_engine.detect_cycles(selected_set)

        # Topological sorting
        topo_order = self.graph_engine.get_topological_order(selected_set)

        # Track completed/scheduled waves: initiative_id -> wave_index
        scheduled_wave: Dict[str, int] = {}
        schedule_items: List[ExecutionScheduleItem] = []
        
        # Waves representation: list of lists of initiative IDs
        waves: List[List[str]] = []

        for init_id in topo_order:
            init = initiatives.get(init_id)
            if not init:
                continue

            # Determine earliest possible wave based on prerequisites
            prereqs = self.graph_engine._prerequisites.get(init_id, set()).intersection(selected_set)
            earliest_wave = 0
            if prereqs:
                earliest_wave = max(scheduled_wave[p] for p in prereqs) + 1

            # Find the lowest wave >= earliest_wave that can accommodate init_id
            placed = False
            wave_candidate = earliest_wave

            while not placed:
                if wave_candidate >= len(waves):
                    # Need a new wave
                    waves.append([])

                current_wave = waves[wave_candidate]

                # Check 1: Concurrency limit
                can_fit_capacity = len(current_wave) < self.max_concurrency

                # Check 2: Concurrent safety with all initiatives already in this wave
                can_fit_safety = True
                for existing_id in current_wave:
                    if not self.graph_engine.are_concurrent_safe(init_id, existing_id):
                        can_fit_safety = False
                        break

                # Check 3: Phase 66 Claim reservation compatibility if active
                can_fit_claims = True
                if self.claim_manager:
                    for comp in init.affected_components:
                        norm_res = comp.replace("\\", "/").strip()
                        # Check compatibility against components claimed by current wave
                        for existing_id in current_wave:
                            ex_init = initiatives.get(existing_id)
                            if ex_init and any(c.replace("\\", "/").strip() == norm_res for c in ex_init.affected_components):
                                can_fit_claims = False
                                break
                        if not can_fit_claims:
                            break

                if can_fit_capacity and can_fit_safety and can_fit_claims:
                    waves[wave_candidate].append(init_id)
                    scheduled_wave[init_id] = wave_candidate
                    placed = True
                else:
                    wave_candidate += 1

        # Build schedule items with deterministic agent assignment
        for wave_idx, wave_members in enumerate(waves):
            for agent_idx, init_id in enumerate(sorted(wave_members)):
                init = initiatives[init_id]
                agent_name = f"agent-{agent_idx + 1}"
                schedule_items.append(
                    ExecutionScheduleItem(
                        initiative_id=init_id,
                        wave_index=wave_idx,
                        estimated_duration=init.effort_units * 30.0,
                        assigned_agent=agent_name,
                        claimed_resources=list(init.affected_components),
                    )
                )

        # Critical path calculation: Longest path in DAG by effort_units
        critical_path = self._calculate_critical_path(selected_set, initiatives)

        return ExecutionSchedule(
            schedule_id=f"sched_{uuid.uuid4().hex[:8]}",
            portfolio_id=portfolio_id,
            items=schedule_items,
            total_waves=len(waves),
            critical_path=critical_path,
        )

    def _calculate_critical_path(
        self,
        selected_ids: Set[str],
        initiatives: Dict[str, EngineeringInitiative],
    ) -> List[str]:
        """Compute the critical path (longest duration dependency chain)."""
        topo = self.graph_engine.get_topological_order(selected_ids)
        dist: Dict[str, float] = {i: initiatives[i].effort_units for i in selected_ids}
        pred: Dict[str, Optional[str]] = {i: None for i in selected_ids}

        for u in topo:
            for v in self.graph_engine._dependents.get(u, set()):
                if v in selected_ids:
                    w = initiatives[v].effort_units
                    if dist[u] + w > dist[v]:
                        dist[v] = dist[u] + w
                        pred[v] = u

        if not dist:
            return []

        # Find target with max distance
        end_node = max(dist.keys(), key=lambda k: dist[k])
        path = []
        curr = end_node
        while curr is not None:
            path.append(curr)
            curr = pred.get(curr)

        path.reverse()
        return path
