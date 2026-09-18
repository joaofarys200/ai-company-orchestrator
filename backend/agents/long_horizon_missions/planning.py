"""
JARVIS OS — Phase 67: Long-Horizon Autonomous Engineering Missions
Mission Planning & Scalable Milestone DAG Engine.
Supports 10, 100, 1,000, and 10,000 Milestone Nodes.
"""

from __future__ import annotations

from collections import deque
import time
from typing import Any, Dict, List, Optional, Set, Tuple
import uuid

from backend.agents.long_horizon_missions.models import (
    Milestone,
    MilestoneState,
    MissionPlan,
)


class CyclicDependencyError(Exception):
    """Raised when a circular dependency is detected in the milestone DAG."""
    pass


class MissionPlanner:
    """
    Constructs, validates, and manages Milestone Directed Acyclic Graphs (DAG).
    Optimized for rapid dependency resolution and topological ordering at large scale (10 to 10,000 nodes).
    """

    def __init__(self, plan: Optional[MissionPlan] = None):
        self.plan = plan

    def create_plan(
        self,
        mission_id: str,
        milestones: List[Milestone],
        edges: Optional[List[Tuple[str, str]]] = None,
    ) -> MissionPlan:
        """
        Creates a new MissionPlan from milestones and dependencies.
        Validates DAG acyclicity and computes topological ordering.
        """
        plan_id = f"plan_{uuid.uuid4().hex[:8]}"
        milestone_dict = {m.milestone_id: m for m in milestones}

        # Build edges from explicit edges or milestone dependencies
        derived_edges: List[Tuple[str, str]] = []
        if edges:
            derived_edges.extend(edges)
        for m in milestones:
            for dep_id in m.dependencies:
                if (dep_id, m.milestone_id) not in derived_edges:
                    derived_edges.append((dep_id, m.milestone_id))

        topo_order = self._topological_sort(milestone_dict, derived_edges)

        plan = MissionPlan(
            plan_id=plan_id,
            mission_id=mission_id,
            milestones=milestone_dict,
            dag_edges=derived_edges,
            topological_order=topo_order,
            created_at=time.time(),
        )
        self.plan = plan
        return plan

    def get_ready_milestones(self, completed_ids: Set[str]) -> List[Milestone]:
        """
        Returns all milestones whose dependencies are completely satisfied
        and are currently in PLANNED or READY state.
        """
        if not self.plan:
            return []

        ready: List[Milestone] = []
        for m_id in self.plan.topological_order:
            m = self.plan.milestones.get(m_id)
            if not m or m.status in (MilestoneState.COMPLETED, MilestoneState.RUNNING, MilestoneState.FAILED):
                continue
            # Check if all dependencies are satisfied
            deps_satisfied = all(dep in completed_ids for dep in m.dependencies)
            if deps_satisfied:
                m.status = MilestoneState.READY
                ready.append(m)

        return ready

    def generate_scalable_dag(
        self,
        mission_id: str,
        node_count: int = 100,
        fanout: int = 4,
        objective_ids: Optional[List[str]] = None,
    ) -> MissionPlan:
        """
        Generates a synthetic or scalable layered DAG for performance benchmarking and testing.
        Capable of scaling to 10, 100, 1,000, or 10,000 nodes in sub-second time.
        """
        milestones: List[Milestone] = []
        edges: List[Tuple[str, str]] = []
        target_obj_ids = list(objective_ids) if objective_ids else [f"OBJ_{mission_id}_01"]

        # Layered structure
        layer_size = max(1, fanout)
        num_layers = max(1, (node_count + layer_size - 1) // layer_size)

        idx = 0
        layers: List[List[str]] = []
        for l in range(num_layers):
            current_layer: List[str] = []
            for _ in range(layer_size):
                if idx >= node_count:
                    break
                m_id = f"M_{idx+1:05d}"
                deps: List[str] = []
                if l > 0:
                    # Depend on nodes from previous layer
                    prev_layer = layers[l - 1]
                    dep_node = prev_layer[len(current_layer) % len(prev_layer)]
                    deps.append(dep_node)
                    edges.append((dep_node, m_id))

                milestones.append(
                    Milestone(
                        milestone_id=m_id,
                        title=f"Milestone Step {idx+1}",
                        objective_ids=target_obj_ids,
                        dependencies=deps,
                        expected_outputs=[f"output_{m_id}.json"],
                        verification_requirements=["UNIT_TEST", "CONTRACT_CHECK"],
                        checkpoint_policy="ALWAYS" if (idx % 25 == 0) else "ON_COMPLETION",
                    )
                )
                current_layer.append(m_id)
                idx += 1
            layers.append(current_layer)

        return self.create_plan(mission_id, milestones, edges)

    @staticmethod
    def _topological_sort(
        milestones: Dict[str, Milestone],
        edges: List[Tuple[str, str]],
    ) -> List[str]:
        """Kahn's algorithm for topological sorting."""
        in_degree: Dict[str, int] = {m_id: 0 for m_id in milestones}
        adj: Dict[str, List[str]] = {m_id: [] for m_id in milestones}

        for u, v in edges:
            if u in adj and v in in_degree:
                adj[u].append(v)
                in_degree[v] += 1

        queue = deque([node for node, deg in in_degree.items() if deg == 0])
        topo_order: List[str] = []

        while queue:
            curr = queue.popleft()
            topo_order.append(curr)
            for nxt in adj.get(curr, []):
                in_degree[nxt] -= 1
                if in_degree[nxt] == 0:
                    queue.append(nxt)

        if len(topo_order) != len(milestones):
            missing = set(milestones.keys()) - set(topo_order)
            raise CyclicDependencyError(
                f"Cyclic dependency detected in milestone DAG! Unresolved nodes: {missing}"
            )

        return topo_order
