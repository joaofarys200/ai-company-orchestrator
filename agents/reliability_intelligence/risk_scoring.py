"""
Phase 72 — Multi-Factor Risk Scoring Engine
Combines anomalies, trends, capacity pressure, recurrence, and architectural dependencies.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from .models import (
    AnomalySignal,
    AnomalyStatus,
    CapacitySignal,
    CapacityStatus,
    DependencyRiskSignal,
    RecurrenceSignal,
    RecurrenceStatus,
    RiskLevel,
    TrendSignal,
    TrendStatus,
)


class RiskScoringEngine:
    """Calculates weighted multi-signal risk index."""

    def score(
        self,
        anomalies: List[AnomalySignal],
        trends: List[TrendSignal],
        capacities: List[CapacitySignal],
        recurrences: List[RecurrenceSignal],
        dependencies: List[DependencyRiskSignal],
    ) -> tuple[float, RiskLevel, List[Dict[str, Any]], List[Dict[str, Any]]]:
        contributing: List[Dict[str, Any]] = []
        contradictory: List[Dict[str, Any]] = []

        total_weight = 0.0
        weighted_score = 0.0

        # 1. Anomalies (Weight: 0.35)
        if anomalies:
            anom_weight = 0.35
            total_weight += anom_weight
            anom_active = [a for a in anomalies if a.status == AnomalyStatus.ANOMALOUS]
            anom_ratio = len(anom_active) / len(anomalies)
            weighted_score += anom_ratio * anom_weight

            for a in anom_active:
                contributing.append({
                    "type": "ANOMALY",
                    "metric": a.metric,
                    "deviation": a.deviation,
                    "detector": a.detector,
                })
            for norm in [a for a in anomalies if a.status == AnomalyStatus.NORMAL]:
                contradictory.append({
                    "type": "NORMAL_METRIC",
                    "metric": norm.metric,
                    "value": norm.observed_value,
                })

        # 2. Trends (Weight: 0.25)
        if trends:
            trend_weight = 0.25
            total_weight += trend_weight
            degrading = [t for t in trends if t.status == TrendStatus.DEGRADING]
            trend_score = sum(t.confidence for t in degrading) / max(1, len(trends))
            weighted_score += min(1.0, trend_score) * trend_weight

            for t in degrading:
                contributing.append({
                    "type": "DEGRADING_TREND",
                    "metric": t.metric,
                    "slope": t.slope,
                    "confidence": t.confidence,
                })
            for t in [t for t in trends if t.status == TrendStatus.IMPROVING]:
                contradictory.append({
                    "type": "IMPROVING_TREND",
                    "metric": t.metric,
                    "slope": t.slope,
                })

        # 3. Capacity (Weight: 0.20)
        if capacities:
            cap_weight = 0.20
            total_weight += cap_weight
            cap_points = sum(
                1.0 if c.status == CapacityStatus.RISK else (0.5 if c.status == CapacityStatus.PRESSURE else 0.0)
                for c in capacities
            )
            cap_score = cap_points / len(capacities)
            weighted_score += cap_score * cap_weight

            for c in capacities:
                if c.status in (CapacityStatus.RISK, CapacityStatus.PRESSURE):
                    contributing.append({
                        "type": "CAPACITY_PRESSURE",
                        "resource": c.resource_type,
                        "status": c.status.value,
                        "utilization": c.utilization,
                    })

        # 4. Recurrence (Weight: 0.10)
        if recurrences:
            rec_weight = 0.10
            total_weight += rec_weight
            recurrent = [r for r in recurrences if r.status in (RecurrenceStatus.RECURRENT, RecurrenceStatus.ESCALATING_RECURRENCE)]
            if recurrent:
                weighted_score += rec_weight
                for r in recurrent:
                    contributing.append({
                        "type": "RECURRING_INCIDENT",
                        "category": r.incident_category,
                        "count": r.occurrence_count,
                    })

        # 5. Dependency Risk (Weight: 0.10)
        if dependencies:
            dep_weight = 0.10
            total_weight += dep_weight
            dep_high = [d for d in dependencies if d.risk_level == RiskLevel.HIGH]
            if dep_high:
                weighted_score += dep_weight
                for d in dep_high:
                    contributing.append({
                        "type": "HIGH_DEPENDENCY_RISK",
                        "dependency": d.dependency,
                    })

        if total_weight == 0.0:
            return 0.0, RiskLevel.UNKNOWN, [], []

        normalized_score = min(1.0, weighted_score / total_weight)

        if normalized_score >= 0.65:
            level = RiskLevel.HIGH
        elif normalized_score >= 0.35:
            level = RiskLevel.MEDIUM
        else:
            level = RiskLevel.LOW

        return round(normalized_score, 3), level, contributing, contradictory
