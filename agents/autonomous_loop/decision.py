"""
JARVIS OS — Phase 40: Autonomous Engineering Loop & Closed-Loop Mission Adaptation
Deterministic Decision Engine & Causal Explainability.

Decisions are strictly deterministic, synthesized from:
ObservedState(t) + Prediction(t) + Evidence(t) + MissionIntent(t) -> Decision(t+1)
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import time
from typing import Any, Dict, List, Optional

from agents.autonomous_loop.models import (
    AdaptationBudget,
    AutonomousLoopState,
    CausalExplanation,
    DriftClassification,
    LoopDecisionType,
    LoopObservationOutcome,
    LoopSnapshot,
    OscillationStatus,
)
from agents.autonomous_loop.observation import LoopObservation
from agents.autonomous_loop.policy import (
    AutonomousDecisionPolicy,
    PolicyEvaluationContext,
    PolicyRuleDefinition,
)


@dataclass
class AutonomousDecisionResult:
    decision: LoopDecisionType
    causal_explanation: CausalExplanation
    rule_matched: str
    priority: int
    cycle_id: str
    mission_id: str
    timestamp: float = field(default_factory=time.time)
    context_summary: dict[str, Any] = field(default_factory=dict)
    evaluated_context: Optional[PolicyEvaluationContext] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision": self.decision.value if isinstance(self.decision, LoopDecisionType) else self.decision,
            "causal_explanation": self.causal_explanation.to_dict(),
            "rule_matched": self.rule_matched,
            "priority": self.priority,
            "cycle_id": self.cycle_id,
            "mission_id": self.mission_id,
            "timestamp": self.timestamp,
            "context_summary": self.context_summary,
        }


class AutonomousDecisionEngine:
    """
    Evaluates observed state against deterministic decision policies.
    """

    @classmethod
    def evaluate_decision(
        cls,
        mission_id: str,
        cycle_id: str,
        loop_state: AutonomousLoopState,
        budget: AdaptationBudget,
        observation: LoopObservation,
        snapshot: Optional[LoopSnapshot] = None,
        prediction_report: Optional[dict[str, Any]] = None,
        comparison_outcome: Optional[LoopObservationOutcome] = None,
        security_violation: bool = False,
        security_reason: str = "",
        economic_approval_required: bool = False,
        economic_reason: str = "",
        oscillation_status: OscillationStatus = OscillationStatus.NORMAL,
        oscillation_reason: str = "",
        drift_classification: DriftClassification = DriftClassification.NO_DRIFT,
        drift_reason: str = "",
        all_requirements_satisfied: bool = False,
        state_consistent: bool = True,
        plan_invalid: bool = False,
        plan_invalid_reason: str = "",
        task_owner_unavailable: bool = False,
        alternative_agent_available: bool = False,
        human_approval_required: bool = False,
        human_approval_reason: str = "",
    ) -> AutonomousDecisionResult:
        # Determine failure conditions from observation
        has_failures = bool(observation.active_failures)
        repairable = False
        failure_msg = ""
        if has_failures:
            # Check if any failure is marked as repairable
            repairable_failures = [f for f in observation.active_failures if f.get("is_repairable")]
            repairable = (len(repairable_failures) == len(observation.active_failures)) and not observation.has_unrepairable_failure
            failure_msg = "; ".join([str(f.get("error", "")) for f in observation.active_failures[:2]])

        # Determine prediction deviation
        prediction_dev = False
        deviation_msg = ""
        if comparison_outcome:
            if comparison_outcome.unexpected_changes:
                prediction_dev = True
                deviation_msg = f"Unexpected files: {len(comparison_outcome.unexpected_changes)} ({', '.join(comparison_outcome.unexpected_changes[:3])})"

        # Context assembly
        ctx = PolicyEvaluationContext(
            mission_id=mission_id,
            cycle_id=cycle_id,
            loop_state=loop_state,
            budget=budget,
            security_violation=security_violation,
            security_reason=security_reason,
            economic_approval_required=economic_approval_required,
            economic_reason=economic_reason,
            oscillation_status=oscillation_status,
            oscillation_reason=oscillation_reason,
            drift_classification=drift_classification,
            drift_reason=drift_reason,
            execution_success=observation.all_tasks_completed and not has_failures,
            all_requirements_satisfied=all_requirements_satisfied,
            required_validation_passed=observation.all_validations_passed,
            evidence_complete=bool(observation.evidence_ids_collected) or all_requirements_satisfied,
            state_consistent=state_consistent,
            no_active_blocks=not security_violation,
            active_failures=observation.active_failures,
            failure_is_repairable=repairable,
            failure_reason=failure_msg,
            plan_invalid_or_new_dependency=plan_invalid,
            plan_invalid_reason=plan_invalid_reason,
            prediction_deviation=prediction_dev,
            prediction_deviation_satisfiable=True,
            deviation_reason=deviation_msg,
            task_owner_unavailable=task_owner_unavailable,
            alternative_agent_available=alternative_agent_available,
            reassignment_reason="Task owner unresponsive in swarm heartbeat" if task_owner_unavailable else "",
            human_approval_required=human_approval_required,
            human_approval_reason=human_approval_reason,
        )

        decision, explanation, rule = AutonomousDecisionPolicy.evaluate(ctx)

        return AutonomousDecisionResult(
            decision=decision,
            causal_explanation=explanation,
            rule_matched=rule.rule_id,
            priority=rule.priority,
            cycle_id=cycle_id,
            mission_id=mission_id,
            context_summary={
                "has_failures": has_failures,
                "is_repairable": repairable,
                "prediction_deviation": prediction_dev,
                "requirements_satisfied": all_requirements_satisfied,
                "consecutive_failures": loop_state.consecutive_failures,
                "adaptation_count": loop_state.adaptation_count,
            },
            evaluated_context=ctx,
        )
