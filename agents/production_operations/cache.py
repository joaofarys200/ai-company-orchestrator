"""
Phase 71 — Production Operations LRU Cache
Thread-safe LRU cache for observation queries and root cause diagnosis lookups.
"""

from __future__ import annotations

import collections
import threading
from typing import Any, Dict, Optional, Tuple


class OperationsCache:
    """Thread-safe LRU cache."""

    def __init__(self, capacity: int = 1000):
        self.capacity = capacity
        self._cache: collections.OrderedDict[str, Any] = collections.OrderedDict()
        self._lock = threading.Lock()
        self.hits = 0
        self.misses = 0

    def get(self, key: str) -> Optional[Any]:
        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
                self.hits += 1
                return self._cache[key]
            self.misses += 1
            return None

    def put(self, key: str, value: Any) -> None:
        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
            self._cache[key] = value
            if len(self._cache) > self.capacity:
                self._cache.popitem(last=False)

    def clear(self) -> None:
        with self._lock:
            self._cache.clear()
            self.hits = 0
            self.misses = 0

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            total = self.hits + self.misses
            rate = (self.hits / total) if total > 0 else 0.0
            return {
                "size": len(self._cache),
                "capacity": self.capacity,
                "hits": self.hits,
                "misses": self.misses,
                "hit_rate": round(rate, 4),
            }
