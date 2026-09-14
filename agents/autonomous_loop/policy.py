"""
JARVIS OS — Phase 40: Autonomous Engineering Loop & Closed-Loop Mission Adaptation
Deterministic Decision Policy Layer & Adaptation Budgets.

Principles:
- PLAN != REALITY: decisions must be driven by observable facts and verifiable evidence.
- No synthetic autonomy, no hardcoded if scenario == "x": decision = "REPAIR".
- Decision rules are ordered, deterministic, versioned, and inspectable.
- AI models interpret, diagnose, and suggest; the policy layer decides.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

from agents.autonomous_loop.models import (
    AdaptationBudget,
    AutonomousLoopState,
    CausalExplanation,
    DriftClassification,
    LoopDecisionType,
    OscillationStatus,
)


@dataclass
class PolicyEvaluationContext:
    mission_id: str
    cycle_id: str
    loop_state: AutonomousLoopState
    budget: AdaptationBudget = field(default_factory=AdaptationBudget)

    def __post_init__(self):
        if not isinstance(self.budget, AdaptationBudget):
            self.budget = AdaptationBudget()
    # Security & Integrity
    security_violation: bool = False
    security_reason: str = ""
    economic_approval_required: bool = False
    economic_reason: str = ""
    oscillation_status: OscillationStatus = OscillationStatus.NORMAL
    oscillation_reason: str = ""
    drift_classification: DriftClassification = DriftClassification.NO_DRIFT
    drift_reason: str = ""
    # Progress & Completion
    execution_success: bool = True
    all_requirements_satisfied: bool = False
    required_validation_passed: bool = True
    evidence_complete: bool = True
    state_consistent: bool = True
    no_active_blocks: bool = True
    # Failures & Discrepancies
    active_failures: list[dict[str, Any]] = field(default_factory=list)
    failure_is_repairable: bool = False
    failure_reason: str = ""
    plan_invalid_or_new_dependency: bool = False
    plan_invalid_reason: str = ""
    prediction_deviation: bool = False
    prediction_deviation_satisfiable: bool = True
    deviation_reason: str = ""
    # Agent availability
    task_owner_unavailable: bool = False
    alternative_agent_available: bool = False
    reassignment_reason: str = ""
    # Explicit human gate requirement
    human_approval_required: bool = False
    human_approval_reason: str = ""
    # Phase 48 Contract-Aware Change Management
    contract_change_detected: bool = False
    contract_change_risk: str = "SAFE"
    contract_migration_approved: bool = True
    contract_validation_passed: bool = True
    contract_mismatch_detected: bool = False
    contract_reason: str = ""


@dataclass
class PolicyRuleDefinition:
    rule_id: str
    priority: int  # lower number = higher priority
    condition_name: str
    allowed_decision: LoopDecisionType
    description: str
    consequence: str


class AutonomousDecisionPolicy:
    """
    Deterministic rule engine that maps an observed PolicyEvaluationContext
    to an allowed operational LoopDecisionType and a causal explanation.
    """

    POLICY_VERSION = "40.1.0"

    RULES_TABLE: list[PolicyRuleDefinition] = [
        PolicyRuleDefinition(
            rule_id="RULE_01_SECURITY_BLOCK",
            priority=1,
            condition_name="security_violation",
            allowed_decision=LoopDecisionType.BLOCK,
            description="Security Sentinel violation detected or prohibited privilege escalation requested.",
            consequence="Execution halted immediately; mission state transitions to BLOCKED.",
        ),
        PolicyRuleDefinition(
            rule_id="RULE_02_ECONOMIC_APPROVAL",
            priority=2,
            condition_name="economic_approval_required",
            allowed_decision=LoopDecisionType.REQUEST_HUMAN,
            description="Mission involves financial transaction or resource purchase exceeding autonomous limit.",
            consequence="Halt for mandatory operator authorization before funds commitment.",
        ),
        PolicyRuleDefinition(
            rule_id="RULE_03_OSCILLATION_DETECTED",
            priority=3,
            condition_name="oscillation_detected",
            allowed_decision=LoopDecisionType.REQUEST_HUMAN,
            description="Repetitive state, cyclical replanning, or repeated repair oscillation detected.",
            consequence="Escalate to operator to break cyclic deadlock; autonomous loop suspended.",
        ),
        PolicyRuleDefinition(
            rule_id="RULE_04_UNEXPECTED_DRIFT",
            priority=4,
            condition_name="unexpected_drift",
            allowed_decision=LoopDecisionType.REQUEST_HUMAN,
            description="Mission requirements or scope diverged unexpectedly from original user directive without formal intent delta.",
            consequence="Escalate to operator for confirmation of scope realignment.",
        ),
        PolicyRuleDefinition(
            rule_id="RULE_05_ADAPTATION_BUDGET_EXHAUSTED",
            priority=5,
            condition_name="adaptation_budget_exhausted",
            allowed_decision=LoopDecisionType.REQUEST_HUMAN,
            description="Adaptations, repairs, or replans exceeded configured AdaptationBudget limits.",
            consequence="Escalate to operator to avoid infinite resource consumption.",
        ),
        PolicyRuleDefinition(
            rule_id="RULE_06_CONSECUTIVE_FAILURES_EXHAUSTED",
            priority=6,
            condition_name="consecutive_failures_exhausted",
            allowed_decision=LoopDecisionType.REQUEST_HUMAN,
            description="Consecutive execution or validation failures exceeded threshold.",
            consequence="Halt autonomous attempts and request manual guidance.",
        ),
        PolicyRuleDefinition(
            rule_id="RULE_07_FINISH_GATE_SATISFIED",
            priority=7,
            condition_name="finish_gate_satisfied",
            allowed_decision=LoopDecisionType.FINISH,
            description="All requirements satisfied, execution succeeded, evidence complete, validation passed, zero false success confirmed.",
            consequence="Mission concludes successfully with verifiable proof ledger.",
        ),
        PolicyRuleDefinition(
            rule_id="RULE_08_HUMAN_APPROVAL_PENDING",
            priority=8,
            condition_name="human_approval_required",
            allowed_decision=LoopDecisionType.REQUEST_HUMAN,
            description="Pending human gate confirmation requested by policy, high risk score, or explicit directive.",
            consequence="Wait for operator input; loop enters WAITING_HUMAN stage.",
        ),
        PolicyRuleDefinition(
            rule_id="RULE_09_REPAIRABLE_VALIDATION_FAILURE",
            priority=9,
            condition_name="repairable_validation_failure",
            allowed_decision=LoopDecisionType.REPAIR,
            description="Task or validation failure occurred with AST/runtime diagnosis and repair budget available.",
            consequence="Trigger self-healing repair pipeline without declaring premature success.",
        ),
        PolicyRuleDefinition(
            rule_id="RULE_10_UNREPAIRABLE_FAILURE",
            priority=10,
            condition_name="unrepairable_failure",
            allowed_decision=LoopDecisionType.REQUEST_HUMAN,
            description="Task failure occurred without viable automated patch diagnosis.",
            consequence="Escalate to operator with diagnostics and failure logs.",
        ),
        PolicyRuleDefinition(
            rule_id="RULE_11_PLAN_INVALID_OR_NEW_DEPENDENCY",
            priority=11,
            condition_name="plan_invalid_or_new_dependency",
            allowed_decision=LoopDecisionType.REPLAN,
            description="Task dependency invalidated, new structural dependency discovered, or plan DAG broken.",
            consequence="Trigger dynamic replanning to compute plan delta preserving completed work.",
        ),
        PolicyRuleDefinition(
            rule_id="RULE_12_PREDICTION_DEVIATION_SATISFIABLE",
            priority=12,
            condition_name="prediction_deviation_satisfiable",
            allowed_decision=LoopDecisionType.ADAPT,
            description="Observed outcome deviated from prediction, but mission requirements remain satisfiable via localized adaptation.",
            consequence="Formulate and apply AdaptationProposal (e.g. add validation, adjust task priority).",
        ),
        PolicyRuleDefinition(
            rule_id="RULE_13_AGENT_UNAVAILABLE_COMPATIBLE_EXISTS",
            priority=13,
            condition_name="agent_unavailable_compatible_exists",
            allowed_decision=LoopDecisionType.REASSIGN,
            description="Assigned task owner agent is offline/unresponsive, and another capable swarm agent is available.",
            consequence="Reassign task ownership to standby agent and update DAG routing.",
        ),
        PolicyRuleDefinition(
            rule_id="RULE_14_NORMAL_PROGRESSION",
            priority=14,
            condition_name="normal_progression",
            allowed_decision=LoopDecisionType.CONTINUE,
            description="Observed state matches expectations, validations pass, requirements progressing steadily.",
            consequence="Advance to next cycle and continue DAG execution.",
        ),
    ]

    @classmethod
    def evaluate(cls, ctx: PolicyEvaluationContext) -> tuple[LoopDecisionType, CausalExplanation, PolicyRuleDefinition]:
        """
        Evaluates context against policy rules deterministically in order of priority.
        Returns: (decision, causal_explanation, matched_rule)
        """
        # Check budget limits
        budget_adaptations_exceeded = ctx.loop_state.adaptation_count >= ctx.budget.max_adaptations
        budget_repairs_exceeded = len(ctx.loop_state.active_repairs) >= ctx.budget.max_repairs
        budget_replans_exceeded = len(ctx.loop_state.active_replans) >= ctx.budget.max_replans
        budget_failures_exceeded = ctx.loop_state.consecutive_failures >= ctx.budget.max_consecutive_failures
        budget_human_requests_exceeded = ctx.loop_state.human_intervention_count >= ctx.budget.max_human_requests

        # Rule 1: Security Sentinel Violation
        if ctx.security_violation:
            rule = cls.RULES_TABLE[0]
            explanation = CausalExplanation(
                observation=f"Security Sentinel violation: {ctx.security_reason or 'Potentially malicious or prohibited action.'}",
                rule=rule.description,
                decision=rule.allowed_decision.value,
                consequence=rule.consequence,
                evidence_refs=["sentinel_audit_log", "security_policy"],
            )
            return rule.allowed_decision, explanation, rule

        # Rule 2: Economic Approval Required
        if ctx.economic_approval_required:
            rule = cls.RULES_TABLE[1]
            explanation = CausalExplanation(
                observation=f"Economic invariant gate triggered: {ctx.economic_reason or 'Financial transaction requires explicit operator authorization.'}",
                rule=rule.description,
                decision=rule.allowed_decision.value,
                consequence=rule.consequence,
                evidence_refs=["economic_ledger", "operator_budget_policy"],
            )
            return rule.allowed_decision, explanation, rule

        # Rule 3: Oscillation Detected
        if ctx.oscillation_status == OscillationStatus.CONFIRMED_OSCILLATION:
            rule = cls.RULES_TABLE[2]
            explanation = CausalExplanation(
                observation=f"Oscillation detected: {ctx.oscillation_reason or 'Cyclic state or repeated repair/replan loop observed.'}",
                rule=rule.description,
                decision=rule.allowed_decision.value,
                consequence=rule.consequence,
                evidence_refs=["loop_fingerprint_ledger"],
            )
            return rule.allowed_decision, explanation, rule

        # Rule 4: Unexpected Mission Drift
        if ctx.drift_classification == DriftClassification.UNEXPECTED_DRIFT:
            rule = cls.RULES_TABLE[3]
            explanation = CausalExplanation(
                observation=f"Unexpected mission drift detected: {ctx.drift_reason or 'Current requirements diverged from user intent.'}",
                rule=rule.description,
                decision=rule.allowed_decision.value,
                consequence=rule.consequence,
                evidence_refs=["intent_diff", "requirements_ledger"],
            )
            return rule.allowed_decision, explanation, rule

        # Rule 5: Adaptation Budget Exhausted
        if budget_adaptations_exceeded or budget_replans_exceeded:
            rule = cls.RULES_TABLE[4]
            reason = "Adaptation count reached budget limit" if budget_adaptations_exceeded else "Replan limit reached"
            explanation = CausalExplanation(
                observation=f"Adaptation budget exhausted: {reason} ({ctx.loop_state.adaptation_count}/{ctx.budget.max_adaptations}).",
                rule=rule.description,
                decision=rule.allowed_decision.value,
                consequence=rule.consequence,
                evidence_refs=["adaptation_budget_ledger"],
            )
            return rule.allowed_decision, explanation, rule

        # Rule 6: Consecutive Failures Exhausted
        if budget_failures_exceeded:
            rule = cls.RULES_TABLE[5]
            explanation = CausalExplanation(
                observation=f"Failure budget exhausted: {ctx.loop_state.consecutive_failures} consecutive failures (limit: {ctx.budget.max_consecutive_failures}).",
                rule=rule.description,
                decision=rule.allowed_decision.value,
                consequence=rule.consequence,
                evidence_refs=["failure_memory", "test_report"],
            )
            return rule.allowed_decision, explanation, rule

        # Rule 7: Finish Gate Satisfied
        finish_gate_ready = (
            ctx.execution_success
            and ctx.all_requirements_satisfied
            and ctx.required_validation_passed
            and ctx.evidence_complete
            and ctx.state_consistent
            and ctx.no_active_blocks
            and not ctx.active_failures
            and ctx.contract_validation_passed
            and not ctx.contract_mismatch_detected
        )
        if finish_gate_ready:
            rule = cls.RULES_TABLE[6]
            explanation = CausalExplanation(
                observation="All mission requirements satisfied with complete verifiable evidence, passing validation suites, and contract compatibility confirmed.",
                rule=rule.description,
                decision=rule.allowed_decision.value,
                consequence=rule.consequence,
                evidence_refs=["zero_false_success_proof", "evidence_ledger"],
            )
            return rule.allowed_decision, explanation, rule

        # Contract Change Human Gate Enforce
        if ctx.contract_change_detected and ctx.contract_change_risk in ("BREAKING", "POTENTIALLY_BREAKING") and not ctx.contract_migration_approved:
            ctx.human_approval_required = True
            if not ctx.human_approval_reason:
                ctx.human_approval_reason = f"Breaking contract change: {ctx.contract_reason or 'operator migration approval required.'}"

        # Rule 8: Human Approval Required
        if ctx.human_approval_required:
            rule = cls.RULES_TABLE[7]
            explanation = CausalExplanation(
                observation=f"Human approval required: {ctx.human_approval_reason or 'Gate requires explicit human sign-off.'}",
                rule=rule.description,
                decision=rule.allowed_decision.value,
                consequence=rule.consequence,
                evidence_refs=["mission_gate_log"],
            )
            return rule.allowed_decision, explanation, rule

        # Rule 9 & 10: Failures
        if ctx.active_failures:
            if ctx.failure_is_repairable and not budget_repairs_exceeded:
                rule = cls.RULES_TABLE[8]
                explanation = CausalExplanation(
                    observation=f"Repairable failure encountered: {ctx.failure_reason or 'Diagnosed AST/syntax/null error.'}",
                    rule=rule.description,
                    decision=rule.allowed_decision.value,
                    consequence=rule.consequence,
                    evidence_refs=["ast_diagnostics", "build_stderr"],
                )
                return rule.allowed_decision, explanation, rule
            else:
                rule = cls.RULES_TABLE[9]
                explanation = CausalExplanation(
                    observation=f"Unrepairable or repair-budget-exceeded failure: {ctx.failure_reason or 'No patch hypothesis available.'}",
                    rule=rule.description,
                    decision=rule.allowed_decision.value,
                    consequence=rule.consequence,
                    evidence_refs=["failure_traceback", "repair_ledger"],
                )
                return rule.allowed_decision, explanation, rule

        # Rule 11: Plan Invalid / New Dependency Discovered
        if ctx.plan_invalid_or_new_dependency:
            rule = cls.RULES_TABLE[10]
            explanation = CausalExplanation(
                observation=f"Plan DAG invalid or new dependency discovered: {ctx.plan_invalid_reason or 'Topology modification required.'}",
                rule=rule.description,
                decision=rule.allowed_decision.value,
                consequence=rule.consequence,
                evidence_refs=["dependency_graph", "plan_topology"],
            )
            return rule.allowed_decision, explanation, rule

        # Rule 12: Prediction Deviation Satisfiable
        if ctx.prediction_deviation and ctx.prediction_deviation_satisfiable:
            rule = cls.RULES_TABLE[11]
            explanation = CausalExplanation(
                observation=f"Prediction deviation observed: {ctx.deviation_reason or 'Unexpected file or task mutation detected.'} Requirements remain satisfiable.",
                rule=rule.description,
                decision=rule.allowed_decision.value,
                consequence=rule.consequence,
                evidence_refs=["prediction_vs_actual_report"],
            )
            return rule.allowed_decision, explanation, rule

        # Rule 13: Task Owner Unavailable, Substitute Available
        if ctx.task_owner_unavailable and ctx.alternative_agent_available:
            rule = cls.RULES_TABLE[12]
            explanation = CausalExplanation(
                observation=f"Task owner unavailable: {ctx.reassignment_reason or 'Primary agent offline, backup swarm agent assigned.'}",
                rule=rule.description,
                decision=rule.allowed_decision.value,
                consequence=rule.consequence,
                evidence_refs=["swarm_health_registry"],
            )
            return rule.allowed_decision, explanation, rule

        # Rule 14: Default Normal Progression
        rule = cls.RULES_TABLE[13]
        explanation = CausalExplanation(
            observation="Execution progressing normally: all observed outputs match expectations and pass validation gates.",
            rule=rule.description,
            decision=rule.allowed_decision.value,
            consequence=rule.consequence,
            evidence_refs=["task_execution_log", "test_report"],
        )
        return rule.allowed_decision, explanation, rule

    @classmethod
    def get_policy_schema(cls) -> dict[str, Any]:
        return {
            "policy_version": cls.POLICY_VERSION,
            "rules_count": len(cls.RULES_TABLE),
            "rules": [asdict(r) for r in cls.RULES_TABLE],
        }
