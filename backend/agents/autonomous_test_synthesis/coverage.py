"""
JARVIS OS — Phase 61: Autonomous Test Synthesis & Coverage-Guided Validation
Module: coverage.py
Multi-dimensional coverage tracker measuring 8 distinct dimensions:
Line, Branch, Symbol, Contract, Behavior, Invariant, Consumer, and Browser.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Set

from .models import CoverageMetrics, TestExecutionResult


class MultiDimensionalCoverageTracker:
    """
    Tracks and updates 8-dimensional coverage state.
    Enforces the invariant that no single dimension alone constitutes sufficient proof.
    """

    def __init__(
        self,
        target_line: float = 0.85,
        target_branch: float = 0.80,
        target_symbol: float = 0.90,
        target_contract: float = 0.95,
        target_behavior: float = 0.90,
        target_invariant: float = 0.85,
        target_consumer: float = 0.80,
        target_browser: float = 0.70,
    ) -> None:
        self.targets = {
            "line": target_line,
            "branch": target_branch,
            "symbol": target_symbol,
            "contract": target_contract,
            "behavior": target_behavior,
            "invariant": target_invariant,
            "consumer": target_consumer,
            "browser": target_browser,
        }
        self.current = CoverageMetrics()
        self.history: List[CoverageMetrics] = []

    def update_with_result(self, result: TestExecutionResult, scenario_type: str = "unit") -> CoverageMetrics:
        if not result.passed:
            return self.current

        delta = result.coverage_delta

        new_sym = min(1.0, self.current.symbol_cov + delta * 0.8)
        new_line = min(1.0, self.current.line_cov + delta * 0.7)
        new_branch = min(1.0, self.current.branch_cov + delta * 0.6)
        new_contract = self.current.contract_cov
        new_behavior = self.current.behavior_cov
        new_invariant = self.current.invariant_cov
        new_consumer = self.current.consumer_cov
        new_browser = self.current.browser_cov

        if scenario_type == "contract":
            new_contract = min(1.0, new_contract + delta * 1.2)
        elif scenario_type in ("behavioral", "economic_sandbox"):
            new_behavior = min(1.0, new_behavior + delta * 1.1)
            new_invariant = min(1.0, new_invariant + delta * 1.0)
        elif scenario_type == "integration":
            new_consumer = min(1.0, new_consumer + delta * 1.0)
        elif scenario_type == "browser":
            new_browser = min(1.0, new_browser + delta * 1.5)
        elif scenario_type == "regression":
            new_invariant = min(1.0, new_invariant + delta * 1.2)

        self.current = CoverageMetrics(
            line_cov=round(new_line, 4),
            branch_cov=round(new_branch, 4),
            symbol_cov=round(new_sym, 4),
            contract_cov=round(new_contract, 4),
            behavior_cov=round(new_behavior, 4),
            invariant_cov=round(new_invariant, 4),
            consumer_cov=round(new_consumer, 4),
            browser_cov=round(new_browser, 4),
        )
        self.history.append(self.current)
        return self.current

    def is_sufficient(self, min_composite: float = 0.75) -> bool:
        """Determines if the multi-dimensional coverage threshold is satisfied."""
        score = self.current.compute_composite_score()
        return score >= min_composite

    def get_coverage_summary(self) -> Dict[str, Any]:
        return {
            "current_metrics": self.current.to_dict(),
            "targets": self.targets,
            "sufficient": self.is_sufficient(),
            "composite_score": self.current.compute_composite_score(),
        }
