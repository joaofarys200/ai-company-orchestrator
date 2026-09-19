"""
Runtime Health Checks and Verification Module
Phase 70 — Autonomous Release Readiness & Production Governance

Verifies concrete process startup, probe endpoints, socket readiness,
and service dependencies under operational conditions.
"""

from __future__ import annotations
from typing import Dict, Any, List
from .models import RuntimeHealthStatus, BlockerCategory, ReleaseBlocker


class RuntimeHealthValidator:
    """Validates operational components across process, endpoints, and connections."""

    @classmethod
    def validate_components(
        cls,
        runtime_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Evaluates operational health:
        - process startup
        - healthcheck
        - readiness endpoint
        - liveness endpoint
        - WebSocket connectivity
        - dependency connectivity
        - database connectivity
        - worker readiness
        - graceful shutdown
        - error rate
        """
        process_started = runtime_data.get("process_started", True)
        healthcheck_ok = runtime_data.get("healthcheck_ok", True)
        readiness_ok = runtime_data.get("readiness_ok", True)
        liveness_ok = runtime_data.get("liveness_ok", True)
        websocket_ok = runtime_data.get("websocket_ok", True)
        dependency_connectivity = runtime_data.get("dependency_connectivity", True)
        database_ok = runtime_data.get("database_ok", True)
        worker_ready = runtime_data.get("worker_ready", True)
        graceful_shutdown_tested = runtime_data.get("graceful_shutdown_tested", True)
        error_rate = float(runtime_data.get("error_rate", 0.0))

        blockers: List[ReleaseBlocker] = []
        requires_human_review = False
        review_reasons: List[str] = []

        if not process_started:
            blockers.append(ReleaseBlocker(
                blocker_id="blocker-runtime-process-failed",
                category=BlockerCategory.CRITICAL_HEALTH_FAILURE,
                description="Process failed to start or exited prematurely during readiness probing",
                evidence="Process exit code non-zero or startup timeout."
            ))

        if not healthcheck_ok or not readiness_ok:
            blockers.append(ReleaseBlocker(
                blocker_id="blocker-runtime-probe-failed",
                category=BlockerCategory.CRITICAL_HEALTH_FAILURE,
                description="Healthcheck or readiness probe endpoint failed",
                evidence=f"Healthcheck: {healthcheck_ok}, Readiness: {readiness_ok}."
            ))

        if not liveness_ok:
            blockers.append(ReleaseBlocker(
                blocker_id="blocker-runtime-liveness-failed",
                category=BlockerCategory.CRITICAL_HEALTH_FAILURE,
                description="Liveness probe returned unhealthy",
                evidence="Process liveness check failed."
            ))

        if not websocket_ok:
            requires_human_review = True
            review_reasons.append("WebSocket connectivity failed handshake during healthcheck")

        if not database_ok or not dependency_connectivity:
            blockers.append(ReleaseBlocker(
                blocker_id="blocker-runtime-dep-unreachable",
                category=BlockerCategory.CRITICAL_HEALTH_FAILURE,
                description="Database or essential external dependency unreachable from runtime",
                evidence=f"Database: {database_ok}, External deps: {dependency_connectivity}."
            ))

        if not worker_ready:
            requires_human_review = True
            review_reasons.append("Background worker pool not fully ready")

        if not graceful_shutdown_tested:
            requires_human_review = True
            review_reasons.append("Graceful shutdown handler was not verified under test")

        if error_rate > 0.05:  # Error rate > 5%
            blockers.append(ReleaseBlocker(
                blocker_id="blocker-runtime-high-error-rate",
                category=BlockerCategory.CRITICAL_HEALTH_FAILURE,
                description=f"Runtime error rate elevated at {error_rate*100:.1f}%",
                evidence="Observed probe failure rate exceeds 5% threshold."
            ))
        elif error_rate > 0.01:
            requires_human_review = True
            review_reasons.append(f"Runtime error rate is {error_rate*100:.1f}%")

        return {
            "process_started": process_started,
            "healthcheck_ok": healthcheck_ok,
            "readiness_ok": readiness_ok,
            "liveness_ok": liveness_ok,
            "websocket_ok": websocket_ok,
            "dependency_connectivity": dependency_connectivity,
            "database_ok": database_ok,
            "worker_ready": worker_ready,
            "graceful_shutdown_tested": graceful_shutdown_tested,
            "error_rate": error_rate,
            "blockers": blockers,
            "requires_human_review": requires_human_review,
            "review_reasons": review_reasons
        }
