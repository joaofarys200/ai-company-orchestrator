from __future__ import annotations

import hashlib
import time
from collections import OrderedDict
from typing import Any, Dict, Optional, Tuple


class SymbolGraphCache:
    """Multi-level LRU cache for symbol extractions, SCC calculations, and impact queries."""

    GRAPH_VERSION = "phase60_v1"
    SCC_ALGORITHM_VERSION = "tarjan_iterative_v1"

    def __init__(self, max_entries: int = 10000) -> None:
        self.max_entries = max_entries
        self.cache: OrderedDict[str, Tuple[Any, float]] = OrderedDict()
        self.hits = 0
        self.misses = 0

    def make_key(
        self,
        repo_rev: str,
        file_hash: str,
        symbol_hash: str = "",
        query_type: str = "symbol",
    ) -> str:
        """Construct deterministic cache key according to Phase 60 specifications."""
        raw = (
            f"{repo_rev}:{file_hash}:{symbol_hash}:"
            f"{self.GRAPH_VERSION}:{self.SCC_ALGORITHM_VERSION}:{query_type}"
        )
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def get(self, key: str) -> Optional[Any]:
        """Retrieve value from cache and update LRU order."""
        if key in self.cache:
            val, _ = self.cache.pop(key)
            self.cache[key] = (val, time.time())
            self.hits += 1
            return val
        self.misses += 1
        return None

    def put(self, key: str, value: Any) -> None:
        """Store item in cache, evicting oldest entry if capacity is exceeded."""
        if key in self.cache:
            self.cache.pop(key)
        elif len(self.cache) >= self.max_entries:
            self.cache.popitem(last=False)
        self.cache[key] = (value, time.time())

    def invalidate_file(self, file_path: str) -> int:
        """Invalidate all cached keys mentioning file_path."""
        norm_file = file_path.replace("\\", "/")
        keys_to_remove = [k for k, (val, _) in self.cache.items() if isinstance(val, dict) and val.get("file_id") == norm_file]
        for k in keys_to_remove:
            self.cache.pop(k, None)
        return len(keys_to_remove)

    def clear(self) -> None:
        """Evict all items."""
        self.cache.clear()
        self.hits = 0
        self.misses = 0

    @property
    def hit_ratio(self) -> float:
        total = self.hits + self.misses
        return round(self.hits / total, 4) if total > 0 else 0.0
