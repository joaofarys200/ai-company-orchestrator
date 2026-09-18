"""
JARVIS OS — Phase 64: Autonomous Architecture Evolution & Design Governance
Module: index.py
Inverted index structures providing O(1) average key lookup with O(k) candidate enumeration.

Complexity:
    Average key lookup: O(1)
    Candidate enumeration for k items: O(k)
"""

from __future__ import annotations

from typing import Dict, List, Set

from .models import ArchitectureAlternative, ArchitectureProblem


class ArchitectureIndex:
    """Inverted indexes over problems and alternatives."""

    def __init__(self):
        self._by_category: Dict[str, Set[str]] = {}
        self._by_severity: Dict[str, Set[str]] = {}
        self._by_node: Dict[str, Set[str]] = {}
        self._by_alternative_type: Dict[str, Set[str]] = {}
        self._problems: Dict[str, ArchitectureProblem] = {}
        self._alternatives: Dict[str, ArchitectureAlternative] = {}

    def index_problem(self, problem: ArchitectureProblem) -> None:
        p_id = problem.problem_id
        self._problems[p_id] = problem

        cat = problem.category.value
        self._by_category.setdefault(cat, set()).add(p_id)

        sev = problem.severity.value
        self._by_severity.setdefault(sev, set()).add(p_id)

        for node in problem.affected_nodes:
            self._by_node.setdefault(node, set()).add(p_id)

    def index_alternative(self, alternative: ArchitectureAlternative) -> None:
        alt_id = alternative.alternative_id
        self._alternatives[alt_id] = alternative

        alt_type = alternative.alternative_type.value
        self._by_alternative_type.setdefault(alt_type, set()).add(alt_id)

    def query_problems_by_category(self, category: str) -> List[ArchitectureProblem]:
        ids = self._by_category.get(category.upper(), set())
        return [self._problems[pid] for pid in ids if pid in self._problems]

    def query_problems_by_severity(self, severity: str) -> List[ArchitectureProblem]:
        ids = self._by_severity.get(severity.upper(), set())
        return [self._problems[pid] for pid in ids if pid in self._problems]

    def query_problems_by_node(self, node: str) -> List[ArchitectureProblem]:
        ids = self._by_node.get(node, set())
        return [self._problems[pid] for pid in ids if pid in self._problems]

    def query_alternatives_by_type(self, alt_type: str) -> List[ArchitectureAlternative]:
        ids = self._by_alternative_type.get(alt_type.lower(), set())
        return [self._alternatives[aid] for aid in ids if aid in self._alternatives]

    def size(self) -> int:
        return len(self._problems) + len(self._alternatives)
