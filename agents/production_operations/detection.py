"""
Phase 71 — Deterministic Incident Detection
Detects incidents based on runtime observations, healthcheck failures, and SLO breaches.
"""

from __future__ import annotations

import time
import uuid
from typing import Dict, List, Optional
from .models import (
    HealthCheckResult,
    HealthStatus,
    Incident,
    IncidentCategory,
    RuntimeObservation,
    SLOEvaluation,
    SLOStatus,
)
from .severity import SeverityClassifier


class IncidentDetector:
    """
    Deterministic detector scanning runtime metrics, health checks, and SLOs to generate Incident entities.
    """

    def __init__(self, service_id: str):
        self.service_id = service_id
        self._detected_incidents: List[Incident] = []

    def detect_from_observation(self, obs: RuntimeObservation) -> List[Incident]:
        """Scans a single RuntimeObservation for operational failures."""
        incidents: List[Incident] = []
        metrics = {
            "error_rate": obs.error_rate,
            "availability": obs.availability,
            "restart_count": obs.restart_count,
        }

        # 1. Process crash / down
        if obs.availability <= 0.0 or obs.health_status == HealthStatus.UNHEALTHY and obs.cpu == 0.0 and obs.memory == 0.0:
            category = IncidentCategory.PROCESS_CRASH
            evidence = [
                f"Observed availability: {obs.availability}",
                f"Observed health status: {obs.health_status.value}",
                f"Evidence ID: {obs.evidence_id}",
            ]
            sev, rule, desc = SeverityClassifier.classify(category, evidence, metrics)
            inc = Incident(
                incident_id=f"inc-proc-{uuid.uuid4().hex[:8]}",
                service=obs.service_id,
                category=category,
                severity=sev,
                confidence=0.98,
                correlation_key=f"corr:{obs.service_id}:{category.value}",
                evidence=evidence,
                rule_triggered=rule,
                description=desc,
                detection_time=time.time(),
            )
            incidents.append(inc)

        # 2. Restart loop
        if obs.restart_count >= 3:
            category = IncidentCategory.RESTART_LOOP
            evidence = [
                f"Restart count observed: {obs.restart_count} in window",
                f"Process ID: {obs.process_id}",
                f"Evidence ID: {obs.evidence_id}",
            ]
            sev, rule, desc = SeverityClassifier.classify(category, evidence, metrics)
            inc = Incident(
                incident_id=f"inc-restart-{uuid.uuid4().hex[:8]}",
                service=obs.service_id,
                category=category,
                severity=sev,
                confidence=0.95,
                correlation_key=f"corr:{obs.service_id}:{category.value}",
                evidence=evidence,
                rule_triggered=rule,
                description=desc,
                detection_time=time.time(),
            )
            incidents.append(inc)

        # 3. High Error Rate
        if obs.error_rate >= 0.05:
            category = IncidentCategory.ERROR_RATE_SLO_BREACH if obs.error_rate < 0.5 else IncidentCategory.HTTP_5XX
            evidence = [
                f"Error rate observed: {obs.error_rate * 100:.2f}%",
                f"Evidence ID: {obs.evidence_id}",
            ]
            sev, rule, desc = SeverityClassifier.classify(category, evidence, metrics)
            inc = Incident(
                incident_id=f"inc-err-{uuid.uuid4().hex[:8]}",
                service=obs.service_id,
                category=category,
                severity=sev,
                confidence=0.92,
                correlation_key=f"corr:{obs.service_id}:{category.value}",
                evidence=evidence,
                rule_triggered=rule,
                description=desc,
                detection_time=time.time(),
            )
            incidents.append(inc)

        # 4. Dependency failure
        failed_deps = [d for d, status in obs.dependency_status.items() if status.lower() in {"down", "unhealthy", "failed", "unreachable"}]
        if failed_deps:
            is_db = any("db" in d.lower() or "database" in d.lower() or "postgres" in d.lower() for d in failed_deps)
            category = IncidentCategory.DATABASE_FAILURE if is_db else IncidentCategory.DEPENDENCY_FAILURE
            evidence = [
                f"Failed dependencies observed: {', '.join(failed_deps)}",
                f"Evidence ID: {obs.evidence_id}",
            ]
            sev, rule, desc = SeverityClassifier.classify(category, evidence, metrics)
            inc = Incident(
                incident_id=f"inc-dep-{uuid.uuid4().hex[:8]}",
                service=obs.service_id,
                category=category,
                severity=sev,
                confidence=0.94,
                correlation_key=f"corr:{obs.service_id}:{failed_deps[0]}",
                evidence=evidence,
                rule_triggered=rule,
                description=desc,
                detection_time=time.time(),
            )
            incidents.append(inc)

        self._detected_incidents.extend(incidents)
        return incidents

    def detect_from_healthchecks(self, results: List[HealthCheckResult]) -> List[Incident]:
        """Generates incidents for failed health checks."""
        incidents: List[Incident] = []
        for res in results:
            if res.status == HealthStatus.UNHEALTHY:
                # Map check to specific category
                if "db" in res.check_name or "database" in res.check_name:
                    cat = IncidentCategory.DATABASE_FAILURE
                elif "ws" in res.check_name or "websocket" in res.check_name:
                    cat = IncidentCategory.WEBSOCKET_FAILURE
                elif "http" in res.check_name:
                    cat = IncidentCategory.HTTP_5XX
                elif "process" in res.check_name:
                    cat = IncidentCategory.PROCESS_CRASH
                elif "dep" in res.check_name:
                    cat = IncidentCategory.DEPENDENCY_FAILURE
                else:
                    cat = IncidentCategory.HEALTHCHECK_FAILURE

                evidence = [
                    f"Check: {res.check_name}",
                    f"Details: {res.details}",
                    f"Evidence ID: {res.evidence_id}",
                ]
                sev, rule, desc = SeverityClassifier.classify(cat, evidence)
                inc = Incident(
                    incident_id=f"inc-hc-{uuid.uuid4().hex[:8]}",
                    service=res.service_id,
                    category=cat,
                    severity=sev,
                    confidence=0.95,
                    correlation_key=f"corr:{res.service_id}:{res.check_name}",
                    evidence=evidence,
                    rule_triggered=rule,
                    description=desc,
                    detection_time=time.time(),
                )
                incidents.append(inc)

        self._detected_incidents.extend(incidents)
        return incidents

    def detect_from_slo(self, evaluations: List[SLOEvaluation]) -> List[Incident]:
        """Generates incidents for breached SLOs."""
        incidents: List[Incident] = []
        for eval_res in evaluations:
            if eval_res.status == SLOStatus.BREACH:
                if "latency" in eval_res.metric.lower():
                    cat = IncidentCategory.LATENCY_SLO_BREACH
                elif "error" in eval_res.metric.lower():
                    cat = IncidentCategory.ERROR_RATE_SLO_BREACH
                else:
                    cat = IncidentCategory.HEALTHCHECK_FAILURE

                evidence = [
                    f"Metric: {eval_res.metric}",
                    f"Observed: {eval_res.observed_value} vs Threshold: {eval_res.threshold}",
                    f"Window: {eval_res.window_seconds}s",
                    f"Evidence ID: {eval_res.evidence_id}",
                ]
                sev, rule, desc = SeverityClassifier.classify(cat, evidence)
                inc = Incident(
                    incident_id=f"inc-slo-{uuid.uuid4().hex[:8]}",
                    service=eval_res.service_id,
                    category=cat,
                    severity=sev,
                    confidence=0.90,
                    correlation_key=f"corr:{eval_res.service_id}:{eval_res.metric}",
                    evidence=evidence,
                    rule_triggered=rule,
                    description=desc,
                    detection_time=time.time(),
                )
                incidents.append(inc)

        self._detected_incidents.extend(incidents)
        return incidents

    def get_detected_incidents(self) -> List[Incident]:
        return list(self._detected_incidents)
