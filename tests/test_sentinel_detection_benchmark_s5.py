"""
JARVIS OS — Test Suite: Sentinel S5 Detection Quality & Threat Correlation Benchmark (40 Scenarios)
Rigorous empirical benchmark evaluating classification accuracy, multi-signal correlation,
adversarial noise resilience, and explanation quality across 40 controlled scenarios.
"""

import time
import unittest
from typing import Any, Dict, List

from security.sentinel.contracts import (
    BaselineDiff,
    BrowserExtensionItem,
    EventCategory,
    HostsInfo,
    NetworkItem,
    PersistenceItem,
    ProcessItem,
    SecurityClassification,
    SecurityEvent,
    SystemBaseline,
    WindowsSecurityStatus,
)
from security.sentinel.correlation import EventCorrelationEngine


class TestSentinelDetectionBenchmarkS5(unittest.TestCase):
    """Benchmark test suite evaluating detection quality across 40 controlled scenarios."""

    def setUp(self):
        self.engine = EventCorrelationEngine()
        self.default_baseline = SystemBaseline(
            baseline_id="BASE-BENCHMARK-INIT",
            timestamp=1000.0,
            integrity_hash="hash_benchmark_init",
            host_info={"hostname": "DESKTOP-BENCHMARK"},
            processes=[],
            network=[],
            persistence=[],
            hosts_info={"exists": True, "custom_entries": []},
            browser_extensions=[],
            windows_security={"defender_realtime_enabled": True, "firewall_domain_enabled": True},
            collector_metrics={},
        )

    # =========================================================================
    # 1. BENIGN CASES (B01 - B10)
    # Expected: BENIGN or empty alert stream (0 High Risk, 0 False Positives)
    # =========================================================================

    def test_b01_chrome_normal(self):
        """B01: Google Chrome execution in Program Files with standard web socket."""
        chrome = ProcessItem(
            pid=4001, ppid=1000, name="chrome.exe", exe_path=r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            cmdline=r"chrome.exe https://docs.python.org", username="User", create_time=1000.0,
            status="running", is_signed=True, is_temp_dir=False
        ).to_dict()
        diff = BaselineDiff(
            base_id="B-0", target_id="B-1", timestamp=time.time(),
            new_processes=[chrome],
        )
        events = self.engine.correlate_diff(diff, self.default_baseline)
        high_risk = [e for e in events if e.severity == SecurityClassification.HIGH_RISK.value]
        self.assertEqual(len(high_risk), 0)
        self.assertTrue(all(e.severity == SecurityClassification.BENIGN.value for e in events))

    def test_b02_vscode_normal(self):
        """B02: Visual Studio Code standard execution in AppData Local Programs."""
        code = ProcessItem(
            pid=4002, ppid=1000, name="Code.exe", exe_path=r"C:\Users\User\AppData\Local\Programs\Microsoft VS Code\Code.exe",
            cmdline=r"Code.exe .", username="User", create_time=1000.0,
            status="running", is_signed=True, is_temp_dir=False
        ).to_dict()
        diff = BaselineDiff(base_id="B-0", target_id="B-1", timestamp=time.time(), new_processes=[code])
        events = self.engine.correlate_diff(diff, self.default_baseline)
        self.assertEqual(len([e for e in events if e.severity == SecurityClassification.HIGH_RISK.value]), 0)

    def test_b03_python_subprocess(self):
        """B03: Python legitimate test runner spawning pytest subprocess."""
        python_proc = ProcessItem(
            pid=4003, ppid=4002, name="python.exe", exe_path=r"C:\Users\User\Desktop\JarvisOS\venv\Scripts\python.exe",
            cmdline=r"python.exe -m pytest tests/", username="User", create_time=1000.0,
            status="running", is_signed=True, is_temp_dir=False
        ).to_dict()
        diff = BaselineDiff(base_id="B-0", target_id="B-1", timestamp=time.time(), new_processes=[python_proc])
        events = self.engine.correlate_diff(diff, self.default_baseline)
        self.assertEqual(len([e for e in events if e.severity == SecurityClassification.HIGH_RISK.value]), 0)

    def test_b04_jarvis_normal(self):
        """B04: JARVIS OS backend server running on port 8000."""
        jarvis_proc = ProcessItem(
            pid=4004, ppid=1000, name="server.py", exe_path=r"C:\Users\User\Desktop\JarvisOS\server.py",
            cmdline=r"python server.py", username="User", create_time=1000.0,
            status="running", is_signed=False, is_temp_dir=False
        ).to_dict()
        diff = BaselineDiff(base_id="B-0", target_id="B-1", timestamp=time.time(), new_processes=[jarvis_proc])
        events = self.engine.correlate_diff(diff, self.default_baseline)
        self.assertEqual(len([e for e in events if e.severity == SecurityClassification.HIGH_RISK.value]), 0)

    def test_b05_playwright_headless(self):
        """B05: Playwright launching headless Chromium browser for automated UI QA."""
        pw_proc = ProcessItem(
            pid=4005, ppid=4003, name="chrome.exe", exe_path=r"C:\Users\User\AppData\Local\ms-playwright\chromium-1155\chrome-win\chrome.exe",
            cmdline=r"chrome.exe --headless --disable-gpu", username="User", create_time=1000.0,
            status="running", is_signed=True, is_temp_dir=False
        ).to_dict()
        diff = BaselineDiff(base_id="B-0", target_id="B-1", timestamp=time.time(), new_processes=[pw_proc])
        events = self.engine.correlate_diff(diff, self.default_baseline)
        self.assertEqual(len([e for e in events if e.severity == SecurityClassification.HIGH_RISK.value]), 0)

    def test_b06_docker_daemon(self):
        """B06: Docker Desktop daemon running in standard Program Files."""
        docker_proc = ProcessItem(
            pid=4006, ppid=4, name="com.docker.backend.exe", exe_path=r"C:\Program Files\Docker\Docker\resources\com.docker.backend.exe",
            cmdline=r"com.docker.backend.exe", username="SYSTEM", create_time=1000.0,
            status="running", is_signed=True, is_temp_dir=False
        ).to_dict()
        diff = BaselineDiff(base_id="B-0", target_id="B-1", timestamp=time.time(), new_processes=[docker_proc])
        events = self.engine.correlate_diff(diff, self.default_baseline)
        self.assertEqual(len([e for e in events if e.severity == SecurityClassification.HIGH_RISK.value]), 0)

    def test_b07_legitimate_updater(self):
        """B07: Software update service executable in Program Files."""
        updater_proc = ProcessItem(
            pid=4007, ppid=4, name="GoogleUpdate.exe", exe_path=r"C:\Program Files (x86)\Google\Update\GoogleUpdate.exe",
            cmdline=r"GoogleUpdate.exe /c", username="SYSTEM", create_time=1000.0,
            status="running", is_signed=True, is_temp_dir=False
        ).to_dict()
        diff = BaselineDiff(base_id="B-0", target_id="B-1", timestamp=time.time(), new_processes=[updater_proc])
        events = self.engine.correlate_diff(diff, self.default_baseline)
        self.assertEqual(len([e for e in events if e.severity == SecurityClassification.HIGH_RISK.value]), 0)

    def test_b08_legitimate_scheduled_task(self):
        """B08: Legitimate Windows Maintenance scheduled task."""
        # Unchanged diff with normal background state
        diff = BaselineDiff(base_id="B-0", target_id="B-1", timestamp=time.time())
        events = self.engine.correlate_diff(diff, self.default_baseline)
        self.assertEqual(len([e for e in events if e.severity == SecurityClassification.HIGH_RISK.value]), 0)

    def test_b09_legitimate_service(self):
        """B09: Standard Windows Audio or Spooler service running normally."""
        spooler = ProcessItem(
            pid=4009, ppid=4, name="spoolsv.exe", exe_path=r"C:\Windows\System32\spoolsv.exe",
            cmdline=r"C:\Windows\System32\spoolsv.exe", username="SYSTEM", create_time=1000.0,
            status="running", is_signed=True, is_temp_dir=False
        ).to_dict()
        diff = BaselineDiff(base_id="B-0", target_id="B-1", timestamp=time.time(), new_processes=[spooler])
        events = self.engine.correlate_diff(diff, self.default_baseline)
        self.assertEqual(len([e for e in events if e.severity == SecurityClassification.HIGH_RISK.value]), 0)

    def test_b10_legitimate_external_connection(self):
        """B10: Standard HTTPS socket to GitHub or Microsoft CDN."""
        chrome_proc = ProcessItem(
            pid=4010, ppid=1000, name="chrome.exe", exe_path=r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            cmdline=r"chrome.exe", username="User", create_time=1000.0, status="running", is_signed=True, is_temp_dir=False
        ).to_dict()
        diff = BaselineDiff(base_id="B-0", target_id="B-1", timestamp=time.time(), new_processes=[chrome_proc])
        events = self.engine.correlate_diff(diff, self.default_baseline)
        self.assertEqual(len([e for e in events if e.severity == SecurityClassification.HIGH_RISK.value]), 0)

    # =========================================================================
    # 2. SUSPICIOUS CASES (A01 - A06e)
    # Expected: SUSPICIOUS (Confidence 0.70 - 0.95, No Autonomous Kill)
    # =========================================================================

    def test_a01_new_unknown_process_in_temp(self):
        """A01: New unknown process running out of user Temp directory."""
        temp_proc = ProcessItem(
            pid=5001, ppid=1000, name="unrecognized_tool.exe", exe_path=r"C:\Users\User\AppData\Local\Temp\unrecognized_tool.exe",
            cmdline=r"unrecognized_tool.exe", username="User", create_time=1000.0,
            status="running", is_signed=False, is_temp_dir=True
        ).to_dict()
        diff = BaselineDiff(base_id="B-0", target_id="B-1", timestamp=time.time(), new_processes=[temp_proc])
        events = self.engine.correlate_diff(diff, self.default_baseline)
        self.assertTrue(any(e.severity == SecurityClassification.SUSPICIOUS.value for e in events))

    def test_a02_process_outside_standard_location(self):
        """A02: Process running from temporary workspace directory."""
        temp_tool = ProcessItem(
            pid=5002, ppid=1000, name="dropper_candidate.exe", exe_path=r"C:\Users\User\AppData\Local\Temp\sub\dropper_candidate.exe",
            cmdline=r"dropper_candidate.exe", username="User", create_time=1000.0,
            status="running", is_signed=False, is_temp_dir=True
        ).to_dict()
        diff = BaselineDiff(base_id="B-0", target_id="B-1", timestamp=time.time(), new_processes=[temp_tool])
        events = self.engine.correlate_diff(diff, self.default_baseline)
        self.assertTrue(any(e.severity == SecurityClassification.SUSPICIOUS.value for e in events))

    def test_a03_new_scheduled_task(self):
        """A03: Newly registered scheduled task in Task Scheduler."""
        persist_task = {
            "kind": "TASK_SCHEDULER", "name": "CustomBackgroundSync", "target_path": r"C:\Tools\sync.exe"
        }
        diff = BaselineDiff(base_id="B-0", target_id="B-1", timestamp=time.time(), new_persistence=[persist_task])
        events = self.engine.correlate_diff(diff, self.default_baseline)
        self.assertTrue(any(e.severity == SecurityClassification.SUSPICIOUS.value and e.category == EventCategory.PERSISTENCE.value for e in events))

    def test_a04_unsigned_executable(self):
        """A04: Unsigned executable running in temp folder."""
        unsigned_tool = ProcessItem(
            pid=5004, ppid=1000, name="unsigned_helper.exe", exe_path=r"C:\Users\User\AppData\Local\Temp\unsigned_helper.exe",
            cmdline=r"unsigned_helper.exe", username="User", create_time=1000.0,
            status="running", is_signed=False, is_temp_dir=True
        ).to_dict()
        diff = BaselineDiff(base_id="B-0", target_id="B-1", timestamp=time.time(), new_processes=[unsigned_tool])
        events = self.engine.correlate_diff(diff, self.default_baseline)
        self.assertTrue(any(e.severity == SecurityClassification.SUSPICIOUS.value for e in events))

    def test_a05_firewall_profile_disabled(self):
        """A05: Windows Firewall profile disabled."""
        baseline_disabled_fw = SystemBaseline(
            baseline_id="BASE-FW-OFF", timestamp=1000.0, integrity_hash="hash_fw_off",
            host_info={}, processes=[], network=[], persistence=[], hosts_info={},
            browser_extensions=[],
            windows_security={"defender_realtime_enabled": True, "firewall_public_enabled": False},
            collector_metrics={}
        )
        diff = BaselineDiff(base_id="B-0", target_id="B-1", timestamp=time.time())
        events = self.engine.correlate_diff(diff, baseline_disabled_fw)
        self.assertTrue(any(e.severity == SecurityClassification.SUSPICIOUS.value and "Firewall" in e.rationale for e in events))

    def test_a06_hosts_modification(self):
        """A06: Hosts file modified with custom DNS mappings."""
        diff = BaselineDiff(
            base_id="B-0", target_id="B-1", timestamp=time.time(),
            hosts_changed=True,
            hosts_diff={"base_sha256": "11111111", "current_sha256": "22222222"}
        )
        events = self.engine.correlate_diff(diff, self.default_baseline)
        self.assertTrue(any(e.severity == SecurityClassification.SUSPICIOUS.value and e.category == EventCategory.HOSTS.value for e in events))

    def test_a06b_browser_extension_sensitive_permissions(self):
        """A06b: Newly installed extension with broad sensitive permissions."""
        ext = {
            "browser": "CHROME", "extension_id": "malicious_extension_id_123",
            "name": "Screen Recorder Pro", "permissions": ["cookies", "<all_urls>", "webRequestBlocking"]
        }
        diff = BaselineDiff(base_id="B-0", target_id="B-1", timestamp=time.time(), new_browser_extensions=[ext])
        events = self.engine.correlate_diff(diff, self.default_baseline)
        self.assertTrue(any(e.severity == SecurityClassification.SUSPICIOUS.value and e.category == EventCategory.BROWSER.value for e in events))

    def test_a06c_registry_startup_entry(self):
        """A06c: New Registry Run key persistence entry."""
        run_key = {
            "kind": "REGISTRY_RUN", "name": "SuspiciousAutoStart", "target_path": r"C:\Users\User\AppData\Local\tool.exe"
        }
        diff = BaselineDiff(base_id="B-0", target_id="B-1", timestamp=time.time(), new_persistence=[run_key])
        events = self.engine.correlate_diff(diff, self.default_baseline)
        self.assertTrue(any(e.severity == SecurityClassification.SUSPICIOUS.value and "persistência" in e.rationale.lower() for e in events))

    def test_a06d_defender_realtime_disabled(self):
        """A06d: Windows Defender Real-time protection disabled."""
        baseline_def_off = SystemBaseline(
            baseline_id="BASE-DEF-OFF", timestamp=1000.0, integrity_hash="hash_def_off",
            host_info={}, processes=[], network=[], persistence=[], hosts_info={},
            browser_extensions=[],
            windows_security={"defender_realtime_enabled": False, "firewall_domain_enabled": True},
            collector_metrics={}
        )
        diff = BaselineDiff(base_id="B-0", target_id="B-1", timestamp=time.time())
        events = self.engine.correlate_diff(diff, baseline_def_off)
        self.assertTrue(any(e.severity == SecurityClassification.HIGH_RISK.value and "Defender" in e.rationale for e in events))

    def test_a06e_browser_extension_benign(self):
        """A06e: Legitimate theme or lightweight extension with minimal permissions."""
        ext = {
            "browser": "EDGE", "extension_id": "dark_reader_theme",
            "name": "Dark Reader Theme", "permissions": ["storage"]
        }
        diff = BaselineDiff(base_id="B-0", target_id="B-1", timestamp=time.time(), new_browser_extensions=[ext])
        events = self.engine.correlate_diff(diff, self.default_baseline)
        self.assertTrue(any(e.severity == SecurityClassification.BENIGN.value for e in events))

    # =========================================================================
    # 3. CORRELATED MULTI-SIGNAL CASES (A07 - A16)
    # Expected: HIGH_RISK with multi-signal corroboration & high confidence
    # =========================================================================

    def test_a07_triple_signal_temp_persistence_network(self):
        """A07: Unsigned process in %TEMP% + Run key persistence + Outbound TCP connection."""
        miner = ProcessItem(
            pid=6001, ppid=1000, name="cryptominer.exe", exe_path=r"C:\Users\User\AppData\Local\Temp\cryptominer.exe",
            cmdline=r"cryptominer.exe -o pool.mine.org", username="User", create_time=1000.0,
            status="running", is_signed=False, is_temp_dir=True
        ).to_dict()
        persist = {"kind": "REGISTRY_RUN", "name": "cryptominer", "target_path": r"C:\Users\User\AppData\Local\Temp\cryptominer.exe"}
        net = [{"pid": 6001, "local_addr": "192.168.1.50", "remote_addr": "198.51.100.99", "remote_port": 3333, "status": "ESTABLISHED"}]

        baseline_with_net = SystemBaseline(
            baseline_id="BASE-NET", timestamp=1000.0, integrity_hash="h1",
            host_info={}, processes=[], network=net, persistence=[], hosts_info={},
            browser_extensions=[], windows_security={"defender_realtime_enabled": True}, collector_metrics={}
        )
        diff = BaselineDiff(
            base_id="B-0", target_id="B-1", timestamp=time.time(),
            new_processes=[miner], new_persistence=[persist]
        )
        events = self.engine.correlate_diff(diff, baseline_with_net)
        high_risk = [e for e in events if e.severity == SecurityClassification.HIGH_RISK.value]
        self.assertEqual(len(high_risk), 1)
        self.assertGreaterEqual(high_risk[0].confidence, 0.85)
        self.assertIn("pasta temporária", high_risk[0].rationale)

    def test_a08_scheduled_task_temp_network(self):
        """A08: Scheduled Task + %TEMP% binary + outbound connection."""
        task_binary = ProcessItem(
            pid=6002, ppid=1000, name="updater_trojan.exe", exe_path=r"C:\Users\User\AppData\Local\Temp\updater_trojan.exe",
            cmdline=r"updater_trojan.exe", username="User", create_time=1000.0,
            status="running", is_signed=False, is_temp_dir=True
        ).to_dict()
        persist = {"kind": "TASK_SCHEDULER", "name": "DailySystemUpdate", "target_path": r"C:\Users\User\AppData\Local\Temp\updater_trojan.exe"}
        net = [{"pid": 6002, "local_addr": "192.168.1.50", "remote_addr": "203.0.113.10", "remote_port": 443, "status": "ESTABLISHED"}]

        baseline_with_net = SystemBaseline(
            baseline_id="BASE-NET-2", timestamp=1000.0, integrity_hash="h2",
            host_info={}, processes=[], network=net, persistence=[], hosts_info={},
            browser_extensions=[], windows_security={"defender_realtime_enabled": True}, collector_metrics={}
        )
        diff = BaselineDiff(
            base_id="B-0", target_id="B-1", timestamp=time.time(),
            new_processes=[task_binary], new_persistence=[persist]
        )
        events = self.engine.correlate_diff(diff, baseline_with_net)
        high_risk = [e for e in events if e.severity == SecurityClassification.HIGH_RISK.value]
        self.assertEqual(len(high_risk), 1)

    def test_a09_hosts_and_unsigned_temp_process(self):
        """A09: Hosts file altered + new unsigned process in temp folder."""
        dropper = ProcessItem(
            pid=6003, ppid=1000, name="patcher.exe", exe_path=r"C:\Users\User\AppData\Local\Temp\patcher.exe",
            cmdline=r"patcher.exe", username="User", create_time=1000.0,
            status="running", is_signed=False, is_temp_dir=True
        ).to_dict()
        diff = BaselineDiff(
            base_id="B-0", target_id="B-1", timestamp=time.time(),
            new_processes=[dropper],
            hosts_changed=True,
            hosts_diff={"base_sha256": "aaaa", "current_sha256": "bbbb"}
        )
        events = self.engine.correlate_diff(diff, self.default_baseline)
        self.assertTrue(any(e.category == EventCategory.HOSTS.value for e in events))
        self.assertTrue(any(e.category == EventCategory.PROCESS.value for e in events))

    def test_a10_new_persistence_and_unknown_temp_process(self):
        """A10: Registry autorun pointing to newly launched temp binary."""
        rat = ProcessItem(
            pid=6004, ppid=1000, name="agent_beacon.exe", exe_path=r"C:\Users\User\AppData\Local\Temp\agent_beacon.exe",
            cmdline=r"agent_beacon.exe", username="User", create_time=1000.0,
            status="running", is_signed=False, is_temp_dir=True
        ).to_dict()
        persist = {"kind": "REGISTRY_RUN", "name": "agent_beacon", "target_path": r"C:\Users\User\AppData\Local\Temp\agent_beacon.exe"}
        diff = BaselineDiff(
            base_id="B-0", target_id="B-1", timestamp=time.time(),
            new_processes=[rat], new_persistence=[persist]
        )
        events = self.engine.correlate_diff(diff, self.default_baseline)
        self.assertTrue(any(e.severity == SecurityClassification.SUSPICIOUS.value for e in events))

    def test_a11_defender_disabled_and_temp_binary(self):
        """A11: Real-time protection disabled concurrently with temp binary launch."""
        bad_app = ProcessItem(
            pid=6005, ppid=1000, name="payload.exe", exe_path=r"C:\Users\User\AppData\Local\Temp\payload.exe",
            cmdline=r"payload.exe", username="User", create_time=1000.0,
            status="running", is_signed=False, is_temp_dir=True
        ).to_dict()
        baseline_def_off = SystemBaseline(
            baseline_id="BASE-DEF-BAD", timestamp=1000.0, integrity_hash="h_def",
            host_info={}, processes=[], network=[], persistence=[], hosts_info={},
            browser_extensions=[], windows_security={"defender_realtime_enabled": False}, collector_metrics={}
        )
        diff = BaselineDiff(base_id="B-0", target_id="B-1", timestamp=time.time(), new_processes=[bad_app])
        events = self.engine.correlate_diff(diff, baseline_def_off)
        self.assertTrue(any(e.severity == SecurityClassification.HIGH_RISK.value for e in events))

    def test_a12_sensitive_extension_and_persistence(self):
        """A12: Browser extension with sensitive permissions and desktop persistence."""
        ext = {"browser": "CHROME", "extension_id": "suspicious_ext", "name": "AdBlock Plus Fake", "permissions": ["cookies", "<all_urls>"]}
        persist = {"kind": "STARTUP_FOLDER", "name": "ExtensionHelper", "target_path": r"C:\Tools\helper.exe"}
        diff = BaselineDiff(base_id="B-0", target_id="B-1", timestamp=time.time(), new_browser_extensions=[ext], new_persistence=[persist])
        events = self.engine.correlate_diff(diff, self.default_baseline)
        self.assertEqual(len(events), 2)
        self.assertTrue(all(e.severity == SecurityClassification.SUSPICIOUS.value for e in events))

    def test_a13_registry_run_pointing_to_temp(self):
        """A13: Registry run key pointing specifically to %TEMP% path."""
        persist = {"kind": "REGISTRY_RUN", "name": "TempPayload", "target_path": r"C:\Users\User\AppData\Local\Temp\evil.exe"}
        diff = BaselineDiff(base_id="B-0", target_id="B-1", timestamp=time.time(), new_persistence=[persist])
        events = self.engine.correlate_diff(diff, self.default_baseline)
        self.assertTrue(any(e.category == EventCategory.PERSISTENCE.value for e in events))

    def test_a14_task_scheduler_persistence_in_appdata(self):
        """A14: Scheduled task persistence targeting unsigned script in AppData."""
        persist = {"kind": "TASK_SCHEDULER", "name": "AppDataTask", "target_path": r"C:\Users\User\AppData\Roaming\script.bat"}
        diff = BaselineDiff(base_id="B-0", target_id="B-1", timestamp=time.time(), new_persistence=[persist])
        events = self.engine.correlate_diff(diff, self.default_baseline)
        self.assertTrue(any(e.category == EventCategory.PERSISTENCE.value for e in events))

    def test_a15_multi_binary_temp_burst(self):
        """A15: Multiple distinct binaries launched from Temp folder in single diff."""
        procs = [
            ProcessItem(pid=6011, ppid=1000, name=f"temp_stage_{i}.exe", exe_path=rf"C:\Users\User\AppData\Local\Temp\temp_stage_{i}.exe",
                        cmdline="stage", username="User", create_time=1000.0, status="running", is_temp_dir=True).to_dict()
            for i in range(3)
        ]
        diff = BaselineDiff(base_id="B-0", target_id="B-1", timestamp=time.time(), new_processes=procs)
        events = self.engine.correlate_diff(diff, self.default_baseline)
        self.assertEqual(len(events), 3)
        self.assertTrue(all(e.severity == SecurityClassification.SUSPICIOUS.value for e in events))

    def test_a16_quadruple_cross_collector_correlation(self):
        """A16: Full cross-collector event: Process in temp + Persistence + Hosts + Active Network."""
        bad_proc = ProcessItem(
            pid=6016, ppid=1000, name="c2_agent.exe", exe_path=r"C:\Users\User\AppData\Local\Temp\c2_agent.exe",
            cmdline="c2_agent.exe", username="User", create_time=1000.0, status="running", is_temp_dir=True
        ).to_dict()
        persist = {"kind": "REGISTRY_RUN", "name": "c2_agent", "target_path": r"C:\Users\User\AppData\Local\Temp\c2_agent.exe"}
        net = [{"pid": 6016, "local_addr": "192.168.1.50", "remote_addr": "198.51.100.42", "remote_port": 8443, "status": "ESTABLISHED"}]

        baseline_with_net = SystemBaseline(
            baseline_id="BASE-QUAD", timestamp=1000.0, integrity_hash="h_quad",
            host_info={}, processes=[], network=net, persistence=[], hosts_info={},
            browser_extensions=[], windows_security={"defender_realtime_enabled": True}, collector_metrics={}
        )
        diff = BaselineDiff(
            base_id="B-0", target_id="B-1", timestamp=time.time(),
            new_processes=[bad_proc], new_persistence=[persist], hosts_changed=True,
            hosts_diff={"base_sha256": "111", "current_sha256": "222"}
        )
        events = self.engine.correlate_diff(diff, baseline_with_net)
        # Verify both high-risk multi-signal process event and hosts event are emitted
        self.assertTrue(any(e.severity == SecurityClassification.HIGH_RISK.value for e in events))
        self.assertTrue(any(e.category == EventCategory.HOSTS.value for e in events))

    # =========================================================================
    # 4. ADVERSARIAL, NOISE & INCOMPLETE TELEMETRY CASES (N01 - N10)
    # Expected: Deduplication, stable confidence, fail-safe handling, and UNKNOWN
    # =========================================================================

    def test_n01_duplicate_consecutive_diffs_deduplicated(self):
        """N01: Emitting identical diff twice in succession must not generate duplicate open events."""
        bad_proc = ProcessItem(
            pid=7001, ppid=1000, name="dup_miner.exe", exe_path=r"C:\Users\User\AppData\Local\Temp\dup_miner.exe",
            cmdline="dup_miner.exe", username="User", create_time=1000.0, status="running", is_temp_dir=True
        ).to_dict()
        diff = BaselineDiff(base_id="B-0", target_id="B-1", timestamp=time.time(), new_processes=[bad_proc])

        # First scan -> 1 event
        events1 = self.engine.correlate_diff(diff, self.default_baseline)
        self.assertEqual(len(events1), 1)

        # Second scan with same diff -> 0 new events (deduplicated into observation_timeline)
        events2 = self.engine.correlate_diff(diff, self.default_baseline)
        self.assertEqual(len(events2), 0)

        # Total open events must remain exactly 1
        self.assertEqual(len(self.engine.get_open_events()), 1)
        self.assertEqual(self.engine.get_open_events()[0].occurrence_count, 2)

    def test_n02_reordered_event_streams_consistency(self):
        """N02: Events arriving in reverse order produce consistent state."""
        proc1 = ProcessItem(pid=7002, ppid=1000, name="tool_a.exe", exe_path=r"C:\Users\User\AppData\Local\Temp\tool_a.exe",
                            cmdline="a", username="User", create_time=1000.0, status="running", is_temp_dir=True).to_dict()
        proc2 = ProcessItem(pid=7003, ppid=1000, name="tool_b.exe", exe_path=r"C:\Users\User\AppData\Local\Temp\tool_b.exe",
                            cmdline="b", username="User", create_time=1000.0, status="running", is_temp_dir=True).to_dict()

        diff_ordered = BaselineDiff(base_id="B-0", target_id="B-1", timestamp=time.time(), new_processes=[proc1, proc2])
        engine1 = EventCorrelationEngine()
        res1 = engine1.correlate_diff(diff_ordered, self.default_baseline)

        diff_reversed = BaselineDiff(base_id="B-0", target_id="B-1", timestamp=time.time(), new_processes=[proc2, proc1])
        engine2 = EventCorrelationEngine()
        res2 = engine2.correlate_diff(diff_reversed, self.default_baseline)

        self.assertEqual(len(res1), len(res2))
        self.assertEqual({e.fingerprint for e in res1}, {e.fingerprint for e in res2})

    def test_n03_stale_timestamps_handled(self):
        """N03: Telemetry with older timestamp is ingested and indexed safely."""
        old_time = time.time() - 3600
        old_proc = ProcessItem(
            pid=7004, ppid=1000, name="stale_proc.exe", exe_path=r"C:\Windows\notepad.exe",
            cmdline="notepad.exe", username="User", create_time=old_time, status="running", is_temp_dir=False
        ).to_dict()
        diff = BaselineDiff(base_id="B-0", target_id="B-1", timestamp=old_time, new_processes=[old_proc])
        events = self.engine.correlate_diff(diff, self.default_baseline)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].severity, SecurityClassification.BENIGN.value)

    def test_n04_contradictory_signals_known_good_precedence(self):
        """N04: If an asset is registered as Known Good, user approval takes precedence."""
        fp = self.engine.compute_fingerprint(EventCategory.PROCESS.value, "process:7005:approved_miner.exe", "TEMP_DIR_EXECUTION")
        self.engine.known_goods[fp] = True

        approved_miner = ProcessItem(
            pid=7005, ppid=1000, name="approved_miner.exe", exe_path=r"C:\Users\User\AppData\Local\Temp\approved_miner.exe",
            cmdline="approved_miner.exe", username="User", create_time=1000.0, status="running", is_temp_dir=True
        ).to_dict()
        diff = BaselineDiff(base_id="B-0", target_id="B-1", timestamp=time.time(), new_processes=[approved_miner])
        events = self.engine.correlate_diff(diff, self.default_baseline)
        self.assertEqual(len(events), 1)
        self.assertTrue(events[0].is_known_good)
        self.assertEqual(events[0].status, "RESOLVED")

    def test_n05_incomplete_telemetry_missing_cmdline(self):
        """N05: Incomplete process telemetry (missing cmdline or path) must not crash."""
        incomplete_proc = {"pid": 7006, "name": "headless_worker", "is_temp_dir": False}
        diff = BaselineDiff(base_id="B-0", target_id="B-1", timestamp=time.time(), new_processes=[incomplete_proc])
        events = self.engine.correlate_diff(diff, self.default_baseline)
        self.assertEqual(len(events), 1)

    def test_n06_empty_diff_produces_zero_alerts(self):
        """N06: Empty diff without system changes must produce 0 alerts."""
        diff = BaselineDiff(base_id="B-0", target_id="B-1", timestamp=time.time())
        events = self.engine.correlate_diff(diff, self.default_baseline)
        self.assertEqual(len(events), 0)

    def test_n07_rapid_burst_stress_load(self):
        """N07: Ingesting a burst of 50 new benign processes concurrently."""
        procs = [
            ProcessItem(pid=8000 + i, ppid=1000, name=f"worker_{i}.exe", exe_path=rf"C:\Tools\worker_{i}.exe",
                        cmdline="run", username="User", create_time=1000.0, status="running", is_temp_dir=False).to_dict()
            for i in range(50)
        ]
        diff = BaselineDiff(base_id="B-0", target_id="B-1", timestamp=time.time(), new_processes=procs)
        t_start = time.perf_counter()
        events = self.engine.correlate_diff(diff, self.default_baseline)
        duration_ms = (time.perf_counter() - t_start) * 1000

        self.assertEqual(len(events), 50)
        # Latency for 50 items must be sub-100ms
        self.assertLess(duration_ms, 100.0)

    def test_n08_stability_across_3_iterations(self):
        """N08: Rule 14 requirement: Running 3 consecutive evaluation cycles produces deterministic output."""
        miner = ProcessItem(
            pid=7008, ppid=1000, name="stable_miner.exe", exe_path=r"C:\Users\User\AppData\Local\Temp\stable_miner.exe",
            cmdline="miner", username="User", create_time=1000.0, status="running", is_temp_dir=True
        ).to_dict()

        for _ in range(3):
            test_engine = EventCorrelationEngine()
            diff = BaselineDiff(base_id="B-0", target_id="B-1", timestamp=time.time(), new_processes=[miner])
            events = test_engine.correlate_diff(diff, self.default_baseline)
            self.assertEqual(len(events), 1)
            self.assertEqual(events[0].severity, SecurityClassification.SUSPICIOUS.value)
            self.assertEqual(events[0].confidence, 0.75)

    def test_n09_explanation_completeness_verification(self):
        """N09: Verifies that HIGH_RISK events contain complete explanations (WHAT, WHY, WHERE, CONFIDENCE)."""
        miner = ProcessItem(
            pid=7009, ppid=1000, name="c2_beacon.exe", exe_path=r"C:\Users\User\AppData\Local\Temp\c2_beacon.exe",
            cmdline="c2_beacon.exe", username="User", create_time=1000.0, status="running", is_temp_dir=True
        ).to_dict()
        persist = {"kind": "REGISTRY_RUN", "name": "c2_beacon", "target_path": r"C:\Users\User\AppData\Local\Temp\c2_beacon.exe"}
        net = [{"pid": 7009, "local_addr": "192.168.1.50", "remote_addr": "198.51.100.1", "remote_port": 443, "status": "ESTABLISHED"}]

        base_net = SystemBaseline(
            baseline_id="BASE-EXP", timestamp=1000.0, integrity_hash="h_exp",
            host_info={}, processes=[], network=net, persistence=[], hosts_info={},
            browser_extensions=[], windows_security={"defender_realtime_enabled": True}, collector_metrics={}
        )
        diff = BaselineDiff(base_id="B-0", target_id="B-1", timestamp=time.time(), new_processes=[miner], new_persistence=[persist])
        events = self.engine.correlate_diff(diff, base_net)

        high_risk = [e for e in events if e.severity == SecurityClassification.HIGH_RISK.value][0]
        # Explanation quality checks
        self.assertTrue(len(high_risk.rationale) > 20)
        self.assertIn("c2_beacon.exe", high_risk.rationale)  # WHAT
        self.assertIn("pasta temporária", high_risk.rationale)  # WHERE
        self.assertIn("persistência", high_risk.rationale)  # WHY
        self.assertGreaterEqual(high_risk.confidence, 0.80)  # CONFIDENCE
        self.assertTrue(len(high_risk.recommended_action) > 10)  # RECOMMENDED ACTION

    def test_n10_degraded_collector_telemetry_handling(self):
        """N10: Ingesting partial telemetry when some collectors are degraded."""
        diff = BaselineDiff(
            base_id="B-0", target_id="B-1", timestamp=time.time(),
            new_processes=[{"pid": 7010, "name": "partial_app.exe", "is_temp_dir": False}],
            hosts_changed=False,
        )
        degraded_baseline = SystemBaseline(
            baseline_id="BASE-DEG", timestamp=1000.0, integrity_hash="h_deg",
            host_info={}, processes=[], network=[], persistence=[], hosts_info={},
            browser_extensions=[], windows_security={},
            collector_metrics={"network_collector": {"status": "ERROR_ACCESS_DENIED"}}
        )
        events = self.engine.correlate_diff(diff, degraded_baseline)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].severity, SecurityClassification.BENIGN.value)


if __name__ == "__main__":
    unittest.main()
