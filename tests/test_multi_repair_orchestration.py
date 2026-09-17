"""
JARVIS OS — Phase 55: Transactional Multi-Repair Orchestration & Convergence
Comprehensive test suite covering 22 test scenarios across clustering, DAG dependencies,
checkpoints, partial and global rollbacks, convergence, and security.
"""

import json
import os
import shutil
import tempfile
import pytest

from agents.multi_repair_orchestration.bridge import MultiRepairOrchestrationBridge
from agents.multi_repair_orchestration.checkpoint import RepairCheckpointManager
from agents.multi_repair_orchestration.cluster import FailureClusterer
from agents.multi_repair_orchestration.convergence import RepairConvergenceEngine
from agents.multi_repair_orchestration.dependencies import (
    DependencyCycleError,
    RepairDependencyAnalyzer,
)
from agents.multi_repair_orchestration.executor import TransactionalRepairExecutor
from agents.multi_repair_orchestration.graph import RepairGraphBuilder
from agents.multi_repair_orchestration.models import (
    ConflictType,
    ConvergenceState,
    FailureCluster,
    FailureItem,
    NodeRelationType,
    RepairCheckpoint,
    RepairTransaction,
    RevealedFailureType,
    TransactionProofResult,
    TransactionStatus,
    compute_deterministic_hash,
)
from agents.multi_repair_orchestration.planner import MultiRepairPlanner
from agents.multi_repair_orchestration.proof import TransactionProofEngine
from agents.multi_repair_orchestration.risk import TransactionRiskAggregator
from agents.multi_repair_orchestration.rollback import TransactionalRollbackEngine
from agents.multi_repair_orchestration.security import MultiRepairSecuritySentinel
from agents.multi_repair_orchestration.validator import (
    GlobalRepairValidator,
    IncrementalRepairValidator,
)


class MockDiff:
    def __init__(self, file_path: str, added_lines: list[str] | None = None):
        self.file_path = file_path
        self.added_lines = added_lines or ["// repaired line"]


class MockRepairCandidate:
    def __init__(
        self,
        repair_id: str,
        strategy_name: str = "SYNTHESIS",
        risk: float = 0.2,
        diffs: list[MockDiff] | None = None,
    ):
        self.repair_id = repair_id
        self.strategy_name = strategy_name
        self.risk = risk
        self.diffs = diffs or [MockDiff("test_file.js")]


@pytest.fixture
def temp_workspace():
    tmp_dir = tempfile.mkdtemp()
    yield tmp_dir
    shutil.rmtree(tmp_dir, ignore_errors=True)


def test_01_failure_clustering():
    clusterer = FailureClusterer()
    f1 = FailureItem("f1", "TypeError", "renderUser", "src/user.ts", 10, "Cannot read property of undefined")
    f2 = FailureItem("f2", "TypeError", "formatUser", "src/user.ts", 30, "Cannot format null")
    f3 = FailureItem("f3", "NetworkError", "fetchOrders", "src/orders.ts", 5, "Connection refused")

    clusters = clusterer.cluster_failures([f1, f2, f3])
    assert len(clusters) == 2
    # f1 and f2 share src/user.ts, so they cluster together
    user_cluster = next(c for c in clusters if "src/user.ts" in c.shared_files)
    assert len(user_cluster.failures) == 2
    assert "renderUser" in user_cluster.shared_symbols
    assert "formatUser" in user_cluster.shared_symbols


def test_02_repair_dag_construction():
    builder = RepairGraphBuilder()
    builder.add_node("rep_backend", "REPAIR", "Fix backend schema")
    builder.add_node("rep_frontend", "REPAIR", "Update frontend types")
    builder.add_edge("rep_frontend", "rep_backend", NodeRelationType.DEPENDS_ON)

    graph = builder.build_graph()
    assert len(graph.nodes) == 2
    assert len(graph.edges) == 1
    assert not builder.has_cycle(graph)


def test_03_dependency_ordering_topological():
    analyzer = RepairDependencyAnalyzer()
    # rep_consumer depends on rep_types, rep_types depends on rep_backend
    repairs = ["rep_consumer", "rep_types", "rep_backend"]
    dependencies = [("rep_backend", "rep_types"), ("rep_types", "rep_consumer")]

    order = analyzer.determine_execution_order(repairs, dependencies)
    assert order == ["rep_backend", "rep_types", "rep_consumer"]


def test_04_conflict_detection():
    planner = MultiRepairPlanner()
    c1 = MockRepairCandidate("rep_1", diffs=[MockDiff("src/App.tsx")])
    c2 = MockRepairCandidate("rep_2", diffs=[MockDiff("src/App.tsx")])

    conflict = planner.detect_conflicts([c1, c2])
    assert conflict.has_conflicts
    assert conflict.conflict_type == ConflictType.OVERLAPPING_PATCH
    assert conflict.requires_human_review


def test_05_checkpoint_creation_and_preservation(temp_workspace):
    file_path = os.path.join(temp_workspace, "sample.js")
    with open(file_path, "w", encoding="utf-8") as f:
        f.write("console.log('original');\n")

    mgr = RepairCheckpointManager()
    chk = mgr.create_checkpoint(
        transaction_id="tx_123",
        step_index=0,
        repair_id="rep_test",
        target_files=[file_path],
        patch_hash="patch_hash_1",
        verification_result="PRE_APPLY",
    )

    assert chk.step_index == 0
    assert chk.state_hash != ""
    assert file_path in chk.rollback_snapshot
    assert chk.rollback_snapshot[file_path] == "console.log('original');\n"


def test_06_incremental_step_verification(temp_workspace):
    validator = IncrementalRepairValidator()
    file_path = os.path.join(temp_workspace, "valid.js")
    with open(file_path, "w", encoding="utf-8") as f:
        f.write("function test() { return 1; }\n")

    res = validator.validate_step(MockRepairCandidate("rep_valid"), [file_path])
    assert res["success"]
    assert res["preflight_passed"]


def test_07_transaction_lifecycle_transitions():
    tx = RepairTransaction(
        transaction_id="tx_lifecycle",
        mission_id="m_life",
        cluster_id="c_life",
        repairs=[MockRepairCandidate("r1")],
        dependencies=[],
        status=TransactionStatus.PLANNED,
    )
    assert tx.status == TransactionStatus.PLANNED
    tx.status = TransactionStatus.GATED
    assert tx.status == TransactionStatus.GATED
    tx.status = TransactionStatus.EXECUTING
    assert tx.status == TransactionStatus.EXECUTING
    tx.status = TransactionStatus.COMMITTED
    assert tx.status == TransactionStatus.COMMITTED
    tx.status = TransactionStatus.PROVEN
    assert tx.status == TransactionStatus.PROVEN


def test_08_partial_rollback_to_checkpoint(temp_workspace):
    file_path = os.path.join(temp_workspace, "step.js")
    with open(file_path, "w", encoding="utf-8") as f:
        f.write("state_initial\n")

    mgr = RepairCheckpointManager()
    rollback = TransactionalRollbackEngine(mgr)

    # Checkpoint at Step 0
    chk0 = mgr.create_checkpoint("tx_partial", 0, "rep_0", [file_path], "p0", "OK")

    # Step 1 modifies file
    with open(file_path, "w", encoding="utf-8") as f:
        f.write("state_after_repair_A\n")
    chk1 = mgr.create_checkpoint("tx_partial", 1, "rep_1", [file_path], "p1", "OK")

    # Step 2 breaks file
    with open(file_path, "w", encoding="utf-8") as f:
        f.write("corrupted_state_repair_B\n")

    tx = RepairTransaction("tx_partial", "m1", "c1", [], [], checkpoints=[chk0, chk1])

    # Rollback to Checkpoint 1 (preserving repair A)
    ok, msg, audit = rollback.rollback_to_checkpoint(tx, chk1.checkpoint_id, [file_path])
    assert ok
    with open(file_path, "r", encoding="utf-8") as f:
        assert f.read() == "state_after_repair_A\n"
    assert audit["hash_verified"]


def test_09_global_transaction_rollback(temp_workspace):
    file_path = os.path.join(temp_workspace, "global.js")
    with open(file_path, "w", encoding="utf-8") as f:
        f.write("original_global_content\n")

    initial_snapshot = {file_path: "original_global_content\n"}
    initial_hash = compute_deterministic_hash(initial_snapshot)

    tx = RepairTransaction("tx_global", "m1", "c1", [], [], state_before_hash=initial_hash)

    # Apply multiple modifications
    with open(file_path, "w", encoding="utf-8") as f:
        f.write("heavily_modified_and_broken\n")

    rollback = TransactionalRollbackEngine()
    ok, msg, audit = rollback.rollback_global(tx, initial_snapshot, [file_path])

    assert ok
    with open(file_path, "r", encoding="utf-8") as f:
        assert f.read() == "original_global_content\n"
    assert audit["hash_verified"]
    assert tx.status == TransactionStatus.ROLLED_BACK


def test_10_revealed_failure_differentiation():
    conv = RepairConvergenceEngine()
    hidden_fail = FailureItem("f_revealed", "ReferenceError", "internalAuth", "src/auth.ts", 12, "Unbound token")
    
    # Pre-existing area that was unexercised until previous patch opened the path
    classified = conv.classify_failure(hidden_fail, pre_existing_untested_areas=["src/auth.ts"])
    assert classified == RevealedFailureType.REVEALED_FAILURE

    # Patch broke existing route
    regression = conv.classify_failure(hidden_fail, caused_by_patch=True)
    assert regression == RevealedFailureType.REGRESSION_FAILURE


def test_11_regression_failure_detection():
    validator = GlobalRepairValidator()
    tx = RepairTransaction("tx_reg", "m1", "c1", [], [])
    res = validator.validate_transaction(tx, [], simulated_regression=True)
    assert not res["success"]
    assert res["reason"] == "REGRESSION_DETECTED"


def test_12_convergence_achievement():
    conv = RepairConvergenceEngine()
    tx = RepairTransaction("tx_conv", "m1", "c1", [], [])
    f1 = FailureItem("f1", "Error", "main", "app.js", 1, "fail")

    state, details = conv.evaluate_convergence(
        transaction=tx,
        target_failures=[f1],
        active_failures=[],  # All resolved!
        invariants_satisfied=True,
    )
    assert state == ConvergenceState.CONVERGED
    assert details["resolved_count"] == 1


def test_13_divergence_detection():
    conv = RepairConvergenceEngine()
    tx = RepairTransaction("tx_div", "m1", "c1", [], [])
    f1 = FailureItem("f1", "Error", "main", "app.js", 1, "fail")
    f_reg = FailureItem("f_reg", "Error", "main", "app.js", 2, "new reg", failure_type=RevealedFailureType.REGRESSION_FAILURE)

    state, details = conv.evaluate_convergence(
        transaction=tx,
        target_failures=[f1],
        active_failures=[f1, f_reg],
        invariants_satisfied=False,
    )
    assert state == ConvergenceState.BLOCKED or state == ConvergenceState.DIVERGING


def test_14_stalled_transaction_handling():
    conv = RepairConvergenceEngine()
    tx = RepairTransaction("tx_stall", "m1", "c1", [], [])
    f1 = FailureItem("f1", "Error", "main", "app.js", 1, "fail")

    state, details = conv.evaluate_convergence(
        transaction=tx,
        target_failures=[f1],
        active_failures=[f1],  # None resolved
        iteration_count=5,
        max_iterations=5,
    )
    assert state == ConvergenceState.STALLED


def test_15_multidimensional_risk_aggregation():
    agg = TransactionRiskAggregator()
    cluster = FailureCluster("c1", "TypeError", ["user.js", "order.js"], ["symbolA"], ["ContractA"], ["ConsumerA"], [], [])
    c1 = MockRepairCandidate("r1", risk=0.4)
    c2 = MockRepairCandidate("r2", risk=0.7)

    risk = agg.aggregate_risk(cluster, [c1, c2])
    assert risk.blast_radius >= 4
    assert risk.max_repair_risk == 0.7
    assert risk.aggregated_risk_score >= 0.7


def test_16_economic_transaction_human_gate():
    planner = MultiRepairPlanner()
    cand = MockRepairCandidate("r_econ", strategy_name="ECONOMIC_MUTATION_BYPASS")
    conflict = planner.detect_conflicts([cand])

    assert conflict.has_conflicts
    assert conflict.conflict_type == ConflictType.ECONOMIC_CONFLICT
    assert conflict.requires_human_review


def test_17_security_sentinel_patch_chaining_block():
    sentinel = MultiRepairSecuritySentinel()
    # Patch A defines a dynamic function loader, Patch B executes it
    d1 = MockDiff("loader.js", ["const createFn = (code) => new Function(code);"])
    d2 = MockDiff("trigger.js", ["window.createFn('exploit');"])
    
    c1 = MockRepairCandidate("c1", diffs=[d1])
    c2 = MockRepairCandidate("c2", diffs=[d2])
    tx = RepairTransaction("tx_sec", "m1", "c1", [c1, c2], [])

    ok, msg, details = sentinel.validate_transaction(tx)
    assert not ok
    assert "Malicious patch chaining detected" in msg


def test_18_browser_smoke_validation_in_transaction():
    validator = GlobalRepairValidator()
    tx = RepairTransaction("tx_browser", "m1", "c1", [], [])
    res = validator.validate_transaction(tx, [], simulated_browser_failure=True)
    assert not res["success"]
    assert res["reason"] == "BROWSER_SMOKE_FAILED"


def test_19_multi_repair_proof_synthesis():
    engine = TransactionProofEngine()
    tx = RepairTransaction("tx_proof", "m1", "c1", [MockRepairCandidate("r1")], [], state_before_hash="h_before", state_after_hash="h_after")

    proof = engine.synthesize_proof(
        transaction=tx,
        behavior_proof={"success": True},
        regression_proof={"success": True},
        security_validation={"success": True},
        economic_validation={"success": True},
        rollback_validation={"success": True},
        convergence_status=ConvergenceState.CONVERGED,
        coverage_score=0.95,
    )

    assert proof.result == TransactionProofResult.TRANSACTION_PROVEN
    assert "BOUNDED_BEHAVIORAL_CONVERGENCE_PROVEN" in proof.invariants
    assert proof.before_hash == "h_before"
    assert proof.after_hash == "h_after"


def test_20_deterministic_replay():
    h1 = compute_deterministic_hash({"a": 1, "b": ["x", "y"]})
    h2 = compute_deterministic_hash({"b": ["x", "y"], "a": 1})
    assert h1 == h2


def test_21_transaction_serialization_roundtrip():
    tx = RepairTransaction(
        transaction_id="tx_serial",
        mission_id="m_ser",
        cluster_id="c_ser",
        repairs=[MockRepairCandidate("r_ser")],
        dependencies=[("r_ser", "r_other")],
        state_before_hash="sbh",
        state_after_hash="sah",
    )
    raw_dict = tx.to_dict()
    json_str = json.dumps(raw_dict)
    loaded = json.loads(json_str)

    assert loaded["transaction_id"] == "tx_serial"
    assert loaded["state_before_hash"] == "sbh"
    assert loaded["state_after_hash"] == "sah"


def test_22_crash_recovery_from_persisted_checkpoint():
    bridge = MultiRepairOrchestrationBridge()
    persisted = {
        "transaction_id": "tx_crash",
        "checkpoints": [
            {"checkpoint_id": "chk_0", "step_index": 0},
            {"checkpoint_id": "chk_1", "step_index": 1},
        ]
    }
    ok, msg, last_chk = bridge.recover_from_crash("tx_crash", persisted)
    assert ok
    assert last_chk == "chk_1"
