"""
Phase 71 — Root Cause Diagnosis Engine
Generates, evaluates, and rejects hypotheses with supporting and contradicting empirical evidence.
"""

from __future__ import annotations

import time
import uuid
from typing import Dict, List, Optional
from .models import Incident, IncidentCategory, RootCauseHypothesis, RootCauseStatus


class RootCauseDiagnostician:
    """
    Synthesizes and evaluates root cause hypotheses for production incidents.
    Never confirms a root cause without verifiable empirical evidence.
    """

    def __init__(self, service_id: str):
        self.service_id = service_id
        self._hypotheses: List[RootCauseHypothesis] = []

    def diagnose_incident(
        self,
        incident: Incident,
        telemetry_evidence: Optional[List[str]] = None,
        logs_evidence: Optional[List[str]] = None,
    ) -> RootCauseHypothesis:
        """
        Formulates a root cause hypothesis based on category and observed evidence.
        """
        all_evidence = list(incident.evidence)
        if telemetry_evidence:
            all_evidence.extend(telemetry_evidence)
        if logs_evidence:
            all_evidence.extend(logs_evidence)

        supporting: List[str] = []
        contradicting: List[str] = []
        hypothesis_text = ""
        confidence = 0.5
        status = RootCauseStatus.UNCERTAIN

        if incident.category == IncidentCategory.PROCESS_CRASH:
            hypothesis_text = "Process died due to unhandled exit or SIGKILL termination."
            for ev in all_evidence:
                if any(kw in ev.lower() for kw in ["exit_code", "sigkill", "oom", "not running", "availability: 0"]):
                    supporting.append(ev)
                elif "process running normally" in ev.lower():
                    contradicting.append(ev)

            if supporting and not contradicting:
                confidence = 0.95
                status = RootCauseStatus.SUPPORTED
            elif contradicting:
                confidence = 0.2
                status = RootCauseStatus.REJECTED

        elif incident.category == IncidentCategory.DATABASE_FAILURE:
            hypothesis_text = "Database connection pool exhaustion or network partition."
            for ev in all_evidence:
                if any(kw in ev.lower() for kw in ["db", "database", "connection refused", "timeout", "pool"]):
                    supporting.append(ev)
                elif "database connection active" in ev.lower():
                    contradicting.append(ev)

            if supporting and not contradicting:
                confidence = 0.92
                status = RootCauseStatus.SUPPORTED
            elif contradicting:
                confidence = 0.15
                status = RootCauseStatus.REJECTED

        elif incident.category in {IncidentCategory.LATENCY_SLO_BREACH, IncidentCategory.HTTP_TIMEOUT}:
            hypothesis_text = "Upstream processing bottleneck or CPU resource saturation."
            for ev in all_evidence:
                if any(kw in ev.lower() for kw in ["latency", "timeout", "cpu", "p95"]):
                    supporting.append(ev)
                elif "low latency" in ev.lower():
                    contradicting.append(ev)

            if len(supporting) >= 2 and not contradicting:
                confidence = 0.88
                status = RootCauseStatus.SUPPORTED
            elif contradicting:
                confidence = 0.25
                status = RootCauseStatus.REJECTED

        elif incident.category == IncidentCategory.RESTART_LOOP:
            hypothesis_text = "Fatal initialization failure in startup sequence causing crash loop."
            for ev in all_evidence:
                if any(kw in ev.lower() for kw in ["restart count", "crash loop", "startup"]):
                    supporting.append(ev)
            if supporting:
                confidence = 0.94
                status = RootCauseStatus.SUPPORTED

        else:
            hypothesis_text = f"General runtime anomaly in {incident.service}: {incident.category.value}."
            supporting.extend(all_evidence)
            status = RootCauseStatus.UNCERTAIN
            confidence = 0.6

        # Invariant: If supporting evidence is empty, status must remain UNCERTAIN or REJECTED
        if not supporting and status == RootCauseStatus.SUPPORTED:
            status = RootCauseStatus.UNCERTAIN
            confidence = 0.4

        hypo = RootCauseHypothesis(
            hypothesis_id=f"hypo-{uuid.uuid4().hex[:8]}",
            incident_id=incident.incident_id,
            hypothesis=hypothesis_text,
            supporting_evidence=supporting,
            contradicting_evidence=contradicting,
            confidence=round(confidence, 3),
            status=status,
            created_at=time.time(),
        )
        self._hypotheses.append(hypo)
        return hypo

    def get_hypotheses(self) -> List[RootCauseHypothesis]:
        return list(self._hypotheses)
