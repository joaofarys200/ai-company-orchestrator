"""
JARVIS OS — Phase 51: Behavioral Proof Coverage & Scenario Exploration
Deterministic Replay Cache and Exploration Experience Storage.
"""

from __future__ import annotations

import copy
from typing import Any, Dict, List, Optional, Tuple

from agents.behavioral_proof_exploration.models import (
    BehavioralScenario,
    ScenarioExecutionResult,
    ShrunkCounterexample,
)


class ExplorationReplayCache:
    """
    Deterministic Replay Cache for Scenario Exploration.
    Stores and retrieves reproducible scenario execution records by seed and scenario ID.
    Experience Memory is treated as advisory: it never overrides current active proof exploration.
    """

    def __init__(self) -> None:
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._experiences: List[Dict[str, Any]] = []

    def _make_key(self, seed: int, scenario_id: str, build_hash: str) -> str:
        return f"{seed}:{scenario_id}:{build_hash}"

    def record_execution(
        self,
        scenario: BehavioralScenario,
        result: ScenarioExecutionResult,
        build_hash: str = "default_build_hash",
        shrunk_cx: Optional[ShrunkCounterexample] = None,
    ) -> None:
        """Store execution in replay cache."""
        key = self._make_key(scenario.seed, scenario.scenario_id, build_hash)
        self._cache[key] = {
            "scenario": copy.deepcopy(scenario.to_dict()),
            "result": copy.deepcopy(result.to_dict()),
            "shrunk_cx": copy.deepcopy(shrunk_cx.to_dict()) if shrunk_cx else None,
            "build_hash": build_hash,
        }

    def get_replay(
        self,
        seed: int,
        scenario_id: str,
        build_hash: str = "default_build_hash",
    ) -> Optional[Dict[str, Any]]:
        """Retrieve execution for deterministic replay."""
        key = self._make_key(seed, scenario_id, build_hash)
        return copy.deepcopy(self._cache.get(key))

    def record_experience(
        self,
        category: str,
        contract_id: str,
        details: Dict[str, Any],
    ) -> None:
        """Record an exploration experience (gap, counterexample, or success)."""
        self._experiences.append({
            "category": category,
            "contract_id": contract_id,
            "details": details,
            "advisory_only": True,
        })

    def list_experiences(self, contract_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """List experiences; explicitly advisory only."""
        if contract_id:
            return [e for e in self._experiences if e["contract_id"] == contract_id]
        return list(self._experiences)
