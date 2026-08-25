"""
Lifecycle and Concurrency tests for SentinelWatchdogService (Fase S2).
"""

import asyncio
import unittest
from unittest.mock import MagicMock

from security.sentinel.baseline import BaselineEngine
from security.sentinel.contracts import BaselineDiff, SystemBaseline
from security.sentinel.watchdog import SentinelWatchdogService


class TestSentinelLifecycle(unittest.IsolatedAsyncioTestCase):
    """Testes de concorrência e integração de ciclo de vida do Sentinel."""

    async def asyncSetUp(self):
        self.mock_engine = MagicMock(spec=BaselineEngine)
        self.baseline = SystemBaseline(
            baseline_id="BASE-LIFECYCLE",
            timestamp=1000.0,
            integrity_hash="hash-life",
            host_info={},
            processes=[],
            network=[],
            persistence=[],
            hosts_info={},
            browser_extensions=[],
            windows_security={},
            collector_metrics={},
        )
        self.mock_engine.get_active_baseline.return_value = self.baseline
        self.mock_engine.capture_baseline.return_value = self.baseline
        self.mock_engine.compare.return_value = BaselineDiff(base_id="BASE-LIFECYCLE", target_id="BASE-LIFECYCLE", timestamp=1001.0)

        self.watchdog = SentinelWatchdogService(
            scan_interval_seconds=60,
            baseline_engine=self.mock_engine,
        )

    async def asyncTearDown(self):
        await self.watchdog.stop()

    async def test_concurrent_audits_prevented_by_lock(self):
        """S2-13: Prevenção de auditorias manuais concorrentes simultâneas."""
        # Executa duas auditorias em paralelo
        results = await asyncio.gather(
            self.watchdog.run_manual_audit(),
            self.watchdog.run_manual_audit(),
        )
        self.assertEqual(len(results), 2)
        self.assertEqual(self.watchdog.total_scans, 2)
        self.assertFalse(self.watchdog._is_auditing_now)

    async def test_watchdog_restart_recovery(self):
        """S2-14: Watchdog pode ser reiniciado sem duplicar tarefas órfãs."""
        await self.watchdog.start()
        self.assertTrue(self.watchdog.is_running)

        # Para e reinicia
        await self.watchdog.stop()
        self.assertFalse(self.watchdog.is_running)

        await self.watchdog.start()
        self.assertTrue(self.watchdog.is_running)

        status = self.watchdog.get_status_dict()
        self.assertEqual(status["status"], "RUNNING")


if __name__ == "__main__":
    unittest.main()
