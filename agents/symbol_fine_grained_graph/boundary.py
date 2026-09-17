from __future__ import annotations

from typing import Dict, List, Optional, Set, Tuple

from .models import SymbolBoundaryCut, SymbolCondensationDAG, SymbolSCC


class SymbolBoundaryManager:
    """Enforces depth, node budget, and service boundaries without dissecting atomic SCCs."""

    def __init__(
        self,
        max_depth: int = 5,
        max_symbols: int = 1000,
        allow_cross_service: bool = True,
    ) -> None:
        self.max_depth = max_depth
        self.max_symbols = max_symbols
        self.allow_cross_service = allow_cross_service

    def should_cut(
        self,
        current_depth: int,
        accumulated_symbol_count: int,
        target_scc: SymbolSCC,
        source_service: Optional[str] = None,
    ) -> Tuple[bool, Optional[SymbolBoundaryCut]]:
        """Determine whether boundary cutoff should trigger for target_scc."""
        # 1. Depth check
        if current_depth > self.max_depth:
            return True, SymbolBoundaryCut(
                cut_scc_id=target_scc.scc_id,
                cut_depth=current_depth,
                outgoing_edges_cut=len(target_scc.edges_external),
                unexplored_symbol_count=target_scc.size,
            )

        # 2. Symbol budget check
        if accumulated_symbol_count + target_scc.size > self.max_symbols:
            return True, SymbolBoundaryCut(
                cut_scc_id=target_scc.scc_id,
                cut_depth=current_depth,
                outgoing_edges_cut=len(target_scc.edges_external),
                unexplored_symbol_count=target_scc.size,
            )

        # 3. Cross-service check
        if not self.allow_cross_service and source_service:
            if target_scc.services and any(svc != source_service for svc in target_scc.services):
                return True, SymbolBoundaryCut(
                    cut_scc_id=target_scc.scc_id,
                    cut_depth=current_depth,
                    outgoing_edges_cut=len(target_scc.edges_external),
                    unexplored_symbol_count=target_scc.size,
                )

        return False, None
