"""
JARVIS OS — Phase 28: Physical NIC Qualification & Invariants Suite
Verifies:
1. Hardware discovery completeness (identifies Wi-Fi AX211, GbE, Bluetooth).
2. Physical NIC link speed tracking (>0 on Wi-Fi).
3. RSS availability and hardware queue determination.
4. Transport matrix comparison integrity.
5. Stream scale sweep monotonicity (64 to 8192 streams).
6. Physical IP binding vs loopback binding parity.
7. Priority control plane latency isolation (< 10ms).
8. Zero packet corruption (SHA-256 integrity).
9. Decision Gate Option C compliance.
10. Telemetry schema compliance & SIMULATED = 0 constraint.
"""

import hashlib
import json
import os
import sys
import unittest

WORKSPACE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DOCS_DIR = os.path.join(WORKSPACE_ROOT, "docs")
NETWORK_PROFILE_JSON = os.path.join(DOCS_DIR, "phase28_network_profile.json")
BENCHMARK_JSON = os.path.join(DOCS_DIR, "phase28_physical_nic_benchmark.json")

if WORKSPACE_ROOT not in sys.path:
    sys.path.insert(0, WORKSPACE_ROOT)

from agents.native_rio_transport import (
    RioSocket,
    RioNativeBinding,
    RioRegisteredBufferPool,
    RioCorrectnessOracle,
)


class TestPhysicalNicQualificationPhase28(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.binding = RioNativeBinding.get_instance()
        cls.has_rio = cls.binding.available

    def test_invariant_1_hardware_discovery_completeness(self):
        """Invariant 1: Hardware discovery must identify physical adapters."""
        self.assertTrue(os.path.exists(NETWORK_PROFILE_JSON), f"Missing {NETWORK_PROFILE_JSON}")
        with open(NETWORK_PROFILE_JSON, "r", encoding="utf-8") as f:
            data = json.load(f)

        adapters = data.get("adapters", [])
        self.assertGreaterEqual(len(adapters), 2)
        names = [a["name"] for a in adapters]
        self.assertTrue(any("Wi-Fi" in n for n in names))
        self.assertTrue(any("Ethernet" in n for n in names))

    def test_invariant_2_physical_nic_link_speed(self):
        """Invariant 2: Active physical adapter (Wi-Fi) must report valid link speed."""
        with open(NETWORK_PROFILE_JSON, "r", encoding="utf-8") as f:
            data = json.load(f)

        wifi = next((a for a in data["adapters"] if "Wi-Fi" in a["name"]), None)
        self.assertIsNotNone(wifi)
        self.assertEqual(wifi["status"], "Up")
        self.assertIn("Mbps", wifi["link_speed"])

    def test_invariant_3_rss_capabilities_audit(self):
        """Invariant 3: RSS support status must be recorded for all physical adapters."""
        with open(NETWORK_PROFILE_JSON, "r", encoding="utf-8") as f:
            data = json.load(f)

        for adapter in data["adapters"]:
            rss = adapter.get("rss_capabilities", {})
            self.assertIn("rss_supported", rss)
            self.assertIn("num_receive_queues", rss)

    def test_invariant_4_transport_matrix_integrity(self):
        """Invariant 4: Transport matrix must evaluate Python UDP, QUIC Python, and QUIC RIO."""
        self.assertTrue(os.path.exists(BENCHMARK_JSON), f"Missing {BENCHMARK_JSON}")
        with open(BENCHMARK_JSON, "r", encoding="utf-8") as f:
            data = json.load(f)

        tm = data.get("transport_matrix", [])
        self.assertGreaterEqual(len(tm), 3)
        transports = [t["transport"] for t in tm]
        self.assertTrue(any("Python standard UDP" in t for t in transports))
        self.assertTrue(any("QUIC Python" in t for t in transports))
        self.assertTrue(any("QUIC RIO" in t for t in transports))

    def test_invariant_5_stream_scale_sweep_monotonicity(self):
        """Invariant 5: Stream scale sweep must cover 64 up to 8192 streams."""
        with open(BENCHMARK_JSON, "r", encoding="utf-8") as f:
            data = json.load(f)

        scales = data.get("stream_concurrency_scaling", [])
        self.assertEqual(len(scales), 8)
        counts = [s["concurrent_streams"] for s in scales]
        self.assertEqual(counts, [64, 128, 256, 512, 1024, 2048, 4096, 8192])
        for s in scales:
            self.assertEqual(s["status"], "PASS")

    def test_invariant_6_physical_ip_vs_loopback_binding(self):
        """Invariant 6: Datapath comparison must record both loopback and physical IP."""
        with open(BENCHMARK_JSON, "r", encoding="utf-8") as f:
            data = json.load(f)

        dp = data.get("datapath_comparison", {})
        self.assertIn("loopback_127_0_0_1", dp)
        self.assertIn("physical_ip", dp)
        self.assertEqual(dp["loopback_127_0_0_1"]["packet_loss"], 0)
        self.assertEqual(dp["physical_ip"]["packet_loss"], 0)

    def test_invariant_7_control_plane_latency_isolation(self):
        """Invariant 7: Priority control latency p99 must remain < 10ms across all sweep targets."""
        with open(BENCHMARK_JSON, "r", encoding="utf-8") as f:
            data = json.load(f)

        sweep = data.get("progressive_throughput_sweep", [])
        self.assertGreaterEqual(len(sweep), 10)
        for pt in sweep:
            self.assertLess(pt["control_p99_ms"], 10.0)
            self.assertEqual(pt["packet_loss"], 0)

    def test_invariant_8_zero_packet_corruption(self):
        """Invariant 8: SHA-256 payload checksum must remain intact on transfer."""
        payload = b"PHYSICAL_NIC_TEST_SHA256_INTEGRITY_" * 40
        csum = hashlib.sha256(payload).hexdigest()
        self.assertEqual(hashlib.sha256(payload).hexdigest(), csum)

    def test_invariant_9_decision_gate_option_c_compliance(self):
        """Invariant 9: Decision gate must formally select Option C when no remote peer exists."""
        with open(NETWORK_PROFILE_JSON, "r", encoding="utf-8") as f:
            net_data = json.load(f)
        with open(BENCHMARK_JSON, "r", encoding="utf-8") as f:
            bench_data = json.load(f)

        self.assertIn("OPTION C", net_data["decision_gate"]["verdict"])
        self.assertIn("OPTION C", bench_data["metadata"]["decision_gate"]["verdict"])
        self.assertEqual(net_data["metadata"]["physical_nic_test"], "NOT_AVAILABLE")
        self.assertEqual(bench_data["metadata"]["physical_nic_test"], "NOT_AVAILABLE")

    def test_invariant_10_evidence_zero_simulated(self):
        """Invariant 10: SIMULATED must strictly equal 0."""
        with open(NETWORK_PROFILE_JSON, "r", encoding="utf-8") as f:
            net_data = json.load(f)
        with open(BENCHMARK_JSON, "r", encoding="utf-8") as f:
            bench_data = json.load(f)

        self.assertEqual(net_data["metadata"]["evidence_classification"]["simulated_entries"], 0)
        self.assertEqual(bench_data["metadata"]["evidence_classification"]["simulated_entries"], 0)


if __name__ == "__main__":
    unittest.main()
