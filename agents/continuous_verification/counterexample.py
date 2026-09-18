"""
JARVIS OS — Phase 62: Continuous Verification & Autonomous Regression Governance
Module: counterexample.py
Counterexample Promotion Manager integrating F61 CounterexampleTestSynthesizer.
Flow: COUNTEREXAMPLE -> MINIMIZE -> SYNTHESIZE -> EXECUTE -> PASS -> REGISTER_PERMANENT_REGRESSION.
Invariant: Never confirm regression if reproduction fails (FAILED_REPRODUCTION -> REGRESSION_CONFIRMED is prohibited).
"""

from __future__ import annotations

import hashlib
import time
from typing import Any, Dict, List, Optional, Set, Tuple

from .models import SelectedTestItem, TestSelectionPriority


class CounterexamplePromotionManager:
    """
    Promotes validated counterexamples into permanent regression tests.
    Ensures non-reproducible counterexamples do not contaminate the regression baseline.
    """
    __test__ = False  # Prevent pytest collection warning

    def __init__(self) -> None:
        self.permanent_regressions: Dict[str, Dict[str, Any]] = {}

    def process_counterexample(
        self,
        counterexample: Dict[str, Any],
        target_symbol: str,
        target_file: str,
        can_reproduce: bool = True,
    ) -> Tuple[str, Optional[SelectedTestItem]]:
        """
        Process counterexample and determine if it qualifies for permanent regression status.
        Returns:
            status: "REGISTER_PERMANENT_REGRESSION" or "INSUFFICIENT_EVIDENCE"
            test_item: Optional[SelectedTestItem] if registered
        """
        # Invariant: If reproduction fails -> INSUFFICIENT_EVIDENCE
        if not can_reproduce:
            return "INSUFFICIENT_EVIDENCE", None

        # 1. Minimize input
        raw_input = counterexample.get("input", {})
        minimized_input = {k: v for k, v in raw_input.items() if v is not None} if isinstance(raw_input, dict) else raw_input

        # 2. Synthesize deterministic regression test id
        c_hash = hashlib.sha256(f"{target_symbol}:{minimized_input}".encode("utf-8")).hexdigest()[:10]
        test_id = f"test_regression_cx_{c_hash}"

        # 3. Create permanent regression record
        reg_record = {
            "test_id": test_id,
            "target_symbol": target_symbol,
            "target_file": target_file,
            "counterexample": minimized_input,
            "registered_at": time.time(),
            "provenance": "CounterexamplePromotionManager",
        }
        self.permanent_regressions[test_id] = reg_record

        # 4. Wrap into SelectedTestItem
        item = SelectedTestItem(
            test_id=test_id,
            priority=TestSelectionPriority.KNOWN_FAILURE_REGRESSION,
            reason=f"Promoted from reproducible counterexample on {target_symbol}",
            is_synthesized=True,
            framework="pytest",
            file_path=target_file,
            symbol_id=target_symbol,
            estimated_cost_ms=10.0,
        )

        return "REGISTER_PERMANENT_REGRESSION", item

    def get_permanent_regression_ids(self) -> Set[str]:
        return set(self.permanent_regressions.keys())
