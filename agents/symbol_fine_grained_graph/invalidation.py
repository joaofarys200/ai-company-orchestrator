from __future__ import annotations

import time
from typing import Any, Dict, List, Optional, Set, Tuple

from .condensation import SymbolCondensationDAG, SymbolGraphCondenser
from .graph import SymbolDependencyGraph
from .models import SymbolEdge, SymbolNode, SymbolSCC
from .scc import SymbolSCCDetector


class IncrementalSymbolUpdater:
    """Handles incremental symbol updates, local SCC recomputation, and SCC split/merge lineage tracking."""

    def __init__(self, scc_detector: Optional[SymbolSCCDetector] = None, condenser: Optional[SymbolGraphCondenser] = None) -> None:
        self.scc_detector = scc_detector or SymbolSCCDetector()
        self.condenser = condenser or SymbolGraphCondenser()
        self.lineage_records: List[Dict[str, Any]] = []

    def handle_symbol_added(
        self,
        node: SymbolNode,
        new_edges: List[SymbolEdge],
        graph: SymbolDependencyGraph,
        current_sccs: List[SymbolSCC],
        revision: int,
    ) -> Tuple[List[SymbolSCC], SymbolCondensationDAG, Optional[Dict[str, Any]]]:
        """Handle SYMBOL_ADDED event incrementally."""
        graph.add_node(node)
        for edge in new_edges:
            graph.add_edge(edge)

        return self._recompute_and_record_lineage(
            trigger_symbol=node.symbol_id,
            trigger_edge=new_edges[0].to_dict() if new_edges else {},
            event_type="SYMBOL_ADDED",
            graph=graph,
            old_sccs=current_sccs,
            revision=revision,
        )

    def handle_symbol_removed(
        self,
        symbol_id: str,
        graph: SymbolDependencyGraph,
        current_sccs: List[SymbolSCC],
        revision: int,
    ) -> Tuple[List[SymbolSCC], SymbolCondensationDAG, Optional[Dict[str, Any]]]:
        """Handle SYMBOL_REMOVED event incrementally."""
        graph.remove_node(symbol_id)

        return self._recompute_and_record_lineage(
            trigger_symbol=symbol_id,
            trigger_edge={},
            event_type="SYMBOL_REMOVED",
            graph=graph,
            old_sccs=current_sccs,
            revision=revision,
        )

    def handle_edge_added(
        self,
        edge: SymbolEdge,
        graph: SymbolDependencyGraph,
        current_sccs: List[SymbolSCC],
        revision: int,
    ) -> Tuple[List[SymbolSCC], SymbolCondensationDAG, Optional[Dict[str, Any]]]:
        """Handle edge addition that might trigger an SCC_MERGE."""
        graph.add_edge(edge)

        return self._recompute_and_record_lineage(
            trigger_symbol=edge.source_symbol,
            trigger_edge=edge.to_dict(),
            event_type="EDGE_ADDED",
            graph=graph,
            old_sccs=current_sccs,
            revision=revision,
        )

    def handle_edge_removed(
        self,
        source_symbol: str,
        target_symbol: str,
        graph: SymbolDependencyGraph,
        current_sccs: List[SymbolSCC],
        revision: int,
    ) -> Tuple[List[SymbolSCC], SymbolCondensationDAG, Optional[Dict[str, Any]]]:
        """Handle edge removal that might trigger an SCC_SPLIT."""
        graph.remove_edge(source_symbol, target_symbol)

        return self._recompute_and_record_lineage(
            trigger_symbol=source_symbol,
            trigger_edge={"source_symbol": source_symbol, "target_symbol": target_symbol},
            event_type="EDGE_REMOVED",
            graph=graph,
            old_sccs=current_sccs,
            revision=revision,
        )

    def _recompute_and_record_lineage(
        self,
        trigger_symbol: str,
        trigger_edge: Dict[str, Any],
        event_type: str,
        graph: SymbolDependencyGraph,
        old_sccs: List[SymbolSCC],
        revision: int,
    ) -> Tuple[List[SymbolSCC], SymbolCondensationDAG, Optional[Dict[str, Any]]]:
        """Recompute SCCs and condensation DAG, identifying SCC_SPLIT or SCC_MERGE lineage."""
        old_scc_ids = [s.scc_id for s in old_sccs]
        old_sizes = {s.scc_id: s.size for s in old_sccs}

        # Re-detect SCCs
        new_sccs = self.scc_detector.detect_sccs(graph)
        new_scc_ids = [s.scc_id for s in new_sccs]

        # Recompute DAG
        new_dag = self.condenser.condense(graph, new_sccs, revision=revision)

        # Detect split or merge
        transition_type = "INCREMENTAL_UPDATE"
        if len(new_sccs) > len(old_sccs):
            transition_type = "SCC_SPLIT"
        elif len(new_sccs) < len(old_sccs):
            transition_type = "SCC_MERGE"

        lineage_record = {
            "timestamp": time.time(),
            "revision": revision,
            "event_type": event_type,
            "transition_type": transition_type,
            "trigger_symbol": trigger_symbol,
            "trigger_edge": trigger_edge,
            "old_scc_count": len(old_sccs),
            "new_scc_count": len(new_sccs),
            "old_scc_ids": old_scc_ids[:5],
            "new_scc_ids": new_scc_ids[:5],
        }
        self.lineage_records.append(lineage_record)

        return new_sccs, new_dag, lineage_record
