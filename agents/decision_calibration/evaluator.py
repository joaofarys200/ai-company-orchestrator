"""
JARVIS OS — Phase 41: Autonomous Decision Calibration & Failure Intelligence
Decision Outcome Evaluator: Causal Classification, Error Taxonomy & Counterfactual Analysis.

Principles:
- PLAN != REALITY: Evaluate whether the decision produced the intended state change.
- Deviation != Decision Error (a prediction deviation with proper DAG adaptation is not an error).
- False Finish is always CRITICAL severity (Zero False Success guard).
- Execution failure != Decision error (compiler crash during valid repair is an EXECUTION_ERROR).
"""

from __future__ import annotations

from dataclasses import dataclass, field
import time
from typing import Any, Dict, List, Optional, Set, Tuple

from agents.autonomous_loop.models import (
    AutonomousLoopState,
    DriftClassification,
    LoopDecisionType,
    OscillationStatus,
)
from agents.autonomous_loop.policy import PolicyEvaluationContext, PolicyRuleDefinition
from agents.decision_calibration.models import (
    CounterfactualDecision,
    DecisionCorrectness,
    DecisionErrorTaxonomy,
    DecisionOutcome,
    DecisionQualityMetrics,
    DecisionSeverity,
    DecisionTrace,
    ExecutionContributionType,
    MissedObservationType,
    PredictionContributionType,
    RuleEvaluationRecord,
)


class DecisionOutcomeEvaluator:
    """
    Evaluates individual loop decisions against empirical observations and known invariants.
    Classifies root causes deterministically and generates counterfactual analysis.
    """

    @classmethod
    def evaluate_decision_outcome(
        cls,
        mission_id: str,
        cycle_id: str,
        decision_id: str,
        decision_type: LoopDecisionType,
        policy_version: str,
        rule_matched_id: str,
        rules_evaluated: list[RuleEvaluationRecord],
        ctx: PolicyEvaluationContext,
        observed_outcome: str,
        expected_decision: Optional[LoopDecisionType] = None,
        evidence_ids: Optional[list[str]] = None,
        prediction_error: bool = False,
        execution_failed: bool = False,
        execution_crash: bool = False,
        available_unused_observations: Optional[list[str]] = None,
    ) -> tuple[DecisionOutcome, DecisionTrace]:
        ev_ids = evidence_ids or []
        outcome_id = f"out_{mission_id}_{cycle_id}_{int(time.time()*1000) % 100000}"

        # 1. Determine correctness
        if expected_decision is not None:
            if decision_type == expected_decision:
                correctness = DecisionCorrectness.CORRECT
            elif (
                expected_decision in [LoopDecisionType.ADAPT, LoopDecisionType.REPLAN]
                and decision_type in [LoopDecisionType.ADAPT, LoopDecisionType.REPLAN]
            ):
                correctness = DecisionCorrectness.PARTIALLY_CORRECT
            else:
                correctness = DecisionCorrectness.INCORRECT
        else:
            # Empirical invariant checks
            if decision_type == LoopDecisionType.FINISH and not (
                ctx.all_requirements_satisfied and ctx.required_validation_passed and ctx.evidence_complete
            ):
                correctness = DecisionCorrectness.INCORRECT
            elif decision_type == LoopDecisionType.CONTINUE and ctx.security_violation:
                correctness = DecisionCorrectness.INCORRECT
            elif decision_type == LoopDecisionType.CONTINUE and ctx.oscillation_status == OscillationStatus.CONFIRMED_OSCILLATION:
                correctness = DecisionCorrectness.INCORRECT
            elif decision_type == LoopDecisionType.CONTINUE and ctx.active_failures and not ctx.failure_is_repairable:
                correctness = DecisionCorrectness.INCORRECT
            else:
                correctness = DecisionCorrectness.CORRECT

        # 2. Causal contributions
        pred_contrib = PredictionContributionType.PREDICTION_NOT_RELEVANT
        if prediction_error:
            pred_contrib = PredictionContributionType.PREDICTION_INCORRECT
        elif ctx.prediction_deviation:
            pred_contrib = PredictionContributionType.PREDICTION_PARTIAL

        exec_contrib = ExecutionContributionType.EXECUTION_SUCCESS
        if execution_crash:
            exec_contrib = ExecutionContributionType.EXECUTION_CRASHED
        elif execution_failed:
            exec_contrib = ExecutionContributionType.EXECUTION_FAILED_UNEXPECTEDLY

        # 3. Classify Root Cause & Missed Observations
        root_cause = DecisionErrorTaxonomy.UNDETERMINED
        severity = DecisionSeverity.INFO
        missed_obs = MissedObservationType.NO_OBSERVATION_GAP
        policy_gap = ""
        contributing_factors: list[str] = []

        if available_unused_observations:
            missed_obs = MissedObservationType.OBSERVATION_AVAILABLE_BUT_UNUSED
            contributing_factors.append(f"Unused observations: {', '.join(available_unused_observations)}")

        if correctness == DecisionCorrectness.CORRECT:
            root_cause = DecisionErrorTaxonomy.EXPECTED_BLOCK if decision_type in [LoopDecisionType.BLOCK, LoopDecisionType.REQUEST_HUMAN] else DecisionErrorTaxonomy.UNDETERMINED
            severity = DecisionSeverity.INFO
        else:
            # False Finish is always CRITICAL
            if decision_type == LoopDecisionType.FINISH:
                severity = DecisionSeverity.CRITICAL
                root_cause = DecisionErrorTaxonomy.POLICY_GAP
                policy_gap = "Rule 7 fired despite unverified evidence or unsatisfied requirements."
                contributing_factors.append("Premature finish gate transition without complete evidence.")

            # False Continue
            elif decision_type == LoopDecisionType.CONTINUE:
                if ctx.security_violation:
                    severity = DecisionSeverity.CRITICAL
                    root_cause = DecisionErrorTaxonomy.POLICY_PRIORITY_ERROR
                    contributing_factors.append("Security sentinel violation ignored by low-priority rule.")
                elif ctx.oscillation_status == OscillationStatus.CONFIRMED_OSCILLATION:
                    severity = DecisionSeverity.MEDIUM
                    # Check if observation was missing or policy failed
                    if available_unused_observations or "oscillation_status" in (available_unused_observations or []):
                        root_cause = DecisionErrorTaxonomy.OBSERVATION_GAP
                        contributing_factors.append("Oscillation state confirmed in previous cycle but not ingested into evaluation context.")
                    else:
                        root_cause = DecisionErrorTaxonomy.POLICY_GAP
                        policy_gap = "Rule 3 failed to fire under active oscillation signature."
                elif prediction_error:
                    severity = DecisionSeverity.LOW
                    root_cause = DecisionErrorTaxonomy.PREDICTION_ERROR
                    contributing_factors.append("Predictor underpredicted affected files leading to unadapted continuation.")
                elif exec_contrib == ExecutionContributionType.EXECUTION_CRASHED:
                    severity = DecisionSeverity.HIGH
                    root_cause = DecisionErrorTaxonomy.EXECUTION_ERROR
                    contributing_factors.append("Worker process crashed; execution error rather than policy flaw.")
                elif ctx.active_failures:
                    severity = DecisionSeverity.HIGH
                    root_cause = DecisionErrorTaxonomy.POLICY_GAP
                    policy_gap = "Active unrepairable failure was not matched by replan or human escalation rules."
                else:
                    severity = DecisionSeverity.MEDIUM
                    root_cause = DecisionErrorTaxonomy.INCORRECT_CLASSIFICATION

            # False Escalation
            elif decision_type == LoopDecisionType.REQUEST_HUMAN:
                severity = DecisionSeverity.LOW
                root_cause = DecisionErrorTaxonomy.POLICY_PRIORITY_ERROR
                contributing_factors.append("Excessive conservatism: autonomous repair/adaptation was viable.")

        # 4. Counterfactual Analysis
        counterfactual = None
        if correctness in [DecisionCorrectness.INCORRECT, DecisionCorrectness.PARTIALLY_CORRECT]:
            alt_dec = expected_decision or (
                LoopDecisionType.REQUEST_HUMAN if ctx.oscillation_status == OscillationStatus.CONFIRMED_OSCILLATION
                else LoopDecisionType.REPAIR if ctx.failure_is_repairable
                else LoopDecisionType.REPLAN if ctx.plan_invalid_or_new_dependency
                else LoopDecisionType.BLOCK if ctx.security_violation
                else LoopDecisionType.ADAPT
            )
            counterfactual = CounterfactualDecision(
                alternative_decision=alt_dec,
                why_valid=f"Alternative decision '{alt_dec.value}' directly satisfies active invariants ({root_cause.value}).",
                why_not_selected=f"Rule evaluating '{decision_type.value}' had higher precedence or context missed observation.",
                expected_effect=f"Would have halted oscillation/repaired failure immediately, avoiding invalid cycle progress.",
                observed_effect=observed_outcome,
                evidence_support=ev_ids,
            )

        # 5. Build DecisionTrace
        trace_id = f"trc_{cycle_id}_{int(time.time()*1000) % 10000}"
        trace = DecisionTrace(
            trace_id=trace_id,
            mission_id=mission_id,
            cycle_id=cycle_id,
            observations_summary={
                "security_violation": ctx.security_violation,
                "oscillation_status": ctx.oscillation_status.value,
                "drift_classification": ctx.drift_classification.value,
                "active_failures_count": len(ctx.active_failures),
                "all_requirements_satisfied": ctx.all_requirements_satisfied,
                "evidence_complete": ctx.evidence_complete,
            },
            rules_evaluated=rules_evaluated,
            matched_rule_id=rule_matched_id,
            decision=decision_type.value,
            gate_status="PASSED" if not ctx.security_violation else "BLOCKED",
            action_executed=f"STAGE_{decision_type.value}",
            result_observed=observed_outcome,
            evaluation_summary=f"Correctness: {correctness.value} | Severity: {severity.value} | RootCause: {root_cause.value}",
        )

        outcome = DecisionOutcome(
            outcome_id=outcome_id,
            mission_id=mission_id,
            cycle_id=cycle_id,
            decision_id=decision_id,
            decision_type=decision_type,
            policy_version=policy_version,
            rule_id=rule_matched_id,
            expected_outcome=expected_decision.value if expected_decision else "COMPLIANT_TRANSITION",
            observed_outcome=observed_outcome,
            decision_correctness=correctness,
            evidence_ids=ev_ids,
            deviation_type=root_cause.value if correctness != DecisionCorrectness.CORRECT else "NONE",
            severity=severity,
            root_cause=root_cause,
            contributing_factors=contributing_factors,
            missed_observations=missed_obs,
            prediction_contribution=pred_contrib,
            execution_contribution=exec_contrib,
            policy_gap=policy_gap,
            counterfactual=counterfactual,
        )

        return outcome, trace

    @classmethod
    def compute_quality_metrics(
        cls,
        outcomes: list[DecisionOutcome],
    ) -> DecisionQualityMetrics:
        """
        Computes formal multi-axis decision quality metrics, confusion matrix,
        and rates for False Finish, False Continue, and False Escalation.
        """
        total = len(outcomes)
        if total == 0:
            return DecisionQualityMetrics()

        correct = sum(1 for o in outcomes if o.decision_correctness == DecisionCorrectness.CORRECT)
        partially = sum(1 for o in outcomes if o.decision_correctness == DecisionCorrectness.PARTIALLY_CORRECT)
        incorrect = sum(1 for o in outcomes if o.decision_correctness == DecisionCorrectness.INCORRECT)

        # False rates
        false_finish = sum(
            1 for o in outcomes
            if o.decision_type == LoopDecisionType.FINISH and o.decision_correctness == DecisionCorrectness.INCORRECT
        )
        false_continue = sum(
            1 for o in outcomes
            if o.decision_type == LoopDecisionType.CONTINUE and o.decision_correctness == DecisionCorrectness.INCORRECT
        )
        false_escalation = sum(
            1 for o in outcomes
            if o.decision_type == LoopDecisionType.REQUEST_HUMAN and o.decision_correctness == DecisionCorrectness.INCORRECT
        )
        false_repair = sum(
            1 for o in outcomes
            if o.decision_type == LoopDecisionType.REPAIR and o.decision_correctness == DecisionCorrectness.INCORRECT
        )
        false_replan = sum(
            1 for o in outcomes
            if o.decision_type == LoopDecisionType.REPLAN and o.decision_correctness == DecisionCorrectness.INCORRECT
        )
        human_requests = sum(1 for o in outcomes if o.decision_type == LoopDecisionType.REQUEST_HUMAN)

        # Confusion matrix: Expected vs Actual
        matrix: dict[str, dict[str, int]] = {}
        all_types = [t.value for t in LoopDecisionType]
        for exp in all_types:
            matrix[exp] = {act: 0 for act in all_types}

        for o in outcomes:
            exp_key = o.expected_outcome
            if exp_key not in matrix:
                exp_key = o.decision_type.value
            act_key = o.decision_type.value
            if exp_key in matrix and act_key in matrix[exp_key]:
                matrix[exp_key][act_key] += 1

        # Precision & Recall per decision
        precisions: dict[str, float] = {}
        recalls: dict[str, float] = {}
        for d_type in all_types:
            tp = matrix[d_type][d_type]
            predicted_count = sum(matrix[exp][d_type] for exp in all_types)
            actual_count = sum(matrix[d_type][act] for act in all_types)

            precisions[d_type] = round(tp / predicted_count, 3) if predicted_count > 0 else 1.0
            recalls[d_type] = round(tp / actual_count, 3) if actual_count > 0 else 1.0

        macro_prec = round(sum(precisions.values()) / len(precisions), 3)
        macro_rec = round(sum(recalls.values()) / len(recalls), 3)

        return DecisionQualityMetrics(
            total_decisions=total,
            correct_decisions=correct,
            partially_correct_decisions=partially,
            incorrect_decisions=incorrect,
            accuracy=round((correct + 0.5 * partially) / total, 4),
            macro_precision=macro_prec,
            macro_recall=macro_rec,
            per_decision_precision=precisions,
            per_decision_recall=recalls,
            confusion_matrix=matrix,
            escalation_rate=round(human_requests / total, 4),
            false_continue_count=false_continue,
            false_continue_rate=round(false_continue / total, 4),
            false_repair_count=false_repair,
            false_replan_count=false_replan,
            false_finish_count=false_finish,
            false_finish_rate=round(false_finish / total, 4),
            false_escalation_count=false_escalation,
            false_escalation_rate=round(false_escalation / total, 4),
            human_request_rate=round(human_requests / total, 4),
        )
