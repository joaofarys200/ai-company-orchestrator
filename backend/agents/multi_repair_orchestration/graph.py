"""
JARVIS OS — Phase 55: Transactional Multi-Repair Orchestration & Convergence
Repair Graph Engine.
Constructs a deterministic multi-entity DAG connecting Repairs, Failures, Root Causes,
Files, Symbols, Contracts, and Tasks with precise relational edges.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Set

from agents.multi_repair_orchestration.models import (
    NodeRelationType,
    RepairEdge,
    RepairGraph,
    RepairNode,
    compute_deterministic_hash,
)


class RepairGraphBuilder:
    """
    Builds and validates a deterministic RepairGraph representation.
    """

    def __init__(self):
        self._nodes: Dict[str, RepairNode] = {}
        self._edges: List[RepairEdge] = []

    def add_node(self, node_id: str, node_type: str, label: str, metadata: Optional[Dict[str, Any]] = None) -> RepairNode:
        if node_id in self._nodes:
            # Update existing metadata
            if metadata:
                self._nodes[node_id].metadata.update(metadata)
            return self._nodes[node_id]

        node = RepairNode(node_id=node_id, node_type=node_type, label=label, metadata=metadata or {})
        self._nodes[node_id] = node
        return node

    def add_edge(
        self,
        source_id: str,
        target_id: str,
        relation: NodeRelationType,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> RepairEdge:
        # Check if identical edge already exists
        for e in self._edges:
            if e.source_id == source_id and e.target_id == target_id and e.relation == relation:
                if metadata:
                    e.metadata.update(metadata)
                return e

        edge = RepairEdge(source_id=source_id, target_id=target_id, relation=relation, metadata=metadata or {})
        self._edges.append(edge)
        return edge

    def build_graph(self) -> RepairGraph:
        # Sort edges deterministically
        self._edges.sort(key=lambda e: (e.source_id, e.target_id, e.relation.value))
        graph = RepairGraph(nodes=dict(self._nodes), edges=list(self._edges))
        graph.recompute_hash()
        return graph

    def has_cycle(self, graph: RepairGraph, dependency_only: bool = True) -> bool:
        """Checks for cycles in the DAG."""
        adj: Dict[str, List[str]] = {}
        for node_id in graph.nodes:
            adj[node_id] = []

        for edge in graph.edges:
            if dependency_only and edge.relation != NodeRelationType.DEPENDS_ON:
                continue
            adj.setdefault(edge.source_id, []).append(edge.target_id)

        visited: Dict[str, int] = {n: 0 for n in graph.nodes}  # 0=unvisited, 1=visiting, 2=visited

        def dfs(u: str) -> bool:
            visited[u] = 1
            for v in adj.get(u, []):
                if visited.get(v, 0) == 1:
                    return True
                if visited.get(v, 0) == 0 and dfs(v):
                    return True
            visited[u] = 2
            return False

        for n in graph.nodes:
            if visited[n] == 0:
                if dfs(n):
                    return True
        return False
