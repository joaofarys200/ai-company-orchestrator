"""
JARVIS OS — Security Sentinel Test Suite
Testes unitários, de integração e de baseline para a Fase S1 (Read-Only Security Audit).
"""

import os
import json
import tempfile
import pytest

from security.sentinel.contracts import (
    SecurityClassification,
    EventCategory,
    IncidentStatus,
    PrivacyClassification,
    SecurityEvidence,
    SecurityEvent,
    ProcessItem,
    NetworkItem,
    PersistenceItem,
    HostsInfo,
    BrowserExtensionItem,
    WindowsSecurityStatus,
    SystemBaseline,
    BaselineDiff,
)
from security.sentinel.collectors.base import BaseCollector
from security.sentinel.collectors.processes import ProcessCollector
from security.sentinel.collectors.network import NetworkCollector
from security.sentinel.collectors.persistence import PersistenceCollector
from security.sentinel.collectors.hosts import HostsCollector
from security.sentinel.collectors.browser import BrowserCollector
from security.sentinel.collectors.security_events import WindowsSecurityEventsCollector
from security.sentinel.baseline import BaselineEngine
from security.sentinel.audit import SecurityAuditRunner


class DummyCollector(BaseCollector):
    def __init__(self):
        super().__init__(name="dummy_collector", category=EventCategory.SYSTEM)

    def collect(self):
        return [
            self.create_evidence(
                asset="dummy:test",
                observation="Dummy observation",
                normalized_data={"key": "value"},
            )
        ]


def test_sentinel_contracts_and_enums():
    assert SecurityClassification.BENIGN == "BENIGN"
    assert SecurityClassification.SUSPICIOUS == "SUSPICIOUS"
    assert SecurityClassification.HIGH_RISK == "HIGH_RISK"
    assert SecurityClassification.CONFIRMED_MALICIOUS == "CONFIRMED_MALICIOUS"
    assert SecurityClassification.UNKNOWN == "UNKNOWN"

    assert EventCategory.PROCESS == "PROCESS"
    assert EventCategory.PERSISTENCE == "PERSISTENCE"
    assert EventCategory.NETWORK == "NETWORK"
    assert EventCategory.HOSTS == "HOSTS"
    assert EventCategory.DEFENDER == "DEFENDER"

    assert IncidentStatus.OPEN == "OPEN"
    assert IncidentStatus.FALSE_POSITIVE == "FALSE_POSITIVE"


def test_base_collector_sanitization_and_hashing():
    collector = DummyCollector()

    # Secret sanitization
    raw_cmd = "myapp.exe --password=Secret123 --token=abc987654 -p SuperSecret"
    sanitized = collector.sanitize_cmdline(raw_cmd)
    assert "Secret123" not in sanitized
    assert "abc987654" not in sanitized
    assert "SuperSecret" not in sanitized
    assert "***REDACTED***" in sanitized

    # File hashing
    with tempfile.NamedTemporaryFile("w", delete=False) as tmp:
        tmp.write("JARVIS_SECURITY_TEST_CONTENT")
        tmp_path = tmp.name

    try:
        h = collector.compute_sha256(tmp_path)
        assert len(h) == 64
        # Empty for non-existent file
        assert collector.compute_sha256("non_existent_file_path_123.exe") == ""
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


def test_base_collector_creates_valid_evidence():
    collector = DummyCollector()
    evidences = collector.collect()
    assert len(evidences) == 1
    ev = evidences[0]
    assert ev.collector == "dummy_collector"
    assert ev.asset == "dummy:test"
    assert ev.observation == "Dummy observation"
    assert ev.confidence == 1.0
    assert len(ev.sha256) == 64


def test_process_collector_execution():
    collector = ProcessCollector()
    evidences = collector.collect()
    assert len(evidences) > 0

    # Ensure current python process is in the collected list
    current_pid = os.getpid()
    found_current = False
    for ev in evidences:
        data = ev.normalized_data
        if data.get("pid") == current_pid:
            found_current = True
            assert "python" in data.get("name", "").lower()
            break
    assert found_current, f"Current PID {current_pid} should be present in process collection"


def test_network_collector_execution():
    collector = NetworkCollector()
    evidences = collector.collect()
    # On any running OS there are usually active or listening connections
    assert isinstance(evidences, list)
    for ev in evidences:
        data = ev.normalized_data
        assert "protocol" in data
        assert "local_port" in data


def test_persistence_collector_execution():
    collector = PersistenceCollector()
    evidences = collector.collect()
    assert isinstance(evidences, list)
    # Validate structure of collected persistence items
    for ev in evidences:
        data = ev.normalized_data
        assert "kind" in data
        assert "name" in data


def test_hosts_collector_with_custom_file():
    hosts_content = """
# Copyright (c) 1993-2009 Microsoft Corp.
127.0.0.1       localhost
::1             localhost
192.168.1.50    mydevserver.local
0.0.0.0         telemetry.tracking.domain
"""
    with tempfile.NamedTemporaryFile("w", delete=False, encoding="utf-8") as tmp:
        tmp.write(hosts_content)
        tmp_path = tmp.name

    try:
        collector = HostsCollector(hosts_path=tmp_path)
        evidences = collector.collect()
        assert len(evidences) == 1
        data = evidences[0].normalized_data
        assert data["exists"] is True
        assert len(data["sha256"]) == 64
        assert len(data["custom_entries"]) >= 4
        domains = [entry["domain"] for entry in data["custom_entries"]]
        assert "localhost" in domains
        assert "mydevserver.local" in domains
        assert "telemetry.tracking.domain" in domains
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


def test_browser_collector_manifest_resolution():
    with tempfile.TemporaryDirectory() as tmp_dir:
        # Create simulated extension structure
        ext_dir = os.path.join(tmp_dir, "test_ext_id", "1.0.0_0")
        os.makedirs(ext_dir, exist_ok=True)
        manifest = {
            "name": "Security Test Extension",
            "version": "1.0.0",
            "description": "Defensive testing extension",
            "permissions": ["storage", "tabs", "cookies"],
        }
        with open(os.path.join(ext_dir, "manifest.json"), "w", encoding="utf-8") as f:
            json.dump(manifest, f)

        collector = BrowserCollector()
        items = collector._scan_chromium_extensions(tmp_dir, "TEST_BROWSER")
        assert len(items) == 1
        item = items[0]
        assert item.extension_id == "test_ext_id"
        assert item.name == "Security Test Extension"
        assert item.version == "1.0.0"
        assert "cookies" in item.permissions


def test_baseline_engine_capture_and_diff():
    with tempfile.TemporaryDirectory() as tmp_dir:
        engine = BaselineEngine(storage_dir=tmp_dir)

        # 1. Capture base snapshot
        baseline_a = engine.capture_baseline(baseline_id="BASE-A")
        assert baseline_a.baseline_id == "BASE-A"
        assert len(baseline_a.integrity_hash) == 64
        assert len(baseline_a.processes) > 0

        # Save and load
        saved_path = engine.save_baseline(baseline_a)
        assert os.path.isfile(saved_path)
        loaded_a = engine.load_baseline("BASE-A")
        assert loaded_a is not None
        assert loaded_a.integrity_hash == baseline_a.integrity_hash

        # 2. Simulate target baseline with simulated additions
        baseline_b = SystemBaseline(
            baseline_id="BASE-B",
            timestamp=baseline_a.timestamp + 100,
            integrity_hash="fake_hash_b",
            host_info=baseline_a.host_info,
            processes=baseline_a.processes + [
                {
                    "pid": 99999,
                    "ppid": 1,
                    "name": "suspicious_process.exe",
                    "exe_path": r"C:\Users\User\AppData\Local\Temp\suspicious_process.exe",
                    "cmdline": "suspicious_process.exe",
                    "username": "user",
                    "create_time": 12345.0,
                    "status": "running",
                    "sha256": "fakehash",
                    "is_temp_dir": True,
                }
            ],
            network=baseline_a.network + [
                {
                    "protocol": "TCP",
                    "local_address": "0.0.0.0",
                    "local_port": 44444,
                    "remote_address": None,
                    "remote_port": None,
                    "status": "LISTEN",
                    "pid": 99999,
                    "process_name": "suspicious_process.exe",
                }
            ],
            persistence=baseline_a.persistence + [
                {
                    "kind": "REGISTRY_RUN",
                    "name": "MaliciousBackdoor",
                    "target_path": r"C:\Users\User\AppData\Local\Temp\suspicious_process.exe",
                    "arguments": "",
                    "location": "HKCU_RUN\\MaliciousBackdoor",
                    "sha256": "fakehash",
                    "is_active": True,
                }
            ],
            hosts_info=baseline_a.hosts_info,
            browser_extensions=baseline_a.browser_extensions,
            windows_security=baseline_a.windows_security,
            collector_metrics=baseline_a.collector_metrics,
        )

        # 3. Compute Deterministic Diff
        diff = engine.compare(baseline_a, baseline_b)
        assert len(diff.new_processes) == 1
        assert diff.new_processes[0]["name"] == "suspicious_process.exe"

        assert len(diff.new_listening_ports) == 1
        assert diff.new_listening_ports[0]["local_port"] == 44444

        assert len(diff.new_persistence) == 1
        assert diff.new_persistence[0]["name"] == "MaliciousBackdoor"


def test_security_audit_runner_full_run():
    with tempfile.TemporaryDirectory() as tmp_dir:
        b_engine = BaselineEngine(storage_dir=os.path.join(tmp_dir, "baselines"))
        runner = SecurityAuditRunner(
            baseline_engine=b_engine,
            reports_dir=os.path.join(tmp_dir, "reports"),
        )

        result = runner.run_audit(save=True)
        assert "baseline" in result
        assert "summary" in result
        assert os.path.isfile(result["baseline_path"])
        assert os.path.isfile(result["report_path"])

        summary = result["summary"]
        assert summary["counts"]["processes"] > 0
        assert "duration_seconds" in summary

        # Read and verify generated markdown report
        with open(result["report_path"], "r", encoding="utf-8") as f:
            md_text = f.read()

        assert "# 🛡️ JARVIS OS — Security Sentinel Audit Report" in md_text
        assert "Resumo Executivo da Telemetria" in md_text
        assert "READ-ONLY" in md_text
