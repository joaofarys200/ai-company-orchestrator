"""
JARVIS OS — Phase 41: Autonomous Decision Calibration & Failure Intelligence
Historical Decision Replay Engine: Pure Read-Only Evaluation of Past Cycles.

Principles:
- Strict READ_ONLY semantics: never execute tasks, never touch filesystem, never emit operational events.
- Replays historical snapshots against specified policy versions to verify deterministic consistency.
- Enables counterfactual analysis without impacting active missions.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import time
from typing import Any, Callable, Dict, List, Optional, Tuple

from agents.autonomous_loop.models import (
    AdaptationBudget,
    AutonomousLoopState,
    CausalExplanation,
    DriftClassification,
    LoopDecisionType,
    OscillationStatus,
)
from agents.autonomous_loop.policy import (
    AutonomousDecisionPolicy,
    PolicyEvaluationContext,
    PolicyRuleDefinition,
)
from agents.decision_calibration.registry import RegisteredPolicyVersion


@dataclass
class HistoricalDecisionRecord:
    cycle_id: str
    mission_id: str
    context_dict: dict[str, Any]
    original_decision: LoopDecisionType
    original_rule_id: str
    observed_outcome: str


@dataclass
class ReplayResultItem:
    cycle_id: str
    mission_id: str
    original_decision: LoopDecisionType
    replayed_decision: LoopDecisionType
    original_rule_id: str
    replayed_rule_id: str
    matched: bool
    explanation: str


class DecisionReplayEngine:
    """
    Executes pure read-only re-evaluation of historical decision contexts
    against a chosen policy version.
    """

    @classmethod
    def context_from_dict(cls, d: dict[str, Any]) -> PolicyEvaluationContext:
        loop_state_dict = d.get("loop_state", {})
        # Reconstruct minimal loop state
        loop_state = AutonomousLoopState(
            mission_id=d.get("mission_id", "m_hist"),
            cycle_id=d.get("cycle_id", "c_hist"),
            adaptation_count=loop_state_dict.get("adaptation_count", 0),
            consecutive_failures=loop_state_dict.get("consecutive_failures", 0),
            human_intervention_count=loop_state_dict.get("human_intervention_count", 0),
        )

        osc_val = d.get("oscillation_status", "NORMAL")
        try:
            osc_status = OscillationStatus(osc_val)
        except ValueError:
            osc_status = OscillationStatus.NORMAL

        drift_val = d.get("drift_classification", "NO_DRIFT")
        try:
            drift_status = DriftClassification(drift_val)
        except ValueError:
            drift_status = DriftClassification.NO_DRIFT

        return PolicyEvaluationContext(
            mission_id=d.get("mission_id", "m_hist"),
            cycle_id=d.get("cycle_id", "c_hist"),
            loop_state=loop_state,
            budget=AdaptationBudget(),
            security_violation=d.get("security_violation", False),
            security_reason=d.get("security_reason", ""),
            economic_approval_required=d.get("economic_approval_required", False),
            economic_reason=d.get("economic_reason", ""),
            oscillation_status=osc_status,
            oscillation_reason=d.get("oscillation_reason", ""),
            drift_classification=drift_status,
            drift_reason=d.get("drift_reason", ""),
            execution_success=d.get("execution_success", True),
            all_requirements_satisfied=d.get("all_requirements_satisfied", False),
            required_validation_passed=d.get("required_validation_passed", True),
            evidence_complete=d.get("evidence_complete", True),
            state_consistent=d.get("state_consistent", True),
            no_active_blocks=d.get("no_active_blocks", True),
            active_failures=d.get("active_failures", []),
            failure_is_repairable=d.get("failure_is_repairable", False),
            failure_reason=d.get("failure_reason", ""),
            plan_invalid_or_new_dependency=d.get("plan_invalid_or_new_dependency", False),
            prediction_deviation=d.get("prediction_deviation", False),
            prediction_deviation_satisfiable=d.get("prediction_deviation_satisfiable", True),
            task_owner_unavailable=d.get("task_owner_unavailable", False),
            alternative_agent_available=d.get("alternative_agent_available", False),
            human_approval_required=d.get("human_approval_required", False),
        )

    @classmethod
    def replay_corpus(
        cls,
        corpus: list[HistoricalDecisionRecord],
        policy_version: Optional[RegisteredPolicyVersion] = None,
        custom_evaluate_fn: Optional[Callable[[PolicyEvaluationContext], tuple[LoopDecisionType, CausalExplanation, Any]]] = None,
    ) -> list[ReplayResultItem]:
        """
        Replays all records in the corpus using either a custom evaluation function or
        the standard AutonomousDecisionPolicy.evaluate method.
        Never executes real tasks, modifies state, or triggers external effects.
        """
        results: list[ReplayResultItem] = []

        eval_fn = custom_evaluate_fn or AutonomousDecisionPolicy.evaluate

        for rec in corpus:
            ctx = cls.context_from_dict(rec.context_dict)
            replayed_decision, explanation, rule = eval_fn(ctx)

            rule_id = getattr(rule, "rule_id", str(rule))
            results.append(ReplayResultItem(
                cycle_id=rec.cycle_id,
                mission_id=rec.mission_id,
                original_decision=rec.original_decision,
                replayed_decision=replayed_decision,
                original_rule_id=rec.original_rule_id,
                replayed_rule_id=rule_id,
                matched=(replayed_decision == rec.original_decision),
                explanation=explanation.observation if hasattr(explanation, "observation") else str(explanation),
            ))

        return results
