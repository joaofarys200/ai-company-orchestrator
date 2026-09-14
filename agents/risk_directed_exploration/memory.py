"""
JARVIS OS — Phase 52: Risk-Directed Behavioral Exploration & Adaptive Proof Search
Experience Memory Bridge: Informs scenario prioritization with past failure experiences.
Strictly enforces 'Memory is not authority'.
"""

from __future__ import annotations

import copy
import time
from typing import Any, Dict, List, Optional

from agents.behavioral_proof_exploration.models import (
    BehavioralScenario,
    Counterexample,
)


class ExplorationMemoryBridge:
    """
    Bridge integrating Phase 42/43 Experience Memory into Risk-Directed Exploration.
    Uses historical failure patterns to bias initial scenario rankings towards high-risk edges.
    Enforces the invariant: 'Memory is not authority — memories never replace active proof verification.'
    """

    def __init__(self) -> None:
        self._memory_entries: List[Dict[str, Any]] = []

    def record_exploration_experience(
        self,
        contract_id: str,
        scenario: BehavioralScenario,
        risk_before: float,
        risk_after: float,
        coverage_delta: float,
        had_divergence: bool,
        counterexample: Optional[Counterexample] = None,
        policy: str = "STANDARD",
        decision: str = "GATE_CLEARED",
    ) -> None:
        """Store structured exploration experience."""
        self._memory_entries.append({
            "contract_id": contract_id,
            "scenario_id": scenario.scenario_id,
            "target": scenario.coverage_target,
            "risk_before": round(risk_before, 4),
            "risk_after": round(risk_after, 4),
            "coverage_delta": round(coverage_delta, 4),
            "had_divergence": had_divergence,
            "counterexample_id": counterexample.counterexample_id if counterexample else None,
            "policy": policy,
            "decision": decision,
            "timestamp": time.time(),
            "advisory_only": True,
        })

    def get_historical_failure_weight(self, contract_id: str, target: str) -> float:
        """
        Query past experiences to assign priority weight to scenarios targeting known weak spots.
        Returns weight multiplier in [0.0, 1.0].
        """
        matches = [
            e for e in self._memory_entries
            if e["contract_id"] == contract_id and target.lower() in e["target"].lower() and e["had_divergence"]
        ]
        if matches:
            return min(1.0, len(matches) * 0.35)
        return 0.1

    def list_experiences(self, contract_id: Optional[str] = None) -> List[Dict[str, Any]]:
        if contract_id:
            return [e for e in self._memory_entries if e["contract_id"] == contract_id]
        return list(self._memory_entries)
