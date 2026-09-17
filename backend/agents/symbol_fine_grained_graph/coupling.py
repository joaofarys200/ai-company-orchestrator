from __future__ import annotations

from typing import Any, Dict, List

from .graph import SymbolDependencyGraph
from .models import SymbolEdgeType, SymbolSCC


class SymbolCouplingCalculator:
    """Computes architectural coupling and instability metrics for symbol components."""

    def compute_metrics(self, scc: SymbolSCC, graph: SymbolDependencyGraph) -> Dict[str, Any]:
        """Calculate afferent, efferent coupling, instability, and internal cohesion."""
        symbol_set = set(scc.symbols)

        # Afferent (Ca): incoming edges from symbols outside this SCC
        afferent_edges = 0
        barrel_reexports = 0

        for sym in scc.symbols:
            for in_edge in graph.get_incoming_edges(sym):
                if in_edge.source_symbol not in symbol_set:
                    afferent_edges += 1
                if in_edge.edge_type == SymbolEdgeType.REEXPORTS:
                    barrel_reexports += 1

        # Efferent (Ce): outgoing edges from symbols in this SCC to outside
        efferent_edges = 0
        for sym in scc.symbols:
            for out_edge in graph.get_outgoing_edges(sym):
                if out_edge.target_symbol not in symbol_set:
                    efferent_edges += 1
                if out_edge.edge_type == SymbolEdgeType.REEXPORTS:
                    barrel_reexports += 1

        total_coupling = afferent_edges + efferent_edges
        instability = round(efferent_edges / total_coupling, 4) if total_coupling > 0 else 0.0

        # Cohesion: internal density
        cohesion = scc.density

        return {
            "scc_id": scc.scc_id,
            "size": scc.size,
            "afferent_coupling": afferent_edges,
            "efferent_coupling": efferent_edges,
            "instability": instability,
            "cohesion": cohesion,
            "barrel_reexports_count": barrel_reexports,
            "is_cycle": scc.is_cycle,
        }
