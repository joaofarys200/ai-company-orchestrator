"""
JARVIS OS — Phase 69: Autonomous Quality Debt Remediation
Risk assessment engine. Evaluates operational blast radius, regression hazard, and reversibility.
"""

from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List


@dataclass
class RemediationRiskReport:
    report_id: str
    debt_id: str
    operational_risk: float  # 0.0 to 1.0
    blast_radius_files: int
    reversibility_score: float  # 1.0 = fully reversible (git revert), 0.0 = irreversible
    regression_hazard: float  # 0.0 to 1.0
    safe_for_autonomous_execution: bool
    risk_factors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class DebtRiskEvaluator:
    """
    Computes composite risk metrics for proposed remediation operations.
    """

    def evaluate_risk(
        self,
        debt_id: str,
        affected_files: List[str],
        is_security_sensitive: bool = False,
        has_database_schema_migration: bool = False,
        test_coverage: float = 0.85,
    ) -> RemediationRiskReport:
        report_id = f"risk_{uuid.uuid4().hex[:8]}"
        risk_factors = []
        operational_risk = 0.1

        # File count impact
        file_count = len(affected_files)
        if file_count > 10:
            operational_risk += 0.4
            risk_factors.append(f"Large surface area ({file_count} files)")
        elif file_count > 3:
            operational_risk += 0.2
            risk_factors.append(f"Moderate surface area ({file_count} files)")

        # Security sensitivity
        if is_security_sensitive:
            operational_risk += 0.3
            risk_factors.append("Security-sensitive boundary touched")

        # Database / state migrations
        reversibility = 1.0
        if has_database_schema_migration:
            operational_risk += 0.3
            reversibility = 0.4
            risk_factors.append("Database schema migration carries rollback complexity")

        # Regression hazard inversely proportional to test coverage
        regression_hazard = max(0.05, 1.0 - test_coverage)
        if regression_hazard > 0.4:
            risk_factors.append(f"Low test coverage ({test_coverage * 100:.0f}%) increases regression hazard")

        operational_risk = min(1.0, operational_risk + (regression_hazard * 0.3))
        safe = (operational_risk <= 0.65) and (reversibility >= 0.5)

        return RemediationRiskReport(
            report_id=report_id,
            debt_id=debt_id,
            operational_risk=round(operational_risk, 3),
            blast_radius_files=file_count,
            reversibility_score=round(reversibility, 3),
            regression_hazard=round(regression_hazard, 3),
            safe_for_autonomous_execution=safe,
            risk_factors=risk_factors,
        )
