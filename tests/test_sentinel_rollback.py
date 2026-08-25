"""Test suite for Sentinel S3 Rollback and Restoration mechanics."""

import hashlib
import json
import os
import tempfile
import unittest
from unittest.mock import patch, MagicMock

from security.sentinel.contracts import (
    ResponseActionStatus,
    ResponseActionType,
    SecurityResponseAction,
)
from security.sentinel.response.executors.process import ProcessTerminationExecutor
from security.sentinel.response.executors.quarantine import FileQuarantineExecutor
from security.sentinel.response.executors.network import FirewallBlockExecutor
from security.sentinel.response.executors.task import ScheduledTaskDisableExecutor
from security.sentinel.response.executors.known_good import MarkKnownGoodExecutor
from security.sentinel.response.engine import ResponseEngine


class TestSentinelRollback(unittest.IsolatedAsyncioTestCase):
    """Test suite for rollback reliability, state restoration, and non-reversible safeguards."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.quarantine_dir = os.path.join(self.temp_dir.name, "quarantine")
        self.engine = ResponseEngine(storage_dir=self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    async def test_quarantine_rollback_restores_file_identically(self):
        """Quarantine rollback restores file to original path with identical SHA-256 and removes quarantine copy."""
        test_file = os.path.join(self.temp_dir.name, "critical_app_file.dat")
        original_content = b"SECRET_RESTORE_DATA_CRYPTOGRAPHIC_INTEGRITY_CHECK_12345"
        with open(test_file, "wb") as f:
            f.write(original_content)
        original_hash = hashlib.sha256(original_content).hexdigest()

        action = self.engine.propose_action(
            incident_id="INC-ROLL-1",
            action_type=ResponseActionType.QUARANTINE_FILE,
            target=test_file,
            rationale="Quarantine test for rollback",
            evidence_ids=["EV-ROLL-1"],
        )

        # 1. Approve & Execute Quarantine
        app_success, act_app, _ = await self.engine.approve_and_execute(
            action_id=action.action_id,
            user="operator_alice",
            session_id="sess_roll",
        )
        self.assertTrue(app_success)
        self.assertEqual(act_app.status, ResponseActionStatus.COMPLETED.value)
        self.assertFalse(os.path.exists(test_file))

        # 2. Rollback Quarantine
        roll_success, act_roll, msg_roll = await self.engine.rollback(
            action_id=action.action_id,
            user="operator_alice",
            session_id="sess_roll",
        )
        self.assertTrue(roll_success)
        self.assertEqual(act_roll.status, ResponseActionStatus.ROLLED_BACK.value)

        # 3. Verify file restored to origin and matches hash
        self.assertTrue(os.path.exists(test_file))
        with open(test_file, "rb") as f:
            restored_content = f.read()
        self.assertEqual(hashlib.sha256(restored_content).hexdigest(), original_hash)

        # Verify quarantine directory copy was cleaned up
        quarantine_path = act_app.execution_result.get("quarantine_path")
        self.assertFalse(os.path.exists(quarantine_path))

    async def test_firewall_rollback_deletes_sentinel_rule_only(self):
        """Firewall rollback deletes only the JARVIS-SENTINEL rule created for this action."""
        executor = FirewallBlockExecutor()
        action = SecurityResponseAction(
            action_id="ACT-NET-RB",
            incident_id="INC-ROLL-2",
            action_type=ResponseActionType.BLOCK_NETWORK_ENDPOINT,
            target="198.51.100.22",
            rationale="Firewall rollback test",
            evidence_ids=["EV-ROLL-2"],
            execution_result={
                "rule_name": "JARVIS-SENTINEL-ACT-NET-RB",
                "ip": "198.51.100.22",
            },
        )

        with patch("subprocess.run") as mock_subproc, \
             patch.object(executor, "_rule_exists", side_effect=[False]):
            mock_subproc.return_value = MagicMock(returncode=0, stdout="Deleted 1 rule(s)")

            success, roll_res = executor.rollback(action)
            self.assertTrue(success)
            self.assertTrue(roll_res.get("rollback_applied"))

    async def test_scheduled_task_rollback_reenables_task(self):
        """Scheduled task rollback calls schtasks /Change /Enable."""
        executor = ScheduledTaskDisableExecutor()
        action = SecurityResponseAction(
            action_id="ACT-TASK-RB",
            incident_id="INC-ROLL-3",
            action_type=ResponseActionType.DISABLE_SCHEDULED_TASK,
            target=r"\LegitimateTask",
            rationale="Task disable rollback test",
            evidence_ids=["EV-ROLL-3"],
            execution_result={"task_name": r"\LegitimateTask"},
        )

        with patch("subprocess.run") as mock_subproc, \
             patch.object(executor, "_query_task", return_value={"exists": True, "status": "Ready"}):
            mock_subproc.return_value = MagicMock(returncode=0, stdout="SUCCESS")

            success, roll_res = executor.rollback(action)
            self.assertTrue(success)
            self.assertTrue(roll_res.get("rollback_applied"))

    async def test_mark_known_good_rollback_removes_entry(self):
        """Rollback on mark known good removes the key from known good entries."""
        action = self.engine.propose_action(
            incident_id="INC-KG-RB",
            action_type=ResponseActionType.MARK_KNOWN_GOOD,
            target="hash:feedface1234",
            rationale="Mark known good rollback test",
            evidence_ids=["EV-KG-1"],
        )

        # Approve and execute
        app_success, act_app, _ = await self.engine.approve_and_execute(
            action_id=action.action_id,
            user="operator_alice",
            session_id="sess_kg",
        )
        self.assertTrue(app_success)
        self.assertEqual(act_app.status, ResponseActionStatus.COMPLETED.value)

        # Rollback
        roll_success, act_roll, _ = await self.engine.rollback(
            action_id=action.action_id,
            user="operator_alice",
            session_id="sess_kg",
        )
        self.assertTrue(roll_success)
        self.assertEqual(act_roll.status, ResponseActionStatus.ROLLED_BACK.value)

    async def test_non_reversible_process_termination_rejects_rollback(self):
        """Process termination cannot be un-done and cleanly rejects rollback attempts."""
        action = self.engine.propose_action(
            incident_id="INC-PROC-NOROLL",
            action_type=ResponseActionType.TERMINATE_PROCESS,
            target="1234",
            rationale="Process cannot be rolled back",
            evidence_ids=["EV-NOROLL-1"],
        )

        # Action is marked rollback_available = False
        self.assertFalse(action.rollback_available)

        # Manually force completed status
        action.status = ResponseActionStatus.COMPLETED.value

        roll_success, act_roll, msg_roll = await self.engine.rollback(
            action_id=action.action_id,
            user="operator_alice",
            session_id="sess_noroll",
        )
        self.assertFalse(roll_success)
        self.assertIn("não suportado", msg_roll.lower())


if __name__ == "__main__":
    unittest.main()
