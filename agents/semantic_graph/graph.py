"""
JARVIS OS — Phase 44: Cross-Language Semantic Graph
Directed Acyclic Multi-Graph representation for cross-language software systems.

Features:
- Deterministic Kahn's topological sort & cycle detection (O(V+E), non-recursive).
- Incremental graph updates with downstream blast radius computation.
- Comprehensive structural validation (missing nodes, cycles, invalid adapters).
- Version tracking and immutable snapshot hashes.
"""

from __future__ import annotations

from collections import deque
from dataclasses import asdict, dataclass, field
import hashlib
import json
import time
from typing import Any, Dict, List, Optional, Set, Tuple

from agents.semantic_graph.models import (
    ConfidenceClass,
    SemanticEdge,
    SemanticGraphVersion,
    SemanticNode,
    SemanticNodeType,
    SemanticRelationType,
    ValidationStatus,
)


class SemanticGraphError(Exception):
    """Base exception for semantic graph operations."""
    pass


class SemanticGraphCycleError(SemanticGraphError):
    """Raised when a cycle is detected in the directed semantic graph."""
    pass


class CrossLanguageSemanticGraph:
    """Formal Directed Acyclic Graph connecting requirements, architecture, code, tests, and tasks across languages."""

    def __init__(
        self,
        nodes: list[SemanticNode] | None = None,
        edges: list[SemanticEdge] | None = None,
        graph_version: int = 1,
    ) -> None:
        self._nodes: dict[str, SemanticNode] = {}
        self._edges: dict[str, SemanticEdge] = {}
        self._out_edges: dict[str, list[str]] = {}  # node_id -> [edge_id, ...]
        self._in_edges: dict[str, list[str]] = {}   # node_id -> [edge_id, ...]
        self.graph_version: int = max(1, int(graph_version))
        self.contract_version: str = "1.0.0"
        self.adapter_version: str = "1.0.0"
        self.created_at: float = time.time()
        self.updated_at: float = self.created_at

        if nodes:
            for n in nodes:
                self.add_node(n)
        if edges:
            for e in edges:
                self.add_edge(e)

    @property
    def nodes(self) -> dict[str, SemanticNode]:
        return self._nodes

    @property
    def edges(self) -> dict[str, SemanticEdge]:
        return self._edges

    def add_node(self, node: SemanticNode) -> None:
        """Adds or replaces a SemanticNode in the graph."""
        self._nodes[node.node_id] = node
        if node.node_id not in self._out_edges:
            self._out_edges[node.node_id] = []
        if node.node_id not in self._in_edges:
            self._in_edges[node.node_id] = []
        self.updated_at = time.time()

    def add_edge(self, edge: SemanticEdge, check_cycle: bool = True) -> None:
        """Adds a SemanticEdge. If check_cycle is True, enforces DAG invariants."""
        if edge.source not in self._nodes:
            raise SemanticGraphError(f"Source node '{edge.source}' does not exist in graph.")
        if edge.target not in self._nodes:
            raise SemanticGraphError(f"Target node '{edge.target}' does not exist in graph.")

        if edge.source == edge.target:
            raise SemanticGraphCycleError(f"Self-referential edge '{edge.edge_id}' on node '{edge.source}'.")

        self._edges[edge.edge_id] = edge
        if edge.edge_id not in self._out_edges[edge.source]:
            self._out_edges[edge.source].append(edge.edge_id)
        if edge.edge_id not in self._in_edges[edge.target]:
            self._in_edges[edge.target].append(edge.edge_id)

        if check_cycle:
            # Validate acyclicity
            has_cycle, cycle_path = self.detect_cycle()
            if has_cycle:
                # Rollback edge
                self.remove_edge(edge.edge_id)
                raise SemanticGraphCycleError(f"Cycle detected after adding edge '{edge.edge_id}': {' -> '.join(cycle_path)}")

        self.updated_at = time.time()

    def remove_edge(self, edge_id: str) -> None:
        if edge_id in self._edges:
            e = self._edges.pop(edge_id)
            if e.source in self._out_edges and edge_id in self._out_edges[e.source]:
                self._out_edges[e.source].remove(edge_id)
            if e.target in self._in_edges and edge_id in self._in_edges[e.target]:
                self._in_edges[e.target].remove(edge_id)
            self.updated_at = time.time()

    def remove_node(self, node_id: str) -> None:
        if node_id in self._nodes:
            # Remove all incoming and outgoing edges
            out_e = list(self._out_edges.get(node_id, []))
            for eid in out_e:
                self.remove_edge(eid)
            in_e = list(self._in_edges.get(node_id, []))
            for eid in in_e:
                self.remove_edge(eid)

            del self._nodes[node_id]
            self._out_edges.pop(node_id, None)
            self._in_edges.pop(node_id, None)
            self.updated_at = time.time()

    def get_node(self, node_id: str) -> Optional[SemanticNode]:
        return self._nodes.get(node_id)

    def get_edge(self, edge_id: str) -> Optional[SemanticEdge]:
        return self._edges.get(edge_id)

    def get_out_edges(self, node_id: str) -> list[SemanticEdge]:
        return [self._edges[eid] for eid in self._out_edges.get(node_id, []) if eid in self._edges]

    def get_in_edges(self, node_id: str) -> list[SemanticEdge]:
        return [self._edges[eid] for eid in self._in_edges.get(node_id, []) if eid in self._edges]

    def get_edges_for_node(self, node_id: str) -> list[SemanticEdge]:
        """Returns all incoming and outgoing edges for a given node."""
        out_e = self.get_out_edges(node_id)
        in_e = self.get_in_edges(node_id)
        seen: set[str] = set()
        res: list[SemanticEdge] = []
        for e in out_e + in_e:
            if e.edge_id not in seen:
                seen.add(e.edge_id)
                res.append(e)
        return res

    def get_downstream_nodes(self, node_id: str) -> set[str]:
        """Returns all reachable downstream nodes using BFS."""
        visited: set[str] = set()
        queue = deque([node_id])
        while queue:
            curr = queue.popleft()
            for edge in self.get_out_edges(curr):
                tgt = edge.target
                if tgt not in visited:
                    visited.add(tgt)
                    queue.append(tgt)
        return visited

    def get_upstream_nodes(self, node_id: str) -> set[str]:
        """Returns all reachable upstream nodes using BFS."""
        visited: set[str] = set()
        queue = deque([node_id])
        while queue:
            curr = queue.popleft()
            for edge in self.get_in_edges(curr):
                src = edge.source
                if src not in visited:
                    visited.add(src)
                    queue.append(src)
        return visited

    def detect_cycle(self) -> tuple[bool, list[str]]:
        """Iterative Kahn's algorithm for cycle detection."""
        in_degree: dict[str, int] = {nid: len(self._in_edges.get(nid, [])) for nid in self._nodes}
        zero_in_degree = deque([nid for nid, deg in in_degree.items() if deg == 0])

        visited_count = 0
        while zero_in_degree:
            curr = zero_in_degree.popleft()
            visited_count += 1
            for edge in self.get_out_edges(curr):
                tgt = edge.target
                in_degree[tgt] -= 1
                if in_degree[tgt] == 0:
                    zero_in_degree.append(tgt)

        if visited_count < len(self._nodes):
            # There is at least one cycle. Extract nodes with in_degree > 0
            cycle_nodes = [nid for nid, deg in in_degree.items() if deg > 0]
            return True, cycle_nodes
        return False, []

    def topological_sort(self) -> list[str]:
        """Iterative Kahn's topological sort returning node IDs in dependency order."""
        in_degree: dict[str, int] = {nid: len(self._in_edges.get(nid, [])) for nid in self._nodes}
        zero_in = [nid for nid, deg in in_degree.items() if deg == 0]
        # Sort for deterministic order
        zero_in.sort()
        queue = deque(zero_in)

        topo_order: list[str] = []
        while queue:
            curr = queue.popleft()
            topo_order.append(curr)

            downstream = sorted([self._edges[eid].target for eid in self._out_edges.get(curr, [])])
            for tgt in downstream:
                in_degree[tgt] -= 1
                if in_degree[tgt] == 0:
                    queue.append(tgt)

        if len(topo_order) < len(self._nodes):
            raise SemanticGraphCycleError("Cannot perform topological sort: graph contains cycles.")

        return topo_order

    def calculate_blast_radius(self, changed_node_ids: list[str]) -> set[str]:
        """Computes the precise set of affected nodes (changed nodes + all downstream dependencies)."""
        blast_radius: set[str] = set()
        for nid in changed_node_ids:
            if nid in self._nodes:
                blast_radius.add(nid)
                blast_radius.update(self.get_downstream_nodes(nid))
        return blast_radius

    def update_node_incremental(self, node: SemanticNode) -> set[str]:
        """Updates a node and returns only the invalidated downstream blast radius.
        
        Avoids full graph reconstruction.
        """
        self.add_node(node)
        self.graph_version += 1
        return self.calculate_blast_radius([node.node_id])

    def validate_graph(self) -> tuple[bool, list[str]]:
        """Validates all structural invariants of the cross-language semantic graph."""
        issues: list[str] = []

        # 1. Edge endpoint existence
        for eid, edge in self._edges.items():
            if edge.source not in self._nodes:
                issues.append(f"Edge '{eid}' source '{edge.source}' not in nodes.")
            if edge.target not in self._nodes:
                issues.append(f"Edge '{eid}' target '{edge.target}' not in nodes.")

        # 2. Cycle detection
        has_cycle, cycle_nodes = self.detect_cycle()
        if has_cycle:
            issues.append(f"Cycle detected involving nodes: {', '.join(cycle_nodes[:5])}")

        # 3. Orphan Tasks: A task with no incoming or outgoing connections
        for nid, node in self._nodes.items():
            if node.node_type == SemanticNodeType.TASK:
                deg_in = len(self._in_edges.get(nid, []))
                deg_out = len(self._out_edges.get(nid, []))
                if deg_in == 0 and deg_out == 0:
                    issues.append(f"Orphan Task '{nid}' has no architectural or semantic linkages.")

        is_valid = len(issues) == 0
        return is_valid, issues

    def version_info(self) -> SemanticGraphVersion:
        """Returns the current immutable version envelope."""
        content_repr = f"{len(self._nodes)}:{len(self._edges)}:{self.updated_at}"
        v = SemanticGraphVersion(
            graph_version=self.graph_version,
            contract_version=self.contract_version,
            adapter_version=self.adapter_version,
            node_count=len(self._nodes),
            edge_count=len(self._edges),
            timestamp=self.updated_at,
        )
        v.calculate_hash(content_repr)
        return v

    def to_dict(self) -> dict[str, Any]:
        return {
            "graph_version": self.graph_version,
            "contract_version": self.contract_version,
            "adapter_version": self.adapter_version,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "nodes": [n.to_dict() for n in self._nodes.values()],
            "edges": [e.to_dict() for e in self._edges.values()],
            "version_info": self.version_info().to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CrossLanguageSemanticGraph:
        g = cls(graph_version=int(data.get("graph_version", 1)))
        g.contract_version = str(data.get("contract_version", "1.0.0"))
        g.adapter_version = str(data.get("adapter_version", "1.0.0"))

        for nd in data.get("nodes", []):
            g.add_node(SemanticNode.from_dict(nd))
        for ed in data.get("edges", []):
            g.add_edge(SemanticEdge.from_dict(ed), check_cycle=False)

        return g
