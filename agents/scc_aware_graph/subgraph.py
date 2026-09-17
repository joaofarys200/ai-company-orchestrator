from __future__ import annotations

import time
import uuid
from typing import Any, Dict, List, Optional, Set

from .boundary import SCCBoundaryManager
from .models import (
    CondensationDAG,
    ImpactConfidence,
    SCCAwareImpactResult,
    SCCImpactScope,
)


class SCCAwareSubgraphExtractor:
    """Extracts targeted subgraphs structured around SCCs, preserving cycles without mid-cluster truncation."""

    def __init__(self, dag: CondensationDAG, node_to_scc: Dict[str, str]) -> None:
        self.dag = dag
        self.node_to_scc = node_to_scc
        self.boundary_manager = SCCBoundaryManager(dag)

    def extract_scc_subgraph(
        self,
        root_symbols: List[str],
        max_sccs: int = 15,
        max_nodes: int = 250,
        max_depth: int = 3,
        contracts_map: Optional[Dict[str, List[str]]] = None,
        tasks_map: Optional[Dict[str, List[str]]] = None,
    ) -> SCCAwareImpactResult:
        start_time = time.perf_counter()
        impact_id = f"scc_impact_{uuid.uuid4().hex[:8]}"
        c_map = contracts_map or {}
        t_map = tasks_map or {}

        # Step 1: Map root symbols to root SCCs
        root_sccs_set: Set[str] = set()
        for sym in root_symbols:
            scc_id = self.node_to_scc.get(sym)
            if scc_id:
                root_sccs_set.add(scc_id)

        root_sccs = sorted(list(root_sccs_set))

        # Step 2: Compute bounded SCCs via boundary manager
        included_sccs, excluded_sccs, boundary_edges, confidence = self.boundary_manager.compute_bounded_sccs(
            root_scc_ids=root_sccs,
            max_sccs=max_sccs,
            max_nodes=max_nodes,
            max_depth=max_depth,
        )

        # Step 3: Classify internal vs external symbols
        internal_symbols: Set[str] = set()
        external_symbols: Set[str] = set()
        all_services: Set[str] = set()
        all_contracts: Set[str] = set()
        all_tasks: Set[str] = set()
        browser_scenarios: Set[str] = set()

        for scc_id in included_sccs:
            node = self.dag.nodes.get(scc_id)
            if not node:
                continue

            scc = node.scc
            all_services.update(scc.services)

            if scc_id in root_sccs_set:
                internal_symbols.update(scc.nodes)
            else:
                external_symbols.update(scc.nodes)

            for sym in scc.nodes:
                if sym in c_map:
                    all_contracts.update(c_map[sym])
                if sym in t_map:
                    all_tasks.update(t_map[sym])
                if "ui" in sym.lower() or "button" in sym.lower() or "page" in sym.lower() or "view" in sym.lower():
                    browser_scenarios.add(f"qa_{sym.lower()}_render")

        all_affected = sorted(list(internal_symbols | external_symbols))

        # Step 4: Classify Scope
        if len(all_services) > 2 or "shared" in all_services:
            scope = SCCImpactScope.REPOSITORY_WIDE_SCC
        elif len(all_services) > 1:
            scope = SCCImpactScope.CROSS_SERVICE_SCC
        elif len(included_sccs) > 1 or len(all_affected) > 10:
            scope = SCCImpactScope.REGIONAL_SCC
        else:
            scope = SCCImpactScope.LOCAL_SCC

        # Step 5: Calculate Blast Radius Score
        # Formula: (total_nodes * 1.0) + (boundary_edges * 1.5) + (contracts * 3.0) + (services * 4.0)
        blast_score = (
            len(all_affected) * 1.0
            + len(boundary_edges) * 1.5
            + len(all_contracts) * 3.0
            + len(all_services) * 4.0
        )

        elapsed_ms = (time.perf_counter() - start_time) * 1000.0

        return SCCAwareImpactResult(
            impact_id=impact_id,
            root_symbols=sorted(root_symbols),
            root_sccs=root_sccs,
            included_sccs=included_sccs,
            excluded_sccs=excluded_sccs,
            boundary_edges=boundary_edges,
            scope=scope,
            confidence=confidence,
            affected_symbols=all_affected,
            internal_affected_symbols=sorted(list(internal_symbols)),
            external_affected_symbols=sorted(list(external_symbols)),
            contracts=sorted(list(all_contracts)),
            tasks=sorted(list(all_tasks)),
            browser_scenarios=sorted(list(browser_scenarios)),
            services=sorted(list(all_services)),
            blast_radius_score=round(blast_score, 2),
            truncated_at_boundary=(confidence == ImpactConfidence.BOUNDARY_LIMITED),
            extraction_ms=round(elapsed_ms, 3),
        )
