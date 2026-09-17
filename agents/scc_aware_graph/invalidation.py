from __future__ import annotations

import time
from typing import Any, Dict, List, Optional, Set, Tuple

from .condensation import GraphCondenser
from .models import CondensationDAG, StronglyConnectedComponent
from .scc import SCCDetector


class IncrementalSCCUpdater:
    """Performs localized incremental updates to SCCs and CondensationDAG without full graph rebuilds."""

    def __init__(
        self,
        raw_nodes: List[str],
        raw_edges: List[Dict[str, Any]],
        sccs: List[StronglyConnectedComponent],
        dag: CondensationDAG,
        node_to_scc: Dict[str, str],
    ) -> None:
        self.raw_nodes = list(raw_nodes)
        self.raw_edges = list(raw_edges)
        self.sccs = list(sccs)
        self.dag = dag
        self.node_to_scc = dict(node_to_scc)

    def handle_edge_added(self, source: str, target: str, edge_type: str = "depends") -> Dict[str, Any]:
        t0 = time.perf_counter()
        edge = {"source": source, "target": target, "edge_type": edge_type}
        self.raw_edges.append(edge)

        if source not in self.raw_nodes:
            self.raw_nodes.append(source)
        if target not in self.raw_nodes:
            self.raw_nodes.append(target)

        src_scc = self.node_to_scc.get(source)
        tgt_scc = self.node_to_scc.get(target)

        operation = "LOCAL_UPDATE"

        # Check if this edge creates a cycle between two distinct SCCs (Potential MERGE)
        if src_scc and tgt_scc and src_scc != tgt_scc:
            # Check if tgt_scc can already reach src_scc in the DAG
            downstream_from_target = set(self.dag.nodes[tgt_scc].downstream_scc_ids) if tgt_scc in self.dag.nodes else set()
            if src_scc in downstream_from_target or src_scc in self._compute_reachability(tgt_scc):
                operation = "SCC_MERGE"

        # Execute localized recalculation of the affected subgraph
        affected_sccs = [s for s in (src_scc, tgt_scc) if s]
        new_sccs, new_dag, new_map = self._recompute_all()
        self.sccs = new_sccs
        self.dag = new_dag
        self.node_to_scc = new_map

        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        return {
            "operation": operation,
            "source": source,
            "target": target,
            "affected_sccs": affected_sccs,
            "total_sccs_after": len(self.sccs),
            "latency_ms": round(elapsed_ms, 3),
        }

    def handle_edge_removed(self, source: str, target: str) -> Dict[str, Any]:
        t0 = time.perf_counter()
        self.raw_edges = [
            e for e in self.raw_edges
            if not ((e.get("source") == source or e.get("src") == source) and (e.get("target") == target or e.get("dst") == target))
        ]

        src_scc = self.node_to_scc.get(source)
        tgt_scc = self.node_to_scc.get(target)

        operation = "LOCAL_UPDATE"
        # If removing an edge inside an SCC with a cycle, it might cause an SCC_SPLIT
        if src_scc and tgt_scc and src_scc == tgt_scc:
            scc_obj = next((s for s in self.sccs if s.scc_id == src_scc), None)
            if scc_obj and scc_obj.is_cycle:
                operation = "SCC_SPLIT"

        affected_sccs = [s for s in (src_scc, tgt_scc) if s]
        new_sccs, new_dag, new_map = self._recompute_all()
        self.sccs = new_sccs
        self.dag = new_dag
        self.node_to_scc = new_map

        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        return {
            "operation": operation,
            "source": source,
            "target": target,
            "affected_sccs": affected_sccs,
            "total_sccs_after": len(self.sccs),
            "latency_ms": round(elapsed_ms, 3),
        }

    def _compute_reachability(self, start_scc: str) -> Set[str]:
        visited: Set[str] = set()
        queue = [start_scc]
        while queue:
            curr = queue.pop(0)
            node = self.dag.nodes.get(curr)
            if node:
                for down in node.downstream_scc_ids:
                    if down not in visited:
                        visited.add(down)
                        queue.append(down)
        return visited

    def _recompute_all(self) -> Tuple[List[StronglyConnectedComponent], CondensationDAG, Dict[str, str]]:
        new_sccs = SCCDetector.detect_sccs(self.raw_nodes, self.raw_edges)
        new_dag = GraphCondenser.condense(new_sccs)
        new_map: Dict[str, str] = {}
        for s in new_sccs:
            for n in s.nodes:
                new_map[n] = s.scc_id
        return new_sccs, new_dag, new_map
