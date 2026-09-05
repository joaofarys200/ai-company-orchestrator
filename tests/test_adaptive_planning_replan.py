"""Tests for Full Replan capabilities in Fase 13 Adaptive Planning."""

import asyncio
import os
import shutil
import tempfile
import pytest

from agents.adaptive_planning import (
    AdaptationBudget,
    AdaptationTrigger,
    MissionAdaptationProposal,
    Observation,
    ObservationSeverity,
    ObservationSource,
    PlanEvaluationDecision,
)
from agents.mission_orchestrator import (
    MissionLifecycleOrchestrator,
)
from agents.mission_state import MissionStateStore
from agents.task_graph import FailureCategory, FailureInfo, TaskGraph, TaskNode, TaskStatus


@pytest.fixture
def temp_project_dir():
    temp_dir = tempfile.mkdtemp(prefix="jarvis_replan_test_")
    yield temp_dir
    shutil.rmtree(temp_dir, ignore_errors=True)


def test_replan_on_architecture_discovery(temp_project_dir):
    """Verifies that an architecture discovery triggers REPLAN and rewires DAG while preserving completed tasks."""
    async def _run():
        project_id = "proj_replan_1"
        mission_id = "mission_replan_1"
        os.makedirs(os.path.join(temp_project_dir, "workspace", "projects", project_id), exist_ok=True)
        store = MissionStateStore(temp_project_dir)
        store.create_mission(
            project_id=project_id,
            title="Replan Test Mission",
            objective="Test replanning on architecture discovery",
            mission_id=mission_id,
        )

        events_captured = []

        async def event_callback(event_type, payload):
            events_captured.append((event_type, payload))

        # Initial graph:
        # t1 (COMPLETED) -> t2_sqlite (FAILED) -> t3_query (PENDING)
        t1 = TaskNode(task_id="t1", title="Setup Environment", category="SETUP", status=TaskStatus.COMPLETED)
        t2_sqlite = TaskNode(task_id="t2_sqlite", title="Setup SQLite Storage", category="CODING", dependencies=["t1"], status=TaskStatus.FAILED, required=True)
        t3_query = TaskNode(task_id="t3_query", title="Execute SQLite Queries", category="CODING", dependencies=["t2_sqlite"], status=TaskStatus.PENDING)

        initial_graph = TaskGraph(nodes=[t1, t2_sqlite, t3_query], graph_version=1)

        budget = AdaptationBudget(max_plan_adaptations=5, max_replans=2, max_graph_churn=20)

        orchestrator = MissionLifecycleOrchestrator(
            project_id=project_id,
            mission_id=mission_id,
            mission_state=store,
            task_graph=initial_graph,
            adaptation_budget=budget,
            callbacks=event_callback,
        )

        # 1. Architecture discovery: SQLite unsupported in distributed production cluster; must switch to PostgreSQL
        arch_change = {
            "summary": "Distributed environment requires PostgreSQL cluster instead of single-file SQLite",
            "affected_tasks": ["t2_sqlite", "t3_query"],
        }
        eval_res = await orchestrator.evaluate_plan(architecture_change=arch_change)
        assert eval_res.decision == PlanEvaluationDecision.REPLAN
        assert eval_res.trigger == AdaptationTrigger.ARCHITECTURE_DISCOVERY
        assert "t2_sqlite" in eval_res.affected_tasks

        # 2. Formulate REPLAN proposal:
        # Preserve t1 (COMPLETED)
        # Remove t2_sqlite, t3_query
        # Add t2_pg (Postgres Setup), t3_pg (Postgres Queries)
        proposal = MissionAdaptationProposal(
            proposal_id="prop_replan_pg",
            mission_id=mission_id,
            base_graph_version=1,
            decision=PlanEvaluationDecision.REPLAN,
            trigger=AdaptationTrigger.ARCHITECTURE_DISCOVERY,
            reason="Substituição total de infraestrutura de dados de SQLite para PostgreSQL após descoberta de clustering.",
            removed_tasks=["t2_sqlite", "t3_query"],
            added_tasks=[
                {
                    "task_id": "t2_pg",
                    "title": "Setup PostgreSQL Cluster",
                    "category": "CODING",
                    "dependencies": ["t1"],
                },
                {
                    "task_id": "t3_pg",
                    "title": "Execute Postgres Queries",
                    "category": "CODING",
                    "dependencies": ["t2_pg"],
                },
            ],
            changed_edges=[("t1", "t2_pg"), ("t2_pg", "t3_pg")],
        )

        # 3. Apply Replan
        applied, msg, record = await orchestrator.propose_and_apply_adaptation(proposal)
        assert applied is True
        assert record is not None
        assert record.decision == "REPLAN"
        assert record.graph_version_before == 1
        assert record.graph_version_after == 2

        # 4. Verify preserved tasks and newly wired DAG
        assert "t1" in orchestrator.task_graph.nodes
        assert orchestrator.task_graph.nodes["t1"].status == TaskStatus.COMPLETED
        assert "t2_sqlite" not in orchestrator.task_graph.nodes
        assert "t3_query" not in orchestrator.task_graph.nodes
        assert "t2_pg" in orchestrator.task_graph.nodes
        assert "t3_pg" in orchestrator.task_graph.nodes
        assert orchestrator.task_graph.nodes["t2_pg"].dependencies == ["t1"]
        assert orchestrator.task_graph.nodes["t3_pg"].dependencies == ["t2_pg"]

        # 5. Verify telemetry events
        event_names = [e[0] for e in events_captured]
        assert "replan_started" in event_names
        assert "adaptation_accepted" in event_names
        assert "graph_version_changed" in event_names
        assert "replan_completed" in event_names

        # 6. Verify replan budget tracked
        replan_count = sum(1 for r in store.load_adaptation_history(project_id, mission_id) if r.get("decision") == "REPLAN")
        assert replan_count == 1

    asyncio.run(_run())
