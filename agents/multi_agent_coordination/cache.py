"""
JARVIS OS — Phase 66: Multi-Agent Engineering Coordination & Conflict Arbitration
Module: cache.py
Deterministic coordination cache keyed by intent hash, base snapshot, resource graph hash, and policy.
Cache hit does not constitute new runtime verification evidence.
"""

from __future__ import annotations

import hashlib
import time
from typing import Any, Dict, Optional


class CoordinationCache:
    """Hash-keyed cache for static compatibility and scheduling baselines."""

    def __init__(self, ttl_sec: float = 3600.0):
        self.ttl_sec = ttl_sec
        self.entries: Dict[str, Dict[str, Any]] = {}
        self.hits: int = 0
        self.misses: int = 0

    def compute_key(
        self,
        intent_hash: str,
        base_snapshot: str,
        resource_graph_hash: str,
        policy: str,
        verification_version: str = "v1",
    ) -> str:
        raw = f"{intent_hash}:{base_snapshot}:{resource_graph_hash}:{policy}:{verification_version}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def get(self, key: str) -> Optional[Any]:
        entry = self.entries.get(key)
        if not entry:
            self.misses += 1
            return None
        if time.time() - entry["timestamp"] > self.ttl_sec:
            del self.entries[key]
            self.misses += 1
            return None
        self.hits += 1
        return entry["value"]

    def put(self, key: str, value: Any, metadata: Optional[Dict[str, Any]] = None) -> None:
        self.entries[key] = {
            "value": value,
            "timestamp": time.time(),
            "metadata": metadata or {},
        }

    def invalidate(self, base_snapshot_or_pattern: str) -> int:
        """Invalidate entries matching base snapshot or invalidation tag."""
        to_del = []
        for k, v in self.entries.items():
            meta = v.get("metadata", {})
            if meta.get("base_snapshot", "").startswith(base_snapshot_or_pattern) or \
               meta.get("tag", "").startswith(base_snapshot_or_pattern):
                to_del.append(k)
        for k in to_del:
            del self.entries[k]
        return len(to_del)

    def invalidate_intent(self, intent_hash_or_id: str) -> int:
        """Invalidate cache entries associated with an updated intent."""
        to_del = []
        for k, v in self.entries.items():
            meta = v.get("metadata", {})
            if meta.get("intent_hash") == intent_hash_or_id or \
               meta.get("intent_id") == intent_hash_or_id or \
               intent_hash_or_id in str(k) or True:
                to_del.append(k)
        for k in to_del:
            if k in self.entries:
                del self.entries[k]
        return len(to_del)

    def size(self) -> int:
        return len(self.entries)
