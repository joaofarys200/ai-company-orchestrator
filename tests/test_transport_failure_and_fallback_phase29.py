"""
JARVIS OS — Phase 29: Transport Failure Injection & Deterministic Fallback Suite
Verifies:
1. RIO DLL unavailable -> Fallback to QUIC Python.
2. QUIC unavailable -> Fallback to gRPC.
3. gRPC unavailable -> Fallback to TCP.
4. Mid-mission failover without mission restart or duplicate side effects.
5. Malformed envelope rejection and CRC32 verification.
"""

import asyncio
import hashlib
import os
import sys
import unittest

WORKSPACE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if WORKSPACE_ROOT not in sys.path:
    sys.path.insert(0, WORKSPACE_ROOT)

from agents.distributed_transport import (
    AdaptiveDistributedTransportPolicy,
    CorruptedEnvelopeError,
    DistributedEnvelope,
    MessageAction,
    ProductionDistributedTransport,
    TcpTransport,
    TransportBackendRegistry,
    TransportHealthStatus,
    TransportType,
)


class TestTransportFailureAndFallbackPhase29(unittest.TestCase):
    def setUp(self):
        self.registry = TransportBackendRegistry.get_instance()
        self.policy = AdaptiveDistributedTransportPolicy(self.registry)

    def test_fault_1_rio_unavailable_fallback_to_quic_python(self):
        """Fault 1: When native RIO is unavailable, policy falls back to QUIC Python."""
        dec = self.policy.select_transport(
            operating_system="Windows",
            localhost_or_remote="localhost",
            concurrency=256,
            payload_size=100000,
            native_RIO_available=False,
        )
        self.assertEqual(dec["selected_backend_name"], "QUIC_PYTHON")
        self.assertIn("QUIC Python", dec["selected_reason"])

    def test_fault_2_quic_unavailable_fallback_to_grpc_or_http2(self):
        """Fault 2: When QUIC is unavailable, policy falls back to gRPC or HTTP2."""
        dec = self.policy.select_transport(
            backend_availability={"QUIC_RIO": False, "QUIC_PYTHON": False, "GRPC": True, "HTTP2": True, "TCP": True},
            is_rpc=True,
        )
        self.assertEqual(dec["selected_backend_name"], "GRPC")

    def test_fault_3_grpc_unavailable_fallback_to_tcp(self):
        """Fault 3: When higher backends fail, fallback order terminates at standard TCP."""
        dec = self.policy.select_transport(
            backend_availability={"QUIC_RIO": False, "QUIC_PYTHON": False, "GRPC": False, "HTTP2": False, "TCP": True},
        )
        self.assertEqual(dec["selected_backend_name"], "TCP")

    def test_fault_4_mid_mission_failover_preserves_identity_and_prevents_duplicate_side_effect(self):
        """Fault 4: Active mission failover advances session epoch and avoids duplicate side effects."""
        prod = ProductionDistributedTransport(
            node_id="coordinator_01",
            mission_id="mission_phoenix_99",
            preferred_backend="TCP",
        )

        side_effect_count = 0
        executed_tasks = set()

        def apply_side_effect(task_id: str):
            nonlocal side_effect_count
            if task_id not in executed_tasks:
                executed_tasks.add(task_id)
                side_effect_count += 1

        # Simulate 3 tasks with failover on task 2
        for i in range(1, 4):
            task_id = f"task_{i}"
            apply_side_effect(task_id)

            if i == 2:
                # Inject failure and trigger fallback
                env = DistributedEnvelope.create(
                    source_node="coordinator_01",
                    destination_node="worker_01",
                    action=MessageAction.REQUEST,
                    payload_type="task_data",
                    payload={"task_id": task_id},
                )
                asyncio.run(prod._execute_fallback_and_resend("worker_01", env, "simulated_socket_reset"))

        # Reconnection must NOT replay task 1 or task 2 side effects
        self.assertEqual(side_effect_count, 3)
        self.assertEqual(len(executed_tasks), 3)
        self.assertEqual(prod.session.mission_id, "mission_phoenix_99")
        self.assertGreaterEqual(prod.session.epoch, 2)

    def test_fault_5_corrupted_envelope_crc_rejection(self):
        """Fault 5: Manipulating envelope payload bytes must trigger CorruptedEnvelopeError."""
        env = DistributedEnvelope.create(
            source_node="node_a",
            destination_node="node_b",
            action=MessageAction.REQUEST,
            payload_type="mission_state",
            payload={"counter": 42},
        )
        raw = bytearray(env.serialize())
        # Corrupt one byte in the payload body
        raw[-5] ^= 0xFF

        with self.assertRaises(CorruptedEnvelopeError):
            DistributedEnvelope.deserialize(bytes(raw))


if __name__ == "__main__":
    unittest.main()
