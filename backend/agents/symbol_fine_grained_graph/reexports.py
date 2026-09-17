from __future__ import annotations

import os
from typing import Dict, List, Optional, Set, Tuple

from .models import BarrelAnalysisResult, BarrelClassification, SymbolEdge, SymbolEdgeType, SymbolNode


class BarrelAnalyzer:
    """Analyzes barrel and re-export modules (__init__.py, index.ts, index.js).

    Disentangles monolithic barrel re-exports, mapping individual exported symbols
    to their origin instead of conflating all consumers into a single massive cluster.
    """

    BARREL_FILENAMES = {
        "__init__.py",
        "index.ts",
        "index.js",
        "index.tsx",
        "index.jsx",
        "index.d.ts",
    }

    def is_barrel(self, file_path: str, symbols: Optional[List[SymbolNode]] = None) -> bool:
        """Determine if a file is a barrel module by filename or export composition."""
        normalized = file_path.replace("\\", "/")
        base = os.path.basename(normalized)
        if base in self.BARREL_FILENAMES:
            return True

        if symbols:
            # If >60% of symbols are re-exports or exports, classify as barrel
            reexport_count = sum(1 for s in symbols if s.exported or s.imported or s.name in ("__all__", "*"))
            if len(symbols) >= 3 and (reexport_count / len(symbols)) >= 0.6:
                return True

        return False

    def analyze_barrel(
        self,
        barrel_file: str,
        symbols: List[SymbolNode],
        edges: List[SymbolEdge],
        target_file_symbol_counts: Optional[Dict[str, int]] = None,
    ) -> BarrelAnalysisResult:
        """Analyze barrel file to map individual re-exports and quantify overapproximation."""
        normalized_file = barrel_file.replace("\\", "/")
        target_counts = target_file_symbol_counts or {}

        reexported_symbols: List[str] = []
        resolution_map: Dict[str, str] = {}
        target_modules: Set[str] = set()

        for edge in edges:
            if edge.edge_type == SymbolEdgeType.REEXPORTS:
                reexported_symbols.append(edge.source_symbol)
                resolution_map[edge.source_symbol] = edge.target_symbol

                # Extract target module
                target_sym = edge.target_symbol
                if "::" in target_sym:
                    mod_part = target_sym.split("::")[0]
                    target_modules.add(mod_part)

        # Measure overapproximation
        # File-level edge treats the whole target module as dependent
        # If target module has 50 symbols but barrel only re-exports 2, ratio is 50/2 = 25.0
        total_target_symbols = 0
        for mod in target_modules:
            total_target_symbols += target_counts.get(mod, max(len(reexported_symbols), 10))

        actual_reexported = len(reexported_symbols)
        if actual_reexported == 0:
            ratio = 1.0
            classification = BarrelClassification.UNKNOWN
        else:
            ratio = round(total_target_symbols / max(actual_reexported, 1), 2)
            if ratio > 3.0 or any("*" in s for s in reexported_symbols):
                classification = BarrelClassification.OVER_APPROXIMATED
            else:
                classification = BarrelClassification.EXACT

        return BarrelAnalysisResult(
            barrel_file=normalized_file,
            reexported_symbols=reexported_symbols,
            resolution_map=resolution_map,
            overapproximation_ratio=ratio,
            classification=classification,
            details={
                "target_modules": sorted(list(target_modules)),
                "reexport_count": actual_reexported,
                "total_target_symbols": total_target_symbols,
                "is_barrel": self.is_barrel(barrel_file, symbols),
            },
        )
