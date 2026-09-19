"""
Runtime Health Analyzer Module
Phase 70 — Autonomous Release Readiness & Production Governance

Performs holistic synthesis of runtime operational signals.
Crucial invariant: Never declares runtime healthy simply because the process started.
"""

from __future__ import annotations
from typing import Dict, Any, List
from .models import RuntimeHealthStatus, ReleaseBlocker
from .runtime import RuntimeHealthValidator


class RuntimeHealthAnalyzer:
    """Holistic runtime health engine synthesizing multi-probe operational evidence."""

    @classmethod
    def analyze(
        cls,
        runtime_evidence: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Analyzes runtime operational health.
        Principle: Never declare runtime healthy just because the process started.
        """
        if not runtime_evidence:
            return {
                "status": RuntimeHealthStatus.INSUFFICIENT_EVIDENCE,
                "blockers": [],
                "requires_human_review": True,
                "review_reasons": ["No operational runtime evidence provided for candidate"]
            }

        validation = RuntimeHealthValidator.validate_components(runtime_evidence)
        blockers: List[ReleaseBlocker] = validation["blockers"]
        requires_human_review = validation["requires_human_review"]
        review_reasons = validation["review_reasons"]

        # Anti-pattern defense: only process_started was true, but no probe evidence
        probes_present = any(
            k in runtime_evidence for k in [
                "healthcheck_ok", "readiness_ok", "liveness_ok",
                "database_ok", "websocket_ok"
            ]
        )
        if runtime_evidence.get("process_started") and not probes_present:
            requires_human_review = True
            review_reasons.append(
                "Process started but no probe verification evidence exists; cannot declare healthy"
            )
            return {
                "status": RuntimeHealthStatus.INSUFFICIENT_EVIDENCE,
                "blockers": blockers,
                "requires_human_review": requires_human_review,
                "review_reasons": review_reasons,
                "details": validation
            }

        status = RuntimeHealthStatus.HEALTHY
        if blockers:
            status = RuntimeHealthStatus.UNAVAILABLE
        elif requires_human_review:
            status = RuntimeHealthStatus.DEGRADED

        return {
            "status": status,
            "blockers": blockers,
            "requires_human_review": requires_human_review,
            "review_reasons": review_reasons,
            "details": validation
        }
