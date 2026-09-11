"""
JARVIS OS — Phase 39.1: TypeScript Dependency Service
Orchestrates parser, resolver, cache, graph, and validator into a unified service.
"""

from __future__ import annotations

import os
import time
from typing import Any, Dict, List, Optional, Set, Tuple

from intelligence.typescript_dependency.cache import TypeScriptDependencyCache
from intelligence.typescript_dependency.graph import NormalizedTypeScriptGraph
from intelligence.typescript_dependency.models import (
    BoundaryType,
    ConfidenceClass,
    TypeScriptDependencyIndex,
    TypeScriptExport,
    TypeScriptImport,
    TypeScriptSymbol,
)
from intelligence.typescript_dependency.parser import TypeScriptSyntaxParser
from intelligence.typescript_dependency.resolver import TypeScriptImportResolver
from intelligence.typescript_dependency.validator import TypeScriptGraphValidator


class TypeScriptDependencyService:
    """
    Main entry point for TypeScript/React dependency intelligence in JARVIS.
    Combines incremental caching, syntax parsing, alias/barrel resolution, and graph traversal.
    """

    IGNORED_DIRS = {
        ".git",
        ".jarvis",
        "node_modules",
        "dist",
        ".next",
        "build",
        "coverage",
        ".pytest_cache",
        "__pycache__",
        "venv",
    }

    VALID_EXTENSIONS = (".ts", ".tsx", ".js", ".jsx")

    def __init__(self, workspace_root: str, cache_file: Optional[str] = None) -> None:
        self.workspace_root = TypeScriptImportResolver.normalize_path(workspace_root)
        self.resolver = TypeScriptImportResolver(self.workspace_root)
        self.cache = TypeScriptDependencyCache(self.workspace_root, cache_file=cache_file)
        self.graph = NormalizedTypeScriptGraph(self.workspace_root)

    def scan_files(self) -> List[str]:
        """Discovers all TypeScript/JavaScript files in workspace."""
        found = []
        for root, dirs, files in os.walk(self.workspace_root):
            dirs[:] = [d for d in dirs if d not in self.IGNORED_DIRS]
            for f in files:
                if f.lower().endswith(self.VALID_EXTENSIONS):
                    abs_path = os.path.join(root, f)
                    rel_path = TypeScriptImportResolver.normalize_path(
                        os.path.relpath(abs_path, self.workspace_root)
                    )
                    found.append(rel_path)
        return sorted(found)

    def index_workspace(self, force_reparse: bool = False, use_node_bridge: bool = False) -> NormalizedTypeScriptGraph:
        """
        Incrementally indexes the workspace and builds the normalized dependency graph.
        """
        all_files = self.scan_files()
        self.resolver.set_known_files(set(all_files))

        indices: List[TypeScriptDependencyIndex] = []

        # 1. Parse or retrieve from cache
        for rel_path in all_files:
            abs_path = os.path.join(self.workspace_root, rel_path)
            try:
                with open(abs_path, "r", encoding="utf-8", errors="replace") as f:
                    content = f.read()
            except OSError:
                continue

            content_hash = TypeScriptSyntaxParser.compute_content_hash(content)

            cached_entry = None if force_reparse else self.cache.get(rel_path, content_hash)
            if cached_entry:
                indices.append(cached_entry)
            else:
                imports, exports, symbols, _ = TypeScriptSyntaxParser.parse_file(
                    rel_path,
                    self.workspace_root,
                    content=content,
                    use_node_bridge=use_node_bridge,
                )
                idx = TypeScriptDependencyIndex(
                    file_path=rel_path,
                    imports=imports,
                    exports=exports,
                    local_symbols=symbols,
                    imported_symbols=[s for imp in imports for s in imp.imported_symbols],
                    re_exports=[exp for exp in exports if exp.is_re_export],
                    content_hash=content_hash,
                    parsed_at=time.time(),
                )
                self.cache.put(idx)
                indices.append(idx)

        # 2. Resolve import targets
        for idx in indices:
            resolved_targets = []
            unresolved = []
            updated_imports = []

            for imp in idx.imports:
                target, conf, boundary = self.resolver.resolve_import(idx.file_path, imp.module_specifier)
                if target:
                    resolved_targets.append(target)
                elif boundary != BoundaryType.EXTERNAL_PACKAGE:
                    unresolved.append(imp.module_specifier)

                updated_imp = TypeScriptImport(
                    source_file=imp.source_file,
                    module_specifier=imp.module_specifier,
                    imported_symbols=imp.imported_symbols,
                    default_import=imp.default_import,
                    namespace_import=imp.namespace_import,
                    is_type_only=imp.is_type_only,
                    is_relative=imp.is_relative,
                    is_dynamic=imp.is_dynamic,
                    line_number=imp.line_number,
                    resolved_target=target,
                    confidence=conf,
                    boundary=boundary,
                )
                updated_imports.append(updated_imp)

            # Update re-exports with resolved targets
            updated_re_exports = []
            for exp in idx.re_exports:
                target = None
                if exp.re_export_source:
                    target, _, _ = self.resolver.resolve_import(idx.file_path, exp.re_export_source)
                    if target and target not in resolved_targets:
                        resolved_targets.append(target)

                updated_exp = TypeScriptExport(
                    source_file=exp.source_file,
                    exported_symbols=exp.exported_symbols,
                    is_default=exp.is_default,
                    is_re_export=exp.is_re_export,
                    re_export_source=exp.re_export_source,
                    is_star_export=exp.is_star_export,
                    star_namespace=exp.star_namespace,
                    is_type_only=exp.is_type_only,
                    line_number=exp.line_number,
                    resolved_target=target,
                )
                updated_re_exports.append(updated_exp)

            idx.imports = updated_imports
            idx.re_exports = updated_re_exports
            idx.resolved_targets = resolved_targets
            idx.unresolved_imports = unresolved

        # 3. Build graph
        self.graph.build_from_indices(indices)

        # 4. Save cache
        self.cache.save_to_disk()
        return self.graph

    def validate_graph(self) -> Dict[str, Any]:
        """Validates graph correctness."""
        return TypeScriptGraphValidator.validate_graph(self.graph, self.workspace_root)

    def invalidate_file(self, rel_path: str) -> Set[str]:
        """Invalidates a single file and returns its downstream blast radius."""
        return self.cache.invalidate_file(rel_path)

    def invalidate_tsconfig(self, tsconfig_path: str) -> Set[str]:
        """Invalidates all files under a modified tsconfig directory."""
        return self.cache.invalidate_tsconfig(tsconfig_path)

    def invalidate_package(self, package_path: str) -> Set[str]:
        """Invalidates all files under a modified package.json directory."""
        return self.cache.invalidate_package(package_path)

    def build_graph(self) -> NormalizedTypeScriptGraph:
        """Rebuilds and returns the normalized graph from current cache."""
        self.graph.build_from_indices(list(self.cache._cache.values()))
        return self.graph

