"""
JARVIS OS — Phase 75: Autonomous Engineering Strategy & Portfolio Orchestration
Module: dependency_graph.py
Inter-initiative dependency DAG, Tarjan cycle detection, conflict analysis, and concurrency safety.
"""

from __future__ import annotations

from collections import defaultdict, deque
from typing import Dict, List, Optional, Set, Tuple

from .models import (
    ConflictDiagnostic,
    ConflictType,
    DependencyCycleError,
    DependencyRelation,
    DependencyType,
    EngineeringInitiative,
)


class DependencyGraphEngine:
    """
    Constructs, validates, and analyzes the inter-initiative dependency and conflict graph.
    """

    def __init__(self):
        self._nodes: Dict[str, EngineeringInitiative] = {}
        # Adjacency: source -> set of targets
        self._prerequisites: Dict[str, Set[str]] = defaultdict(set)       # target -> sources that must complete before target
        self._dependents: Dict[str, Set[str]] = defaultdict(set)          # source -> targets that depend on source
        self._soft_preferences: Dict[str, Set[str]] = defaultdict(set)    # target -> preferred earlier sources
        self._mutual_exclusions: Dict[str, Set[str]] = defaultdict(set)   # id -> set of excluded ids
        self._evidence_invalidations: Dict[str, Set[str]] = defaultdict(set)  # modifier -> set of invalidated target ids

    def add_initiative(self, initiative: EngineeringInitiative) -> None:
        """Register an initiative node in the graph."""
        self._nodes[initiative.id] = initiative
        for prereq in initiative.prerequisites:
            self.add_dependency(prereq, initiative.id, DependencyType.HARD_PREREQUISITE)
        for excl in initiative.mutual_exclusions:
            self.add_mutual_exclusion(initiative.id, excl)
        for soft in initiative.soft_preferences:
            self.add_dependency(soft, initiative.id, DependencyType.SOFT_PREFERENCE)

    def add_dependency(
        self,
        source_id: str,
        target_id: str,
        dep_type: DependencyType = DependencyType.HARD_PREREQUISITE,
        reason: str = "",
    ) -> None:
        """Add a directed relationship from source to target."""
        if dep_type == DependencyType.HARD_PREREQUISITE:
            self._prerequisites[target_id].add(source_id)
            self._dependents[source_id].add(target_id)
        elif dep_type == DependencyType.SOFT_PREFERENCE:
            self._soft_preferences[target_id].add(source_id)
        elif dep_type == DependencyType.MUTUAL_EXCLUSION:
            self.add_mutual_exclusion(source_id, target_id)
        elif dep_type == DependencyType.EVIDENCE_INVALIDATION:
            self._evidence_invalidations[source_id].add(target_id)

    def add_mutual_exclusion(self, id_a: str, id_b: str, reason: str = "") -> None:
        """Register mutual exclusion between two initiatives."""
        self._mutual_exclusions[id_a].add(id_b)
        self._mutual_exclusions[id_b].add(id_a)

    def detect_cycles(self, subset_ids: Optional[Set[str]] = None) -> None:
        """
        Tarjan's algorithm / DFS for detecting cycles among hard prerequisites.
        Raises DependencyCycleError with explicit cycle path if a cycle exists.
        Never silently discards dependencies.
        """
        active_ids = subset_ids if subset_ids is not None else set(self._nodes.keys())
        
        # Build subgraph restricted to active_ids
        adj: Dict[str, List[str]] = defaultdict(list)
        for target in active_ids:
            for source in self._prerequisites.get(target, set()):
                if source in active_ids:
                    # source -> target in execution order
                    adj[source].append(target)

        visited: Dict[str, int] = {}  # 0: unvisited, 1: visiting, 2: visited
        parent_map: Dict[str, str] = {}

        def dfs(node: str, path: List[str]) -> Optional[List[str]]:
            visited[node] = 1
            for nxt in adj.get(node, []):
                if visited.get(nxt, 0) == 1:
                    # Cycle detected: extract subpath from nxt to node, plus nxt
                    idx = path.index(nxt) if nxt in path else 0
                    cycle = path[idx:] + [nxt]
                    return cycle
                elif visited.get(nxt, 0) == 0:
                    res = dfs(nxt, path + [nxt])
                    if res:
                        return res
            visited[node] = 2
            return None

        for n in active_ids:
            if visited.get(n, 0) == 0:
                cycle_found = dfs(n, [n])
                if cycle_found:
                    raise DependencyCycleError(cycle_found)

    def detect_conflicts(self, candidate_ids: Set[str]) -> List[ConflictDiagnostic]:
        """
        Examine candidate set for mutual exclusions, overlapping component modifications,
        and evidence invalidations.
        """
        diagnostics: List[ConflictDiagnostic] = []
        candidate_list = sorted(list(candidate_ids))

        # 1. Mutual exclusions
        for i in range(len(candidate_list)):
            for j in range(i + 1, len(candidate_list)):
                id_a, id_b = candidate_list[i], candidate_list[j]
                if id_b in self._mutual_exclusions.get(id_a, set()):
                    diagnostics.append(
                        ConflictDiagnostic(
                            conflict_type=ConflictType.MUTUAL_EXCLUSION,
                            initiative_ids=[id_a, id_b],
                            description=f"Initiatives '{id_a}' and '{id_b}' are mutually exclusive.",
                            resolvable=False,
                        )
                    )

        # 2. Overlapping component blast radii
        for i in range(len(candidate_list)):
            for j in range(i + 1, len(candidate_list)):
                id_a, id_b = candidate_list[i], candidate_list[j]
                node_a = self._nodes.get(id_a)
                node_b = self._nodes.get(id_b)
                if not node_a or not node_b:
                    continue
                overlap = set(node_a.affected_components).intersection(set(node_b.affected_components))
                if overlap:
                    diagnostics.append(
                        ConflictDiagnostic(
                            conflict_type=ConflictType.OVERLAPPING_COMPONENTS,
                            initiative_ids=[id_a, id_b],
                            description=f"Initiatives '{id_a}' and '{id_b}' modify overlapping components: {sorted(list(overlap))}",
                            resolvable=True,  # Resolvable by serializing execution order
                        )
                    )

        # 3. Evidence Invalidation: Does A modify files that B uses for evidence baseline?
        for id_a in candidate_list:
            node_a = self._nodes.get(id_a)
            if not node_a:
                continue
            for id_b in candidate_list:
                if id_a == id_b:
                    continue
                node_b = self._nodes.get(id_b)
                if not node_b or not node_b.evidence:
                    continue
                # If A's affected files intersect B's affected files or B relies on A
                if set(node_a.affected_components).intersection(set(node_b.affected_components)):
                    if id_a not in self._prerequisites.get(id_b, set()):
                        diagnostics.append(
                            ConflictDiagnostic(
                                conflict_type=ConflictType.EVIDENCE_STALENESS,
                                initiative_ids=[id_a, id_b],
                                description=f"Executing '{id_a}' will invalidate empirical baseline evidence for '{id_b}'.",
                                resolvable=True,
                            )
                        )

        return diagnostics

    def are_concurrent_safe(self, init_id_a: str, init_id_b: str) -> bool:
        """
        Check if two initiatives can safely run in parallel.
        They must:
        - Have no hard prerequisite relationship between them.
        - Not be mutually exclusive.
        - Have completely disjoint affected components.
        """
        if init_id_a == init_id_b:
            return False
        # Prerequisites check
        if init_id_a in self._prerequisites.get(init_id_b, set()):
            return False
        if init_id_b in self._prerequisites.get(init_id_a, set()):
            return False
        # Mutual exclusion
        if init_id_b in self._mutual_exclusions.get(init_id_a, set()):
            return False
        # Overlapping components
        node_a = self._nodes.get(init_id_a)
        node_b = self._nodes.get(init_id_b)
        if node_a and node_b:
            overlap = set(node_a.affected_components).intersection(set(node_b.affected_components))
            if overlap:
                return False
        return True

    def get_topological_order(self, subset_ids: Optional[Set[str]] = None) -> List[str]:
        """
        Produce a deterministic topological ordering of initiatives respecting hard prerequisites.
        Raises DependencyCycleError if cycles exist.
        """
        self.detect_cycles(subset_ids)
        active_ids = subset_ids if subset_ids is not None else set(self._nodes.keys())
        
        in_degree: Dict[str, int] = {i: 0 for i in active_ids}
        adj: Dict[str, List[str]] = defaultdict(list)

        for target in active_ids:
            for source in self._prerequisites.get(target, set()):
                if source in active_ids:
                    adj[source].append(target)
                    in_degree[target] += 1

        # Use deterministic alphabetical priority queue / sorted list
        queue = sorted([n for n, deg in in_degree.items() if deg == 0])
        order: List[str] = []

        while queue:
            curr = queue.pop(0)
            order.append(curr)
            for nxt in sorted(adj.get(curr, [])):
                in_degree[nxt] -= 1
                if in_degree[nxt] == 0:
                    queue.append(nxt)
            queue.sort()

        return order

    def compute_prerequisite_transitive_closure(self, initiative_id: str) -> Set[str]:
        """Return all transitive hard prerequisites required before initiative_id can run."""
        closure = set()
        stack = list(self._prerequisites.get(initiative_id, set()))
        while stack:
            curr = stack.pop()
            if curr not in closure:
                closure.add(curr)
                stack.extend(self._prerequisites.get(curr, set()))
        return closure
