"""
JARVIS OS — Phase 67: Long-Horizon Autonomous Engineering Missions
High-Performance State & Milestone Cache (LRU).
"""

from __future__ import annotations

from collections import OrderedDict
import time
from typing import Any, Dict, Optional


class MissionStateCache:
    """LRU cache with optional TTL for large DAG nodes and checkpoint lookups."""

    def __init__(self, max_size: int = 10000, default_ttl_sec: float = 3600.0):
        self.max_size = max_size
        self.default_ttl = default_ttl_sec
        self._cache: OrderedDict[str, Tuple[Any, float]] = OrderedDict()

    def get(self, key: str) -> Optional[Any]:
        if key not in self._cache:
            return None
        value, expires_at = self._cache[key]
        if time.time() > expires_at:
            del self._cache[key]
            return None
        self._cache.move_to_end(key)
        return value

    def set(self, key: str, value: Any, ttl_sec: Optional[float] = None) -> None:
        if key in self._cache:
            self._cache.move_to_end(key)
        elif len(self._cache) >= self.max_size:
            self._cache.popitem(last=False)
        ttl = ttl_sec if ttl_sec is not None else self.default_ttl
        self._cache[key] = (value, time.time() + ttl)

    def clear(self) -> None:
        self._cache.clear()

    def size(self) -> int:
        return len(self._cache)
