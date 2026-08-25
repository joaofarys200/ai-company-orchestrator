"""
JARVIS OS — Test Suite: Sentinel S2.5 Shutdown & Resource Cleanup
Validação empírica de cancelamento limpo de background tasks e ausência de tasks órfãs.
"""

import asyncio
import unittest
from security.sentinel.contracts import SentinelLifecycleState
from security.sentinel.watchdog import SentinelWatchdogService


class TestSentinelShutdown(unittest.IsolatedAsyncioTestCase):
    """Testes de paragem e limpeza de recursos."""

    async def test_clean_shutdown_without_orphan_tasks(self):
        """Valida que o método stop() cancela a background task e limpa os recursos perfeitamente."""
        watchdog = SentinelWatchdogService(scan_interval_seconds=1)
        await watchdog.start()
        self.assertTrue(watchdog.is_running)
        task = watchdog._task
        self.assertIsNotNone(task)
        self.assertFalse(task.done())

        # Executa paragem
        await watchdog.stop()

        self.assertFalse(watchdog.is_running)
        self.assertEqual(watchdog.lifecycle_state, SentinelLifecycleState.STOPPED)
        self.assertIsNone(watchdog._task)
        self.assertTrue(task.done())

    async def test_repeated_shutdown_cycles(self):
        """Valida 5 ciclos consecutivos de start -> running -> stop sem conflitos ou leaks."""
        for cycle in range(1, 6):
            watchdog = SentinelWatchdogService(scan_interval_seconds=1)
            await watchdog.start()
            self.assertTrue(watchdog.is_running)
            await asyncio.sleep(0.05)
            await watchdog.stop()
            self.assertFalse(watchdog.is_running)
            self.assertEqual(watchdog.lifecycle_state, SentinelLifecycleState.STOPPED)

