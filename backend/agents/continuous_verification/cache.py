"""
JARVIS OS — Phase 62: Continuous Verification & Autonomous Regression Governance
Module: cache.py
Deterministic Verification Cache keyed by:
change_hash + verification_scope + test_hash + baseline_hash.
Invariant: A cache hit is NEVER considered fresh/new evidence.
Invalidates when source, test, contract, baseline, environment, or policy changes.
"""

from __future__ import annotations

import hashlib
import json
import time
from typing import Any, Dict, Optional, Tuple

from .models import VerificationDecision


class VerificationCache:
    """
    Deterministic cache for verification decisions.
    Keys incorporate:
    change_hash + verification_scope + test_hash + baseline_hash + policy + env.
    """

    def __init__(self) -> None:
        self._entries: Dict[str, Dict[str, Any]] = {}
        self.hits: int = 0
        self.misses: int = 0

    def compute_cache_key(
        self,
        change_hash: str,
        verification_scope: str,
        test_hash: str,
        baseline_hash: str,
        policy_name: str = "STANDARD",
        env_metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        env_str = json.dumps(env_metadata or {}, sort_keys=True)
        raw = f"{change_hash}|{verification_scope}|{test_hash}|{baseline_hash}|{policy_name}|{env_str}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def get(self, key: str) -> Optional[VerificationDecision]:
        entry = self._entries.get(key)
        if entry is None:
            self.misses += 1
            return None

        self.hits += 1
        decision = entry["decision"]
        return decision

    def put(self, key: str, decision: VerificationDecision) -> None:
        self._entries[key] = {
            "decision": decision,
            "cached_at": time.time(),
        }

    def invalidate_all(self, reason: str = "") -> int:
        count = len(self._entries)
        self._entries.clear()
        return count

    def invalidate_matching(self, substring: str) -> int:
        keys_to_del = [k for k in self._entries if substring in k]
        for k in keys_to_del:
            del self._entries[k]
        return len(keys_to_del)

    @property
    def hit_rate(self) -> float:
        total = self.hits + self.misses
        return round(self.hits / total, 4) if total > 0 else 0.0
