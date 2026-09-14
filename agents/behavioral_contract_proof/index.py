"""
JARVIS OS — Phase 50: Behavioral Contract Preservation & Migration Proof
O(1) Inverted Index for Behavioral Entities, Proofs, and Counterexamples.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, List, Optional, Set

from agents.behavioral_contract_proof.models import BehaviorBaseline, Counterexample, MigrationProof, RuntimeTrace


class BehavioralIndex:
    """
    High-performance O(1) inverted lookup index for baselines, traces, proofs, and counterexamples.
    """

    def __init__(self) -> None:
        self._baselines_by_contract: Dict[str, Set[str]] = defaultdict(set)
        self._baselines_by_consumer: Dict[str, Set[str]] = defaultdict(set)
        self._baselines_by_event: Dict[str, Set[str]] = defaultdict(set)

        self._proofs_by_contract: Dict[str, Set[str]] = defaultdict(set)
        self._proofs_by_consumer: Dict[str, Set[str]] = defaultdict(set)
        self._proofs_by_migration: Dict[str, MigrationProof] = {}

        self._counterexamples_by_consumer: Dict[str, List[Counterexample]] = defaultdict(list)
        self._counterexamples_by_contract: Dict[str, List[Counterexample]] = defaultdict(list)

    def index_baseline(self, baseline: BehaviorBaseline) -> None:
        """Indexes a baseline by contract, consumer, and event topics."""
        b_key = f"{baseline.contract_id}:{baseline.contract_version}:{baseline.consumer_id}"
        self._baselines_by_contract[baseline.contract_id].add(b_key)
        self._baselines_by_consumer[baseline.consumer_id].add(b_key)

        for ev in baseline.events:
            topic = ev.get("topic") or ev.get("name")
            if topic:
                self._baselines_by_event[topic].add(b_key)

    def index_proof(self, proof: MigrationProof, contract_id: str) -> None:
        """Indexes a migration proof."""
        self._proofs_by_migration[proof.migration_id] = proof
        self._proofs_by_contract[contract_id].add(proof.migration_id)
        for c in proof.consumers:
            self._proofs_by_consumer[c].add(proof.migration_id)

        for cex in proof.counterexamples:
            self._counterexamples_by_consumer[cex.consumer_id].append(cex)
            self._counterexamples_by_contract[cex.contract_id].append(cex)

    def get_proof(self, migration_id: str) -> Optional[MigrationProof]:
        """O(1) proof lookup."""
        return self._proofs_by_migration.get(migration_id)

    def get_counterexamples_for_consumer(self, consumer_id: str) -> List[Counterexample]:
        """O(1) counterexample lookup by consumer."""
        return list(self._counterexamples_by_consumer.get(consumer_id, []))

    def get_counterexamples_for_contract(self, contract_id: str) -> List[Counterexample]:
        """O(1) counterexample lookup by contract."""
        return list(self._counterexamples_by_contract.get(contract_id, []))

    def clear(self) -> None:
        """Resets the index."""
        self._baselines_by_contract.clear()
        self._baselines_by_consumer.clear()
        self._baselines_by_event.clear()
        self._proofs_by_contract.clear()
        self._proofs_by_consumer.clear()
        self._proofs_by_migration.clear()
        self._counterexamples_by_consumer.clear()
        self._counterexamples_by_contract.clear()
