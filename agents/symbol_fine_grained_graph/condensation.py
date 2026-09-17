from __future__ import annotations

import heapq
from typing import Any, Dict, List, Set, Tuple

from .graph import SymbolDependencyGraph
from .models import SymbolCondensationDAG, SymbolCondensationDAGNode, SymbolSCC


class SymbolGraphCondenser:
    """Condenses a SymbolDependencyGraph into an acyclic Directed Acyclic Graph (DAG) of SCC meta-nodes."""

    def condense(
        self, graph: SymbolDependencyGraph, sccs: List[SymbolSCC], revision: int = 1
    ) -> SymbolCondensationDAG:
        """Condense SCCs into meta-nodes and meta-edges, ensuring topological acyclicity."""
        # 1. Map each symbol to its SCC ID
        sym_to_scc: Dict[str, str] = {}
        scc_map: Dict[str, SymbolSCC] = {}
        for scc in sccs:
            scc_map[scc.scc_id] = scc
            for sym in scc.symbols:
                sym_to_scc[sym] = scc.scc_id

        # 2. Build DAG nodes
        dag_nodes: Dict[str, SymbolCondensationDAGNode] = {
            scc.scc_id: SymbolCondensationDAGNode(scc_id=scc.scc_id, scc=scc)
            for scc in sccs
        }

        # 3. Create meta-edges between SCCs
        meta_edges_set: Set[Tuple[str, str]] = set()
        for edge in graph.edges:
            src_scc = sym_to_scc.get(edge.source_symbol)
            dst_scc = sym_to_scc.get(edge.target_symbol)
            if src_scc and dst_scc and src_scc != dst_scc:
                meta_edges_set.add((src_scc, dst_scc))

        meta_edges: List[Dict[str, Any]] = []
        for src_scc, dst_scc in sorted(list(meta_edges_set)):
            meta_edges.append({"source_scc": src_scc, "target_scc": dst_scc})
            if src_scc in dag_nodes and dst_scc in dag_nodes:
                dag_nodes[src_scc].downstream_scc_ids.append(dst_scc)
                dag_nodes[dst_scc].upstream_scc_ids.append(src_scc)

        # 4. Kahn's Algorithm for Topological Sort and Acyclicity Proof
        in_degree: Dict[str, int] = {scc_id: 0 for scc_id in dag_nodes}
        for src_scc, dst_scc in meta_edges_set:
            in_degree[dst_scc] = in_degree.get(dst_scc, 0) + 1

        # Min-heap for deterministic ordering by SCC ID
        heap: List[str] = [scc_id for scc_id, deg in in_degree.items() if deg == 0]
        heapq.heapify(heap)

        topological_order: List[str] = []
        order_idx = 0

        while heap:
            curr = heapq.heappop(heap)
            topological_order.append(curr)
            dag_nodes[curr].topological_order = order_idx
            order_idx += 1

            for neighbor in dag_nodes[curr].downstream_scc_ids:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    heapq.heappush(heap, neighbor)

        is_acyclic = len(topological_order) == len(dag_nodes)

        return SymbolCondensationDAG(
            dag_id=f"sym_dag_rev_{revision}",
            nodes=dag_nodes,
            edges=meta_edges,
            is_acyclic=is_acyclic,
            topological_ordering=topological_order,
            revision=revision,
        )
