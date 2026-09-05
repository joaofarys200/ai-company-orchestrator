"""Unit tests A through X for Fase 13 Adaptive Planning models and validation."""

import pytest
from agents.adaptive_planning import (
    AdaptationBudget,
    AdaptationRecord,
    AdaptationStatus,
    AdaptationTrigger,
    AdaptivePlanningEngine,
    AdaptivePlanningValidator,
    MissionAdaptationProposal,
    Observation,
    ObservationSeverity,
    ObservationSource,
    PlanEvaluationDecision,
)
from agents.task_graph import FailureCategory, FailureInfo, TaskGraph, TaskNode, TaskStatus


# ── TEST A: MODEL ROUNDTRIP ──────────────────────────────────────────────────


def test_a_model_serialization_deserialization():
    obs = Observation(
        source=ObservationSource.TEST,
        event="Pytest 3 failures in auth module",
        task_id="task_1",
        severity=ObservationSeverity.HIGH,
        impact="Auth token generation broken",
        details={"failures": ["test_jwt_sign", "test_jwt_verify"]},
    )
    obs_dict = obs.to_dict()
    obs_restored = Observation.from_dict(obs_dict)
    assert obs_restored.observation_id == obs.observation_id
    assert obs_restored.source == ObservationSource.TEST
    assert obs_restored.severity == ObservationSeverity.HIGH
    assert obs_restored.details == obs.details

    prop = MissionAdaptationProposal(
        proposal_id="prop_001",
        mission_id="m_001",
        base_graph_version=1,
        decision=PlanEvaluationDecision.ADAPT_PLAN,
        trigger=AdaptationTrigger.TEST_FAILURE,
        reason="Adapting auth tasks due to test failure",
        affected_tasks=["t1"],
        added_tasks=[{"task_id": "t1_fix", "title": "Fix Auth"}],
        removed_tasks=["t1_old"],
        evidence_ids=["ev_001"],
    )
    prop_dict = prop.to_dict()
    prop_restored = MissionAdaptationProposal.from_dict(prop_dict)
    assert prop_restored.proposal_id == "prop_001"
    assert prop_restored.decision == PlanEvaluationDecision.ADAPT_PLAN
    assert prop_restored.trigger == AdaptationTrigger.TEST_FAILURE
    assert prop_restored.evidence_ids == ["ev_001"]


# ── TEST B: STRATEGY FINGERPRINT DETERMINISM ─────────────────────────────────


def test_b_strategy_fingerprint_determinism():
    p1 = MissionAdaptationProposal(
        decision=PlanEvaluationDecision.ADAPT_PLAN,
        added_tasks=[{"task_id": "b", "title": "B"}, {"task_id": "a", "title": "A"}],
        removed_tasks=["z", "y"],
        changed_edges=[["b", "c"], ["a", "b"]],
    )
    p2 = MissionAdaptationProposal(
        decision=PlanEvaluationDecision.ADAPT_PLAN,
        added_tasks=[{"task_id": "a", "title": "A"}, {"task_id": "b", "title": "B"}],
        removed_tasks=["y", "z"],
        changed_edges=[["a", "b"], ["b", "c"]],
    )
    assert p1.compute_strategy_fingerprint() == p2.compute_strategy_fingerprint()
    assert len(p1.compute_strategy_fingerprint()) == 64


# ── TEST C: VALID ADAPTATION ACCEPTANCE ──────────────────────────────────────


def test_c_valid_adaptation_acceptance():
    validator = AdaptivePlanningValidator()
    graph = TaskGraph(
        nodes=[
            TaskNode(task_id="t1", title="Task 1", status=TaskStatus.COMPLETED),
            TaskNode(task_id="t2", title="Task 2", status=TaskStatus.PENDING, dependencies=["t1"]),
        ],
        graph_version=1,
    )
    prop = MissionAdaptationProposal(
        proposal_id="prop_val",
        mission_id="m_1",
        base_graph_version=1,
        decision=PlanEvaluationDecision.ADAPT_PLAN,
        trigger=AdaptationTrigger.NEW_REQUIREMENT,
        reason="Adicionar tarefa paralela para validação de segurança.",
        added_tasks=[{"task_id": "t3", "title": "Security Check", "dependencies": ["t1"]}],
        evidence_ids=["ev_req_1"],
    )
    valid, reason, trial = validator.validate_proposal(prop, graph)
    assert valid is True
    assert trial is not None
    assert "t3" in trial.nodes
    assert trial.nodes["t3"].dependencies == ["t1"]


# ── TEST D: CYCLE REJECTION IN TRIAL DAG ─────────────────────────────────────


def test_d_cycle_rejection_in_trial_dag():
    validator = AdaptivePlanningValidator()
    graph = TaskGraph(
        nodes=[
            TaskNode(task_id="t1", title="Task 1", status=TaskStatus.PENDING),
            TaskNode(task_id="t2", title="Task 2", status=TaskStatus.PENDING, dependencies=["t1"]),
        ],
        graph_version=1,
    )
    # Adding edge t1 -> t2 and then t2 -> t1 creates a cycle
    prop = MissionAdaptationProposal(
        base_graph_version=1,
        decision=PlanEvaluationDecision.ADAPT_PLAN,
        trigger=AdaptationTrigger.UNEXPECTED_COMPLEXITY,
        reason="Introduzir dependência cíclica inválida.",
        changed_edges=[["t2", "t1"]],
    )
    valid, reason, _ = validator.validate_proposal(prop, graph)
    assert valid is False
    assert "REJECTED_CYCLE_DETECTED" in reason


# ── TEST E: COMPLETED TASK PRESERVATION WITHOUT JUSTIFICATION ────────────────


def test_e_completed_task_rejection_without_justification():
    validator = AdaptivePlanningValidator()
    graph = TaskGraph(
        nodes=[
            TaskNode(task_id="t1", title="Task 1", status=TaskStatus.COMPLETED),
            TaskNode(task_id="t2", title="Task 2", status=TaskStatus.PENDING, dependencies=["t1"]),
        ],
        graph_version=1,
    )
    prop = MissionAdaptationProposal(
        base_graph_version=1,
        decision=PlanEvaluationDecision.ADAPT_PLAN,
        trigger=AdaptationTrigger.REQUIREMENT_CHANGE,
        reason="Tentativa de remover t1 que já está COMPLETED sem justificativa.",
        removed_tasks=["t1"],
    )
    valid, reason, _ = validator.validate_proposal(prop, graph)
    assert valid is False
    assert "COMPLETED_TASK_REGRESSION_FORBIDDEN" in reason


# ── TEST F: COMPLETED TASK MUTATION WITH EXPLICIT JUSTIFICATION ──────────────


def test_f_completed_task_acceptance_with_justification():
    validator = AdaptivePlanningValidator()
    graph = TaskGraph(
        nodes=[
            TaskNode(task_id="t1", title="Task 1", status=TaskStatus.COMPLETED),
            TaskNode(task_id="t2", title="Task 2", status=TaskStatus.PENDING, dependencies=["t1"]),
        ],
        graph_version=1,
    )
    prop = MissionAdaptationProposal(
        base_graph_version=1,
        decision=PlanEvaluationDecision.ADAPT_PLAN,
        trigger=AdaptationTrigger.REQUIREMENT_CHANGE,
        reason="Substituir t1 por versão atualizada após mudança fundamental no escopo.",
        removed_tasks=["t1"],
        added_tasks=[{"task_id": "t1_v2", "title": "Task 1 Updated"}],
        justification_for_completed_tasks="O cliente alterou os requisitos de infraestrutura e t1 precisa de ser reconstruída com nova especificação.",
    )
    valid, reason, trial = validator.validate_proposal(prop, graph)
    assert valid is True
    assert "t1" not in trial.nodes
    assert "t1_v2" in trial.nodes


# ── TEST G: RUNNING TASK NON-INTERFERENCE ────────────────────────────────────


def test_g_running_task_non_interference():
    validator = AdaptivePlanningValidator()
    graph = TaskGraph(
        nodes=[
            TaskNode(task_id="t1", title="Task 1", status=TaskStatus.RUNNING),
            TaskNode(task_id="t2", title="Task 2", status=TaskStatus.PENDING, dependencies=["t1"]),
        ],
        graph_version=1,
    )
    prop = MissionAdaptationProposal(
        base_graph_version=1,
        decision=PlanEvaluationDecision.ADAPT_PLAN,
        trigger=AdaptationTrigger.RUNTIME_FAILURE,
        reason="Tentar mutar tarefa que está em execução activa.",
        removed_tasks=["t1"],
        evidence_ids=["ev_run"],
    )
    valid, reason, _ = validator.validate_proposal(prop, graph)
    assert valid is False
    assert "RUNNING_TASK_MUTATION_FORBIDDEN" in reason


# ── TEST H: STALE GRAPH VERSION REJECTION ────────────────────────────────────


def test_h_stale_graph_version_rejection():
    validator = AdaptivePlanningValidator()
    graph = TaskGraph(nodes=[], graph_version=5)
    prop = MissionAdaptationProposal(
        base_graph_version=4,  # Stale!
        decision=PlanEvaluationDecision.ADAPT_PLAN,
        trigger=AdaptationTrigger.HUMAN_INTERVENTION,
        reason="Proposta baseada em versão obsoleta do grafo.",
    )
    valid, reason, _ = validator.validate_proposal(prop, graph)
    assert valid is False
    assert "REJECTED_STALE_GRAPH_VERSION" in reason


# ── TEST I: STRATEGY OSCILLATION DETECTION ───────────────────────────────────


def test_i_strategy_oscillation_detection():
    budget = AdaptationBudget(max_strategy_repeats=2)
    validator = AdaptivePlanningValidator(budget=budget)
    graph = TaskGraph(nodes=[], graph_version=1)

    prop = MissionAdaptationProposal(
        base_graph_version=1,
        decision=PlanEvaluationDecision.ADAPT_PLAN,
        trigger=AdaptationTrigger.TEST_FAILURE,
        reason="Re-tentativa de estratégia repetida.",
        added_tasks=[{"task_id": "test_patch", "title": "Test Patch"}],
        evidence_ids=["ev_osc"],
    )
    fp = prop.compute_strategy_fingerprint()

    # Create history with 2 existing records with same fingerprint
    history = [
        {"strategy_fingerprint": fp, "adaptation_id": "ad_1"},
        {"strategy_fingerprint": fp, "adaptation_id": "ad_2"},
    ]

    valid, reason, _ = validator.validate_proposal(prop, graph, adaptation_history=history)
    assert valid is False
    assert "REJECTED_STRATEGY_OSCILLATION" in reason


# ── TEST J: ALTERNATING CYCLE OSCILLATION DETECTION (A -> B -> A) ────────────


def test_j_alternating_cycle_detection():
    validator = AdaptivePlanningValidator()
    graph = TaskGraph(nodes=[], graph_version=1)

    p_a = MissionAdaptationProposal(
        base_graph_version=1,
        decision=PlanEvaluationDecision.ADAPT_PLAN,
        trigger=AdaptationTrigger.UNEXPECTED_COMPLEXITY,
        reason="Estratégia A.",
        added_tasks=[{"task_id": "strat_a", "title": "Strategy A"}],
    )
    fp_a = p_a.compute_strategy_fingerprint()

    p_b = MissionAdaptationProposal(
        base_graph_version=1,
        decision=PlanEvaluationDecision.ADAPT_PLAN,
        trigger=AdaptationTrigger.UNEXPECTED_COMPLEXITY,
        reason="Estratégia B.",
        added_tasks=[{"task_id": "strat_b", "title": "Strategy B"}],
    )
    fp_b = p_b.compute_strategy_fingerprint()

    # History: [A, B] -> Current is A again
    history = [
        {"strategy_fingerprint": fp_a},
        {"strategy_fingerprint": fp_b},
    ]

    valid, reason, _ = validator.validate_proposal(p_a, graph, adaptation_history=history)
    assert valid is False
    assert "REJECTED_STRATEGY_OSCILLATION" in reason
    assert "Ciclo alternado" in reason


# ── TEST K: ADAPTATION BUDGET EXHAUSTION ──────────────────────────────────────


def test_k_adaptation_budget_exhaustion():
    budget = AdaptationBudget(max_plan_adaptations=3)
    validator = AdaptivePlanningValidator(budget=budget)
    graph = TaskGraph(nodes=[], graph_version=1)

    history = [
        {"strategy_fingerprint": f"fp_{i}", "decision": "ADAPT_PLAN"}
        for i in range(3)
    ]

    prop = MissionAdaptationProposal(
        base_graph_version=1,
        decision=PlanEvaluationDecision.ADAPT_PLAN,
        trigger=AdaptationTrigger.RUNTIME_FAILURE,
        reason="Proposta após orçamento esgotado.",
        evidence_ids=["ev_bud"],
    )
    valid, reason, _ = validator.validate_proposal(prop, graph, adaptation_history=history)
    assert valid is False
    assert "BUDGET_EXCEEDED" in reason


# ── TEST L: GRAPH CHURN LIMIT ENFORCEMENT ────────────────────────────────────


def test_l_graph_churn_limit_enforcement():
    budget = AdaptationBudget(max_graph_churn=5)
    validator = AdaptivePlanningValidator(budget=budget)
    graph = TaskGraph(nodes=[], graph_version=1)

    # Adding 6 tasks exceeds max_graph_churn of 5
    prop = MissionAdaptationProposal(
        base_graph_version=1,
        decision=PlanEvaluationDecision.ADAPT_PLAN,
        trigger=AdaptationTrigger.NEW_REQUIREMENT,
        reason="Adicionar 6 tarefas duma vez.",
        added_tasks=[{"task_id": f"t_{i}", "title": f"T {i}"} for i in range(6)],
    )
    valid, reason, _ = validator.validate_proposal(prop, graph)
    assert valid is False
    assert "CHURN_LIMIT_EXCEEDED" in reason


# ── TEST M: REPLAN BUDGET EXHAUSTION ─────────────────────────────────────────


def test_m_replan_budget_exhaustion():
    budget = AdaptationBudget(max_replans=1)
    validator = AdaptivePlanningValidator(budget=budget)
    graph = TaskGraph(nodes=[], graph_version=1)

    history = [
        {"strategy_fingerprint": "fp_0", "decision": "REPLAN"}
    ]

    prop = MissionAdaptationProposal(
        base_graph_version=1,
        decision=PlanEvaluationDecision.REPLAN,
        trigger=AdaptationTrigger.GOAL_OBSOLETED,
        reason="Segundo replan não permitido pelo orçamento.",
    )
    valid, reason, _ = validator.validate_proposal(prop, graph, adaptation_history=history)
    assert valid is False
    assert "REPLAN_BUDGET_EXCEEDED" in reason


# ── TEST N: MISSING REASON REJECTION ─────────────────────────────────────────


def test_n_missing_reason_rejection():
    validator = AdaptivePlanningValidator()
    graph = TaskGraph(nodes=[], graph_version=1)
    prop = MissionAdaptationProposal(
        base_graph_version=1,
        decision=PlanEvaluationDecision.ADAPT_PLAN,
        trigger=AdaptationTrigger.HUMAN_INTERVENTION,
        reason="curto",  # Less than 10 characters!
    )
    valid, reason, _ = validator.validate_proposal(prop, graph)
    assert valid is False
    assert "MISSING_REASON" in reason


# ── TEST O: UNALLOWED TRIGGER REJECTION ──────────────────────────────────────


def test_o_unallowed_trigger_rejection():
    validator = AdaptivePlanningValidator()
    graph = TaskGraph(nodes=[], graph_version=1)
    prop = MissionAdaptationProposal(
        base_graph_version=1,
        decision=PlanEvaluationDecision.ADAPT_PLAN,
        trigger="INVALID_TRIGGER_UNKNOWN",  # type: ignore
        reason="Gatilho não documentado na taxonomia.",
        evidence_ids=["ev_1"],
    )
    valid, reason, _ = validator.validate_proposal(prop, graph)
    assert valid is False
    assert "INVALID_TRIGGER" in reason


# ── TEST P: MISSING EVIDENCE ON VALIDATION FAILURE TRIGGER ───────────────────


def test_p_missing_evidence_on_validation_failure():
    validator = AdaptivePlanningValidator()
    graph = TaskGraph(nodes=[], graph_version=1)
    prop = MissionAdaptationProposal(
        base_graph_version=1,
        decision=PlanEvaluationDecision.ADAPT_PLAN,
        trigger=AdaptationTrigger.VALIDATION_FAILURE,
        reason="Validação falhou mas não enviamos evidência nenhuma.",
        evidence_ids=[],  # Empty!
    )
    valid, reason, _ = validator.validate_proposal(prop, graph)
    assert valid is False
    assert "EVIDENCE_REQUIRED" in reason


# ── TEST Q: SCOPE ESCALATION REJECTION ───────────────────────────────────────


def test_q_scope_escalation_rejection():
    validator = AdaptivePlanningValidator()
    graph = TaskGraph(nodes=[], graph_version=1)
    prop = MissionAdaptationProposal(
        base_graph_version=1,
        decision=PlanEvaluationDecision.ADAPT_PLAN,
        trigger=AdaptationTrigger.NEW_REQUIREMENT,
        reason="Tentativa de alterar escopo fora dos limites permitidos.",
        requested_scope="FULL_SYSTEM_ROOT_TAKEOVER_ESCALATION",
    )
    valid, reason, _ = validator.validate_proposal(prop, graph)
    assert valid is False
    assert "SCOPE_ESCALATION_FORBIDDEN" in reason


# ── TEST R: PRESERVED TASKS TRACKING AND VERIFICATION ────────────────────────


def test_r_preserved_tasks_tracking():
    validator = AdaptivePlanningValidator()
    graph = TaskGraph(
        nodes=[
            TaskNode(task_id="t1", title="Task 1", status=TaskStatus.COMPLETED),
            TaskNode(task_id="t2", title="Task 2", status=TaskStatus.PENDING),
            TaskNode(task_id="t3", title="Task 3", status=TaskStatus.READY),
        ],
        graph_version=1,
    )
    prop = MissionAdaptationProposal(
        base_graph_version=1,
        decision=PlanEvaluationDecision.ADAPT_PLAN,
        trigger=AdaptationTrigger.NEW_REQUIREMENT,
        reason="Adicionar tarefa t4 preservando t1, t2 e t3.",
        added_tasks=[{"task_id": "t4", "title": "Task 4"}],
    )
    valid, reason, trial = validator.validate_proposal(prop, graph)
    assert valid is True
    preserved = validator.get_preserved_task_ids(prop, graph)
    assert set(preserved) == {"t1", "t2", "t3"}


# ── TEST S: ECONOMIC MISSION CANNOT BYPASS GATES ─────────────────────────────


def test_s_economic_mission_gate_bypass_rejection():
    validator = AdaptivePlanningValidator()
    graph = TaskGraph(nodes=[], graph_version=1)
    prop = MissionAdaptationProposal(
        base_graph_version=1,
        decision=PlanEvaluationDecision.ADAPT_PLAN,
        trigger=AdaptationTrigger.NEW_REQUIREMENT,
        reason="Tentar pular verificação de pagamento bypass human approval gate.",
        is_economic=True,
        added_tasks=[{"task_id": "pay_bypass", "title": "Bypass gate"}],
    )
    valid, reason, _ = validator.validate_proposal(prop, graph)
    assert valid is False
    assert "ECONOMIC_GATE_BYPASS_FORBIDDEN" in reason


# ── TEST T: ECONOMIC MISSION CANNOT REMOVE EVIDENCE REQUIREMENTS ─────────────


def test_t_economic_mission_evidence_removal_rejection():
    validator = AdaptivePlanningValidator()
    graph = TaskGraph(nodes=[], graph_version=1)
    prop = MissionAdaptationProposal(
        base_graph_version=1,
        decision=PlanEvaluationDecision.ADAPT_PLAN,
        trigger=AdaptationTrigger.NEW_REQUIREMENT,
        reason="Remover critério de prova e reconciliação financeira.",
        is_economic=True,
        acceptance_criteria_changes=[{"action": "remove", "criterion_id": "crit_audit"}],
    )
    valid, reason, _ = validator.validate_proposal(prop, graph)
    assert valid is False
    assert "ECONOMIC_EVIDENCE_REMOVAL_FORBIDDEN" in reason


# ── TEST U: ECONOMIC MISSION CANNOT INVENT PHANTOM REVENUE ───────────────────


def test_u_economic_mission_phantom_revenue_rejection():
    validator = AdaptivePlanningValidator()
    graph = TaskGraph(nodes=[], graph_version=1)
    prop = MissionAdaptationProposal(
        base_graph_version=1,
        decision=PlanEvaluationDecision.ADAPT_PLAN,
        trigger=AdaptationTrigger.NEW_REQUIREMENT,
        reason="Inventar receita fictícia de €50.000 sem liquidação externa comprovada.",
        is_economic=True,
    )
    valid, reason, _ = validator.validate_proposal(prop, graph)
    assert valid is False
    assert "ECONOMIC_PHANTOM_REVENUE_FORBIDDEN" in reason


# ── TEST V: PLAN QUALITY METRICS COMPUTATION ─────────────────────────────────


def test_v_plan_quality_metrics_computation():
    engine = AdaptivePlanningEngine()
    graph = TaskGraph(
        nodes=[
            TaskNode(task_id="t1", title="T1", status=TaskStatus.COMPLETED),
            TaskNode(task_id="t2", title="T2", status=TaskStatus.FAILED, required=True),
            TaskNode(task_id="t3", title="T3", status=TaskStatus.BLOCKED, dependencies=["t2"], required=True),
        ],
        graph_version=2,
    )
    obs = [
        Observation(source=ObservationSource.TEST, event="Fail 1", severity=ObservationSeverity.HIGH),
        Observation(source=ObservationSource.BUILD, event="Warn 1", severity=ObservationSeverity.LOW),
    ]
    metrics = engine.compute_plan_quality_metrics(graph, obs)
    assert metrics.total_tasks == 3
    assert metrics.completed_tasks == 1
    assert metrics.failed_tasks == 1
    assert metrics.blocked_tasks == 1
    assert metrics.observation_severity_score == 3.5  # HIGH (3.0) + LOW (0.5)
    assert metrics.unrecoverable_blockage is True


# ── TEST W: OBSERVATION SEVERITY IMPACT ──────────────────────────────────────


def test_w_observation_severity_impact():
    engine = AdaptivePlanningEngine()
    graph = TaskGraph(
        nodes=[TaskNode(task_id="t1", title="T1", status=TaskStatus.READY)],
        graph_version=1,
    )
    # Low severity observations do not trigger adaptation
    low_obs = [Observation(source=ObservationSource.BUILD, event="Minor lint warning", severity=ObservationSeverity.LOW)]
    eval_low = engine.evaluate_plan(graph, low_obs)
    assert eval_low.decision == PlanEvaluationDecision.KEEP_PLAN

    # Critical severity observation triggers adaptation or replan
    crit_obs = [Observation(source=ObservationSource.RUNTIME, event="Fatal DB corruption", severity=ObservationSeverity.CRITICAL)]
    eval_crit = engine.evaluate_plan(graph, crit_obs)
    assert eval_crit.decision in {PlanEvaluationDecision.ADAPT_PLAN, PlanEvaluationDecision.REPLAN}


# ── TEST X: PLAN EVALUATION DECISION RULES ───────────────────────────────────


def test_x_plan_evaluation_decision_rules():
    engine = AdaptivePlanningEngine()

    # 1. Healthy graph -> KEEP_PLAN
    healthy_graph = TaskGraph(
        nodes=[
            TaskNode(task_id="t1", title="T1", status=TaskStatus.COMPLETED),
            TaskNode(task_id="t2", title="T2", status=TaskStatus.READY),
        ],
        graph_version=1,
    )
    res_healthy = engine.evaluate_plan(healthy_graph, [])
    assert res_healthy.decision == PlanEvaluationDecision.KEEP_PLAN

    # 2. Permanent failure on critical node -> ADAPT_PLAN / REPLAN
    fail_graph = TaskGraph(
        nodes=[
            TaskNode(task_id="t1", title="T1", status=TaskStatus.FAILED, required=True),
        ],
        graph_version=1,
    )
    fail_info = FailureInfo(
        category=FailureCategory.PERMANENT_FAILURE,
        message="Node server died",
        timestamp="2026-09-02T21:00:00Z",
        attempt=3,
    )
    res_fail = engine.evaluate_plan(fail_graph, [], failure_info=fail_info)
    assert res_fail.decision in {PlanEvaluationDecision.ADAPT_PLAN, PlanEvaluationDecision.REPLAN}
    assert res_fail.trigger == AdaptationTrigger.RUNTIME_FAILURE
    assert "t1" in res_fail.affected_tasks

    # 3. Budget exhausted -> BLOCK_MISSION
    budget_exhausted_engine = AdaptivePlanningEngine(budget=AdaptationBudget(max_plan_adaptations=1))
    history = [{"strategy_fingerprint": "f1", "decision": "ADAPT_PLAN"}]
    res_blocked = budget_exhausted_engine.evaluate_plan(fail_graph, [], failure_info=fail_info, adaptation_history=history)
    assert res_blocked.decision == PlanEvaluationDecision.BLOCK_MISSION
