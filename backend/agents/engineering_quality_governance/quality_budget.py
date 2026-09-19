"""
JARVIS OS — Phase 68: Quality Budget Governor
Defines and enforces limits for:
- maximum critical debt
- maximum unresolved contract drift
- maximum security debt
- maximum flaky rate
- maximum regression rate
- maximum architecture degradation
- maximum quality uncertainty
- maximum human review backlog

When a limit is breached:
Triggers QUALITY_GATE -> BLOCKED or HUMAN_REVIEW according to policy.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from .models import (
    DebtCategory,
    DebtSeverity,
    QualityBudget,
    QualityGateStatus,
    TechnicalDebtItem,
)


class QualityBudgetGovernor:
    """
    Enforces quality budget limits over snapshots, debt items, and mission metrics.
    """

    def __init__(self, budget: Optional[QualityBudget] = None) -> None:
        self.budget = budget or QualityBudget()

    def check_budget_compliance(
        self,
        debt_items: List[TechnicalDebtItem],
        metrics: Dict[str, Any],
    ) -> Tuple[bool, List[Dict[str, Any]], Optional[QualityGateStatus]]:
        """
        Evaluates current metrics and debt against the QualityBudget.
        Returns:
            (is_compliant, violations, suggested_gate_status)
        """
        violations: List[Dict[str, Any]] = []

        # 1. Critical Debt Check
        critical_debts = [d for d in debt_items if d.severity == DebtSeverity.CRITICAL]
        if len(critical_debts) > self.budget.max_critical_debt:
            violations.append({
                "limit": "max_critical_debt",
                "budget": self.budget.max_critical_debt,
                "actual": len(critical_debts),
                "severity": "CRITICAL",
                "recommended_action": "BLOCK",
            })

        # 2. Security Debt Check
        security_debts = [d for d in debt_items if d.category == DebtCategory.SECURITY]
        if len(security_debts) > self.budget.max_security_debt:
            violations.append({
                "limit": "max_security_debt",
                "budget": self.budget.max_security_debt,
                "actual": len(security_debts),
                "severity": "CRITICAL",
                "recommended_action": "BLOCK",
            })

        # 3. Contract Drift Check
        contract_drift_count = int(metrics.get("unresolved_contract_drift", 0))
        if contract_drift_count > self.budget.max_unresolved_contract_drift:
            violations.append({
                "limit": "max_unresolved_contract_drift",
                "budget": self.budget.max_unresolved_contract_drift,
                "actual": contract_drift_count,
                "severity": "HIGH",
                "recommended_action": "BLOCK",
            })

        # 4. Flaky Rate Check
        flaky_rate = float(metrics.get("flaky_rate", 0.0))
        if flaky_rate > self.budget.max_flaky_rate:
            violations.append({
                "limit": "max_flaky_rate",
                "budget": self.budget.max_flaky_rate,
                "actual": flaky_rate,
                "severity": "MEDIUM",
                "recommended_action": "HUMAN_REVIEW",
            })

        # 5. Regression Rate Check
        regression_rate = float(metrics.get("regression_rate", 0.0))
        if regression_rate > self.budget.max_regression_rate:
            violations.append({
                "limit": "max_regression_rate",
                "budget": self.budget.max_regression_rate,
                "actual": regression_rate,
                "severity": "HIGH",
                "recommended_action": "BLOCK",
            })

        # 6. Architecture Degradation Check
        arch_degradations = int(metrics.get("architecture_degradation_count", 0))
        if arch_degradations > self.budget.max_architecture_degradation:
            violations.append({
                "limit": "max_architecture_degradation",
                "budget": self.budget.max_architecture_degradation,
                "actual": arch_degradations,
                "severity": "HIGH",
                "recommended_action": "BLOCK",
            })

        # 7. Quality Uncertainty Check
        uncertainty = float(metrics.get("quality_uncertainty", 0.0))
        if uncertainty > self.budget.max_quality_uncertainty:
            violations.append({
                "limit": "max_quality_uncertainty",
                "budget": self.budget.max_quality_uncertainty,
                "actual": uncertainty,
                "severity": "MEDIUM",
                "recommended_action": "HUMAN_REVIEW",
            })

        # 8. Human Review Backlog Check
        review_backlog = int(metrics.get("human_review_backlog", 0))
        if review_backlog > self.budget.max_human_review_backlog:
            violations.append({
                "limit": "max_human_review_backlog",
                "budget": self.budget.max_human_review_backlog,
                "actual": review_backlog,
                "severity": "MEDIUM",
                "recommended_action": "HUMAN_REVIEW",
            })

        if not violations:
            return True, [], None

        # Determine gate status based on worst violation
        has_critical_or_block = any(v["recommended_action"] == "BLOCK" for v in violations)
        suggested_gate = QualityGateStatus.QUALITY_BLOCKED if has_critical_or_block else QualityGateStatus.QUALITY_REVIEW_REQUIRED

        return False, violations, suggested_gate
