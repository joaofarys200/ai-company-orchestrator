"""
JARVIS OS — Phase 61: Autonomous Test Synthesis & Coverage-Guided Validation
Module: index.py
Fast, constant-time reverse indexes for requirements, candidates, symbols, and contracts.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Set

from .models import TestCandidate, TestRequirement


class TestSynthesisIndex:
    """Reverse index manager for Phase 61."""

    def __init__(self) -> None:
        self.by_symbol: Dict[str, Set[str]] = {}
        self.by_requirement: Dict[str, Set[str]] = {}
        self.by_contract: Dict[str, Set[str]] = {}
        self.by_file: Dict[str, Set[str]] = {}
        self.candidates_by_target: Dict[str, List[str]] = {}

    def index_requirement(self, req: TestRequirement) -> None:
        self.by_symbol.setdefault(req.symbol_id, set()).add(req.requirement_id)
        self.by_file.setdefault(req.file_id, set()).add(req.requirement_id)
        if req.contract_id:
            self.by_contract.setdefault(req.contract_id, set()).add(req.requirement_id)

    def index_candidate(self, cand: TestCandidate) -> None:
        self.by_requirement.setdefault(cand.requirement_id, set()).add(cand.test_id)
        self.candidates_by_target.setdefault(cand.target, []).append(cand.test_id)

    def get_requirements_for_symbol(self, symbol_id: str) -> List[str]:
        return list(self.by_symbol.get(symbol_id, set()))

    def get_candidates_for_requirement(self, requirement_id: str) -> List[str]:
        return list(self.by_requirement.get(requirement_id, set()))

    def get_candidates_for_target(self, target: str) -> List[str]:
        return self.candidates_by_target.get(target, [])
