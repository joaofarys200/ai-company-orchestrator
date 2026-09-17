from __future__ import annotations

from typing import Dict, List, Optional, Set

from .models import CondensationDAG, CondensationDAGNode


class CondensationDAGManager:
    """Provides navigation, topological traversal, and reachability across the condensation DAG."""

    def __init__(self, dag: CondensationDAG) -> None:
        self.dag = dag

    def get_downstream_sccs(self, root_scc_id: str, max_depth: int = 10) -> List[str]:
        """Calculates downstream reachability in the DAG up to max_depth."""
        if root_scc_id not in self.dag.nodes:
            return []

        visited: Set[str] = set()
        queue = [(root_scc_id, 0)]

        while queue:
            curr_scc, depth = queue.pop(0)
            if depth >= max_depth:
                continue

            node = self.dag.nodes.get(curr_scc)
            if not node:
                continue

            for downstream in node.downstream_scc_ids:
                if downstream not in visited:
                    visited.add(downstream)
                    queue.append((downstream, depth + 1))

        # Return sorted according to topological order
        return sorted(
            list(visited),
            key=lambda sid: self.dag.nodes[sid].topological_order if sid in self.dag.nodes else 999999,
        )

    def get_upstream_sccs(self, target_scc_id: str, max_depth: int = 10) -> List[str]:
        """Calculates upstream dependencies in the DAG up to max_depth."""
        if target_scc_id not in self.dag.nodes:
            return []

        visited: Set[str] = set()
        queue = [(target_scc_id, 0)]

        while queue:
            curr_scc, depth = queue.pop(0)
            if depth >= max_depth:
                continue

            node = self.dag.nodes.get(curr_scc)
            if not node:
                continue

            for upstream in node.upstream_scc_ids:
                if upstream not in visited:
                    visited.add(upstream)
                    queue.append((upstream, depth + 1))

        return sorted(list(visited))

    def get_scc_depth(self, scc_id: str) -> int:
        """Computes depth in the DAG (longest distance from root)."""
        node = self.dag.nodes.get(scc_id)
        if not node:
            return 0
        if not node.upstream_scc_ids:
            return 0
        return 1 + max((self.get_scc_depth(u) for u in node.upstream_scc_ids), default=0)

    def get_all_scc_ids(self) -> List[str]:
        return list(self.dag.nodes.keys())
