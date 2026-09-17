from __future__ import annotations

import time
from collections import deque
from typing import Any, Dict, List, Optional, Set, Tuple

from .boundary import SymbolBoundaryManager
from .condensation import SymbolCondensationDAG
from .graph import SymbolDependencyGraph
from .models import (
    ImpactConfidence,
    SymbolAwareImpactResult,
    SymbolImpactScope,
    SymbolPrecisionComparison,
    SymbolSCC,
)


class SymbolAwareImpactAnalyzer:
    """Calculates targeted blast radius starting from individual symbol IDs.

    Computes both Symbol-Level Impact and File-Level Impact simultaneously,
    quantifying precision gains and overapproximation reduction.
    """

    def __init__(self, boundary_mgr: Optional[SymbolBoundaryManager] = None) -> None:
        self.boundary_mgr = boundary_mgr or SymbolBoundaryManager()

    def analyze_symbol_impact(
        self,
        symbol_id: str,
        graph: SymbolDependencyGraph,
        dag: SymbolCondensationDAG,
        contract_index: Optional[Dict[str, List[str]]] = None,
        task_index: Optional[Dict[str, List[str]]] = None,
        scenario_index: Optional[Dict[str, List[str]]] = None,
    ) -> Tuple[SymbolAwareImpactResult, SymbolPrecisionComparison]:
        """Traverse the condensation DAG downstream from the root symbol's SCC."""
        start_time = time.perf_counter()

        # 1. Locate root node and its SCC
        root_sym = graph.nodes.get(symbol_id)
        root_file = root_sym.file_id if root_sym else (symbol_id.split("::")[0] if "::" in symbol_id else "")

        # Find which SCC contains this symbol
        root_scc_id: Optional[str] = None
        for scc_id, node in dag.nodes.items():
            if symbol_id in node.scc.symbols:
                root_scc_id = scc_id
                break

        if not root_scc_id:
            # Symbol not in any detected SCC (e.g. isolated or missing)
            # Create a virtual single-node SCC
            root_scc_id = f"scc_virtual_{symbol_id}"

        # 2. Downstream BFS traversal across DAG
        visited_sccs: Set[str] = set()
        queue: deque[Tuple[str, int]] = deque([(root_scc_id, 0)])
        visited_sccs.add(root_scc_id)

        included_sccs: List[str] = []
        excluded_sccs: List[str] = []
        boundary_edges: List[Dict[str, Any]] = []
        affected_symbols: Set[str] = set()
        affected_files: Set[str] = set()
        truncated = False

        if root_file:
            affected_files.add(root_file)

        root_service = root_file.split("/")[0] if root_file else ""

        while queue:
            curr_scc_id, depth = queue.popleft()
            dag_node = dag.nodes.get(curr_scc_id)
            if not dag_node:
                affected_symbols.add(symbol_id)
                included_sccs.append(curr_scc_id)
                continue

            # Check boundary cutoff
            should_cut, cut_record = self.boundary_mgr.should_cut(
                current_depth=depth,
                accumulated_symbol_count=len(affected_symbols),
                target_scc=dag_node.scc,
                source_service=root_service,
            )

            if should_cut and depth > 0:
                truncated = True
                excluded_sccs.append(curr_scc_id)
                if cut_record:
                    boundary_edges.append(cut_record.to_dict())
                continue

            included_sccs.append(curr_scc_id)
            for sym in dag_node.scc.symbols:
                affected_symbols.add(sym)
            for f in dag_node.scc.files:
                affected_files.add(f)

            # Enqueue consumers that depend on this SCC (and downstream dependents)
            for next_scc_id in list(dict.fromkeys(dag_node.upstream_scc_ids + dag_node.downstream_scc_ids)):
                if next_scc_id not in visited_sccs:
                    visited_sccs.add(next_scc_id)
                    queue.append((next_scc_id, depth + 1))

        # 3. Classify internal vs external symbols
        internal_affected = [s for s in affected_symbols if s.startswith(root_file)] if root_file else list(affected_symbols)
        external_affected = [s for s in affected_symbols if s not in internal_affected]

        # 4. Integrate Contracts, Tasks, and Scenarios
        c_index = contract_index or {}
        t_index = task_index or {}
        sc_index = scenario_index or {}

        affected_contracts: Set[str] = set()
        affected_tasks: Set[str] = set()
        affected_scenarios: Set[str] = set()

        for sym in affected_symbols:
            for c in c_index.get(sym, []):
                affected_contracts.add(c)
            for t in t_index.get(sym, []):
                affected_tasks.add(t)
            for sc in sc_index.get(sym, []):
                affected_scenarios.add(sc)

        for f in affected_files:
            for c in c_index.get(f, []):
                affected_contracts.add(c)
            for t in t_index.get(f, []):
                affected_tasks.add(t)
            for sc in sc_index.get(f, []):
                affected_scenarios.add(sc)

        # 5. Determine Scope
        services = sorted(list({f.split("/")[0] for f in affected_files if "/" in f}))
        if len(affected_symbols) <= 1:
            scope = SymbolImpactScope.SYMBOL_LOCAL
        elif len(affected_files) == 1:
            scope = SymbolImpactScope.FILE_LOCAL
        elif len(services) <= 1 and len(affected_files) <= 5:
            scope = SymbolImpactScope.MODULE
        elif len(services) == 1:
            scope = SymbolImpactScope.SERVICE
        elif len(services) > 1 and len(affected_files) < 15:
            scope = SymbolImpactScope.CROSS_SERVICE
        else:
            scope = SymbolImpactScope.REPOSITORY_WIDE

        confidence = ImpactConfidence.BOUNDARY_LIMITED if truncated else ImpactConfidence.FULL

        # Blast radius score
        blast_score = round(
            (len(affected_symbols) * 0.4)
            + (len(affected_files) * 0.3)
            + (len(affected_contracts) * 0.2)
            + (len(affected_tasks) * 0.1),
            2,
        )

        extraction_ms = round((time.perf_counter() - start_time) * 1000, 2)

        impact_res = SymbolAwareImpactResult(
            impact_id=f"impact_{symbol_id.replace(':', '_')}",
            root_symbols=[symbol_id],
            root_sccs=[root_scc_id],
            included_sccs=included_sccs,
            excluded_sccs=excluded_sccs,
            boundary_edges=boundary_edges,
            scope=scope,
            confidence=confidence,
            affected_symbols=sorted(list(affected_symbols)),
            internal_affected_symbols=sorted(internal_affected),
            external_affected_symbols=sorted(external_affected),
            affected_files=sorted(list(affected_files)),
            contracts=sorted(list(affected_contracts)),
            tasks=sorted(list(affected_tasks)),
            browser_scenarios=sorted(list(affected_scenarios)),
            services=services,
            blast_radius_score=blast_score,
            truncated_at_boundary=truncated,
            extraction_ms=extraction_ms,
        )

        # 6. Compute File-Level Impact vs Symbol-Level Impact Comparison
        comparison = self._compare_with_file_impact(root_file, symbol_id, impact_res, graph, dag)

        return impact_res, comparison

    def _compare_with_file_impact(
        self,
        root_file: str,
        symbol_id: str,
        sym_impact: SymbolAwareImpactResult,
        graph: SymbolDependencyGraph,
        dag: SymbolCondensationDAG,
    ) -> SymbolPrecisionComparison:
        """Compare symbol-level blast radius against traditional coarse file-level propagation."""
        # In a file-level graph, modifying root_file triggers all files downstream in the file graph
        file_dependents = graph.get_file_dependents(root_file) if root_file else set()
        file_reach = {root_file} | file_dependents

        # Count total symbols residing in all reached files
        total_file_symbols = 0
        for f in file_reach:
            syms_in_file = graph.file_to_symbols.get(f, set())
            total_file_symbols += max(len(syms_in_file), 1)

        # Size of root symbol's SCC vs coarse file SCC
        root_dag_node = dag.nodes.get(sym_impact.root_sccs[0]) if sym_impact.root_sccs else None
        sym_scc_size = root_dag_node.scc.size if root_dag_node else 1

        # File SCC size approximation (all symbols in the files of the root SCC)
        file_scc_size = 0
        if root_dag_node:
            for f in root_dag_node.scc.files:
                file_scc_size += max(len(graph.file_to_symbols.get(f, set())), 1)
        file_scc_size = max(file_scc_size, sym_scc_size)

        sym_impact_count = len(sym_impact.affected_symbols)
        file_impact_count = max(total_file_symbols, sym_impact_count)

        precision_gain = round(1.0 - (sym_impact_count / file_impact_count), 4) if file_impact_count > 0 else 0.0
        overapproximation_reduction = (
            round((file_scc_size - sym_scc_size) / file_scc_size, 4) if file_scc_size > 0 else 0.0
        )

        reasons: List[str] = [
            f"File-level graph conflates all {total_file_symbols} symbols in {len(file_reach)} files.",
            f"Symbol-level graph resolved {sym_impact_count} precise symbols directly on the call/import graph.",
            f"Overapproximation reduced by {round(overapproximation_reduction * 100, 1)}% through granular edge filtering.",
        ]

        return SymbolPrecisionComparison(
            file_scc_size=file_scc_size,
            symbol_scc_size=sym_scc_size,
            file_impact_count=file_impact_count,
            symbol_impact_count=sym_impact_count,
            precision_gain=max(precision_gain, 0.0),
            overapproximation_reduction=max(overapproximation_reduction, 0.0),
            reasons=reasons,
        )
