"""
JARVIS OS — Phase 69: Autonomous Quality Debt Remediation
Content-addressed remediation cache.
Cache key: debt_hash + quality_snapshot_hash + policy + architecture_hash + verification_version.
Explicit rule: A cache hit is NEVER considered new empirical evidence.
"""

from __future__ import annotations

import hashlib
import time
from typing import Any, Dict, Optional


class RemediationCache:
    """
    Caches expensive root-cause and impact analysis results.
    Explicitly tags retrieved entries to prevent mistaking cache hits for new empirical evidence.
    """

    def __init__(self):
        self._store: Dict[str, Dict[str, Any]] = {}
        self._stats = {"hits": 0, "misses": 0, "invalidations": 0}

    def generate_cache_key(
        self,
        debt_hash: str,
        quality_snapshot_hash: str,
        policy: str,
        architecture_hash: str,
        verification_version: str,
    ) -> str:
        composite = f"{debt_hash}:{quality_snapshot_hash}:{policy}:{architecture_hash}:{verification_version}"
        return hashlib.sha256(composite.encode("utf-8")).hexdigest()

    def get(self, key: str) -> Optional[Dict[str, Any]]:
        entry = self._store.get(key)
        if entry is not None:
            self._stats["hits"] += 1
            # Mark that this is a cached result, not fresh evidence
            cached_copy = dict(entry["data"])
            cached_copy["__is_cached_hit__"] = True
            cached_copy["__is_fresh_evidence__"] = False
            return cached_copy
        self._stats["misses"] += 1
        return None

    def put(self, key: str, data: Dict[str, Any], ttl_seconds: float = 3600.0) -> None:
        self._store[key] = {
            "data": data,
            "stored_at": time.time(),
            "expires_at": time.time() + ttl_seconds,
        }

    def invalidate(self, reason: str = "State mutation") -> int:
        count = len(self._store)
        self._store.clear()
        self._stats["invalidations"] += count
        return count

    def get_stats(self) -> Dict[str, int]:
        return dict(self._stats)
