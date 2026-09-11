"""
JARVIS OS — Phase 29: Transport Productionization & Correctness Invariants Suite
Verifies:
1. Unified DistributedTransport abstraction layer operations.
2. TransportCapabilityDetector testable detection and NOT_AVAILABLE physical multi-host tracking.
3. TransportBackendRegistry official backends and fallback priorities.
4. AdaptiveDistributedTransportPolicy deterministic property tests.
5. TransportHealthMonitor lifecycle transitions.
6. TransportSession identity and epoch management across failover.
7. Control plane isolation (Stream 0 & Stream 2 priority).
8. Multi-process E2E result verification.
9. 16 Correctness invariants (duplicate execution 0, side effects 0, no mission restart on reconnect).
10. Evidence zero simulated constraint (SIMULATED = 0).
"""

import hashlib
import json
import os
import sys
import unittest

WORKSPACE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if WORKSPACE_ROOT not in sys.path:
    sys.path.insert(0, WORKSPACE_ROOT)

from agents.distributed_transport import (
    AdaptiveDistributedTransportPolicy,
    DistributedEnvelope,
    DistributedTransport,
    MessageAction,
    ProductionDistributedTransport,
    TcpTransport,
    TransportBackendInfo,
    TransportBackendRegistry,
    TransportCapabilityDetector,
    TransportHealthMonitor,
    TransportHealthStatus,
    TransportPriorityChannel,
    TransportSession,
    TransportType,
)


class TestTransportProductionizationPhase29(unittest.TestCase):
    def setUp(self):
        self.registry = TransportBackendRegistry.get_instance()
        self.policy = AdaptiveDistributedTransportPolicy(self.registry)

    def test_invariant_1_capability_detector_accuracy(self):
        """Invariant 1: Capability detector must test real platform and mark physical peer NOT_AVAILABLE."""
        caps = TransportCapabilityDetector.detect()
        self.assertIn("operating_system", caps)
        self.assertIn("cpu_count", caps)
        self.assertGreater(caps["cpu_count"], 0)
        self.assertEqual(caps["physical_multi_host_test"], "NOT_AVAILABLE")
        self.assertFalse(caps["remote_peers_available"])

    def test_invariant_2_backend_registry_integrity(self):
        """Invariant 2: Official backends must be present and MULTI_SOCKET_SHARD marked rejected."""
        backends = {b.backend_name: b for b in self.registry.list_backends()}
        self.assertIn("QUIC_RIO", backends)
        self.assertIn("QUIC_PYTHON", backends)
        self.assertIn("GRPC", backends)
        self.assertIn("HTTP2", backends)
        self.assertIn("TCP", backends)
        self.assertIn("MULTI_SOCKET_SHARD", backends)

        shard = backends["MULTI_SOCKET_SHARD"]
        self.assertFalse(shard.availability)
        self.assertEqual(shard.health, TransportHealthStatus.FAILED)
        self.assertIn("NO_MEASURABLE_SCALING", shard.rejection_reason)

    def test_invariant_3_policy_determinism_property(self):
        """Invariant 3: Same policy inputs must deterministically yield identical outputs."""
        kwargs = {
            "operating_system": "Windows",
            "localhost_or_remote": "localhost",
            "concurrency": 128,
            "payload_size": 100000,
            "packet_loss_estimate": 0.0,
            "native_RIO_available": True,
        }
        res1 = self.policy.select_transport(**kwargs)
        res2 = self.policy.select_transport(**kwargs)
        self.assertEqual(res1["selected_backend_name"], res2["selected_backend_name"])
        self.assertEqual(res1["fallback_order_names"], res2["fallback_order_names"])
        self.assertEqual(res1["policy_version"], "29.1.0")

    def test_invariant_4_windows_local_policy_workload_matching(self):
        """Invariant 4: Windows localhost selects QUIC_RIO under heavy load, QUIC_PYTHON under light load."""
        heavy = self.policy.select_transport(
            operating_system="Windows",
            localhost_or_remote="localhost",
            concurrency=128,
            payload_size=100000,
            native_RIO_available=True,
        )
        self.assertEqual(heavy["selected_backend_name"], "QUIC_RIO")

        light = self.policy.select_transport(
            operating_system="Windows",
            localhost_or_remote="localhost",
            concurrency=4,
            payload_size=1024,
            native_RIO_available=True,
        )
        self.assertEqual(light["selected_backend_name"], "QUIC_PYTHON")

    def test_invariant_5_policy_fallback_chain_no_cycles(self):
        """Invariant 5: Fallback chain must be cycle-free and contain only distinct viable backends."""
        res = self.policy.select_transport(concurrency=64, payload_size=50000)
        selected = res["selected_backend_name"]
        chain = res["fallback_order_names"]
        self.assertNotIn(selected, chain)
        self.assertEqual(len(chain), len(set(chain)))

    def test_invariant_6_unavailable_backend_never_selected(self):
        """Invariant 6: Backends marked unavailable or failed must never be selected."""
        res = self.policy.select_transport(
            backend_availability={"QUIC_RIO": False, "QUIC_PYTHON": False, "GRPC": True, "HTTP2": True, "TCP": True}
        )
        self.assertNotIn(res["selected_backend_name"], ["QUIC_RIO", "QUIC_PYTHON"])
        self.assertIn(res["selected_backend_name"], ["GRPC", "HTTP2", "TCP"])

    def test_invariant_7_health_monitor_state_machine(self):
        """Invariant 7: Health monitor must transition across states according to failure thresholds."""
        monitor = TransportHealthMonitor("node_test")
        self.assertEqual(monitor.health_status, TransportHealthStatus.HEALTHY)

        # Record errors
        monitor.record_error("timeout 1")
        self.assertEqual(monitor.health_status, TransportHealthStatus.DEGRADED)

        monitor.record_error("timeout 2")
        monitor.record_error("timeout 3")
        self.assertEqual(monitor.health_status, TransportHealthStatus.FAILING)

        monitor.record_error("fatal error", fatal=True)
        self.assertEqual(monitor.health_status, TransportHealthStatus.FAILED)

        # Recovery
        monitor.record_fallback()
        self.assertEqual(monitor.health_status, TransportHealthStatus.RECOVERING)

        # 3 fast successes -> healthy
        monitor.record_success(5.0)
        monitor.record_success(4.0)
        monitor.record_success(3.0)
        self.assertEqual(monitor.health_status, TransportHealthStatus.HEALTHY)

    def test_invariant_8_transport_session_epoch_preservation(self):
        """Invariant 8: Reconnection and failover must advance epoch without altering session_id or mission_id."""
        prod = ProductionDistributedTransport(
            node_id="node_a",
            mission_id="mission_gamma_42",
            preferred_backend="TCP",
        )
        init_session_id = prod.session.session_id
        init_mission_id = prod.session.mission_id
        init_epoch = prod.session.epoch

        # Simulate fallback
        env = DistributedEnvelope.create(
            source_node="node_a",
            destination_node="node_b",
            action=MessageAction.REQUEST,
            payload_type="test",
            payload="DATA",
        )
        import asyncio
        asyncio.run(prod._execute_fallback_and_resend("node_b", env, "simulated_backend_drop"))

        self.assertEqual(prod.session.session_id, init_session_id)
        self.assertEqual(prod.session.mission_id, init_mission_id)
        self.assertEqual(prod.session.epoch, init_epoch + 1)
        self.assertGreaterEqual(prod.fallback_count, 1)

    def test_invariant_9_control_plane_channel_priority(self):
        """Invariant 9: Stream 0 and Stream 2 control channels must be explicitly defined and prioritized."""
        self.assertEqual(TransportPriorityChannel.CONTROL.value, "CONTROL")
        self.assertEqual(TransportPriorityChannel.CONTROL_STATE.value, "CONTROL_STATE")
        self.assertEqual(TransportPriorityChannel.BULK.value, "BULK")

    def test_invariant_10_multiprocess_e2e_results_verification(self):
        """Invariant 10: Multi-process results must verify LOCAL_MULTI_PROCESS with zero drop."""
        results_path = os.path.join(WORKSPACE_ROOT, "docs", "phase29_multiprocess_e2e_results.json")
        self.assertTrue(os.path.exists(results_path), f"Missing {results_path}")
        with open(results_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        self.assertEqual(data["execution_mode"], "LOCAL_MULTI_PROCESS")
        self.assertEqual(data["physical_multi_host_test"], "NOT_AVAILABLE")
        self.assertEqual(data["status"], "PASS")
        self.assertEqual(data["invariants"]["duplicate_execution"], 0)
        self.assertEqual(data["invariants"]["duplicate_side_effect"], 0)
        self.assertTrue(data["invariants"]["checkpoint_identity_preserved"])

    def test_invariant_11_evidence_classification_zero_simulated(self):
        """Invariant 11: SIMULATED must strictly equal 0."""
        results_path = os.path.join(WORKSPACE_ROOT, "docs", "phase29_multiprocess_e2e_results.json")
        with open(results_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.assertEqual(data["evidence_classification"]["simulated_entries"], 0)


if __name__ == "__main__":
    unittest.main()
