from __future__ import annotations

from typing import Dict, List, Set, Tuple

from .condensation import SymbolCondensationDAG
from .graph import SymbolDependencyGraph
from .models import SymbolSCC


class SymbolGraphValidator:
    """Formal verification of symbol graph invariants, SCC partition completeness, and DAG acyclicity."""

    def validate_scc_partition(self, graph: SymbolDependencyGraph, sccs: List[SymbolSCC]) -> Tuple[bool, List[str]]:
        """Verify that SCCs form a strict mathematical partition over graph symbols."""
        errors: List[str] = []
        seen_symbols: Set[str] = set()

        for scc in sccs:
            for sym in scc.symbols:
                if sym in seen_symbols:
                    errors.append(f"Symbol {sym} appears in multiple SCCs (duplicate assignment).")
                seen_symbols.add(sym)

        # Check for unassigned symbols
        missing_symbols = set(graph.nodes.keys()) - seen_symbols
        if missing_symbols:
            errors.append(f"{len(missing_symbols)} graph symbols were not assigned to any SCC.")

        return len(errors) == 0, errors

    def validate_dag_acyclicity(self, dag: SymbolCondensationDAG) -> Tuple[bool, List[str]]:
        """Verify that the Condensation DAG is strictly acyclic."""
        errors: List[str] = []
        if not dag.is_acyclic:
            errors.append("Condensation DAG was flagged as containing cycles.")

        # Check topological ordering property
        # For every edge (u, v), order(u) must be < order(v)
        node_orders = {nid: n.topological_order for nid, n in dag.nodes.items()}

        for edge in dag.edges:
            src = edge["source_scc"]
            dst = edge["target_scc"]
            src_order = node_orders.get(src, -1)
            dst_order = node_orders.get(dst, -1)

            if src_order >= dst_order and dst_order != -1:
                errors.append(f"Topological order violation on DAG edge {src} -> {dst}: {src_order} >= {dst_order}")

        return len(errors) == 0, errors

    def validate_file_edge_grounding(self, graph: SymbolDependencyGraph) -> Tuple[bool, List[str]]:
        """Verify that every derived file edge has at least 1 valid underlying symbol edge."""
        errors: List[str] = []
        edge_ids = {id(e) for e in graph.edges}
        for (src_file, dst_file), symbol_edges in graph._file_edge_index.items():
            if not symbol_edges:
                errors.append(f"File edge {src_file} -> {dst_file} has no grounding symbol edges.")
            for se in symbol_edges:
                if id(se) not in edge_ids:
                    errors.append(f"Grounding edge {se.source_symbol} -> {se.target_symbol} missing from graph edges.")

        return len(errors) == 0, errors
