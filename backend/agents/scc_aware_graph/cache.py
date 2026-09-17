from __future__ import annotations

import collections
import time
from typing import Any, Dict, List, Optional


class SCCDeterministicCache:
    """Bounded, thread-safe LRU cache for deterministic SCC partitions and condensation DAGs."""

    def __init__(self, max_entries: int = 500) -> None:
        self.max_entries = max_entries
        self._entries: collections.OrderedDict[str, Any] = collections.OrderedDict()
        self.hits = 0
        self.misses = 0

    def get(self, key: str) -> Optional[Any]:
        if key not in self._entries:
            self.misses += 1
            return None
        self._entries.move_to_end(key)
        self.hits += 1
        return self._entries[key]

    def put(self, key: str, value: Any) -> None:
        if key in self._entries:
            self._entries.pop(key)
        while len(self._entries) >= self.max_entries:
            self._entries.popitem(last=False)
        self._entries[key] = value

    def invalidate(self, key: str) -> bool:
        if key in self._entries:
            del self._entries[key]
            return True
        return False

    def clear(self) -> None:
        self._entries.clear()

    def get_stats(self) -> Dict[str, Any]:
        total = self.hits + self.misses
        ratio = (self.hits / total) if total > 0 else 0.0
        return {
            "entries": len(self._entries),
            "hits": self.hits,
            "misses": self.misses,
            "hit_ratio": round(ratio, 4),
        }
