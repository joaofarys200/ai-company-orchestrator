"""
Observability Readiness Module
Phase 70 — Autonomous Release Readiness & Production Governance

Evaluates logging structure, error tracing, health telemetry, and mission observability.
"""

from __future__ import annotations
from typing import Dict, Any, List
from .models import ObservabilityStatus, BlockerCategory, ReleaseBlocker


class ObservabilityReadiness:
    """Evaluates telemetry signals, distributed tracing, and diagnostic visibility."""

    @classmethod
    def evaluate(
        cls,
        observability_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Verifies:
        - structured logs
        - error visibility
        - health signals
        - request tracing
        - mission telemetry
        - security events
        - verification evidence
        Classifies: READY, PARTIAL, MISSING, UNKNOWN
        """
        if not observability_data:
            return {
                "status": ObservabilityStatus.UNKNOWN,
                "blockers": [],
                "requires_human_review": True,
                "review_reasons": ["Observability configuration and telemetry data completely absent"]
            }

        structured_logs = observability_data.get("structured_logs", False)
        error_visibility = observability_data.get("error_visibility", False)
        health_signals = observability_data.get("health_signals", False)
        request_tracing = observability_data.get("request_tracing", False)
        mission_telemetry = observability_data.get("mission_telemetry", False)
        security_events = observability_data.get("security_events", False)
        verification_evidence = observability_data.get("verification_evidence", False)

        blockers: List[ReleaseBlocker] = []
        requires_human_review = False
        review_reasons: List[str] = []

        total_signals = sum([
            structured_logs, error_visibility, health_signals,
            request_tracing, mission_telemetry, security_events,
            verification_evidence
        ])

        if not error_visibility and not health_signals:
            blockers.append(ReleaseBlocker(
                blocker_id="blocker-obs-blind-runtime",
                category=BlockerCategory.MISSING_MANDATORY_EVIDENCE,
                description="Crucial error visibility and health signaling are missing; system is blind",
                evidence="Neither error visibility nor health signals are enabled in observability configuration."
            ))

        if total_signals >= 5 and structured_logs and error_visibility:
            status = ObservabilityStatus.READY
        elif total_signals >= 2:
            status = ObservabilityStatus.PARTIAL
            requires_human_review = True
            review_reasons.append(
                f"Observability is partial ({total_signals}/7 signals present); risk elevated"
            )
        else:
            status = ObservabilityStatus.MISSING
            requires_human_review = True
            review_reasons.append("Observability is critically deficient; missing diagnostics for production operation")

        return {
            "status": status,
            "signals_present": total_signals,
            "structured_logs": structured_logs,
            "error_visibility": error_visibility,
            "health_signals": health_signals,
            "request_tracing": request_tracing,
            "mission_telemetry": mission_telemetry,
            "security_events": security_events,
            "verification_evidence": verification_evidence,
            "blockers": blockers,
            "requires_human_review": requires_human_review,
            "review_reasons": review_reasons
        }
