"""
JARVIS OS — Phase 62: Continuous Verification & Autonomous Regression Governance
Module: index.py
Fast reverse lookup index mapping symbols, files, decisions, and change hashes.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Set
from .models import VerificationDecision


class VerificationIndex:
    """In-memory index supporting constant-time lookup across continuous verification artifacts."""

    def __init__(self) -> None:
        self.symbol_to_tests: Dict[str, Set[str]] = {}
        self.file_to_tests: Dict[str, Set[str]] = {}
        self.change_to_runs: Dict[str, List[str]] = {}
        self.decisions_by_id: Dict[str, VerificationDecision] = {}

    def index_test_mapping(self, test_id: str, file_path: Optional[str] = None, symbol_id: Optional[str] = None) -> None:
        if file_path:
            self.file_to_tests.setdefault(file_path, set()).add(test_id)
        if symbol_id:
            self.symbol_to_tests.setdefault(symbol_id, set()).add(test_id)

    def index_run(self, change_hash: str, run_id: str) -> None:
        self.change_to_runs.setdefault(change_hash, []).append(run_id)

    def index_decision(self, decision: VerificationDecision) -> None:
        self.decisions_by_id[decision.decision_id] = decision

    def find_tests_for_symbol(self, symbol_id: str) -> List[str]:
        return sorted(list(self.symbol_to_tests.get(symbol_id, set())))

    def find_tests_for_file(self, file_path: str) -> List[str]:
        return sorted(list(self.file_to_tests.get(file_path, set())))

    def get_runs_for_change(self, change_hash: str) -> List[str]:
        return self.change_to_runs.get(change_hash, [])

    def get_decision(self, decision_id: str) -> Optional[VerificationDecision]:
        return self.decisions_by_id.get(decision_id)
