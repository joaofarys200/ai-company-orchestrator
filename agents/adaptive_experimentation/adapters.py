"""
JARVIS OS — Phase 79: Autonomous Adaptive Experimentation & Scientific Hypothesis Validation
Module: adapters.py
Subsystem adapters connecting adaptive experimentation to Phases 75, 77, and 78.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from .models import ScientificHypothesis


class Phase78CausalHypothesisAdapter:
    """Adapts Phase 78 CausalHypothesis objects into ScientificHypothesis models."""

    @staticmethod
    def adapt_causal_hypotheses(causal_hypotheses: List[Any]) -> List[ScientificHypothesis]:
        """Convert a list of Phase 78 CausalHypothesis into normalized ScientificHypothesis instances."""
        if not causal_hypotheses:
            return []

        raw_confidences = [max(0.05, getattr(h, "confidence", 0.5)) for h in causal_hypotheses]
        total = sum(raw_confidences)

        scientific = []
        for h, raw_c in zip(causal_hypotheses, raw_confidences):
            norm_prior = round(raw_c / total, 4)
            s_hyp = ScientificHypothesis(
                hypothesis_id=getattr(h, "hypothesis_id", "hyp_unknown"),
                statement=getattr(h, "title", "Hypothesis"),
                prior_probability=norm_prior,
                posterior_probability=norm_prior,
                evidence_refs=list(getattr(h, "supporting_evidence", [])),
                status=getattr(h, "status", "CANDIDATE"),
            )
            scientific.append(s_hyp)

        return scientific


class Phase75BudgetAdapter:
    """Adapts Phase 75 portfolio capacity and budget limits into investigation cost budgets."""

    @staticmethod
    def derive_cost_budget(portfolio_metrics: Optional[Dict[str, Any]] = None) -> float:
        """Derives a normalized cost budget from Phase 75 metrics."""
        if not portfolio_metrics:
            return 1.0  # Default normalized budget
        remaining_budget = portfolio_metrics.get("remaining_budget", 1.0)
        return max(0.2, min(5.0, float(remaining_budget)))
