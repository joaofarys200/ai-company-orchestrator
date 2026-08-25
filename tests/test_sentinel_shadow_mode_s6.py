"""
JARVIS OS — Sentinel Phase S6: Real-World Shadow Mode & Detection Telemetry Test Suite
Validação exaustiva do Shadow Mode (100% Read-Only), Human Review, métricas de fadiga de alertas e separação de falhas de coletores.
"""

from __future__ import annotations

import json
import os
import tempfile
import time
import unittest

from security.sentinel.contracts import (
    BaselineDiff,
    EventCategory,
    HumanIncidentReview,
    KnownGoodItem,
    SecurityClassification,
    SecurityEvent,
    SecurityEvidence,
    SecurityPosture,
    SentinelLifecycleState,
    SentinelShadowModeState,
    SystemBaseline,
)
from security.sentinel.correlation import EventCorrelationEngine
from security.sentinel.watchdog import SentinelWatchdogService


class MockResponseEngine:
    """Mock do motor de resposta defensiva para testar bloqueio em Shadow Mode."""
    def __init__(self) -> None:
        self.actions = []

    def get_actions(self):
        return self.actions

    async def approve_and_execute(self, action_id, user, session_id, incident_id=None, timestamp=None):
        return True, {"action_id": action_id, "status": "COMPLETED"}, "Action executed"

    async def rollback(self, action_id, user, session_id):
        return True, {"action_id": action_id, "status": "ROLLED_BACK"}, "Action rolled back"

    def reject(self, action_id, user, reason):
        return True, {"action_id": action_id, "status": "REJECTED"}, "Action rejected"


class TestSentinelShadowModeS6(unittest.IsolatedAsyncioTestCase):
    """Test suite para validação do Shadow Mode, Telemetria e Human Review (Fase S6)."""

    async def test_shadow_mode_lifecycle_states(self) -> None:
        """Valida a máquina de estados do Shadow Mode (STARTING, COLLECTING, ANALYZING, PAUSED, STOPPED, DEGRADED)."""
        watchdog = SentinelWatchdogService(scan_interval_seconds=60)
        self.assertTrue(watchdog.shadow_mode)
        self.assertEqual(watchdog.shadow_mode_state, SentinelShadowModeState.COLLECTING)

        status = watchdog.get_status_dict()
        self.assertTrue(status["shadow_mode"])
        self.assertEqual(status["shadow_state"], "COLLECTING")

        # Transição para ANALYZING
        watchdog.shadow_mode_state = SentinelShadowModeState.ANALYZING
        self.assertEqual(watchdog.get_status_dict()["shadow_state"], "ANALYZING")

        # Transição para PAUSED
        watchdog.shadow_mode_state = SentinelShadowModeState.PAUSED
        self.assertEqual(watchdog.get_status_dict()["shadow_state"], "PAUSED")

        # Transição para DEGRADED
        watchdog.shadow_mode_state = SentinelShadowModeState.DEGRADED
        self.assertEqual(watchdog.get_status_dict()["shadow_state"], "DEGRADED")

    async def test_shadow_mode_mutative_actions_blocked(self) -> None:
        """Garante que qualquer tentativa de aprovação/execução de ação é estritamente bloqueada em Shadow Mode."""
        mock_resp = MockResponseEngine()
        watchdog = SentinelWatchdogService(response_engine=mock_resp, scan_interval_seconds=60)
        watchdog.shadow_mode = True

        success, action, msg = await watchdog.approve_and_execute_action(
            action_id="ACT-TEST-001",
            user="human_operator",
            session_id="test_session",
        )

        self.assertFalse(success)
        self.assertIsNone(action)
        self.assertIn("Ações de resposta bloqueadas", msg)
        self.assertIn("Shadow Mode", msg)

    async def test_human_review_workflow_and_evidence_immutability(self) -> None:
        """Valida o fluxo completo de Human Review preservando as evidências originais imutáveis."""
        engine = EventCorrelationEngine()

        now = time.time()
        evidence_1 = SecurityEvidence(
            evidence_id="EVID-TEST-001",
            timestamp=now,
            collector="ProcessCollector",
            host="WIN-SENTINEL-DEV",
            asset="powershell.exe",
            observation="Execução de PowerShell com comando em Base64",
            raw_reference="PID: 4920",
            normalized_data={"pid": 4920, "encoded": True},
            sha256="abc123hash",
            confidence=0.88,
            source="system",
        )

        # Injeta evento correlacionado
        diff = BaselineDiff(
            base_id="BASE-01",
            target_id="BASE-02",
            timestamp=now,
            new_processes=[{
                "pid": 4920,
                "name": "powershell.exe",
                "cmdline": "powershell.exe -enc VGVzdA==",
                "is_temp_dir": True,
            }],
        )

        events = engine.correlate_diff(diff=diff, evidences=[evidence_1])
        self.assertGreaterEqual(len(events), 1)
        event = events[0]
        original_severity = event.severity
        original_model_class = event.model_classification

        self.assertIn(original_model_class, (SecurityClassification.HIGH_RISK.value, SecurityClassification.SUSPICIOUS.value))
        self.assertIsNone(event.human_review)

        # Submete Human Review marcando como BENIGN (Falso Positivo)
        review = engine.submit_human_review(
            event_id=event.event_id,
            operator="lead_security_analyst",
            final_classification="BENIGN",
            reason="Script legítimo de manutenção de pacotes do desenvolvedor",
        )

        self.assertIsNotNone(review)
        self.assertEqual(review.operator, "lead_security_analyst")
        self.assertEqual(review.final_classification, "BENIGN")
        self.assertEqual(review.previous_classification, original_severity)
        self.assertTrue(review.is_false_positive)

        # Verifica integridade do evento
        self.assertIsNotNone(event.human_review)
        self.assertEqual(event.human_review["final_classification"], "BENIGN")
        self.assertEqual(event.model_classification, original_model_class)  # Classificação original do modelo inalterada
        self.assertTrue(event.is_known_good)
        self.assertEqual(event.status, "RESOLVED")

        # Evidência original permanece inalterada
        self.assertEqual(evidence_1.observation, "Execução de PowerShell com comando em Base64")
        self.assertEqual(evidence_1.sha256, "abc123hash")
        self.assertEqual(evidence_1.confidence, 0.88)

    async def test_shadow_telemetry_metrics_and_alert_fatigue(self) -> None:
        """Valida o cálculo de métricas em tempo real e o Alert Fatigue Score do Shadow Mode."""
        watchdog = SentinelWatchdogService(scan_interval_seconds=60)
        engine = watchdog.correlation_engine

        now = time.time()
        # Cria eventos com repetição
        for i in range(5):
            engine._record_or_update_event(
                category=EventCategory.PROCESS.value,
                severity=SecurityClassification.SUSPICIOUS.value,
                confidence=0.85,
                fingerprint=f"FP-TEST-{i % 2}",  # 2 fingerprints distintos repetidos 5 vezes -> deduplicação ativa
                evidence_ids=[f"EVID-{i}"],
                rationale=f"Teste de processo repetido {i}",
                recommended_action="Investigar processo",
            )

        # Aplica 1 revisão humana
        first_event = list(engine.active_events.values())[0]
        watchdog.submit_human_review(
            event_id=first_event.event_id,
            operator="operator_1",
            final_classification="BENIGN",
            reason="Processo validado",
        )

        telemetry = watchdog.get_shadow_telemetry()
        self.assertTrue(telemetry["shadow_mode"])
        self.assertEqual(telemetry["total_incidents"], 2)
        self.assertGreaterEqual(telemetry["deduplicated_events"], 3)
        self.assertGreater(telemetry["duplicate_alert_rate"], 0.0)
        self.assertGreaterEqual(telemetry["alert_fatigue_score"], 0.0)
        self.assertLessEqual(telemetry["alert_fatigue_score"], 1.0)
        self.assertEqual(telemetry["human_reviews_count"], 1)
        self.assertEqual(telemetry["false_positive_rate_after_review"], 1.0)

    async def test_collector_degradation_separated_from_security_incident(self) -> None:
        """Garante que a falha de um coletor resulta em estado DEGRADED e não gera incidente de segurança malicioso."""
        watchdog = SentinelWatchdogService(scan_interval_seconds=60)
        
        # Simula falha do coletor de browser
        watchdog._lifecycle_state = SentinelLifecycleState.DEGRADED
        watchdog._degraded_reason = "Falha ao aceder ao perfil de extensões do Chrome: PermissionDenied"
        watchdog._degraded_collectors = ["BrowserCollector"]

        status = watchdog.get_status_dict()
        self.assertEqual(status["lifecycle_state"], "DEGRADED")
        self.assertEqual(status["degraded_collectors"], ["BrowserCollector"])
        self.assertEqual(status["posture"], SecurityPosture.DEGRADED.value)

        # Nenhum evento de segurança falso deve ter sido gerado
        self.assertEqual(len(watchdog.correlation_engine.get_high_risk_events()), 0)
        self.assertEqual(len(watchdog.correlation_engine.get_open_events()), 0)

    async def test_shadow_mode_state_persistence_and_resume(self) -> None:
        """Valida a persistência determinística e recuperação de estado do Shadow Mode."""
        engine_1 = EventCorrelationEngine()
        now = time.time()
        
        # Cria evento e revisão
        engine_1._record_or_update_event(
            category=EventCategory.PERSISTENCE.value,
            severity=SecurityClassification.HIGH_RISK.value,
            confidence=0.92,
            fingerprint="FP-PERSISTENCE-01",
            evidence_ids=["EVID-PERSIST-1"],
            rationale="Chave de registo Run modificada",
            recommended_action="Reverter chave",
        )
        event_id = list(engine_1.active_events.values())[0].event_id
        
        engine_1.submit_human_review(
            event_id=event_id,
            operator="admin_qa",
            final_classification="KNOWN_GOOD",
            reason="Entrada autorizada pelo instalador",
        )

        # Exporta estado para snapshot serializado
        snapshot = {
            "active_events": {k: v.to_dict() for k, v in engine_1.active_events.items()},
            "known_goods": {k: v.to_dict() for k, v in engine_1.known_goods.items()},
        }

        serialized_data = json.dumps(snapshot)

        # Restaura num segundo motor (simulando restart do Sentinel)
        engine_2 = EventCorrelationEngine()
        loaded_data = json.loads(serialized_data)

        for k, kg_dict in loaded_data["known_goods"].items():
            engine_2.known_goods[k] = KnownGoodItem(**kg_dict)

        # Valida que o fingerprint continua conhecido e benigno
        self.assertIn("FP-PERSISTENCE-01", engine_2.known_goods)
        self.assertEqual(engine_2.known_goods["FP-PERSISTENCE-01"].accepted_by, "admin_qa")
        self.assertEqual(engine_2.known_goods["FP-PERSISTENCE-01"].current_state["final_classification"], "KNOWN_GOOD")


if __name__ == "__main__":
    unittest.main()
