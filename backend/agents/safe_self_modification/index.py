"""
JARVIS OS — Phase 65: Safe Self-Modification & Transactional Architecture Implementation
Module: index.py
Fast-lookup indices mapping transactions, snapshots, checkpoints, and modified files.
"""

from __future__ import annotations

from typing import Dict, List, Set


class ModificationIndex:
    """In-memory index for rapid retrieval of transactional assets."""

    def __init__(self):
        self.tx_by_decision: Dict[str, str] = {}  # decision_id -> tx_id
        self.tx_by_file: Dict[str, Set[str]] = {}  # file_path -> set of tx_ids
        self.checkpoints_by_tx: Dict[str, List[str]] = {}  # tx_id -> list of cp_ids

    def register_transaction(self, tx_id: str, decision_id: str, files: List[str]) -> None:
        self.tx_by_decision[decision_id] = tx_id
        for f in files:
            if f not in self.tx_by_file:
                self.tx_by_file[f] = set()
            self.tx_by_file[f].add(tx_id)

    def register_checkpoint(self, tx_id: str, cp_id: str) -> None:
        if tx_id not in self.checkpoints_by_tx:
            self.checkpoints_by_tx[tx_id] = []
        self.checkpoints_by_tx[tx_id].append(cp_id)

    def find_transactions_for_file(self, file_path: str) -> List[str]:
        return list(self.tx_by_file.get(file_path, set()))
