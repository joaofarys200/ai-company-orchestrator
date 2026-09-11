"""
JARVIS OS — Phase 39.1: TypeScript Incremental Dependency Cache
Manages SHA-256 content-hash caching, fine-grained invalidation (file change, deletion,
rename, tsconfig/package edit), and incremental blast radius tracking.
"""

from __future__ import annotations

import json
import os
import time
from typing import Any, Dict, List, Optional, Set, Tuple

from intelligence.typescript_dependency.models import TypeScriptDependencyIndex


class TypeScriptDependencyCache:
    """
    Incremental dependency cache with persistent disk backing and fast memory indexing.
    """

    DEFAULT_CACHE_DIR = ".jarvis"
    DEFAULT_CACHE_FILE = "ts_dependency_cache.json"

    def __init__(self, workspace_root: str, cache_file: Optional[str] = None) -> None:
        self.workspace_root = os.path.normpath(workspace_root).replace(os.sep, "/")
        self.cache_path = (
            cache_file
            if cache_file
            else os.path.join(self.workspace_root, self.DEFAULT_CACHE_DIR, self.DEFAULT_CACHE_FILE)
        )
        self._cache: Dict[str, TypeScriptDependencyIndex] = {}
        self._config_hashes: Dict[str, str] = {}
        self.stats = {
            "hits": 0,
            "misses": 0,
            "reparsed": 0,
            "reused": 0,
            "invalidations": 0,
        }
        self.load_from_disk()

    def __len__(self) -> int:
        return len(self._cache)

    def __contains__(self, item: str) -> bool:
        return item in self._cache

    def get(self, rel_path: str, current_hash: str) -> Optional[TypeScriptDependencyIndex]:
        """Returns the cached index if content_hash matches; otherwise returns None."""
        entry = self._cache.get(rel_path)
        if entry and entry.content_hash == current_hash:
            self.stats["hits"] += 1
            self.stats["reused"] += 1
            return entry
        self.stats["misses"] += 1
        return None

    def put(self, index: TypeScriptDependencyIndex) -> None:
        """Stores or updates a file dependency index in cache."""
        self._cache[index.file_path] = index
        self.stats["reparsed"] += 1

    def remove(self, rel_path: str) -> None:
        """Removes a deleted or renamed file from cache."""
        if rel_path in self._cache:
            del self._cache[rel_path]
            self.stats["invalidations"] += 1

    def invalidate_file(self, rel_path: str) -> Set[str]:
        """
        Invalidates a file and determines its direct and downstream consumers.
        Returns the set of affected files (blast radius).
        """
        self.remove(rel_path)
        affected = self.get_downstream_consumers(rel_path)
        return affected

    def invalidate_tsconfig(self, tsconfig_path: str) -> Set[str]:
        """Invalidates all files governed by a tsconfig."""
        norm_cfg = tsconfig_path.replace(os.sep, "/")
        cfg_dir = os.path.dirname(norm_cfg)
        invalidated = set()
        for f in list(self._cache.keys()):
            if not cfg_dir or f.startswith(cfg_dir + "/"):
                self.remove(f)
                invalidated.add(f)
        return invalidated

    def invalidate_package(self, package_path: str) -> Set[str]:
        """Invalidates all files governed by a package.json."""
        norm_pkg = package_path.replace(os.sep, "/")
        pkg_dir = os.path.dirname(norm_pkg)
        invalidated = set()
        for f in list(self._cache.keys()):
            if not pkg_dir or f.startswith(pkg_dir + "/"):
                self.remove(f)
                invalidated.add(f)
        return invalidated

    def invalidate_configs_if_changed(self, current_config_hashes: Dict[str, str]) -> bool:
        """
        Checks if tsconfig or package.json files changed; if so, invalidates resolved targets.
        """
        changed = False
        for cfg_path, h in current_config_hashes.items():
            if self._config_hashes.get(cfg_path) != h:
                changed = True
                self._config_hashes[cfg_path] = h

        if changed:
            self.stats["invalidations"] += len(self._cache)
            # Re-verify resolved targets across all cached files
            for entry in self._cache.values():
                entry.resolved_targets.clear()
                entry.unresolved_imports.clear()
        return changed

    def get_direct_consumers(self, target_file: str) -> Set[str]:
        """Returns files that directly import target_file."""
        norm_target = target_file.replace(os.sep, "/")
        consumers = set()
        for src, index in self._cache.items():
            if norm_target in index.resolved_targets:
                consumers.add(src)
        return consumers

    def get_downstream_consumers(self, target_file: str) -> Set[str]:
        """Recursively traverses reverse dependency edges to find all downstream consumers."""
        visited = set()
        queue = [target_file.replace(os.sep, "/")]

        while queue:
            curr = queue.pop(0)
            direct = self.get_direct_consumers(curr)
            for d in direct:
                if d not in visited and d != target_file:
                    visited.add(d)
                    queue.append(d)
        return visited

    def all_entries(self) -> List[TypeScriptDependencyIndex]:
        """Returns all currently indexed file entries."""
        return list(self._cache.values())

    def clear(self) -> None:
        """Clears cache completely."""
        self._cache.clear()
        self._config_hashes.clear()
        self.stats = {"hits": 0, "misses": 0, "reparsed": 0, "reused": 0, "invalidations": 0}

    def save_to_disk(self) -> None:
        """Persists the cache to disk."""
        try:
            os.makedirs(os.path.dirname(self.cache_path), exist_ok=True)
            data = {
                "version": "39.1.0",
                "saved_at": time.time(),
                "config_hashes": self._config_hashes,
                "entries": {k: v.to_dict() for k, v in self._cache.items()},
            }
            with open(self.cache_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except OSError:
            pass

    def load_from_disk(self) -> None:
        """Loads cached index from disk if available."""
        if not os.path.isfile(self.cache_path):
            return
        try:
            with open(self.cache_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._config_hashes = data.get("config_hashes", {})
            entries = data.get("entries", {})
            for k, v in entries.items():
                self._cache[k] = TypeScriptDependencyIndex.from_dict(v)
        except (OSError, json.JSONDecodeError):
            self._cache.clear()

    @property
    def hit_rate(self) -> float:
        total = self.stats["hits"] + self.stats["misses"]
        return round(self.stats["hits"] / total, 4) if total > 0 else 0.0
