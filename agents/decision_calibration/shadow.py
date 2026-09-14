"""
JARVIS OS — Phase 41: Autonomous Decision Calibration & Failure Intelligence
Shadow Policy Engine: Dual-Policy Real-Time Comparative Evaluation.

Principles:
- ACTIVE policy executes operational decisions.
- SHADOW policy evaluates concurrently on identical inputs with ZERO operational side-effects.
- Discrepancies between active and shadow decisions are logged for calibration review.
"""

from __future__ import annotations

import time
from typing import Any, Callable, Dict, List, Optional, Tuple

from agents.autonomous_loop.models import LoopDecisionType
from agents.autonomous_loop.policy import PolicyEvaluationContext
from agents.decision_calibration.models import ShadowComparisonRecord


class ShadowPolicyEngine:
    """
    Coordinates side-by-side evaluation of an active policy and a candidate shadow policy.
    Ensures shadow evaluation remains strictly decoupled from execution.
    """

    def __init__(self, shadow_version: Optional[str] = None):
        self.shadow_version = shadow_version
        self.comparisons: list[ShadowComparisonRecord] = []

    def evaluate_shadow(
        self,
        cycle_id: str,
        active_version: str,
        active_decision: LoopDecisionType,
        ctx: PolicyEvaluationContext,
        shadow_eval_fn: Optional[Callable[[PolicyEvaluationContext], tuple[LoopDecisionType, Any, Any]]] = None,
    ) -> Optional[ShadowComparisonRecord]:
        if not self.shadow_version or shadow_eval_fn is None:
            return None

        # Execute shadow evaluation strictly in-memory
        shadow_dec, shadow_exp, shadow_rule = shadow_eval_fn(ctx)

        agreement = (active_decision == shadow_dec)
        disagreement_reason = ""
        if not agreement:
            rule_id = getattr(shadow_rule, "rule_id", str(shadow_rule))
            disagreement_reason = f"Active chose {active_decision.value}; Shadow chose {shadow_dec.value} via rule {rule_id}"

        record = ShadowComparisonRecord(
            comparison_id=f"shd_{cycle_id}_{int(time.time()*1000) % 10000}",
            cycle_id=cycle_id,
            active_policy_version=active_version,
            active_decision=active_decision,
            shadow_policy_version=self.shadow_version,
            shadow_decision=shadow_dec,
            agreement=agreement,
            disagreement_reason=disagreement_reason,
        )
        self.comparisons.append(record)
        return record

    def get_summary(self) -> dict[str, Any]:
        total = len(self.comparisons)
        agreements = sum(1 for c in self.comparisons if c.agreement)
        disagreements = total - agreements
        rate = round(agreements / total, 4) if total > 0 else 1.0

        return {
            "shadow_version": self.shadow_version,
            "total_comparisons": total,
            "agreements": agreements,
            "disagreements": disagreements,
            "agreement_rate": rate,
            "recent_disagreements": [
                c.to_dict() for c in self.comparisons if not c.agreement
            ][-5:],
        }
