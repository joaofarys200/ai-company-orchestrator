from __future__ import annotations

import os
from typing import Any, Dict, List, Optional, Set, Tuple

from .aliases import AliasResolver
from .boundary import SymbolBoundaryManager
from .cache import SymbolGraphCache
from .condensation import SymbolCondensationDAG, SymbolGraphCondenser
from .coupling import SymbolCouplingCalculator
from .edges import SymbolEdgeBuilder
from .extractor import MultiLanguageSymbolExtractor
from .graph import SymbolDependencyGraph
from .impact import SymbolAwareImpactAnalyzer
from .index import SymbolIndex
from .invalidation import IncrementalSymbolUpdater
from .metrics import SymbolMetricsCollector
from .models import (
    BarrelAnalysisResult,
    BarrelClassification,
    SymbolAwareImpactResult,
    SymbolEdge,
    SymbolNode,
    SymbolPrecisionComparison,
    SymbolSCC,
)
from .reexports import BarrelAnalyzer
from .resolver import GlobalSymbolResolver
from .scc import SymbolSCCDetector
from .security import SymbolSecuritySentinel
from .storage import SymbolSQLiteStorage
from .symbols import SymbolManager
from .validator import SymbolGraphValidator


class SymbolFineGrainedGraphBridge:
    """Unified facade orchestrating the Symbol-Fine-Grained Dependency Graph and SCC Precision layer."""

    _instance: Optional[SymbolFineGrainedGraphBridge] = None

    def __init__(self, workspace_root: Optional[str] = None, db_path: str = ":memory:") -> None:
        self.workspace_root = (workspace_root or os.getcwd()).replace("\\", "/")
        self.mgr = SymbolManager()
        self.edge_builder = SymbolEdgeBuilder()
        self.extractor = MultiLanguageSymbolExtractor(self.mgr)
        self.aliases = AliasResolver()
        self.resolver = GlobalSymbolResolver(self.aliases)
        self.barrel_analyzer = BarrelAnalyzer()
        self.graph = SymbolDependencyGraph()
        self.scc_detector = SymbolSCCDetector()
        self.condenser = SymbolGraphCondenser()
        self.boundary_mgr = SymbolBoundaryManager()
        self.coupling_calc = SymbolCouplingCalculator()
        self.impact_analyzer = SymbolAwareImpactAnalyzer(self.boundary_mgr)
        self.updater = IncrementalSymbolUpdater(self.scc_detector, self.condenser)
        self.cache = SymbolGraphCache()
        self.storage = SymbolSQLiteStorage(db_path)
        self.metrics = SymbolMetricsCollector()
        self.security = SymbolSecuritySentinel(self.workspace_root)
        self.validator = SymbolGraphValidator()
        self.index = SymbolIndex()

        self.sccs: List[SymbolSCC] = []
        self.dag: Optional[SymbolCondensationDAG] = None
        self.barrel_results: Dict[str, BarrelAnalysisResult] = {}
        self.revision = 1

    @classmethod
    def get_instance(cls, workspace_root: Optional[str] = None, db_path: str = ":memory:") -> SymbolFineGrainedGraphBridge:
        """Singleton accessor."""
        if cls._instance is None:
            cls._instance = cls(workspace_root, db_path)
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """Reset singleton for test isolation."""
        cls._instance = None

    def build_from_files(self, files_dict: Dict[str, str]) -> Dict[str, Any]:
        """Build the full symbol graph from a dict of {file_path: file_content}."""
        # 1. Clear previous state
        self.graph = SymbolDependencyGraph()
        self.index.clear()
        self.aliases.clear()
        self.resolver = GlobalSymbolResolver(self.aliases)
        all_symbols: List[SymbolNode] = []
        raw_edges: List[SymbolEdge] = []

        # 2. Multi-language AST symbol extraction
        for fpath, content in files_dict.items():
            syms, edges = self.extractor.extract_file(fpath, content)
            for s in syms:
                if self.security.validate_symbol_node(s):
                    all_symbols.append(s)
                    self.graph.add_node(s)
                    self.index.index_symbol(s)
            for e in edges:
                if self.security.validate_symbol_edge(e):
                    raw_edges.append(e)

        # 3. Global cross-module symbol resolution
        self.resolver.index_symbols(all_symbols)

        # 4. Barrel analysis and resolution map registration
        target_counts: Dict[str, int] = {f: len(self.graph.file_to_symbols.get(f, set())) for f in files_dict}
        raw_edges_by_sym: Dict[str, List[SymbolEdge]] = {}
        for e in raw_edges:
            raw_edges_by_sym.setdefault(e.source_symbol, []).append(e)

        for fpath, syms in self.graph.file_to_symbols.items():
            file_sym_objects = [self.graph.nodes[s] for s in syms if s in self.graph.nodes]
            if self.barrel_analyzer.is_barrel(fpath, file_sym_objects):
                file_edges = [e for s in syms for e in raw_edges_by_sym.get(s, [])]
                b_res = self.barrel_analyzer.analyze_barrel(fpath, file_sym_objects, file_edges, target_counts)
                self.barrel_results[fpath] = b_res
                for exp_name, target in b_res.resolution_map.items():
                    self.resolver.register_barrel_reexport(fpath, exp_name, target)

        # 5. Resolve edges and populate graph
        resolved_edges = self.resolver.resolve_edges(raw_edges)
        for e in resolved_edges:
            self.graph.add_edge(e)

        # 6. Symbol-level SCC Detection (Iterative Tarjan)
        self.sccs = self.scc_detector.detect_sccs(self.graph)

        # 7. Condensation DAG (Kahn's Algorithm)
        self.dag = self.condenser.condense(self.graph, self.sccs, revision=self.revision)

        # 8. Formal Validation
        part_ok, part_errs = self.validator.validate_scc_partition(self.graph, self.sccs)
        dag_ok, dag_errs = self.validator.validate_dag_acyclicity(self.dag)
        ground_ok, ground_errs = self.validator.validate_file_edge_grounding(self.graph)

        # 9. Persist to storage
        self.storage.save_graph(self.graph, self.sccs, self.dag, revision=self.revision)

        largest_scc = self.sccs[0] if self.sccs else None

        return {
            "symbol_count": len(self.graph.nodes),
            "symbol_edge_count": len(self.graph.edges),
            "file_count": len(self.graph.file_to_symbols),
            "derived_file_edge_count": len(self.graph.get_derived_file_edges()),
            "scc_count": len(self.sccs),
            "largest_scc_size": largest_scc.size if largest_scc else 0,
            "largest_scc_id": largest_scc.scc_id if largest_scc else None,
            "barrel_count": len(self.barrel_results),
            "partition_valid": part_ok,
            "dag_acyclic": dag_ok,
            "grounding_valid": ground_ok,
            "validation_errors": part_errs + dag_errs + ground_errs,
        }

    def query_symbol_impact(
        self,
        symbol_id: str,
        contracts: Optional[Dict[str, List[str]]] = None,
        tasks: Optional[Dict[str, List[str]]] = None,
        scenarios: Optional[Dict[str, List[str]]] = None,
    ) -> Dict[str, Any]:
        """Query targeted blast radius starting from a fine-grained symbol_id."""
        if not self.dag:
            return {"error": "Graph has not been constructed yet."}

        impact_res, comparison = self.impact_analyzer.analyze_symbol_impact(
            symbol_id=symbol_id,
            graph=self.graph,
            dag=self.dag,
            contract_index=contracts,
            task_index=tasks,
            scenario_index=scenarios,
        )

        return {
            "impact": impact_res.to_dict(),
            "comparison": comparison.to_dict(),
        }

    def get_status(self) -> Dict[str, Any]:
        """Return global telemetry and architectural health."""
        largest_scc = self.sccs[0] if self.sccs else None
        return {
            "symbol_count": len(self.graph.nodes),
            "symbol_edge_count": len(self.graph.edges),
            "file_count": len(self.graph.file_to_symbols),
            "derived_file_edges": len(self.graph.get_derived_file_edges()),
            "scc_count": len(self.sccs),
            "largest_scc_size": largest_scc.size if largest_scc else 0,
            "barrel_modules_detected": len(self.barrel_results),
            "cache_hit_ratio": self.cache.hit_ratio,
            "revision": self.revision,
            "ram_mb": self.metrics.measure_memory_mb(),
            "ready": True,
        }

    def get_largest_scc(self) -> Optional[Dict[str, Any]]:
        """Return detailed info on the largest symbol SCC."""
        if not self.sccs:
            return None
        largest = self.sccs[0]
        coupling = self.coupling_calc.compute_metrics(largest, self.graph)
        res = largest.to_dict()
        res["coupling"] = coupling
        return res
