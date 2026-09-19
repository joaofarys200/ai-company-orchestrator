"""
JARVIS OS — Phase 68: Contract Quality Evaluator
Integrates F44–F49 (Semantic Graph, Runtime Discovery, Contract Drift,
Polymorphic Contracts, Change Management, Build Extraction).

Evaluates:
- breaking changes
- polymorphic ambiguity
- consumer coverage
- contract drift
- unresolved consumers
- stale schemas
- undocumented changes

States:
HEALTHY, DEGRADED, UNKNOWN, BLOCKED.
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


class ContractQualityEvaluator:
    """
    Evaluates schema and semantic contract stability, drift, and consumer safety.
    """

    def __init__(self) -> None:
        pass

    def evaluate(
        self,
        context: Optional[Dict[str, Any]] = None,
        scope: str = "global",
    ) -> DimensionEvaluation:
        ctx = context or {}
        c_data = ctx.get("contract", {})

        breaking_changes = int(c_data.get("breaking_changes", 0))
        poly_ambiguity = int(c_data.get("polymorphic_ambiguity", 0))
        consumer_cov = float(c_data.get("consumer_coverage", 0.95))
        contract_drift = int(c_data.get("contract_drift", 0))
        unresolved_consumers = int(c_data.get("unresolved_consumers", 0))
        stale_schemas = int(c_data.get("stale_schemas", 0))
        undocumented_changes = int(c_data.get("undocumented_changes", 0))

        observations = [
            QualityObservation(
                dimension=QualityDimension.CONTRACT,
                metric_name="breaking_changes",
                measured_value=breaking_changes,
                evidence={"breaking_count": breaking_changes},
                uncertainty=0.01,
                scope=scope,
                observation_type=ObservationType.OBSERVED,
            ),
            QualityObservation(
                dimension=QualityDimension.CONTRACT,
                metric_name="polymorphic_ambiguity",
                measured_value=poly_ambiguity,
                evidence={"ambiguous_variants": poly_ambiguity},
                uncertainty=0.03,
                scope=scope,
                observation_type=ObservationType.OBSERVED,
            ),
            QualityObservation(
                dimension=QualityDimension.CONTRACT,
                metric_name="consumer_coverage",
                measured_value=consumer_cov,
                evidence={"verified_consumer_ratio": consumer_cov},
                uncertainty=0.02,
                scope=scope,
                observation_type=ObservationType.OBSERVED,
            ),
            QualityObservation(
                dimension=QualityDimension.CONTRACT,
                metric_name="contract_drift",
                measured_value=contract_drift,
                evidence={"unregistered_schema_deviations": contract_drift},
                uncertainty=0.04,
                scope=scope,
                observation_type=ObservationType.OBSERVED,
            ),
            QualityObservation(
                dimension=QualityDimension.CONTRACT,
                metric_name="unresolved_consumers",
                measured_value=unresolved_consumers,
                evidence={"unresolved_consumer_endpoints": unresolved_consumers},
                uncertainty=0.05,
                scope=scope,
                observation_type=ObservationType.ESTIMATED,
            ),
            QualityObservation(
                dimension=QualityDimension.CONTRACT,
                metric_name="stale_schemas",
                measured_value=stale_schemas,
                evidence={"outdated_idl_or_pydantic": stale_schemas},
                uncertainty=0.02,
                scope=scope,
                observation_type=ObservationType.OBSERVED,
            ),
            QualityObservation(
                dimension=QualityDimension.CONTRACT,
                metric_name="undocumented_changes",
                measured_value=undocumented_changes,
                evidence={"payload_alterations_without_doc": undocumented_changes},
                uncertainty=0.03,
                scope=scope,
                observation_type=ObservationType.OBSERVED,
            ),
        ]

        if breaking_changes > 0 or unresolved_consumers > 2:
            status = DimensionStatus.BLOCKED
        elif contract_drift > 0 or poly_ambiguity > 0 or stale_schemas > 0 or consumer_cov < 0.85:
            status = DimensionStatus.DEGRADED
        elif not c_data:
            status = DimensionStatus.UNKNOWN
        else:
            status = DimensionStatus.HEALTHY

        summary = (
            f"Contract status {status.value}: breaking={breaking_changes}, "
            f"drift={contract_drift}, unresolved={unresolved_consumers}, "
            f"consumer_cov={consumer_cov:.1%}"
        )

        return DimensionEvaluation(
            dimension=QualityDimension.CONTRACT,
            observations=observations,
            evidence=[{"evaluator": "ContractQualityEvaluator", "breaking": breaking_changes}],
            uncertainty=0.02 if c_data else 0.50,
            scope=scope,
            status=status,
            summary=summary,
        )

    def compare_contracts(
        self,
        baseline_eval: DimensionEvaluation,
        after_eval: DimensionEvaluation,
    ) -> Tuple[DimensionChange, List[Dict[str, Any]], List[Dict[str, Any]]]:
        base_obs = {o.metric_name: o.measured_value for o in baseline_eval.observations}
        after_obs = {o.metric_name: o.measured_value for o in after_eval.observations}

        degradations = []
        improvements = []

        b_brk = int(base_obs.get("breaking_changes", 0))
        a_brk = int(after_obs.get("breaking_changes", 0))
        if a_brk > b_brk:
            degradations.append({"metric": "breaking_changes", "from": b_brk, "to": a_brk, "reason": "new breaking changes introduced"})
        elif a_brk < b_brk:
            improvements.append({"metric": "breaking_changes", "from": b_brk, "to": a_brk, "reason": "breaking changes resolved"})

        b_drift = int(base_obs.get("contract_drift", 0))
        a_drift = int(after_obs.get("contract_drift", 0))
        if a_drift > b_drift:
            degradations.append({"metric": "contract_drift", "from": b_drift, "to": a_drift, "reason": "contract drift detected"})
        elif a_drift < b_drift:
            improvements.append({"metric": "contract_drift", "from": b_drift, "to": a_drift, "reason": "contract drift reconciled"})

        if degradations and not improvements:
            return DimensionChange.DEGRADED, degradations, improvements
        if improvements and not degradations:
            return DimensionChange.IMPROVED, degradations, improvements
        if degradations and improvements:
            return DimensionChange.UNCERTAIN, degradations, improvements

        return DimensionChange.UNCHANGED, degradations, improvements
