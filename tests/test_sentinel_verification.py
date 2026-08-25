"""Test suite for Sentinel S3 Empirical Post-State Verification."""

import hashlib
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
from security.sentinel.response.engine import ResponseEngine


class TestSentinelVerification(unittest.IsolatedAsyncioTestCase):
    """Test suite ensuring empirical post-state verification is enforced and never relies on exit codes."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.quarantine_dir = os.path.join(self.temp_dir.name, "quarantine")
        self.engine = ResponseEngine(storage_dir=self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    async def test_process_termination_verified_by_pid_absence(self):
        """Process termination verification checks that PID no longer exists in the OS process table."""
        executor = ProcessTerminationExecutor()
        action = SecurityResponseAction(
            action_id="ACT-PROC-VERIFY",
            incident_id="INC-V1",
            action_type=ResponseActionType.TERMINATE_PROCESS,
            target="99999",
            rationale="Test process termination verification",
            evidence_ids=["EV-V1"],
            pre_state={"pid": 99999, "name": "suspicious.exe", "create_time": 123456789},
        )

        # Case 1: PID is gone -> Verified True
        with patch("psutil.pid_exists", return_value=False):
            verified, verify_res = executor.verify(action)
            self.assertTrue(verified)
            self.assertTrue(verify_res.get("verified"))

        # Case 2: PID still exists with same create_time -> Verified False
        with patch("psutil.pid_exists", return_value=True), \
             patch("psutil.Process") as mock_proc_cls:
            mock_proc = MagicMock()
            mock_proc.create_time.return_value = 123456789
            mock_proc_cls.return_value = mock_proc

            verified, verify_res = executor.verify(action)
            self.assertFalse(verified)
            self.assertIn("continua ativo", verify_res.get("reason", "").lower())

    async def test_quarantine_verified_by_source_absence_and_hash_match(self):
        """Quarantine verification checks that file is absent at original path AND present in quarantine with identical SHA-256."""
        # Create dummy file to quarantine
        test_file = os.path.join(self.temp_dir.name, "suspicious_payload.bin")
        content = b"DEFENSIVE_SECURITY_TEST_PAYLOAD_12345"
        with open(test_file, "wb") as f:
            f.write(content)
        content_hash = hashlib.sha256(content).hexdigest()

        action = self.engine.propose_action(
            incident_id="INC-QUAR-V",
            action_type=ResponseActionType.QUARANTINE_FILE,
            target=test_file,
            rationale="Suspicious unindexed binary",
            evidence_ids=["EV-QUAR-1"],
        )

        # Approve and execute
        success, act, msg = await self.engine.approve_and_execute(
            action_id=action.action_id,
            user="operator_alice",
            session_id="sess_1",
        )

        self.assertTrue(success)
        self.assertEqual(act.status, ResponseActionStatus.COMPLETED.value)
        self.assertFalse(os.path.exists(test_file))  # File removed from source

        # Check quarantine post-state
        self.assertTrue(act.verification_result.get("verified"))
        self.assertEqual(act.verification_result.get("post_state", {}).get("sha256"), content_hash)

    async def test_firewall_rule_verified_by_query(self):
        """Firewall block verification queries Windows Firewall to prove rule existence."""
        executor = FirewallBlockExecutor()
        action = SecurityResponseAction(
            action_id="ACT-NET-VERIFY",
            incident_id="INC-V2",
            action_type=ResponseActionType.BLOCK_NETWORK_ENDPOINT,
            target="198.51.100.77",
            rationale="C2 beaconing endpoint",
            evidence_ids=["EV-V2"],
        )

        with patch.object(executor, "_rule_exists", return_value=True):
            verified, verify_res = executor.verify(action)
            self.assertTrue(verified)
            self.assertTrue(verify_res.get("verified"))

        with patch.object(executor, "_rule_exists", return_value=False):
            verified, verify_res = executor.verify(action)
            self.assertFalse(verified)
            self.assertIn("não foi encontrada", verify_res.get("reason", "").lower())

    async def test_verification_failure_marks_action_failed(self):
        """If verification fails after execution, action status is set to FAILED."""
        # Create action for firewall block but mock verification as False
        action = self.engine.propose_action(
            incident_id="INC-FAIL-V",
            action_type=ResponseActionType.BLOCK_NETWORK_ENDPOINT,
            target="198.51.100.88",
            rationale="Test verification failure",
            evidence_ids=["EV-FAIL-1"],
        )

        # Mock execute success but verify failure
        with patch.object(self.engine._executors[ResponseActionType.BLOCK_NETWORK_ENDPOINT], "pre_check", return_value=(True, "OK")), \
             patch.object(self.engine._executors[ResponseActionType.BLOCK_NETWORK_ENDPOINT], "execute", return_value={"success": True}), \
             patch.object(self.engine._executors[ResponseActionType.BLOCK_NETWORK_ENDPOINT], "verify", return_value=(False, {"verified": False, "reason": "Rule not active in profile"})):

            success, act, msg = await self.engine.approve_and_execute(
                action_id=action.action_id,
                user="operator_alice",
                session_id="sess_1",
            )

            self.assertFalse(success)
            self.assertEqual(act.status, ResponseActionStatus.FAILED.value)
            self.assertIn("verificação empírica falhou", act.error_message.lower())


if __name__ == "__main__":
    unittest.main()
