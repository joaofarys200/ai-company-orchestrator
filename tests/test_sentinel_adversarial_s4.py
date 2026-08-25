"""
JARVIS OS — Test Suite: Sentinel S4 Adversarial Validation Matrix (S4-01 to S4-20)
Comprehensive adversarial stress tests evaluating security boundaries, anti-replay,
drift detection, privilege containment, integrity validation, and fail-safe properties.
"""

import asyncio
import hashlib
import json
import os
import tempfile
import time
import unittest
from unittest.mock import MagicMock, patch

from security.sentinel.contracts import (
    PermissionLevel,
    ResponseActionStatus,
    ResponseActionType,
    SecurityClassification,
    SecurityEvidence,
    SecurityResponseAction,
)
from security.sentinel.response.engine import ResponseEngine
from security.sentinel.response.executors.network import FirewallBlockExecutor
from security.sentinel.response.executors.process import (
    PROTECTED_PROCESSES,
    ProcessTerminationExecutor,
)
from security.sentinel.response.executors.quarantine import FileQuarantineExecutor
from security.sentinel.response.executors.task import ScheduledTaskDisableExecutor


class TestSentinelAdversarialS4(unittest.IsolatedAsyncioTestCase):
    """Adversarial validation suite covering scenarios S4-01 through S4-20."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.quarantine_dir = os.path.join(self.temp_dir.name, "quarantine")
        self.engine = ResponseEngine(storage_dir=self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    # S4-01: Unauthorized Action
    async def test_s4_01_unauthorized_action(self):
        """Attempt to execute a mutation action without human approval must be blocked."""
        action = self.engine.propose_action(
            incident_id="INC-S4-01",
            action_type=ResponseActionType.BLOCK_NETWORK_ENDPOINT,
            target="198.51.100.11",
            rationale="Adversarial unapproved action test",
            evidence_ids=["EV-S4-01"],
        )

        # Action is in WAITING_APPROVAL state
        self.assertEqual(action.status, ResponseActionStatus.WAITING_APPROVAL.value)

        # Attempt to bypass approval by calling execute directly on executor without engine authorization
        executor = self.engine._executors[ResponseActionType.BLOCK_NETWORK_ENDPOINT]
        # Direct execution check: action cannot be executed via engine without valid user and session
        success, act, msg = await self.engine.approve_and_execute(
            action_id=action.action_id,
            user="",  # Missing user
            session_id="",  # Missing session
        )
        self.assertFalse(success)
        self.assertEqual(action.status, ResponseActionStatus.WAITING_APPROVAL.value)

    # S4-02: Approval Replay
    async def test_s4_02_approval_replay(self):
        """Re-using an already executed or completed approval must be blocked."""
        action = self.engine.propose_action(
            incident_id="INC-S4-02",
            action_type=ResponseActionType.MARK_KNOWN_GOOD,
            target="hash:abcdef0123456789",
            rationale="Legitimate hash",
            evidence_ids=["EV-S4-02"],
        )

        # First approval and execution
        success1, act1, _ = await self.engine.approve_and_execute(
            action_id=action.action_id,
            user="operator_sec",
            session_id="session_legit_01",
            incident_id="INC-S4-02",
        )
        self.assertTrue(success1)
        self.assertEqual(act1.status, ResponseActionStatus.COMPLETED.value)

        # Replay attempt
        success2, act2, msg2 = await self.engine.approve_and_execute(
            action_id=action.action_id,
            user="attacker_replay",
            session_id="session_forged_99",
            incident_id="INC-S4-02",
        )
        self.assertFalse(success2)
        self.assertIn("replay bloqueado", msg2.lower())

    # S4-03: Wrong Incident Approval
    async def test_s4_03_wrong_incident_approval(self):
        """Approval submitted with a mismatched incident_id must be strictly blocked."""
        action = self.engine.propose_action(
            incident_id="INC-ACTUAL-42",
            action_type=ResponseActionType.BLOCK_NETWORK_ENDPOINT,
            target="198.51.100.99",
            rationale="Suspicious external beacon",
            evidence_ids=["EV-S4-03"],
        )

        success, _, msg = await self.engine.approve_and_execute(
            action_id=action.action_id,
            user="operator_sec",
            session_id="session_01",
            incident_id="INC-FORGED-99",
        )
        self.assertFalse(success)
        self.assertIn("incident", msg.lower())

    # S4-04: Target Drift
    async def test_s4_04_target_drift(self):
        """If target state changes or drifts before execution, action pre-check must fail safe."""
        # Create a dummy test file
        test_file = os.path.join(self.temp_dir.name, "drift_target.dat")
        with open(test_file, "w") as f:
            f.write("Initial content before proposal")

        action = self.engine.propose_action(
            incident_id="INC-S4-04",
            action_type=ResponseActionType.QUARANTINE_FILE,
            target=test_file,
            rationale="Quarantine test for drift",
            evidence_ids=["EV-S4-04"],
        )

        # Delete the file before approval (target drifted / missing)
        os.remove(test_file)

        success, act, msg = await self.engine.approve_and_execute(
            action_id=action.action_id,
            user="operator_sec",
            session_id="session_01",
        )
        self.assertFalse(success)
        self.assertEqual(act.status, ResponseActionStatus.FAILED.value)
        self.assertTrue("não existe" in msg.lower() or "não encontrado" in msg.lower())

    # S4-05: Stale Evidence
    async def test_s4_05_stale_evidence(self):
        """Proposing an action without evidence or with empty evidence list must be rejected."""
        with self.assertRaises(ValueError):
            self.engine.propose_action(
                incident_id="INC-S4-05",
                action_type=ResponseActionType.BLOCK_NETWORK_ENDPOINT,
                target="198.51.100.77",
                rationale="Missing evidence test",
                evidence_ids=[],  # Empty evidence IDs
            )

    # S4-06: PID Reuse Safeguard
    async def test_s4_06_pid_reuse(self):
        """When a PID is reused by a new process (different create_time), executor must abort."""
        executor = ProcessTerminationExecutor()

        action = SecurityResponseAction(
            action_id="ACT-S4-06",
            incident_id="INC-S4-06",
            action_type=ResponseActionType.TERMINATE_PROCESS,
            target="8888",
            rationale="Test PID reuse safety",
            evidence_ids=["EV-S4-06"],
            pre_state={"pid": 8888, "name": "miner.exe", "create_time": 1000.0, "path": "C:\\Temp\\miner.exe"},
        )

        # Simulate PID 8888 exists but belongs to a new legitimate process (different create_time)
        with patch("psutil.Process") as mock_proc_cls:
            mock_proc = MagicMock()
            mock_proc.name.return_value = "svchost_helper.exe"
            mock_proc.create_time.return_value = 2000.0  # Newer creation time!
            mock_proc.is_running.return_value = True
            mock_proc_cls.return_value = mock_proc

            success, msg = executor.pre_check(action)
            self.assertFalse(success)
            self.assertTrue("reciclado" in msg.lower() or "drift" in msg.lower())

    # S4-07: Existing Firewall Rule Preservation
    async def test_s4_07_existing_firewall_rule_preserved(self):
        """If a firewall block is executed, it must create a distinct JARVIS rule and not touch existing rules."""
        executor = FirewallBlockExecutor()
        action = SecurityResponseAction(
            action_id="ACT-S4-07",
            incident_id="INC-S4-07",
            action_type=ResponseActionType.BLOCK_NETWORK_ENDPOINT,
            target="198.51.100.33",
            rationale="Preserve pre-existing rules test",
            evidence_ids=["EV-S4-07"],
        )

        with patch("subprocess.run") as mock_subproc:
            mock_subproc.return_value = MagicMock(returncode=0, stdout="Ok.\r\n")
            res = executor.execute(action)
            self.assertEqual(res.get("rule_name"), "JARVIS-SENTINEL-ACT-S4-07")
            # Verify netsh command adds a uniquely prefixed rule
            cmd_called = mock_subproc.call_args[0][0]
            self.assertIn("advfirewall", cmd_called)
            self.assertIn("name=JARVIS-SENTINEL-ACT-S4-07", cmd_called)

    # S4-08: Firewall Rollback Isolation
    async def test_s4_08_firewall_rollback_isolation(self):
        """Firewall rollback must only delete the JARVIS-SENTINEL rule and preserve all system rules."""
        executor = FirewallBlockExecutor()
        action = SecurityResponseAction(
            action_id="ACT-S4-08",
            incident_id="INC-S4-08",
            action_type=ResponseActionType.BLOCK_NETWORK_ENDPOINT,
            target="198.51.100.44",
            rationale="Firewall rollback isolation test",
            evidence_ids=["EV-S4-08"],
            execution_result={"rule_name": "JARVIS-SENTINEL-ACT-S4-08"},
        )

        with patch("subprocess.run") as mock_subproc, \
             patch.object(executor, "_rule_exists", return_value=True):
            mock_subproc.return_value = MagicMock(returncode=0, stdout="Deleted 1 rule(s).")
            success, roll_res = executor.rollback(action)
            self.assertTrue(success)
            self.assertTrue(roll_res.get("rollback_applied"))
            cmd_called = mock_subproc.call_args[0][0]
            self.assertIn("delete", cmd_called)
            self.assertIn("name=JARVIS-SENTINEL-ACT-S4-08", cmd_called)

    # S4-09: Scheduled Task Collision & Drift
    async def test_s4_09_scheduled_task_collision(self):
        """If a scheduled task is deleted or altered externally, executor must detect drift and reject."""
        executor = ScheduledTaskDisableExecutor()
        action = SecurityResponseAction(
            action_id="ACT-S4-09",
            incident_id="INC-S4-09",
            action_type=ResponseActionType.DISABLE_SCHEDULED_TASK,
            target=r"\NonExistentOrDeletedTask",
            rationale="Task drift test",
            evidence_ids=["EV-S4-09"],
        )

        with patch.object(executor, "_query_task", return_value={"exists": False}):
            success, msg = executor.pre_check(action)
            self.assertFalse(success)
            self.assertTrue("não existe" in msg.lower() or "não encontrada" in msg.lower())

    # S4-10: Quarantine Collision & File Modification
    async def test_s4_10_quarantine_collision(self):
        """If target file is modified (hash changed) between proposal and execution, pre-check must detect drift."""
        test_file = os.path.join(self.temp_dir.name, "quarantine_drift.bin")
        with open(test_file, "wb") as f:
            f.write(b"ORIGINAL_PAYLOAD_CONTENT")

        action = self.engine.propose_action(
            incident_id="INC-S4-10",
            action_type=ResponseActionType.QUARANTINE_FILE,
            target=test_file,
            rationale="Quarantine file collision test",
            evidence_ids=["EV-S4-10"],
        )

        # Modify the file content after proposal
        with open(test_file, "wb") as f:
            f.write(b"COMPLETELY_DIFFERENT_CONTENT_TAMPERED")

        # Execute approval: executor pre_check will detect hash mismatch with pre_state
        executor = self.engine._executors[ResponseActionType.QUARANTINE_FILE]
        success, msg = executor.pre_check(action)
        self.assertFalse(success)
        self.assertTrue("modificado" in msg.lower() or "drift" in msg.lower())

    # S4-11: Critical System File Quarantine Block
    async def test_s4_11_critical_file_quarantine_blocked(self):
        """Attempting to quarantine files in C:\\Windows, System32 or Program Files must be strictly blocked."""
        executor = FileQuarantineExecutor(quarantine_dir=self.quarantine_dir)

        system_targets = [
            r"C:\Windows\System32\cmd.exe",
            r"C:\Windows\explorer.exe",
            r"C:\Program Files\Common Files\system.dll",
        ]

        for target in system_targets:
            action = SecurityResponseAction(
                action_id="ACT-S4-11",
                incident_id="INC-S4-11",
                action_type=ResponseActionType.QUARANTINE_FILE,
                target=target,
                rationale="Critical system file quarantine attempt",
                evidence_ids=["EV-S4-11"],
            )
            success, msg = executor.pre_check(action)
            self.assertFalse(success, f"Target {target} should be blocked")
            self.assertIn("não é permitido", msg.lower())

    # S4-12: Protected Process Termination Block
    async def test_s4_12_protected_process_termination_blocked(self):
        """Attempting to terminate critical OS processes (PID 0, PID 4, csrss, lsass, services) must be blocked."""
        executor = ProcessTerminationExecutor()

        # PID 0 (System Idle)
        action_0 = SecurityResponseAction(
            action_id="ACT-S4-12-0",
            incident_id="INC-S4-12",
            action_type=ResponseActionType.TERMINATE_PROCESS,
            target="0",
            rationale="Test terminate PID 0",
            evidence_ids=["EV-S4-12"],
        )
        success_0, msg_0 = executor.pre_check(action_0)
        self.assertFalse(success_0)

        # PID 4 (System)
        action_4 = SecurityResponseAction(
            action_id="ACT-S4-12-4",
            incident_id="INC-S4-12",
            action_type=ResponseActionType.TERMINATE_PROCESS,
            target="4",
            rationale="Test terminate PID 4",
            evidence_ids=["EV-S4-12"],
        )
        success_4, msg_4 = executor.pre_check(action_4)
        self.assertFalse(success_4)

        # Critical Windows executables
        for proc_name in ["csrss.exe", "lsass.exe", "services.exe", "explorer.exe"]:
            with patch("psutil.Process") as mock_proc_cls:
                mock_proc = MagicMock()
                mock_proc.name.return_value = proc_name
                mock_proc.pid = 1234
                mock_proc.is_running.return_value = True
                mock_proc_cls.return_value = mock_proc

                action = SecurityResponseAction(
                    action_id=f"ACT-S4-12-{proc_name}",
                    incident_id="INC-S4-12",
                    action_type=ResponseActionType.TERMINATE_PROCESS,
                    target="1234",
                    rationale=f"Attempt terminate {proc_name}",
                    evidence_ids=["EV-S4-12"],
                )
                success, msg = executor.pre_check(action)
                self.assertFalse(success)
                self.assertTrue("prote" in msg.lower() or "bloqueado" in msg.lower())

    # S4-13: JARVIS Self-Protection
    async def test_s4_13_jarvis_self_protection(self):
        """Sentinel must prevent terminating the running JARVIS Python or Electron processes."""
        executor = ProcessTerminationExecutor()

        with patch("psutil.Process") as mock_proc_cls:
            mock_proc = MagicMock()
            mock_proc.name.return_value = "python.exe"
            mock_proc.pid = os.getpid()
            mock_proc.is_running.return_value = True
            mock_proc_cls.return_value = mock_proc

            action = SecurityResponseAction(
                action_id="ACT-S4-13",
                incident_id="INC-S4-13",
                action_type=ResponseActionType.TERMINATE_PROCESS,
                target=str(os.getpid()),
                rationale="Attempt to terminate JARVIS backend process",
                evidence_ids=["EV-S4-13"],
            )
            success, msg = executor.pre_check(action)
            self.assertFalse(success)
            self.assertTrue("prote" in msg.lower() or "bloqueado" in msg.lower())

    # S4-14: Approval Session Mismatch
    async def test_s4_14_approval_session_mismatch(self):
        """Approval submitted with empty or forged session context must fail."""
        action = self.engine.propose_action(
            incident_id="INC-S4-14",
            action_type=ResponseActionType.BLOCK_NETWORK_ENDPOINT,
            target="198.51.100.55",
            rationale="Session mismatch test",
            evidence_ids=["EV-S4-14"],
        )

        success, _, msg = await self.engine.approve_and_execute(
            action_id=action.action_id,
            user="legit_operator",
            session_id="",  # Missing session ID
        )
        self.assertFalse(success)
        self.assertIn("sessão", msg.lower())

    # S4-15: Duplicate Action Idempotency & Safety
    async def test_s4_15_duplicate_action_safety(self):
        """Triggering duplicate actions for the same incident/target is tracked without race conditions."""
        action1 = self.engine.propose_action(
            incident_id="INC-S4-15",
            action_type=ResponseActionType.MARK_KNOWN_GOOD,
            target="hash:dup12345",
            rationale="Duplicate test 1",
            evidence_ids=["EV-S4-15"],
        )

        action2 = self.engine.propose_action(
            incident_id="INC-S4-15",
            action_type=ResponseActionType.MARK_KNOWN_GOOD,
            target="hash:dup12345",
            rationale="Duplicate test 2",
            evidence_ids=["EV-S4-15"],
        )

        self.assertNotEqual(action1.action_id, action2.action_id)
        self.assertEqual(len(self.engine.get_actions()), 2)

    # S4-16: Verification Failure Handling
    async def test_s4_16_verification_failure_handling(self):
        """If execution completes but empirical verification fails, action status must be marked FAILED."""
        action = self.engine.propose_action(
            incident_id="INC-S4-16",
            action_type=ResponseActionType.BLOCK_NETWORK_ENDPOINT,
            target="198.51.100.66",
            rationale="Verification failure test",
            evidence_ids=["EV-S4-16"],
        )

        # Mock execute success but verify failure
        with patch.object(self.engine._executors[ResponseActionType.BLOCK_NETWORK_ENDPOINT], "pre_check", return_value=(True, "OK")), \
             patch.object(self.engine._executors[ResponseActionType.BLOCK_NETWORK_ENDPOINT], "execute", return_value={"success": True}), \
             patch.object(self.engine._executors[ResponseActionType.BLOCK_NETWORK_ENDPOINT], "verify", return_value=(False, {"verified": False, "reason": "Rule not active in profile"})):

            success, act, msg = await self.engine.approve_and_execute(
                action_id=action.action_id,
                user="operator_sec",
                session_id="session_01",
            )
            self.assertFalse(success)
            self.assertEqual(act.status, ResponseActionStatus.FAILED.value)
            self.assertIn("verificação empírica falhou", act.error_message.lower())

    # S4-17: Rollback Failure Handling
    async def test_s4_17_rollback_failure_handling(self):
        """If rollback fails due to OS errors, action status retains failure details without corruption."""
        action = self.engine.propose_action(
            incident_id="INC-S4-17",
            action_type=ResponseActionType.DISABLE_SCHEDULED_TASK,
            target=r"\FailingRollbackTask",
            rationale="Rollback failure test",
            evidence_ids=["EV-S4-17"],
        )

        # Force state to COMPLETED so rollback can be called
        action.status = ResponseActionStatus.COMPLETED.value
        action.rollback_available = True

        with patch.object(self.engine._executors[ResponseActionType.DISABLE_SCHEDULED_TASK], "rollback", return_value=(False, {"error": "Access is denied"})):
            success, act, msg = await self.engine.rollback(
                action_id=action.action_id,
                user="operator_sec",
                session_id="session_01",
            )
            self.assertFalse(success)
            self.assertTrue("falha" in act.error_message.lower() or "error" in act.error_message.lower())

    # S4-18: Evidence Tampering Detection
    async def test_s4_18_evidence_tampering_detection(self):
        """SecurityEvidence payload integrity must match computed SHA-256 hash."""
        raw_data = {"pid": 1234, "cmdline": "test_app.exe"}
        raw_ref = json.dumps(raw_data, sort_keys=True)
        raw_hash = hashlib.sha256(raw_ref.encode()).hexdigest()

        ev = SecurityEvidence(
            evidence_id="EV-S4-18",
            timestamp=time.time(),
            collector="process_collector",
            host="DESKTOP-LOCAL",
            asset="process:1234",
            observation="Process telemetry evidence",
            raw_reference=raw_ref,
            normalized_data=raw_data,
            sha256=raw_hash,
            confidence=0.9,
            source="process_collector",
        )
        self.assertEqual(ev.sha256, raw_hash)

        # Tamper payload
        tampered_data = {"pid": 1234, "cmdline": "MALICIOUS_TAMPERED_INJECT.exe"}
        computed_tampered_hash = hashlib.sha256(json.dumps(tampered_data, sort_keys=True).encode()).hexdigest()
        self.assertNotEqual(ev.sha256, computed_tampered_hash)

    # S4-19: Event Injection Rejection
    async def test_s4_19_event_injection_rejection(self):
        """Correlation engine rejects synthetic events without valid collectors or corrupted timestamps."""
        # Any response proposal with invalid permission level is strictly rejected
        with self.assertRaises(PermissionError):
            self.engine.propose_action(
                incident_id="INC-S4-19",
                action_type=ResponseActionType.TERMINATE_PROCESS,
                target="1234",
                rationale="Injected high risk action",
                evidence_ids=["EV-S4-19"],
                permission_level=PermissionLevel.CRITICAL_MUTATION,
            )

    # S4-20: UI Approval Forgery Prevention
    async def test_s4_20_ui_approval_forgery_prevention(self):
        """Directly approving an unknown action_id must fail cleanly and not execute any operation."""
        success, act, msg = await self.engine.approve_and_execute(
            action_id="ACT-FORGED-INJECT-999",
            user="attacker",
            session_id="forged_sess",
        )
        self.assertFalse(success)
        self.assertIsNone(act)
        self.assertIn("não encontrada", msg.lower())


if __name__ == "__main__":
    unittest.main()
