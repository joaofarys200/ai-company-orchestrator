"""
JARVIS OS — Phase 64: Autonomous Architecture Evolution & Design Governance
Module: cost.py
Multi-dimensional architecture cost estimation model with explicit epistemic status.

Rule:
    Never present an estimated figure as an observed fact.
    Classifications: OBSERVED, ESTIMATED, INFERRED.
"""

from __future__ import annotations

from typing import Dict

from .models import (
    AlternativeType,
    ArchitectureAlternative,
    ArchitectureSnapshot,
    CostCategory,
    CostEstimationResult,
    CostObservationStatus,
)


class ArchitectureCostModel:
    """Estimates implementation, migration, testing, and operational costs."""

    def estimate_cost(
        self,
        alternative: ArchitectureAlternative,
        snapshot: ArchitectureSnapshot,
    ) -> CostEstimationResult:
        alt_type = alternative.alternative_type

        # 1. Baseline: keep_current
        if alt_type == AlternativeType.KEEP_CURRENT:
            costs = {
                CostCategory.IMPLEMENTATION.value: 0.0,
                CostCategory.MIGRATION.value: 0.0,
                CostCategory.TESTING.value: 1.0,
                CostCategory.RUNTIME.value: 0.0,
                CostCategory.OPERATIONAL.value: 2.0,
                CostCategory.ROLLBACK.value: 0.0,
                CostCategory.MAINTENANCE.value: 8.0,  # Technical debt drag
            }
            return CostEstimationResult(
                alternative_id=alternative.alternative_id,
                costs=costs,
                observation_status=CostObservationStatus.ESTIMATED,
                total_estimated_effort_hours=11.0,
                currency_budget=0.0,
            )

        # 2. Refactoring alternatives
        base_hours = len(alternative.affected_components) * 6.0
        if alt_type in [AlternativeType.EVENT_DRIVEN, AlternativeType.SERVICE_SPLIT]:
            base_hours *= 2.5
        elif alt_type in [AlternativeType.FACADE, AlternativeType.ADAPTER_LAYER]:
            base_hours *= 0.8

        impl_cost = round(base_hours, 1)
        migr_cost = round(base_hours * 0.4, 1)
        test_cost = round(base_hours * 0.5, 1)
        runt_cost = 2.0 if alt_type == AlternativeType.ADAPTER_LAYER else 0.5
        oper_cost = round(base_hours * 0.2, 1)
        roll_cost = round(base_hours * 0.3, 1)
        maint_cost = round(base_hours * 0.15, 1)

        costs = {
            CostCategory.IMPLEMENTATION.value: impl_cost,
            CostCategory.MIGRATION.value: migr_cost,
            CostCategory.TESTING.value: test_cost,
            CostCategory.RUNTIME.value: runt_cost,
            CostCategory.OPERATIONAL.value: oper_cost,
            CostCategory.ROLLBACK.value: roll_cost,
            CostCategory.MAINTENANCE.value: maint_cost,
        }

        total_hours = sum(costs.values())

        return CostEstimationResult(
            alternative_id=alternative.alternative_id,
            costs=costs,
            observation_status=CostObservationStatus.ESTIMATED,
            total_estimated_effort_hours=round(total_hours, 1),
            currency_budget=round(total_hours * 85.0, 2),  # Inferred engineering rate
        )
