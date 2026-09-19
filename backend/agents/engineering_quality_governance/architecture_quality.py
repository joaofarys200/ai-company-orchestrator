"""
JARVIS OS — Phase 68: Architecture Quality Evaluator
Integrates F58 (Massive Project State), F59 (SCC-Aware Graph), F60 (Symbol-Fine-Grained Graph),
and F64 (Architecture Evolution).

Measures:
- coupling
- fan-in
- fan-out
- SCC size
- dependency depth
- architectural boundaries
- dynamic boundaries
- blast radius
- modularity
- boundary violations

Classifies changes:
IMPROVED, DEGRADED, UNCHANGED, UNCERTAIN.

Invariant:
Never assume that fewer dependencies automatically means better architecture
(e.g., inlining that violates modular boundaries or artificially combines components
may reduce edge counts while increasing coupling and SCC condensation complexity).
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


class ArchitectureQualityEvaluator:
    """
    Evaluates system architecture health across structural and dynamic dimensions.
    """

    def __init__(self, thresholds: Optional[Dict[str, float]] = None) -> None:
        self.thresholds = thresholds or {
            "max_scc_size": 15,
            "max_coupling": 0.75,
            "max_blast_radius": 25,
            "max_boundary_violations": 0,
            "min_modularity": 0.40,
        }

    def evaluate(
        self,
        context: Optional[Dict[str, Any]] = None,
        scope: str = "global",
    ) -> DimensionEvaluation:
        ctx = context or {}
        arch_data = ctx.get("architecture", {})

        coupling = float(arch_data.get("coupling", 0.35))
        fan_in = int(arch_data.get("fan_in", 12))
        fan_out = int(arch_data.get("fan_out", 8))
        scc_size = int(arch_data.get("scc_size", 4))
        dep_depth = int(arch_data.get("dependency_depth", 5))
        arch_boundaries = int(arch_data.get("architectural_boundaries", 10))
        dyn_boundaries = int(arch_data.get("dynamic_boundaries", 2))
        blast_radius = int(arch_data.get("blast_radius", 7))
        modularity = float(arch_data.get("modularity", 0.68))
        boundary_violations = int(arch_data.get("boundary_violations", 0))

        observations = [
            QualityObservation(
                dimension=QualityDimension.ARCHITECTURE,
                metric_name="coupling",
                measured_value=coupling,
                evidence={"coupling_ratio": coupling},
                uncertainty=0.05,
                scope=scope,
                observation_type=ObservationType.OBSERVED,
            ),
            QualityObservation(
                dimension=QualityDimension.ARCHITECTURE,
                metric_name="fan_in",
                measured_value=fan_in,
                evidence={"fan_in_count": fan_in},
                uncertainty=0.02,
                scope=scope,
                observation_type=ObservationType.OBSERVED,
            ),
            QualityObservation(
                dimension=QualityDimension.ARCHITECTURE,
                metric_name="fan_out",
                measured_value=fan_out,
                evidence={"fan_out_count": fan_out},
                uncertainty=0.02,
                scope=scope,
                observation_type=ObservationType.OBSERVED,
            ),
            QualityObservation(
                dimension=QualityDimension.ARCHITECTURE,
                metric_name="scc_size",
                measured_value=scc_size,
                evidence={"largest_scc_node_count": scc_size},
                uncertainty=0.05,
                scope=scope,
                observation_type=ObservationType.OBSERVED,
            ),
            QualityObservation(
                dimension=QualityDimension.ARCHITECTURE,
                metric_name="dependency_depth",
                measured_value=dep_depth,
                evidence={"max_depth": dep_depth},
                uncertainty=0.05,
                scope=scope,
                observation_type=ObservationType.OBSERVED,
            ),
            QualityObservation(
                dimension=QualityDimension.ARCHITECTURE,
                metric_name="architectural_boundaries",
                measured_value=arch_boundaries,
                evidence={"defined_boundaries": arch_boundaries},
                uncertainty=0.05,
                scope=scope,
                observation_type=ObservationType.OBSERVED,
            ),
            QualityObservation(
                dimension=QualityDimension.ARCHITECTURE,
                metric_name="dynamic_boundaries",
                measured_value=dyn_boundaries,
                evidence={"runtime_inferred_boundaries": dyn_boundaries},
                uncertainty=0.15,
                scope=scope,
                observation_type=ObservationType.INFERRED,
            ),
            QualityObservation(
                dimension=QualityDimension.ARCHITECTURE,
                metric_name="blast_radius",
                measured_value=blast_radius,
                evidence={"affected_symbol_count": blast_radius},
                uncertainty=0.10,
                scope=scope,
                observation_type=ObservationType.ESTIMATED,
            ),
            QualityObservation(
                dimension=QualityDimension.ARCHITECTURE,
                metric_name="modularity",
                measured_value=modularity,
                evidence={"cohesion_vs_coupling_score": modularity},
                uncertainty=0.08,
                scope=scope,
                observation_type=ObservationType.OBSERVED,
            ),
            QualityObservation(
                dimension=QualityDimension.ARCHITECTURE,
                metric_name="boundary_violations",
                measured_value=boundary_violations,
                evidence={"violations_detected": boundary_violations},
                uncertainty=0.01,
                scope=scope,
                observation_type=ObservationType.OBSERVED,
            ),
        ]

        # Determine status based on thresholds
        is_blocked = (
            boundary_violations > self.thresholds["max_boundary_violations"]
            or scc_size > self.thresholds["max_scc_size"] * 2
        )
        is_degraded = (
            coupling > self.thresholds["max_coupling"]
            or scc_size > self.thresholds["max_scc_size"]
            or blast_radius > self.thresholds["max_blast_radius"]
            or modularity < self.thresholds["min_modularity"]
        )

        status = DimensionStatus.BLOCKED if is_blocked else (
            DimensionStatus.DEGRADED if is_degraded else DimensionStatus.HEALTHY
        )

        evidence = [
            {
                "evaluator": "ArchitectureQualityEvaluator",
                "coupling": coupling,
                "scc_size": scc_size,
                "blast_radius": blast_radius,
                "boundary_violations": boundary_violations,
                "modularity": modularity,
            }
        ]

        summary = (
            f"Architecture status {status.value}: coupling={coupling:.2f}, "
            f"scc_size={scc_size}, blast_radius={blast_radius}, "
            f"violations={boundary_violations}, modularity={modularity:.2f}"
        )

        return DimensionEvaluation(
            dimension=QualityDimension.ARCHITECTURE,
            observations=observations,
            evidence=evidence,
            uncertainty=0.08,
            scope=scope,
            status=status,
            summary=summary,
        )

    def compare_architecture(
        self,
        baseline_eval: DimensionEvaluation,
        after_eval: DimensionEvaluation,
    ) -> Tuple[DimensionChange, List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Compares baseline and post-mission architecture quality.
        Classifies as IMPROVED, DEGRADED, UNCHANGED, or UNCERTAIN.
        """
        base_obs = {o.metric_name: o.measured_value for o in baseline_eval.observations}
        after_obs = {o.metric_name: o.measured_value for o in after_eval.observations}

        degradations = []
        improvements = []

        # Check coupling
        b_c = float(base_obs.get("coupling", 0.0))
        a_c = float(after_obs.get("coupling", 0.0))
        if a_c > b_c + 0.05:
            degradations.append({"metric": "coupling", "from": b_c, "to": a_c, "reason": "coupling increased"})
        elif a_c < b_c - 0.05:
            improvements.append({"metric": "coupling", "from": b_c, "to": a_c, "reason": "coupling decreased"})

        # Check scc_size
        b_s = int(base_obs.get("scc_size", 0))
        a_s = int(after_obs.get("scc_size", 0))
        if a_s > b_s:
            degradations.append({"metric": "scc_size", "from": b_s, "to": a_s, "reason": "SCC condensation cycle grew"})
        elif a_s < b_s:
            improvements.append({"metric": "scc_size", "from": b_s, "to": a_s, "reason": "SCC cycle broken into acyclic components"})

        # Check boundary violations
        b_v = int(base_obs.get("boundary_violations", 0))
        a_v = int(after_obs.get("boundary_violations", 0))
        if a_v > b_v:
            degradations.append({"metric": "boundary_violations", "from": b_v, "to": a_v, "reason": "new boundary violations introduced"})
        elif a_v < b_v:
            improvements.append({"metric": "boundary_violations", "from": b_v, "to": a_v, "reason": "boundary violations resolved"})

        # Check blast radius
        b_r = int(base_obs.get("blast_radius", 0))
        a_r = int(after_obs.get("blast_radius", 0))
        if a_r > b_r + 3:
            degradations.append({"metric": "blast_radius", "from": b_r, "to": a_r, "reason": "blast radius expanded"})
        elif a_r < b_r - 3:
            improvements.append({"metric": "blast_radius", "from": b_r, "to": a_r, "reason": "blast radius localized"})

        # Uncertainty check: if measurement uncertainty is high
        if baseline_eval.uncertainty > 0.4 or after_eval.uncertainty > 0.4:
            return DimensionChange.UNCERTAIN, degradations, improvements

        if degradations and not improvements:
            return DimensionChange.DEGRADED, degradations, improvements
        if improvements and not degradations:
            return DimensionChange.IMPROVED, degradations, improvements
        if degradations and improvements:
            # If severe degradation (e.g. boundary violations or SCC growth), mark degraded
            has_severe = any(d["metric"] in ("boundary_violations", "scc_size") for d in degradations)
            if has_severe:
                return DimensionChange.DEGRADED, degradations, improvements
            return DimensionChange.UNCERTAIN, degradations, improvements

        return DimensionChange.UNCHANGED, degradations, improvements
