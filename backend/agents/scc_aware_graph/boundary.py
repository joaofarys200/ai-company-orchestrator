from __future__ import annotations

from typing import Any, Dict, List, Set, Tuple

from .models import CondensationDAG, ImpactConfidence, SCCBoundaryCut


class SCCBoundaryManager:
    """Manages exploration budgets across the condensation DAG and reports explicit boundary cuts."""

    def __init__(self, dag: CondensationDAG) -> None:
        self.dag = dag

    def compute_bounded_sccs(
        self,
        root_scc_ids: List[str],
        max_sccs: int = 15,
        max_nodes: int = 250,
        max_depth: int = 3,
    ) -> Tuple[List[str], List[str], List[Dict[str, Any]], ImpactConfidence]:
        """Traverses the Condensation DAG preserving whole SCCs and halting cleanly at boundaries."""
        included_sccs: List[str] = []
        excluded_sccs: Set[str] = set()
        boundary_edges: List[Dict[str, Any]] = []

        total_nodes = 0
        visited: Set[str] = set()
        queue: List[Tuple[str, int]] = [(sid, 0) for sid in root_scc_ids if sid in self.dag.nodes]

        truncated = False

        while queue:
            curr_scc_id, depth = queue.pop(0)
            if curr_scc_id in visited:
                continue

            node = self.dag.nodes.get(curr_scc_id)
            if not node:
                continue

            scc_size = node.scc.size

            # Check if including this entire SCC would violate budgets (unless it's a root SCC)
            if visited and (len(included_sccs) >= max_sccs or (total_nodes + scc_size > max_nodes) or depth > max_depth):
                excluded_sccs.add(curr_scc_id)
                truncated = True
                continue

            visited.add(curr_scc_id)
            included_sccs.append(curr_scc_id)
            total_nodes += scc_size

            # Explore downstream meta-edges
            for downstream_id in node.downstream_scc_ids:
                if downstream_id not in visited:
                    queue.append((downstream_id, depth + 1))

        # Collect exact boundary edges: outgoing edges from included SCCs that point to non-included nodes
        included_set = set(included_sccs)
        for sid in included_sccs:
            scc_node = self.dag.nodes[sid]
            for edge in scc_node.scc.outgoing_edges:
                tgt_node = edge.get("target") or edge.get("dst", "")
                # Check if target belongs to an included SCC
                target_in_included = False
                for inc_id in included_sccs:
                    if tgt_node in self.dag.nodes[inc_id].scc.nodes:
                        target_in_included = True
                        break
                if not target_in_included:
                    boundary_edges.append(edge)

        confidence = ImpactConfidence.BOUNDARY_LIMITED if (truncated or len(boundary_edges) > 0 and len(included_sccs) < len(self.dag.nodes)) else ImpactConfidence.FULL
        if not truncated and len(boundary_edges) == 0:
            confidence = ImpactConfidence.FULL

        return included_sccs, sorted(list(excluded_sccs)), boundary_edges, confidence
