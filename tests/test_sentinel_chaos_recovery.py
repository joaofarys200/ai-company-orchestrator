"""
JARVIS OS — Test Suite: Sentinel S4 Chaos & Recovery Testing
Evaluates Sentinel resilience under severe conditions: corrupted storage, subprocess timeouts,
concurrent execution races, and process restart state recovery.
"""

import asyncio
import os
import subprocess
import tempfile
import unittest
from unittest.mock import patch, MagicMock

from security.sentinel.contracts import (
    PermissionLevel,
    ResponseActionStatus,
    ResponseActionType,
)
from security.sentinel.response.engine import ResponseEngine
from security.sentinel.response.executors.network import FirewallBlockExecutor


class TestSentinelChaosRecovery(unittest.IsolatedAsyncioTestCase):
    """Test suite for chaos resilience, recovery from corrupted storage, and timeouts."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.engine = ResponseEngine(storage_dir=self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    async def test_corrupted_response_history_json_recovery(self):
        """Corrupted/truncated response_history.json must not crash the engine during initialization."""
        history_path = os.path.join(self.temp_dir.name, "response_history.json")
        # Write corrupted garbage data
        with open(history_path, "w", encoding="utf-8") as f:
            f.write("{ INVALID_JSON_TRUNCATED_GARBAGE_!@#$%^&*() \n 12345 ")

        # Initializing new engine instance on the same directory must survive cleanly
        new_engine = ResponseEngine(storage_dir=self.temp_dir.name)
        self.assertEqual(len(new_engine.get_actions()), 0)

        # Proposing new actions must work without issues
        action = new_engine.propose_action(
            incident_id="INC-CHAOS-01",
            action_type=ResponseActionType.MARK_KNOWN_GOOD,
            target="hash:clean123",
            rationale="Action proposed after corrupted history recovery",
            evidence_ids=["EV-CHAOS-01"],
        )
        self.assertIsNotNone(action)
        self.assertEqual(len(new_engine.get_actions()), 1)

    async def test_executor_subprocess_timeout_handled_safely(self):
        """Subprocess timeout during firewall or schtasks commands must mark action FAILED without hanging."""
        action = self.engine.propose_action(
            incident_id="INC-CHAOS-02",
            action_type=ResponseActionType.BLOCK_NETWORK_ENDPOINT,
            target="198.51.100.200",
            rationale="Subprocess timeout chaos test",
            evidence_ids=["EV-CHAOS-02"],
        )

        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd=["netsh"], timeout=5)):
            success, act, msg = await self.engine.approve_and_execute(
                action_id=action.action_id,
                user="operator_sec",
                session_id="session_chaos",
            )
            self.assertFalse(success)
            self.assertEqual(act.status, ResponseActionStatus.FAILED.value)
            self.assertIn("falha", act.error_message.lower())

    async def test_concurrent_approval_race_prevention(self):
        """Concurrent calls approving the same action concurrently must result in exactly 1 execution and 1 replay block."""
        action = self.engine.propose_action(
            incident_id="INC-CHAOS-03",
            action_type=ResponseActionType.MARK_KNOWN_GOOD,
            target="hash:race12345",
            rationale="Race condition approval test",
            evidence_ids=["EV-CHAOS-03"],
        )

        # Launch 2 concurrent approval tasks
        res1, res2 = await asyncio.gather(
            self.engine.approve_and_execute(action.action_id, "user_1", "sess_1", "INC-CHAOS-03"),
            self.engine.approve_and_execute(action.action_id, "user_2", "sess_2", "INC-CHAOS-03"),
            return_exceptions=True,
        )

        # One must succeed and one must fail (due to lock & status transition)
        successes = [r[0] for r in (res1, res2) if isinstance(r, tuple)]
        self.assertEqual(successes.count(True), 1)
        self.assertEqual(successes.count(False), 1)

    async def test_restart_state_preservation(self):
        """Actions persisted in history must be accurately reloaded with exact status after Sentinel restart."""
        action = self.engine.propose_action(
            incident_id="INC-CHAOS-04",
            action_type=ResponseActionType.MARK_KNOWN_GOOD,
            target="hash:persist123",
            rationale="State preservation test",
            evidence_ids=["EV-CHAOS-04"],
        )

        await self.engine.approve_and_execute(
            action_id=action.action_id,
            user="operator_sec",
            session_id="sess_persist",
        )

        # Simulate service restart with new engine instance
        restarted_engine = ResponseEngine(storage_dir=self.temp_dir.name)
        reloaded_action = restarted_engine.get_action(action.action_id)

        self.assertIsNotNone(reloaded_action)
        self.assertEqual(reloaded_action.status, ResponseActionStatus.COMPLETED.value)
        self.assertEqual(reloaded_action.approved_by, "operator_sec")


if __name__ == "__main__":
    unittest.main()
