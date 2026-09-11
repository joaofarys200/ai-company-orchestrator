"""
JARVIS OS — Phase 39.1: Normalized TypeScript Dependency Graph
Builds, validates, and traverses the normalized dependency graph of TypeScript/React files.
Provides forward/reverse dependencies, barrel re-export chaining, symbol consumer tracking,
circular dependency detection, and integration with RepoGraph.
"""

from __future__ import annotations

from collections import defaultdict, deque
import os
from typing import Any, Dict, List, Optional, Set, Tuple

from intelligence.typescript_dependency.models import (
    BoundaryType,
    ConfidenceClass,
    DependencyEdge,
    DependencyRelationType,
    TypeScriptDependencyIndex,
    TypeScriptExport,
    TypeScriptImport,
    TypeScriptSymbol,
)


class NormalizedTypeScriptGraph:
    """
    Normalized directed dependency graph for TypeScript & React applications.
    Integrates seamlessly with RepoGraph and Predictive Impact Engine.
    """

    def __init__(self, workspace_root: str) -> None:
        self.workspace_root = workspace_root.replace(os.sep, "/")
        self.nodes: Set[str] = set()
        self.edges: List[DependencyEdge] = []
        self.forward_edges: Dict[str, Set[str]] = defaultdict(set)
        self.reverse_edges: Dict[str, Set[str]] = defaultdict(set)
        self.file_symbols: Dict[str, List[TypeScriptSymbol]] = defaultdict(list)
        self.symbol_exporters: Dict[str, List[Tuple[str, TypeScriptSymbol]]] = defaultdict(list)
        self.barrel_re_exports: Dict[str, List[TypeScriptExport]] = defaultdict(list)
        self.unresolved_dependencies: List[DependencyEdge] = []
        self.cycles: List[List[str]] = []

    def build_from_indices(self, indices: List[TypeScriptDependencyIndex]) -> NormalizedTypeScriptGraph:
        """Populates the normalized graph from a collection of file indices."""
        self.clear()

        # 1. Register nodes
        for idx in indices:
            norm_path = idx.file_path.replace(os.sep, "/")
            self.nodes.add(norm_path)
            self.file_symbols[norm_path] = list(idx.local_symbols)

            for sym in idx.local_symbols:
                if sym.is_exported:
                    self.symbol_exporters[sym.name].append((norm_path, sym))

        # 2. Build edges from imports and re-exports
        for idx in indices:
            src = idx.file_path.replace(os.sep, "/")

            # Direct Imports
            for imp in idx.imports:
                target = imp.resolved_target
                if target:
                    norm_target = target.replace(os.sep, "/")
                    rel_type = (
                        DependencyRelationType.ALIAS_RESOLVES
                        if "@" in imp.module_specifier
                        else DependencyRelationType.IMPORTS
                    )
                    edge = DependencyEdge(
                        source=src,
                        target=norm_target,
                        relation_type=rel_type,
                        confidence_class=imp.confidence,
                        origin="import",
                        resolved=True,
                        symbol=imp.imported_symbols[0] if imp.imported_symbols else None,
                        metadata={
                            "line_number": imp.line_number,
                            "is_type_only": imp.is_type_only,
                            "module_specifier": imp.module_specifier,
                            "boundary": imp.boundary.value if hasattr(imp.boundary, "value") else str(imp.boundary),
                        },
                    )
                    self._add_edge(edge)
                else:
                    # Unresolved or external import
                    if imp.boundary != BoundaryType.EXTERNAL_PACKAGE:
                        unres_edge = DependencyEdge(
                            source=src,
                            target=imp.module_specifier,
                            relation_type=DependencyRelationType.DYNAMIC_UNRESOLVED if imp.is_dynamic else DependencyRelationType.IMPORTS,
                            confidence_class=ConfidenceClass.UNCERTAIN,
                            origin="import",
                            resolved=False,
                            metadata={"is_dynamic": imp.is_dynamic, "line_number": imp.line_number},
                        )
                        self.unresolved_dependencies.append(unres_edge)

            # Re-exports & Barrels
            for exp in idx.re_exports:
                target = exp.resolved_target
                if target:
                    norm_target = target.replace(os.sep, "/")
                    edge = DependencyEdge(
                        source=src,
                        target=norm_target,
                        relation_type=DependencyRelationType.RE_EXPORTS,
                        confidence_class=ConfidenceClass.INFERRED,
                        origin="re-export",
                        resolved=True,
                        symbol=exp.exported_symbols[0] if exp.exported_symbols else "*",
                        metadata={
                            "is_star_export": exp.is_star_export,
                            "line_number": exp.line_number,
                        },
                    )
                    self._add_edge(edge)
                    self.barrel_re_exports[src].append(exp)

        # 3. Detect circular dependencies
        self.cycles = self.detect_circular_dependencies()
        return self

    def _add_edge(self, edge: DependencyEdge) -> None:
        """Adds a single edge preventing duplicates."""
        for existing in self.edges:
            if (
                existing.source == edge.source
                and existing.target == edge.target
                and existing.relation_type == edge.relation_type
                and existing.symbol == edge.symbol
            ):
                return
        self.edges.append(edge)
        self.forward_edges[edge.source].add(edge.target)
        self.reverse_edges[edge.target].add(edge.source)

    def get_forward_dependencies(self, file_path: str, recursive: bool = False) -> Set[str]:
        """Returns files imported by file_path."""
        norm = file_path.replace(os.sep, "/")
        if not recursive:
            return set(self.forward_edges.get(norm, set()))

        visited = set()
        queue = deque([norm])
        while queue:
            curr = queue.popleft()
            for dep in self.forward_edges.get(curr, set()):
                if dep not in visited and dep != norm:
                    visited.add(dep)
                    queue.append(dep)
        return visited

    def get_reverse_dependencies(self, file_path: str, recursive: bool = False) -> Set[str]:
        """Returns files that import file_path (consumers)."""
        norm = file_path.replace(os.sep, "/")
        if not recursive:
            return set(self.reverse_edges.get(norm, set()))

        visited = set()
        queue = deque([norm])
        while queue:
            curr = queue.popleft()
            for consumer in self.reverse_edges.get(curr, set()):
                if consumer not in visited and consumer != norm:
                    visited.add(consumer)
                    queue.append(consumer)
        return visited

    def resolve_symbol_origin(self, file_path: str, symbol_name: str) -> Optional[Tuple[str, TypeScriptSymbol]]:
        """
        Traces back through barrels/re-exports to find the originating declaration file for a symbol.
        """
        norm = file_path.replace(os.sep, "/")
        # 1. Check local declarations
        for sym in self.file_symbols.get(norm, []):
            if sym.name == symbol_name:
                return (norm, sym)

        # 2. Check re-exports from barrels
        for exp in self.barrel_re_exports.get(norm, []):
            if exp.resolved_target:
                target_file = exp.resolved_target.replace(os.sep, "/")
                if exp.is_star_export or symbol_name in exp.exported_symbols:
                    found = self.resolve_symbol_origin(target_file, symbol_name)
                    if found:
                        return found
        return None

    def get_symbol_consumers(self, origin_file: str, symbol_name: str) -> Set[str]:
        """
        Finds all files in the workspace that consume symbol_name, either directly
        or through intermediate barrel re-exports.
        """
        consumers = set()
        norm_origin = origin_file.replace(os.sep, "/")

        # Direct consumers of the origin file
        for consumer in self.reverse_edges.get(norm_origin, set()):
            # If consumer is a barrel, propagate to consumer's consumers
            if consumer in self.barrel_re_exports:
                consumers.update(self.get_reverse_dependencies(consumer, recursive=True))
            consumers.add(consumer)

        return consumers

    def detect_circular_dependencies(self) -> List[List[str]]:
        """Finds all simple cycles using Tarjan's or DFS cycle detection."""
        cycles = []
        visited = set()
        rec_stack = set()
        path = []

        def dfs(node: str):
            visited.add(node)
            rec_stack.add(node)
            path.append(node)

            for neighbor in sorted(self.forward_edges.get(node, set())):
                if neighbor not in visited:
                    dfs(neighbor)
                elif neighbor in rec_stack:
                    # Cycle detected
                    idx = path.index(neighbor)
                    cycle = path[idx:] + [neighbor]
                    cycles.append(cycle)

            path.pop()
            rec_stack.remove(node)

        for node in sorted(self.nodes):
            if node not in visited:
                dfs(node)

        return cycles

    def summary(self) -> Dict[str, Any]:
        """Returns formal statistical summary of the graph."""
        resolved_count = len([e for e in self.edges if e.resolved])
        unresolved_count = len(self.unresolved_dependencies)
        alias_edges = len([e for e in self.edges if e.relation_type == DependencyRelationType.ALIAS_RESOLVES])
        re_export_edges = len([e for e in self.edges if e.relation_type == DependencyRelationType.RE_EXPORTS])
        symbol_count = sum(len(syms) for syms in self.file_symbols.values())

        boundaries = {
            "INTRA_PACKAGE": len([e for e in self.edges if e.metadata.get("boundary") == "INTRA_PACKAGE"]),
            "INTER_PACKAGE": len([e for e in self.edges if e.metadata.get("boundary") == "INTER_PACKAGE"]),
            "EXTERNAL_PACKAGE": len([e for e in self.edges if e.metadata.get("boundary") == "EXTERNAL_PACKAGE"]),
        }

        return {
            "total_nodes": len(self.nodes),
            "total_edges": len(self.edges),
            "resolved_edges": resolved_count,
            "unresolved_edges": unresolved_count,
            "alias_resolved_edges": alias_edges,
            "re_export_edges": re_export_edges,
            "total_symbols_indexed": symbol_count,
            "circular_dependencies_count": len(self.cycles),
            "cycles": self.cycles,
            "boundaries": boundaries,
        }

    def clear(self) -> None:
        """Resets the graph."""
        self.nodes.clear()
        self.edges.clear()
        self.forward_edges.clear()
        self.reverse_edges.clear()
        self.file_symbols.clear()
        self.symbol_exporters.clear()
        self.barrel_re_exports.clear()
        self.unresolved_dependencies.clear()
        self.cycles.clear()
