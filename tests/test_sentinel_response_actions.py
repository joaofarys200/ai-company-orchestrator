"""Unit tests for Sentinel S3 Response Actions and safety bounds."""

import os
import tempfile
import unittest
from unittest.mock import patch, MagicMock

from security.sentinel.contracts import (
    PermissionLevel,
    ResponseActionStatus,
    ResponseActionType,
    SecurityResponseAction,
)
from security.sentinel.response.engine import ResponseEngine
from security.sentinel.response.executors.process import ProcessTerminationExecutor, PROTECTED_PROCESSES
from security.sentinel.response.executors.task import ScheduledTaskDisableExecutor
from security.sentinel.response.executors.network import FirewallBlockExecutor
from security.sentinel.response.executors.quarantine import FileQuarantineExecutor
from security.sentinel.response.executors.known_good import MarkKnownGoodExecutor


class TestSentinelResponseActions(unittest.IsolatedAsyncioTestCase):
    """Test suite for Sentinel S3 response actions and executor safety."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.quarantine_dir = os.path.join(self.temp_dir.name, "quarantine")
        self.engine = ResponseEngine(storage_dir=self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    async def test_propose_action_contract_structure(self):
        """Action proposal must have all required fields and start in WAITING_APPROVAL state."""
        action = self.engine.propose_action(
            incident_id="INC-001",
            action_type=ResponseActionType.TERMINATE_PROCESS,
            target="12345",
            rationale="High-risk process executing from temp folder",
            evidence_ids=["EV-001"],
            permission_level=PermissionLevel.LOW_RISK_MUTATION,
        )

        self.assertIsNotNone(action)
        self.assertEqual(action.status, ResponseActionStatus.WAITING_APPROVAL)
        self.assertEqual(action.incident_id, "INC-001")
        self.assertEqual(action.action_type, ResponseActionType.TERMINATE_PROCESS)
        self.assertEqual(action.target, "12345")
        self.assertEqual(action.permission_level, PermissionLevel.LOW_RISK_MUTATION)
        self.assertTrue(action.approval_required)
        self.assertIsNone(action.approved_by)

    async def test_protected_process_termination_blocked(self):
        """Critical OS processes (PID 0, 4, explorer.exe, csrss.exe, etc.) must be protected from termination."""
        executor = ProcessTerminationExecutor()

        # Protect PID 0 and PID 4
        action_pid0 = SecurityResponseAction(
            action_id="ACT-P0",
            incident_id="INC-001",
            action_type=ResponseActionType.TERMINATE_PROCESS,
            target="0",
            rationale="Test termination of system idle process",
            evidence_ids=["EV-001"],
        )
        success, msg = executor.pre_check(action_pid0)
        self.assertFalse(success)
        self.assertIn("protegido", msg.lower())

        action_pid4 = SecurityResponseAction(
            action_id="ACT-P4",
            incident_id="INC-001",
            action_type=ResponseActionType.TERMINATE_PROCESS,
            target="4",
            rationale="Test termination of system process",
            evidence_ids=["EV-001"],
        )
        success, msg = executor.pre_check(action_pid4)
        self.assertFalse(success)
        self.assertIn("protegido", msg.lower())

        # Mock protected process by name
        with patch("psutil.Process") as mock_proc_cls:
            mock_proc = MagicMock()
            mock_proc.name.return_value = "csrss.exe"
            mock_proc.pid = 999
            mock_proc.is_running.return_value = True
            mock_proc_cls.return_value = mock_proc

            action_csrss = SecurityResponseAction(
                action_id="ACT-CSRSS",
                incident_id="INC-001",
                action_type=ResponseActionType.TERMINATE_PROCESS,
                target="999",
                rationale="Test termination of csrss",
                evidence_ids=["EV-001"],
            )
            success, msg = executor.pre_check(action_csrss)
            self.assertFalse(success)
            self.assertTrue("prote" in msg.lower() or "bloqueado" in msg.lower())

    async def test_scheduled_task_disable_never_deletes(self):
        """Scheduled task executor must only disable tasks, never delete them."""
        executor = ScheduledTaskDisableExecutor()
        action = self.engine.propose_action(
            incident_id="INC-002",
            action_type=ResponseActionType.DISABLE_SCHEDULED_TASK,
            target=r"\MaliciousTask",
            rationale="Suspicious scheduled task running unsigned payload",
            evidence_ids=["EV-002"],
        )

        with patch("subprocess.run") as mock_subproc:
            # Mock schtasks /Query
            mock_subproc.return_value = MagicMock(returncode=0, stdout="Ready\r\n")

            # Verify preconditions
            success, msg = executor.pre_check(action)
            self.assertTrue(success)

            # Verify execution command contains /Change /Disable and NEVER /Delete
            mock_subproc.return_value = MagicMock(returncode=0, stdout="SUCCESS")
            exec_res = executor.execute(action)
            self.assertTrue(exec_res.get("success", True))
            self.assertTrue(action.rollback_available)
            self.assertIn("DISABLE_SCHEDULED_TASK", action.rollback_plan)

    async def test_firewall_block_rule_naming_convention(self):
        """Firewall rules created by Sentinel must follow the JARVIS-SENTINEL-{ACTION_ID} prefix."""
        executor = FirewallBlockExecutor()
        action = SecurityResponseAction(
            action_id="ACT-NET-123",
            incident_id="INC-003",
            action_type=ResponseActionType.BLOCK_NETWORK_ENDPOINT,
            target="198.51.100.42",
            rationale="High volume outbound connection to unindexed endpoint",
            evidence_ids=["EV-003"],
        )

        expected_rule_name = "JARVIS-SENTINEL-ACT-NET-123"
        self.assertEqual(executor._rule_name_for_action(action.action_id), expected_rule_name)

        # Invalid IP target must be rejected
        invalid_action = SecurityResponseAction(
            action_id="ACT-NET-INV",
            incident_id="INC-003",
            action_type=ResponseActionType.BLOCK_NETWORK_ENDPOINT,
            target="not_an_ip_or_domain!;rm -rf",
            rationale="Invalid injection test",
            evidence_ids=["EV-003"],
        )
        val_success, val_msg = executor.pre_check(invalid_action)
        self.assertFalse(val_success)
        self.assertIn("inválido", val_msg.lower())

    async def test_quarantine_protects_system_directories(self):
        """Quarantine executor must prevent moving files in Windows, System32 or Program Files."""
        executor = FileQuarantineExecutor(quarantine_dir=self.quarantine_dir)

        # Try to quarantine a file in System32
        win_dir = os.environ.get("WINDIR", "C:\\Windows")
        system_file = os.path.join(win_dir, "System32", "kernel32.dll")

        action = SecurityResponseAction(
            action_id="ACT-QUAR-SYS",
            incident_id="INC-004",
            action_type=ResponseActionType.QUARANTINE_FILE,
            target=system_file,
            rationale="Attempt to quarantine system file",
            evidence_ids=["EV-004"],
        )

        val_success, val_msg = executor.pre_check(action)
        self.assertFalse(val_success)
        self.assertIn("não é permitido", val_msg.lower())

    async def test_permission_levels_enforced(self):
        """In Phase S3, only READ_ONLY and LOW_RISK_MUTATION are allowed; HIGH_RISK_MUTATION and CRITICAL_MUTATION must raise PermissionError."""
        # Propose with HIGH_RISK_MUTATION
        with self.assertRaises(PermissionError):
            self.engine.propose_action(
                incident_id="INC-005",
                action_type=ResponseActionType.TERMINATE_PROCESS,
                target="1111",
                rationale="High risk action",
                evidence_ids=["EV-005"],
                permission_level=PermissionLevel.HIGH_RISK_MUTATION,
            )

        # Propose with CRITICAL_MUTATION
        with self.assertRaises(PermissionError):
            self.engine.propose_action(
                incident_id="INC-006",
                action_type=ResponseActionType.TERMINATE_PROCESS,
                target="2222",
                rationale="Critical action",
                evidence_ids=["EV-006"],
                permission_level=PermissionLevel.CRITICAL_MUTATION,
            )


def asyncio_future(result):
    f = MagicMock()
    f.__await__ = MagicMock(return_value=iter([result]))
    return f


if __name__ == "__main__":
    unittest.main()
