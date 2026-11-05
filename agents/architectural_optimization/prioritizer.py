"""
JARVIS OS — Phase 74: Autonomous Architectural Evolution & Optimization
Module: prioritizer.py
Selects and authorizes optimization decisions based on Pareto ranking,
empirical experiment outcomes, and governance constraints.
"""

from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional, Tuple

from .models import (
    ArchitecturalAlternative,
    ExperimentOutcome,
    ExperimentRecord,
    OptimizationDecision,
    OptimizationOpportunity,
    ParetoEvaluation,
)


class OptimizationPrioritizer:
    """
    Combines Pareto ranking with empirical experiment validation to produce
    a definitive, governed optimization decision.
    """

    def decide_optimization(
        self,
        opportunity: OptimizationOpportunity,
        alternatives: List[ArchitecturalAlternative],
        pareto_eval: ParetoEvaluation,
        experiments: Dict[str, ExperimentRecord],  # alt_id -> ExperimentRecord
        human_approval_token: Optional[str] = None,
    ) -> OptimizationDecision:
        """
        Determines the winning alternative that is BOTH Pareto-ranked AND empirically confirmed.
        Enforces human approval boundary on security-sensitive or high-risk optimizations.
        """
        dec_id = f"dec_{uuid.uuid4().hex[:8]}"
        rejection_reasons: List[str] = []
        alts_by_id = {alt.alternative_id: alt for alt in alternatives}

        # 1. Iterate through Pareto-ranked alternatives in order
        selected_alt: Optional[ArchitecturalAlternative] = None
        for alt_id in pareto_eval.ranked_alternatives:
            exp = experiments.get(alt_id)
            if not exp:
                rejection_reasons.append(f"Alternative '{alt_id}' was not empirically benchmarked.")
                continue

            if exp.outcome == ExperimentOutcome.REGRESSION_DETECTED:
                rejection_reasons.append(
                    f"Alternative '{alt_id}' rejected due to empirical regression: {exp.summary}"
                )
                continue

            if exp.outcome == ExperimentOutcome.NO_MEASURABLE_IMPROVEMENT:
                rejection_reasons.append(
                    f"Alternative '{alt_id}' rejected because benchmark showed no measurable improvement: {exp.summary}"
                )
                continue

            if exp.outcome == ExperimentOutcome.IMPROVEMENT_CONFIRMED:
                selected_alt = alts_by_id.get(alt_id)
                break

        if not selected_alt:
            return OptimizationDecision(
                decision_id=dec_id,
                opportunity_id=opportunity.opportunity_id,
                selected_alternative_id=None,
                governance_authorized=False,
                requires_human_approval=False,
                rationale="No candidate alternative demonstrated confirmed empirical improvement without regression.",
                rejection_reasons=rejection_reasons,
            )

        # 2. Check Governance & Security Gating
        requires_human_approval = (
            selected_alt.is_security_sensitive
            or selected_alt.regression_risk_score >= 0.4
            or opportunity.metadata.get("is_security_sensitive", False)
        )

        if requires_human_approval:
            if not human_approval_token:
                return OptimizationDecision(
                    decision_id=dec_id,
                    opportunity_id=opportunity.opportunity_id,
                    selected_alternative_id=selected_alt.alternative_id,
                    governance_authorized=False,
                    requires_human_approval=True,
                    human_approval_token=None,
                    rationale=(
                        f"Alternative '{selected_alt.alternative_id}' confirmed by benchmark, "
                        f"but requires human approval token due to security/risk profile."
                    ),
                    rejection_reasons=rejection_reasons,
                )
            else:
                return OptimizationDecision(
                    decision_id=dec_id,
                    opportunity_id=opportunity.opportunity_id,
                    selected_alternative_id=selected_alt.alternative_id,
                    governance_authorized=True,
                    requires_human_approval=True,
                    human_approval_token=human_approval_token,
                    rationale=f"Alternative '{selected_alt.alternative_id}' approved with valid human authorization token.",
                    rejection_reasons=rejection_reasons,
                )

        # Fully autonomous low-risk authorized decision
        return OptimizationDecision(
            decision_id=dec_id,
            opportunity_id=opportunity.opportunity_id,
            selected_alternative_id=selected_alt.alternative_id,
            governance_authorized=True,
            requires_human_approval=False,
            rationale=f"Alternative '{selected_alt.alternative_id}' empirically confirmed and within autonomous authorization boundaries.",
            rejection_reasons=rejection_reasons,
        )
