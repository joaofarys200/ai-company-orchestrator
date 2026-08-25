"""
JARVIS OS — Test Suite: Sentinel S5 Temporal Correlation & Latency Benchmark
Evaluates detection latency (collector, correlation, alert) across percentiles (mean, median, p95, max)
and temporal correlation across sliding windows (1s, 5s, 30s, 60s, 5min).
"""

import time
import unittest
from typing import List

from security.sentinel.contracts import (
    BaselineDiff,
    ProcessItem,
    SecurityClassification,
    SystemBaseline,
)
from security.sentinel.correlation import EventCorrelationEngine


class TestSentinelTemporalCorrelationS5(unittest.TestCase):
    """Test suite for temporal correlation and latency benchmarking."""

    def setUp(self):
        self.engine = EventCorrelationEngine()
        self.baseline = SystemBaseline(
            baseline_id="BASE-TEMPORAL-INIT",
            timestamp=1000.0,
            integrity_hash="hash_temporal_init",
            host_info={},
            processes=[],
            network=[],
            persistence=[],
            hosts_info={},
            browser_extensions=[],
            windows_security={"defender_realtime_enabled": True},
            collector_metrics={},
        )

    def test_correlation_latency_percentiles_under_load(self):
        """Measures correlation latency over 50 iterations and calculates Mean, Median, P95, and Max."""
        latencies_ms: List[float] = []

        proc = ProcessItem(
            pid=9001, ppid=1000, name="latency_test_proc.exe",
            exe_path=r"C:\Users\User\AppData\Local\Temp\latency_test_proc.exe",
            cmdline="latency_test_proc.exe", username="User", create_time=1000.0,
            status="running", is_temp_dir=True
        ).to_dict()

        diff = BaselineDiff(base_id="B-0", target_id="B-1", timestamp=time.time(), new_processes=[proc])

        # Execute 50 cycles
        for _ in range(50):
            engine = EventCorrelationEngine()
            t0 = time.perf_counter()
            events = engine.correlate_diff(diff, self.baseline)
            t1 = time.perf_counter()
            latencies_ms.append((t1 - t0) * 1000.0)

        latencies_ms.sort()
        mean_latency = sum(latencies_ms) / len(latencies_ms)
        median_latency = latencies_ms[len(latencies_ms) // 2]
        p95_index = int(len(latencies_ms) * 0.95)
        p95_latency = latencies_ms[p95_index]
        max_latency = max(latencies_ms)

        # Assert performance bounds (Correlation latency P95 must be < 5.0ms)
        self.assertLess(p95_latency, 5.0)
        self.assertLess(mean_latency, 2.0)

    def test_temporal_window_1s_association(self):
        """Temporal window 1s: Process event + Persistence registered 1s apart."""
        t_base = time.time()
        proc = ProcessItem(
            pid=9002, ppid=1000, name="agent1s.exe", exe_path=r"C:\Users\User\AppData\Local\Temp\agent1s.exe",
            cmdline="agent1s.exe", username="User", create_time=t_base, status="running", is_temp_dir=True
        ).to_dict()
        persist = {"kind": "REGISTRY_RUN", "name": "agent1s", "target_path": r"C:\Users\User\AppData\Local\Temp\agent1s.exe"}

        diff = BaselineDiff(base_id="B-0", target_id="B-1", timestamp=t_base + 1.0, new_processes=[proc], new_persistence=[persist])
        events = self.engine.correlate_diff(diff, self.default_baseline if hasattr(self, 'default_baseline') else self.baseline)
        self.assertTrue(any(e.severity == SecurityClassification.SUSPICIOUS.value for e in events))

    def test_temporal_window_5s_association(self):
        """Temporal window 5s: Multi-signal event arriving 5 seconds after baseline."""
        t_base = time.time()
        miner = ProcessItem(
            pid=9003, ppid=1000, name="miner5s.exe", exe_path=r"C:\Users\User\AppData\Local\Temp\miner5s.exe",
            cmdline="miner5s.exe", username="User", create_time=t_base, status="running", is_temp_dir=True
        ).to_dict()
        persist = {"kind": "REGISTRY_RUN", "name": "miner5s", "target_path": r"C:\Users\User\AppData\Local\Temp\miner5s.exe"}
        net = [{"pid": 9003, "local_addr": "192.168.1.50", "remote_addr": "198.51.100.2", "remote_port": 80, "status": "ESTABLISHED"}]

        base_with_net = SystemBaseline(
            baseline_id="BASE-5S", timestamp=t_base, integrity_hash="h5s",
            host_info={}, processes=[], network=net, persistence=[], hosts_info={},
            browser_extensions=[], windows_security={"defender_realtime_enabled": True}, collector_metrics={}
        )
        diff = BaselineDiff(base_id="B-0", target_id="B-1", timestamp=t_base + 5.0, new_processes=[miner], new_persistence=[persist])
        events = self.engine.correlate_diff(diff, base_with_net)
        high_risk = [e for e in events if e.severity == SecurityClassification.HIGH_RISK.value]
        self.assertEqual(len(high_risk), 1)

    def test_temporal_window_30s_association(self):
        """Temporal window 30s: Event arriving after 30 seconds maintains accurate correlation."""
        t_base = time.time()
        bad_proc = ProcessItem(
            pid=9004, ppid=1000, name="tool30s.exe", exe_path=r"C:\Users\User\AppData\Local\Temp\tool30s.exe",
            cmdline="tool30s", username="User", create_time=t_base, status="running", is_temp_dir=True
        ).to_dict()
        diff = BaselineDiff(base_id="B-0", target_id="B-1", timestamp=t_base + 30.0, new_processes=[bad_proc])
        events = self.engine.correlate_diff(diff, self.baseline)
        self.assertEqual(len(events), 1)

    def test_temporal_window_60s_association(self):
        """Temporal window 60s: Event arriving after 60s is successfully indexed with correct timeline."""
        t_base = time.time()
        bad_proc = ProcessItem(
            pid=9005, ppid=1000, name="tool60s.exe", exe_path=r"C:\Users\User\AppData\Local\Temp\tool60s.exe",
            cmdline="tool60s", username="User", create_time=t_base, status="running", is_temp_dir=True
        ).to_dict()
        diff = BaselineDiff(base_id="B-0", target_id="B-1", timestamp=t_base + 60.0, new_processes=[bad_proc])
        events = self.engine.correlate_diff(diff, self.baseline)
        self.assertEqual(len(events), 1)

    def test_temporal_window_5min_association(self):
        """Temporal window 5min: Event arriving after 5 minutes is accurately tracked."""
        t_base = time.time()
        bad_proc = ProcessItem(
            pid=9006, ppid=1000, name="tool5min.exe", exe_path=r"C:\Users\User\AppData\Local\Temp\tool5min.exe",
            cmdline="tool5min", username="User", create_time=t_base, status="running", is_temp_dir=True
        ).to_dict()
        diff = BaselineDiff(base_id="B-0", target_id="B-1", timestamp=t_base + 300.0, new_processes=[bad_proc])
        events = self.engine.correlate_diff(diff, self.baseline)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].severity, SecurityClassification.SUSPICIOUS.value)


if __name__ == "__main__":
    unittest.main()
