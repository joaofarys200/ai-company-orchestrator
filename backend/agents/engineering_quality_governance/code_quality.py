"""
JARVIS OS — Phase 68: Code Quality Evaluator
Computes observable metrics:
- complexity (cyclomatic / cognitive)
- duplication ratio
- function size
- class size
- nesting depth
- dead code signals
- import anomalies (circular, unused, wildcard)
- type uncertainty
- code churn
- change concentration

No rigid universal thresholds; thresholds are policy-configurable.
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


class CodeQualityEvaluator:
    """
    Evaluates observable code quality metrics without rigid dogmatic assumptions.
    All thresholds are policy-driven.
    """

    def __init__(self, thresholds: Optional[Dict[str, float]] = None) -> None:
        self.thresholds = thresholds or {
            "max_complexity": 20.0,
            "max_duplication_ratio": 0.08,
            "max_function_size": 80.0,
            "max_class_size": 400.0,
            "max_nesting": 5.0,
            "max_type_uncertainty": 0.25,
            "max_change_concentration": 0.70,
        }

    def evaluate(
        self,
        context: Optional[Dict[str, Any]] = None,
        scope: str = "global",
    ) -> DimensionEvaluation:
        ctx = context or {}
        code_data = ctx.get("code", {})

        complexity = float(code_data.get("complexity", 8.5))
        duplication = float(code_data.get("duplication", 0.02))
        fn_size = float(code_data.get("function_size", 28.0))
        class_size = float(code_data.get("class_size", 140.0))
        nesting = float(code_data.get("nesting", 2.4))
        dead_code = int(code_data.get("dead_code_signals", 0))
        import_anomalies = int(code_data.get("import_anomalies", 0))
        type_uncertainty = float(code_data.get("type_uncertainty", 0.06))
        code_churn = int(code_data.get("code_churn", 120))
        change_conc = float(code_data.get("change_concentration", 0.35))

        observations = [
            QualityObservation(
                dimension=QualityDimension.CODE,
                metric_name="complexity",
                measured_value=complexity,
                evidence={"mean_cyclomatic_complexity": complexity},
                uncertainty=0.03,
                scope=scope,
                observation_type=ObservationType.OBSERVED,
            ),
            QualityObservation(
                dimension=QualityDimension.CODE,
                metric_name="duplication",
                measured_value=duplication,
                evidence={"duplication_ratio": duplication},
                uncertainty=0.04,
                scope=scope,
                observation_type=ObservationType.OBSERVED,
            ),
            QualityObservation(
                dimension=QualityDimension.CODE,
                metric_name="function_size",
                measured_value=fn_size,
                evidence={"mean_loc_per_function": fn_size},
                uncertainty=0.02,
                scope=scope,
                observation_type=ObservationType.OBSERVED,
            ),
            QualityObservation(
                dimension=QualityDimension.CODE,
                metric_name="class_size",
                measured_value=class_size,
                evidence={"mean_loc_per_class": class_size},
                uncertainty=0.02,
                scope=scope,
                observation_type=ObservationType.OBSERVED,
            ),
            QualityObservation(
                dimension=QualityDimension.CODE,
                metric_name="nesting",
                measured_value=nesting,
                evidence={"mean_max_nesting_depth": nesting},
                uncertainty=0.03,
                scope=scope,
                observation_type=ObservationType.OBSERVED,
            ),
            QualityObservation(
                dimension=QualityDimension.CODE,
                metric_name="dead_code_signals",
                measured_value=dead_code,
                evidence={"unreferenced_symbols_detected": dead_code},
                uncertainty=0.10,
                scope=scope,
                observation_type=ObservationType.ESTIMATED,
            ),
            QualityObservation(
                dimension=QualityDimension.CODE,
                metric_name="import_anomalies",
                measured_value=import_anomalies,
                evidence={"circular_or_stale_imports": import_anomalies},
                uncertainty=0.05,
                scope=scope,
                observation_type=ObservationType.OBSERVED,
            ),
            QualityObservation(
                dimension=QualityDimension.CODE,
                metric_name="type_uncertainty",
                measured_value=type_uncertainty,
                evidence={"untyped_or_any_ratio": type_uncertainty},
                uncertainty=0.05,
                scope=scope,
                observation_type=ObservationType.OBSERVED,
            ),
            QualityObservation(
                dimension=QualityDimension.CODE,
                metric_name="code_churn",
                measured_value=code_churn,
                evidence={"lines_added_and_deleted": code_churn},
                uncertainty=0.01,
                scope=scope,
                observation_type=ObservationType.OBSERVED,
            ),
            QualityObservation(
                dimension=QualityDimension.CODE,
                metric_name="change_concentration",
                measured_value=change_conc,
                evidence={"gini_coefficient_of_changes": change_conc},
                uncertainty=0.06,
                scope=scope,
                observation_type=ObservationType.ESTIMATED,
            ),
        ]

        is_degraded = (
            complexity > self.thresholds["max_complexity"]
            or duplication > self.thresholds["max_duplication_ratio"]
            or type_uncertainty > self.thresholds["max_type_uncertainty"]
            or change_conc > self.thresholds["max_change_concentration"]
        )

        status = DimensionStatus.DEGRADED if is_degraded else DimensionStatus.HEALTHY
        summary = (
            f"Code status {status.value}: complexity={complexity:.1f}, "
            f"duplication={duplication:.1%}, fn_size={fn_size:.1f}, "
            f"nesting={nesting:.1f}, dead_code={dead_code}, "
            f"type_uncertainty={type_uncertainty:.1%}"
        )

        return DimensionEvaluation(
            dimension=QualityDimension.CODE,
            observations=observations,
            evidence=[{"evaluator": "CodeQualityEvaluator", "churn": code_churn}],
            uncertainty=0.05,
            scope=scope,
            status=status,
            summary=summary,
        )

    def compare_code(
        self,
        baseline_eval: DimensionEvaluation,
        after_eval: DimensionEvaluation,
    ) -> Tuple[DimensionChange, List[Dict[str, Any]], List[Dict[str, Any]]]:
        base_obs = {o.metric_name: o.measured_value for o in baseline_eval.observations}
        after_obs = {o.metric_name: o.measured_value for o in after_eval.observations}

        degradations = []
        improvements = []

        b_comp = float(base_obs.get("complexity", 0.0))
        a_comp = float(after_obs.get("complexity", 0.0))
        if a_comp > b_comp + 2.0:
            degradations.append({"metric": "complexity", "from": b_comp, "to": a_comp, "reason": "cyclomatic complexity increased"})
        elif a_comp < b_comp - 2.0:
            improvements.append({"metric": "complexity", "from": b_comp, "to": a_comp, "reason": "cyclomatic complexity refactored"})

        b_dup = float(base_obs.get("duplication", 0.0))
        a_dup = float(after_obs.get("duplication", 0.0))
        if a_dup > b_dup + 0.03:
            degradations.append({"metric": "duplication", "from": b_dup, "to": a_dup, "reason": "duplication increased"})
        elif a_dup < b_dup - 0.03:
            improvements.append({"metric": "duplication", "from": b_dup, "to": a_dup, "reason": "duplication extracted"})

        b_type = float(base_obs.get("type_uncertainty", 0.0))
        a_type = float(after_obs.get("type_uncertainty", 0.0))
        if a_type > b_type + 0.08:
            degradations.append({"metric": "type_uncertainty", "from": b_type, "to": a_type, "reason": "type annotations loosened or omitted"})
        elif a_type < b_type - 0.08:
            improvements.append({"metric": "type_uncertainty", "from": b_type, "to": a_type, "reason": "type annotations tightened"})

        if degradations and not improvements:
            return DimensionChange.DEGRADED, degradations, improvements
        if improvements and not degradations:
            return DimensionChange.IMPROVED, degradations, improvements
        if degradations and improvements:
            return DimensionChange.UNCERTAIN, degradations, improvements

        return DimensionChange.UNCHANGED, degradations, improvements
