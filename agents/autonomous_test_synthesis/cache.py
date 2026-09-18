"""
JARVIS OS — Phase 61: Autonomous Test Synthesis & Coverage-Guided Validation
Module: cache.py
Multi-level deterministic test generation and execution result cache with LRU eviction.
"""

from __future__ import annotations

import collections
import hashlib
from typing import Any, Dict, Optional


class TestSynthesisCache:
    """Caches test candidates and execution outcomes using deterministic compound keys."""

    def __init__(self, max_entries: int = 1000) -> None:
        self.max_entries = max_entries
        self._cache: collections.OrderedDict[str, Any] = collections.OrderedDict()
        self.hits: int = 0
        self.misses: int = 0

    def get(self, key: str) -> Optional[Any]:
        if key in self._cache:
            self.hits += 1
            self._cache.move_to_end(key)
            return self._cache[key]
        self.misses += 1
        return None

    def put(self, key: str, value: Any) -> None:
        if key in self._cache:
            self._cache.move_to_end(key)
        self._cache[key] = value
        if len(self._cache) > self.max_entries:
            self._cache.popitem(last=False)

    def invalidate_symbol(self, symbol_id: str) -> int:
        to_del = [k for k in self._cache if symbol_id in k]
        for k in to_del:
            del self._cache[k]
        return len(to_del)

    def compute_compound_key(self, symbol_id: str, file_hash: str, requirement_id: str) -> str:
        payload = f"{symbol_id}::{file_hash}::{requirement_id}"
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    @property
    def hit_ratio(self) -> float:
        total = self.hits + self.misses
        return round(self.hits / total, 4) if total > 0 else 0.0
