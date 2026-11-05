"""
JARVIS OS — Phase 74: Autonomous Architectural Evolution & Optimization
Module: opportunity_detector.py
Discovers architectural optimization opportunities using multi-source evidence
(dependency topology, test latencies, and reliability telemetry).
"""

from __future__ import annotations

import time
import uuid
from typing import Any, Dict, List, Optional, Tuple

from .models import (
    ArchitecturalMetricSnapshot,
    InsufficientEvidenceError,
    OpportunityCategory,
    OptimizationOpportunity,
)


class OpportunityDetector:
    """
    Detects actionable architectural optimization opportunities grounded in
    empirical evidence rather than superficial complexity metrics.
    """

    def __init__(self, min_sample_count: int = 3, min_confidence: float = 0.6):
        self.min_sample_count = min_sample_count
        self.min_confidence = min_confidence

    def analyze_system(
        self,
        dependency_graph: Dict[str, List[str]],
        execution_latencies: Optional[Dict[str, List[float]]] = None,
        failure_clusters: Optional[Dict[str, int]] = None,
        known_constraints: Optional[Dict[str, Any]] = None,
    ) -> List[OptimizationOpportunity]:
        """
        Synthesizes multi-source telemetry to identify genuine architectural bottlenecks.
        """
        opportunities: List[OptimizationOpportunity] = []
        latencies = execution_latencies or {}
        failures = failure_clusters or {}

        # 1. Detect Excessive Coupling / Dependency Concentration
        # Look for central modules with excessive fan-in (> 8) combined with high latency
        for node, dependents in dependency_graph.items():
            fan_in = len(dependents)
            if fan_in >= 5:
                # Check latency telemetry if available
                node_latencies = latencies.get(node, [])
                if len(node_latencies) < self.min_sample_count and not node_latencies:
                    # Lack of telemetry is noted, but high coupling alone is evaluated conservatively
                    confidence = 0.5
                else:
                    confidence = 0.85

                avg_latency = (
                    sum(node_latencies) / len(node_latencies)
                    if node_latencies
                    else 50.0  # nominal
                )

                if fan_in >= 8 or (fan_in >= 5 and avg_latency >= 100.0):
                    opp_id = f"opp_coupling_{uuid.uuid4().hex[:8]}"
                    baseline = {
                        "coupling_ratio": ArchitecturalMetricSnapshot(
                            metric_name="coupling_ratio",
                            value=round(fan_in / max(1, len(dependency_graph)), 3),
                            sample_count=len(dependency_graph),
                            unit="ratio",
                        ),
                        "execution_latency_ms": ArchitecturalMetricSnapshot(
                            metric_name="execution_latency_ms",
                            value=round(avg_latency, 2),
                            sample_count=len(node_latencies) if node_latencies else 1,
                            unit="ms",
                        ),
                    }
                    evidence = [
                        f"Component '{node}' has high fan-in ({fan_in} direct dependents).",
                        f"Mean execution latency: {avg_latency:.1f}ms across {len(node_latencies)} observations.",
                    ]

                    opp = OptimizationOpportunity(
                        opportunity_id=opp_id,
                        title=f"Decouple central dependency bottleneck in '{node}'",
                        category=OpportunityCategory.DEPENDENCY_CONCENTRATION,
                        affected_components=[node] + dependents[:5],
                        supporting_evidence=evidence,
                        baseline_metrics=baseline,
                        severity_score=round(min(1.0, 0.4 + (fan_in * 0.05)), 2),
                        confidence_score=confidence,
                    )
                    opportunities.append(opp)

        # 2. Detect Failure Propagation Clusters
        for node, fail_count in failures.items():
            if fail_count >= self.min_sample_count:
                dependents = dependency_graph.get(node, [])
                opp_id = f"opp_fail_{uuid.uuid4().hex[:8]}"
                baseline = {
                    "incident_count": ArchitecturalMetricSnapshot(
                        metric_name="incident_count",
                        value=float(fail_count),
                        sample_count=fail_count,
                        unit="count",
                    )
                }
                evidence = [
                    f"Component '{node}' has experienced {fail_count} correlated failures.",
                    f"Affects {len(dependents)} downstream dependent modules.",
                ]
                opp = OptimizationOpportunity(
                    opportunity_id=opp_id,
                    title=f"Isolate failure propagation boundary for '{node}'",
                    category=OpportunityCategory.FAILURE_PROPAGATION_CLUSTER,
                    affected_components=[node] + dependents[:3],
                    supporting_evidence=evidence,
                    baseline_metrics=baseline,
                    severity_score=0.8,
                    confidence_score=0.9,
                )
                opportunities.append(opp)

        return opportunities

    def validate_evidence_sufficiency(self, opportunity: OptimizationOpportunity) -> Tuple[bool, str]:
        """
        Validates that an opportunity meets epistemic rigor standards.
        Rejects proposals based on insufficient samples or low confidence.
        """
        if opportunity.confidence_score < self.min_confidence:
            return False, f"Opportunity confidence {opportunity.confidence_score:.2f} is below minimum {self.min_confidence:.2f}."

        for metric_name, snapshot in opportunity.baseline_metrics.items():
            if snapshot.sample_count < self.min_sample_count:
                return False, f"Metric '{metric_name}' has only {snapshot.sample_count} samples (minimum required: {self.min_sample_count})."

        return True, "Evidence is sufficient and validated."
