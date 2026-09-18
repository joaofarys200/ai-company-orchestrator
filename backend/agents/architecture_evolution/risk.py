"""
JARVIS OS — Phase 64: Autonomous Architecture Evolution & Design Governance
Module: risk.py
Multi-dimensional risk vector analyzer across security, reliability, migration,
rollback, economic, operational, and data loss axes.

Rule:
    Never use a single aggregated scalar to mask underlying domain risks.
"""

from __future__ import annotations

from typing import Dict

from .models import (
    AlternativeType,
    ArchitectureAlternative,
    ArchitectureSnapshot,
    ContractBreakStatus,
    ReversibilityStatus,
    RiskAnalysisResult,
    RiskCriticality,
)


class ArchitectureRiskAnalyzer:
    """Evaluates multi-axis risk profiles for candidate architectural changes."""

    def analyze_risk(
        self,
        alternative: ArchitectureAlternative,
        snapshot: ArchitectureSnapshot,
        contract_status: ContractBreakStatus = ContractBreakStatus.NON_BREAKING,
    ) -> RiskAnalysisResult:
        alt_type = alternative.alternative_type

        # 1. Baseline: keep_current
        if alt_type == AlternativeType.KEEP_CURRENT:
            risk_vector = {
                "security": 0.05,
                "reliability": 0.15,
                "migration": 0.0,
                "rollback": 0.0,
                "economic": 0.0,
                "operational": 0.10,
                "data_loss": 0.0,
                "contract": 0.0,
            }
            uncertainty_vector = {k: 0.05 for k in risk_vector}
            return RiskAnalysisResult(
                alternative_id=alternative.alternative_id,
                security_risk=0.05,
                reliability_risk=0.15,
                migration_risk=0.0,
                rollback_risk=0.0,
                economic_risk=0.0,
                operational_risk=0.10,
                data_loss_risk=0.0,
                contract_risk=0.0,
                risk_vector=risk_vector,
                uncertainty_vector=uncertainty_vector,
                criticality=RiskCriticality.LOW,
            )

        # 2. Risk vector components
        sec_risk = 0.10
        if any(z in str(alternative.affected_components) for z in snapshot.risk_zones):
            sec_risk = 0.45

        rel_risk = 0.20
        if alt_type == AlternativeType.EVENT_DRIVEN:
            rel_risk = 0.50

        mig_risk = 0.30 if alternative.migration_complexity == "HIGH" else 0.15
        if alt_type == AlternativeType.SERVICE_SPLIT:
            mig_risk = 0.65

        roll_risk = 0.10
        if alternative.reversibility == ReversibilityStatus.DIFFICULT_TO_REVERSE:
            roll_risk = 0.60
        elif alternative.reversibility == ReversibilityStatus.IRREVERSIBLE:
            roll_risk = 0.95

        econ_risk = 0.15
        op_risk = 0.25 if alt_type in [AlternativeType.EVENT_DRIVEN, AlternativeType.SERVICE_SPLIT] else 0.10
        data_risk = 0.35 if alt_type == AlternativeType.DATA_BOUNDARY else 0.05

        contr_risk = 0.10
        if contract_status == ContractBreakStatus.BREAKING:
            contr_risk = 0.85
        elif contract_status == ContractBreakStatus.POTENTIALLY_BREAKING:
            contr_risk = 0.45

        risk_vector = {
            "security": sec_risk,
            "reliability": rel_risk,
            "migration": mig_risk,
            "rollback": roll_risk,
            "economic": econ_risk,
            "operational": op_risk,
            "data_loss": data_risk,
            "contract": contr_risk,
        }

        uncertainty_vector = {
            "security": 0.15 if sec_risk > 0.3 else 0.05,
            "reliability": 0.20 if alt_type == AlternativeType.EVENT_DRIVEN else 0.08,
            "migration": 0.15,
            "rollback": 0.10,
            "economic": 0.10,
            "operational": 0.15,
            "data_loss": 0.10,
            "contract": 0.12,
        }

        # Determine Criticality
        max_risk = max(risk_vector.values())
        if max_risk >= 0.80 or roll_risk >= 0.80 or sec_risk >= 0.80:
            crit = RiskCriticality.CRITICAL
        elif max_risk >= 0.50:
            crit = RiskCriticality.HIGH
        elif max_risk >= 0.25:
            crit = RiskCriticality.MEDIUM
        else:
            crit = RiskCriticality.LOW

        return RiskAnalysisResult(
            alternative_id=alternative.alternative_id,
            security_risk=sec_risk,
            reliability_risk=rel_risk,
            migration_risk=mig_risk,
            rollback_risk=roll_risk,
            economic_risk=econ_risk,
            operational_risk=op_risk,
            data_loss_risk=data_risk,
            contract_risk=contr_risk,
            risk_vector=risk_vector,
            uncertainty_vector=uncertainty_vector,
            criticality=crit,
        )
