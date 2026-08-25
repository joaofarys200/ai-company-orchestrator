"""
JARVIS OS — Test Suite: Sentinel S2.5 Degraded Mode & Collector Fault Tolerance
Validação empírica de resiliência a falhas de coletores individuais sem derrubar o sistema.
"""

import asyncio
import unittest
import tempfile
import shutil

from security.sentinel.contracts import (
    EventCategory,
    SentinelLifecycleState,
    SecurityPosture,
)
from security.sentinel.watchdog import SentinelWatchdogService
from security.sentinel.baseline import BaselineEngine
from security.sentinel.collectors.base import BaseCollector


class FailingCollector(BaseCollector):
    """Coletor com injeção de falha propositada para testar o modo degradado."""

    def __init__(self, name: str = "simulated_flaky_collector"):
        super().__init__(name=name, category=EventCategory.SYSTEM)

    def collect(self):
        raise RuntimeError("Simulated collector hardware/timeout fault")


class FastDummyCollector(BaseCollector):
    """Coletor rápido para testes unitários determinísticos."""

    def __init__(self, name: str = "process_collector"):
        super().__init__(name=name, category=EventCategory.PROCESS)

    def collect(self):
        return [
            self.create_evidence(
                asset="process:dummy.exe",
                observation="Dummy process for testing",
                normalized_data={"pid": 999, "name": "dummy.exe", "is_temp_dir": False},
            )
        ]


class TestSentinelDegradedMode(unittest.IsolatedAsyncioTestCase):
    """Testes de modo degradado e tolerância a falhas parciais."""

    async def asyncSetUp(self):
        self.tmp_dir = tempfile.mkdtemp()

    async def asyncTearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    async def test_sentinel_enters_degraded_mode_when_collector_fails(self):
        """Valida que uma falha num coletor coloca o Sentinel em DEGRADED com telemetria explicável."""
        engine = BaselineEngine(storage_dir=self.tmp_dir)
        # Substitui coletores pesados pelos controlados pelo teste
        engine.collectors = [
            FastDummyCollector(name="process_collector"),
            FailingCollector(name="simulated_flaky_collector"),
        ]

        watchdog = SentinelWatchdogService(scan_interval_seconds=60, baseline_engine=engine)
        await watchdog.start()

        # Aguarda o baseline ser concluído em background
        for _ in range(20):
            if watchdog.is_baseline_ready:
                break
            await asyncio.sleep(0.05)

        self.assertTrue(watchdog.is_baseline_ready)
        self.assertEqual(watchdog.lifecycle_state, SentinelLifecycleState.DEGRADED)
        self.assertIn("simulated_flaky_collector", watchdog.degraded_collectors)
        self.assertIn("Falha parcial nos coletores", str(watchdog.degraded_reason))
        self.assertEqual(watchdog.get_posture(), SecurityPosture.DEGRADED)

        status = watchdog.get_status_dict()
        self.assertEqual(status["lifecycle_state"], "DEGRADED")
        self.assertEqual(status["posture"], "DEGRADED")
        self.assertIn("simulated_flaky_collector", status["degraded_collectors"])

        # Valida que uma auditoria manual subsequente também mantém o estado consistente
        audit_res = await watchdog.run_manual_audit()
        self.assertIsNotNone(audit_res["baseline_id"])
        self.assertEqual(audit_res["processes_count"], 1)

        await watchdog.stop()

