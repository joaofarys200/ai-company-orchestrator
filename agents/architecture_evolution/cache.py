"""
JARVIS OS — Phase 64: Autonomous Architecture Evolution & Design Governance
Module: cache.py
Deterministic multi-key cache for architectural evaluation results.

Rule:
    Cache key: snapshot_hash + problem_hash + constraint_hash + policy + knowledge_version.
    Cache hit never constitutes new local evidence.
"""

from __future__ import annotations

import hashlib
import json
import time
from typing import Any, Dict, Optional


class ArchitectureCache:
    """Provides deterministic caching for architectural evaluation stages."""

    def __init__(self, max_entries: int = 500):
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._max_entries = max_entries

    def compute_key(
        self,
        snapshot_hash: str,
        problem_hash: str,
        constraint_hash: str,
        policy: str,
        knowledge_version: str = "v1",
    ) -> str:
        raw = f"{snapshot_hash}:{problem_hash}:{constraint_hash}:{policy}:{knowledge_version}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def get(self, key: str) -> Optional[Dict[str, Any]]:
        entry = self._cache.get(key)
        if entry:
            entry["last_accessed"] = time.time()
            return entry.get("data")
        return None

    def put(
        self,
        key: str,
        data: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        if len(self._cache) >= self._max_entries:
            # Evict LRU
            oldest_key = min(self._cache.keys(), key=lambda k: self._cache[k].get("last_accessed", 0))
            del self._cache[oldest_key]

        self._cache[key] = {
            "data": data,
            "metadata": metadata or {},
            "created_at": time.time(),
            "last_accessed": time.time(),
        }

    def invalidate(self, pattern: str = "") -> int:
        """Invalidates entries matching a snapshot, problem, or policy pattern."""
        if not pattern:
            count = len(self._cache)
            self._cache.clear()
            return count

        keys_to_del = [
            k for k, v in self._cache.items()
            if pattern in str(v.get("metadata", {})) or pattern in k
        ]
        for k in keys_to_del:
            del self._cache[k]
        return len(keys_to_del)

    def size(self) -> int:
        return len(self._cache)
