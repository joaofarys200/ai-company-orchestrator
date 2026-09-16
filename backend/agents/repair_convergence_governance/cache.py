"""
JARVIS OS — Phase 56: Convergence Cache
Deterministic in-memory cache for state fingerprints, detector results, and verification hashes.
"""

from __future__ import annotations

from typing import Dict, Any, Optional


class ConvergenceCache:
    """Provides fast deterministic lookup for evaluated state snapshots and detector results."""

    def __init__(self, max_entries: int = 500):
        self.max_entries = max_entries
        self.cache_entries: Dict[str, Any] = {}

    def get(self, key: str) -> Optional[Any]:
        return self.cache_entries.get(key)

    def put(self, key: str, value: Any) -> None:
        if len(self.cache_entries) >= self.max_entries:
            # Simple eviction of oldest item
            first_key = next(iter(self.cache_entries))
            del self.cache_entries[first_key]
        self.cache_entries[key] = value

    def clear(self) -> None:
        self.cache_entries.clear()
