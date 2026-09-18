"""
JARVIS OS — Phase 64: Autonomous Architecture Evolution & Design Governance
Module: comparison.py
Multi-dimensional comparative trade-off evaluator across architectural candidates.

Rule:
    Never produce an absolute 'BEST_ARCHITECTURE'.
    Produce COMPARABLE_ALTERNATIVES with explicit multi-axis trade-offs.
    Do not automatically select an alternative based solely on an aggregated scalar.
"""

from __future__ import annotations

from typing import Any, Dict, List

from .models import (
    ArchitectureAlternative,
    ArchitectureComparisonResult,
    ArchitectureProblem,
    CostEstimationResult,
    ImpactAnalysisResult,
    RiskAnalysisResult,
)


class ArchitectureComparator:
    """Compares candidate alternatives across technical, operational, and financial dimensions."""

    def compare_alternatives(
        self,
        problem: ArchitectureProblem,
        alternatives: List[ArchitectureAlternative],
        impacts: Dict[str, ImpactAnalysisResult],
        risks: Dict[str, RiskAnalysisResult],
        costs: Dict[str, CostEstimationResult],
    ) -> ArchitectureComparisonResult:
        serialized_alternatives: List[Dict[str, Any]] = []
        tradeoffs: List[Dict[str, Any]] = []
        radar_metrics: Dict[str, Dict[str, float]] = {}

        for alt in alternatives:
            alt_id = alt.alternative_id
            imp = impacts.get(alt_id)
            rsk = risks.get(alt_id)
            cst = costs.get(alt_id)

            blast = imp.blast_radius if imp else 0
            crit = rsk.criticality.value if rsk else "LOW"
            effort = cst.total_estimated_effort_hours if cst else 0.0

            serialized_alternatives.append({
                "alternative_id": alt_id,
                "title": alt.title,
                "type": alt.alternative_type.value,
                "reversibility": alt.reversibility.value,
                "blast_radius": blast,
                "risk_criticality": crit,
                "estimated_effort_hours": effort,
                "is_hypothesis_from_f63": alt.is_hypothesis_from_f63,
            })

            # Radar metrics normalized between 0.0 and 1.0 (higher = better/safer)
            coupling_score = 0.9 if alt.alternative_type.value in ["modularization", "boundary_extraction"] else 0.5
            reversibility_score = 1.0 if alt.reversibility.value == "EASILY_REVERSIBLE" else 0.7 if "WITH_MIGRATION" in alt.reversibility.value else 0.2
            cost_efficiency = max(0.1, 1.0 - (effort / 100.0))
            risk_safety = 0.9 if crit == "LOW" else 0.6 if crit == "MEDIUM" else 0.3 if crit == "HIGH" else 0.1
            contract_safety = 0.95 if not imp or not imp.affected_contracts else 0.6

            radar_metrics[alt_id] = {
                "coupling_reduction": coupling_score,
                "reversibility": reversibility_score,
                "cost_efficiency": round(cost_efficiency, 2),
                "risk_safety": risk_safety,
                "contract_safety": contract_safety,
                "verification_tractability": 0.85 if blast < 20 else 0.50,
            }

            tradeoffs.append({
                "alternative_id": alt_id,
                "title": alt.title,
                "pros": alt.benefits,
                "cons": alt.costs,
                "risks": alt.risks,
                "summary": f"Trade-off: Blast radius={blast}, Effort={effort}h, Reversibility={alt.reversibility.value}",
            })

        return ArchitectureComparisonResult(
            problem_id=problem.problem_id,
            alternatives=serialized_alternatives,
            tradeoffs=tradeoffs,
            radar_metrics=radar_metrics,
        )
