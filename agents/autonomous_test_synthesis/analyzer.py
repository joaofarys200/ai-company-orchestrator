"""
JARVIS OS — Phase 61: Autonomous Test Synthesis & Coverage-Guided Validation
Module: analyzer.py
Coverage gap analyzer inspecting current test evidence and identifying blind spots.
Invariance: "no test" is NEVER treated as "safe".
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Set

from .models import (
    CoverageGapType,
    CoverageMetrics,
    TestRequirement,
    TestRequirementSource,
)


class CoverageGapAnalyzer:
    """
    Evaluates current test evidence across 8 dimensions and discovers untested blind spots.
    """

    def __init__(self) -> None:
        self._tested_symbols: Set[str] = set()
        self._tested_branches: Set[str] = set()
        self._tested_contracts: Set[str] = set()
        self._tested_consumers: Set[str] = set()
        self._tested_invariants: Set[str] = set()
        self._tested_browser_routes: Set[str] = set()
        self._tested_repair_paths: Set[str] = set()

    def record_test_execution(
        self,
        symbol_id: Optional[str] = None,
        branch_id: Optional[str] = None,
        contract_id: Optional[str] = None,
        consumer_id: Optional[str] = None,
        invariant: Optional[str] = None,
        browser_route: Optional[str] = None,
        repair_path: Optional[str] = None,
    ) -> None:
        """Register coverage feedback from an executed test."""
        if symbol_id:
            self._tested_symbols.add(symbol_id)
        if branch_id:
            self._tested_branches.add(branch_id)
        if contract_id:
            self._tested_contracts.add(contract_id)
        if consumer_id:
            self._tested_consumers.add(consumer_id)
        if invariant:
            self._tested_invariants.add(invariant)
        if browser_route:
            self._tested_browser_routes.add(browser_route)
        if repair_path:
            self._tested_repair_paths.add(repair_path)

    def analyze_gaps(
        self,
        requirements: List[TestRequirement],
    ) -> List[Dict[str, Any]]:
        """
        Identify unsatisfied requirements and categorize gaps.
        Returns detailed gap items for the synthesis planner.
        """
        gaps: List[Dict[str, Any]] = []

        for req in requirements:
            is_satisfied = False

            if req.coverage_gap == CoverageGapType.UNTESTED_SYMBOL:
                is_satisfied = req.symbol_id in self._tested_symbols
            elif req.coverage_gap == CoverageGapType.UNTESTED_CONSUMER:
                is_satisfied = req.consumer_id in self._tested_consumers if req.consumer_id else False
            elif req.coverage_gap == CoverageGapType.UNTESTED_CONTRACT_VARIANT:
                is_satisfied = req.contract_id in self._tested_contracts if req.contract_id else False
            elif req.coverage_gap == CoverageGapType.UNTESTED_INVARIANT:
                is_satisfied = req.invariant in self._tested_invariants
            elif req.coverage_gap == CoverageGapType.UNTESTED_BROWSER_FLOW:
                is_satisfied = req.invariant in self._tested_browser_routes
            elif req.coverage_gap == CoverageGapType.UNTESTED_REPAIR_PATH:
                is_satisfied = req.symbol_id in self._tested_repair_paths
            else:
                is_satisfied = req.symbol_id in self._tested_symbols

            if not is_satisfied:
                # Epistemic invariant: untreated requirement is high-risk uncertainty
                gaps.append(
                    {
                        "requirement_id": req.requirement_id,
                        "source": req.source.value,
                        "symbol_id": req.symbol_id,
                        "file_id": req.file_id,
                        "gap_type": req.coverage_gap.value if req.coverage_gap else "UNKNOWN_GAP",
                        "risk": req.risk,
                        "priority": req.priority,
                        "invariant": req.invariant,
                        "remedy_strategy": self._suggest_strategy(req),
                    }
                )

        return gaps

    def compute_metrics(
        self,
        total_symbols: int = 10,
        total_branches: int = 20,
        total_contracts: int = 5,
        total_consumers: int = 8,
        total_invariants: int = 12,
        total_routes: int = 4,
    ) -> CoverageMetrics:
        """Calculate normalized coverage ratios across 8 dimensions."""
        sym_cov = min(1.0, len(self._tested_symbols) / max(1, total_symbols))
        branch_cov = min(1.0, len(self._tested_branches) / max(1, total_branches))
        contract_cov = min(1.0, len(self._tested_contracts) / max(1, total_contracts))
        consumer_cov = min(1.0, len(self._tested_consumers) / max(1, total_consumers))
        inv_cov = min(1.0, len(self._tested_invariants) / max(1, total_invariants))
        browser_cov = min(1.0, len(self._tested_browser_routes) / max(1, total_routes))
        line_cov = min(1.0, (sym_cov + branch_cov) / 2.0)
        beh_cov = min(1.0, (contract_cov + inv_cov) / 2.0)

        return CoverageMetrics(
            line_cov=round(line_cov, 4),
            branch_cov=round(branch_cov, 4),
            symbol_cov=round(sym_cov, 4),
            contract_cov=round(contract_cov, 4),
            behavior_cov=round(beh_cov, 4),
            invariant_cov=round(inv_cov, 4),
            consumer_cov=round(consumer_cov, 4),
            browser_cov=round(browser_cov, 4),
        )

    def _suggest_strategy(self, req: TestRequirement) -> str:
        if req.source == TestRequirementSource.CONTRACT:
            return "CONTRACT_TEST_SYNTHESIS"
        elif req.source == TestRequirementSource.BEHAVIORAL_INVARIANT:
            return "BEHAVIORAL_TEST_SYNTHESIS"
        elif req.source == TestRequirementSource.ECONOMIC_POLICY:
            return "BEHAVIORAL_TEST_SYNTHESIS"
        elif req.source == TestRequirementSource.SECURITY_POLICY:
            return "ERROR_PATH_TEST_SYNTHESIS"
        elif req.source == TestRequirementSource.COUNTEREXAMPLE:
            return "REGRESSION_TEST_SYNTHESIS"
        elif req.scenario_type == "browser":
            return "BROWSER_TEST_SYNTHESIS"
        return "UNIT_TEST_SYNTHESIS"
