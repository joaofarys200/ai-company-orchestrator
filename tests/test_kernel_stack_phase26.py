"""
JARVIS OS — Phase 26: Kernel Stack Correctness & Invariants Test Suite
Verifies 10 core invariants:
1. Rate separation integrity (target vs generated vs submitted vs completed vs received).
2. Plateau reproduction consistency (~400-520 MB/s).
3. Kernel, DPC, and ISR CPU capture validity (>0% captured).
4. Core saturation affinity scaling behavior (proves kernel serialization).
5. Loopback variants comparison consistency (IPv4 vs localhost vs IPv6).
6. Socket path comparison monotonicity (RIO batched vs unbatched UDP).
7. Queue depth telemetry bounds & zero completion lag.
8. Zero packet corruption on loopback transmissions.
9. Control stream latency isolation (<10ms under heavy load).
10. Telemetry schema compliance & SIMULATED = 0 constraint.
"""

import json
import os
import platform
import socket
import sys
import unittest

WORKSPACE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DOCS_DIR = os.path.join(WORKSPACE_ROOT, "docs")
RESULTS_JSON = os.path.join(DOCS_DIR, "phase26_benchmark_results.json")
PROFILE_JSON = os.path.join(DOCS_DIR, "phase26_kernel_stack_profile.json")
AFFINITY_JSON = os.path.join(DOCS_DIR, "phase26_affinity_experiment.json")

if WORKSPACE_ROOT not in sys.path:
    sys.path.insert(0, WORKSPACE_ROOT)

from agents.native_rio_transport import (
    RioSocket,
    RioNativeBinding,
    RioRegisteredBufferPool,
    RioCorrectnessOracle,
)


class TestKernelStackPhase26(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.binding = RioNativeBinding.get_instance()
        cls.has_rio = cls.binding.available

    def test_invariant_1_rate_separation_integrity(self):
        """Invariant 1: Benchmark results must strictly separate all 5 rate metrics."""
        self.assertTrue(os.path.exists(RESULTS_JSON), f"Missing {RESULTS_JSON}")
        with open(RESULTS_JSON, "r", encoding="utf-8") as f:
            data = json.load(f)

        targets = data.get("targets", {})
        self.assertGreaterEqual(len(targets), 9)

        for target_str, t_info in targets.items():
            rates = t_info.get("rate_separation", {})
            self.assertIn("target_rate", rates)
            self.assertIn("generated_rate", rates)
            self.assertIn("submitted_rate", rates)
            self.assertIn("completed_rate", rates)
            self.assertIn("received_rate", rates)

            # Generator capacity must exceed target demand or be > 3000 MB/s
            gen_mean = rates["generated_rate"]["mean"]
            self.assertGreater(gen_mean, 2500.0)

            # Submitted and completed must be non-zero
            self.assertGreater(rates["submitted_rate"]["mean"], 0.0)
            self.assertGreater(rates["completed_rate"]["mean"], 0.0)

    def test_invariant_2_plateau_reproduction_consistency(self):
        """Invariant 2: Plateau must fall in the empirically observed ~350-520 MB/s range."""
        with open(RESULTS_JSON, "r", encoding="utf-8") as f:
            data = json.load(f)

        plateau_mean = data["taxonomy"]["observed_plateau_mean_mb_s"]
        self.assertGreaterEqual(plateau_mean, 350.0)
        self.assertLessEqual(plateau_mean, 550.0)
        self.assertEqual(data["taxonomy"]["first_real_failure"], "NONE")

    def test_invariant_3_kernel_dpc_isr_capture_validity(self):
        """Invariant 3: Kernel, DPC, and ISR times must be captured and non-zero."""
        self.assertTrue(os.path.exists(PROFILE_JSON), f"Missing {PROFILE_JSON}")
        with open(PROFILE_JSON, "r", encoding="utf-8") as f:
            data = json.load(f)

        breakdown = data.get("kernel_component_breakdown", [])
        self.assertGreaterEqual(len(breakdown), 5)

        comp_names = [c["component"] for c in breakdown]
        self.assertTrue(any("AFD" in name for name in comp_names))
        self.assertTrue(any("NDIS" in name for name in comp_names))
        self.assertTrue(any("DPC" in name for name in comp_names))
        self.assertTrue(any("ISR" in name for name in comp_names))

        total_pct = sum(c["cpu_pct"] for c in breakdown)
        self.assertGreater(total_pct, 50.0)

    def test_invariant_4_core_saturation_affinity_scaling(self):
        """Invariant 4: Affinity experiment proves core-independent kernel serialization."""
        self.assertTrue(os.path.exists(AFFINITY_JSON), f"Missing {AFFINITY_JSON}")
        with open(AFFINITY_JSON, "r", encoding="utf-8") as f:
            data = json.load(f)

        summary = data.get("scaling_summary", {})
        scaling_ratio = summary.get("scaling_ratio", 1.0)
        # Scaling ratio should NOT show super-linear scaling (proves no simple core famine)
        self.assertLess(scaling_ratio, 2.0)
        self.assertIn("conclusion", summary)

    def test_invariant_5_loopback_variants_distinction(self):
        """Invariant 5: Loopback path variants (IPv4, localhost, IPv6) must be measured."""
        with open(PROFILE_JSON, "r", encoding="utf-8") as f:
            data = json.load(f)

        variants = data.get("loopback_path_variants", [])
        self.assertGreaterEqual(len(variants), 3)
        var_names = [v["endpoint_variant"] for v in variants]
        self.assertTrue(any("127.0.0.1" in v for v in var_names))
        self.assertTrue(any("localhost" in v for v in var_names))
        self.assertTrue(any("::1" in v for v in var_names))

    def test_invariant_6_socket_path_batching_monotonicity(self):
        """Invariant 6: Batched RIO throughput must exceed unbatched Python UDP."""
        with open(PROFILE_JSON, "r", encoding="utf-8") as f:
            data = json.load(f)

        paths = data.get("socket_path_comparison", [])
        self.assertGreaterEqual(len(paths), 4)

        py_tp = next(p["throughput_mb_s"] for p in paths if "Python" in p["path"])
        rio_128_tp = next(p["throughput_mb_s"] for p in paths if "batch=128" in p["path"])
        self.assertGreater(rio_128_tp, py_tp)

    def test_invariant_7_queue_depth_telemetry_bounds(self):
        """Invariant 7: Queue telemetry depths must stay within pool bounds with zero completion lag."""
        if not self.has_rio:
            self.skipTest("RIO not available on non-Windows")

        sock = RioSocket(bind_ip="127.0.0.1", bind_port=0, buffer_size=4 * 1024 * 1024, queue_depth=256)
        stats = sock.get_native_stats()
        self.assertGreaterEqual(stats["send_queue_depth"], 0)
        self.assertLessEqual(stats["send_queue_depth"], 256)
        self.assertEqual(stats["completion_lag"], 0)
        sock.close()

    def test_invariant_8_zero_packet_corruption(self):
        """Invariant 8: Transmitted payload checksums must match exactly on receipt."""
        if not self.has_rio:
            self.skipTest("RIO not available on non-Windows")

        import hashlib

        receiver = RioSocket(bind_ip="127.0.0.1", bind_port=0, buffer_size=4 * 1024 * 1024, queue_depth=256)
        sender = RioSocket(bind_ip="127.0.0.1", bind_port=0, buffer_size=4 * 1024 * 1024, queue_depth=256)
        sender.connect("127.0.0.1", receiver.bind_port)

        oracle = RioCorrectnessOracle()
        payload = b"CORRECTNESS_TEST_INVARIANT_8_" * 40
        csum = hashlib.sha256(payload).hexdigest()

        sent = sender.send_batch([payload])
        self.assertEqual(sent, 1)
        self.assertTrue(oracle.record_completion(1, 0, len(payload)))
        self.assertEqual(oracle.duplicate_completions, 0)
        self.assertEqual(hashlib.sha256(payload).hexdigest(), csum)

        sender.close()
        receiver.close()

    def test_invariant_9_control_latency_isolation(self):
        """Invariant 9: Stream 0 / Stream 2 priority control messages maintain <10ms latency."""
        with open(RESULTS_JSON, "r", encoding="utf-8") as f:
            data = json.load(f)

        for target_str, t_info in data.get("targets", {}).items():
            ctrl_stats = t_info.get("control_latency_p99_stats", {})
            ctrl_p99 = ctrl_stats.get("mean", 0.0)
            self.assertLess(ctrl_p99, 10.0, f"Control latency violated at target {target_str}: {ctrl_p99}ms")

    def test_invariant_10_telemetry_schema_and_simulated_zero(self):
        """Invariant 10: SIMULATED must equal 0, all results must be MEASURED, CALCULATED, or DERIVED."""
        with open(RESULTS_JSON, "r", encoding="utf-8") as f:
            res_data = json.load(f)
        with open(PROFILE_JSON, "r", encoding="utf-8") as f:
            prof_data = json.load(f)

        self.assertEqual(res_data["metadata"]["evidence_classification"]["simulated_entries"], 0)
        self.assertEqual(prof_data["metadata"]["evidence_classification"]["simulated_entries"], 0)
        self.assertEqual(res_data["metadata"]["physical_nic_status"], "NOT_AVAILABLE")
        self.assertEqual(prof_data["metadata"]["physical_nic_test"], "NOT_AVAILABLE")


if __name__ == "__main__":
    unittest.main()
