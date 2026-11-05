"""
JARVIS OS — Phase 78: Autonomous Causal Diagnosis & Root-Cause Analysis
Module: graph.py
Causal DAG builder, topological sort, cycle detection, path tracing, and root-cause isolation.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Set, Tuple

from .models import (
    CausalEdge,
    CausalEdgeType,
    CausalNode,
    CausalNodeType,
    CyclicCausalGraphError,
)


class CausalGraphBuilder:
    """
    Constructs and analyzes Directed Acyclic Graphs (DAGs) representing causal mechanisms,
    separating root causes, contributing factors, intermediate states, and symptoms.
    """

    def __init__(self):
        self.nodes: Dict[str, CausalNode] = {}
        self.edges: List[CausalEdge] = []
        # Adjacency list: source_id -> list of (target_id, edge)
        self._adj: Dict[str, List[CausalEdge]] = {}
        # In-degree map: node_id -> in_degree count
        self._in_degree: Dict[str, int] = {}

    def add_node(
        self,
        node_id: str,
        node_type: CausalNodeType,
        description: str,
        subsystem: str,
        timestamp: Optional[float] = None,
        evidence_refs: Optional[List[str]] = None,
        metadata: Optional[Dict] = None,
    ) -> CausalNode:
        """Add a causal node to the graph."""
        node = CausalNode(
            node_id=node_id,
            node_type=node_type,
            description=description,
            subsystem=subsystem,
            timestamp=timestamp or 0.0,
            evidence_refs=evidence_refs or [],
            metadata=metadata or {},
        )
        self.nodes[node_id] = node
        if node_id not in self._adj:
            self._adj[node_id] = []
        if node_id not in self._in_degree:
            self._in_degree[node_id] = 0
        return node

    def add_edge(
        self,
        source_id: str,
        target_id: str,
        edge_type: CausalEdgeType = CausalEdgeType.DIRECTLY_CAUSES,
        confidence: float = 1.0,
        evidence_refs: Optional[List[str]] = None,
        mechanism: str = "",
    ) -> CausalEdge:
        """Add a directed causal edge from source to target, validating against cycles."""
        if source_id not in self.nodes:
            raise KeyError(f"Source node '{source_id}' does not exist in causal graph.")
        if target_id not in self.nodes:
            raise KeyError(f"Target node '{target_id}' does not exist in causal graph.")

        edge = CausalEdge(
            source_id=source_id,
            target_id=target_id,
            edge_type=edge_type,
            confidence=confidence,
            evidence_refs=evidence_refs or [],
            mechanism=mechanism,
        )

        # Temporary check for cycles
        self._adj[source_id].append(edge)
        self._in_degree[target_id] = self._in_degree.get(target_id, 0) + 1

        if self._has_cycle():
            # Revert edge and raise CyclicCausalGraphError
            self._adj[source_id].pop()
            self._in_degree[target_id] -= 1
            raise CyclicCausalGraphError(
                f"Adding causal edge '{source_id}' -> '{target_id}' creates an invalid causal loop."
            )

        self.edges.append(edge)
        return edge

    def _has_cycle(self) -> bool:
        """DFS cycle detection."""
        visited: Set[str] = set()
        rec_stack: Set[str] = set()

        def dfs(node_id: str) -> bool:
            visited.add(node_id)
            rec_stack.add(node_id)
            for edge in self._adj.get(node_id, []):
                neighbor = edge.target_id
                if neighbor not in visited:
                    if dfs(neighbor):
                        return True
                elif neighbor in rec_stack:
                    return True
            rec_stack.remove(node_id)
            return False

        for node_id in self.nodes:
            if node_id not in visited:
                if dfs(node_id):
                    return True
        return False

    def topological_sort(self) -> List[str]:
        """Returns nodes sorted in topological causal order (causes strictly precede effects)."""
        in_deg = dict(self._in_degree)
        queue = [n for n, deg in in_deg.items() if deg == 0]
        order = []

        while queue:
            curr = queue.pop(0)
            order.append(curr)
            for edge in self._adj.get(curr, []):
                target = edge.target_id
                in_deg[target] -= 1
                if in_deg[target] == 0:
                    queue.append(target)

        if len(order) != len(self.nodes):
            raise CyclicCausalGraphError("Graph has cycle, cannot topologically sort.")
        return order

    def find_paths_to_symptom(self, symptom_node_id: str) -> List[List[str]]:
        """Finds all directed paths from source nodes leading to a given symptom node."""
        all_paths: List[List[str]] = []

        def dfs(current: str, current_path: List[str]):
            if current == symptom_node_id:
                all_paths.append(list(current_path))
                return
            for edge in self._adj.get(current, []):
                dfs(edge.target_id, current_path + [edge.target_id])

        for node_id, deg in self._in_degree.items():
            if deg == 0:  # Potential root cause / origin
                dfs(node_id, [node_id])

        return all_paths

    def get_edge(self, source_id: str, target_id: str) -> Optional[CausalEdge]:
        """Retrieve the directed edge from source_id to target_id if it exists."""
        for edge in self._adj.get(source_id, []):
            if edge.target_id == target_id:
                return edge
        return None

    def identify_candidate_root_causes(self, symptom_node_id: str) -> List[str]:
        """
        Identifies all origin nodes (in-degree 0 or marked ROOT_CAUSE)
        that have at least one reachable path to the target symptom.
        """
        paths = self.find_paths_to_symptom(symptom_node_id)
        candidates = {path[0] for path in paths if len(path) > 1}
        return sorted(list(candidates))
