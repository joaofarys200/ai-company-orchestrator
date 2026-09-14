"""
JARVIS OS — Phase 49: Build Contract Cache
Deterministic caching layer with artifact hash and schema version invalidation.
"""

from __future__ import annotations

import hashlib
import time
from typing import Any, Dict, Optional, Tuple

from agents.build_contract_extraction.models import ExtractedContractBundle


class BuildContractCache:
    """
    Deterministic cache for build-extracted contract bundles.
    Cache key incorporates artifact content hash, extractor version, and schema version.
    """

    EXTRACTOR_VERSION: str = "49.1.0"

    def __init__(self) -> None:
        self._cache: dict[str, dict[str, Any]] = {}
        self.hits: int = 0
        self.misses: int = 0
        self.invalidations: int = 0

    def compute_cache_key(
        self,
        artifact_path: str,
        content_hash: str,
        schema_version: str = "1.0.0",
    ) -> str:
        """Computes a deterministic cache key."""
        raw = f"{artifact_path}:{content_hash}:{schema_version}:{self.EXTRACTOR_VERSION}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def get(
        self,
        artifact_path: str,
        content_hash: str,
        schema_version: str = "1.0.0",
    ) -> Optional[ExtractedContractBundle]:
        """Retrieves cached bundle if valid."""
        key = self.compute_cache_key(artifact_path, content_hash, schema_version)
        entry = self._cache.get(key)
        if entry:
            self.hits += 1
            return entry["bundle"]
        self.misses += 1
        return None

    def put(
        self,
        artifact_path: str,
        content_hash: str,
        bundle: ExtractedContractBundle,
        schema_version: str = "1.0.0",
    ) -> str:
        """Stores extracted contract bundle in cache."""
        key = self.compute_cache_key(artifact_path, content_hash, schema_version)
        self._cache[key] = {
            "bundle": bundle,
            "artifact_path": artifact_path,
            "content_hash": content_hash,
            "cached_at": time.time(),
        }
        return key

    def invalidate(self, artifact_path: str) -> int:
        """Invalidates all cached entries for a specific artifact path."""
        keys_to_del = [k for k, v in self._cache.items() if v["artifact_path"] == artifact_path]
        for k in keys_to_del:
            del self._cache[k]
        self.invalidations += len(keys_to_del)
        return len(keys_to_del)

    def invalidate_all(self) -> int:
        """Flushes the entire contract extraction cache."""
        count = len(self._cache)
        self._cache.clear()
        self.invalidations += count
        return count

    @property
    def hit_ratio(self) -> float:
        total = self.hits + self.misses
        return round(self.hits / total, 4) if total > 0 else 0.0

    def stats(self) -> dict[str, Any]:
        return {
            "entries_count": len(self._cache),
            "hits": self.hits,
            "misses": self.misses,
            "hit_ratio": self.hit_ratio,
            "invalidations": self.invalidations,
        }
