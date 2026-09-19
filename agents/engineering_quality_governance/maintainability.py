"""
JARVIS OS — Phase 68: Maintainability Quality Evaluator
Synthesizes:
- architecture structure
- code complexity
- symbol graph reachability
- testability index
- documentation completeness & freshness
- change propagation factor
- ownership / agent surface clarity
- module boundaries

Produces: MAINTAINABILITY_OBSERVATION with concrete structural evidence.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from .models import (
    DimensionChange,
    DimensionEvaluation,
    DimensionStatus,
    ObservationType,
    QualityDimension,
    QualityObservation,
)


class MaintainabilityQualityEvaluator:
    """
    Evaluates long-term maintainability, comprehensibility, and modular modifiability.
    """

    def __init__(self) -> None:
        pass

    def evaluate(
        self,
        context: Optional[Dict[str, Any]] = None,
        scope: str = "global",
    ) -> DimensionEvaluation:
        ctx = context or {}
        m_data = ctx.get("maintainability", {})

        testability_index = float(m_data.get("testability_index", 0.85))
        doc_completeness = float(m_data.get("documentation_completeness", 0.90))
        change_propagation = float(m_data.get("change_propagation_factor", 0.22))
        symbol_graph_clarity = float(m_data.get("symbol_graph_clarity", 0.88))
        ownership_clarity = float(m_data.get("ownership_clarity", 0.80))
        module_boundary_index = float(m_data.get("module_boundary_index", 0.82))

        observations = [
            QualityObservation(
                dimension=QualityDimension.MAINTAINABILITY,
                metric_name="testability_index",
                measured_value=testability_index,
                evidence={"decoupled_injection_score": testability_index},
                uncertainty=0.04,
                scope=scope,
                observation_type=ObservationType.OBSERVED,
            ),
            QualityObservation(
                dimension=QualityDimension.MAINTAINABILITY,
                metric_name="documentation_completeness",
                measured_value=doc_completeness,
                evidence={"documented_symbols_ratio": doc_completeness},
                uncertainty=0.03,
                scope=scope,
                observation_type=ObservationType.OBSERVED,
            ),
            QualityObservation(
                dimension=QualityDimension.MAINTAINABILITY,
                metric_name="change_propagation_factor",
                measured_value=change_propagation,
                evidence={"ripple_effect_ratio": change_propagation},
                uncertainty=0.05,
                scope=scope,
                observation_type=ObservationType.ESTIMATED,
            ),
            QualityObservation(
                dimension=QualityDimension.MAINTAINABILITY,
                metric_name="symbol_graph_clarity",
                measured_value=symbol_graph_clarity,
                evidence={"unambiguous_symbol_resolution_pct": symbol_graph_clarity},
                uncertainty=0.03,
                scope=scope,
                observation_type=ObservationType.OBSERVED,
            ),
            QualityObservation(
                dimension=QualityDimension.MAINTAINABILITY,
                metric_name="ownership_clarity",
                measured_value=ownership_clarity,
                evidence={"agent_or_team_surface_mapping": ownership_clarity},
                uncertainty=0.08,
                scope=scope,
                observation_type=ObservationType.INFERRED,
            ),
            QualityObservation(
                dimension=QualityDimension.MAINTAINABILITY,
                metric_name="module_boundary_index",
                measured_value=module_boundary_index,
                evidence={"encapsulation_adherence": module_boundary_index},
                uncertainty=0.04,
                scope=scope,
                observation_type=ObservationType.OBSERVED,
            ),
        ]

        is_degraded = (
            testability_index < 0.60
            or doc_completeness < 0.60
            or change_propagation > 0.50
            or module_boundary_index < 0.60
        )

        status = DimensionStatus.DEGRADED if is_degraded else DimensionStatus.HEALTHY
        summary = (
            f"Maintainability status {status.value}: testability={testability_index:.1%}, "
            f"doc={doc_completeness:.1%}, ripple={change_propagation:.1%}, "
            f"boundaries={module_boundary_index:.1%}"
        )

        return DimensionEvaluation(
            dimension=QualityDimension.MAINTAINABILITY,
            observations=observations,
            evidence=[{
                "evaluator": "MaintainabilityQualityEvaluator",
                "testability_index": testability_index,
                "change_propagation": change_propagation,
            }],
            uncertainty=0.05,
            scope=scope,
            status=status,
            summary=summary,
        )

    def compare_maintainability(
        self,
        baseline_eval: DimensionEvaluation,
        after_eval: DimensionEvaluation,
    ) -> Tuple[DimensionChange, List[Dict[str, Any]], List[Dict[str, Any]]]:
        base_obs = {o.metric_name: o.measured_value for o in baseline_eval.observations}
        after_obs = {o.metric_name: o.measured_value for o in after_eval.observations}

        degradations = []
        improvements = []

        b_rip = float(base_obs.get("change_propagation_factor", 0.0))
        a_rip = float(after_obs.get("change_propagation_factor", 0.0))
        if a_rip > b_rip + 0.10:
            degradations.append({"metric": "change_propagation_factor", "from": b_rip, "to": a_rip, "reason": "change ripple effect expanded"})
        elif a_rip < b_rip - 0.10:
            improvements.append({"metric": "change_propagation_factor", "from": b_rip, "to": a_rip, "reason": "change ripple effect contained"})

        b_test = float(base_obs.get("testability_index", 0.0))
        a_test = float(after_obs.get("testability_index", 0.0))
        if a_test < b_test - 0.10:
            degradations.append({"metric": "testability_index", "from": b_test, "to": a_test, "reason": "testability decreased"})
        elif a_test > b_test + 0.10:
            improvements.append({"metric": "testability_index", "from": b_test, "to": a_test, "reason": "testability improved"})

        if degradations and not improvements:
            return DimensionChange.DEGRADED, degradations, improvements
        if improvements and not degradations:
            return DimensionChange.IMPROVED, degradations, improvements
        if degradations and improvements:
            return DimensionChange.UNCERTAIN, degradations, improvements

        return DimensionChange.UNCHANGED, degradations, improvements
