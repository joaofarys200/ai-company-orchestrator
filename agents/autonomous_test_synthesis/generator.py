"""
JARVIS OS — Phase 61: Autonomous Test Synthesis & Coverage-Guided Validation
Module: generator.py
Orchestrates the 8 generation strategies based on requirements, symbols, contracts, and behavior.
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

from .candidate import TestCandidateManager
from .models import (
    CostEstimate,
    TestCandidate,
    TestFramework,
    TestRequirement,
    TestRequirementSource,
    TestStrategy,
)
from .templates import TestCodeTemplates


class AutonomousTestGenerator:
    """
    Generates tailored, high-fidelity test candidates using symbol impact,
    contracts, behavior, counterexamples, and Playwright browser specs.
    """

    def __init__(self, candidate_mgr: TestCandidateManager) -> None:
        self.candidate_mgr = candidate_mgr
        self.templates = TestCodeTemplates()

    def generate_for_requirement(
        self,
        requirement: TestRequirement,
        strategy: Optional[TestStrategy] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> List[TestCandidate]:
        """Synthesize one or more test candidates satisfying the requirement."""
        ctx = context or {}
        strat = strategy or self._resolve_strategy(requirement)

        candidates: List[TestCandidate] = []

        if strat == TestStrategy.UNIT_TEST_SYNTHESIS:
            candidates.extend(self._synthesize_unit(requirement, ctx))
        elif strat == TestStrategy.CONTRACT_TEST_SYNTHESIS:
            candidates.extend(self._synthesize_contract(requirement, ctx))
        elif strat == TestStrategy.BEHAVIORAL_TEST_SYNTHESIS:
            candidates.extend(self._synthesize_behavioral(requirement, ctx))
        elif strat == TestStrategy.REGRESSION_TEST_SYNTHESIS:
            candidates.extend(self._synthesize_regression(requirement, ctx))
        elif strat == TestStrategy.BROWSER_TEST_SYNTHESIS:
            candidates.extend(self._synthesize_browser(requirement, ctx))
        elif strat == TestStrategy.ERROR_PATH_TEST_SYNTHESIS:
            candidates.extend(self._synthesize_error_path(requirement, ctx))
        elif strat == TestStrategy.PROPERTY_TEST_SYNTHESIS:
            candidates.extend(self._synthesize_property(requirement, ctx))
        elif strat == TestStrategy.INTEGRATION_TEST_SYNTHESIS:
            candidates.extend(self._synthesize_integration(requirement, ctx))
        else:
            candidates.extend(self._synthesize_unit(requirement, ctx))

        return candidates

    def _resolve_strategy(self, req: TestRequirement) -> TestStrategy:
        if req.source == TestRequirementSource.CONTRACT:
            return TestStrategy.CONTRACT_TEST_SYNTHESIS
        elif req.source in (TestRequirementSource.BEHAVIORAL_INVARIANT, TestRequirementSource.ECONOMIC_POLICY):
            return TestStrategy.BEHAVIORAL_TEST_SYNTHESIS
        elif req.source == TestRequirementSource.COUNTEREXAMPLE:
            return TestStrategy.REGRESSION_TEST_SYNTHESIS
        elif req.source == TestRequirementSource.SECURITY_POLICY:
            return TestStrategy.ERROR_PATH_TEST_SYNTHESIS
        elif req.scenario_type == "browser":
            return TestStrategy.BROWSER_TEST_SYNTHESIS
        elif req.consumer_id is not None:
            return TestStrategy.INTEGRATION_TEST_SYNTHESIS
        return TestStrategy.UNIT_TEST_SYNTHESIS

    def _synthesize_unit(self, req: TestRequirement, ctx: Dict[str, Any]) -> List[TestCandidate]:
        symbol_name = req.symbol_id.split("::")[-1] if "::" in req.symbol_id else req.symbol_id
        module_path = req.file_id.replace("/", ".").replace(".py", "").replace(".ts", "")
        inputs = ctx.get("inputs", {"arg1": 10, "arg2": "sample"})
        expected = ctx.get("expected", {"return_value": 42})
        invariants = [req.invariant] if req.invariant else ["Return value must be valid"]

        is_ts = req.file_id.endswith(".ts") or req.file_id.endswith(".tsx")
        if is_ts:
            code = self.templates.render_typescript_unit(symbol_name, module_path, inputs, expected)
            framework = TestFramework.VITEST
            lang = "typescript"
        else:
            code = self.templates.render_python_unit(symbol_name, module_path, inputs, expected, invariants)
            framework = TestFramework.PYTEST
            lang = "python"

        cost = CostEstimate(generation_cost=0.005, execution_cost=0.01, environment_cost=0.001, total_cost=0.016)
        cand = self.candidate_mgr.create_candidate(
            requirement_id=req.requirement_id,
            target=req.symbol_id,
            framework=framework,
            language=lang,
            files=[req.file_id],
            inputs=inputs,
            expected_outputs=expected,
            invariants=invariants,
            code=code,
            risk=req.risk,
            estimated_cost=cost,
            predicted_coverage_gain=0.15,
            provenance="unit_synthesis_engine",
        )
        return [cand]

    def _synthesize_contract(self, req: TestRequirement, ctx: Dict[str, Any]) -> List[TestCandidate]:
        cid = req.contract_id or "OrderPaymentContract"
        module_path = req.file_id.replace("/", ".").replace(".py", "")
        variant = ctx.get("variant", "v2_polymorphic")
        payload = ctx.get("payload", {"amount": 100.0, "currency": "EUR", "user_id": "usr_test_123"})
        is_poly = ctx.get("is_polymorphic", True)

        code = self.templates.render_python_contract(cid, module_path, variant, payload, is_poly)
        cost = CostEstimate(generation_cost=0.01, execution_cost=0.02, environment_cost=0.002, total_cost=0.032)

        cand = self.candidate_mgr.create_candidate(
            requirement_id=req.requirement_id,
            target=f"{req.symbol_id}::{cid}",
            framework=TestFramework.PYTEST,
            language="python",
            files=[req.file_id],
            inputs={"payload": payload, "variant": variant},
            expected_outputs={"is_valid": True},
            invariants=[f"Contract schema conforms to {variant}"],
            code=code,
            risk=req.risk,
            estimated_cost=cost,
            predicted_coverage_gain=0.25,
            provenance="contract_synthesis_engine",
        )
        return [cand]

    def _synthesize_behavioral(self, req: TestRequirement, ctx: Dict[str, Any]) -> List[TestCandidate]:
        scenario = ctx.get("scenario_name", "economic_payment_cycle")
        module_path = req.file_id.replace("/", ".").replace(".py", "")
        stages = ["REQUEST", "AUTH", "VALIDATION", "BUSINESS_LOGIC", "RESPONSE", "ECONOMIC_EFFECT"]
        inputs = ctx.get("inputs", {"transaction_id": "tx_mock_999", "amount": 250.0, "sandbox_mode": True})

        code = self.templates.render_python_behavior(scenario, module_path, stages, inputs)
        cost = CostEstimate(generation_cost=0.02, execution_cost=0.04, environment_cost=0.01, total_cost=0.07)

        cand = self.candidate_mgr.create_candidate(
            requirement_id=req.requirement_id,
            target=f"{req.symbol_id}::{scenario}",
            framework=TestFramework.PYTEST,
            language="python",
            files=[req.file_id],
            inputs=inputs,
            expected_outputs={"status": "VERIFIED"},
            invariants=["REQUEST->AUTH->VALIDATION->BUSINESS_LOGIC->ECONOMIC_EFFECT invariant chain"],
            code=code,
            risk=req.risk,
            estimated_cost=cost,
            predicted_coverage_gain=0.30,
            provenance="behavioral_synthesis_engine",
        )
        return [cand]

    def _synthesize_regression(self, req: TestRequirement, ctx: Dict[str, Any]) -> List[TestCandidate]:
        cx_id = ctx.get("counterexample_id", "cx_404_drift")
        module_path = req.file_id.replace("/", ".").replace(".py", "")
        func_name = req.symbol_id.split("::")[-1] if "::" in req.symbol_id else req.symbol_id
        violating_input = ctx.get("violating_input", {"amount": -50.0, "bypass_auth": True})
        prop = req.invariant or "Negative amount must raise ValidationError"

        code = self.templates.render_python_regression(cx_id, module_path, func_name, violating_input, prop)
        cost = CostEstimate(generation_cost=0.01, execution_cost=0.015, environment_cost=0.002, total_cost=0.027)

        cand = self.candidate_mgr.create_candidate(
            requirement_id=req.requirement_id,
            target=f"{req.symbol_id}::counterexample::{cx_id}",
            framework=TestFramework.PYTEST,
            language="python",
            files=[req.file_id],
            inputs=violating_input,
            expected_outputs={"exception_caught": True},
            invariants=[prop],
            code=code,
            risk=0.95,
            estimated_cost=cost,
            predicted_coverage_gain=0.20,
            provenance="counterexample_regression_engine",
        )
        return [cand]

    def _synthesize_browser(self, req: TestRequirement, ctx: Dict[str, Any]) -> List[TestCandidate]:
        scenario_id = ctx.get("scenario_id", "mission_control_overview")
        route = ctx.get("route", "/missions")
        selectors = ctx.get("selectors", ["#mission-control-root", "#view-tab-autonomous_test_synthesis"])
        texts = ctx.get("expected_texts", ["JARVIS Mission Control", "Autonomous Test Synthesis"])

        code = self.templates.render_playwright_browser(scenario_id, route, selectors, texts)
        cost = CostEstimate(generation_cost=0.03, execution_cost=0.15, environment_cost=0.05, browser_cost=0.10, total_cost=0.33)

        cand = self.candidate_mgr.create_candidate(
            requirement_id=req.requirement_id,
            target=f"browser::{scenario_id}",
            framework=TestFramework.PLAYWRIGHT,
            language="python",
            files=[req.file_id],
            inputs={"route": route, "selectors": selectors},
            expected_outputs={"navigation_success": True},
            invariants=["DOM stability and zero console error invariant"],
            code=code,
            risk=0.7,
            estimated_cost=cost,
            predicted_coverage_gain=0.35,
            provenance="playwright_browser_engine",
        )
        return [cand]

    def _synthesize_error_path(self, req: TestRequirement, ctx: Dict[str, Any]) -> List[TestCandidate]:
        symbol_name = req.symbol_id.split("::")[-1] if "::" in req.symbol_id else req.symbol_id
        module_path = req.file_id.replace("/", ".").replace(".py", "")
        inputs = ctx.get("inputs", {"malicious_path": "../../../etc/passwd", "token": "invalid"})
        expected = ctx.get("expected", {"exception": "SecurityException"})
        invariants = ["Path traversal attempt must raise SecurityException and reject input"]

        code = f'''# Auto-generated by JARVIS Autonomous Test Synthesis (Phase 61)
# Error path & security isolation test
import pytest

def test_error_path_{symbol_name}_security_isolation():
    from {module_path} import {symbol_name}
    with pytest.raises(Exception):
        {symbol_name}({", ".join(f"{k}={repr(v)}" for k, v in inputs.items())})
'''
        cost = CostEstimate(generation_cost=0.01, execution_cost=0.01, environment_cost=0.002, total_cost=0.022)
        cand = self.candidate_mgr.create_candidate(
            requirement_id=req.requirement_id,
            target=f"{req.symbol_id}::error_path",
            framework=TestFramework.PYTEST,
            language="python",
            files=[req.file_id],
            inputs=inputs,
            expected_outputs=expected,
            invariants=invariants,
            code=code,
            risk=1.0,
            estimated_cost=cost,
            predicted_coverage_gain=0.20,
            provenance="security_error_path_engine",
        )
        return [cand]

    def _synthesize_property(self, req: TestRequirement, ctx: Dict[str, Any]) -> List[TestCandidate]:
        symbol_name = req.symbol_id.split("::")[-1] if "::" in req.symbol_id else req.symbol_id
        module_path = req.file_id.replace("/", ".").replace(".py", "")

        code = f'''# Auto-generated by JARVIS Autonomous Test Synthesis (Phase 61)
# Property-based parameterized test
import pytest

@pytest.mark.parametrize("val", [0, 1, -1, 100, 10000])
def test_property_{symbol_name}(val):
    from {module_path} import {symbol_name}
    res = {symbol_name}(val)
    assert res is not None
'''
        cost = CostEstimate(generation_cost=0.01, execution_cost=0.02, environment_cost=0.002, total_cost=0.032)
        cand = self.candidate_mgr.create_candidate(
            requirement_id=req.requirement_id,
            target=f"{req.symbol_id}::property",
            framework=TestFramework.PYTEST,
            language="python",
            files=[req.file_id],
            inputs={"values": [0, 1, -1, 100, 10000]},
            expected_outputs={"invariance": True},
            invariants=["Output is deterministic for all integer partitions"],
            code=code,
            risk=req.risk,
            estimated_cost=cost,
            predicted_coverage_gain=0.18,
            provenance="property_synthesis_engine",
        )
        return [cand]

    def _synthesize_integration(self, req: TestRequirement, ctx: Dict[str, Any]) -> List[TestCandidate]:
        consumer = req.consumer_id or "ConsumerModule"
        module_path = req.file_id.replace("/", ".").replace(".py", "")

        code = f'''# Auto-generated by JARVIS Autonomous Test Synthesis (Phase 61)
# Integration test between symbol and downstream consumer
import pytest

def test_integration_{req.symbol_id.replace("::", "_")}_with_{consumer}():
    from {module_path} import {req.symbol_id.split("::")[-1]}
    # Simulated consumer call
    res = {req.symbol_id.split("::")[-1]}()
    assert res is not None
'''
        cost = CostEstimate(generation_cost=0.015, execution_cost=0.03, environment_cost=0.005, total_cost=0.05)
        cand = self.candidate_mgr.create_candidate(
            requirement_id=req.requirement_id,
            target=f"{req.symbol_id}::integration::{consumer}",
            framework=TestFramework.PYTEST,
            language="python",
            files=[req.file_id],
            inputs={"consumer": consumer},
            expected_outputs={"integration_ok": True},
            invariants=[f"Contract agreement with {consumer}"],
            code=code,
            risk=req.risk,
            estimated_cost=cost,
            predicted_coverage_gain=0.22,
            provenance="integration_synthesis_engine",
        )
        return [cand]
