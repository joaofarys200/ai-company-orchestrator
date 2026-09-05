"""Integration tests for Fase 13 Adaptive Planning with MissionLifecycleOrchestrator and MissionStateStore."""

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
    MissionLifecycleStatus,
)
from agents.mission_state import MissionStateStore
from agents.task_graph import FailureCategory, FailureInfo, TaskGraph, TaskNode, TaskStatus


@pytest.fixture
def temp_project_dir():
    temp_dir = tempfile.mkdtemp(prefix="jarvis_ap_test_")
    yield temp_dir
    shutil.rmtree(temp_dir, ignore_errors=True)


def test_adaptive_planning_orchestrator_integration(temp_project_dir):
    """Verifies that an orchestrator can record observations, evaluate plans, and apply adaptations."""
    async def _run():
        project_id = "proj_ap_1"
        mission_id = "mission_ap_1"
        os.makedirs(os.path.join(temp_project_dir, "workspace", "projects", project_id), exist_ok=True)
        store = MissionStateStore(temp_project_dir)
        store.create_mission(
            project_id=project_id,
            title="Adaptive Test Mission",
            objective="Verify adaptive planning",
            mission_id=mission_id,
        )

        events_captured = []

        async def event_callback(event_type, payload):
            events_captured.append((event_type, payload))

        # Initial graph: t1 -> t2
        t1 = TaskNode(task_id="t1", title="Setup Database", category="CODING", status=TaskStatus.READY)
        t2 = TaskNode(task_id="t2", title="Seed Database", category="CODING", dependencies=["t1"], status=TaskStatus.PENDING)
        initial_graph = TaskGraph(nodes=[t1, t2], graph_version=1)

        orchestrator = MissionLifecycleOrchestrator(
            project_id=project_id,
            mission_id=mission_id,
            mission_state=store,
            task_graph=initial_graph,
            callbacks=event_callback,
        )

        # 1. Record structured observation
        obs = Observation(
            source=ObservationSource.TEST,
            event="Database migrations failed due to schema mismatch",
            task_id="t1",
            severity=ObservationSeverity.HIGH,
            evidence_id="ev_mig_01",
        )
        orchestrator.record_observation(obs)
        assert len(orchestrator.observations) == 1

        # 2. Evaluate plan
        eval_res = await orchestrator.evaluate_plan()
        assert eval_res.decision in {PlanEvaluationDecision.ADAPT_PLAN, PlanEvaluationDecision.REPLAN}

        # 3. Propose and apply adaptation: add a migration fix task before t1
        proposal = MissionAdaptationProposal(
            proposal_id="prop_fix_mig",
            mission_id=mission_id,
            base_graph_version=1,
            decision=PlanEvaluationDecision.ADAPT_PLAN,
            trigger=AdaptationTrigger.TEST_FAILURE,
            reason="Adicionar tarefa de correção de migrações antes da configuração.",
            added_tasks=[
                {
                    "task_id": "t0_fix",
                    "title": "Fix Schema Migrations",
                    "category": "CODING",
                    "dependencies": [],
                }
            ],
            changed_edges=[("t0_fix", "t1")],
            evidence_ids=["ev_mig_01"],
        )

        success, msg, record = await orchestrator.propose_and_apply_adaptation(proposal)
        assert success is True
        assert record is not None
        assert record.graph_version_before == 1
        assert record.graph_version_after == 2
        assert orchestrator.task_graph.graph_version == 2
        assert orchestrator.plan_version == 2
        assert "t0_fix" in orchestrator.task_graph.nodes
        assert "t0_fix" in orchestrator.task_graph.nodes["t1"].dependencies

        # 4. Verify persistence in MissionStateStore
        history = store.load_adaptation_history(project_id, mission_id)
        assert len(history) == 1
        assert history[0]["proposal_id"] == "prop_fix_mig"
        assert history[0]["graph_version_after"] == 2

        # 5. Check checkpointing preserves adaptive planning state
        cp = orchestrator.save_checkpoint("After adaptive planning update")
        assert cp.graph_version == 2
        assert getattr(cp, "plan_version", 1) == 2
        assert len(getattr(cp, "adaptation_history", [])) == 1

        # 6. Verify crash recovery reconstructs plan_version and strategy
        reconstructed_orch = MissionLifecycleOrchestrator(
            project_id=project_id,
            mission_id=mission_id,
            mission_state=store,
        )
        latest_cp = reconstructed_orch.load_latest_checkpoint()
        assert latest_cp is not None
        reconstructed_orch.recover_from_checkpoint(latest_cp)
        assert reconstructed_orch.task_graph.graph_version == 2
        assert reconstructed_orch.plan_version == 2
        assert reconstructed_orch.plan_churn_count >= 1
        assert "t0_fix" in reconstructed_orch.task_graph.nodes

        # 7. Check emitted events
        event_names = [e[0] for e in events_captured]
        assert "plan_evaluation_started" in event_names
        assert "plan_evaluation_completed" in event_names
        assert "adaptation_proposed" in event_names
        assert "adaptation_validating" in event_names
        assert "adaptation_accepted" in event_names
        assert "graph_version_changed" in event_names

    asyncio.run(_run())
