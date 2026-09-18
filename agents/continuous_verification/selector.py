"""
JARVIS OS — Phase 62: Continuous Verification & Autonomous Regression Governance
Module: selector.py
ContinuousTestSelector selecting existing tests prior to test synthesis, following the 8-level priority cascade.
"""

from __future__ import annotations

import os
import re
from typing import Any, Dict, List, Optional, Set

from .models import (
    SelectedTestItem,
    TestSelectionPlan,
    TestSelectionPriority,
    VerificationSurface,
)
from .planner import VerificationPlan


class ContinuousTestSelector:
    """
    Selects existing tests before generating new ones.
    Priority Cascade (Deterministic, Risk-Guided, Impact-Guided, Cost-Aware):
    1. known failure regression
    2. directly affected symbol tests
    3. direct consumer tests
    4. contract tests
    5. behavioral tests
    6. high-risk tests
    7. browser tests
    8. broader regression tests
    """
    __test__ = False  # Prevent pytest collection warning

    def __init__(self, known_regression_ids: Optional[Set[str]] = None) -> None:
        self.known_regression_ids = known_regression_ids or set()

    def select_tests(
        self,
        surface: VerificationSurface,
        plan: VerificationPlan,
        available_tests: Optional[List[Dict[str, Any]]] = None,
    ) -> TestSelectionPlan:
        """Deterministically select tests based on impact surface and budget."""
        tests_pool = available_tests or []
        
        # Categorized candidates
        candidates_by_priority: Dict[TestSelectionPriority, List[SelectedTestItem]] = {
            p: [] for p in TestSelectionPriority
        }
        
        covered_symbols: Set[str] = set()
        covered_contracts: Set[str] = set()
        covered_files: Set[str] = set()

        # Step 1: Evaluate each candidate in pool
        for t in tests_pool:
            t_id = t.get("test_id", "")
            target_file = t.get("target_file", "")
            target_symbol = t.get("target_symbol", "")
            framework = t.get("framework", "pytest")
            cost_ms = t.get("estimated_cost_ms", 10.0)

            # 1. Known Failure Regression
            if t_id in self.known_regression_ids or "regression" in t_id.lower() or t.get("is_regression"):
                candidates_by_priority[TestSelectionPriority.KNOWN_FAILURE_REGRESSION].append(
                    SelectedTestItem(
                        test_id=t_id,
                        priority=TestSelectionPriority.KNOWN_FAILURE_REGRESSION,
                        reason=f"Matches known failure regression: {t_id}",
                        framework=framework,
                        file_path=target_file,
                        symbol_id=target_symbol,
                        estimated_cost_ms=cost_ms,
                    )
                )
                if target_symbol:
                    covered_symbols.add(target_symbol)
                continue

            # 2. Directly Affected Symbol Tests
            if target_symbol and target_symbol in surface.affected_symbols:
                candidates_by_priority[TestSelectionPriority.DIRECTLY_AFFECTED_SYMBOL].append(
                    SelectedTestItem(
                        test_id=t_id,
                        priority=TestSelectionPriority.DIRECTLY_AFFECTED_SYMBOL,
                        reason=f"Directly tests affected symbol: {target_symbol}",
                        framework=framework,
                        file_path=target_file,
                        symbol_id=target_symbol,
                        estimated_cost_ms=cost_ms,
                    )
                )
                covered_symbols.add(target_symbol)
                continue

            # 3. Direct Consumer Tests
            is_consumer = any(target_file in c or (target_symbol and target_symbol in c) for c in surface.affected_consumers)
            if is_consumer:
                candidates_by_priority[TestSelectionPriority.DIRECT_CONSUMER].append(
                    SelectedTestItem(
                        test_id=t_id,
                        priority=TestSelectionPriority.DIRECT_CONSUMER,
                        reason=f"Verifies direct consumer: {target_file}",
                        framework=framework,
                        file_path=target_file,
                        symbol_id=target_symbol,
                        estimated_cost_ms=cost_ms,
                    )
                )
                continue

            # 4. Contract Tests
            is_contract = any(target_file in c or (target_symbol and target_symbol in c) for c in surface.affected_contracts) or "contract" in t_id.lower()
            if is_contract and surface.affected_contracts:
                candidates_by_priority[TestSelectionPriority.CONTRACT].append(
                    SelectedTestItem(
                        test_id=t_id,
                        priority=TestSelectionPriority.CONTRACT,
                        reason=f"Verifies affected contract boundary: {target_file}",
                        framework=framework,
                        file_path=target_file,
                        symbol_id=target_symbol,
                        estimated_cost_ms=cost_ms,
                    )
                )
                if target_file:
                    covered_contracts.add(target_file)
                continue

            # 5. Behavioral Tests
            if any(b in t_id.lower() for b in ["behavior", "flow", "state", "invariant"]) or surface.affected_behaviors:
                candidates_by_priority[TestSelectionPriority.BEHAVIORAL].append(
                    SelectedTestItem(
                        test_id=t_id,
                        priority=TestSelectionPriority.BEHAVIORAL,
                        reason=f"Validates behavioral preservation: {t_id}",
                        framework=framework,
                        file_path=target_file,
                        symbol_id=target_symbol,
                        estimated_cost_ms=cost_ms,
                    )
                )
                continue

            # 6. High-Risk Tests
            if surface.risk_level in ("HIGH", "CRITICAL") and any(r in t_id.lower() for r in ["security", "sentinel", "auth", "token"]):
                candidates_by_priority[TestSelectionPriority.HIGH_RISK].append(
                    SelectedTestItem(
                        test_id=t_id,
                        priority=TestSelectionPriority.HIGH_RISK,
                        reason=f"High-risk defensive test: {t_id}",
                        framework=framework,
                        file_path=target_file,
                        symbol_id=target_symbol,
                        estimated_cost_ms=cost_ms,
                    )
                )
                continue

            # 7. Browser Tests
            if (framework in ("playwright", "cypress") or "browser" in t_id.lower()) and surface.browser_surfaces:
                if plan.policy.max_browser_tests > 0:
                    candidates_by_priority[TestSelectionPriority.BROWSER].append(
                        SelectedTestItem(
                            test_id=t_id,
                            priority=TestSelectionPriority.BROWSER,
                            reason=f"Browser UI surface test: {t_id}",
                            framework="playwright",
                            file_path=target_file,
                            symbol_id=target_symbol,
                            estimated_cost_ms=max(cost_ms, 50.0),
                        )
                    )
                continue

            # 8. Broader Regression Tests
            if target_file in surface.affected_files:
                candidates_by_priority[TestSelectionPriority.BROADER_REGRESSION].append(
                    SelectedTestItem(
                        test_id=t_id,
                        priority=TestSelectionPriority.BROADER_REGRESSION,
                        reason=f"Broader regression on affected file: {target_file}",
                        framework=framework,
                        file_path=target_file,
                        symbol_id=target_symbol,
                        estimated_cost_ms=cost_ms,
                    )
                )
                covered_files.add(target_file)

        # Step 2: Budget-Guided Selection
        selected: List[SelectedTestItem] = []
        skipped: List[str] = []
        deferred: List[str] = []
        max_budget = plan.budget_tests
        browser_count = 0

        for priority in TestSelectionPriority:
            # Deterministic sorting by test_id
            group = sorted(candidates_by_priority[priority], key=lambda x: x.test_id)
            for item in group:
                if item.priority == TestSelectionPriority.BROWSER:
                    if browser_count >= plan.policy.max_browser_tests:
                        deferred.append(f"{item.test_id} (browser budget limit reached)")
                        continue
                    browser_count += 1

                if len(selected) < max_budget:
                    selected.append(item)
                else:
                    deferred.append(f"{item.test_id} (max_tests budget {max_budget} reached)")

        # Step 3: Identify Required But Missing Tests (Coverage Gaps)
        required_but_missing: List[Dict[str, Any]] = []
        for sym in surface.affected_symbols:
            if sym not in covered_symbols:
                required_but_missing.append({
                    "gap_type": "SYMBOL_UNCOVERED",
                    "target_symbol": sym,
                    "reason": f"No existing test selected for affected symbol '{sym}'",
                    "risk_level": surface.risk_level,
                })

        for contract in surface.affected_contracts:
            if contract not in covered_contracts:
                required_but_missing.append({
                    "gap_type": "CONTRACT_UNCOVERED",
                    "target_contract": contract,
                    "reason": f"Contract '{contract}' has no corresponding contract test selected",
                    "risk_level": surface.risk_level,
                })

        return TestSelectionPlan(
            selected=selected,
            skipped=skipped,
            deferred=deferred,
            required_but_missing=required_but_missing,
        )
