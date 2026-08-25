"""
Unit tests for Sentinel Event Deduplication & Known Good Engine (Fase S2).
"""

import unittest
import time

from security.sentinel.contracts import (
    BaselineDiff,
    KnownGoodItem,
    SecurityClassification,
    SystemBaseline,
)
from security.sentinel.correlation import EventCorrelationEngine


class TestSentinelDeduplication(unittest.TestCase):
    """Testes de deduplicação temporal e registo de Known Good."""

    def setUp(self):
        self.engine = EventCorrelationEngine()
        self.baseline = SystemBaseline(
            baseline_id="BASE-1",
            timestamp=1000.0,
            integrity_hash="hash1",
            host_info={},
            processes=[],
            network=[],
            persistence=[],
            hosts_info={},
            browser_extensions=[],
            windows_security={"defender_realtime_enabled": True, "firewall_public_enabled": True},
            collector_metrics={},
        )

    def test_repeated_diff_does_not_create_duplicate_events(self):
        """S2-07: Scans subsequentes com a mesma alteração não geram múltiplos eventos."""
        diff = BaselineDiff(
            base_id="BASE-1",
            target_id="BASE-2",
            timestamp=1000.0,
            new_processes=[{"pid": 300, "name": "updater.exe", "exe_path": "C:\\Program Files\\updater.exe", "is_temp_dir": False}],
        )

        # Scan 1: Cria o evento
        events_1 = self.engine.correlate_diff(diff, self.baseline)
        self.assertEqual(len(events_1), 1)
        self.assertEqual(len(self.engine.active_events), 1)

        fp = events_1[0].fingerprint
        self.assertEqual(self.engine.active_events[fp].occurrence_count, 1)

        # Scan 2: Mesma alteração persistente
        events_2 = self.engine.correlate_diff(diff, self.baseline)
        # Não emite novo evento (deve retornar lista vazia)
        self.assertEqual(len(events_2), 0)
        # Mantém apenas 1 evento com contagem 2
        self.assertEqual(len(self.engine.active_events), 1)
        self.assertEqual(self.engine.active_events[fp].occurrence_count, 2)
        self.assertEqual(len(self.engine.active_events[fp].observation_timeline), 2)

    def test_known_good_registration_resolves_and_suppresses_alerts(self):
        """S2-09: Itens aprovados como Known Good são marcados como resolvidos."""
        diff = BaselineDiff(
            base_id="BASE-1",
            target_id="BASE-2",
            timestamp=1000.0,
            new_persistence=[{"kind": "REGISTRY_RUN", "name": "CustomTool", "target_path": "C:\\Tools\\run.exe"}],
        )

        events = self.engine.correlate_diff(diff, self.baseline)
        self.assertEqual(len(events), 1)
        fp = events[0].fingerprint
        self.assertEqual(self.engine.active_events[fp].status, "OPEN")

        # Utilizador aprova o item como Known Good
        kg = KnownGoodItem(
            item_key=fp,
            category="PERSISTENCE",
            accepted_by="joao",
            accepted_at=time.time(),
            reason="Ferramenta interna legítima",
            previous_state={},
            current_state={},
        )
        self.engine.register_known_good(kg)

        self.assertTrue(self.engine.is_known_good(fp))
        self.assertEqual(self.engine.active_events[fp].status, "RESOLVED")
        self.assertTrue(self.engine.active_events[fp].is_known_good)
        self.assertEqual(len(self.engine.get_open_events()), 0)


if __name__ == "__main__":
    unittest.main()
