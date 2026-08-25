"""
JARVIS OS — Sentinel Watchdog Service (Fase S2)
Serviço de monitorização contínua passiva em background, 100% read-only, com lock de concorrência.
"""

from __future__ import annotations

import asyncio
import os
import time
from typing import Any, Callable, Coroutine, Dict, List, Optional
import psutil

from security.sentinel.baseline import BaselineEngine
from security.sentinel.collectors.browser import BrowserCollector
from security.sentinel.collectors.hosts import HostsCollector
from security.sentinel.collectors.network import NetworkCollector
from security.sentinel.collectors.persistence import PersistenceCollector
from security.sentinel.collectors.processes import ProcessCollector
from security.sentinel.collectors.security_events import WindowsSecurityEventsCollector
from security.sentinel.contracts import (
    BaselineDiff,
    HumanIncidentReview,
    KnownGoodItem,
    SecurityClassification,
    SecurityPosture,
    SecurityEvent,
    SentinelLifecycleState,
    SentinelShadowModeState,
    SystemBaseline,
)
from security.sentinel.correlation import EventCorrelationEngine
from security.sentinel.response.engine import ResponseEngine


class SentinelWatchdogService:
    """Serviço em background de monitorização contínua de segurança do Windows."""

    def __init__(
        self,
        scan_interval_seconds: int = 60,
        event_callback: Optional[Callable[[SecurityEvent], Coroutine[Any, Any, None]]] = None,
        status_callback: Optional[Callable[[Dict[str, Any]], Coroutine[Any, Any, None]]] = None,
        baseline_engine: Optional[BaselineEngine] = None,
        response_engine: Optional[ResponseEngine] = None,
    ) -> None:
        self.scan_interval_seconds = scan_interval_seconds
        self.event_callback = event_callback
        self.status_callback = status_callback
        self.baseline_engine = baseline_engine or BaselineEngine()
        self.correlation_engine = EventCorrelationEngine()
        self.response_engine = response_engine or ResponseEngine()

        self._active_baseline: Optional[SystemBaseline] = None
        self._last_diff: Optional[BaselineDiff] = None
        self._is_running = False
        self._is_paused = False
        self._task: Optional[asyncio.Task[None]] = None
        self._lock = asyncio.Lock()

        # Máquina de estados de arranque e modo degradado
        self._lifecycle_state = SentinelLifecycleState.STOPPED
        self._is_baseline_ready = False
        self._baseline_started_at = 0.0
        self._baseline_completed_at = 0.0
        self._degraded_reason: Optional[str] = None
        self._degraded_collectors: List[str] = []

        # Shadow Mode (Fase S6) — Padrão: 100% Read-Only
        self.shadow_mode = True
        self.shadow_mode_state = SentinelShadowModeState.COLLECTING
        self.shadow_start_time = time.time()

        # Métricas operacionais
        self._total_scans = 0
        self._last_scan_time = 0.0
        self._last_scan_duration_seconds = 0.0
        self._is_auditing_now = False

    @property
    def is_running(self) -> bool:
        return self._is_running

    @property
    def is_paused(self) -> bool:
        return self._is_paused

    @property
    def lifecycle_state(self) -> SentinelLifecycleState:
        return self._lifecycle_state

    @property
    def is_baseline_ready(self) -> bool:
        return self._is_baseline_ready

    @property
    def degraded_reason(self) -> Optional[str]:
        return self._degraded_reason

    @property
    def degraded_collectors(self) -> List[str]:
        return list(self._degraded_collectors)

    @property
    def total_scans(self) -> int:
        return self._total_scans

    @property
    def active_baseline(self) -> Optional[SystemBaseline]:
        return self._active_baseline

    def get_posture(self) -> SecurityPosture:
        """Determina a postura geral defensiva do endpoint."""
        open_events = self.correlation_engine.get_open_events()
        high_risk = self.correlation_engine.get_high_risk_events()

        if any(ev.severity == SecurityClassification.HIGH_RISK.value for ev in high_risk):
            return SecurityPosture.HIGH_RISK
        if self._lifecycle_state == SentinelLifecycleState.DEGRADED:
            return SecurityPosture.DEGRADED
        if self._lifecycle_state in (SentinelLifecycleState.STARTING, SentinelLifecycleState.BASELINE_RUNNING):
            return SecurityPosture.MONITORING
        if len(open_events) > 0:
            return SecurityPosture.ATTENTION
        if self._is_running:
            return SecurityPosture.MONITORING
        return SecurityPosture.GOOD

    def get_status_dict(self) -> Dict[str, Any]:
        """Gera payload estruturado de telemetria do Sentinel com estado de ciclo de vida e shadow mode."""
        process = psutil.Process(os.getpid())
        mem_info = process.memory_info()

        baseline_dur = (
            round(self._baseline_completed_at - self._baseline_started_at, 2)
            if self._baseline_completed_at > 0
            else 0.0
        )

        return {
            "schema_version": 1,
            "status": "PAUSED" if self._is_paused else ("RUNNING" if self._is_running else "STOPPED"),
            "lifecycle_state": self._lifecycle_state.value,
            "shadow_mode": self.shadow_mode,
            "shadow_state": self.shadow_mode_state.value,
            "is_baseline_ready": self._is_baseline_ready,
            "degraded_reason": self._degraded_reason,
            "degraded_collectors": self._degraded_collectors,
            "baseline_duration_seconds": baseline_dur,
            "posture": self.get_posture().value,
            "is_auditing_now": self._is_auditing_now,
            "scan_interval_seconds": self.scan_interval_seconds,
            "total_scans": self._total_scans,
            "last_scan_time": self._last_scan_time,
            "last_scan_duration_seconds": round(self._last_scan_duration_seconds, 2),
            "next_scan_in_seconds": max(0, int(self._last_scan_time + self.scan_interval_seconds - time.time())) if self._is_running and not self._is_paused else 0,
            "active_baseline_id": self._active_baseline.baseline_id if self._active_baseline else None,
            "open_events_count": len(self.correlation_engine.get_open_events()),
            "high_risk_events_count": len(self.correlation_engine.get_high_risk_events()),
            "actions_count": len(self.response_engine.get_actions()),
            "pending_actions_count": len([a for a in self.response_engine.get_actions() if a.status in ("PROPOSED", "WAITING_APPROVAL")]),
            "cpu_percent": psutil.cpu_percent(interval=None),
            "memory_mb": round(mem_info.rss / (1024 * 1024), 2),
        }

    def get_shadow_telemetry(self) -> Dict[str, Any]:
        """Calcula e devolve métricas e estatísticas do Shadow Mode em tempo real."""
        events = list(self.correlation_engine.event_history)
        open_events = self.correlation_engine.get_open_events()
        high_risk_events = self.correlation_engine.get_high_risk_events()

        elapsed_hours = max((time.time() - self.shadow_start_time) / 3600.0, 0.001)

        # Contagens por severidade
        sev_counts: Dict[str, int] = {
            "BENIGN": 0, "SUSPICIOUS": 0, "HIGH_RISK": 0, "CONFIRMED_MALICIOUS": 0, "UNKNOWN": 0
        }
        for ev in events:
            sev_counts[ev.severity] = sev_counts.get(ev.severity, 0) + 1

        unknown_count = sev_counts.get("UNKNOWN", 0)
        unknown_rate = (unknown_count / len(events)) if len(events) > 0 else 0.0

        # Deduplicação
        dedup_count = sum(max(0, ev.occurrence_count - 1) for ev in events)
        duplicate_alert_rate = (dedup_count / (len(events) + dedup_count)) if (len(events) + dedup_count) > 0 else 0.0

        # Revisões Humanas
        reviewed_events = [ev for ev in events if ev.human_review is not None]
        false_positive_reviews = [
            ev for ev in reviewed_events
            if ev.human_review and ev.human_review.get("is_false_positive") is True
        ]
        fp_rate = (len(false_positive_reviews) / len(reviewed_events)) if len(reviewed_events) > 0 else 0.0

        # Taxas horárias
        alerts_per_hour = round(len(events) / elapsed_hours, 2)
        alerts_per_day = round(alerts_per_hour * 24.0, 2)
        high_risk_per_day = round((len(high_risk_events) / elapsed_hours) * 24.0, 2)

        # Alert Fatigue Score (0.0 = sem fadiga, 1.0 = saturação crítica de alertas)
        # Composto por proporção de duplicados e densidade horária
        alert_fatigue_score = round(min(1.0, (duplicate_alert_rate * 0.4) + (min(alerts_per_hour, 20.0) / 20.0 * 0.6)), 3)

        process = psutil.Process(os.getpid())
        mem_info = process.memory_info()

        return {
            "schema_version": 1,
            "shadow_mode": self.shadow_mode,
            "shadow_state": self.shadow_mode_state.value,
            "elapsed_seconds": round(time.time() - self.shadow_start_time, 1),
            "total_observations": self._total_scans * 6,
            "total_changes": len(events),
            "total_security_events": len(events),
            "total_incidents": len(self.correlation_engine.active_events),
            "severity_distribution": sev_counts,
            "unknown_rate": round(unknown_rate, 4),
            "correlation_count": len(events),
            "deduplicated_events": dedup_count,
            "duplicate_alert_rate": round(duplicate_alert_rate, 4),
            "collector_failures": len(self._degraded_collectors),
            "collector_failure_rate": (len(self._degraded_collectors) / 6.0),
            "scan_duration_seconds": round(self._last_scan_duration_seconds, 3),
            "alerts_per_hour": alerts_per_hour,
            "alerts_per_day": alerts_per_day,
            "high_risk_per_day": high_risk_per_day,
            "human_reviews_count": len(reviewed_events),
            "false_positive_rate_after_review": round(fp_rate, 4),
            "alert_fatigue_score": alert_fatigue_score,
            "cpu_percent": psutil.cpu_percent(interval=None),
            "memory_mb": round(mem_info.rss / (1024 * 1024), 2),
        }

    def submit_human_review(
        self,
        event_id: str,
        operator: str,
        final_classification: str,
        reason: str,
    ) -> Optional[Dict[str, Any]]:
        """Aplica revisão humana a um incidente em Shadow Mode."""
        review = self.correlation_engine.submit_human_review(
            event_id=event_id,
            operator=operator,
            final_classification=final_classification,
            reason=reason,
        )
        return review.to_dict() if review else None

    def get_actions(self) -> List[Dict[str, Any]]:
        """Retorna lista serializada de todas as ações de resposta."""
        return [a.to_dict() for a in self.response_engine.get_actions()]

    async def approve_and_execute_action(
        self,
        action_id: str,
        user: str,
        session_id: str,
        incident_id: Optional[str] = None,
        timestamp: Optional[float] = None,
    ) -> Tuple[bool, Optional[Dict[str, Any]], str]:
        """Aprova e executa ação de resposta (Bloqueada em Shadow Mode)."""
        if self.shadow_mode:
            return False, None, "Ações de resposta bloqueadas: Sentinel a operar em Shadow Mode (100% Read-Only)"

        success, action, msg = await self.response_engine.approve_and_execute(
            action_id=action_id,
            user=user,
            session_id=session_id,
            incident_id=incident_id,
            timestamp=timestamp,
        )
        return success, action.to_dict() if action else None, msg

    async def rollback_action(
        self,
        action_id: str,
        user: str,
        session_id: str,
    ) -> Tuple[bool, Optional[Dict[str, Any]], str]:
        """Reverte ação através do ResponseEngine."""
        success, action, msg = await self.response_engine.rollback(
            action_id=action_id,
            user=user,
            session_id=session_id,
        )
        return success, action.to_dict() if action else None, msg

    def reject_action(
        self,
        action_id: str,
        user: str,
        reason: str,
    ) -> Tuple[bool, Optional[Dict[str, Any]], str]:
        """Rejeita proposta de ação através do ResponseEngine."""
        success, action, msg = self.response_engine.reject(
            action_id=action_id,
            user=user,
            reason=reason,
        )
        return success, action.to_dict() if action else None, msg

    async def start(self) -> None:
        """Inicia o watchdog em background de forma não bloqueante."""
        async with self._lock:
            if self._is_running:
                return

            self._is_running = True
            self._is_paused = False
            self._lifecycle_state = (
                SentinelLifecycleState.READY
                if self._is_baseline_ready
                else SentinelLifecycleState.STARTING
            )

            # Cria a tarefa em background para não atrasar a inicialização do servidor
            self._task = asyncio.create_task(self._watchdog_loop())

        if self.status_callback:
            try:
                await self.status_callback(self.get_status_dict())
            except Exception:
                pass

    async def stop(self) -> None:
        """Termina o watchdog de forma limpa sem deixar tasks órfãs."""
        async with self._lock:
            if not self._is_running:
                self._lifecycle_state = SentinelLifecycleState.STOPPED
                return

            self._is_running = False
            self._is_paused = False
            self._lifecycle_state = SentinelLifecycleState.STOPPED

            if self._task and not self._task.done():
                self._task.cancel()
                try:
                    await self._task
                except asyncio.CancelledError:
                    pass
                self._task = None

        if self.status_callback:
            try:
                await self.status_callback(self.get_status_dict())
            except Exception:
                pass

    def pause(self) -> None:
        """Pausa temporariamente os scans periódicos."""
        self._is_paused = True
        self._lifecycle_state = SentinelLifecycleState.PAUSED

    def resume(self) -> None:
        """Retoma os scans periódicos."""
        self._is_paused = False
        self._lifecycle_state = (
            SentinelLifecycleState.READY
            if self._is_baseline_ready
            else SentinelLifecycleState.STARTING
        )

    async def run_manual_audit(self) -> Dict[str, Any]:
        """Executa um ciclo completo de auditoria imediata em worker thread com lock de concorrência."""
        async with self._lock:
            self._is_auditing_now = True
            try:
                t0 = time.time()
                new_baseline = await asyncio.to_thread(self.baseline_engine.capture_baseline, set_as_active=False)

                if self._active_baseline:
                    diff = await asyncio.to_thread(self.baseline_engine.compare, self._active_baseline, new_baseline)
                    self._last_diff = diff
                    new_events = self.correlation_engine.correlate_diff(diff, new_baseline)

                    # Notifica novos eventos detetados
                    for ev in new_events:
                        if self.event_callback:
                            try:
                                await self.event_callback(ev)
                            except Exception:
                                pass
                else:
                    self._active_baseline = new_baseline
                    self._is_baseline_ready = True
                    self._lifecycle_state = SentinelLifecycleState.READY

                self._total_scans += 1
                self._last_scan_time = time.time()
                self._last_scan_duration_seconds = time.time() - t0

                return {
                    "baseline_id": new_baseline.baseline_id,
                    "integrity_hash": new_baseline.integrity_hash,
                    "duration_seconds": round(self._last_scan_duration_seconds, 2),
                    "processes_count": len(new_baseline.processes),
                    "network_sockets_count": len(new_baseline.network),
                    "persistence_count": len(new_baseline.persistence),
                    "open_events": [ev.to_dict() for ev in self.correlation_engine.get_open_events()],
                }
            finally:
                self._is_auditing_now = False

    async def _watchdog_loop(self) -> None:
        """Loop contínuo assíncrono de observação."""
        # 1. Captura o baseline inicial em background se ainda não existir
        if not self._active_baseline:
            self._lifecycle_state = SentinelLifecycleState.BASELINE_RUNNING
            self._baseline_started_at = time.time()
            if self.status_callback:
                try:
                    await self.status_callback(self.get_status_dict())
                except Exception:
                    pass

            try:
                self._active_baseline = await asyncio.to_thread(
                    self.baseline_engine.capture_baseline, set_as_active=True
                )
                self._baseline_completed_at = time.time()
                self._is_baseline_ready = True

                # Verificar se algum coletor reportou erro
                metrics = self._active_baseline.collector_metrics or {}
                degraded = [
                    col for col, m in metrics.items()
                    if str(m.get("status", "")).startswith("ERROR")
                ]
                if degraded:
                    self._degraded_collectors = degraded
                    self._degraded_reason = f"Falha parcial nos coletores: {', '.join(degraded)}"
                    self._lifecycle_state = SentinelLifecycleState.DEGRADED
                else:
                    self._degraded_collectors = []
                    self._degraded_reason = None
                    self._lifecycle_state = SentinelLifecycleState.READY

                if self.status_callback:
                    try:
                        await self.status_callback(self.get_status_dict())
                    except Exception:
                        pass
            except Exception as exc:
                self._lifecycle_state = SentinelLifecycleState.FAILED
                self._degraded_reason = f"Falha crítica na captura de baseline: {str(exc)}"
                if self.status_callback:
                    try:
                        await self.status_callback(self.get_status_dict())
                    except Exception:
                        pass

        while self._is_running:
            try:
                await asyncio.sleep(self.scan_interval_seconds)
                if not self._is_running:
                    break

                if self._is_paused or self._is_auditing_now:
                    continue

                # Executa ciclo periódico não-destrutivo
                await self.run_manual_audit()

                if self.status_callback:
                    try:
                        await self.status_callback(self.get_status_dict())
                    except Exception:
                        pass

            except asyncio.CancelledError:
                break
            except Exception as e:
                # Falha resiliente sem deitar abaixo o loop
                await asyncio.sleep(5.0)

    def accept_known_good(self, item_key: str, reason: str, user: str = "local_user") -> None:
        """Regista um item como Known Good aprovado pelo utilizador."""
        kg = KnownGoodItem(
            item_key=item_key,
            category="USER_APPROVAL",
            accepted_by=user,
            accepted_at=time.time(),
            reason=reason,
            previous_state={},
            current_state={},
        )
        self.correlation_engine.register_known_good(kg)
        if self._active_baseline:
            self._active_baseline.known_goods.append(kg.to_dict())


