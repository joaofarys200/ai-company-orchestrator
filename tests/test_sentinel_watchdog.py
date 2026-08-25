"""
Unit and Integration tests for SentinelWatchdogService (Fase S2).
"""

import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from security.sentinel.baseline import BaselineEngine
from security.sentinel.contracts import (
    BaselineDiff,
    SecurityClassification,
    SecurityPosture,
    SystemBaseline,
)
from security.sentinel.watchdog import SentinelWatchdogService


class TestSentinelWatchdog(unittest.IsolatedAsyncioTestCase):
    """Testes de ciclo de vida e monitorização contínua do Watchdog."""

    async def asyncSetUp(self):
        self.mock_baseline_engine = MagicMock(spec=BaselineEngine)
        self.mock_baseline = SystemBaseline(
            baseline_id="BASELINE-TEST-1234",
            timestamp=1000.0,
            integrity_hash="fake-sha256-hash",
            host_info={"hostname": "TEST-HOST"},
            processes=[{"pid": 100, "name": "explorer.exe", "is_temp_dir": False}],
            network=[{"protocol": "TCP", "local_port": 80, "status": "LISTEN"}],
            persistence=[{"kind": "SERVICE", "name": "wuauserv"}],
            hosts_info={"line_count": 20},
            browser_extensions=[],
            windows_security={"defender_realtime_enabled": True, "firewall_public_enabled": True},
            collector_metrics={},
        )
        self.mock_baseline_engine.get_active_baseline.return_value = self.mock_baseline
        self.mock_baseline_engine.capture_baseline.return_value = self.mock_baseline
        self.mock_baseline_engine.compare.return_value = BaselineDiff(
            base_id="BASELINE-TEST-1234",
            target_id="BASELINE-TEST-1234",
            timestamp=1001.0,
        )

        self.event_cb = AsyncMock()
        self.status_cb = AsyncMock()

        self.watchdog = SentinelWatchdogService(
            scan_interval_seconds=1,
            event_callback=self.event_cb,
            status_callback=self.status_cb,
            baseline_engine=self.mock_baseline_engine,
        )

    async def asyncTearDown(self):
        await self.watchdog.stop()

    async def test_watchdog_startup_and_shutdown(self):
        """S2-01 & S2-02: Watchdog inicia e termina de forma limpa."""
        self.assertFalse(self.watchdog.is_running)
        await self.watchdog.start()
        self.assertTrue(self.watchdog.is_running)
        self.assertFalse(self.watchdog.is_paused)

        status = self.watchdog.get_status_dict()
        self.assertEqual(status["status"], "RUNNING")
        self.assertEqual(status["schema_version"], 1)

        await self.watchdog.stop()
        self.assertFalse(self.watchdog.is_running)

    async def test_watchdog_pause_and_resume(self):
        """Watchdog pausa e retoma corretamente."""
        await self.watchdog.start()
        self.watchdog.pause()
        self.assertTrue(self.watchdog.is_paused)
        self.assertEqual(self.watchdog.get_status_dict()["status"], "PAUSED")

        self.watchdog.resume()
        self.assertFalse(self.watchdog.is_paused)
        self.assertEqual(self.watchdog.get_status_dict()["status"], "RUNNING")

    async def test_watchdog_periodic_scan_execution(self):
        """S2-03: Executa scans periódicos em background."""
        await self.watchdog.start()
        # Aguarda 1.5s para que o loop execute pelo menos 1 ciclo
        await asyncio.sleep(1.5)
        self.assertGreaterEqual(self.watchdog.total_scans, 1)

    async def test_watchdog_manual_audit(self):
        """S2-10: Executa auditoria sob demanda com resultado estruturado."""
        result = await self.watchdog.run_manual_audit()
        self.assertIn("baseline_id", result)
        self.assertIn("duration_seconds", result)
        self.assertEqual(self.watchdog.total_scans, 1)

    async def test_watchdog_posture_calculation(self):
        """Calcula a postura com base no estado dos eventos."""
        posture = self.watchdog.get_posture()
        self.assertEqual(posture, SecurityPosture.GOOD)

        # Regista um evento de risco elevado
        from security.sentinel.contracts import SecurityEvent
        ev = SecurityEvent(
            event_id="EV-1",
            fingerprint="FP-1",
            timestamp=1000.0,
            first_seen=1000.0,
            last_seen=1000.0,
            occurrence_count=1,
            category="PROCESS",
            severity=SecurityClassification.HIGH_RISK.value,
            confidence=0.9,
            evidence_ids=["p:1"],
            rationale="Anomalia crítica",
            recommended_action="Inspecionar",
        )
        self.watchdog.correlation_engine.active_events[ev.fingerprint] = ev
        self.assertEqual(self.watchdog.get_posture(), SecurityPosture.HIGH_RISK)


if __name__ == "__main__":
    unittest.main()
