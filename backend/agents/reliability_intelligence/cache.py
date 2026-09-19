"""
Phase 72 — Reliability Cache
Thread-safe in-memory cache with TTL for baselines and risk scores.
"""

from __future__ import annotations

import time
from typing import Any, Dict, Optional


class ReliabilityCache:
    """Caches baseline calculations and risk scores with explicit TTL."""

    def __init__(self, default_ttl_seconds: float = 60.0):
        self.default_ttl = default_ttl_seconds
        self._store: Dict[str, tuple[Any, float]] = {}

    def get(self, key: str) -> Optional[Any]:
        if key not in self._store:
            return None
        val, expiry = self._store[key]
        if time.time() > expiry:
            del self._store[key]
            return None
        return val

    def set(self, key: str, value: Any, ttl: Optional[float] = None) -> None:
        expiry = time.time() + (ttl if ttl is not None else self.default_ttl)
        self._store[key] = (value, expiry)

    def invalidate(self, key: str) -> None:
        self._store.pop(key, None)

    def clear(self) -> None:
        self._store.clear()
