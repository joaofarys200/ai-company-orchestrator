"""
JARVIS OS — Phase 65: Safe Self-Modification & Transactional Architecture Implementation
Module: cache.py
Deterministic cache for preflight and static validation artifacts.
Invalidates when files, contracts, or policies change.
Cache hit does not constitute new runtime verification evidence.
"""

from __future__ import annotations

import hashlib
import time
from typing import Any, Dict, Optional, Tuple


class ModificationCache:
    """Hash-keyed cache for preflight baselines and static AST validations."""

    def __init__(self, ttl_sec: float = 3600.0):
        self.ttl_sec = ttl_sec
        self.entries: Dict[str, Dict[str, Any]] = {}

    def compute_key(self, snapshot_hash: str, patch_hash: str, policy_name: str) -> str:
        raw = f"{snapshot_hash}:{patch_hash}:{policy_name}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def get(self, key: str) -> Optional[Any]:
        entry = self.entries.get(key)
        if not entry:
            return None
        if time.time() - entry["timestamp"] > self.ttl_sec:
            del self.entries[key]
            return None
        return entry["value"]

    def put(self, key: str, value: Any, metadata: Optional[Dict[str, Any]] = None) -> None:
        self.entries[key] = {
            "value": value,
            "timestamp": time.time(),
            "metadata": metadata or {},
        }

    def invalidate(self, snapshot_hash_prefix: str) -> int:
        keys_to_del = [
            k for k, v in self.entries.items()
            if k.startswith(snapshot_hash_prefix)
            or v.get("metadata", {}).get("snapshot_hash", "").startswith(snapshot_hash_prefix)
        ]
        for k in keys_to_del:
            del self.entries[k]
        return len(keys_to_del)

    def size(self) -> int:
        return len(self.entries)
