"""
Phase 72 — Calibrated Incident Risk Prediction
Predicts failure class, horizon, and confidence.
Separates PREDICTION_QUALITY from DECISION_QUALITY.
"""

from __future__ import annotations

import time
import uuid
from typing import Any, Dict, List, Optional

from .models import (
    AnomalySignal,
    AnomalyStatus,
    CapacitySignal,
    CapacityStatus,
    DependencyRiskSignal,
    RecurrenceSignal,
    RiskLevel,
    RiskPrediction,
    TrendSignal,
    TrendStatus,
)
from .risk_scoring import RiskScoringEngine


class IncidentPredictor:
    """Produces empirical, bounded failure risk predictions."""

    def __init__(self, model_version: str = "v1.0.0-empirical"):
        self.model_version = model_version
        self.scoring_engine = RiskScoringEngine()

    def predict(
        self,
        target_service: str,
        anomalies: List[AnomalySignal],
        trends: List[TrendSignal],
        capacities: List[CapacitySignal],
        recurrences: List[RecurrenceSignal],
        dependencies: List[DependencyRiskSignal],
        horizon_seconds: float = 300.0,
    ) -> RiskPrediction:
        prediction_id = f"pred_{uuid.uuid4().hex[:8]}"
        now = time.time()

        score, risk_level, contributing, contradictory = self.scoring_engine.score(
            anomalies=anomalies,
            trends=trends,
            capacities=capacities,
            recurrences=recurrences,
            dependencies=dependencies,
        )

        # Determine failure class based on dominant contributing signals
        failure_class = "UNKNOWN_RUNTIME_RISK"
        evidence_ids = []

        for a in anomalies:
            evidence_ids.append(a.evidence_id)
            if a.status == AnomalyStatus.ANOMALOUS:
                if "latency" in a.metric:
                    failure_class = "LATENCY_SLO_BREACH"
                elif "error" in a.metric:
                    failure_class = "HTTP_5XX_BURST"
                elif "restart" in a.metric:
                    failure_class = "RESTART_LOOP"

        for c in capacities:
            evidence_ids.append(c.evidence_id)
            if c.status in (CapacityStatus.RISK, CapacityStatus.PRESSURE):
                if failure_class == "UNKNOWN_RUNTIME_RISK":
                    failure_class = f"RESOURCE_EXHAUSTION_{c.resource_type.upper()}"

        for t in trends:
            evidence_ids.append(t.evidence_id)

        # Confidence: based on data richness and consensus
        has_anom = any(a.status == AnomalyStatus.ANOMALOUS for a in anomalies)
        has_trend = any(t.status == TrendStatus.DEGRADING for t in trends)
        has_cap = any(c.status in (CapacityStatus.RISK, CapacityStatus.PRESSURE) for c in capacities)

        signal_count = sum([has_anom, has_trend, has_cap])
        confidence = 0.85 if signal_count >= 2 else (0.60 if signal_count == 1 else 0.25)

        # Invariant: If there are zero signals or all UNKNOWN, prediction MUST be UNKNOWN
        if not anomalies and not trends and not capacities:
            return RiskPrediction(
                prediction_id=prediction_id,
                target=target_service,
                failure_class="INSUFFICIENT_EVIDENCE",
                horizon_seconds=horizon_seconds,
                probability_estimate=0.0,
                confidence=0.0,
                risk_level=RiskLevel.UNKNOWN,
                evidence_ids=[f"ev_none_{uuid.uuid4().hex[:6]}"],
                contributing_signals=[],
                contradictory_signals=[],
                model_version=self.model_version,
                generated_at=now,
            )

        return RiskPrediction(
            prediction_id=prediction_id,
            target=target_service,
            failure_class=failure_class,
            horizon_seconds=horizon_seconds,
            probability_estimate=score,
            confidence=confidence,
            risk_level=risk_level,
            evidence_ids=list(set(evidence_ids)),
            contributing_signals=contributing,
            contradictory_signals=contradictory,
            model_version=self.model_version,
            generated_at=now,
        )
