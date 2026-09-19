"""
JARVIS OS — Phase 68: Technical Debt Prioritization
Evaluates:
- risk
- impact
- recurrence
- remediation cost
- affected missions
- security relevance
- reversibility
- evidence strength

Core Invariant:
Do NOT reduce prioritization to a single scalar authority.
Produces a detailed PRIORITY_VECTOR alongside human-readable rationale.
"""

from __future__ import annotations

from typing import Any, Dict, List

from .models import DebtCategory, DebtSeverity, PriorityVector, TechnicalDebtItem


class DebtPrioritizer:
    """
    Evaluates multi-attribute prioritization vectors for technical debt items.
    """

    def __init__(self) -> None:
        pass

    def compute_priority_vector(
        self,
        item: TechnicalDebtItem,
        affected_missions_count: int = 1,
    ) -> PriorityVector:
        # Multi-factor attribute scoring
        risk = float(item.risk)

        # Impact inferred from severity & category
        impact_map = {
            DebtSeverity.CRITICAL: 1.0,
            DebtSeverity.HIGH: 0.8,
            DebtSeverity.MEDIUM: 0.5,
            DebtSeverity.LOW: 0.2,
        }
        impact = impact_map.get(item.severity, 0.5)

        # Recurrence normalized
        recurrence = min(1.0, item.recurrence_count / 5.0)

        # Remediation cost
        remediation_cost = float(item.estimated_cost)

        # Security relevance: if category is SECURITY or touches security, maximum factor
        security_relevance = 1.0 if item.category == DebtCategory.SECURITY else (
            0.6 if "security" in item.affected_surface.lower() or "auth" in item.affected_surface.lower() else 0.1
        )

        # Reversibility: Architectural changes are harder to reverse than documentation/test tweaks
        reversibility_map = {
            DebtCategory.ARCHITECTURAL: 0.2,
            DebtCategory.CONTRACT: 0.3,
            DebtCategory.SECURITY: 0.4,
            DebtCategory.CODE: 0.7,
            DebtCategory.TEST: 0.9,
            DebtCategory.DOCUMENTATION: 1.0,
            DebtCategory.OPERATIONAL: 0.6,
            DebtCategory.BEHAVIOR: 0.5,
            DebtCategory.PERFORMANCE: 0.6,
        }
        reversibility = reversibility_map.get(item.category, 0.5)

        # Evidence strength inferred from confidence and count of evidence entries
        evidence_strength = min(1.0, (item.confidence * 0.7) + (min(len(item.evidence), 3) * 0.1))

        # Balanced ranking calculation (for ordering in UI, NOT as a dogmatic absolute authority)
        # Higher risk, impact, security, recurrence and lower reversibility -> higher urgency
        rank_score = (
            (risk * 0.25)
            + (impact * 0.25)
            + (security_relevance * 0.20)
            + (recurrence * 0.15)
            + ((1.0 - reversibility) * 0.10)
            + (evidence_strength * 0.05)
        )

        explanation = (
            f"Debt item '{item.debt_id}' in category '{item.category.value}': "
            f"risk={risk:.2f}, impact={impact:.2f}, security={security_relevance:.2f}, "
            f"recurrence={item.recurrence_count}x, cost={remediation_cost:.1f}, "
            f"reversibility={reversibility:.2f}. "
            f"{'CRITICAL SECURITY PRIORITY: Must be mitigated immediately.' if security_relevance > 0.8 else 'Scheduled for standard governance backlog.'}"
        )

        return PriorityVector(
            debt_id=item.debt_id,
            risk=risk,
            impact=impact,
            recurrence=recurrence,
            remediation_cost=remediation_cost,
            affected_missions=affected_missions_count,
            security_relevance=security_relevance,
            reversibility=reversibility,
            evidence_strength=evidence_strength,
            rank_score=rank_score,
            explanation=explanation,
        )

    def prioritize_all(
        self,
        items: List[TechnicalDebtItem],
    ) -> List[PriorityVector]:
        vectors = [self.compute_priority_vector(item) for item in items]
        # Sort descending by rank_score
        vectors.sort(key=lambda v: v.rank_score, reverse=True)
        return vectors
