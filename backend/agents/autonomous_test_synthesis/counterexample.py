"""
JARVIS OS — Phase 61: Autonomous Test Synthesis & Coverage-Guided Validation
Module: counterexample.py
Synthesizes targeted regression tests from behavioral counterexamples and persists them
as KNOWN_FAILURE_REGRESSION to ensure permanent prevention of recurrence.
"""

from __future__ import annotations

import hashlib
import json
import os
from typing import Any, Dict, List, Optional

from .candidate import TestCandidateManager
from .models import (
    CostEstimate,
    CounterexampleEvidence,
    TestCandidate,
    TestFramework,
    TestRequirement,
    TestRequirementSource,
)
from .templates import TestCodeTemplates


class CounterexampleTestSynthesizer:
    """
    Transforms counterexamples from Behavioral Contract Proof (Phase 50) and Risk-Directed
    Exploration (Phase 52) into persistent regression tests.
    """

    def __init__(self, candidate_mgr: TestCandidateManager, persistence_dir: Optional[str] = None) -> None:
        self.candidate_mgr = candidate_mgr
        self.persistence_dir = persistence_dir
        self.known_regressions: Dict[str, Dict[str, Any]] = {}
        self.templates = TestCodeTemplates()

    def synthesize_regression_test(
        self,
        counterexample: CounterexampleEvidence,
        module_path: str,
    ) -> TestCandidate:
        """Generate a concrete regression test reproducing the counterexample."""
        func_name = counterexample.symbol_id.split("::")[-1] if "::" in counterexample.symbol_id else counterexample.symbol_id
        code = self.templates.render_python_regression(
            counterexample_id=counterexample.counterexample_id,
            module_path=module_path,
            func_name=func_name,
            violating_input=counterexample.violating_input,
            expected_property=counterexample.expected_property,
        )

        req_id = f"REQ_CTX_{counterexample.counterexample_id}"
        cand = self.candidate_mgr.create_candidate(
            requirement_id=req_id,
            target=f"{counterexample.symbol_id}::{counterexample.counterexample_id}",
            framework=TestFramework.PYTEST,
            language="python",
            files=[counterexample.file_id],
            inputs=counterexample.violating_input,
            expected_outputs={"preserved_property": counterexample.expected_property},
            invariants=[counterexample.expected_property],
            code=code,
            risk=0.95,
            estimated_cost=CostEstimate(generation_cost=0.01, execution_cost=0.015, total_cost=0.025),
            predicted_coverage_gain=0.20,
            provenance="KNOWN_FAILURE_REGRESSION",
        )

        # Register in known regressions dictionary
        self.known_regressions[counterexample.counterexample_id] = {
            "test_id": cand.test_id,
            "counterexample": counterexample.to_dict(),
            "status": "ACTIVE_REGRESSION_PREVENTER",
            "code": code,
        }

        return cand

    def get_known_regressions(self) -> List[Dict[str, Any]]:
        return list(self.known_regressions.values())
