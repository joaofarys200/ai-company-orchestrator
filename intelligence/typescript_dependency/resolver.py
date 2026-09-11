"""
JARVIS OS — Phase 39.1: TypeScript Import & Path Resolver
Deterministic resolver for TypeScript & React imports, extensions, index barrels,
tsconfig path aliases (compilerOptions.paths/baseUrl), and package boundaries.
Normalizes all paths canonically on Windows.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from intelligence.tsconfig_resolver import (
    MonorepoResolver,
    PackageJsonData,
    TSConfigData,
    TSConfigResolver,
)
from intelligence.typescript_dependency.models import (
    BoundaryType,
    ConfidenceClass,
    DependencyRelationType,
)


class TypeScriptImportResolver:
    """
    Deterministic path and symbol resolver for TypeScript & React applications.
    Ensures canonical path normalization on Windows and accurate barrel/alias resolution.
    """

    ALLOWED_EXTENSIONS = (
        ".ts",
        ".tsx",
        ".d.ts",
        ".js",
        ".jsx",
        ".mjs",
        ".cjs",
        ".json",
        ".css",
    )

    INDEX_BARRELS = (
        "/index.ts",
        "/index.tsx",
        "/index.d.ts",
        "/index.js",
        "/index.jsx",
    )

    def __init__(self, workspace_root: str) -> None:
        self.workspace_root = self.normalize_path(workspace_root)
        self.tsconfigs: Dict[str, TSConfigData] = {}
        self.packages: Dict[str, PackageJsonData] = {}
        self.known_files: Set[str] = set()
        self._load_configurations()

    @staticmethod
    def normalize_path(p: str) -> str:
        """Converts any path to a canonical normalized string with forward slashes."""
        if not p:
            return ""
        norm = os.path.normpath(p).replace(os.sep, "/")
        # Remove trailing slash unless root
        if len(norm) > 1 and norm.endswith("/"):
            norm = norm[:-1]
        return norm

    def set_known_files(self, files: Set[str]) -> None:
        """Sets the active universe of known workspace files (relative to workspace_root)."""
        self.known_files = {self.normalize_path(f) for f in files}

    def _load_configurations(self) -> None:
        """Loads tsconfig.json and package.json files from workspace."""
        for root, dirs, files in os.walk(self.workspace_root):
            # Ignore build/node_modules
            dirs[:] = [d for d in dirs if d not in (".git", "node_modules", "dist", ".next", "build", "venv")]
            for f in files:
                abs_file = os.path.join(root, f)
                rel_file = self.normalize_path(os.path.relpath(abs_file, self.workspace_root))
                lower = f.lower()

                if lower.startswith("tsconfig") and lower.endswith(".json"):
                    ts_data = TSConfigResolver.load_tsconfig(abs_file)
                    if ts_data:
                        self.tsconfigs[rel_file] = ts_data
                        # If tsconfig has references, load referenced configs too
                        for ref in ts_data.references:
                            ref_abs = os.path.normpath(os.path.join(os.path.dirname(abs_file), ref))
                            if not ref_abs.endswith(".json"):
                                ref_abs += "/tsconfig.json" if os.path.isdir(ref_abs) else ".json"
                            ref_rel = self.normalize_path(os.path.relpath(ref_abs, self.workspace_root))
                            if ref_rel not in self.tsconfigs and os.path.exists(ref_abs):
                                ref_data = TSConfigResolver.load_tsconfig(ref_abs)
                                if ref_data:
                                    self.tsconfigs[ref_rel] = ref_data

                elif lower == "package.json":
                    pkg_data = MonorepoResolver.load_package_json(abs_file)
                    if pkg_data:
                        self.packages[pkg_data.name] = pkg_data

    def resolve_import(
        self,
        source_file: str,
        module_specifier: str,
    ) -> Tuple[Optional[str], ConfidenceClass, BoundaryType]:
        """
        Resolves a module specifier from a source file into a canonical workspace relative path.
        Returns: (resolved_relative_path, confidence, boundary_type)
        """
        norm_source = self.normalize_path(source_file)
        source_dir = os.path.dirname(norm_source)

        if not module_specifier:
            return None, ConfidenceClass.UNCERTAIN, BoundaryType.INTRA_PACKAGE

        # 1. Relative Imports (./ or ../)
        if module_specifier.startswith("."):
            joined = self.normalize_path(os.path.join(source_dir, module_specifier))
            resolved = self.probe_file(joined)
            if resolved:
                return resolved, ConfidenceClass.DETERMINISTIC, BoundaryType.INTRA_PACKAGE
            return None, ConfidenceClass.UNCERTAIN, BoundaryType.INTRA_PACKAGE

        # 2. TSConfig Path Aliases & baseUrl
        # Look for tsconfig matching source_dir or root
        active_tsconfig = self._find_matching_tsconfig(norm_source)
        if active_tsconfig:
            resolved_alias = TSConfigResolver.resolve_alias_path(
                module_specifier,
                active_tsconfig,
                self.known_files,
                self.workspace_root,
            )
            if resolved_alias:
                return self.normalize_path(resolved_alias), ConfidenceClass.DETERMINISTIC, BoundaryType.INTRA_PACKAGE

        # Fallback: check all loaded tsconfigs for alias matches
        for ts_data in self.tsconfigs.values():
            resolved_alias = TSConfigResolver.resolve_alias_path(
                module_specifier,
                ts_data,
                self.known_files,
                self.workspace_root,
            )
            if resolved_alias:
                return self.normalize_path(resolved_alias), ConfidenceClass.DETERMINISTIC, BoundaryType.INTRA_PACKAGE

        # 3. Workspace Monorepo Package Imports (e.g. '@jarvis/common')
        if self.packages:
            resolved_pkg = MonorepoResolver.resolve_package_import(
                module_specifier,
                self.packages,
                self.known_files,
                self.workspace_root,
            )
            if resolved_pkg:
                return self.normalize_path(resolved_pkg), ConfidenceClass.DETERMINISTIC, BoundaryType.INTER_PACKAGE

        # 4. External NPM Packages (e.g. 'react', 'lucide-react', 'monaco-editor')
        return None, ConfidenceClass.DETERMINISTIC, BoundaryType.EXTERNAL_PACKAGE

    def probe_file(self, candidate_rel: str) -> Optional[str]:
        """
        Probes a relative candidate path for matching files or directory index barrels.
        Canonicalizes against self.known_files and disk.
        """
        norm = self.normalize_path(candidate_rel)

        # A. Check if already exact match in known_files
        if norm in self.known_files:
            return norm

        # Also check on disk if known_files is partial
        abs_cand = os.path.join(self.workspace_root, norm)
        if os.path.isfile(abs_cand):
            return norm

        # B. Probe direct file extensions
        for ext in self.ALLOWED_EXTENSIONS:
            with_ext = norm + ext
            if with_ext in self.known_files:
                return with_ext
            if os.path.isfile(os.path.join(self.workspace_root, with_ext)):
                return with_ext

        # C. Probe directory index barrels
        for barrel in self.INDEX_BARRELS:
            with_barrel = norm.rstrip("/") + barrel
            if with_barrel in self.known_files:
                return with_barrel
            if os.path.isfile(os.path.join(self.workspace_root, with_barrel)):
                return with_barrel

        return None

    def _find_matching_tsconfig(self, source_file: str) -> Optional[TSConfigData]:
        """Finds the most specific tsconfig for a given source file."""
        norm_source = self.normalize_path(source_file)
        best_match: Optional[TSConfigData] = None
        best_len = -1

        for rel_cfg, data in self.tsconfigs.items():
            cfg_dir = self.normalize_path(os.path.dirname(rel_cfg))
            if cfg_dir == "" or norm_source.startswith(cfg_dir + "/"):
                if len(cfg_dir) > best_len:
                    best_len = len(cfg_dir)
                    best_match = data

        return best_match
