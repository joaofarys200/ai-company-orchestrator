"""
JARVIS OS — Test Suite: Sentinel S4 False Positive Testing & Legitimate Workload Baseline
Evaluates correlation and classification accuracy against typical developer and OS workloads
(VS Code, Chrome, Python test runners, standard network sockets, system tasks).
"""

import time
import unittest

from security.sentinel.contracts import (
    BaselineDiff,
    ProcessItem,
    SecurityClassification,
    SystemBaseline,
)
from security.sentinel.correlation import EventCorrelationEngine


class TestSentinelFalsePositives(unittest.TestCase):
    """Test suite ensuring that benign system activities and unknown items do not trigger false alerts."""

    def setUp(self):
        self.engine = EventCorrelationEngine()
        self.baseline = SystemBaseline(
            baseline_id="BASE-INIT",
            timestamp=1000.0,
            integrity_hash="hash_init",
            host_info={"hostname": "DESKTOP-DEV"},
            processes=[],
            network=[],
            persistence=[],
            hosts_info={"exists": True, "custom_entries": []},
            browser_extensions=[],
            windows_security={"defender_realtime_enabled": True},
            collector_metrics={},
        )

    def test_benign_developer_workload_no_false_positives(self):
        """Standard developer activities (VS Code, Chrome, Python, Node.js) must not trigger high risk incidents."""
        # Developer launches VS Code, Chrome, and Python pytest
        code_proc = ProcessItem(
            pid=2001, ppid=1001, name="Code.exe", exe_path=r"C:\Users\User\AppData\Local\Programs\Microsoft VS Code\Code.exe",
            cmdline=r"Code.exe .", username="User", create_time=1100.0,
            status="running", sha256="code_hash_1", is_signed=True, is_temp_dir=False
        ).to_dict()

        chrome_proc = ProcessItem(
            pid=2002, ppid=1001, name="chrome.exe", exe_path=r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            cmdline=r"chrome.exe https://github.com", username="User", create_time=1105.0,
            status="running", sha256="chrome_hash_1", is_signed=True, is_temp_dir=False
        ).to_dict()

        python_proc = ProcessItem(
            pid=2003, ppid=2001, name="python.exe", exe_path=r"C:\Users\User\Desktop\JarvisOS\venv\Scripts\python.exe",
            cmdline=r"python.exe -m pytest tests/", username="User", create_time=1110.0,
            status="running", sha256="python_hash_1", is_signed=True, is_temp_dir=False
        ).to_dict()

        diff = BaselineDiff(
            base_id="BASE-1",
            target_id="BASE-2",
            timestamp=time.time(),
            new_processes=[code_proc, chrome_proc, python_proc],
            removed_processes=[],
            new_listening_ports=[],
            removed_listening_ports=[],
            new_persistence=[],
            removed_persistence=[],
            hosts_changed=False,
            new_browser_extensions=[],
            removed_browser_extensions=[],
            security_status_changed=False,
        )

        events = self.engine.correlate_diff(diff, self.baseline)

        # Count events by severity
        high_risk_events = [e for e in events if e.severity == SecurityClassification.HIGH_RISK.value]
        benign_events = [e for e in events if e.severity == SecurityClassification.BENIGN.value]

        # False positive rate for high risk must be exactly 0
        false_positive_count = len(high_risk_events)
        total_evaluations = 3
        false_positive_rate = false_positive_count / total_evaluations

        self.assertEqual(false_positive_count, 0)
        self.assertEqual(false_positive_rate, 0.0)
        self.assertEqual(len(benign_events), 3)

    def test_unknown_binary_without_malicious_indicators_is_not_flagged_high_risk(self):
        """An unknown benign utility (e.g. customized in-house CLI) is observed as benign/informational, not high risk."""
        inhouse_tool = ProcessItem(
            pid=3333, ppid=1001, name="my_internal_tool.exe", exe_path=r"C:\Tools\my_internal_tool.exe",
            cmdline=r"my_internal_tool.exe --run", username="User", create_time=1200.0,
            status="running", sha256="inhouse_tool_sha256", is_signed=False, is_temp_dir=False
        ).to_dict()

        diff = BaselineDiff(
            base_id="B-0",
            target_id="B-1",
            timestamp=time.time(),
            new_processes=[inhouse_tool],
            removed_processes=[],
            new_listening_ports=[],
            removed_listening_ports=[],
            new_persistence=[],
            removed_persistence=[],
            hosts_changed=False,
            new_browser_extensions=[],
            removed_browser_extensions=[],
            security_status_changed=False,
        )

        events = self.engine.correlate_diff(diff, self.baseline)
        for ev in events:
            # Must NOT be classified as HIGH_RISK
            self.assertNotEqual(ev.severity, SecurityClassification.HIGH_RISK.value)
            # Response actions must not be recommended for benign unindexed tools
            self.assertFalse(ev.approval_required and "TERMINATE" in ev.recommended_action)


if __name__ == "__main__":
    unittest.main()
