"""
JARVIS OS — Phase 63: Cross-Project Engineering Learning & Verification Transfer
Module: cache.py
Deterministic transfer decision cache.
Keyed by source knowledge hash, target fingerprint, policy, and adapter version.
Cache hits never count as new verification evidence.
"""

from __future__ import annotations

import hashlib
import json
import time
from typing import Any, Dict, Optional

from .models import KnowledgeTransferDecision


class DeterministicTransferCache:
    """Caches transfer decisions deterministically to prevent redundant evaluations."""

    def __init__(self) -> None:
        self._store: Dict[str, Dict[str, Any]] = {}
        self._key_fingerprints: Dict[str, str] = {}
        self._hits: int = 0
        self._misses: int = 0

    @staticmethod
    def compute_cache_key(
        source_knowledge_hash: str,
        target_fingerprint_hash: str,
        policy_name: str,
        adapter_version: str = "v1.0",
    ) -> str:
        payload = f"{source_knowledge_hash}:{target_fingerprint_hash}:{policy_name}:{adapter_version}"
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def get(self, cache_key: str) -> Optional[KnowledgeTransferDecision]:
        entry = self._store.get(cache_key)
        if not entry:
            self._misses += 1
            return None

        # Check expiration
        if entry.get("expires_at") and entry["expires_at"] < time.time():
            self._store.pop(cache_key, None)
            self._misses += 1
            return None

        self._hits += 1
        decision_dict = entry["decision"]
        # Reconstruct decision
        dec = KnowledgeTransferDecision(
            decision_id=decision_dict["decision_id"],
            state=decision_dict["state"],
            target_project_id=decision_dict["target_project_id"],
            item_id=decision_dict["item_id"],
            category=decision_dict["category"],
            rationale=decision_dict["rationale"] + " [FROM_DETERMINISTIC_CACHE]",
            local_validation_plan=decision_dict.get("local_validation_plan", {}),
            requires_human_review=decision_dict.get("requires_human_review", False),
            confidence=decision_dict.get("confidence", 0.0),
            timestamp=decision_dict.get("timestamp", time.time()),
        )
        return dec

    def put(
        self,
        cache_key: str,
        decision: KnowledgeTransferDecision,
        target_fingerprint_hash: str = "",
        ttl_seconds: float = 3600.0,
    ) -> None:
        fp_hash = target_fingerprint_hash or self._key_fingerprints.get(cache_key, decision.target_project_id)
        self._store[cache_key] = {
            "decision": decision.to_dict(),
            "target_fingerprint_hash": fp_hash,
            "expires_at": time.time() + ttl_seconds,
            "cached_at": time.time(),
        }

    def invalidate(self, target_fingerprint_hash: Optional[str] = None) -> int:
        """Invalidate all or fingerprint-specific entries."""
        if not target_fingerprint_hash:
            count = len(self._store)
            self._store.clear()
            self._key_fingerprints.clear()
            return count

        to_del = [
            k for k, v in self._store.items()
            if self._key_fingerprints.get(k) == target_fingerprint_hash
            or target_fingerprint_hash in self._key_fingerprints.get(k, "")
            or v.get("target_fingerprint_hash") == target_fingerprint_hash
            or target_fingerprint_hash in k
            or target_fingerprint_hash in str(v.get("decision", {}).get("target_project_id", ""))
        ]
        for k in to_del:
            self._store.pop(k, None)
            self._key_fingerprints.pop(k, None)
        return len(to_del)

    @property
    def hit_rate(self) -> float:
        total = self._hits + self._misses
        return self._hits / total if total > 0 else 0.0
