"""
Release Risk Model Module
Phase 70 — Autonomous Release Readiness & Production Governance

Builds the 11-dimensional release risk vector with epistemic confidence ratings.
Crucial invariant: Never reduces risk vector solely to a single scalar without dimension detail.
"""

from __future__ import annotations
from typing import Dict, Any, Optional
from .models import ReleaseRiskVector, RiskVectorItem, RiskDimension


class ReleaseRiskModel:
    """Calculates multi-dimensional risk vectors across all release boundaries."""

    @classmethod
    def calculate_vector(
        cls,
        security_summary: Dict[str, Any],
        quality_summary: Dict[str, Any],
        architecture_summary: Dict[str, Any],
        behavior_summary: Dict[str, Any],
        contract_summary: Dict[str, Any],
        performance_summary: Dict[str, Any],
        runtime_summary: Dict[str, Any],
        configuration_summary: Dict[str, Any],
        dependency_summary: Dict[str, Any],
        rollback_summary: Dict[str, Any],
        observability_summary: Dict[str, Any]
    ) -> ReleaseRiskVector:
        """
        Builds the 11-dimensional release risk vector.
        Each dimension has: value (0.0 safe - 1.0 risky), confidence (0.0 - 1.0), evidence.
        """
        dimensions: Dict[str, RiskVectorItem] = {}

        # 1. Security
        sec_blockers = len(security_summary.get("blockers", []))
        sec_val = 0.95 if sec_blockers > 0 else (0.4 if security_summary.get("security_debt_count", 0) > 0 else 0.05)
        dimensions[RiskDimension.SECURITY.value] = RiskVectorItem(
            dimension=RiskDimension.SECURITY.value,
            value=sec_val,
            confidence=0.95,
            evidence=f"Blockers: {sec_blockers}, Debt: {security_summary.get('security_debt_count', 0)}"
        )

        # 2. Quality
        qual_blockers = len(quality_summary.get("blockers", []))
        qual_val = 0.90 if qual_blockers > 0 else (1.0 - quality_summary.get("overall_score", 0.95))
        dimensions[RiskDimension.QUALITY.value] = RiskVectorItem(
            dimension=RiskDimension.QUALITY.value,
            value=max(0.05, qual_val),
            confidence=1.0 - quality_summary.get("uncertainty", 0.05),
            evidence=f"Score: {quality_summary.get('overall_score', 0.95):.2f}, Uncertainty: {quality_summary.get('uncertainty', 0.05):.2f}"
        )

        # 3. Architecture
        arch_blockers = len(architecture_summary.get("blockers", []))
        arch_val = 0.90 if arch_blockers > 0 else (0.35 if architecture_summary.get("requires_human_review") else 0.08)
        dimensions[RiskDimension.ARCHITECTURE.value] = RiskVectorItem(
            dimension=RiskDimension.ARCHITECTURE.value,
            value=arch_val,
            confidence=0.90,
            evidence=f"Status: {architecture_summary.get('classification', 'HEALTHY')}, SCCs: {architecture_summary.get('unresolved_sccs', 0)}"
        )

        # 4. Behavior
        beh_blockers = len(behavior_summary.get("blockers", []))
        beh_val = 0.95 if beh_blockers > 0 else (0.45 if behavior_summary.get("potential_drift") else 0.05)
        dimensions[RiskDimension.BEHAVIOR.value] = RiskVectorItem(
            dimension=RiskDimension.BEHAVIOR.value,
            value=beh_val,
            confidence=0.85 if behavior_summary.get("evidence_depth") != "INSUFFICIENT" else 0.40,
            evidence=f"Status: {behavior_summary.get('status', 'PRESERVED')}, Invariants violated: {behavior_summary.get('invariants_violated', 0)}"
        )

        # 5. Contract
        con_blockers = len(contract_summary.get("blockers", []))
        con_val = 0.95 if con_blockers > 0 else (0.40 if contract_summary.get("requires_human_review") else 0.05)
        dimensions[RiskDimension.CONTRACT.value] = RiskVectorItem(
            dimension=RiskDimension.CONTRACT.value,
            value=con_val,
            confidence=0.92,
            evidence=f"Status: {contract_summary.get('status', 'COMPATIBLE')}, Breaking: {contract_summary.get('breaking_changes', 0)}"
        )

        # 6. Performance
        perf_blockers = len(performance_summary.get("blockers", []))
        perf_val = 0.90 if perf_blockers > 0 else (0.45 if performance_summary.get("requires_human_review") else 0.10)
        perf_conf = 0.95 if performance_summary.get("nature") == "observed" else 0.60
        dimensions[RiskDimension.PERFORMANCE.value] = RiskVectorItem(
            dimension=RiskDimension.PERFORMANCE.value,
            value=perf_val,
            confidence=perf_conf,
            evidence=f"Classification: {performance_summary.get('classification', 'WITHIN_BUDGET')}, Nature: {performance_summary.get('nature', 'observed')}"
        )

        # 7. Runtime
        rt_blockers = len(runtime_summary.get("blockers", []))
        rt_val = 0.95 if rt_blockers > 0 else (0.35 if runtime_summary.get("requires_human_review") else 0.05)
        dimensions[RiskDimension.RUNTIME.value] = RiskVectorItem(
            dimension=RiskDimension.RUNTIME.value,
            value=rt_val,
            confidence=0.90,
            evidence=f"Status: {runtime_summary.get('status', 'HEALTHY')}, Blockers: {rt_blockers}"
        )

        # 8. Configuration
        cfg_blockers = len(configuration_summary.get("blockers", []))
        cfg_val = 0.95 if cfg_blockers > 0 else (0.30 if configuration_summary.get("requires_human_review") else 0.05)
        dimensions[RiskDimension.CONFIGURATION.value] = RiskVectorItem(
            dimension=RiskDimension.CONFIGURATION.value,
            value=cfg_val,
            confidence=0.95,
            evidence=f"Status: {configuration_summary.get('status', 'READY')}, Unsafe defaults: {configuration_summary.get('unsafe_defaults', False)}"
        )

        # 9. Dependency
        dep_blockers = len(dependency_summary.get("blockers", []))
        dep_val = 0.90 if dep_blockers > 0 else (0.30 if dependency_summary.get("unpinned_count", 0) > 0 else 0.05)
        dimensions[RiskDimension.DEPENDENCY.value] = RiskVectorItem(
            dimension=RiskDimension.DEPENDENCY.value,
            value=dep_val,
            confidence=0.92,
            evidence=f"Status: {dependency_summary.get('status', 'READY')}, Unpinned: {dependency_summary.get('unpinned_count', 0)}"
        )

        # 10. Rollback
        rb_blockers = len(rollback_summary.get("blockers", []))
        rb_val = 0.95 if rb_blockers > 0 else (0.40 if rollback_summary.get("requires_human_review") else 0.05)
        dimensions[RiskDimension.ROLLBACK.value] = RiskVectorItem(
            dimension=RiskDimension.ROLLBACK.value,
            value=rb_val,
            confidence=0.90,
            evidence=f"Status: {rollback_summary.get('status', 'ROLLBACK_READY')}, Checkpoint verified: {rollback_summary.get('checkpoint_verified', True)}"
        )

        # 11. Observability
        obs_blockers = len(observability_summary.get("blockers", []))
        obs_val = 0.90 if obs_blockers > 0 else (0.40 if observability_summary.get("status") == "PARTIAL" else 0.08)
        dimensions[RiskDimension.OBSERVABILITY.value] = RiskVectorItem(
            dimension=RiskDimension.OBSERVABILITY.value,
            value=obs_val,
            confidence=0.88,
            evidence=f"Status: {observability_summary.get('status', 'READY')}, Signals: {observability_summary.get('signals_present', 7)}/7"
        )

        # Composite overall risk (optional auxiliary metric, non-mandatory)
        avg_risk = sum(item.value for item in dimensions.values()) / len(dimensions)

        return ReleaseRiskVector(
            dimensions=dimensions,
            overall_risk_score=round(avg_risk, 4)
        )
