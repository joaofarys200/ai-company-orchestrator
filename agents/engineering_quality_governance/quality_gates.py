"""
JARVIS OS — Phase 68: Quality Gate Engine
Enforces multi-dimensional gate decisions:
- QUALITY_ACCEPTED
- QUALITY_ACCEPTED_WITH_DEBT
- QUALITY_REVIEW_REQUIRED
- QUALITY_BLOCKED
- QUALITY_INCONCLUSIVE

Hard Invariant:
Never produce a simplistic 'quality_ok = True' boolean.
Every decision must explicitly provide:
scope, evidence, degradations, improvements, debt items, uncertainty, and policy.
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

from .models import (
    DebtSeverity,
    DimensionChange,
    QualityDelta,
    QualityGateDecision,
    QualityGateStatus,
    QualitySnapshot,
    TechnicalDebtItem,
)
from .quality_budget import QualityBudgetGovernor


class QualityGateEngine:
    """
    Evaluates system snapshots, deltas, and debt to produce nuanced QualityGateDecisions.
    """

    def __init__(self, budget_governor: Optional[QualityBudgetGovernor] = None) -> None:
        self.budget_governor = budget_governor or QualityBudgetGovernor()

    def evaluate_gate(
        self,
        snapshot: QualitySnapshot,
        delta: Optional[QualityDelta] = None,
        debt_items: Optional[List[TechnicalDebtItem]] = None,
        policy: Optional[Dict[str, Any]] = None,
        scope: str = "global",
    ) -> QualityGateDecision:
        pol = policy or {"policy_name": "GOVERNED", "strict_mode": False}
        debts = debt_items or []

        # 1. Compute uncertainty across dimensions
        uncertainties = [d.uncertainty for d in snapshot.dimensions.values()]
        mean_uncertainty = sum(uncertainties) / max(len(uncertainties), 1)

        # 2. Check for inconclusive data
        if mean_uncertainty > 0.45 or len(snapshot.dimensions) < 5:
            return QualityGateDecision(
                decision=QualityGateStatus.QUALITY_INCONCLUSIVE,
                scope=scope,
                evidence=[{"reason": "Insufficient dimensional evidence or excessive measurement uncertainty"}],
                degradations=[],
                improvements=[],
                debt=[d.to_dict() for d in debts],
                uncertainty=mean_uncertainty,
                policy=pol,
                timestamp=time.time(),
            )

        # 3. Collect degradations and improvements from delta
        degradations = delta.degradations if delta else []
        improvements = delta.improvements if delta else []

        # Check dimension evaluations in current snapshot
        critical_degradations = []
        for dim_name, dim_eval in snapshot.dimensions.items():
            if dim_eval.status.value == "BLOCKED":
                critical_degradations.append({
                    "dimension": dim_name,
                    "reason": f"Dimension {dim_name} is BLOCKED in snapshot",
                    "status": "BLOCKED",
                })

        # Check critical debts
        critical_debts = [d for d in debts if d.severity == DebtSeverity.CRITICAL]

        # 4. Check Budget Compliance
        metrics = {
            "unresolved_contract_drift": len([d for d in debts if d.category.value == "CONTRACT"]),
            "flaky_rate": 0.01,
            "regression_rate": len(degradations) / max(1, len(degradations) + len(improvements) + 10),
            "architecture_degradation_count": len([d for d in degradations if d.get("metric") in ("scc_size", "boundary_violations")]),
            "quality_uncertainty": mean_uncertainty,
            "human_review_backlog": 0,
        }
        is_compliant, violations, suggested_gate = self.budget_governor.check_budget_compliance(debts, metrics)

        # 5. Determine Decision
        if critical_debts or critical_degradations or suggested_gate == QualityGateStatus.QUALITY_BLOCKED:
            status = QualityGateStatus.QUALITY_BLOCKED
        elif suggested_gate == QualityGateStatus.QUALITY_REVIEW_REQUIRED or mean_uncertainty > 0.30:
            status = QualityGateStatus.QUALITY_REVIEW_REQUIRED
        elif debts:
            status = QualityGateStatus.QUALITY_ACCEPTED_WITH_DEBT
        else:
            status = QualityGateStatus.QUALITY_ACCEPTED

        evidence = [
            {"evaluator": "QualityGateEngine", "dimensions_evaluated": len(snapshot.dimensions)},
            {"budget_compliant": is_compliant, "budget_violations": violations},
        ]

        return QualityGateDecision(
            decision=status,
            scope=scope,
            evidence=evidence,
            degradations=degradations + critical_degradations,
            improvements=improvements,
            debt=[d.to_dict() for d in debts],
            uncertainty=mean_uncertainty,
            policy=pol,
            timestamp=time.time(),
        )
