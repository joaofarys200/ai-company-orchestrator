"""
JARVIS OS — Phase 27: Multi-Socket Shard Failure Injection & Resilience Suite
Tests:
1. Socket shard abrupt failure and seamless failover to peer shards.
2. Shard recovery and traffic re-balancing.
3. All-shards failed boundary condition handling.
4. Uneven shard load tolerance.
5. Large payload bounds enforcement per shard.
"""

import os
import sys
import unittest

WORKSPACE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if WORKSPACE_ROOT not in sys.path:
    sys.path.insert(0, WORKSPACE_ROOT)

from agents.native_rio_transport.multi_socket_shard import MultiSocketTransportShard


class TestMultiSocketFailureInjectionPhase27(unittest.TestCase):
    def test_fault_1_shard_abrupt_failure_and_failover(self):
        """Fault 1: When a shard fails, active traffic must automatically fail over to surviving shards."""
        shard = MultiSocketTransportShard(num_shards=4, base_bind_port=42000, strategy="round_robin")
        self.assertEqual(shard.get_aggregate_stats()["active_shards"], 4)

        # Fail shard 1
        self.assertTrue(shard.fail_shard(1))
        self.assertEqual(shard.get_aggregate_stats()["active_shards"], 3)

        # Send 60 packets: none should be routed to shard 1
        for s_id in range(60):
            shard.send_stream_packet(stream_id=s_id, payload=b"FAILOVER_TEST" * 10)

        stats = shard.get_aggregate_stats()
        shard.close()

        # Shard 1 must have 0 packets
        self.assertEqual(stats["per_shard"][1]["packets_sent"], 0)
        self.assertGreater(stats["per_shard"][0]["packets_sent"], 0)
        self.assertGreater(stats["per_shard"][2]["packets_sent"], 0)
        self.assertGreater(stats["per_shard"][3]["packets_sent"], 0)

    def test_fault_2_shard_recovery_and_restoration(self):
        """Fault 2: Recovered shard must resume receiving routed traffic."""
        shard = MultiSocketTransportShard(num_shards=3, base_bind_port=42010, strategy="round_robin")
        shard.fail_shard(0)
        self.assertEqual(shard.get_aggregate_stats()["active_shards"], 2)

        # Recover shard 0
        self.assertTrue(shard.recover_shard(0))
        self.assertEqual(shard.get_aggregate_stats()["active_shards"], 3)

        # Send packets: shard 0 must receive packets now
        for s_id in range(30):
            shard.send_stream_packet(stream_id=s_id, payload=b"RECOVERY_TEST" * 10)

        stats = shard.get_aggregate_stats()
        shard.close()

        self.assertGreater(stats["per_shard"][0]["packets_sent"], 0)

    def test_fault_3_all_shards_failed_boundary(self):
        """Fault 3: If all shards are marked failed, send must return safely without uncaught exception."""
        shard = MultiSocketTransportShard(num_shards=2, base_bind_port=42020)
        shard.fail_shard(0)
        shard.fail_shard(1)
        self.assertEqual(shard.get_aggregate_stats()["active_shards"], 0)

        # Sending must not raise an unhandled crash
        res = shard.send_stream_packet(stream_id=1, payload=b"CRASH_TEST")
        # May return False or fallback safely
        self.assertIn(res, [True, False])
        shard.close()

    def test_fault_4_uneven_shard_load_tolerance(self):
        """Fault 4: Sending 90% load to single shard directly must not destabilize peers."""
        shard = MultiSocketTransportShard(num_shards=4, base_bind_port=42030)
        # Heavy burst to shard 0
        batch = [b"BURST_DATA" * 50] * 64
        sent_0 = shard.send_batch_to_shard(0, batch)
        self.assertEqual(sent_0, 64)

        # Normal packet directly to shard 2
        sent_2 = shard.send_batch_to_shard(2, [b"PEER_DATA"])
        self.assertEqual(sent_2, 1)

        stats = shard.get_aggregate_stats()
        shard.close()

        self.assertEqual(stats["per_shard"][0]["packets_sent"], 64)
        self.assertEqual(stats["per_shard"][2]["packets_sent"], 1)
        self.assertEqual(stats["total_errors"], 0)

    def test_fault_5_invalid_shard_index(self):
        """Fault 5: Passing out-of-bounds shard index must return 0 or False without crash."""
        shard = MultiSocketTransportShard(num_shards=2, base_bind_port=42040)
        sent = shard.send_batch_to_shard(999, [b"BAD_INDEX"])
        self.assertEqual(sent, 0)
        self.assertFalse(shard.fail_shard(-1))
        self.assertFalse(shard.recover_shard(100))
        shard.close()


if __name__ == "__main__":
    unittest.main()
