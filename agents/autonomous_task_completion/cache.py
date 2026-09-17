"""
JARVIS OS — Phase 57: Task Completion In-Memory Cache
Provides high-throughput caching for plan templates, task understandings, and intermediate proofs.
"""

from __future__ import annotations

import time
from typing import Any


class TaskCompletionCache:
    """In-memory LRU-like cache with TTL for mission evaluations and plans."""

    _store: dict[str, tuple[float, Any]] = {}
    DEFAULT_TTL: float = 300.0  # 5 minutes

    @classmethod
    def get(cls, key: str) -> Any | None:
        if key not in cls._store:
            return None
        ts, val = cls._store[key]
        if time.time() - ts > cls.DEFAULT_TTL:
            del cls._store[key]
            return None
        return val

    @classmethod
    def set(cls, key: str, value: Any, ttl: float | None = None) -> None:
        cls._store[key] = (time.time(), value)

    @classmethod
    def invalidate(cls, key: str) -> None:
        cls._store.pop(key, None)

    @classmethod
    def clear(cls) -> None:
        cls._store.clear()
