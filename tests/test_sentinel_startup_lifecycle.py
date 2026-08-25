"""
JARVIS OS — Test Suite: Sentinel S2.5 Startup & Lifecycle Reliability
Validação empírica de transição de estados de ciclo de vida e arranque não-bloqueante.
"""

import asyncio
import time
import unittest
from unittest.mock import MagicMock

from security.sentinel.contracts import SentinelLifecycleState, SecurityPosture
from security.sentinel.watchdog import SentinelWatchdogService
from security.sentinel.baseline import BaselineEngine


class TestSentinelStartupLifecycle(unittest.IsolatedAsyncioTestCase):
    """Testes de inicialização não bloqueante e ciclo de vida do Sentinel."""

    async def test_watchdog_non_blocking_startup_and_lifecycle_transitions(self):
        """Valida que o arranque do watchdog não bloqueia a execução e transita os estados corretamente."""
        mock_engine = MagicMock(spec=BaselineEngine)
        fake_baseline = MagicMock()
        fake_baseline.baseline_id = "BASELINE-MOCK-1"
        fake_baseline.collector_metrics = {"proc": {"status": "OK"}}
        fake_baseline.processes = []
        fake_baseline.network = []
        fake_baseline.persistence = []
        mock_engine.capture_baseline.return_value = fake_baseline
        mock_engine.get_active_baseline.return_value = None

        watchdog = SentinelWatchdogService(scan_interval_seconds=60, baseline_engine=mock_engine)
        
        self.assertEqual(watchdog.lifecycle_state, SentinelLifecycleState.STOPPED)
        self.assertFalse(watchdog.is_baseline_ready)

        # Inicia o watchdog
        t0 = time.time()
        await watchdog.start()
        startup_latency = time.time() - t0

        # Startup deve ser quase instantâneo (< 200ms) porque o baseline corre em background
        self.assertLess(startup_latency, 0.2, f"Startup bloqueou a thread durante {startup_latency:.2f}s")
        self.assertTrue(watchdog.is_running)

        # Aguarda a conclusão do baseline em background
        for _ in range(20):
            if watchdog.is_baseline_ready:
                break
            await asyncio.sleep(0.05)

        self.assertTrue(watchdog.is_baseline_ready, "Baseline inicial não ficou pronto a tempo")
        self.assertEqual(watchdog.lifecycle_state, SentinelLifecycleState.READY)
        self.assertIsNotNone(watchdog.active_baseline)

        status = watchdog.get_status_dict()
        self.assertEqual(status["status"], "RUNNING")
        self.assertEqual(status["lifecycle_state"], "READY")
        self.assertTrue(status["is_baseline_ready"])
        self.assertGreaterEqual(status["baseline_duration_seconds"], 0.0)

        await watchdog.stop()
        self.assertEqual(watchdog.lifecycle_state, SentinelLifecycleState.STOPPED)

    async def test_prevent_duplicate_watchdog_start(self):
        """Valida que múltiplas chamadas a start() não criam instâncias duplicadas de background tasks."""
        watchdog = SentinelWatchdogService(scan_interval_seconds=60)
        await watchdog.start()
        first_task = watchdog._task

        # Segunda chamada imediata
        await watchdog.start()
        self.assertIs(watchdog._task, first_task, "Foi criada uma nova task duplicada indevidamente")

        await watchdog.stop()

    async def test_watchdog_pause_resume_state_transitions(self):
        """Valida transições de estado durante pause e resume."""
        watchdog = SentinelWatchdogService(scan_interval_seconds=60)
        await watchdog.start()

        watchdog.pause()
        self.assertTrue(watchdog.is_paused)
        self.assertEqual(watchdog.lifecycle_state, SentinelLifecycleState.PAUSED)
        self.assertEqual(watchdog.get_status_dict()["status"], "PAUSED")

        watchdog.resume()
        self.assertFalse(watchdog.is_paused)
        self.assertIn(watchdog.lifecycle_state, (SentinelLifecycleState.READY, SentinelLifecycleState.STARTING))

        await watchdog.stop()

