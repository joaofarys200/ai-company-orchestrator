"""Adversarial and functional test suite for Sentinel S3 Human Approval verification."""

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


class TestSentinelApproval(unittest.IsolatedAsyncioTestCase):
    """Test suite for human approval verification, replay prevention and authorization checks."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.engine = ResponseEngine(storage_dir=self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    async def test_unauthenticated_approval_rejected(self):
        """Approval must reject empty user, blank session, or missing authorization."""
        action = self.engine.propose_action(
            incident_id="INC-APP-1",
            action_type=ResponseActionType.BLOCK_NETWORK_ENDPOINT,
            target="198.51.100.99",
            rationale="Malicious command & control endpoint",
            evidence_ids=["EV-APP-1"],
        )

        # 1. Empty user
        success, act, msg = await self.engine.approve_and_execute(
            action_id=action.action_id,
            user="",
            session_id="sess_123",
        )
        self.assertFalse(success)
        self.assertIn("utilizador", msg.lower())

        # 2. Empty session_id
        success, act, msg = await self.engine.approve_and_execute(
            action_id=action.action_id,
            user="operator_alice",
            session_id="",
        )
        self.assertFalse(success)
        self.assertIn("sessão", msg.lower())

    async def test_mismatched_incident_id_rejected(self):
        """Approval providing a mismatched incident_id must fail."""
        action = self.engine.propose_action(
            incident_id="INC-ORIGINAL",
            action_type=ResponseActionType.BLOCK_NETWORK_ENDPOINT,
            target="198.51.100.99",
            rationale="Malicious command & control endpoint",
            evidence_ids=["EV-APP-2"],
        )

        success, act, msg = await self.engine.approve_and_execute(
            action_id=action.action_id,
            user="operator_alice",
            session_id="sess_123",
            incident_id="INC-FORGED-OR-DIFFERENT",
        )
        self.assertFalse(success)
        self.assertIn("incident", msg.lower())

    async def test_replayed_approval_prevented(self):
        """Once approved and executed (or completed), an action cannot be re-approved/replayed."""
        action = self.engine.propose_action(
            incident_id="INC-REPLAY",
            action_type=ResponseActionType.MARK_KNOWN_GOOD,
            target="hash:abc123456",
            rationale="Legitimate build artifact",
            evidence_ids=["EV-APP-3"],
        )

        # First approval and execution succeeds
        success1, act1, msg1 = await self.engine.approve_and_execute(
            action_id=action.action_id,
            user="operator_alice",
            session_id="sess_123",
            incident_id="INC-REPLAY",
        )
        self.assertTrue(success1)
        self.assertEqual(act1.status, ResponseActionStatus.COMPLETED.value)

        # Replay attempt must be rejected
        success2, act2, msg2 = await self.engine.approve_and_execute(
            action_id=action.action_id,
            user="operator_attacker",
            session_id="sess_replay",
            incident_id="INC-REPLAY",
        )
        self.assertFalse(success2)
        self.assertIn("replay bloqueado", msg2.lower())

    async def test_rejection_marks_action_rejected_and_blocks_execution(self):
        """Rejecting an action sets status to REJECTED and blocks any subsequent approval."""
        action = self.engine.propose_action(
            incident_id="INC-REJECT",
            action_type=ResponseActionType.TERMINATE_PROCESS,
            target="55555",
            rationale="Suspicious background process",
            evidence_ids=["EV-APP-4"],
        )

        success_rej, act_rej, msg_rej = self.engine.reject(
            action_id=action.action_id,
            user="operator_bob",
            reason="False positive: process is development test runner",
        )
        self.assertTrue(success_rej)
        self.assertEqual(act_rej.status, ResponseActionStatus.REJECTED.value)

        # Attempt to approve rejected action must fail
        success_app, act_app, msg_app = await self.engine.approve_and_execute(
            action_id=action.action_id,
            user="operator_alice",
            session_id="sess_123",
        )
        self.assertFalse(success_app)
        self.assertIn("replay bloqueado", msg_app.lower())

    async def test_non_existent_action_approval_fails(self):
        """Attempting to approve a non-existent action ID cleanly returns failure."""
        success, act, msg = await self.engine.approve_and_execute(
            action_id="ACT-NON-EXISTENT",
            user="operator_alice",
            session_id="sess_123",
        )
        self.assertFalse(success)
        self.assertIsNone(act)
        self.assertIn("não encontrada", msg.lower())


if __name__ == "__main__":
    unittest.main()
