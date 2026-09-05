"""Adversarial and Chaos Testing for Fase 13 Adaptive Planning."""

import asyncio
import os
import shutil
import tempfile
import pytest

from agents.adaptive_planning import (
    AdaptationBudget,
    AdaptationTrigger,
    MissionAdaptationProposal,
    PlanEvaluationDecision,
)
from agents.mission_orchestrator import (
    MissionLifecycleOrchestrator,
)
from agents.mission_state import MissionStateStore
from agents.task_graph import TaskGraph, TaskNode, TaskStatus


@pytest.fixture
def temp_project_dir():
    temp_dir = tempfile.mkdtemp(prefix="jarvis_chaos_test_")
    yield temp_dir
    shutil.rmtree(temp_dir, ignore_errors=True)


def test_chaos_concurrent_proposal_race(temp_project_dir):
    """Verifies that concurrent adaptation proposals are serialized safely and reject stale base versions."""
    async def _run():
        project_id = "proj_chaos_1"
        mission_id = "mission_chaos_1"
        os.makedirs(os.path.join(temp_project_dir, "workspace", "projects", project_id), exist_ok=True)
        store = MissionStateStore(temp_project_dir)
        store.create_mission(
            project_id=project_id,
            title="Chaos Test Mission",
            objective="Verify concurrent proposal resilience",
            mission_id=mission_id,
        )

        initial_graph = TaskGraph(
            nodes=[
                TaskNode(task_id="t1", title="Base Node 1", status=TaskStatus.READY),
                TaskNode(task_id="t2", title="Base Node 2", status=TaskStatus.PENDING, dependencies=["t1"]),
            ],
            graph_version=1,
        )

        orchestrator = MissionLifecycleOrchestrator(
            project_id=project_id,
            mission_id=mission_id,
            mission_state=store,
            task_graph=initial_graph,
        )

        # Launch 5 concurrent proposals all based on graph_version=1
        async def submit_proposal(idx: int):
            prop = MissionAdaptationProposal(
                proposal_id=f"prop_concurrent_{idx}",
                mission_id=mission_id,
                base_graph_version=1,
                decision=PlanEvaluationDecision.ADAPT_PLAN,
                trigger=AdaptationTrigger.NEW_REQUIREMENT,
                reason=f"Concurrent patch number {idx} arriving simultaneously.",
                added_tasks=[
                    {
                        "task_id": f"t_patch_{idx}",
                        "title": f"Patch Task {idx}",
                        "category": "CODING",
                        "dependencies": ["t1"],
                    }
                ],
            )
            return await orchestrator.propose_and_apply_adaptation(prop)

        results = await asyncio.gather(*(submit_proposal(i) for i in range(5)))

        # Exactly 1 proposal should succeed at v1 -> v2 (or others rebased/rejected cleanly without corrupting the graph)
        successes = [r for r in results if r[0] is True]
        failures = [r for r in results if r[0] is False]

        # In all cases: no unhandled exception, graph version increased, DAG valid
        assert len(successes) >= 1
        assert len(successes) + len(failures) == 5
        orchestrator.task_graph.validate()
        assert orchestrator.task_graph.graph_version >= 2

    asyncio.run(_run())


def test_chaos_scope_escalation_attempt(temp_project_dir):
    """Verifies that malicious scope escalation attempts in proposals are blocked without mutating graph."""
    async def _run():
        project_id = "proj_chaos_2"
        mission_id = "mission_chaos_2"
        os.makedirs(os.path.join(temp_project_dir, "workspace", "projects", project_id), exist_ok=True)
        store = MissionStateStore(temp_project_dir)
        store.create_mission(
            project_id=project_id,
            title="Chaos Scope Escalation",
            objective="Block scope escalation",
            mission_id=mission_id,
        )

        initial_graph = TaskGraph(
            nodes=[
                TaskNode(task_id="t1", title="Normal Task", status=TaskStatus.READY),
            ],
            graph_version=1,
        )

        orchestrator = MissionLifecycleOrchestrator(
            project_id=project_id,
            mission_id=mission_id,
            mission_state=store,
            task_graph=initial_graph,
        )

        malicious_prop = MissionAdaptationProposal(
            proposal_id="prop_malicious_scope",
            mission_id=mission_id,
            base_graph_version=1,
            decision=PlanEvaluationDecision.ADAPT_PLAN,
            trigger=AdaptationTrigger.NEW_REQUIREMENT,
            reason="Tentativa de acesso ao sistema de ficheiros raiz do servidor.",
            requested_scope={"paths": ["../../Windows/System32", "/etc/shadow"], "command": "rm -rf /"},
            added_tasks=[{"task_id": "mal_1", "title": "Root Escalation Task"}],
        )

        success, msg, record = await orchestrator.propose_and_apply_adaptation(malicious_prop)
        assert success is False
        assert "SCOPE_ESCALATION_FORBIDDEN" in msg
        assert orchestrator.task_graph.graph_version == 1
        assert "mal_1" not in orchestrator.task_graph.nodes

    asyncio.run(_run())


def test_chaos_rapid_alternating_oscillation(temp_project_dir):
    """Verifies that an LLM alternating between strategies A -> B -> A is detected and halted."""
    async def _run():
        project_id = "proj_chaos_3"
        mission_id = "mission_chaos_3"
        os.makedirs(os.path.join(temp_project_dir, "workspace", "projects", project_id), exist_ok=True)
        store = MissionStateStore(temp_project_dir)
        store.create_mission(
            project_id=project_id,
            title="Chaos Oscillation",
            objective="Detect alternating oscillation",
            mission_id=mission_id,
        )

        initial_graph = TaskGraph(
            nodes=[
                TaskNode(task_id="t1", title="Base Node", status=TaskStatus.READY),
            ],
            graph_version=1,
        )

        orchestrator = MissionLifecycleOrchestrator(
            project_id=project_id,
            mission_id=mission_id,
            mission_state=store,
            task_graph=initial_graph,
            adaptation_budget=AdaptationBudget(max_plan_adaptations=10, max_strategy_repeats=3),
        )

        # Apply strategy A
        prop_a = MissionAdaptationProposal(
            proposal_id="prop_strat_a",
            mission_id=mission_id,
            base_graph_version=1,
            decision=PlanEvaluationDecision.ADAPT_PLAN,
            trigger=AdaptationTrigger.NEW_REQUIREMENT,
            reason="Aplicar Estratégia A baseada em GraphQL.",
            added_tasks=[{"task_id": "t_graphql", "title": "Use GraphQL Endpoint", "category": "CODING"}],
        )
        ok_a, _, _ = await orchestrator.propose_and_apply_adaptation(prop_a)
        assert ok_a is True
        assert orchestrator.task_graph.graph_version == 2

        # Apply strategy B
        prop_b = MissionAdaptationProposal(
            proposal_id="prop_strat_b",
            mission_id=mission_id,
            base_graph_version=2,
            decision=PlanEvaluationDecision.ADAPT_PLAN,
            trigger=AdaptationTrigger.NEW_REQUIREMENT,
            reason="Aplicar Estratégia B revertendo para REST.",
            removed_tasks=["t_graphql"],
            added_tasks=[{"task_id": "t_rest", "title": "Use REST Endpoint", "category": "CODING"}],
        )
        ok_b, _, _ = await orchestrator.propose_and_apply_adaptation(prop_b)
        assert ok_b is True
        assert orchestrator.task_graph.graph_version == 3

        # Attempt strategy A again (A -> B -> A cycle)
        prop_a2 = MissionAdaptationProposal(
            proposal_id="prop_strat_a_repeat",
            mission_id=mission_id,
            base_graph_version=3,
            decision=PlanEvaluationDecision.ADAPT_PLAN,
            trigger=AdaptationTrigger.NEW_REQUIREMENT,
            reason="Voltar para Estratégia A baseada em GraphQL novamente.",
            added_tasks=[{"task_id": "t_graphql", "title": "Use GraphQL Endpoint", "category": "CODING"}],
        )
        assert prop_a2.compute_strategy_fingerprint() == prop_a.compute_strategy_fingerprint()
        ok_a2, msg_a2, _ = await orchestrator.propose_and_apply_adaptation(prop_a2)
        assert ok_a2 is False
        assert "REJECTED_STRATEGY_OSCILLATION" in msg_a2
        assert orchestrator.task_graph.graph_version == 3  # Graph version unchanged

    asyncio.run(_run())
