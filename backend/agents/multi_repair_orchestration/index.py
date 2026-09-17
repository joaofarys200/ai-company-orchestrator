"""
JARVIS OS — Phase 55: Transactional Multi-Repair Orchestration & Convergence
Multi-Repair Ledger Index.
Maintains in-memory and persistent registries of failure clusters, repair graphs,
transactions, checkpoints, and proofs.
"""

from __future__ import annotations

from typing import Dict, List, Optional

from agents.multi_repair_orchestration.models import (
    FailureCluster,
    RepairCheckpoint,
    RepairGraph,
    RepairTransaction,
    TransactionProof,
)


class MultiRepairLedgerIndex:
    """
    Central repository index for multi-repair orchestration artifacts.
    """

    def __init__(self):
        self.clusters: Dict[str, FailureCluster] = {}
        self.graphs: Dict[str, RepairGraph] = {}
        self.transactions: Dict[str, RepairTransaction] = {}
        self.checkpoints: Dict[str, RepairCheckpoint] = {}
        self.proofs: Dict[str, TransactionProof] = {}

    def register_cluster(self, cluster: FailureCluster) -> None:
        self.clusters[cluster.cluster_id] = cluster

    def register_graph(self, cluster_id: str, graph: RepairGraph) -> None:
        self.graphs[cluster_id] = graph

    def register_transaction(self, transaction: RepairTransaction) -> None:
        self.transactions[transaction.transaction_id] = transaction
        for chk in transaction.checkpoints:
            self.checkpoints[chk.checkpoint_id] = chk
        if transaction.proof:
            self.proofs[transaction.proof.proof_id] = transaction.proof

    def get_transaction(self, tx_id: str) -> Optional[RepairTransaction]:
        return self.transactions.get(tx_id)

    def get_checkpoint(self, chk_id: str) -> Optional[RepairCheckpoint]:
        return self.checkpoints.get(chk_id)
