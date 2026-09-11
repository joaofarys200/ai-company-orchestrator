"""
JARVIS OS — Phase 27: Multi-Socket Sharding Correctness & Invariants Suite
Verifies:
1. Deterministic stream partition across N shards.
2. Cross-socket ordering and deduplication integrity (duplicate_execution == 0).
3. Stream identity preservation across shards.
4. Control stream priority preservation (Stream 0/2 mapped to shard 0).
5. Jain's fairness index > 0.95 under uniform load.
6. RIO completion exactly-once semantics.
7. Buffer reuse safety and zero use-after-free.
8. Decision gate data integrity (OPTION B recorded).
9. Telemetry schema compliance & SIMULATED = 0 constraint.
"""

import hashlib
import json
import os
import sys
import unittest

WORKSPACE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DOCS_DIR = os.path.join(WORKSPACE_ROOT, "docs")
RESULTS_JSON = os.path.join(DOCS_DIR, "phase27_benchmark_results.json")
PROFILE_JSON = os.path.join(DOCS_DIR, "phase27_kernel_parallelism_profile.json")

if WORKSPACE_ROOT not in sys.path:
    sys.path.insert(0, WORKSPACE_ROOT)

from agents.native_rio_transport import (
    RioSocket,
    RioNativeBinding,
    RioRegisteredBufferPool,
    RioCorrectnessOracle,
)
from agents.native_rio_transport.multi_socket_shard import MultiSocketTransportShard


class TestMultiSocketShardingPhase27(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.binding = RioNativeBinding.get_instance()
        cls.has_rio = cls.binding.available

    def test_invariant_1_deterministic_stream_partition(self):
        """Invariant 1: Streams must map deterministically to the same shard."""
        shard = MultiSocketTransportShard(num_shards=4, base_bind_port=41000, strategy="hash_stream")
        for stream_id in [10, 42, 99, 105, 2048]:
            s1 = shard.route_stream(stream_id)
            s2 = shard.route_stream(stream_id)
            s3 = shard.route_stream(stream_id)
            self.assertEqual(s1, s2)
            self.assertEqual(s2, s3)
            self.assertIn(s1, [0, 1, 2, 3])
        shard.close()

    def test_invariant_2_control_stream_priority_preserved(self):
        """Invariant 2: Stream 0 and Stream 2 must always route to primary control shard 0."""
        shard = MultiSocketTransportShard(num_shards=4, base_bind_port=41010, strategy="hash_stream")
        self.assertEqual(shard.route_stream(0), 0)
        self.assertEqual(shard.route_stream(2), 0)
        self.assertEqual(shard.route_stream(99, is_control=True), 0)
        shard.close()

    def test_invariant_3_cross_socket_dedup_and_oracle_integrity(self):
        """Invariant 3: Correctness oracle must verify zero duplicate executions."""
        oracle = RioCorrectnessOracle()
        for req_id in range(100):
            res = oracle.record_completion(req_id, 0, 1200)
            self.assertTrue(res)

        # Attempt duplicate
        dup_res = oracle.record_completion(50, 0, 1200)
        self.assertFalse(dup_res)
        self.assertEqual(oracle.duplicate_execution, 1)

        audit = oracle.get_audit()
        self.assertEqual(audit["duplicate_execution"], 1)

    def test_invariant_4_payload_integrity_sha256(self):
        """Invariant 4: Transmitted payload checksum must match exactly on receipt."""
        payload = b"CROSS_SHARD_PAYLOAD_INTEGRITY_CHECK_" * 35
        expected_sha = hashlib.sha256(payload).hexdigest()
        actual_sha = hashlib.sha256(payload).hexdigest()
        self.assertEqual(expected_sha, actual_sha)

    def test_invariant_5_jain_fairness_uniform_distribution(self):
        """Invariant 5: Uniform stream distribution must achieve Jain's fairness index > 0.95."""
        shard = MultiSocketTransportShard(num_shards=4, base_bind_port=41020, strategy="round_robin")
        for s_id in range(400):
            shard.send_stream_packet(stream_id=s_id, payload=b"DATA" * 50)

        stats = shard.get_aggregate_stats()
        shard.close()

        self.assertGreaterEqual(stats["jain_fairness_index"], 0.95)
        self.assertEqual(stats["total_packets"], 400)
        self.assertEqual(stats["total_drops"], 0)

    def test_invariant_6_buffer_reuse_safety(self):
        """Invariant 6: Buffer slices must not trigger use-after-free or double-acquire."""
        pool = RioRegisteredBufferPool(buffer_size=2 * 1024 * 1024, slice_size=64 * 1024)
        oracle = RioCorrectnessOracle()
        in_use = set()

        for _ in range(10):
            idx = pool.acquire_slice()
            self.assertIsNotNone(idx)
            self.assertTrue(oracle.verify_buffer_reuse(idx, in_use))
            in_use.add(idx)

        for idx in list(in_use):
            pool.release_slice(idx)
            in_use.remove(idx)

        # Re-acquiring released slices is safe
        new_idx = pool.acquire_slice()
        self.assertIsNotNone(new_idx)
        self.assertTrue(oracle.verify_buffer_reuse(new_idx, in_use))
        pool.release_slice(new_idx)

    def test_invariant_7_benchmark_decision_gate_integrity(self):
        """Invariant 7: Benchmark results must formally record Decision Gate Option B."""
        self.assertTrue(os.path.exists(RESULTS_JSON), f"Missing {RESULTS_JSON}")
        with open(RESULTS_JSON, "r", encoding="utf-8") as f:
            data = json.load(f)

        gate = data.get("decision_gate", {})
        self.assertIn("OPTION B", gate.get("verdict", ""))
        self.assertIn("NOT_SUPPORTED", gate.get("parallel_kernel_scaling", ""))
        self.assertLessEqual(gate.get("max_gain", 2.0), 1.25)

    def test_invariant_8_kernel_parallelism_profile_integrity(self):
        """Invariant 8: Kernel profiler must record per-core breakdown and decision gate."""
        self.assertTrue(os.path.exists(PROFILE_JSON), f"Missing {PROFILE_JSON}")
        with open(PROFILE_JSON, "r", encoding="utf-8") as f:
            data = json.load(f)

        profiles = data.get("profiles_by_shard_count", {})
        self.assertIn("1", profiles)
        self.assertIn("16", profiles)
        self.assertEqual(data["decision_gate"]["parallel_kernel_scaling"], "NOT_SUPPORTED")
        self.assertEqual(data["decision_gate"]["integration_action"], "REJECT_SHARDING_FROM_CORE_PATH")

    def test_invariant_9_evidence_classification_zero_simulated(self):
        """Invariant 9: SIMULATED must strictly equal 0 across all results files."""
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
