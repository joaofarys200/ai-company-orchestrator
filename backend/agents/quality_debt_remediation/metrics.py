"""
JARVIS OS — Phase 69: Autonomous Quality Debt Remediation
Remediation metrics and prioritization engine.
Calculates priority vectors without single-number reductionism and tracks remediation performance metrics.
"""

from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List

from .debt import IngestedDebtItem
from .models import RemediationPriorityVector


@dataclass
class RemediationMetricsSummary:
    total_debts_ingested: int
    total_validated: int
    total_resolved: int
    total_partially_resolved: int
    total_deferred: int
    total_blocked: int
    total_rolled_back: int
    gaming_incidents_blocked: int
    average_resolution_time_ms: float
    convergence_rate: float

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class RemediationPriorityEngine:
    """
    Computes a multi-attribute priority vector for technical debt items.
    Balances risk, severity, recurrence, blast radius, security, contract, and behavior impact.
    Does NOT declare a simplistic 'best debt to fix'.
    """

    SEVERITY_WEIGHTS = {
        "CRITICAL": 1.0,
        "HIGH": 0.75,
        "MEDIUM": 0.5,
        "LOW": 0.25,
    }

    def compute_priority_vector(self, item: IngestedDebtItem) -> RemediationPriorityVector:
        severity_score = self.SEVERITY_WEIGHTS.get(item.severity.upper(), 0.5)
        risk_score = min(1.0, severity_score * (item.recurrence / 2.0))
        recurrence_score = min(1.0, item.recurrence / 5.0)

        # Blast radius heuristic based on affected surface length or depth
        surface_depth = len(item.affected_surface.split("."))
        blast_radius = min(1.0, surface_depth / 5.0)

        security_score = 1.0 if "SECURITY" in item.category.upper() else 0.1
        contract_score = 0.8 if "CONTRACT" in item.category.upper() or "API" in item.affected_surface.upper() else 0.2
        behavior_score = 0.85 if "BEHAVIOR" in item.category.upper() else 0.2

        remediation_cost = min(1.0, (blast_radius * 0.5) + (severity_score * 0.5))
        evidence_strength = item.confidence
        age_normalized = min(1.0, item.age_days / 60.0)

        # Composite multi-factor rank score (for sorting only, not single-number authority)
        rank_score = round(
            (severity_score * 0.25)
            + (security_score * 0.20)
            + (risk_score * 0.15)
            + (evidence_strength * 0.15)
            + (recurrence_score * 0.10)
            + (contract_score * 0.10)
            + (age_normalized * 0.05),
            4,
        )

        rationale = (
            f"Debt {item.debt_id} priority vector calculated: Severity={severity_score:.2f}, "
            f"Security={security_score:.2f}, BlastRadius={blast_radius:.2f}, RankScore={rank_score:.4f}."
        )

        return RemediationPriorityVector(
            debt_id=item.debt_id,
            risk=round(risk_score, 3),
            severity=round(severity_score, 3),
            recurrence=round(recurrence_score, 3),
            blast_radius=round(blast_radius, 3),
            security=round(security_score, 3),
            contract_impact=round(contract_score, 3),
            behavior_impact=round(behavior_score, 3),
            remediation_cost=round(remediation_cost, 3),
            evidence_strength=round(evidence_strength, 3),
            age=round(age_normalized, 3),
            rank_score=rank_score,
            rationale=rationale,
        )


class RemediationMetricsEngine:
    """
    Computes system-level remediation metrics and velocity.
    """

    def compute_summary(
        self,
        ingested_count: int,
        validated_count: int,
        resolved_count: int,
        partially_resolved_count: int,
        deferred_count: int,
        blocked_count: int,
        rolled_back_count: int,
        gaming_count: int,
        durations_ms: List[float],
    ) -> RemediationMetricsSummary:
        avg_dur = sum(durations_ms) / len(durations_ms) if durations_ms else 0.0
        convergence_rate = round(resolved_count / max(1, ingested_count), 4)

        return RemediationMetricsSummary(
            total_debts_ingested=ingested_count,
            total_validated=validated_count,
            total_resolved=resolved_count,
            total_partially_resolved=partially_resolved_count,
            total_deferred=deferred_count,
            total_blocked=blocked_count,
            total_rolled_back=rolled_back_count,
            gaming_incidents_blocked=gaming_count,
            average_resolution_time_ms=round(avg_dur, 2),
            convergence_rate=convergence_rate,
        )

