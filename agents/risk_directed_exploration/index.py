"""
JARVIS OS — Phase 52: Risk-Directed Behavioral Exploration & Adaptive Proof Search
Risk Exploration Index: Central repository for risk scores, rankings, graph, and proofs.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from agents.risk_directed_exploration.models import (
    AdaptiveProofResult,
    BehavioralExplorationRisk,
    BehavioralUncertainty,
    ScenarioGraph,
    ScenarioRanking,
)


class RiskExplorationIndex:
    """
    Unified registry and query repository for Phase 52 artifacts.
    """

    def __init__(self) -> None:
        self._risks: Dict[str, BehavioralExplorationRisk] = {}
        self._uncertainties: Dict[str, BehavioralUncertainty] = {}
        self._rankings: Dict[str, List[ScenarioRanking]] = {}
        self._proofs: Dict[str, AdaptiveProofResult] = {}
        self.graph = ScenarioGraph()

    def register_risk(self, contract_id: str, risk: BehavioralExplorationRisk) -> None:
        self._risks[contract_id] = risk

    def register_uncertainty(self, contract_id: str, uncertainty: BehavioralUncertainty) -> None:
        self._uncertainties[contract_id] = uncertainty

    def register_rankings(self, contract_id: str, rankings: List[ScenarioRanking]) -> None:
        self._rankings[contract_id] = rankings

    def register_proof(self, proof: AdaptiveProofResult) -> None:
        self._proofs[proof.proof_id] = proof

    def get_proof(self, proof_id: str) -> Optional[AdaptiveProofResult]:
        return self._proofs.get(proof_id)

    def get_rankings(self, contract_id: str) -> Optional[List[ScenarioRanking]]:
        return self._rankings.get(contract_id)

    def get_risk(self, contract_id: str) -> Optional[BehavioralExplorationRisk]:
        return self._risks.get(contract_id)

    def list_proofs(self) -> List[AdaptiveProofResult]:
        return list(self._proofs.values())

    def clear(self) -> None:
        self._risks.clear()
        self._uncertainties.clear()
        self._rankings.clear()
        self._proofs.clear()
        self.graph = ScenarioGraph()
