"""
Unit tests for Sentinel EventCorrelationEngine (Fase S2).
"""

import unittest

from security.sentinel.contracts import (
    BaselineDiff,
    EventCategory,
    SecurityClassification,
    SystemBaseline,
)
from security.sentinel.correlation import EventCorrelationEngine


class TestSentinelCorrelation(unittest.TestCase):
    """Testes de correlação de sinais e geração de SecurityEvents."""

    def setUp(self):
        self.engine = EventCorrelationEngine()
        self.baseline = SystemBaseline(
            baseline_id="BASE-1",
            timestamp=1000.0,
            integrity_hash="hash1",
            host_info={},
            processes=[],
            network=[{"protocol": "TCP", "local_port": 443, "status": "ESTABLISHED", "pid": 999}],
            persistence=[],
            hosts_info={},
            browser_extensions=[],
            windows_security={"defender_realtime_enabled": True, "firewall_public_enabled": True},
            collector_metrics={},
        )

    def test_benign_new_process_observation(self):
        """S2-04: Processo novo fora de %TEMP% gera evento de severidade BENIGN sem alarme falso."""
        diff = BaselineDiff(
            base_id="BASE-1",
            target_id="BASE-2",
            timestamp=1000.0,
            new_processes=[{"pid": 200, "name": "notepad.exe", "exe_path": "C:\\Windows\\notepad.exe", "is_temp_dir": False}],
        )
        events = self.engine.correlate_diff(diff, self.baseline)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].severity, SecurityClassification.BENIGN.value)
        self.assertEqual(events[0].category, EventCategory.PROCESS.value)

    def test_triple_signal_correlation_temp_persistence_network(self):
        """S2-08: Triplo sinal (%TEMP% + Persistência + Rede) gera HIGH_RISK com alta confiança."""
        diff = BaselineDiff(
            base_id="BASE-1",
            target_id="BASE-2",
            timestamp=1000.0,
            new_processes=[{
                "pid": 999,
                "name": "malware.exe",
                "exe_path": "C:\\Users\\user\\AppData\\Local\\Temp\\malware.exe",
                "is_temp_dir": True,
            }],
            new_persistence=[{
                "kind": "REGISTRY_RUN",
                "name": "malware",
                "target_path": "C:\\Users\\user\\AppData\\Local\\Temp\\malware.exe",
            }],
        )
        events = self.engine.correlate_diff(diff, self.baseline)
        high_risk = [e for e in events if e.severity == SecurityClassification.HIGH_RISK.value]
        self.assertEqual(len(high_risk), 1)
        self.assertGreaterEqual(high_risk[0].confidence, 0.85)
        self.assertIn("pasta temporária", high_risk[0].rationale)

    def test_hosts_file_modification_detection(self):
        """S2-06: Alteração do ficheiro hosts gera evento de categoria HOSTS."""
        diff = BaselineDiff(
            base_id="BASE-1",
            target_id="BASE-2",
            timestamp=1000.0,
            hosts_changed=True,
            hosts_diff={"base_sha256": "1111", "current_sha256": "2222"},
        )
        events = self.engine.correlate_diff(diff, self.baseline)
        hosts_events = [e for e in events if e.category == EventCategory.HOSTS.value]
        self.assertEqual(len(hosts_events), 1)
        self.assertEqual(hosts_events[0].severity, SecurityClassification.SUSPICIOUS.value)

    def test_defender_realtime_disabled_alert(self):
        """Alerta imediato se o Defender for desativado."""
        degraded_baseline = SystemBaseline(
            baseline_id="BASE-2",
            timestamp=1000.0,
            integrity_hash="hash2",
            host_info={},
            processes=[],
            network=[],
            persistence=[],
            hosts_info={},
            browser_extensions=[],
            windows_security={"defender_realtime_enabled": False, "firewall_public_enabled": True},
            collector_metrics={},
        )
        diff = BaselineDiff(base_id="BASE-1", target_id="BASE-2", timestamp=1000.0)
        events = self.engine.correlate_diff(diff, degraded_baseline)
        def_events = [e for e in events if e.category == EventCategory.DEFENDER.value]
        self.assertEqual(len(def_events), 1)
        self.assertEqual(def_events[0].severity, SecurityClassification.HIGH_RISK.value)


if __name__ == "__main__":
    unittest.main()
