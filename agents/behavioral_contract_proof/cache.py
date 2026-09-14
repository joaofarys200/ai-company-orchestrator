"""
JARVIS OS — Phase 50: Behavioral Contract Preservation & Migration Proof
Deterministic Cache for Behavioral Comparison and Proofs.
"""

from __future__ import annotations

import hashlib
from typing import Any, Dict, Optional, Tuple

from agents.behavioral_contract_proof.models import MigrationProof


class BehaviorProofCache:
    """
    LRU / hash-based cache keyed by baseline_hash + target_hash + invariant_set_hash.
    """

    def __init__(self, max_size: int = 10000) -> None:
        self._cache: Dict[str, MigrationProof] = {}
        self._max_size = max_size
        self._hits = 0
        self._misses = 0

    @classmethod
    def make_key(cls, baseline_hash: str, target_hash: str, invariants: list) -> str:
        """Constructs deterministic composite key."""
        inv_str = ",".join(sorted(str(i) for i in invariants))
        raw = f"{baseline_hash}:{target_hash}:{inv_str}".encode("utf-8")
        return hashlib.sha256(raw).hexdigest()

    def get(self, key: str) -> Optional[MigrationProof]:
        """Retrieves cached proof."""
        if key in self._cache:
            self._hits += 1
            return self._cache[key]
        self._misses += 1
        return None

    def put(self, key: str, proof: MigrationProof) -> None:
        """Stores proof in cache."""
        if len(self._cache) >= self._max_size:
            # Pop first item
            first_key = next(iter(self._cache))
            del self._cache[first_key]
        self._cache[key] = proof

    @property
    def hit_ratio(self) -> float:
        total = self._hits + self._misses
        return round(self._hits / total, 4) if total > 0 else 0.0

    def stats(self) -> Dict[str, Any]:
        return {
            "size": len(self._cache),
            "hits": self._hits,
            "misses": self._misses,
            "hit_ratio": self.hit_ratio,
        }

    def clear(self) -> None:
        self._cache.clear()
        self._hits = 0
        self._misses = 0
