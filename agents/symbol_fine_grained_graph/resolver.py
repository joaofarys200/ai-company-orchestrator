from __future__ import annotations

import os
from typing import Dict, List, Optional, Set, Tuple

from .aliases import AliasResolver
from .models import SymbolEdge, SymbolEdgeType, SymbolNode


class GlobalSymbolResolver:
    """Resolves relative and imported symbol targets to canonical symbol_ids."""

    def __init__(self, alias_resolver: Optional[AliasResolver] = None) -> None:
        self.aliases = alias_resolver or AliasResolver()
        # symbol_id -> SymbolNode
        self.symbols_by_id: Dict[str, SymbolNode] = {}
        # file_id -> {qualified_name: symbol_id}
        self.symbols_by_file_and_name: Dict[str, Dict[str, str]] = {}
        # file_id -> SymbolNode (module symbol)
        self.module_symbols: Dict[str, SymbolNode] = {}
        # module_path/name -> file_id (e.g. "agents.task" -> "agents/task.py")
        self.module_to_file: Dict[str, str] = {}
        # barrel_file -> {exported_name: target_symbol_id}
        self.barrel_reexports: Dict[str, Dict[str, str]] = {}

    def index_symbols(self, symbols: List[SymbolNode]) -> None:
        """Register all defined symbols for cross-module lookup."""
        for sym in symbols:
            self.symbols_by_id[sym.symbol_id] = sym
            norm_file = sym.file_id.replace("\\", "/")

            if norm_file not in self.symbols_by_file_and_name:
                self.symbols_by_file_and_name[norm_file] = {}
            self.symbols_by_file_and_name[norm_file][sym.qualified_name] = sym.symbol_id
            self.symbols_by_file_and_name[norm_file][sym.name] = sym.symbol_id

            # Register module mappings
            base = os.path.basename(norm_file)
            name_no_ext = os.path.splitext(base)[0]
            rel_no_ext = os.path.splitext(norm_file)[0]
            dotted = rel_no_ext.replace("/", ".")

            self.module_to_file[norm_file] = norm_file
            self.module_to_file[rel_no_ext] = norm_file
            self.module_to_file[dotted] = norm_file
            self.module_to_file[name_no_ext] = norm_file

            # Also register alias if provenance has alias information
            if sym.provenance.get("alias") and sym.provenance.get("original_name"):
                self.aliases.register_alias(norm_file, sym.name, sym.provenance["original_name"])

    def register_barrel_reexport(self, barrel_file: str, export_name: str, target_symbol_id: str) -> None:
        """Register a resolved re-export from a barrel file."""
        norm_file = barrel_file.replace("\\", "/")
        if norm_file not in self.barrel_reexports:
            self.barrel_reexports[norm_file] = {}
        self.barrel_reexports[norm_file][export_name] = target_symbol_id

    def resolve_target(self, source_file: str, target_ref: str) -> Optional[str]:
        """Resolve a raw target reference (e.g. 'helper', './utils::format', 'math.sqrt') to canonical symbol_id."""
        norm_source = source_file.replace("\\", "/")

        # 1. Exact match in registered symbol IDs
        if target_ref in self.symbols_by_id:
            return target_ref

        # 2. Check local alias
        resolved_name = self.aliases.resolve_alias(norm_source, target_ref)
        if resolved_name != target_ref and resolved_name in self.symbols_by_id:
            return resolved_name

        # 3. Local file symbol match
        local_symbols = self.symbols_by_file_and_name.get(norm_source, {})
        if target_ref in local_symbols:
            return local_symbols[target_ref]
        if resolved_name in local_symbols:
            return local_symbols[resolved_name]

        # 4. Target contains module separator '::' (e.g. './utils::format' or 'agents.runner::run')
        if "::" in target_ref:
            mod_part, sym_part = target_ref.split("::", 1)
            target_file = self._resolve_module_path(norm_source, mod_part)
            if target_file:
                # Check barrel re-exports first
                if target_file in self.barrel_reexports and sym_part in self.barrel_reexports[target_file]:
                    return self.barrel_reexports[target_file][sym_part]

                file_syms = self.symbols_by_file_and_name.get(target_file, {})
                if sym_part in file_syms:
                    return file_syms[sym_part]
                # Default export or wildcard
                if sym_part == "default" or sym_part == "*":
                    return f"{target_file}::{sym_part}"
                return f"{target_file}::{sym_part}"

        # 5. Relative path lookup without '::'
        target_file = self._resolve_module_path(norm_source, target_ref)
        if target_file:
            return f"{target_file}::MODULE"

        return None

    def _resolve_module_path(self, source_file: str, module_spec: str) -> Optional[str]:
        """Resolve a relative or absolute module specifier to a concrete file path."""
        norm_spec = module_spec.replace("\\", "/")
        source_dir = os.path.dirname(source_file)

        # Handle relative imports: './sub', '../common', '.'
        if norm_spec.startswith("."):
            joined = os.path.normpath(os.path.join(source_dir, norm_spec)).replace("\\", "/")
            candidates = [
                joined,
                f"{joined}.py",
                f"{joined}.ts",
                f"{joined}.tsx",
                f"{joined}.js",
                f"{joined}/__init__.py",
                f"{joined}/index.ts",
                f"{joined}/index.js",
            ]
            for cand in candidates:
                if cand in self.module_to_file:
                    return self.module_to_file[cand]
                if cand in self.symbols_by_file_and_name:
                    return cand

        # Dotted or direct module name
        if norm_spec in self.module_to_file:
            return self.module_to_file[norm_spec]

        dotted = norm_spec.replace(".", "/")
        candidates = [
            dotted,
            f"{dotted}.py",
            f"{dotted}.ts",
            f"{dotted}/__init__.py",
            f"{dotted}/index.ts",
        ]
        for cand in candidates:
            if cand in self.module_to_file:
                return self.module_to_file[cand]

        return None

    def resolve_edges(self, edges: List[SymbolEdge]) -> List[SymbolEdge]:
        """Resolve all edge targets in-place or return updated edges."""
        resolved_edges: List[SymbolEdge] = []
        for edge in edges:
            src_file = edge.source_symbol.split("::")[0] if "::" in edge.source_symbol else ""
            canonical_target = self.resolve_target(src_file, edge.target_symbol)

            if canonical_target and canonical_target != edge.target_symbol:
                edge.provenance["original_target"] = edge.target_symbol
                edge.target_symbol = canonical_target
                resolved_edges.append(edge)
            else:
                resolved_edges.append(edge)

        return resolved_edges
