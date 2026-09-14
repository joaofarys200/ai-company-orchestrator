"""
JARVIS OS — Phase 51: Behavioral Proof Coverage & Scenario Exploration
Exploration Index: Unified Registry for Scenarios, Coverage Reports, Counterexamples, and Proofs.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from agents.behavioral_proof_exploration.models import (
    BehavioralCoverage,
    BehavioralScenario,
    BoundedExplorationProof,
    ProofResult,
    ProofScope,
    ShrunkCounterexample,
)


class ExplorationIndex:
    """
    Central storage and query repository for Phase 51 artifacts.
    """

    def __init__(self) -> None:
        self._scopes: Dict[str, ProofScope] = {}
        self._scenarios: Dict[str, BehavioralScenario] = {}
        self._coverages: Dict[str, BehavioralCoverage] = {}
        self._shrunk_cx: Dict[str, ShrunkCounterexample] = {}
        self._proofs: Dict[str, BoundedExplorationProof] = {}

    def register_scope(self, scope: ProofScope) -> None:
        self._scopes[scope.scope_id] = scope

    def register_scenario(self, scenario: BehavioralScenario) -> None:
        self._scenarios[scenario.scenario_id] = scenario

    def register_coverage(self, coverage: BehavioralCoverage) -> None:
        self._coverages[coverage.coverage_id] = coverage

    def register_shrunk_counterexample(self, cx: ShrunkCounterexample) -> None:
        self._shrunk_cx[cx.counterexample_id] = cx

    def register_proof(self, proof: BoundedExplorationProof) -> None:
        self._proofs[proof.proof_id] = proof

    def get_proof(self, proof_id: str) -> Optional[BoundedExplorationProof]:
        return self._proofs.get(proof_id)

    def get_coverage(self, coverage_id: str) -> Optional[BehavioralCoverage]:
        return self._coverages.get(coverage_id)

    def get_shrunk_counterexample(self, cx_id: str) -> Optional[ShrunkCounterexample]:
        return self._shrunk_cx.get(cx_id)

    def list_proofs(
        self,
        contract_id: Optional[str] = None,
        result: Optional[ProofResult] = None,
    ) -> List[BoundedExplorationProof]:
        proofs = list(self._proofs.values())
        if contract_id:
            proofs = [p for p in proofs if p.scope.contract_id == contract_id]
        if result:
            proofs = [p for p in proofs if p.result == result]
        return proofs

    def clear(self) -> None:
        self._scopes.clear()
        self._scenarios.clear()
        self._coverages.clear()
        self._shrunk_cx.clear()
        self._proofs.clear()
