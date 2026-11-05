"""
JARVIS OS — Phase 73: Autonomous Macro-Refactoring Engine
Module: graph.py
Migration DAG representation, topological sort, dependency validation, cycle detection,
and transitive dependency traversal.
"""

from __future__ import annotations

from typing import Dict, List, Set

from .models import (
    DependencyCycleError,
    MigrationStep,
    StepState,
    UnresolvedDependencyError,
)


class MigrationGraph:
    """
    Manages the Directed Acyclic Graph (DAG) of migration steps.
    Enforces valid dependencies, absence of cycles, and deterministic topological execution order.
    """

    def __init__(self, steps: Dict[str, MigrationStep]):
        self.steps: Dict[str, MigrationStep] = dict(steps)
        self._adj: Dict[str, List[str]] = {s_id: [] for s_id in self.steps}
        self._rev_adj: Dict[str, List[str]] = {s_id: [] for s_id in self.steps}
        self._build_edges()

    def _build_edges(self) -> None:
        for step_id, step in self.steps.items():
            for dep in step.dependencies:
                if dep not in self.steps:
                    raise UnresolvedDependencyError(
                        f"Step '{step_id}' depends on undiscovered or unresolved step '{dep}'."
                    )
                self._adj[dep].append(step_id)
                self._rev_adj[step_id].append(dep)

    def validate(self) -> None:
        """
        Validates the DAG:
        1. Checks that all dependencies exist.
        2. Detects any directed cycle using depth-first search.
        """
        visited: Dict[str, int] = {s_id: 0 for s_id in self.steps}  # 0=unvisited, 1=visiting, 2=visited

        def dfs(node: str, path: List[str]) -> None:
            visited[node] = 1
            path.append(node)
            for neighbor in self._adj.get(node, []):
                if visited[neighbor] == 1:
                    cycle = path[path.index(neighbor):] + [neighbor]
                    raise DependencyCycleError(
                        f"Dependency cycle detected in migration graph: {' -> '.join(cycle)}"
                    )
                if visited[neighbor] == 0:
                    dfs(neighbor, path)
            path.pop()
            visited[node] = 2

        for step_id in sorted(self.steps.keys()):
            if visited[step_id] == 0:
                dfs(step_id, [])

    def topological_sort(self) -> List[str]:
        """
        Produces a deterministic, topological execution order of step IDs.
        """
        self.validate()
        in_degree: Dict[str, int] = {s_id: len(self._rev_adj[s_id]) for s_id in self.steps}
        queue: List[str] = sorted([s_id for s_id, deg in in_degree.items() if deg == 0])
        order: List[str] = []

        while queue:
            node = queue.pop(0)
            order.append(node)
            for next_node in sorted(self._adj.get(node, [])):
                in_degree[next_node] -= 1
                if in_degree[next_node] == 0:
                    queue.append(next_node)
                    queue.sort()

        if len(order) != len(self.steps):
            raise DependencyCycleError("Cycle detected during topological sorting.")

        return order

    def get_downstream_dependents(self, step_id: str) -> Set[str]:
        """
        Computes the transitive set of all downstream steps that depend on `step_id`.
        """
        if step_id not in self.steps:
            return set()

        dependents: Set[str] = set()
        queue: List[str] = list(self._adj.get(step_id, []))

        while queue:
            curr = queue.pop(0)
            if curr not in dependents:
                dependents.add(curr)
                queue.extend(self._adj.get(curr, []))

        return dependents

    def get_upstream_dependencies(self, step_id: str) -> Set[str]:
        """
        Computes the transitive set of all predecessor steps that `step_id` depends on.
        """
        if step_id not in self.steps:
            return set()

        dependencies: Set[str] = set()
        queue: List[str] = list(self._rev_adj.get(step_id, []))

        while queue:
            curr = queue.pop(0)
            if curr not in dependencies:
                dependencies.add(curr)
                queue.extend(self._rev_adj.get(curr, []))

        return dependencies

    def is_step_ready_to_execute(self, step_id: str) -> bool:
        """
        Predecessor Acceptance Invariant:
        A step can only be executed if ALL its direct dependencies are in ACCEPTED state.
        """
        step = self.steps.get(step_id)
        if not step:
            return False

        if step.state != StepState.PENDING and step.state != StepState.READY:
            return False

        for dep_id in step.dependencies:
            dep_step = self.steps.get(dep_id)
            if not dep_step or dep_step.state != StepState.ACCEPTED:
                return False

        return True
