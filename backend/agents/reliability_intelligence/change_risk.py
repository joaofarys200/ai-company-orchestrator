"""
Phase 72 — Change Risk Assessment
Integrates self-modification safety (F65), quality governance (F68), debt (F69),
release readiness (F70), and production incident history (F71).
"""

from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional

from .models import (
    ChangeRiskAssessment,
    RiskLevel,
)


class ChangeRiskEvaluator:
    """Calculates risk score for proposed code or configuration changes."""

    def evaluate(
        self,
        change_id: str,
        changed_files: List[str],
        changed_symbols: List[str],
        contracts_affected: List[str],
        impacted_services: List[str],
        historical_incident_rate: float = 0.0,
        debt_score: float = 0.0,
        coupling_score: float = 0.0,
        prior_rollback: bool = False,
    ) -> ChangeRiskAssessment:
        evidence_id = f"ev_cr_{uuid.uuid4().hex[:8]}"

        if not changed_files and not changed_symbols and not contracts_affected:
            return ChangeRiskAssessment(
                assessment_id=f"cra_{uuid.uuid4().hex[:6]}",
                change_id=change_id,
                changed_files=[],
                changed_symbols=[],
                contracts_affected=[],
                impacted_services=impacted_services,
                historical_incident_rate=historical_incident_rate,
                debt_score=debt_score,
                coupling_score=coupling_score,
                risk_level=RiskLevel.INSUFFICIENT_EVIDENCE,
                evidence_id=evidence_id,
            )

        points = 0
        if len(changed_files) >= 10:
            points += 2
        elif len(changed_files) >= 4:
            points += 1

        if len(changed_symbols) >= 15:
            points += 2
        elif len(changed_symbols) >= 5:
            points += 1

        if len(contracts_affected) >= 2:
            points += 3
        elif len(contracts_affected) >= 1:
            points += 1

        if len(impacted_services) >= 3:
            points += 2

        if historical_incident_rate > 0.2:
            points += 2

        if debt_score > 50.0:
            points += 2
        elif debt_score > 20.0:
            points += 1

        if coupling_score > 0.7:
            points += 2

        if prior_rollback:
            points += 3

        if points >= 6:
            risk = RiskLevel.HIGH
        elif points >= 3:
            risk = RiskLevel.MEDIUM
        else:
            risk = RiskLevel.LOW

        return ChangeRiskAssessment(
            assessment_id=f"cra_{uuid.uuid4().hex[:6]}",
            change_id=change_id,
            changed_files=changed_files,
            changed_symbols=changed_symbols,
            contracts_affected=contracts_affected,
            impacted_services=impacted_services,
            historical_incident_rate=round(historical_incident_rate, 3),
            debt_score=round(debt_score, 2),
            coupling_score=round(coupling_score, 3),
            risk_level=risk,
            evidence_id=evidence_id,
        )
