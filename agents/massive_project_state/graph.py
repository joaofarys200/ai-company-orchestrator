from __future__ import annotations

from typing import Any, Dict, List, Optional, Set

from .models import GraphEdge, GraphPartitionLevel


class PartitionedGraphManager:
    """Manages hierarchical graph partitions across services and modules."""

    def __init__(self) -> None:
        self._edges: List[GraphEdge] = []
        self._outgoing: Dict[str, List[GraphEdge]] = {}
        self._incoming: Dict[str, List[GraphEdge]] = {}
        self.revision = 1

    def add_edge(
        self,
        source: str,
        target: str,
        edge_type: str,
        weight: float = 1.0,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> GraphEdge:
        edge = GraphEdge(
            source=source,
            target=target,
            edge_type=edge_type,
            weight=weight,
            metadata=metadata or {},
        )
        self._edges.append(edge)
        self._outgoing.setdefault(source, []).append(edge)
        self._incoming.setdefault(target, []).append(edge)
        self.revision += 1
        return edge

    def get_outgoing(self, source: str) -> List[GraphEdge]:
        return self._outgoing.get(source, [])

    def get_incoming(self, target: str) -> List[GraphEdge]:
        return self._incoming.get(target, [])

    def get_edges_between(self, source: str, target: str) -> List[GraphEdge]:
        return [e for e in self.get_outgoing(source) if e.target == target]

    def remove_edges_for_node(self, node_id: str) -> None:
        # Remove outgoing
        out = self._outgoing.pop(node_id, [])
        # Remove incoming
        inc = self._incoming.pop(node_id, [])

        removed = set(out + inc)
        self._edges = [e for e in self._edges if e not in removed]

        for target, edges in self._incoming.items():
            self._incoming[target] = [e for e in edges if e.source != node_id]
        for source, edges in self._outgoing.items():
            self._outgoing[source] = [e for e in edges if e.target != node_id]

        self.revision += 1

    def clear(self) -> None:
        self._edges.clear()
        self._outgoing.clear()
        self._incoming.clear()
        self.revision += 1

    def edge_count(self) -> int:
        return len(self._edges)
