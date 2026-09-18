"""
JARVIS OS — Phase 61: Autonomous Test Synthesis & Coverage-Guided Validation
Comprehensive Test Suite (25 Test Cases)
"""

from __future__ import annotations

import os
import sys

# Ensure repository root is on sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from typing import Any, Dict, List

from backend.agents.autonomous_test_synthesis.analyzer import CoverageGapAnalyzer
from backend.agents.autonomous_test_synthesis.behavior import BehaviorTestGenerator
from backend.agents.autonomous_test_synthesis.bridge import AutonomousTestSynthesisBridge
from backend.agents.autonomous_test_synthesis.browser import BrowserTestSynthesizer
from backend.agents.autonomous_test_synthesis.cache import TestSynthesisCache
from backend.agents.autonomous_test_synthesis.candidate import TestCandidateManager
from backend.agents.autonomous_test_synthesis.contracts import ContractTestGenerator
from backend.agents.autonomous_test_synthesis.counterexample import CounterexampleTestSynthesizer
from backend.agents.autonomous_test_synthesis.coverage import MultiDimensionalCoverageTracker
from backend.agents.autonomous_test_synthesis.executor import TestExecutor
from backend.agents.autonomous_test_synthesis.feedback import AdaptiveFeedbackEngine
from backend.agents.autonomous_test_synthesis.generator import AutonomousTestGenerator
from backend.agents.autonomous_test_synthesis.index import TestSynthesisIndex
from backend.agents.autonomous_test_synthesis.minimizer import (
    TestMinimalityEvaluator,
    TestQualityEvaluator,
)
from backend.agents.autonomous_test_synthesis.models import (
    CostEstimate,
    CounterexampleEvidence,
    CoverageGapType,
    CoverageMetrics,
    MutationResult,
    MutationType,
    TestCandidate,
    TestCandidateStatus,
    TestExecutionResult,
    TestFramework,
    TestRequirement,
    TestRequirementSource,
    TestStrategy,
)
from backend.agents.autonomous_test_synthesis.policy import TestSynthesisPolicy
from backend.agents.autonomous_test_synthesis.ranking import RiskGuidedTestRanker
from backend.agents.autonomous_test_synthesis.requirements import TestRequirementExtractor
from backend.agents.autonomous_test_synthesis.risk import TestRiskEvaluator
from backend.agents.autonomous_test_synthesis.security import TestSecuritySentinel
from backend.agents.autonomous_test_synthesis.validator import (
    MutationTestingEngine,
    TestSynthesisValidator,
)


class TestAutonomousTestSynthesis:
    """25 Test Cases validating Phase 61 requirements."""

    def setup_method(self) -> None:
        AutonomousTestSynthesisBridge.reset_instance()
        self.bridge = AutonomousTestSynthesisBridge.get_instance()

    # 1. requirement extraction
    def test_01_requirement_extraction(self) -> None:
        extractor = TestRequirementExtractor()
        reqs = extractor.extract_from_change(
            symbol_id="agents/payment.py::process_transaction",
            file_id="agents/payment.py",
            acceptance_criteria=["Must reject negative values"],
            contracts=[{"contract_id": "PaymentDTO", "is_polymorphic": True}],
            behavioral_invariants=["REQUEST->AUTH->ECONOMIC_EFFECT chain preserved"],
            risk_score=0.8,
        )
        assert len(reqs) >= 4
        sources = {r.source for r in reqs}
        assert TestRequirementSource.SYMBOL_IMPACT in sources
        assert TestRequirementSource.CONTRACT in sources
        assert TestRequirementSource.BEHAVIORAL_INVARIANT in sources
        assert TestRequirementSource.USER_ACCEPTANCE_CRITERION in sources

    # 2. coverage gap
    def test_02_coverage_gap(self) -> None:
        analyzer = CoverageGapAnalyzer()
        req = TestRequirement(
            requirement_id="REQ_1",
            source=TestRequirementSource.SYMBOL_IMPACT,
            symbol_id="agents/test.py::untested_fn",
            file_id="agents/test.py",
            coverage_gap=CoverageGapType.UNTESTED_SYMBOL,
        )
        gaps = analyzer.analyze_gaps([req])
        assert len(gaps) == 1
        assert gaps[0]["gap_type"] == CoverageGapType.UNTESTED_SYMBOL.value

        # After recording execution
        analyzer.record_test_execution(symbol_id="agents/test.py::untested_fn")
        gaps_after = analyzer.analyze_gaps([req])
        assert len(gaps_after) == 0

    # 3. symbol-guided generation
    def test_03_symbol_guided_generation(self) -> None:
        mgr = TestCandidateManager()
        generator = AutonomousTestGenerator(mgr)
        req = TestRequirement(
            requirement_id="REQ_SYM",
            source=TestRequirementSource.SYMBOL_IMPACT,
            symbol_id="agents/payment.py::calculate_discount",
            file_id="agents/payment.py",
            risk=0.6,
        )
        cands = generator.generate_for_requirement(req)
        assert len(cands) == 1
        assert "calculate_discount" in cands[0].code
        assert cands[0].framework == TestFramework.PYTEST

    # 4. contract-guided generation
    def test_04_contract_guided_generation(self) -> None:
        mgr = TestCandidateManager()
        c_gen = ContractTestGenerator(mgr)
        req = TestRequirement(
            requirement_id="REQ_CTR",
            source=TestRequirementSource.CONTRACT,
            symbol_id="agents/payment.py::OrderDTO",
            file_id="agents/payment.py",
            contract_id="OrderDTO",
        )
        spec = {
            "contract_id": "OrderDTO",
            "variants": ["standard", "premium"],
            "sample_payloads": {
                "standard": {"items": 1},
                "premium": {"items": 5, "discount": 0.2},
            },
        }
        cands = c_gen.generate_contract_suite(req, spec, is_closed_exhaustive=False)
        assert len(cands) == 3  # 2 variants + 1 open fallback
        assert any("open_fallback" in c.target for c in cands)

    # 5. behavior-guided generation
    def test_05_behavior_guided_generation(self) -> None:
        mgr = TestCandidateManager()
        b_gen = BehaviorTestGenerator(mgr)
        req = TestRequirement(
            requirement_id="REQ_BEH",
            source=TestRequirementSource.BEHAVIORAL_INVARIANT,
            symbol_id="agents/payment.py::pipeline",
            file_id="agents/payment.py",
        )
        cand = b_gen.generate_stage_test(req, target_stages=["REQUEST", "AUTH", "ECONOMIC_EFFECT"])
        assert "REQUEST" in cand.code
        assert "AUTH" in cand.code
        assert "ECONOMIC_EFFECT" in cand.code

    # 6. risk ranking
    def test_06_risk_ranking(self) -> None:
        mgr = TestCandidateManager()
        ranker = RiskGuidedTestRanker()
        c1 = mgr.create_candidate(
            requirement_id="R1", target="low_risk", framework=TestFramework.PYTEST,
            language="python", files=["a.py"], inputs={}, expected_outputs={}, invariants=[],
            code="assert True", risk=0.2, predicted_coverage_gain=0.05,
        )
        c2 = mgr.create_candidate(
            requirement_id="R2", target="critical_security", framework=TestFramework.PYTEST,
            language="python", files=["b.py"], inputs={}, expected_outputs={}, invariants=["sec"],
            code="assert token", risk=0.95, predicted_coverage_gain=0.30, provenance="security_test",
        )
        ranked = ranker.rank_candidates([c1, c2])
        assert ranked[0].test_id == c2.test_id  # Critical security must rank #1

    # 7. deterministic ordering
    def test_07_deterministic_ordering(self) -> None:
        mgr = TestCandidateManager()
        ranker = RiskGuidedTestRanker()
        c1 = mgr.create_candidate(
            requirement_id="R1", target="equal_1", framework=TestFramework.PYTEST,
            language="python", files=["a.py"], inputs={}, expected_outputs={}, invariants=[],
            code="assert True", risk=0.5, predicted_coverage_gain=0.1,
        )
        c2 = mgr.create_candidate(
            requirement_id="R2", target="equal_2", framework=TestFramework.PYTEST,
            language="python", files=["b.py"], inputs={}, expected_outputs={}, invariants=[],
            code="assert 1", risk=0.5, predicted_coverage_gain=0.1,
        )
        # Order must be deterministic across runs
        r1 = [c.test_id for c in ranker.rank_candidates([c1, c2])]
        r2 = [c.test_id for c in ranker.rank_candidates([c2, c1])]
        assert r1 == r2

    # 8. test quality
    def test_08_test_quality_evaluator(self) -> None:
        mgr = TestCandidateManager()
        bad_cand = mgr.create_candidate(
            requirement_id="R_BAD", target="fn", framework=TestFramework.PYTEST,
            language="python", files=["a.py"], inputs={}, expected_outputs={}, invariants=[],
            code="def test_vacuous():\n    assert True",
        )
        is_valid, reason = TestQualityEvaluator.evaluate_quality(bad_cand)
        assert not is_valid
        assert "Trivial vacuous assertion" in reason

    # 9. test minimality
    def test_09_test_minimality(self) -> None:
        mgr = TestCandidateManager()
        minimizer = TestMinimalityEvaluator()
        c1 = mgr.create_candidate(
            requirement_id="R1", target="fn", framework=TestFramework.PYTEST,
            language="python", files=["a.py"], inputs={"a": 1}, expected_outputs={}, invariants=["inv1"],
            code="def test_1():\n    fn()\n    assert result == 1",
        )
        c2 = mgr.create_candidate(
            requirement_id="R1", target="fn", framework=TestFramework.PYTEST,
            language="python", files=["a.py"], inputs={"a": 1}, expected_outputs={}, invariants=["inv1"],
            code="def test_2():\n    fn()\n    assert result == 1",
        )
        filtered = minimizer.filter_minimal_set([c1, c2])
        assert len(filtered) == 1
        assert c2.status == TestCandidateStatus.REJECTED

    # 10. mutation testing
    def test_10_mutation_testing(self) -> None:
        engine = MutationTestingEngine()
        code = "def calc(x):\n    return x + 10"
        mutants = engine.generate_mutants("calc", "calc.py", code)
        assert len(mutants) >= 1
        assert mutants[0].mutation_type == MutationType.OPERATOR_SWAP

        mgr = TestCandidateManager()
        killer = mgr.create_candidate(
            requirement_id="R", target="calc", framework=TestFramework.PYTEST,
            language="python", files=["calc.py"], inputs={"x": 5}, expected_outputs={"return_value": 15},
            invariants=["calc(5) must be 15"], code="assert calc(5) == 15",
        )
        score_res = engine.evaluate_mutation_score(mutants, [killer])
        assert score_res["mutation_score"] == 1.0
        assert score_res["mutants_detected"] >= 1

    # 11. failure feedback
    def test_11_failure_feedback(self) -> None:
        executor = TestExecutor()
        mgr = TestCandidateManager()
        failing_cand = mgr.create_candidate(
            requirement_id="R_FAIL", target="payment", framework=TestFramework.PYTEST,
            language="python", files=["payment.py"], inputs={"amount": -100.0},
            expected_outputs={}, invariants=[], code="def test_neg():\n    assert False",
        )
        res = executor.execute(failing_cand)
        assert not res.passed
        assert res.counterexample is not None
        assert res.counterexample.violating_input["amount"] == -100.0

    # 12. counterexample regression test
    def test_12_counterexample_regression_test(self) -> None:
        mgr = TestCandidateManager()
        syn = CounterexampleTestSynthesizer(mgr)
        cx = CounterexampleEvidence(
            counterexample_id="cx_drift_01",
            source_invariant="amount >= 0",
            violating_input={"amount": -50.0},
            observed_output="Accepted",
            expected_property="ValidationError",
            symbol_id="agents/payment.py::pay",
            file_id="agents/payment.py",
        )
        cand = syn.synthesize_regression_test(cx, "agents.payment")
        assert "KNOWN_FAILURE_REGRESSION" in cand.provenance
        assert "cx_drift_01" in cand.code
        assert len(syn.get_known_regressions()) == 1

    # 13. repair integration
    def test_13_repair_integration(self) -> None:
        bridge = AutonomousTestSynthesisBridge.get_instance()
        # Coverage not yet sufficient -> blocked
        ready, msg = bridge.verify_repair_readiness("REP_01", ["agents/payment.py::pay"], required_coverage=0.90)
        assert not ready
        assert "REPAIR_BLOCKED" in msg

    # 14. multi-repair integration
    def test_14_multi_repair_integration(self) -> None:
        bridge = AutonomousTestSynthesisBridge.get_instance()
        res = bridge.synthesize_for_change(
            symbol_id="agents/multi.py::repair_point",
            file_id="agents/multi.py",
            contracts=[{"contract_id": "MultiDTO"}],
        )
        assert res["candidates_count"] > 0
        assert res["evidence_count"] > 0

    # 15. convergence integration
    def test_15_convergence_integration(self) -> None:
        tracker = MultiDimensionalCoverageTracker(target_symbol=0.90)
        assert not tracker.is_sufficient(min_composite=0.85)

    # 16. browser test generation
    def test_16_browser_test_generation(self) -> None:
        mgr = TestCandidateManager()
        b_syn = BrowserTestSynthesizer(mgr)
        req = TestRequirement(
            requirement_id="REQ_BRO", source=TestRequirementSource.USER_ACCEPTANCE_CRITERION,
            symbol_id="browser::missions", file_id="frontend/missions.tsx", scenario_type="browser",
        )
        cand = b_syn.generate_browser_test(
            requirement=req,
            route="/missions",
            selectors=["#mission-control-root"],
            expected_texts=["JARVIS Mission Control"],
        )
        assert cand.framework == TestFramework.PLAYWRIGHT
        assert "waitForSelector('#mission-control-root'" in cand.code

    # 17. security block
    def test_17_security_block(self) -> None:
        sentinel = TestSecuritySentinel()
        mgr = TestCandidateManager()
        malicious_cand = mgr.create_candidate(
            requirement_id="R_MAL", target="fn", framework=TestFramework.PYTEST,
            language="python", files=["a.py"], inputs={}, expected_outputs={}, invariants=[],
            code="def test_rm():\n    import shutil\n    shutil.rmtree('/tmp')",
        )
        is_safe, reason = sentinel.validate_candidate_safety(malicious_cand)
        assert not is_safe
        assert "SECURITY_BLOCKED" in reason

    # 18. economic sandbox
    def test_18_economic_sandbox(self) -> None:
        extractor = TestRequirementExtractor()
        reqs = extractor.extract_from_change(
            symbol_id="agents/payment.py::pay",
            file_id="agents/payment.py",
            economic_policies=["Never transfer real funds during test suite execution"],
        )
        eco_req = next(r for r in reqs if r.source == TestRequirementSource.ECONOMIC_POLICY)
        assert eco_req.scenario_type == "economic_sandbox"
        assert eco_req.risk == 1.0  # Max risk

    # 19. large repository scope
    def test_19_large_repository_scope(self) -> None:
        bridge = AutonomousTestSynthesisBridge.get_instance()
        # Synthesis scoped strictly to target symbol and direct contracts
        res = bridge.synthesize_for_change(
            symbol_id="agents/scoped.py::action",
            file_id="agents/scoped.py",
        )
        # Should not generate tests for unrelated symbols in repo
        assert res["symbol_id"] == "agents/scoped.py::action"
        assert res["duration_ms"] < 2000.0  # Under 2 seconds

    # 20. deterministic replay
    def test_20_deterministic_replay(self) -> None:
        mgr1 = TestCandidateManager()
        mgr2 = TestCandidateManager()
        id1 = mgr1.generate_deterministic_id("REQ_1", "target_A", "assert True == 1")
        id2 = mgr2.generate_deterministic_id("REQ_1", "target_A", "assert True == 1")
        assert id1 == id2

    # 21. duplicate elimination
    def test_21_duplicate_elimination(self) -> None:
        minimizer = TestMinimalityEvaluator()
        mgr = TestCandidateManager()
        c1 = mgr.create_candidate(
            requirement_id="R1", target="fn", framework=TestFramework.PYTEST,
            language="python", files=["a.py"], inputs={"k": "v"}, expected_outputs={}, invariants=["inv"],
            code="def test_a():\n    fn()\n    assert 1",
        )
        c2 = mgr.create_candidate(
            requirement_id="R1", target="fn", framework=TestFramework.PYTEST,
            language="python", files=["a.py"], inputs={"k": "v"}, expected_outputs={}, invariants=["inv"],
            code="def test_b():\n    fn()\n    assert 1",
        )
        res = minimizer.filter_minimal_set([c1, c2])
        assert len(res) == 1

    # 22. insufficient coverage
    def test_22_insufficient_coverage(self) -> None:
        validator = TestSynthesisValidator()
        mgr = TestCandidateManager()
        c = mgr.create_candidate(
            requirement_id="R1", target="fn", framework=TestFramework.PYTEST,
            language="python", files=["a.py"], inputs={}, expected_outputs={}, invariants=[],
            code="def test_sample():\n    fn()\n    assert 1",
        )
        is_valid, errors = validator.validate_suite([c], [TestExecutionResult("fn", True, 1.0, 0.1, 0.0)], composite_coverage=0.40, min_required_coverage=0.75)
        assert not is_valid
        assert any("below threshold" in e for e in errors)

    # 23. unknown contract
    def test_23_unknown_contract(self) -> None:
        mgr = TestCandidateManager()
        gen = ContractTestGenerator(mgr)
        req = TestRequirement(
            requirement_id="R_UNK", source=TestRequirementSource.CONTRACT,
            symbol_id="agents/c.py::unknown", file_id="agents/c.py",
        )
        cands = gen.generate_contract_suite(req, {"contract_id": "UnknownDTO"}, is_closed_exhaustive=False)
        assert any("open_fallback" in c.target for c in cands)

    # 24. dynamic consumer
    def test_24_dynamic_consumer(self) -> None:
        extractor = TestRequirementExtractor()
        reqs = extractor.extract_from_change(
            symbol_id="agents/dyn.py::producer",
            file_id="agents/dyn.py",
            impact_result={"downstream_consumers": ["dynamic_consumer_module"]},
        )
        c_req = next(r for r in reqs if r.consumer_id == "dynamic_consumer_module")
        assert c_req.coverage_gap == CoverageGapType.UNTESTED_CONSUMER

    # 25. test poisoning
    def test_25_test_poisoning_defense(self) -> None:
        mgr = TestCandidateManager()
        c = mgr.create_candidate(
            requirement_id="R_POI", target="T", framework=TestFramework.PYTEST,
            language="python", files=["a.py"], inputs={}, expected_outputs={}, invariants=[],
            code="assert valid_output()",
        )
        h1 = c.compute_hash()
        # Tamper with code
        c.code = "assert tampered()"
        h2 = c.compute_hash()
        assert h1 != h2
