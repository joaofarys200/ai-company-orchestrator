"""
Release Assessment Cache Module
Phase 70 — Autonomous Release Readiness & Production Governance

In-memory content-addressed cache for release evaluation results,
with invalidation hooks and cache hit/miss accounting.
"""

from __future__ import annotations
from typing import Dict, Any, Optional


class ReleaseReadinessCache:
    """Content-addressed cache storing evaluation decisions by artifact/commit digest."""

    def __init__(self):
        self._cache: Dict[str, Dict[str, Any]] = {}
        self.hits: int = 0
        self.misses: int = 0

    def get(self, cache_key: str) -> Optional[Dict[str, Any]]:
        """Retrieves cached evaluation entry if valid."""
        if cache_key in self._cache:
            self.hits += 1
            return self._cache[cache_key]
        self.misses += 1
        return None

    def put(self, cache_key: str, data: Dict[str, Any]) -> None:
        """Stores evaluation data in cache."""
        self._cache[cache_key] = data

    def invalidate(self, cache_key: Optional[str] = None) -> int:
        """Invalidates specific key or flushes entire cache."""
        if cache_key is not None:
            if cache_key in self._cache:
                del self._cache[cache_key]
                return 1
            return 0
        count = len(self._cache)
        self._cache.clear()
        return count

    def get_stats(self) -> Dict[str, Any]:
        """Returns cache telemetry."""
        total = self.hits + self.misses
        hit_rate = (self.hits / total) if total > 0 else 0.0
        return {
            "size": len(self._cache),
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate_pct": round(hit_rate * 100, 2)
        }
