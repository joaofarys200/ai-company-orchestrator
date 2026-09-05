"""Long-horizon mission execution and multi-stage adaptation test for Fase 13."""

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
from agents.task_graph import TaskGraph, TaskNode, TaskStatus


@pytest.fixture
def temp_project_dir():
    temp_dir = tempfile.mkdtemp(prefix="jarvis_long_horizon_")
    yield temp_dir
    shutil.rmtree(temp_dir, ignore_errors=True)


def test_long_horizon_adaptive_mission_lifecycle(temp_project_dir):
    """Executes a multi-stage long-horizon mission with observations, adaptations, replanning, and satisfaction."""
    async def _run():
        project_id = "proj_lh_1"
        mission_id = "mission_lh_1"
        os.makedirs(os.path.join(temp_project_dir, "workspace", "projects", project_id), exist_ok=True)
        store = MissionStateStore(temp_project_dir)
        store.create_mission(
            project_id=project_id,
            title="Long Horizon Adaptive Mission",
            objective="Build and deploy full-stack e-commerce with adaptive fault recovery",
            mission_id=mission_id,
        )

        events_captured = []

        async def event_callback(event_type, payload):
            events_captured.append((event_type, payload))

        # Initial DAG v1:
        # t1 (Init Repo) -> t2 (Data Models) -> t3 (API Endpoints) -> t4 (End-to-End Tests)
        t1 = TaskNode(task_id="t1", title="Init Repository", category="SETUP", status=TaskStatus.COMPLETED)
        t2 = TaskNode(task_id="t2", title="Define Data Models", category="CODING", dependencies=["t1"], status=TaskStatus.COMPLETED)
        t3 = TaskNode(task_id="t3", title="Implement API Endpoints", category="CODING", dependencies=["t2"], status=TaskStatus.READY)
        t4 = TaskNode(task_id="t4", title="Run E2E Tests", category="TEST", dependencies=["t3"], status=TaskStatus.PENDING)

        initial_graph = TaskGraph(nodes=[t1, t2, t3, t4], graph_version=1)

        budget = AdaptationBudget(max_plan_adaptations=5, max_replans=2, max_graph_churn=25)

        orchestrator = MissionLifecycleOrchestrator(
            project_id=project_id,
            mission_id=mission_id,
            mission_state=store,
            task_graph=initial_graph,
            adaptation_budget=budget,
            callbacks=event_callback,
        )

        # ── STAGE 1: LOCAL RUNTIME FAILURE & ADAPTATION ──
        # During execution of t3, external payment gateway SDK fails
        obs1 = Observation(
            source=ObservationSource.RUNTIME,
            event="Stripe API SDK v1 deprecated endpoint rejected with 410 Gone",
            task_id="t3",
            severity=ObservationSeverity.HIGH,
            evidence_id="ev_stripe_error",
        )
        orchestrator.record_observation(obs1)

        # Plan evaluation recommends ADAPT_PLAN
        eval_1 = await orchestrator.evaluate_plan()
        assert eval_1.decision in {PlanEvaluationDecision.ADAPT_PLAN, PlanEvaluationDecision.REPLAN}

        # Formulate adaptation: insert t3_patch (Update Stripe SDK) before t3
        prop_1 = MissionAdaptationProposal(
            proposal_id="prop_stripe_upgrade",
            mission_id=mission_id,
            base_graph_version=1,
            decision=PlanEvaluationDecision.ADAPT_PLAN,
            trigger=AdaptationTrigger.RUNTIME_FAILURE,
            reason="Atualizar SDK de pagamentos Stripe para versão estável v2.",
            added_tasks=[
                {
                    "task_id": "t3_patch",
                    "title": "Upgrade Stripe SDK",
                    "category": "CODING",
                    "dependencies": ["t2"],
                }
            ],
            changed_edges=[("t3_patch", "t3")],
            evidence_ids=["ev_stripe_error"],
        )
        ok_1, msg_1, rec_1 = await orchestrator.propose_and_apply_adaptation(prop_1)
        assert ok_1 is True
        assert orchestrator.task_graph.graph_version == 2
        assert orchestrator.plan_version == 2
        assert "t3_patch" in orchestrator.task_graph.nodes
        assert "t3_patch" in orchestrator.task_graph.nodes["t3"].dependencies

        # ── STAGE 2: EXECUTION PROGRESS & COMPLETION OF PATCH ──
        orchestrator.task_graph.nodes["t3_patch"].status = TaskStatus.COMPLETED
        orchestrator.task_graph.nodes["t3"].status = TaskStatus.COMPLETED

        # ── STAGE 3: ARCHITECTURE DISCOVERY & REPLAN ──
        # User adds compliance requirement: GDPR data retention policy requires separate audit DB
        arch_discovery = {
            "summary": "GDPR Compliance requires dedicated Audit Log Service and separate schema",
            "affected_tasks": ["t4"],
        }
        eval_2 = await orchestrator.evaluate_plan(architecture_change=arch_discovery)
        assert eval_2.decision == PlanEvaluationDecision.REPLAN
        assert eval_2.trigger == AdaptationTrigger.ARCHITECTURE_DISCOVERY

        prop_2 = MissionAdaptationProposal(
            proposal_id="prop_gdpr_replan",
            mission_id=mission_id,
            base_graph_version=2,
            decision=PlanEvaluationDecision.REPLAN,
            trigger=AdaptationTrigger.ARCHITECTURE_DISCOVERY,
            reason="Adição mandatória de serviço de auditoria GDPR antes dos testes E2E finais.",
            added_tasks=[
                {
                    "task_id": "t4_audit",
                    "title": "Implement GDPR Audit Service",
                    "category": "CODING",
                    "dependencies": ["t3"],
                },
                {
                    "task_id": "t5_e2e_compliance",
                    "title": "E2E Integration & Compliance Verification",
                    "category": "TEST",
                    "dependencies": ["t4_audit"],
                },
            ],
            removed_tasks=["t4"],
        )

        ok_2, msg_2, rec_2 = await orchestrator.propose_and_apply_adaptation(prop_2)
        assert ok_2 is True
        assert orchestrator.task_graph.graph_version == 3
        assert orchestrator.plan_version == 3
        assert "t4" not in orchestrator.task_graph.nodes
        assert "t4_audit" in orchestrator.task_graph.nodes
        assert "t5_e2e_compliance" in orchestrator.task_graph.nodes

        # ── STAGE 4: CHECKPOINT & CRASH RECOVERY ──
        cp = orchestrator.save_checkpoint("Midway long-horizon execution")
        assert cp.graph_version == 3

        reconstructed = MissionLifecycleOrchestrator(
            project_id=project_id,
            mission_id=mission_id,
            mission_state=store,
        )
        loaded_cp = reconstructed.load_latest_checkpoint()
        assert loaded_cp is not None
        reconstructed.recover_from_checkpoint(loaded_cp)
        assert reconstructed.task_graph.graph_version == 3
        assert "t4_audit" in reconstructed.task_graph.nodes

        # ── STAGE 5: FINAL SATISFACTION VERIFICATION ──
        # Complete remaining nodes
        reconstructed.task_graph.nodes["t4_audit"].status = TaskStatus.COMPLETED
        reconstructed.task_graph.nodes["t5_e2e_compliance"].status = TaskStatus.COMPLETED

        satisfied, reason = await reconstructed.verify_satisfaction()
        assert satisfied is True
        assert "satisfeitos" in reason

    asyncio.run(_run())
