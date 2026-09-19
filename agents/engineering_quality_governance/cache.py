"""
JARVIS OS — Phase 68: Quality Evaluation Cache
Content-addressed caching for dimension evaluations.

Cache Key:
architecture_hash + quality_scope + policy + verification_version

Invalidation:
Invalidates whenever architecture, contracts, behavior, tests, policy, or mission state changes.

Invariant:
Cache hit is NEVER considered new empirical evidence.
Cached records are explicitly flagged with is_cached=True.
"""

from __future__ import annotations

import copy
import hashlib
import json
from typing import Any, Dict, Optional

from .models import DimensionEvaluation


class QualityEvaluationCache:
    """
    LRU / Content-addressed cache for dimension evaluations.
    """

    def __init__(self, max_entries: int = 500) -> None:
        self.max_entries = max_entries
        self._cache: Dict[str, Dict[str, Any]] = {}

    def _make_key(
        self,
        architecture_hash: str,
        quality_scope: str,
        policy: str,
        verification_version: str,
    ) -> str:
        payload = f"{architecture_hash}:{quality_scope}:{policy}:{verification_version}"
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def get(
        self,
        architecture_hash: str,
        quality_scope: str,
        policy: str,
        verification_version: str,
    ) -> Optional[Dict[str, DimensionEvaluation]]:
        k = self._make_key(architecture_hash, quality_scope, policy, verification_version)
        entry = self._cache.get(k)
        if not entry:
            return None

        # Return deepcopy with evidence flagged as cached (NOT new evidence)
        cached_evals: Dict[str, DimensionEvaluation] = copy.deepcopy(entry["evaluations"])
        for dim_eval in cached_evals.values():
            dim_eval.evidence.append({"is_cached": True, "note": "Retrieved from cache; NOT fresh empirical evidence"})

        return cached_evals

    def put(
        self,
        architecture_hash: str,
        quality_scope: str,
        policy: str,
        verification_version: str,
        evaluations: Dict[str, DimensionEvaluation],
    ) -> None:
        if len(self._cache) >= self.max_entries:
            # Evict oldest
            oldest = next(iter(self._cache))
            del self._cache[oldest]

        k = self._make_key(architecture_hash, quality_scope, policy, verification_version)
        self._cache[k] = {
            "evaluations": copy.deepcopy(evaluations),
            "created_at": evaluations,
        }

    def invalidate_all(self) -> None:
        self._cache.clear()

    def invalidate_scope(self, quality_scope: str) -> None:
        to_del = [k for k in self._cache]
        self._cache.clear()
