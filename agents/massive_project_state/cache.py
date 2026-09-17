from __future__ import annotations

import collections
import time
from typing import Any, Dict, List, Optional, Tuple


class CacheEntry:
    def __init__(self, key: str, value: Any, size: int = 1, state_hash: str = "", schema_version: str = "1.0.0") -> None:
        self.key = key
        self.value = value
        self.size = size
        self.state_hash = state_hash
        self.schema_version = schema_version
        self.last_access = time.time()


class DeterministicLRUCache:
    """Bounded, thread-safe LRU cache with deterministic eviction and hit/miss metrics."""

    def __init__(self, max_entries: int = 1000, max_bytes: int = 64 * 1024 * 1024) -> None:
        self.max_entries = max_entries
        self.max_bytes = max_bytes
        self._entries: collections.OrderedDict[str, CacheEntry] = collections.OrderedDict()
        self._current_bytes = 0

        self.hits = 0
        self.misses = 0
        self.evictions = 0

    def get(self, key: str) -> Optional[Any]:
        if key not in self._entries:
            self.misses += 1
            return None

        entry = self._entries[key]
        entry.last_access = time.time()
        self._entries.move_to_end(key)
        self.hits += 1
        return entry.value

    def put(
        self,
        key: str,
        value: Any,
        size: int = 1,
        state_hash: str = "",
        schema_version: str = "1.0.0",
    ) -> Optional[str]:
        evicted_key: Optional[str] = None

        if key in self._entries:
            old_entry = self._entries.pop(key)
            self._current_bytes -= old_entry.size

        # Evict until within entry limit and byte limit
        while len(self._entries) >= self.max_entries or (self._current_bytes + size > self.max_bytes and self._entries):
            oldest_key, oldest_entry = self._entries.popitem(last=False)
            self._current_bytes -= oldest_entry.size
            self.evictions += 1
            if evicted_key is None:
                evicted_key = oldest_key

        entry = CacheEntry(key, value, size=size, state_hash=state_hash, schema_version=schema_version)
        self._entries[key] = entry
        self._current_bytes += size
        return evicted_key

    def invalidate(self, key: str) -> bool:
        if key in self._entries:
            entry = self._entries.pop(key)
            self._current_bytes -= entry.size
            return True
        return False

    def invalidate_by_hash(self, state_hash: str) -> int:
        keys_to_remove = [k for k, e in self._entries.items() if e.state_hash == state_hash]
        for k in keys_to_remove:
            self.invalidate(k)
        return len(keys_to_remove)

    def clear(self) -> None:
        self._entries.clear()
        self._current_bytes = 0

    def get_stats(self) -> Dict[str, Any]:
        total = self.hits + self.misses
        hit_ratio = (self.hits / total) if total > 0 else 0.0
        return {
            "entries": len(self._entries),
            "max_entries": self.max_entries,
            "bytes_used": self._current_bytes,
            "max_bytes": self.max_bytes,
            "hits": self.hits,
            "misses": self.misses,
            "evictions": self.evictions,
            "hit_ratio": round(hit_ratio, 4),
        }
