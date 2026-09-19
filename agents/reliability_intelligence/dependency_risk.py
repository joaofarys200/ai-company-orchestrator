"""
Phase 72 — Dependency Risk Analysis
Integrates architectural topology (F44, F49, F50, F59, F60) and runtime telemetry.
Never assumes causality solely from graph proximity.
"""

from __future__ import annotations

import time
import uuid
from typing import Any, Dict, List, Optional

from .models import (
    DependencyRiskSignal,
    RiskLevel,
)


class DependencyRiskEvaluator:
    """Evaluates systemic risk of upstream and downstream dependencies."""

    def __init__(
        self,
        high_centrality_threshold: float = 0.7,
        broad_dependency_threshold: int = 8,
    ):
        self.high_centrality = high_centrality_threshold
        self.broad_threshold = broad_dependency_threshold

    def evaluate(
        self,
        service: str,
        dependency: str,
        graph_metadata: Optional[Dict[str, Any]] = None,
        runtime_latency_ms: Optional[float] = None,
        historical_incidents: int = 0,
    ) -> DependencyRiskSignal:
        evidence_id = f"ev_dep_{uuid.uuid4().hex[:8]}"

        if graph_metadata is None:
            return DependencyRiskSignal(
                signal_id=f"dep_{uuid.uuid4().hex[:6]}",
                service=service,
                dependency=dependency,
                centrality=0.0,
                scc_id=None,
                breadth=0,
                historical_incident_count=historical_incidents,
                runtime_status="unknown",
                risk_level=RiskLevel.INSUFFICIENT_EVIDENCE,
                evidence_id=evidence_id,
            )

        centrality = float(graph_metadata.get("centrality", 0.0))
        scc_id = graph_metadata.get("scc_id")
        is_cyclic = bool(graph_metadata.get("in_cycle", False))
        breadth = int(graph_metadata.get("dependency_count", 1))
        contract_status = graph_metadata.get("contract_status", "stable")

        # Risk scoring
        risk_points = 0
        if centrality >= self.high_centrality:
            risk_points += 2
        if is_cyclic:
            risk_points += 2
        if breadth >= self.broad_threshold:
            risk_points += 1
        if historical_incidents >= 2:
            risk_points += 2
        if contract_status in ("drifting", "broken", "unstable"):
            risk_points += 2
        if runtime_latency_ms and runtime_latency_ms > 500.0:
            risk_points += 2

        if risk_points >= 4:
            level = RiskLevel.HIGH
        elif risk_points >= 2:
            level = RiskLevel.MEDIUM
        else:
            level = RiskLevel.LOW

        rt_status = "healthy"
        if runtime_latency_ms and runtime_latency_ms > 500.0:
            rt_status = "degraded"

        return DependencyRiskSignal(
            signal_id=f"dep_{uuid.uuid4().hex[:6]}",
            service=service,
            dependency=dependency,
            centrality=round(centrality, 3),
            scc_id=scc_id,
            breadth=breadth,
            historical_incident_count=historical_incidents,
            runtime_status=rt_status,
            risk_level=level,
            evidence_id=evidence_id,
        )
