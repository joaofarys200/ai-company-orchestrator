"""
JARVIS OS — Phase 52: Risk-Directed Behavioral Exploration & Adaptive Proof Search
Deterministic Ranking Cache ensuring reproducible scenario priorities.
"""

from __future__ import annotations

import copy
import json
from typing import Any, Dict, List, Optional

from agents.behavioral_proof_exploration.models import compute_deterministic_id
from agents.risk_directed_exploration.models import ScenarioRanking


class DeterministicRankingCache:
    """
    Guarantees that given identical contract input, policy, memory, and seed,
    the scenario priority ranking is 100% reproducible across executions.
    """

    def __init__(self) -> None:
        self._cache: Dict[str, List[Dict[str, Any]]] = {}

    def _make_key(
        self,
        contract_id: str,
        policy: str,
        seed: int,
        policy_version: str = "v1",
        risk_model_version: str = "v1",
    ) -> str:
        data = {
            "contract_id": contract_id,
            "policy": policy,
            "seed": seed,
            "policy_ver": policy_version,
            "risk_ver": risk_model_version,
        }
        return compute_deterministic_id(data, prefix="rank_cache_")

    def store_rankings(
        self,
        contract_id: str,
        policy: str,
        seed: int,
        rankings: List[ScenarioRanking],
    ) -> str:
        key = self._make_key(contract_id, policy, seed)
        self._cache[key] = [r.to_dict() for r in rankings]
        return key

    def get_rankings(
        self,
        contract_id: str,
        policy: str,
        seed: int,
    ) -> Optional[List[Dict[str, Any]]]:
        key = self._make_key(contract_id, policy, seed)
        cached = self._cache.get(key)
        return copy.deepcopy(cached) if cached else None
