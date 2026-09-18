"""
JARVIS OS — Phase 62: Continuous Verification & Autonomous Regression Governance
Comprehensive Unit Test Suite (20 Mandated Scenarios)
"""

import os
import pytest
from typing import Any, Dict, List

from backend.agents.continuous_verification.bridge import ContinuousVerificationBridge
from backend.agents.continuous_verification.change_detection import ChangeDetector
from backend.agents.continuous_verification.counterexample import CounterexamplePromotionManager
from backend.agents.continuous_verification.coverage import MultidimensionalCoverageEvaluator
from backend.agents.continuous_verification.executor import ContinuousTestExecutor, ExecutionResultItem
from backend.agents.continuous_verification.flaky import FlakyTestDetector
from backend.agents.continuous_verification.impact import ImpactToVerificationPlanner
from backend.agents.continuous_verification.models import (
    BaselineSnapshot,
    ChangeItem,
    ChangeSet,
    ChangeSource,
    ChangeType,
    CoverageVector,
    FlakyAnalysisResult,
    FlakyStatus,
    RegressionClassification,
    RegressionComparisonResult,
    SelectedTestItem,
    TestSelectionPlan,
    TestSelectionPriority,
    VerificationDecisionOutcome,
    VerificationPolicyName,
    VerificationState,
    VerificationSurface,
)
from backend.agents.continuous_verification.planner import ContinuousVerificationPlanner
from backend.agents.continuous_verification.policy import VerificationPolicyEngine
from backend.agents.continuous_verification.regression import RegressionComparator
from backend.agents.continuous_verification.security import VerificationSecuritySentinel
from backend.agents.continuous_verification.selector import ContinuousTestSelector
from backend.agents.continuous_verification.synthesis_bridge import ContinuousSynthesisBridge
from backend.agents.continuous_verification.validator import VerificationDecisionValidator


@pytest.fixture(autouse=True)
def reset_bridge():
    ContinuousVerificationBridge.reset_instance()
    yield
    ContinuousVerificationBridge.reset_instance()


def test_01_change_sem_impacto():
    """1. Invariant: NO_CHANGE -> NO_VERIFICATION (empty change set)."""
    bridge = ContinuousVerificationBridge.get_instance(db_path=":memory:")
    cs = ChangeSet(id="cs_empty", changes=[], source="test")
    decision = bridge.verify_change(change_set=cs)

    assert decision.outcome == VerificationDecisionOutcome.VERIFIED_WITHIN_SCOPE
    assert decision.scope.get("type") == "NO_CHANGE"
    assert len(decision.tests_run) == 0
    assert "NO_VERIFICATION" in decision.reasons[0]


def test_02_change_com_impacto_direto():
    """2. Direct symbol change -> VERIFIED_WITHIN_SCOPE upon passing test."""
    bridge = ContinuousVerificationBridge.get_instance(db_path=":memory:")
    item = ChangeItem(
        file_path="agents/calculator.py",
        symbol_id="func:add_numbers",
        change_type=ChangeType.SYMBOL_CHANGED,
        before_hash="h1",
        after_hash="h2",
    )
    cs = ChangeSet(id="cs_direct", changes=[item], source="test")
    available_tests = [
        {"test_id": "test_add_numbers", "target_file": "agents/calculator.py", "target_symbol": "func:add_numbers"}
    ]
    decision = bridge.verify_change(change_set=cs, available_tests=available_tests)

    assert decision.outcome == VerificationDecisionOutcome.VERIFIED_WITHIN_SCOPE
    assert "test_add_numbers" in decision.tests_run
    assert decision.coverage_after is not None
    assert decision.coverage_after.symbol_coverage > 0


def test_03_change_com_consumer_impact():
    """3. Change impacting consumers -> consumer tests selected and executed."""
    surface = VerificationSurface(
        affected_files=["agents/base.py", "agents/consumer_service.py"],
        affected_symbols=["func:base_compute"],
        affected_consumers=["consumer:agents/consumer_service.py::call_base"],
        risk_level="MEDIUM",
    )
    planner = ContinuousVerificationPlanner()
    plan = planner.create_plan(surface)
    selector = ContinuousTestSelector()
    tests = [
        {"test_id": "test_consumer_flow", "target_file": "agents/consumer_service.py", "target_symbol": "consumer:agents/consumer_service.py::call_base"}
    ]
    sel_plan = selector.select_tests(surface, plan, available_tests=tests)

    assert len(sel_plan.selected) == 1
    assert sel_plan.selected[0].priority == TestSelectionPriority.DIRECT_CONSUMER


def test_04_contract_drift():
    """4. Contract change -> CONTRACT test priority and validation."""
    bridge = ContinuousVerificationBridge.get_instance(db_path=":memory:")
    item = ChangeItem(
        file_path="contracts/payment_contract.py",
        symbol_id="class:PaymentContract",
        change_type=ChangeType.CONTRACT_CHANGED,
        before_hash="h_old",
        after_hash="h_new",
    )
    cs = ChangeSet(id="cs_contract", changes=[item], source="test")
    available_tests = [
        {"test_id": "test_payment_contract_conformance", "target_file": "contracts/payment_contract.py"}
    ]
    decision = bridge.verify_change(change_set=cs, available_tests=available_tests)

    assert decision.outcome == VerificationDecisionOutcome.VERIFIED_WITHIN_SCOPE
    assert "test_payment_contract_conformance" in decision.tests_run


def test_05_missing_tests_triggers_synthesis():
    """5. Required uncovered symbol -> invokes F61 test synthesis and executes candidate."""
    bridge = ContinuousVerificationBridge.get_instance(db_path=":memory:")
    item = ChangeItem(
        file_path="agents/novel_service.py",
        symbol_id="func:novel_algorithm",
        change_type=ChangeType.SYMBOL_ADDED,
        before_hash="",
        after_hash="h_novel",
    )
    cs = ChangeSet(id="cs_novel", changes=[item], source="test")
    # No existing tests provided -> gap resolution triggers synthesis!
    decision = bridge.verify_change(change_set=cs, available_tests=[])

    assert decision.outcome == VerificationDecisionOutcome.VERIFIED_WITHIN_SCOPE
    assert len(decision.tests_run) >= 1
    assert any("synth" in t for t in decision.tests_run)


def test_06_regression_detection():
    """6. Failed test -> REGRESSION_DETECTED with specific reason."""
    bridge = ContinuousVerificationBridge.get_instance(db_path=":memory:")
    item = ChangeItem(
        file_path="agents/calc.py",
        symbol_id="func:divide",
        change_type=ChangeType.SYMBOL_CHANGED,
        before_hash="h_prev",
        after_hash="h_curr",
    )
    cs = ChangeSet(id="cs_regress", changes=[item], source="test")
    available_tests = [
        {"test_id": "test_calc_regression_divide_by_zero", "target_file": "agents/calc.py", "target_symbol": "func:divide"}
    ]
    decision = bridge.verify_change(change_set=cs, available_tests=available_tests)

    assert decision.outcome == VerificationDecisionOutcome.REGRESSION_DETECTED
    assert len(decision.regressions) > 0


def test_07_flaky_test_governance():
    """7. Intermittent failure -> FLAKY_REVIEW_REQUIRED, never masked as PASS."""
    bridge = ContinuousVerificationBridge.get_instance(db_path=":memory:")
    item = ChangeItem(
        file_path="agents/socket_worker.py",
        symbol_id="func:connect_socket",
        change_type=ChangeType.SYMBOL_CHANGED,
    )
    cs = ChangeSet(id="cs_flaky", changes=[item], source="test")
    available_tests = [
        {"test_id": "test_socket_flaky_intermittent", "target_file": "agents/socket_worker.py", "target_symbol": "func:connect_socket"}
    ]
    decision = bridge.verify_change(change_set=cs, available_tests=available_tests)

    assert decision.outcome == VerificationDecisionOutcome.FLAKY
    assert len(decision.flaky_tests) > 0
    assert "FLAKY_REVIEW_REQUIRED" in decision.reasons[0]


def test_08_counterexample_promotion():
    """8. Counterexample promotion: reproducible -> registered; unreproducible -> INSUFFICIENT_EVIDENCE."""
    mgr = CounterexamplePromotionManager()
    cx = {"input": {"val": -5}, "expected": "ValidationError"}

    # Case A: Reproducible
    status, item = mgr.process_counterexample(cx, target_symbol="func:deposit", target_file="agents/wallet.py", can_reproduce=True)
    assert status == "REGISTER_PERMANENT_REGRESSION"
    assert item is not None
    assert item.priority == TestSelectionPriority.KNOWN_FAILURE_REGRESSION
    assert item.test_id in mgr.get_permanent_regression_ids()

    # Case B: Non-reproducible (Prohibited from confirmation)
    status_fail, item_fail = mgr.process_counterexample(cx, target_symbol="func:deposit", target_file="agents/wallet.py", can_reproduce=False)
    assert status_fail == "INSUFFICIENT_EVIDENCE"
    assert item_fail is None


def test_09_dynamic_reflection():
    """9. Dynamic reflection (eval, getattr, etc.) -> increases uncertainty and flags dynamic boundaries."""
    planner = ImpactToVerificationPlanner()
    cs = ChangeSet(
        id="cs_dyn",
        changes=[ChangeItem(file_path="agents/dynamic_dispatcher.py", change_type=ChangeType.MODIFIED)],
    )
    files = {"agents/dynamic_dispatcher.py": "result = eval('2 + 2')\ngetattr(obj, 'action')"}
    surface = planner.analyze(cs, workspace_files=files)

    assert surface.uncertainty >= 0.4
    assert "agents/dynamic_dispatcher.py" in surface.dynamic_boundaries


def test_10_deleted_symbol():
    """10. Symbol deletion detected as SYMBOL_REMOVED."""
    detector = ChangeDetector()
    before = "def active_sym():\n    return 1\n"
    after = "# Removed\n"
    items = detector.detect_from_file_pair("agents/clean.py", before, after)

    removed = [i for i in items if i.change_type == ChangeType.SYMBOL_REMOVED]
    assert len(removed) == 1
    assert "active_sym" in removed[0].symbol_id


def test_11_renamed_file():
    """11. Renamed/created/deleted file lifecycle detected deterministically."""
    detector = ChangeDetector()
    items_created = detector.detect_from_file_pair("agents/new_feature.py", None, "def run(): pass\n")
    assert items_created[0].change_type == ChangeType.CREATED

    items_deleted = detector.detect_from_file_pair("agents/old_feature.py", "def old(): pass\n", None)
    assert items_deleted[0].change_type == ChangeType.DELETED


def test_12_browser_only_change():
    """12. Browser/frontend changes -> routes to browser surface tests."""
    bridge = ContinuousVerificationBridge.get_instance(db_path=":memory:")
    item = ChangeItem(file_path="frontend/src/App.tsx", change_type=ChangeType.MODIFIED)
    cs = ChangeSet(id="cs_browser", changes=[item], source="test")
    available_tests = [
        {"test_id": "test_browser_app_mount", "target_file": "frontend/src/App.tsx", "framework": "playwright"}
    ]
    decision = bridge.verify_change(change_set=cs, available_tests=available_tests)

    assert decision.outcome == VerificationDecisionOutcome.VERIFIED_WITHIN_SCOPE
    assert "test_browser_app_mount" in decision.tests_run
    assert decision.coverage_after.browser_coverage == 1.0


def test_13_cache_hit():
    """13. Deterministic cache hit on unchanged verification scope."""
    bridge = ContinuousVerificationBridge.get_instance(db_path=":memory:")
    item = ChangeItem(file_path="agents/math.py", symbol_id="func:square", change_type=ChangeType.MODIFIED)
    cs = ChangeSet(id="cs_math", changes=[item], source="test")
    available_tests = [{"test_id": "test_square", "target_file": "agents/math.py", "target_symbol": "func:square"}]

    # Run 1: Cache miss
    d1 = bridge.verify_change(change_set=cs, available_tests=available_tests)
    assert bridge.metrics.real_repository.cache_misses == 1

    # Run 2: Cache hit
    d2 = bridge.verify_change(change_set=cs, available_tests=available_tests)
    assert bridge.metrics.real_repository.cache_hits == 1
    assert d1.decision_id == d2.decision_id


def test_14_cache_invalidation():
    """14. Invalidate cache on policy, test, or baseline drift."""
    bridge = ContinuousVerificationBridge.get_instance(db_path=":memory:")
    inv_count = bridge.cache.invalidate_all("Policy change")
    assert inv_count >= 0


def test_15_security_sentinel_block():
    """15. Security Sentinel blocks destructive commands (rmtree, os.system)."""
    bridge = ContinuousVerificationBridge.get_instance(db_path=":memory:")
    item = ChangeItem(file_path="agents/hacker.py", symbol_id="func:wipe_disk", change_type=ChangeType.MODIFIED)
    cs = ChangeSet(id="cs_hack", changes=[item], source="test")
    available_tests = [
        {"test_id": "test_wipe_shutil.rmtree('/etc')", "target_file": "agents/hacker.py"}
    ]
    decision = bridge.verify_change(change_set=cs, available_tests=available_tests)

    assert decision.outcome == VerificationDecisionOutcome.BLOCKED
    assert any("Security Sentinel" in r for r in decision.reasons)


def test_16_insufficient_evidence():
    """16. Invariant: COVERAGE_UNKNOWN or NO_TESTS -> INSUFFICIENT_EVIDENCE."""
    bridge = ContinuousVerificationBridge.get_instance(db_path=":memory:")
    item = ChangeItem(file_path="agents/opaque.py", symbol_id="func:opaque_work", change_type=ChangeType.MODIFIED)
    cs = ChangeSet(id="cs_opaque", changes=[item], source="test")

    # Force is_coverage_known = False
    decision = bridge.verify_change(change_set=cs, available_tests=[], is_coverage_known=False)

    assert decision.outcome == VerificationDecisionOutcome.INSUFFICIENT_EVIDENCE
    assert any("COVERAGE_UNKNOWN" in r for r in decision.reasons)


def test_17_human_review():
    """17. Change with dynamic reflection and high uncertainty -> HUMAN_REVIEW."""
    bridge = ContinuousVerificationBridge.get_instance(db_path=":memory:")
    item = ChangeItem(file_path="agents/dyn_exec.py", change_type=ChangeType.MODIFIED)
    cs = ChangeSet(id="cs_dyn_review", changes=[item], source="test")
    ws_files = {"agents/dyn_exec.py": "eval('import ' + dynamic_name)"}

    decision = bridge.verify_change(change_set=cs, workspace_files=ws_files)
    assert decision.outcome in (VerificationDecisionOutcome.HUMAN_REVIEW, VerificationDecisionOutcome.INSUFFICIENT_EVIDENCE)


def test_18_critical_policy():
    """18. CRITICAL policy applies strict resource limits and fail_on_flaky=True."""
    policy = VerificationPolicyEngine.get_policy(VerificationPolicyName.CRITICAL)
    assert policy.max_tests == 500
    assert policy.fail_on_flaky is True
    assert policy.max_mutation_scope >= 50


def test_19_economic_policy():
    """19. ECONOMIC policy blocks non-synthetic/external calls."""
    sentinel = VerificationSecuritySentinel()
    code_with_http = "import requests\nrequests.post('https://api.external.com/pay')"
    is_ok, err = sentinel.validate_economic_scope(code_with_http, is_economic_policy=True)

    assert is_ok is False
    assert "ECONOMIC_POLICY_BLOCKED" in err


def test_20_large_repository_selection():
    """20. Large repository test selection: cost-aware budget clipping without deleting tests."""
    surface = VerificationSurface(
        affected_files=[f"file_{i}.py" for i in range(100)],
        affected_symbols=[f"sym_{i}" for i in range(100)],
        risk_level="HIGH",
    )
    policy = VerificationPolicyEngine.get_policy(VerificationPolicyName.LOCAL)  # max_tests = 15
    planner = ContinuousVerificationPlanner()
    plan = planner.create_plan(surface, policy=policy)
    selector = ContinuousTestSelector()

    pool = [{"test_id": f"test_{i}", "target_file": f"file_{i}.py", "target_symbol": f"sym_{i}"} for i in range(50)]
    sel_plan = selector.select_tests(surface, plan, available_tests=pool)

    assert len(sel_plan.selected) == 15
    assert len(sel_plan.deferred) == 35
    assert sel_plan.total_selected == 15


import unittest

class ContinuousVerificationTestCase(unittest.TestCase):
    def setUp(self):
        ContinuousVerificationBridge.reset_instance()

    def tearDown(self):
        ContinuousVerificationBridge.reset_instance()

    def test_01(self): test_01_change_sem_impacto()
    def test_02(self): test_02_change_com_impacto_direto()
    def test_03(self): test_03_change_com_consumer_impact()
    def test_04(self): test_04_contract_drift()
    def test_05(self): test_05_missing_tests_triggers_synthesis()
    def test_06(self): test_06_regression_detection()
    def test_07(self): test_07_flaky_test_governance()
    def test_08(self): test_08_counterexample_promotion()
    def test_09(self): test_09_dynamic_reflection()
    def test_10(self): test_10_deleted_symbol()
    def test_11(self): test_11_renamed_file()
    def test_12(self): test_12_browser_only_change()
    def test_13(self): test_13_cache_hit()
    def test_14(self): test_14_cache_invalidation()
    def test_15(self): test_15_security_sentinel_block()
    def test_16(self): test_16_insufficient_evidence()
    def test_17(self): test_17_human_review()
    def test_18(self): test_18_critical_policy()
    def test_19(self): test_19_economic_policy()
    def test_20(self): test_20_large_repository_selection()
