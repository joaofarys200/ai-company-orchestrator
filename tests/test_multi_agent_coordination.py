"""
JARVIS OS — Phase 66: Multi-Agent Engineering Coordination & Conflict Arbitration
Comprehensive Test Suite covering all 20 required verification dimensions.
"""

import os
import shutil
import tempfile
import unittest

from backend.agents.multi_agent_coordination import (
    AgentChangeSet,
    AgentConflict,
    AgentEngineeringIntent,
    AgentPriorityModel,
    ArbitrationDecision,
    ArbitrationResolution,
    ClaimType,
    ConflictType,
    DeadlockState,
    IntentState,
    MergeResult,
    MultiAgentCoordinationBridge,
    RebaseResult,
    ResourceClaim,
    ResourceGranularity,
    SchedulingDecision,
)
from backend.agents.multi_agent_coordination.claims import ClaimManager
from backend.agents.multi_agent_coordination.conflicts import AgentConflictDetector
from backend.agents.multi_agent_coordination.dependencies import CoordinationDependencyAnalyzer
from backend.agents.multi_agent_coordination.intent import IntentManager
from backend.agents.multi_agent_coordination.merge import CoordinationMergeEngine
from backend.agents.multi_agent_coordination.rebase import RebaseEngine
from backend.agents.multi_agent_coordination.security import SecuritySentinel
from backend.agents.multi_agent_coordination.verification import SharedVerificationManager
from backend.agents.multi_agent_coordination.workspace import WorkspaceIsolationManager


class TestMultiAgentCoordination(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp(prefix="jarvis_phase66_test_")
        self.bridge = MultiAgentCoordinationBridge(
            workspace_root=self.tmp_dir,
            db_path=":memory:",
            policy_name="STANDARD",
        )

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    # 1. Intent Validation
    def test_01_intent_validation(self):
        it_valid = AgentEngineeringIntent(
            agent_id="agent_1",
            mission_id="m1",
            task_id="t1",
            intent_id="i1",
            requested_files=["backend/api.py"],
            requested_symbols=["handle_request"],
            requested_contracts=["APIContract"],
            expected_changes=["Add auth header check"],
            expected_effect="Secure endpoints",
        )
        ok, msg = self.bridge.intent_mgr.register_intent(it_valid)
        self.assertTrue(ok)
        val_ok, val_msg = self.bridge.intent_mgr.validate_intent("i1")
        self.assertTrue(val_ok)
        self.assertEqual(it_valid.state, IntentState.VALIDATED)

        # Invalid intent without agent_id or empty changes
        it_invalid = AgentEngineeringIntent(
            agent_id="",
            mission_id="m1",
            task_id="t2",
            intent_id="i2",
        )
        ok_inv, msg_inv = self.bridge.intent_mgr.register_intent(it_invalid)
        self.assertFalse(ok_inv)

    # 2. Resource Claims
    def test_02_claims_compatibility_and_expiration(self):
        claim_mgr = ClaimManager()
        c1 = ResourceClaim(
            claim_id="c1",
            intent_id="i1",
            agent_id="a1",
            resource_uri="backend/api.py",
            granularity=ResourceGranularity.FILE,
            claim_type=ClaimType.READ,
            ttl_seconds=1.0,
        )
        c2 = ResourceClaim(
            claim_id="c2",
            intent_id="i2",
            agent_id="a2",
            resource_uri="backend/api.py",
            granularity=ResourceGranularity.FILE,
            claim_type=ClaimType.READ,
            ttl_seconds=1.0,
        )
        # READ + READ is compatible
        self.assertTrue(claim_mgr.is_compatible(c1, c2))

        # READ + WRITE is potentially incompatible / conflict
        c3 = ResourceClaim(
            claim_id="c3",
            intent_id="i3",
            agent_id="a3",
            resource_uri="backend/api.py",
            granularity=ResourceGranularity.FILE,
            claim_type=ClaimType.WRITE,
            ttl_seconds=1.0,
        )
        self.assertFalse(claim_mgr.is_compatible(c1, c3))

        # Test claim release
        ok, _, _ = claim_mgr.acquire_claim(c1)
        self.assertTrue(ok)
        self.assertIn("c1", claim_mgr.active_claims)
        claim_mgr.release_claim("c1")
        self.assertNotIn("c1", claim_mgr.active_claims)

    # 3. Dependency Graph
    def test_03_dependency_graph(self):
        dep_analyzer = CoordinationDependencyAnalyzer()
        it_a = AgentEngineeringIntent(
            agent_id="a1", mission_id="m1", task_id="t1", intent_id="i1",
            requested_files=["backend/core.py"],
        )
        it_b = AgentEngineeringIntent(
            agent_id="a2", mission_id="m1", task_id="t2", intent_id="i2",
            requested_files=["frontend/app.tsx"],
            dependencies=["i1"],
        )
        res = dep_analyzer.build_dependency_graph([it_a, it_b])
        self.assertFalse(res["has_cycle"])
        self.assertEqual(res["topological_order"], ["i1", "i2"])

    # 4. Conflict Detection
    def test_04_conflict_detection(self):
        detector = AgentConflictDetector()
        it_a = AgentEngineeringIntent(
            agent_id="a1", mission_id="m1", task_id="t1", intent_id="i1",
            requested_files=["backend/routes.py"],
            requested_symbols=["login"],
            requested_contracts=["AuthContract"],
        )
        it_b = AgentEngineeringIntent(
            agent_id="a2", mission_id="m1", task_id="t2", intent_id="i2",
            requested_files=["backend/routes.py"],
            requested_symbols=["login"],
            requested_contracts=["AuthContract"],
        )
        conflicts = detector.detect_conflicts([it_a, it_b])
        self.assertGreaterEqual(len(conflicts), 2)  # SYMBOL_CONFLICT and CONTRACT_CONFLICT detected

    # 5. Arbitration
    def test_05_arbitration_strategies(self):
        it_a = AgentEngineeringIntent(
            agent_id="a1", mission_id="m1", task_id="t1", intent_id="i1",
            requested_files=["backend/routes.py"],
            requested_symbols=["auth_token"],
            priority=0.9,
        )
        it_b = AgentEngineeringIntent(
            agent_id="a2", mission_id="m1", task_id="t2", intent_id="i2",
            requested_files=["backend/routes.py"],
            requested_symbols=["auth_token"],
            priority=0.4,
        )
        conf = AgentConflict(
            conflict_id="conf_sym",
            intent_a="i1",
            intent_b="i2",
            resource="backend/routes.py#auth_token",
            conflict_type=ConflictType.SYMBOL_CONFLICT,
            severity="HIGH",
        )
        decision = self.bridge.arbiter.arbitrate_conflict(conf, it_a, it_b)
        self.assertEqual(decision.resolution, ArbitrationResolution.SERIALIZE)
        self.assertEqual(decision.preferred_order, ["i1", "i2"])

    # 6. Parallel Scheduling
    def test_06_parallel_scheduling_safety(self):
        # Two completely disjoint intents should be scheduled PARALLEL_SAFE
        it_fe = AgentEngineeringIntent(
            agent_id="a_fe", mission_id="m1", task_id="t_fe", intent_id="i_fe",
            requested_files=["frontend/Button.tsx"],
        )
        it_be = AgentEngineeringIntent(
            agent_id="a_be", mission_id="m1", task_id="t_be", intent_id="i_be",
            requested_files=["backend/logger.py"],
        )
        sched = self.bridge.scheduler.schedule_intents([it_fe, it_be])
        self.assertEqual(sched["decision"], SchedulingDecision.PARALLEL_SAFE.value)
        self.assertEqual(len(sched["parallel_waves"]), 1)
        self.assertEqual(len(sched["parallel_waves"][0]), 2)

    # 7. Workspace Isolation
    def test_07_workspace_isolation(self):
        ws_mgr = WorkspaceIsolationManager(self.tmp_dir)
        ws_a = ws_mgr.create_isolated_workspace("a1", "tx_1", "snap_1")
        ws_b = ws_mgr.create_isolated_workspace("a2", "tx_2", "snap_1")
        self.assertNotEqual(ws_a.workspace_id, ws_b.workspace_id)
        self.assertNotEqual(ws_a.isolated_path, ws_b.isolated_path)
        self.assertTrue(os.path.exists(ws_a.isolated_path))
        self.assertTrue(os.path.exists(ws_b.isolated_path))

    # 8. Merge
    def test_08_merge_engine(self):
        merge_engine = CoordinationMergeEngine()
        base = {"src/calc.py": "def add(a, b):\n    return a + b\n\ndef sub(a, b):\n    return a - b\n"}
        cs_a = AgentChangeSet(
            changeset_id="cs_a",
            agent_id="a1",
            intent_id="i1",
            transaction_id="tx_1",
            base_snapshot="snap_0",
            patch={"src/calc.py": "def add(a, b):\n    # Optimized\n    return a + b\n\ndef sub(a, b):\n    return a - b\n"},
            affected_files=["src/calc.py"],
            affected_symbols=["add"],
        )
        cs_b = AgentChangeSet(
            changeset_id="cs_b",
            agent_id="a2",
            intent_id="i2",
            transaction_id="tx_2",
            base_snapshot="snap_0",
            patch={"src/calc.py": "def add(a, b):\n    return a + b\n\ndef sub(a, b):\n    # Validated\n    return a - b\n"},
            affected_files=["src/calc.py"],
            affected_symbols=["sub"],
        )
        res = merge_engine.merge_changesets(base, cs_a, cs_b)
        self.assertTrue(res.success)
        self.assertIn("Optimized", res.merged_files["src/calc.py"])
        self.assertIn("Validated", res.merged_files["src/calc.py"])

    # 9. Rebase
    def test_09_rebase_engine(self):
        rebase_engine = RebaseEngine()
        cs = AgentChangeSet(
            changeset_id="cs_1",
            agent_id="a1",
            intent_id="i1",
            transaction_id="tx_1",
            base_snapshot="snap_old",
            patch={"src/hello.py": "def hello():\n    return 'hello world'\n"},
            affected_files=["src/hello.py"],
        )
        new_base = {"src/hello.py": "def hello():\n    return 'hello'\n\ndef greet():\n    return 'welcome'\n"}
        res = rebase_engine.rebase_changeset(cs, "snap_new", new_base)
        self.assertTrue(res.success)
        self.assertEqual(res.new_base_snapshot, "snap_new")

    # 10. Stale Base Detection
    def test_10_stale_base_detection(self):
        cs = AgentChangeSet(
            changeset_id="cs_stale",
            agent_id="a1",
            intent_id="i1",
            transaction_id="tx_1",
            base_snapshot="snap_old_hash",
            patch={"src/config.py": "PORT = 9000\n"},
            affected_files=["src/config.py"],
        )
        latest_snap = "snap_new_hash"
        self.assertTrue(cs.is_stale(latest_snap))
        self.assertFalse(cs.is_stale("snap_old_hash"))

    # 11. Deadlock Detection
    def test_11_deadlock_detection_and_resolution(self):
        it_a = AgentEngineeringIntent(
            agent_id="a1", mission_id="m1", task_id="t1", intent_id="i1",
            dependencies=["i2"],  # i1 waits on i2
        )
        it_b = AgentEngineeringIntent(
            agent_id="a2", mission_id="m1", task_id="t2", intent_id="i2",
            dependencies=["i1"],  # i2 waits on i1 -> Cycle
        )
        res = self.bridge.detect_deadlocks([it_a, it_b])
        self.assertTrue(res["has_deadlock"])
        self.assertEqual(res["state"], DeadlockState.DEADLOCK.value)

    # 12. Starvation Detection
    def test_12_starvation_detection_and_prevention(self):
        it_starved = AgentEngineeringIntent(
            agent_id="a_low", mission_id="m1", task_id="t_low", intent_id="i_low",
            wait_count=5, priority=0.1,
        )
        it_high = AgentEngineeringIntent(
            agent_id="a_high", mission_id="m1", task_id="t_high", intent_id="i_high",
            wait_count=0, priority=0.9,
        )
        res = self.bridge.detect_starvation([it_high, it_starved], max_wait_count=4)
        self.assertTrue(res["starvation_detected"])
        self.assertIn("i_low", res["starved_intents"])
        self.assertEqual(res["boosted_order"][0], "i_low")  # Fair boost prioritizes starved

    # 13. Security Conflict
    def test_13_security_conflict_block(self):
        sec = SecuritySentinel()
        # Protected files (.env, secrets, credentials) must be blocked
        is_safe, msg = sec.validate_file_safety(".env")
        self.assertFalse(is_safe)
        self.assertIn("SECURITY_BLOCK", msg)

        is_safe_src, msg_src = sec.validate_file_safety("backend/core/logic.py")
        self.assertTrue(is_safe_src)

    # 14. Shared Verification
    def test_14_shared_verification(self):
        verif_mgr = SharedVerificationManager()
        cs = AgentChangeSet(
            changeset_id="cs_1", agent_id="a1", intent_id="i1", transaction_id="tx_1",
            base_snapshot="snap_1", patch={}, affected_files=["backend/api.py"],
        )
        # 0 tests found rule: 0 tests cannot evaluate as PASS
        res_zero = verif_mgr.run_shared_verification([cs], ["backend/api.py"], [])
        self.assertFalse(res_zero["success"])
        self.assertEqual(res_zero["evidence"]["tests_evaluated"], 0)

        # Non-zero tests evaluated
        res_valid = verif_mgr.run_shared_verification([cs], ["backend/api.py"], ["test_api_endpoints"])
        self.assertTrue(res_valid["success"])
        self.assertGreater(res_valid["evidence"]["tests_evaluated"], 0)

    # 15. Provenance Graph
    def test_15_provenance_graph(self):
        prov = self.bridge.provenance_tracker.record_coordination_event(
            agent_id="a1",
            mission_id="m1",
            intent_id="i1",
            claim_ids=["c1", "c2"],
            transaction_id="tx_1",
            base_snapshot="snap_0",
            patch_hash="p_hash_abc",
            merge_hash="m_hash_def",
            verification_hash="v_hash_123",
        )
        self.assertEqual(prov.agent_id, "a1")
        self.assertEqual(prov.transaction_id, "tx_1")
        self.assertIn("tx_1", self.bridge.provenance_tracker.events)

    # 16. Convergence
    def test_16_convergence_budget_enforcement(self):
        gov = self.bridge.convergence_gov
        # Under budget
        state, msg = gov.record_wave(conflicts_count=2)
        self.assertIn(state.value, ["CONVERGING", "STABLE"])

        # Exceeding budget
        gov.current_retries = 20
        gov.max_conflict_retries = 5
        state_ex, msg_ex = gov.record_wave(conflicts_count=5)
        self.assertEqual(state_ex.value, "BLOCKED")

    # 17. Unseen Multi-Agent Task
    def test_17_unseen_multi_agent_task(self):
        # Scenario: 3 agents attempting coordinated changes with 1 dependency
        it_core = AgentEngineeringIntent(
            agent_id="a_core", mission_id="m_unseen", task_id="t_core", intent_id="i_core",
            requested_files=["backend/service.py"],
            requested_symbols=["process_payment"],
        )
        it_audit = AgentEngineeringIntent(
            agent_id="a_audit", mission_id="m_unseen", task_id="t_audit", intent_id="i_audit",
            requested_files=["backend/audit.py"],
            requested_symbols=["log_audit"],
            dependencies=["i_core"],
        )
        coord_res = self.bridge.coordinate_intents([it_core, it_audit])
        self.assertTrue(coord_res["success"])
        self.assertEqual(len(coord_res["schedule"]["parallel_waves"]), 2)

    # 18. Denominator Reconciliation
    def test_18_denominator_reconciliation(self):
        from backend.agents.multi_agent_coordination.validator import CoordinationGateValidator
        validator = CoordinationGateValidator()
        # Sum of per_phase must equal total declared with delta == 0
        per_phase = {"F40": 10, "F55": 8, "F56": 12, "F60": 15, "F62": 20, "F66": 20}
        total = sum(per_phase.values())
        reconciliation = validator.reconcile_denominators(per_phase, total)
        self.assertTrue(reconciliation["valid"])
        self.assertEqual(reconciliation["delta"], 0)

        # Mismatched total must fail
        bad_reconciliation = validator.reconcile_denominators(per_phase, total + 5)
        self.assertFalse(bad_reconciliation["valid"])
        self.assertEqual(bad_reconciliation["delta"], -5)

    # 19. Cache Invalidation
    def test_19_cache_invalidation(self):
        cache = self.bridge.cache
        key = cache.compute_key("i_hash_1", "snap_0", "res_hash_a", "STANDARD", "v1")
        cache.put(key, {"cached": True, "data": 42})
        self.assertIsNotNone(cache.get(key))

        # Invalidation
        cache.invalidate_intent("i_hash_1")
        self.assertIsNone(cache.get(key))

    # 20. Rollback After Merge
    def test_20_rollback_after_merge(self):
        ws_mgr = self.bridge.workspace_mgr
        ws = ws_mgr.create_isolated_workspace("a1", "tx_rb", "snap_orig")
        test_file = os.path.join(ws.isolated_path, "sample.txt")
        with open(test_file, "w", encoding="utf-8") as f:
            f.write("original content")

        # Create snapshot
        snap_mgr = ws_mgr
        snap = snap_mgr.create_snapshot("tx_rb")

        # Mutate file (simulating unsafe merge or test failure)
        with open(test_file, "w", encoding="utf-8") as f:
            f.write("corrupted or failing mutation")

        # Execute rollback
        rb_ok = snap_mgr.rollback_to_snapshot("tx_rb", snap)
        self.assertTrue(rb_ok)
        with open(test_file, "r", encoding="utf-8") as f:
            restored = f.read()
        self.assertEqual(restored, "original content")


if __name__ == "__main__":
    unittest.main()
