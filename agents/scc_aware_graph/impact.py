from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

from .models import CondensationDAG, SCCAwareImpactResult
from .subgraph import SCCAwareSubgraphExtractor


class SCCAwareImpactAnalyzer:
    """Performs high-level impact analysis separating internal cycle blast radius from boundary propagation."""

    def __init__(self, dag: CondensationDAG, node_to_scc: Dict[str, str]) -> None:
        self.dag = dag
        self.node_to_scc = node_to_scc
        self.extractor = SCCAwareSubgraphExtractor(dag, node_to_scc)

    def analyze_impact(
        self,
        changed_symbols: List[str],
        max_sccs: int = 15,
        max_nodes: int = 250,
        max_depth: int = 3,
        contracts_map: Optional[Dict[str, List[str]]] = None,
        tasks_map: Optional[Dict[str, List[str]]] = None,
    ) -> SCCAwareImpactResult:
        return self.extractor.extract_scc_subgraph(
            root_symbols=changed_symbols,
            max_sccs=max_sccs,
            max_nodes=max_nodes,
            max_depth=max_depth,
            contracts_map=contracts_map,
            tasks_map=tasks_map,
        )

    def compare_naive_vs_scc_impact(
        self,
        changed_symbols: List[str],
        raw_edges: List[Dict[str, Any]],
        naive_max_depth: int = 3,
        naive_max_nodes: int = 50,
    ) -> Dict[str, Any]:
        """Compares naive BFS DFS exploration against SCC-aware condensation exploration."""
        # 1. Run Naive DFS
        t_naive0 = time.perf_counter()
        visited_nodes = set(changed_symbols)
        queue = [(s, 0) for s in changed_symbols]
        edges_explored = 0
        truncated_naive = False

        adj: Dict[str, List[str]] = {}
        for e in raw_edges:
            src = e.get("source") or e.get("src", "")
            tgt = e.get("target") or e.get("dst", "")
            adj.setdefault(src, []).append(tgt)

        while queue and len(visited_nodes) < naive_max_nodes:
            curr, depth = queue.pop(0)
            if depth >= naive_max_depth:
                truncated_naive = True
                continue
            for neighbor in adj.get(curr, []):
                edges_explored += 1
                if neighbor not in visited_nodes:
                    visited_nodes.add(neighbor)
                    queue.append((neighbor, depth + 1))

        if len(visited_nodes) >= naive_max_nodes and queue:
            truncated_naive = True
        naive_time_ms = (time.perf_counter() - t_naive0) * 1000.0

        # 2. Run SCC-Aware Analysis
        scc_result = self.analyze_impact(changed_symbols)

        return {
            "naive_approach": {
                "nodes_visited": len(visited_nodes),
                "edges_explored": edges_explored,
                "latency_ms": round(naive_time_ms, 3),
                "truncated_arbitrarily": truncated_naive,
                "confidence": "UNKNOWN" if truncated_naive else "FULL",
            },
            "scc_aware_approach": {
                "included_sccs": len(scc_result.included_sccs),
                "nodes_visited": len(scc_result.affected_symbols),
                "internal_nodes": len(scc_result.internal_affected_symbols),
                "external_nodes": len(scc_result.external_affected_symbols),
                "boundary_edges": len(scc_result.boundary_edges),
                "latency_ms": scc_result.extraction_ms,
                "confidence": scc_result.confidence.value,
                "scope": scc_result.scope.value,
                "blast_radius_score": scc_result.blast_radius_score,
            },
            "structural_clarity_improvement": (
                "Preserved whole strongly connected components without mid-cycle cuts; "
                "isolated internal cycle propagation from cross-service boundary edges."
            ),
        }
