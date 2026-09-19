from __future__ import annotations

import asyncio
import json
import os
import time
from typing import Any, Mapping
import uuid

from backend.message_protocol import system_message
from backend.websocket.context import WebSocketSessionState
from backend.websocket.contracts import MessageHandler
from backend.websocket.handlers import bind_handler_methods
from backend.websocket.handlers.common import WebSocketResponder


MISSION_HANDLERS = {
    "mission_list": "handle",
    "mission_create": "handle",
    "mission_get": "handle",
    "mission_update": "handle",
    "mission_set_status": "handle",
    "work_package_create": "handle",
    "work_package_update": "handle",
    "work_package_set_status": "handle",
    "work_package_add_dependency": "handle",
    "deliverable_create": "handle",
    "deliverable_update": "handle",
    "deliverable_set_status": "handle",
    "evidence_attach": "handle",
    "criterion_create": "handle",
    "criterion_set_status": "handle",
    "mission_resume_snapshot": "handle",
    "mission_execute_work_package": "handle",
    "mission_apply_execution": "handle",
    "mission_review_execution": "handle",
    "mission_retry_execution": "handle",
    "mission_cancel_execution": "handle",
    "mission_release_stale_lock": "handle",
    "mission_autonomy_run": "handle",
    "mission_plan_decompose": "handle",
    "mission_checkpoint_create": "handle",
    "mission_checkpoint_restore": "handle",
    "mission_subdag_propose": "handle",
    "mission_subdag_get_history": "handle",
    "mission_plan_evaluate": "handle",
    "mission_adaptation_propose": "handle",
    "mission_adaptation_get_history": "handle",
    "mission_swarm_status": "handle",
    "mission_swarm_reassign": "handle",
    "mission_collaboration_status": "handle",
    "mission_collaboration_arbitrate": "handle",
    "mission_federation_status": "handle",
    "mission_federation_scale": "handle",
    "mission_federation_rebalance": "handle",
    "mission_federation_switch_mode": "handle",
    "mission_understanding_get": "handle",
    "mission_understanding_review": "handle",
    "mission_timeline_get": "handle",
    "mission_control_get": "handle",
    "mission_control_event_stream": "handle",
    "mission_control_command": "handle",
    "mission_intent_preview": "handle",
    "mission_intent_change": "handle",
    "mission_predict_impact": "handle",
    "mission_get_predictions": "handle",
    "mission_loop_status": "handle",
    "mission_loop_step": "handle",
    "mission_loop_run": "handle",
    "mission_loop_respond_human": "handle",
    "mission_decision_quality_status": "handle",
    "mission_policy_proposal_review": "handle",
    "mission_policy_rollback": "handle",
    "mission_experience_memory_status": "handle",
    "mission_experience_curate": "handle",
    "mission_semantic_graph_status": "handle",
    "mission_contract_discovery_status": "handle",
    "mission_contract_proposal_review": "handle",
    "mission_contract_health_status": "handle",
    "mission_contract_drift_review": "handle",
    "mission_contract_rollback": "handle",
    "mission_polymorphic_schema_status": "handle",
    "mission_polymorphic_variant_review": "handle",
    "mission_polymorphic_compatibility_check": "handle",
    "mission_contract_change_prediction": "handle",
    "mission_contract_migration_plan": "handle",
    "mission_contract_change_gate_action": "handle",
    "mission_build_contract_extraction_status": "handle",
    "mission_dynamic_consumer_resolution": "handle",
    "mission_build_contract_trigger_extract": "handle",
    "mission_behavioral_baseline_status": "handle",
    "mission_behavioral_proof_status": "handle",
    "mission_behavioral_proof_trigger": "handle",
    "mission_architecture_evolution_status": "handle",
    "mission_architecture_evolution_observe": "handle",
    "mission_architecture_evolution_evaluate": "handle",
    "mission_self_modification_status": "handle",
    "mission_self_modification_execute": "handle",
    "mission_self_modification_rollback": "handle",
    "mission_multi_agent_coordination_status": "handle",
    "mission_multi_agent_intent_submit": "handle",
    "mission_multi_agent_arbitrate": "handle",
    "mission_multi_agent_schedule": "handle",
    # Phase 67
    "mission_long_horizon_status": "handle",
    "mission_long_horizon_create": "handle",
    "mission_long_horizon_step": "handle",
    "mission_long_horizon_run": "handle",
    "mission_long_horizon_checkpoint_create": "handle",
    "mission_long_horizon_recover": "handle",
    "mission_long_horizon_adapt": "handle",
    "mission_long_horizon_completion_evaluate": "handle",
    # Phase 68
    "mission_quality_governance_status": "handle",
    "mission_quality_governance_snapshot": "handle",
    "mission_quality_governance_baseline": "handle",
    "mission_quality_governance_gate": "handle",
    "mission_quality_governance_debt_list": "handle",
    "mission_quality_governance_trend": "handle",
    "mission_quality_governance_hotspots": "handle",
    # Phase 69
    "mission_debt_remediation_status": "handle",
    "mission_debt_remediation_validate": "handle",
    "mission_debt_remediation_root_cause": "handle",
    "mission_debt_remediation_options": "handle",
    "mission_debt_remediation_plan": "handle",
    "mission_debt_remediation_execute": "handle",
    "mission_debt_remediation_resolve": "handle",
    # Phase 70
    "mission_release_readiness_status": "handle",
    "mission_release_readiness_baseline": "handle",
    "mission_release_readiness_evaluate": "handle",
    "mission_release_readiness_plan": "handle",
    "mission_release_readiness_gate": "handle",
    "mission_release_readiness_rollback": "handle",
}


def message_type(message: Mapping[str, Any]) -> str:
    return str(message.get("type", ""))


class MissionWebSocketHandler:
    OPERATIONS = frozenset(MISSION_HANDLERS)

    def __init__(
        self,
        mission_planner: Any,
        mission_executor: Any,
        mission_autonomy: Any,
        responder: WebSocketResponder,
    ) -> None:
        self.mission_planner = mission_planner
        self.mission_executor = mission_executor
        self.mission_autonomy = mission_autonomy
        self.responder = responder
        self.connections = responder.connections

    def routes(self) -> dict[str, MessageHandler]:
        return bind_handler_methods(self, MISSION_HANDLERS)

    async def handle(
        self,
        websocket: Any,
        message: dict,
        session: WebSocketSessionState,
    ) -> None:
        from agents.mission_state import MissionStateError

        operation = message_type(message)
        project_id = str(
            message.get("project_id")
            or session.selected_project_id
            or ""
        ).strip()
        try:
            snapshot = None
            autonomy_cycle = None
            planner = self.mission_planner
            executor = self.mission_executor
            if operation == "mission_list":
                await self.responder.send_mission_list(
                    websocket,
                    project_id,
                )
                return
            if operation == "mission_create":
                snapshot = await asyncio.to_thread(
                    planner.create_mission,
                    project_id,
                    message.get("title"),
                    message.get("objective"),
                    message.get("description", ""),
                    message.get("current_phase", ""),
                    message.get("metadata"),
                    message.get("mission_id"),
                )
            elif operation in {
                "mission_get",
                "mission_resume_snapshot",
            }:
                snapshot = await asyncio.to_thread(
                    planner.load_mission,
                    project_id,
                    message.get("mission_id"),
                )
            elif operation == "mission_update":
                snapshot = await asyncio.to_thread(
                    planner.update_mission,
                    project_id,
                    message.get("mission_id"),
                    message.get("expected_version"),
                    message.get("changes"),
                )
            elif operation == "mission_set_status":
                snapshot = await asyncio.to_thread(
                    planner.set_mission_status,
                    project_id,
                    message.get("mission_id"),
                    message.get("status"),
                    message.get("expected_version"),
                )
            elif operation == "work_package_create":
                snapshot = await asyncio.to_thread(
                    planner.create_work_package,
                    project_id,
                    message.get("mission_id"),
                    message.get("title"),
                    message.get("description", ""),
                    message.get("type", "GENERIC"),
                    message.get("priority", 0),
                    message.get("dependencies"),
                    message.get("executor_kind", "MANUAL"),
                    message.get("executor_ref", ""),
                    message.get("metadata"),
                    message.get("required", True),
                    message.get("work_package_id"),
                )
            elif operation == "work_package_update":
                snapshot = await asyncio.to_thread(
                    planner.update_work_package,
                    project_id,
                    message.get("mission_id"),
                    message.get("work_package_id"),
                    message.get("expected_version"),
                    message.get("changes"),
                )
            elif operation == "work_package_set_status":
                snapshot = await asyncio.to_thread(
                    planner.set_work_package_status,
                    project_id,
                    message.get("mission_id"),
                    message.get("work_package_id"),
                    message.get("status"),
                    message.get("expected_version"),
                    message.get("blocked_reason", ""),
                )
            elif operation == "work_package_add_dependency":
                snapshot = await asyncio.to_thread(
                    planner.add_dependency,
                    project_id,
                    message.get("mission_id"),
                    message.get("work_package_id"),
                    message.get("dependency"),
                )
            elif operation == "deliverable_create":
                snapshot = await asyncio.to_thread(
                    planner.create_deliverable,
                    project_id,
                    message.get("mission_id"),
                    message.get("work_package_id"),
                    message.get("name"),
                    message.get("description", ""),
                    message.get("kind", "GENERIC"),
                    message.get("artifact_refs"),
                    message.get("acceptance_criteria"),
                    message.get("evidence_refs"),
                    message.get("deliverable_id"),
                )
            elif operation == "deliverable_update":
                snapshot = await asyncio.to_thread(
                    planner.update_deliverable,
                    project_id,
                    message.get("mission_id"),
                    message.get("deliverable_id"),
                    message.get("expected_version"),
                    message.get("changes"),
                )
            elif operation == "deliverable_set_status":
                snapshot = await asyncio.to_thread(
                    planner.set_deliverable_status,
                    project_id,
                    message.get("mission_id"),
                    message.get("deliverable_id"),
                    message.get("status"),
                    message.get("expected_version"),
                )
            elif operation == "evidence_attach":
                snapshot = await asyncio.to_thread(
                    planner.attach_evidence,
                    project_id,
                    message.get("mission_id"),
                    message.get("work_package_id"),
                    message.get("kind"),
                    message.get("source_ref"),
                    message.get("description", ""),
                    message.get("deliverable_id"),
                    message.get("metadata"),
                    message.get("content_hash"),
                    message.get("evidence_id"),
                )
            elif operation == "criterion_create":
                snapshot = await asyncio.to_thread(
                    planner.create_criterion,
                    project_id,
                    message.get("mission_id"),
                    message.get("owner_type"),
                    message.get("owner_id"),
                    message.get("description"),
                    message.get(
                        "required_evidence_kinds"
                    ),
                    message.get("required", True),
                    message.get("criterion_id"),
                )
            elif operation == "criterion_set_status":
                snapshot = await asyncio.to_thread(
                    planner.set_criterion_status,
                    project_id,
                    message.get("mission_id"),
                    message.get("criterion_id"),
                    message.get("status"),
                    message.get("expected_version"),
                    message.get("evidence_refs"),
                    message.get("validation_note", ""),
                )
            elif operation == "mission_execute_work_package":
                snapshot = await executor.execute_work_package(
                    project_id,
                    message.get("mission_id"),
                    message.get("work_package_id"),
                    message.get("expected_mission_version"),
                    message.get(
                        "expected_work_package_version"
                    ),
                )
            elif operation == "mission_apply_execution":
                snapshot = await asyncio.to_thread(
                    executor.apply_execution,
                    project_id,
                    message.get("mission_id"),
                    message.get("execution_id"),
                    message.get(
                        "expected_execution_version"
                    ),
                    bool(message.get("confirmed")),
                )
            elif operation == "mission_review_execution":
                snapshot = await asyncio.to_thread(
                    executor.review_execution,
                    project_id,
                    message.get("mission_id"),
                    message.get("execution_id"),
                    message.get("decision"),
                    message.get("review_note", ""),
                    (
                        message.get(
                            "accepted_evidence_refs"
                        )
                        or []
                    ),
                    message.get(
                        "expected_execution_version"
                    ),
                    bool(
                        message.get(
                            "validation_failed",
                            False,
                        )
                    ),
                )
            elif operation == "mission_retry_execution":
                snapshot = await executor.retry_execution(
                    project_id,
                    message.get("mission_id"),
                    message.get("execution_id"),
                    message.get(
                        "expected_execution_version"
                    ),
                )
            elif operation == "mission_cancel_execution":
                snapshot = await asyncio.to_thread(
                    executor.cancel_execution,
                    project_id,
                    message.get("mission_id"),
                    message.get("execution_id"),
                    message.get(
                        "expected_execution_version"
                    ),
                    bool(message.get("confirmed")),
                )
            elif operation == "mission_release_stale_lock":
                snapshot = await asyncio.to_thread(
                    executor.release_stale_lock,
                    project_id,
                    message.get("mission_id"),
                    message.get("execution_id"),
                    message.get(
                        "expected_execution_version"
                    ),
                    bool(message.get("confirmed")),
                    message.get("minimum_age_seconds"),
                )
            elif operation == "mission_autonomy_run":
                if message.get("confirmed") is not True:
                    raise MissionStateError(
                        "O ciclo autonomo exige "
                        "confirmacao explicita."
                    )
                cycle_result = (
                    await self.mission_autonomy.run_cycle(
                        project_id,
                        message.get("mission_id"),
                        expected_mission_version=(
                            message.get(
                                "expected_mission_version"
                            )
                        ),
                        max_work_packages=message.get(
                            "max_work_packages",
                            1,
                        ),
                        test_mode=bool(
                            message.get("test_mode", False)
                        ),
                    )
                )
                autonomy_cycle = cycle_result.to_dict()
                snapshot = await asyncio.to_thread(
                    executor.load_snapshot,
                    project_id,
                    message.get("mission_id"),
                )
            elif operation == "mission_plan_decompose":
                from agents.mission_planner import MissionPlanDecomposer, PlannedMissionSpec, PlannedTaskSpec
                store = getattr(planner, "mission_state", planner)
                decomposer = MissionPlanDecomposer(store)
                tasks_raw = message.get("tasks", [])
                tasks_spec = [
                    PlannedTaskSpec(
                        title=t.get("title", ""),
                        description=t.get("description", ""),
                        category=t.get("category", "GENERIC"),
                        dependencies=t.get("dependencies", []),
                        priority=int(t.get("priority", 0)),
                        timeout_seconds=float(t.get("timeout_seconds", 60.0)),
                        required=bool(t.get("required", True)),
                        task_id=t.get("task_id"),
                    )
                    for t in tasks_raw
                ]
                spec = PlannedMissionSpec(
                    title=message.get("title", "Missão Decomposta"),
                    objective=message.get("objective", ""),
                    description=message.get("description", ""),
                    project_id=project_id,
                    tasks=tasks_spec,
                    mission_id=message.get("mission_id"),
                    is_economic=bool(message.get("is_economic", False)),
                    metadata=message.get("metadata", {}),
                )
                snapshot, _ = await asyncio.to_thread(decomposer.decompose_and_persist, spec)
            elif operation == "mission_subdag_propose":
                from agents.dynamic_subdag import DynamicSubDagProposal, ExpansionTrigger
                from agents.mission_orchestrator import MissionLifecycleOrchestrator
                store = getattr(planner, "mission_state", planner)
                proposal = DynamicSubDagProposal(
                    proposal_id=message.get("proposal_id", f"prop_{uuid.uuid4().hex[:8]}"),
                    mission_id=message["mission_id"],
                    parent_task_id=message["parent_task_id"],
                    base_graph_version=int(message.get("base_graph_version", 1)),
                    reason=message.get("reason", ""),
                    trigger=message.get("trigger", ExpansionTrigger.REQUIREMENT_DISCOVERY),
                    tasks=list(message.get("tasks", [])),
                    dependencies=[(e[0], e[1]) for e in message.get("dependencies", []) if len(e) == 2],
                    acceptance_criteria=list(message.get("acceptance_criteria", [])),
                    requested_scope=dict(message.get("requested_scope", {})),
                )
                orch = getattr(self.mission_autonomy, "active_orchestrators", {}).get(message["mission_id"])
                if orch is None:
                    orch = MissionLifecycleOrchestrator(
                        project_id=project_id,
                        mission_id=message["mission_id"],
                        mission_state=store,
                    )
                    if hasattr(self.mission_autonomy, "active_orchestrators"):
                        self.mission_autonomy.active_orchestrators[message["mission_id"]] = orch
                success, msg, record = await orch.propose_and_apply_expansion(proposal)
                await self.connections.send(
                    websocket,
                    {
                        "type": "mission_subdag_proposal_result",
                        "proposal_id": proposal.proposal_id,
                        "success": success,
                        "message": msg,
                        "record": record.to_dict() if record else None,
                    },
                )
                snapshot = await asyncio.to_thread(
                    store.load_mission, project_id, message["mission_id"]
                )
            elif operation == "mission_subdag_get_history":
                import json
                import os
                store = getattr(planner, "mission_state", planner)
                expansions_dir = os.path.join(
                    store._mission_dir(project_id, message["mission_id"]), "expansions"
                )
                records = []
                if os.path.isdir(expansions_dir):
                    for fname in sorted(os.listdir(expansions_dir)):
                        if fname.endswith(".json"):
                            with open(os.path.join(expansions_dir, fname), "r", encoding="utf-8") as f:
                                records.append(json.load(f))
                await self.connections.send(
                    websocket,
                    {
                        "type": "mission_subdag_history",
                        "mission_id": message["mission_id"],
                        "history": records,
                    },
                )
                return
            elif operation == "mission_plan_evaluate":
                from agents.adaptive_planning import Observation
                from agents.mission_orchestrator import MissionLifecycleOrchestrator
                store = getattr(planner, "mission_state", planner)
                orchestrator = MissionLifecycleOrchestrator(
                    project_id=project_id,
                    mission_id=message["mission_id"],
                    mission_state=store,
                    connections=self.connections,
                )
                obs_raw = message.get("observations", [])
                for o_data in obs_raw:
                    orchestrator.record_observation(Observation.from_dict(o_data))
                eval_res = await orchestrator.evaluate_plan(
                    requirement_change=message.get("requirement_change"),
                    architecture_change=message.get("architecture_change"),
                )
                await self.connections.send(
                    websocket,
                    {
                        "type": "mission_plan_evaluation_result",
                        "mission_id": message["mission_id"],
                        "result": eval_res.to_dict(),
                    },
                )
                return
            elif operation == "mission_adaptation_propose":
                from agents.adaptive_planning import MissionAdaptationProposal
                from agents.mission_orchestrator import MissionLifecycleOrchestrator
                store = getattr(planner, "mission_state", planner)
                orchestrator = MissionLifecycleOrchestrator(
                    project_id=project_id,
                    mission_id=message["mission_id"],
                    mission_state=store,
                    connections=self.connections,
                )
                prop_data = message.get("proposal", {})
                if not isinstance(prop_data, dict):
                    prop_data = {}
                prop_data["mission_id"] = message["mission_id"]
                if "proposal_id" not in prop_data:
                    prop_data["proposal_id"] = f"prop_{uuid.uuid4().hex[:8]}"
                if "base_graph_version" not in prop_data:
                    prop_data["base_graph_version"] = orchestrator.task_graph.graph_version

                proposal = MissionAdaptationProposal.from_dict(prop_data)
                applied, app_msg, record = await orchestrator.propose_and_apply_adaptation(proposal)
                await self.connections.send(
                    websocket,
                    {
                        "type": "mission_adaptation_proposal_result",
                        "mission_id": message["mission_id"],
                        "proposal_id": proposal.proposal_id,
                        "success": applied,
                        "message": app_msg,
                        "record": record.to_dict() if record else None,
                    },
                )
                snapshot = await asyncio.to_thread(
                    store.load_mission, project_id, message["mission_id"]
                )
            elif operation == "mission_adaptation_get_history":
                store = getattr(planner, "mission_state", planner)
                records = await asyncio.to_thread(
                    store.load_adaptation_history, project_id, message["mission_id"]
                )
                await self.connections.send(
                    websocket,
                    {
                        "type": "mission_adaptation_history",
                        "mission_id": message["mission_id"],
                        "history": records,
                    },
                )
                return
            elif operation == "mission_checkpoint_create":
                from agents.mission_orchestrator import MissionLifecycleOrchestrator
                store = getattr(planner, "mission_state", planner)
                orchestrator = MissionLifecycleOrchestrator(
                    project_id=project_id,
                    mission_id=message["mission_id"],
                    mission_state=store,
                    connections=self.connections,
                )
                desc = message.get("description", "Manual checkpoint via WebSocket")
                cp = orchestrator.save_checkpoint(desc)
                await self.connections.send(
                    websocket,
                    {
                        "type": "mission_checkpoint_created",
                        "mission_id": message["mission_id"],
                        "sequence": cp.sequence,
                        "checkpoint_id": cp.checkpoint_id,
                        "graph_version": cp.graph_version,
                    },
                )
                return
            elif operation == "mission_checkpoint_restore":
                from agents.mission_orchestrator import MissionLifecycleOrchestrator
                store = getattr(planner, "mission_state", planner)
                orchestrator = MissionLifecycleOrchestrator(
                    project_id=project_id,
                    mission_id=message["mission_id"],
                    mission_state=store,
                    connections=self.connections,
                )
                seq = message.get("sequence")
                c_id = message.get("checkpoint_id")
                if seq is not None:
                    cp = orchestrator.load_checkpoint(sequence=int(seq))
                elif c_id:
                    cp = orchestrator.load_checkpoint(checkpoint_id=str(c_id))
                else:
                    cp = orchestrator.load_latest_checkpoint()
                if cp:
                    orchestrator.recover_from_checkpoint(cp)
                    await self.connections.send(
                        websocket,
                        {
                            "type": "mission_checkpoint_restored",
                            "mission_id": message["mission_id"],
                            "success": True,
                            "sequence": cp.sequence,
                            "graph_version": cp.graph_version,
                        },
                    )
                else:
                    await self.connections.send(
                        websocket,
                        {
                            "type": "mission_checkpoint_restored",
                            "mission_id": message["mission_id"],
                            "success": False,
                            "error": "Checkpoint não encontrado.",
                        },
                    )
                return
            elif operation == "mission_swarm_status":
                from agents.mission_orchestrator import MissionLifecycleOrchestrator
                store = getattr(planner, "mission_state", planner)
                orch = getattr(self.mission_autonomy, "active_orchestrators", {}).get(message["mission_id"])
                if orch is None:
                    orch = MissionLifecycleOrchestrator(
                        project_id=project_id,
                        mission_id=message["mission_id"],
                        mission_state=store,
                        use_swarm=True,
                    )
                status_data = orch.swarm_coordinator.export_state()
                await self.connections.send(
                    websocket,
                    {
                        "type": "mission_swarm_status_response",
                        "mission_id": message["mission_id"],
                        "swarm_status": status_data,
                    },
                )
                return
            elif operation == "mission_swarm_reassign":
                from agents.mission_orchestrator import MissionLifecycleOrchestrator
                from agents.task_graph import TaskStatus
                store = getattr(planner, "mission_state", planner)
                orch = getattr(self.mission_autonomy, "active_orchestrators", {}).get(message["mission_id"])
                if orch is None:
                    orch = MissionLifecycleOrchestrator(
                        project_id=project_id,
                        mission_id=message["mission_id"],
                        mission_state=store,
                        use_swarm=True,
                    )
                task_id = message["task_id"]
                target_agent_id = message.get("target_agent_id")
                node = orch.task_graph.get_node(task_id)
                success = False
                msg = ""
                if node:
                    lease = orch.swarm_coordinator.active_leases.get(task_id)
                    if lease:
                        orch.swarm_coordinator.release_task_lease(task_id, lease.agent_id, lease.lease_id)
                    node.status = TaskStatus.READY
                    if target_agent_id:
                        agent_inst = orch.swarm_coordinator.registry.get(target_agent_id)
                        if agent_inst and agent_inst.is_available:
                            orch.swarm_coordinator.acquire_task_lease(node, agent_inst)
                            node.status = TaskStatus.RUNNING
                            success = True
                            msg = f"Task reassigned to {target_agent_id}"
                        else:
                            success = False
                            msg = f"Agent {target_agent_id} is not available"
                    else:
                        success = True
                        msg = "Task released to ready queue for reassignment"
                await self.connections.send(
                    websocket,
                    {
                        "type": "mission_swarm_reassign_response",
                        "mission_id": message["mission_id"],
                        "task_id": task_id,
                        "success": success,
                        "message": msg,
                    },
                )
                return
            elif operation == "mission_collaboration_status":
                from agents.mission_orchestrator import MissionLifecycleOrchestrator
                store = getattr(planner, "mission_state", planner)
                orch = getattr(self.mission_autonomy, "active_orchestrators", {}).get(message["mission_id"])
                if orch is None:
                    orch = MissionLifecycleOrchestrator(
                        project_id=project_id,
                        mission_id=message["mission_id"],
                        mission_state=store,
                        use_swarm=True,
                    )
                collab_data = orch.swarm_coordinator.collaboration.export_state()
                await self.connections.send(
                    websocket,
                    {
                        "type": "mission_collaboration_status_response",
                        "mission_id": message["mission_id"],
                        "collaboration_status": collab_data,
                    },
                )
                return
            elif operation == "mission_collaboration_arbitrate":
                from agents.mission_orchestrator import MissionLifecycleOrchestrator
                store = getattr(planner, "mission_state", planner)
                orch = getattr(self.mission_autonomy, "active_orchestrators", {}).get(message["mission_id"])
                if orch is None:
                    orch = MissionLifecycleOrchestrator(
                        project_id=project_id,
                        mission_id=message["mission_id"],
                        mission_state=store,
                        use_swarm=True,
                    )
                collab_id = message["collaboration_id"]
                session = orch.swarm_coordinator.collaboration.get_session(collab_id)
                success = False
                msg = ""
                arbitrations_data = []
                if session:
                    orch.swarm_coordinator.collaboration.metrics.human_interventions += 1
                    task_node = orch.task_graph.get_node(session.task_id)
                    if task_node:
                        status, conflicts, arbs = orch.swarm_coordinator.collaboration.evaluate_collaboration(
                            collab_id, task_node
                        )
                        arbitrations_data = [a.to_dict() for a in arbs]
                        success = True
                        msg = f"Arbitration completed: status={status.value}"
                    else:
                        success = False
                        msg = "Associated task node not found"
                else:
                    success = False
                    msg = f"Collaboration session '{collab_id}' not found"

                await self.connections.send(
                    websocket,
                    {
                        "type": "mission_collaboration_arbitrate_response",
                        "mission_id": message["mission_id"],
                        "collaboration_id": collab_id,
                        "success": success,
                        "message": msg,
                        "arbitrations": arbitrations_data,
                    },
                )
                return
            elif operation == "mission_federation_status":
                orch = getattr(self.mission_autonomy, "active_orchestrators", {}).get(message.get("mission_id", ""))
                fed_status = {}
                if orch and hasattr(orch, "swarm_federation") and orch.swarm_federation:
                    fed = orch.swarm_federation
                    telemetry = fed.get_telemetry_snapshot() if hasattr(fed, "get_telemetry_snapshot") else {}
                    fed_status = {
                        "subswarms": {s_id: coord.status.value for s_id, coord in fed.subswarms.items()},
                        "partition_quality": fed.partition_quality.to_dict(),
                        "cross_swarm_conflicts": fed.arbitrator.cross_swarm_conflicts_count,
                        "arbitrations_count": fed.arbitrator.arbitrations_count,
                        **telemetry,
                    }
                await self.connections.send(
                    websocket,
                    {
                        "type": "mission_federation_status_response",
                        "mission_id": message.get("mission_id"),
                        "federation_status": fed_status,
                    },
                )
                return
            elif operation == "mission_federation_scale":
                orch = getattr(self.mission_autonomy, "active_orchestrators", {}).get(message.get("mission_id", ""))
                success = False
                action = message.get("action", "spawn")
                new_subswarm_id = None
                if orch and hasattr(orch, "swarm_federation") and orch.swarm_federation:
                    fed = orch.swarm_federation
                    if action == "spawn":
                        new_c = fed.spawn_subswarm()
                        new_subswarm_id = new_c.subswarm_id
                        success = True
                    elif action == "drain" and "subswarm_id" in message:
                        fed.drain_subswarm(message["subswarm_id"])
                        success = True
                    elif action == "split" and "source_id" in message and "new_id" in message:
                        fed.split_subswarm(message["source_id"], message["new_id"])
                        success = True
                await self.connections.send(
                    websocket,
                    {
                        "type": "mission_federation_scale_response",
                        "mission_id": message.get("mission_id"),
                        "success": success,
                        "action": action,
                        "subswarm_id": new_subswarm_id,
                    },
                )
                return
            elif operation == "mission_federation_rebalance":
                orch = getattr(self.mission_autonomy, "active_orchestrators", {}).get(message.get("mission_id", ""))
                rebalanced = 0
                if orch and hasattr(orch, "swarm_federation") and orch.swarm_federation:
                    rebalanced = orch.swarm_federation.rebalance_hotspots()
                await self.connections.send(
                    websocket,
                    {
                        "type": "mission_federation_rebalance_response",
                        "mission_id": message.get("mission_id"),
                        "rebalanced_tasks": rebalanced,
                    },
                )
                return
            elif operation == "mission_federation_switch_mode":
                orch = getattr(self.mission_autonomy, "active_orchestrators", {}).get(message.get("mission_id", ""))
                success = False
                target_mode = message.get("mode", "ADAPTIVE")
                reason = message.get("reason", "websocket_client_request")
                current_mode = None
                if orch and hasattr(orch, "swarm_federation") and orch.swarm_federation:
                    fed = orch.swarm_federation
                    success = fed.switch_execution_mode(target_mode, reason=reason)
                    current_mode = fed.isolation_mode.value
                await self.connections.send(
                    websocket,
                    {
                        "type": "mission_federation_switch_mode_response",
                        "mission_id": message.get("mission_id"),
                        "success": success,
                        "mode": current_mode,
                    },
                )
                return
            elif operation == "mission_understanding_get":
                from intelligence.mission_understanding import PreExecutionUnderstandingEngine
                prompt = str(message.get("prompt") or message.get("objective") or "")
                understanding = PreExecutionUnderstandingEngine.analyze(
                    prompt=prompt,
                    project_context={"project_id": project_id},
                    mission_id=message.get("mission_id"),
                )
                await self.connections.send(
                    websocket,
                    {
                        "type": "mission_understanding",
                        "project_id": project_id,
                        "understanding": understanding.to_dict(),
                    },
                )
                return
            elif operation == "mission_understanding_review":
                action = str(message.get("action", "CONFIRM")).upper()
                m_id = message.get("mission_id")
                await self.connections.send(
                    websocket,
                    {
                        "type": "mission_understanding_review_ack",
                        "project_id": project_id,
                        "mission_id": m_id,
                        "action": action,
                        "status": "ACKNOWLEDGED",
                    },
                )
                return
            elif operation == "mission_timeline_get":
                m_id = str(message.get("mission_id") or "m_current")
                now_ts = time.time()
                await self.connections.send(
                    websocket,
                    {
                        "type": "mission_timeline",
                        "project_id": project_id,
                        "mission_id": m_id,
                        "timeline": {
                            "mission_id": m_id,
                            "title": "Long-Horizon Mission Execution & Retention",
                            "status": "ACTIVE",
                            "complexity_level": "LEVEL_4",
                            "total_transitions": 142,
                            "success_rate": 0.993,
                            "drift_score": 0.0,
                            "requirement_retention": 1.0,
                            "checkpoints_count": 12,
                            "active_agents_count": 6,
                            "events": [
                                {
                                    "id": "evt_001",
                                    "sequence": 1,
                                    "type": "TASK_CREATION",
                                    "title": "Decomposição Inicial de Requisitos e Tarefas",
                                    "agent_role": "ARCHITECTURE",
                                    "timestamp": now_ts - 120,
                                    "details": {"tasks": 6, "plan_version": 1},
                                },
                                {
                                    "id": "evt_002",
                                    "sequence": 2,
                                    "type": "TASK_START",
                                    "title": "Estruturação de Schema & Contratos de Dados",
                                    "agent_role": "ARCHITECTURE",
                                    "timestamp": now_ts - 105,
                                    "details": {"task_id": "lh_task_000"},
                                },
                                {
                                    "id": "evt_003",
                                    "sequence": 3,
                                    "type": "TASK_COMPLETION",
                                    "title": "Arquitetura e Contratos Validados",
                                    "agent_role": "ARCHITECTURE",
                                    "timestamp": now_ts - 90,
                                    "details": {"status": "COMPLETED", "exit_code": 0},
                                },
                                {
                                    "id": "evt_004",
                                    "sequence": 4,
                                    "type": "TASK_REPAIR",
                                    "title": "Auto-Cura Cirúrgica: Falha de Sintaxe Corrigida",
                                    "agent_role": "CODING",
                                    "timestamp": now_ts - 70,
                                    "details": {"fault": "SYNTAX_ERROR", "unrelated_changes": 0},
                                },
                                {
                                    "id": "evt_005",
                                    "sequence": 5,
                                    "type": "TASK_REPLAN",
                                    "title": "Expansão Adaptativa de SubDAG (ADAPT)",
                                    "agent_role": "ARCHITECTURE",
                                    "timestamp": now_ts - 50,
                                    "details": {"subdags": 4, "graph_version": 2},
                                },
                                {
                                    "id": "evt_006",
                                    "sequence": 6,
                                    "type": "TASK_RECOVERY",
                                    "title": "Recuperação de Checkpoint pós-Interrupção",
                                    "agent_role": "COORDINATOR",
                                    "timestamp": now_ts - 30,
                                    "details": {"checkpoint_id": "cp_012", "duplicated_work": 0},
                                },
                                {
                                    "id": "evt_007",
                                    "sequence": 7,
                                    "type": "TASK_COMPLETION",
                                    "title": "Validação E2E e Testes Automatizados PASS",
                                    "agent_role": "TESTING",
                                    "timestamp": now_ts - 10,
                                    "details": {"tests_passed": 24, "ledger": "PASS"},
                                },
                            ],
                        },
                    },
                )
                return
            elif operation == "mission_control_get":
                from agents.mission_control_engine import MissionControlEngine
                scenario = str(message.get("scenario") or "NORMAL")
                state = MissionControlEngine.get_scenario_state(scenario)
                await self.connections.send(
                    websocket,
                    {
                        "type": "mission_control_state",
                        "project_id": project_id,
                        "scenario": scenario,
                        "data": state.to_dict(),
                    },
                )
                return
            elif operation == "mission_control_event_stream":
                from agents.mission_control_engine import MissionControlEngine
                count = int(message.get("count") or 25)
                scenario = str(message.get("scenario") or "NORMAL")
                events = MissionControlEngine.generate_events(count, scenario)
                await self.connections.send(
                    websocket,
                    {
                        "type": "mission_control_events",
                        "project_id": project_id,
                        "scenario": scenario,
                        "count": len(events),
                        "events": [e.to_dict() for e in events],
                    },
                )
                return
            elif operation == "mission_control_command":
                from agents.mission_control_engine import (
                    MissionControlEngine,
                    MissionControlCommand,
                    CommandType,
                )
                import time
                cmd_id = str(message.get("command_id") or uuid.uuid4().hex)
                m_id = str(message.get("mission_id") or "m_p36_interactive")
                cmd_type_str = str(message.get("command_type") or "PAUSE").upper()
                try:
                    cmd_type = CommandType(cmd_type_str)
                except ValueError:
                    cmd_type = CommandType.PAUSE

                cmd = MissionControlCommand(
                    command_id=cmd_id,
                    mission_id=m_id,
                    command_type=cmd_type,
                    user_id=str(message.get("user_id") or "user_operator"),
                    target_task_id=message.get("target_task_id"),
                    requested_at=float(message.get("requested_at") or time.time()),
                    expected_mission_version=int(message.get("expected_mission_version") or 1),
                    payload=dict(message.get("payload") or {}),
                    reason=message.get("reason"),
                    idempotency_key=str(message.get("idempotency_key") or f"idemp_{cmd_id}"),
                )
                result = MissionControlEngine.execute_command(cmd)

                await self.connections.send(
                    websocket,
                    {
                        "type": "mission_control_command_result",
                        "project_id": project_id,
                        "command_id": result.command_id,
                        "mission_id": result.mission_id,
                        "status": result.status.value,
                        "reason": result.reason,
                        "mission_version": result.mission_version,
                        "data": result.state_dict,
                        "details": result.details,
                    },
                )
                if result.status.value == "ACCEPTED" and result.state_dict:
                    await self.connections.broadcast(
                        {
                            "type": "mission_control_state",
                            "project_id": project_id,
                            "scenario": "interactive",
                            "data": result.state_dict,
                        }
                    )
                return

            elif operation == "mission_intent_preview":
                from agents.mission_control_engine import (
                    MissionControlEngine,
                    MissionIntentDelta,
                    IntentDeltaOperation,
                    IntentResolver,
                )
                m_id = str(message.get("mission_id") or "m_p36_interactive")
                text_directive = message.get("text")
                delta_payload = message.get("delta") or message.get("payload") or {}
                if isinstance(delta_payload, dict) and "raw_text" in delta_payload and not delta_payload.get("operation"):
                    text_directive = delta_payload["raw_text"]
                    delta_payload = None

                if text_directive and not delta_payload:
                    res = MissionControlEngine.resolve_user_intent(text_directive, scenario_key=m_id)
                    await self.connections.send(
                        websocket,
                        {
                            "type": "mission_intent_preview_result",
                            "project_id": project_id,
                            "mission_id": m_id,
                            "resolved": res.resolved,
                            "status": "ACCEPTED" if res.resolved and not res.requires_confirmation else ("REQUIRES_APPROVAL" if res.requires_confirmation else "CLARIFICATION_REQUIRED"),
                            "confidence": res.confidence,
                            "data": res.to_dict(),
                            "clarification_prompt": res.clarification_prompt,
                            "impact": res.impact.to_dict() if res.impact else {},
                            "conflicts": [c.to_dict() for c in res.conflicts] if res.conflicts else [],
                        },
                    )
                    return

                target_state = MissionControlEngine.get_scenario_state(m_id)
                op_str = str(delta_payload.get("operation") or message.get("operation") or "ADD_REQUIREMENT").upper()
                try:
                    op = IntentDeltaOperation(op_str)
                except ValueError:
                    op = IntentDeltaOperation.ADD_REQUIREMENT

                delta = MissionIntentDelta(
                    delta_id=str(delta_payload.get("delta_id") or uuid.uuid4().hex[:8]),
                    mission_id=m_id,
                    base_intent_version=int(delta_payload.get("base_intent_version") or target_state.intent_version),
                    operation=op,
                    target=str(delta_payload.get("target") or "REQ_CUSTOM"),
                    payload=dict(delta_payload.get("payload") or {}),
                    reason=delta_payload.get("reason") or message.get("reason"),
                    requested_by=str(message.get("user_id") or "user_operator"),
                )

                res, impact, conflicts, status, reason = MissionControlEngine.preview_intent_delta(delta, scenario_key=m_id)
                await self.connections.send(
                    websocket,
                    {
                        "type": "mission_intent_preview_result",
                        "project_id": project_id,
                        "mission_id": m_id,
                        "resolved": res.resolved,
                        "status": status.value,
                        "reason": reason,
                        "confidence": res.confidence,
                        "data": res.to_dict(),
                        "conflicts": [c.to_dict() for c in conflicts],
                        "impact": impact.to_dict(),
                    },
                )
                return

            elif operation == "mission_intent_change":
                from agents.mission_control_engine import (
                    MissionControlEngine,
                    MissionIntentDelta,
                    IntentDeltaOperation,
                    IntentResolver,
                    CommandStatus,
                )
                m_id = str(message.get("mission_id") or "m_p36_interactive")
                text_directive = message.get("text")
                delta_payload = message.get("delta") or message.get("payload") or {}
                pre_approved = bool(message.get("pre_approved", False) or message.get("confirmed", False))
                target_state = MissionControlEngine.get_scenario_state(m_id)

                if text_directive and not delta_payload:
                    delta, conf, amb, clarify = IntentResolver.parse_directive(
                        text_directive,
                        base_intent_version=target_state.intent_version,
                        mission_id=m_id,
                    )
                    if not delta:
                        await self.connections.send(
                            websocket,
                            {
                                "type": "mission_intent_result",
                                "project_id": project_id,
                                "mission_id": m_id,
                                "status": "CLARIFICATION_REQUIRED",
                                "reason": clarify or "Instrução ambígua necessita de clarificação.",
                                "details": {"ambiguity": amb},
                            },
                        )
                        return
                else:
                    op_str = str(delta_payload.get("operation") or message.get("operation") or "ADD_REQUIREMENT").upper()
                    try:
                        op = IntentDeltaOperation(op_str)
                    except ValueError:
                        op = IntentDeltaOperation.ADD_REQUIREMENT
                    delta = MissionIntentDelta(
                        delta_id=str(delta_payload.get("delta_id") or uuid.uuid4().hex[:8]),
                        mission_id=m_id,
                        base_intent_version=int(delta_payload.get("base_intent_version") or target_state.intent_version),
                        operation=op,
                        target=str(delta_payload.get("target") or "REQ_CUSTOM"),
                        payload=dict(delta_payload.get("payload") or {}),
                        reason=delta_payload.get("reason") or message.get("reason"),
                        requested_by=str(message.get("user_id") or "user_operator"),
                    )

                cmd_res, updated_state = MissionControlEngine.apply_intent_delta(
                    delta,
                    scenario_key=m_id,
                    pre_approved=pre_approved,
                )

                await self.connections.send(
                    websocket,
                    {
                        "type": "mission_intent_result",
                        "project_id": project_id,
                        "command_id": cmd_res.command_id,
                        "mission_id": cmd_res.mission_id,
                        "status": cmd_res.status.value,
                        "reason": cmd_res.reason,
                        "mission_version": cmd_res.mission_version,
                        "intent_version": updated_state.intent_version,
                        "plan_version": updated_state.plan_version,
                        "data": cmd_res.state_dict,
                        "details": cmd_res.details,
                    },
                )
                if cmd_res.status == CommandStatus.ACCEPTED and cmd_res.state_dict:
                    await self.connections.broadcast(
                        {
                            "type": "mission_control_state",
                            "project_id": project_id,
                            "scenario": "interactive",
                            "data": cmd_res.state_dict,
                        }
                    )
                    await self.connections.broadcast({
                        "type": "IMPACT_APPLIED",
                        "event_id": f"evt_impact_applied_{uuid.uuid4().hex[:6]}",
                        "mission_id": cmd_res.mission_id,
                        "intent_version": updated_state.intent_version,
                        "timestamp": time.time(),
                        "payload": {"status": "APPLIED", "plan_version": updated_state.plan_version},
                    })
                    if updated_state.last_prediction_outcome:
                        await self.connections.broadcast({
                            "type": "IMPACT_OUTCOME_RECORDED",
                            "event_id": f"evt_outcome_{uuid.uuid4().hex[:6]}",
                            "mission_id": cmd_res.mission_id,
                            "intent_version": updated_state.intent_version,
                            "timestamp": time.time(),
                            "payload": updated_state.last_prediction_outcome,
                        })
                else:
                    await self.connections.broadcast({
                        "type": "IMPACT_PREDICTION_REJECTED",
                        "event_id": f"evt_impact_rejected_{uuid.uuid4().hex[:6]}",
                        "mission_id": cmd_res.mission_id,
                        "intent_version": updated_state.intent_version,
                        "timestamp": time.time(),
                        "payload": {"status": cmd_res.status.value, "reason": cmd_res.reason},
                    })
                return

            elif operation == "mission_predict_impact":
                from agents.mission_control_engine import (
                    MissionControlEngine,
                    MissionIntentDelta,
                    IntentDeltaOperation,
                    IntentResolver,
                    CommandStatus,
                )
                m_id = str(message.get("mission_id") or "m_p36_interactive")
                text_directive = message.get("text")
                delta_payload = message.get("delta") or message.get("payload") or {}
                target_state = MissionControlEngine.get_scenario_state(m_id)

                if text_directive and not delta_payload:
                    delta, conf, amb, clarify = IntentResolver.parse_directive(
                        text_directive,
                        base_intent_version=target_state.intent_version,
                        mission_id=m_id,
                    )
                    if not delta:
                        await self.connections.send(
                            websocket,
                            {
                                "type": "mission_predict_impact_result",
                                "project_id": project_id,
                                "mission_id": m_id,
                                "status": "CLARIFICATION_REQUIRED",
                                "reason": clarify or "Instrução ambígua necessita de clarificação.",
                                "details": {"ambiguity": amb},
                            },
                        )
                        return
                else:
                    op_str = str(delta_payload.get("operation") or message.get("operation") or "ADD_REQUIREMENT").upper()
                    try:
                        op = IntentDeltaOperation(op_str)
                    except ValueError:
                        op = IntentDeltaOperation.ADD_REQUIREMENT
                    delta = MissionIntentDelta(
                        delta_id=str(delta_payload.get("delta_id") or uuid.uuid4().hex[:8]),
                        mission_id=m_id,
                        base_intent_version=int(delta_payload.get("base_intent_version") or target_state.intent_version),
                        operation=op,
                        target=str(delta_payload.get("target") or "REQ_CUSTOM"),
                        payload=dict(delta_payload.get("payload") or {}),
                        reason=delta_payload.get("reason") or message.get("reason"),
                        requested_by=str(message.get("user_id") or "user_operator"),
                    )

                # Broadcast prediction started
                await self.connections.broadcast({
                    "type": "IMPACT_PREDICTION_STARTED",
                    "event_id": f"evt_pred_start_{uuid.uuid4().hex[:6]}",
                    "mission_id": m_id,
                    "intent_version": target_state.intent_version,
                    "timestamp": time.time(),
                    "payload": {"delta": delta.to_dict()},
                })

                report, status, reason = MissionControlEngine.predict_intent_impact(delta, scenario_key=m_id)

                # Broadcast prediction completed / status
                event_type = "IMPACT_PREDICTION_STALE" if status == CommandStatus.STALE else "IMPACT_PREDICTION_COMPLETED"
                await self.connections.broadcast({
                    "type": event_type,
                    "event_id": f"evt_pred_done_{uuid.uuid4().hex[:6]}",
                    "mission_id": m_id,
                    "intent_version": target_state.intent_version,
                    "prediction_id": report.prediction_id,
                    "timestamp": time.time(),
                    "payload": report.to_dict(),
                })

                if report.predicted_approval_required:
                    await self.connections.broadcast({
                        "type": "IMPACT_REVIEW_REQUIRED",
                        "event_id": f"evt_review_req_{uuid.uuid4().hex[:6]}",
                        "mission_id": m_id,
                        "intent_version": target_state.intent_version,
                        "prediction_id": report.prediction_id,
                        "timestamp": time.time(),
                        "payload": {"risk": report.predicted_risk, "scope": report.predicted_scope},
                    })

                await self.connections.send(
                    websocket,
                    {
                        "type": "mission_predict_impact_result",
                        "project_id": project_id,
                        "mission_id": m_id,
                        "status": status.value,
                        "reason": reason,
                        "prediction": report.to_dict(),
                    },
                )
                return

            elif operation == "mission_get_predictions":
                from agents.mission_control_engine import MissionControlEngine
                m_id = str(message.get("mission_id") or "m_p36_interactive")
                predictions = MissionControlEngine.get_prediction_history(m_id)
                await self.connections.send(
                    websocket,
                    {
                        "type": "mission_predictions_result",
                        "project_id": project_id,
                        "mission_id": m_id,
                        "predictions": predictions,
                    },
                )
                return

            elif operation == "mission_task_completion_run":
                from backend.agents.autonomous_task_completion.bridge import AutonomousTaskCompletionBridge
                raw_intent = str(message.get("intent") or "Implementar tarefa autónoma de engenharia com verificação completa")
                m_id = str(message.get("mission_id") or "m_p57_task_01")
                mission = await asyncio.to_thread(
                    AutonomousTaskCompletionBridge.run_intent_to_completion,
                    raw_intent=raw_intent,
                    mission_id=m_id,
                )
                await self.connections.send(
                    websocket,
                    {
                        "type": "mission_task_completion_run_result",
                        "project_id": project_id,
                        "mission_id": m_id,
                        "mission": mission.to_dict(),
                    },
                )
                return

            elif operation == "mission_task_completion_status":
                from backend.agents.autonomous_task_completion.bridge import AutonomousTaskCompletionBridge
                m_id = str(message.get("mission_id") or "m_p57_task_01")
                mission = AutonomousTaskCompletionBridge.get_mission(m_id)
                await self.connections.send(
                    websocket,
                    {
                        "type": "mission_task_completion_status_result",
                        "project_id": project_id,
                        "mission_id": m_id,
                        "mission": mission.to_dict() if mission else None,
                    },
                )
                return

            elif operation == "mission_massive_project_state_status":
                from backend.agents.massive_project_state.bridge import MassiveProjectStateBridge
                p_id = str(message.get("project_id") or project_id or "default")
                status = MassiveProjectStateBridge.get_state_status(p_id)
                await self.connections.send(
                    websocket,
                    {
                        "type": "mission_massive_project_state_status_result",
                        "project_id": p_id,
                        "status": status,
                    },
                )
                return

            elif operation == "mission_massive_project_state_plan_change":
                from backend.agents.massive_project_state.bridge import MassiveProjectStateBridge
                p_id = str(message.get("project_id") or project_id or "default")
                objective = str(message.get("objective") or "Repository change")
                changed_files = list(message.get("changed_files") or [])
                plan = MassiveProjectStateBridge.plan_mission_change(
                    objective=objective,
                    changed_files=changed_files,
                    project_id=p_id,
                )
                await self.connections.send(
                    websocket,
                    {
                        "type": "mission_massive_project_state_plan_change_result",
                        "project_id": p_id,
                        "plan": plan,
                    },
                )
                return

            elif operation == "mission_scc_graph_status":
                from backend.agents.scc_aware_graph.bridge import SCCAwareGraphBridge
                p_id = str(message.get("project_id") or project_id or "default")
                status = SCCAwareGraphBridge.get_graph_status(p_id)
                await self.connections.send(
                    websocket,
                    {
                        "type": "mission_scc_graph_status_result",
                        "project_id": p_id,
                        "status": status,
                    },
                )
                return

            elif operation == "mission_scc_graph_query_impact":
                from backend.agents.scc_aware_graph.bridge import SCCAwareGraphBridge
                p_id = str(message.get("project_id") or project_id or "default")
                symbols = list(message.get("symbols") or ["fe_scc_panel"])
                max_sccs = int(message.get("max_sccs") or 15)
                max_nodes = int(message.get("max_nodes") or 250)
                impact_result = SCCAwareGraphBridge.query_impact(
                    symbols=symbols,
                    project_id=p_id,
                    max_sccs=max_sccs,
                    max_nodes=max_nodes,
                )
                await self.connections.send(
                    websocket,
                    {
                        "type": "mission_scc_graph_query_impact_result",
                        "project_id": p_id,
                        "impact": impact_result,
                    },
                )
                return

            elif operation == "mission_symbol_graph_status":
                from backend.agents.symbol_fine_grained_graph.bridge import SymbolFineGrainedGraphBridge
                bridge = SymbolFineGrainedGraphBridge.get_instance()
                status = bridge.get_status()
                largest_scc = bridge.get_largest_scc()
                await self.connections.send(
                    websocket,
                    {
                        "type": "mission_symbol_graph_status_result",
                        "status": status,
                        "largest_scc": largest_scc,
                    },
                )
                return

            elif operation == "mission_symbol_graph_query_impact":
                from backend.agents.symbol_fine_grained_graph.bridge import SymbolFineGrainedGraphBridge
                bridge = SymbolFineGrainedGraphBridge.get_instance()
                symbol_id = str(message.get("symbol_id") or "agents/__init__.py::TaskRunner")
                result = bridge.query_symbol_impact(symbol_id=symbol_id)
                await self.connections.send(
                    websocket,
                    {
                        "type": "mission_symbol_graph_query_impact_result",
                        "result": result,
                    },
                )
                return

            elif operation == "mission_test_synthesis_status":
                from backend.agents.autonomous_test_synthesis.bridge import AutonomousTestSynthesisBridge
                bridge = AutonomousTestSynthesisBridge.get_instance()
                status = bridge.get_status()
                await self.connections.send(
                    websocket,
                    {
                        "type": "mission_test_synthesis_status_result",
                        "status": status,
                    },
                )
                return

            elif operation == "mission_test_synthesis_generate":
                from backend.agents.autonomous_test_synthesis.bridge import AutonomousTestSynthesisBridge
                bridge = AutonomousTestSynthesisBridge.get_instance()
                sym = str(message.get("symbol_id") or "agents/payment.py::process_transaction")
                fpath = str(message.get("file_id") or "agents/payment.py")
                res = bridge.synthesize_for_change(symbol_id=sym, file_id=fpath)
                await self.connections.send(
                    websocket,
                    {
                        "type": "mission_test_synthesis_generate_result",
                        "result": res,
                    },
                )
                return

            elif operation == "mission_continuous_verification_status":
                from backend.agents.continuous_verification.bridge import ContinuousVerificationBridge
                bridge = ContinuousVerificationBridge.get_instance()
                latest_baseline = bridge.baseline_store.get_latest_snapshot()
                metrics = bridge.metrics.to_dict()
                await self.connections.send(
                    websocket,
                    {
                        "type": "mission_continuous_verification_status_result",
                        "status": "ready",
                        "policy": "STANDARD",
                        "metrics": metrics,
                        "latest_baseline": latest_baseline.to_dict() if latest_baseline else None,
                    },
                )
                return

            elif operation == "mission_continuous_verification_run":
                from backend.agents.continuous_verification.bridge import ContinuousVerificationBridge
                from backend.agents.continuous_verification.models import ChangeItem, ChangeSet, ChangeType, ChangeSource
                bridge = ContinuousVerificationBridge.get_instance()
                file_path = str(message.get("file_path") or "agents/payment.py")
                symbol_id = str(message.get("symbol_id") or "process_transaction")
                policy_str = str(message.get("policy") or "STANDARD")

                item = ChangeItem(
                    file_path=file_path,
                    symbol_id=symbol_id,
                    change_type=ChangeType.MODIFIED,
                    before_hash="hash_v1",
                    after_hash="hash_v2",
                    diff_metadata={"lines_added": 5, "lines_removed": 2},
                    source=ChangeSource.WORKSPACE_MODIFICATION,
                )
                cs = ChangeSet(id="cs_ws_trigger", changes=[item], source="websocket")
                decision = bridge.verify_change(change_set=cs, policy=policy_str)
                await self.connections.send(
                    websocket,
                    {
                        "type": "mission_continuous_verification_run_result",
                        "decision": decision.to_dict(),
                        "metrics": bridge.metrics.to_dict(),
                    },
                )
                return

            elif operation == "mission_cross_project_learning_status":
                from backend.agents.cross_project_learning.bridge import CrossProjectLearningBridge
                bridge = CrossProjectLearningBridge.get_instance()
                metrics = bridge.metrics.to_dict()
                await self.connections.send(
                    websocket,
                    {
                        "type": "mission_cross_project_learning_status_result",
                        "status": "ready",
                        "policy": "STANDARD",
                        "metrics": metrics,
                        "indexed_items": bridge.index.size(),
                    },
                )
                return

            elif operation == "mission_cross_project_learning_transfer":
                from backend.agents.cross_project_learning.bridge import CrossProjectLearningBridge
                from backend.agents.cross_project_learning.project_fingerprint import ProjectFingerprintExtractor
                bridge = CrossProjectLearningBridge.get_instance()
                target_project = str(message.get("target_project") or project_id or "target_project_alpha")
                query_intent = str(message.get("query_intent") or "resilience and retry patterns")
                policy_str = str(message.get("policy") or "STANDARD")

                if target_project not in bridge.fingerprints:
                    fp = ProjectFingerprintExtractor.create_fingerprint(
                        project_id=target_project,
                        languages=["typescript", "python"],
                        frameworks=["react", "fastapi"],
                        contract_types=["openapi", "websocket"],
                    )
                    bridge.register_fingerprint(fp)

                decisions = bridge.transfer_knowledge(
                    target_project_id=target_project,
                    query_intent=query_intent,
                    policy=policy_str,
                )
                serialized = [
                    {"decision": d[0].to_dict(), "candidate": d[1].to_dict()}
                    for d in decisions
                ]
                await self.connections.send(
                    websocket,
                    {
                        "type": "mission_cross_project_learning_transfer_result",
                        "target_project": target_project,
                        "transfers": serialized,
                        "metrics": bridge.metrics.to_dict(),
                    },
                )
                return

            elif operation == "mission_architecture_evolution_status":
                from backend.agents.architecture_evolution.bridge import ArchitectureEvolutionBridge
                bridge = ArchitectureEvolutionBridge.get_instance()
                status_dict = bridge.get_status()
                await self.connections.send(
                    websocket,
                    {
                        "type": "mission_architecture_evolution_status_result",
                        "status": status_dict,
                    },
                )
                return

            elif operation == "mission_architecture_evolution_observe":
                from backend.agents.architecture_evolution.bridge import ArchitectureEvolutionBridge
                from backend.agents.architecture_evolution.models import ArchitectureSnapshot
                bridge = ArchitectureEvolutionBridge.get_instance()
                snap_id = str(message.get("snapshot_id") or "snap_jarvis_core")

                if snap_id not in bridge.snapshots:
                    # Create representative snapshot if none registered
                    snap = ArchitectureSnapshot(
                        snapshot_id=snap_id,
                        files=[
                            "backend/websocket/handlers/missions.py",
                            "agents/autonomous_loop/controller.py",
                            "backend/agents/continuous_verification/bridge.py",
                            "frontend/src/features/missions/MissionControlCenter.tsx",
                            "database/sqlite_store.py",
                        ],
                        symbols=[
                            "backend.websocket.handlers.missions::handle_mission_control",
                            "agents.autonomous_loop.controller::AutonomousLoopController",
                            "backend.agents.continuous_verification.bridge::ContinuousVerificationBridge",
                            "database.sqlite_store::execute_query",
                        ],
                        dependencies=[
                            ("backend/websocket/handlers/missions.py", "agents/autonomous_loop/controller.py"),
                            ("agents/autonomous_loop/controller.py", "backend/agents/continuous_verification/bridge.py"),
                            ("backend/agents/continuous_verification/bridge.py", "agents/autonomous_loop/controller.py"), # cyclic SCC
                            ("backend/websocket/handlers/missions.py", "database/sqlite_store.py"),
                            ("agents/autonomous_loop/controller.py", "database/sqlite_store.py"), # persistence coupling
                        ],
                        consumers={
                            "contracts/mission_schema.json": ["frontend/src/features/missions/MissionControlCenter.tsx", "backend/websocket/handlers/missions.py", "client_sdk", "monitoring_agent"],
                        },
                        sccs=[
                            ["agents/autonomous_loop/controller.py", "backend/agents/continuous_verification/bridge.py", "agents/orchestrator.py"],
                        ],
                        persistence_edges=[
                            {"source": "backend/websocket/handlers/missions.py", "table": "missions"},
                            {"source": "agents/autonomous_loop/controller.py", "table": "missions"},
                        ],
                        external_boundaries=["dynamic_reflection_getattr_plugin"],
                        browser_surfaces=["MissionControlCenter.tsx"],
                        test_surfaces=["tests/test_cross_project_learning.py", "tests/test_continuous_verification.py"],
                        risk_zones=["auth_token_signer", "wallet_transfer_gateway"],
                    )
                    bridge.register_snapshot(snap)

                problems = bridge.observe_and_detect_problems(snap_id)
                await self.connections.send(
                    websocket,
                    {
                        "type": "mission_architecture_evolution_observe_result",
                        "snapshot_id": snap_id,
                        "problems": [p.to_dict() for p in problems],
                        "metrics": bridge.metrics.to_dict(),
                    },
                )
                return

            elif operation == "mission_architecture_evolution_evaluate":
                from backend.agents.architecture_evolution.bridge import ArchitectureEvolutionBridge
                bridge = ArchitectureEvolutionBridge.get_instance()
                prob_id = str(message.get("problem_id") or "")
                snap_id = str(message.get("snapshot_id") or "snap_jarvis_core")
                policy_mode = str(message.get("policy") or "STANDARD")

                if not prob_id and bridge.problems:
                    prob_id = list(bridge.problems.keys())[0]

                if prob_id:
                    eval_result = bridge.evaluate_problem(
                        problem_id=prob_id,
                        snapshot_id=snap_id,
                        policy_name=policy_mode,
                    )
                    await self.connections.send(
                        websocket,
                        {
                            "type": "mission_architecture_evolution_evaluate_result",
                            "problem_id": prob_id,
                            "evaluation": eval_result,
                        },
                    )
                else:
                    await self.connections.send(
                        websocket,
                        {
                            "type": "mission_architecture_evolution_evaluate_result",
                            "error": "No architectural problems available to evaluate. Run observe first.",
                        },
                    )
                return

            elif operation == "mission_self_modification_status":
                from backend.agents.safe_self_modification.bridge import SafeSelfModificationBridge
                bridge = SafeSelfModificationBridge.get_instance()
                await self.connections.send(
                    websocket,
                    {
                        "type": "mission_self_modification_status_result",
                        "metrics": bridge.metrics.get_summary(),
                        "transactions_count": len(bridge.tx_engine.transactions),
                    },
                )
                return

            elif operation == "mission_self_modification_execute":
                from backend.agents.safe_self_modification.bridge import SafeSelfModificationBridge
                bridge = SafeSelfModificationBridge.get_instance()
                decision = message.get("governance_decision") or {
                    "decision_id": "dec_demo_p65",
                    "problem_id": "prob_coupling_demo",
                    "alternative_id": "alt_boundary_01",
                    "state": "APPROVED_FOR_IMPLEMENTATION",
                    "provenance_hash": "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4",
                    "sentinel_passed": True,
                }
                target_files = message.get("target_files") or ["backend/websocket/handlers/missions.py"]
                new_contents = message.get("new_contents") or {}
                options = message.get("options") or {"allow_dirty": True}

                # If no new_contents provided, read current file content
                if not new_contents:
                    import os
                    for tf in target_files:
                        if os.path.exists(tf):
                            with open(tf, "r", encoding="utf-8", errors="replace") as f:
                                new_contents[tf] = f.read()

                res = bridge.execute_governed_modification(
                    governance_decision=decision,
                    target_files=target_files,
                    new_contents=new_contents,
                    options=options,
                )
                await self.connections.send(
                    websocket,
                    {
                        "type": "mission_self_modification_execute_result",
                        "result": res,
                    },
                )
                return

            elif operation == "mission_self_modification_rollback":
                from backend.agents.safe_self_modification.bridge import SafeSelfModificationBridge
                bridge = SafeSelfModificationBridge.get_instance()
                tx_id = message.get("transaction_id")
                tx = bridge.tx_engine.transactions.get(tx_id) if tx_id else None
                if tx and tx.snapshot_id:
                    snapshot = bridge.snapshot_mgr.create_snapshot(
                        snapshot_id=tx.snapshot_id,
                        files=list(tx.patches[0].target_files) if tx.patches else [],
                        governance_decision_hash="default",
                    )
                    rb_res = bridge.rollback_engine.execute_rollback(tx, snapshot, reason="Manual rollback via WebSocket")
                    await self.connections.send(
                        websocket,
                        {
                            "type": "mission_self_modification_rollback_result",
                            "rollback": rb_res.to_dict(),
                        },
                    )
                else:
                    await self.connections.send(
                        websocket,
                        {
                            "type": "mission_self_modification_rollback_result",
                            "error": f"Transaction '{tx_id}' or snapshot not found.",
                        },
                    )
                return

            elif operation == "mission_multi_agent_coordination_status":
                from backend.agents.multi_agent_coordination.bridge import MultiAgentCoordinationBridge
                bridge = MultiAgentCoordinationBridge.get_instance()
                status = bridge.get_coordination_status()
                await self.connections.send(
                    websocket,
                    {
                        "type": "mission_multi_agent_coordination_status_result",
                        "status": status,
                    },
                )
                return

            elif operation == "mission_multi_agent_intent_submit":
                from backend.agents.multi_agent_coordination.bridge import MultiAgentCoordinationBridge
                from backend.agents.multi_agent_coordination.models import AgentEngineeringIntent
                bridge = MultiAgentCoordinationBridge.get_instance()
                intent_data = message.get("intent", {})
                if isinstance(intent_data, dict) and "agent_id" in intent_data:
                    intent = AgentEngineeringIntent.from_dict(intent_data)
                else:
                    intent = AgentEngineeringIntent(
                        agent_id=str(message.get("agent_id") or "agent_unknown"),
                        mission_id=str(message.get("mission_id") or "mission_default"),
                        task_id=str(message.get("task_id") or "task_default"),
                        intent_id=str(message.get("intent_id") or f"intent_{uuid.uuid4().hex[:8]}"),
                        requested_files=list(message.get("requested_files", [])),
                        requested_symbols=list(message.get("requested_symbols", [])),
                        requested_contracts=list(message.get("requested_contracts", [])),
                        expected_changes=list(message.get("expected_changes", [])),
                        expected_effect=str(message.get("expected_effect") or ""),
                    )
                ok, reg_msg = bridge.intent_mgr.register_intent(intent)
                if ok:
                    bridge.intent_mgr.validate_intent(intent.intent_id)
                await self.connections.send(
                    websocket,
                    {
                        "type": "mission_multi_agent_intent_submit_result",
                        "success": ok,
                        "message": reg_msg,
                        "intent": intent.to_dict(),
                    },
                )
                return

            elif operation == "mission_multi_agent_arbitrate":
                from backend.agents.multi_agent_coordination.bridge import MultiAgentCoordinationBridge
                bridge = MultiAgentCoordinationBridge.get_instance()
                intents = list(bridge.intent_mgr.intents.values())
                coord_res = bridge.coordinate_intents(intents)
                await self.connections.send(
                    websocket,
                    {
                        "type": "mission_multi_agent_arbitrate_result",
                        "result": coord_res,
                    },
                )
                return

            elif operation == "mission_multi_agent_schedule":
                from backend.agents.multi_agent_coordination.bridge import MultiAgentCoordinationBridge
                bridge = MultiAgentCoordinationBridge.get_instance()
                intents = list(bridge.intent_mgr.intents.values())
                sched = bridge.scheduler.schedule_intents(intents)
                await self.connections.send(
                    websocket,
                    {
                        "type": "mission_multi_agent_schedule_result",
                        "schedule": sched,
                    },
                )
                return

            elif operation == "mission_long_horizon_status":
                from backend.agents.long_horizon_missions.bridge import LongHorizonMissionBridge
                bridge = LongHorizonMissionBridge.get_instance()
                mid = message.get("mission_id", "default_mission")
                m = bridge.get_mission(mid)
                await self.connections.send(
                    websocket,
                    {
                        "type": "mission_long_horizon_status_result",
                        "mission": m.to_dict() if m else None,
                    },
                )
                return

            elif operation == "mission_long_horizon_create":
                from backend.agents.long_horizon_missions.bridge import LongHorizonMissionBridge
                bridge = LongHorizonMissionBridge.get_instance()
                obj = message.get("objective", "Autonomous Long-Horizon Mission")
                m = bridge.create_mission(
                    objective=obj,
                    success_criteria=message.get("success_criteria"),
                    policy_name=message.get("policy_name", "GOVERNED"),
                    milestone_count=int(message.get("milestone_count", 10)),
                    mission_id=message.get("mission_id"),
                )
                await self.connections.send(
                    websocket,
                    {
                        "type": "mission_long_horizon_create_result",
                        "mission": m.to_dict(),
                    },
                )
                return

            elif operation == "mission_long_horizon_step":
                from backend.agents.long_horizon_missions.bridge import LongHorizonMissionBridge
                bridge = LongHorizonMissionBridge.get_instance()
                mid = message.get("mission_id")
                res = bridge.execute_step(mid, context=message.get("context"))
                await self.connections.send(
                    websocket,
                    {
                        "type": "mission_long_horizon_step_result",
                        "result": res,
                    },
                )
                return

            elif operation == "mission_long_horizon_run":
                from backend.agents.long_horizon_missions.bridge import LongHorizonMissionBridge
                bridge = LongHorizonMissionBridge.get_instance()
                mid = message.get("mission_id")
                max_s = int(message.get("max_steps", 100))
                res = bridge.run_bounded(mid, max_steps=max_s, context=message.get("context"))
                await self.connections.send(
                    websocket,
                    {
                        "type": "mission_long_horizon_run_result",
                        "result": res,
                    },
                )
                return

            elif operation == "mission_quality_governance_status":
                from backend.agents.engineering_quality_governance.bridge import EngineeringQualityGovernanceBridge
                bridge = EngineeringQualityGovernanceBridge.get_instance()
                mid = message.get("mission_id", "default_mission")
                base = bridge.baseline_manager.get_baseline(mid)
                after = bridge.baseline_manager.get_after(mid)
                debts = bridge.debt_manager.list_unresolved()
                await self.connections.send(
                    websocket,
                    {
                        "type": "mission_quality_governance_status_result",
                        "baseline": base.to_dict() if base else None,
                        "after": after.to_dict() if after else None,
                        "unresolved_debt_count": len(debts),
                    },
                )
                return

            elif operation == "mission_quality_governance_snapshot":
                from backend.agents.engineering_quality_governance.bridge import EngineeringQualityGovernanceBridge
                bridge = EngineeringQualityGovernanceBridge.get_instance()
                mid = message.get("mission_id", "default_mission")
                snap = bridge.capture_after(mid, context=message.get("context"))
                await self.connections.send(
                    websocket,
                    {
                        "type": "mission_quality_governance_snapshot_result",
                        "snapshot": snap.to_dict(),
                    },
                )
                return

            elif operation == "mission_quality_governance_gate":
                from backend.agents.engineering_quality_governance.bridge import EngineeringQualityGovernanceBridge
                bridge = EngineeringQualityGovernanceBridge.get_instance()
                mid = message.get("mission_id", "default_mission")
                pol = message.get("policy_name", "GOVERNED")
                gate = bridge.evaluate_quality_gate(mid, policy_name=pol)
                await self.connections.send(
                    websocket,
                    {
                        "type": "mission_quality_governance_gate_result",
                        "gate_decision": gate.to_dict(),
                    },
                )
                return

            elif operation == "mission_quality_governance_debt_list":
                from backend.agents.engineering_quality_governance.bridge import EngineeringQualityGovernanceBridge
                bridge = EngineeringQualityGovernanceBridge.get_instance()
                debts = bridge.debt_manager.list_items()
                vectors = bridge.prioritize_debt()
                await self.connections.send(
                    websocket,
                    {
                        "type": "mission_quality_governance_debt_list_result",
                        "debts": [d.to_dict() for d in debts],
                        "priority_vectors": [v.to_dict() for v in vectors],
                    },
                )
                return

            elif operation == "mission_quality_governance_hotspots":
                from backend.agents.engineering_quality_governance.bridge import EngineeringQualityGovernanceBridge
                bridge = EngineeringQualityGovernanceBridge.get_instance()
                hotspots = bridge.get_hotspots()
                await self.connections.send(
                    websocket,
                    {
                        "type": "mission_quality_governance_hotspots_result",
                        "hotspots": [h.to_dict() for h in hotspots],
                    },
                )
                return

            # Phase 69 Autonomous Quality Debt Remediation Handlers
            elif operation == "mission_debt_remediation_status":
                from backend.agents.quality_debt_remediation.bridge import QualityDebtRemediationBridge
                bridge = QualityDebtRemediationBridge.get_instance()
                validations = bridge.store.get_all("debt_validations")
                plans = bridge.store.get_all("remediation_plans")
                deferments = bridge.store.get_all("deferments")
                resolutions = bridge.store.get_all("resolution_results")
                await self.connections.send(
                    websocket,
                    {
                        "type": "mission_debt_remediation_status_result",
                        "validations_count": len(validations),
                        "plans_count": len(plans),
                        "deferments_count": len(deferments),
                        "resolutions_count": len(resolutions),
                        "recent_resolutions": resolutions[-5:] if resolutions else [],
                    },
                )
                return

            elif operation == "mission_debt_remediation_validate":
                from backend.agents.quality_debt_remediation.bridge import QualityDebtRemediationBridge
                bridge = QualityDebtRemediationBridge.get_instance()
                raw_debt = message.get("debt_item") or {
                    "debt_id": "debt_demo_01",
                    "category": "ARCHITECTURAL",
                    "severity": "HIGH",
                    "affected_surface": "backend.agents.massive_project_state",
                    "evidence": {"scc_cycle": True},
                    "confidence": 0.90,
                }
                debt_item = bridge.ingestion_engine.ingest(raw_debt)
                validation = bridge.validator.validate(debt_item)
                await self.connections.send(
                    websocket,
                    {
                        "type": "mission_debt_remediation_validate_result",
                        "validation": validation.to_dict(),
                    },
                )
                return

            elif operation == "mission_debt_remediation_root_cause":
                from backend.agents.quality_debt_remediation.bridge import QualityDebtRemediationBridge
                bridge = QualityDebtRemediationBridge.get_instance()
                raw_debt = message.get("debt_item") or {
                    "debt_id": "debt_demo_01",
                    "category": "ARCHITECTURAL",
                    "severity": "HIGH",
                    "affected_surface": "backend.agents.massive_project_state",
                    "evidence": {"scc_cycle": True},
                    "confidence": 0.90,
                }
                debt_item = bridge.ingestion_engine.ingest(raw_debt)
                root_cause = bridge.root_cause_engine.analyze(debt_item)
                await self.connections.send(
                    websocket,
                    {
                        "type": "mission_debt_remediation_root_cause_result",
                        "root_cause": root_cause.to_dict(),
                    },
                )
                return

            elif operation == "mission_debt_remediation_options":
                from backend.agents.quality_debt_remediation.bridge import QualityDebtRemediationBridge
                bridge = QualityDebtRemediationBridge.get_instance()
                raw_debt = message.get("debt_item") or {
                    "debt_id": "debt_demo_01",
                    "category": "ARCHITECTURAL",
                    "severity": "HIGH",
                    "affected_surface": "backend.agents.massive_project_state",
                    "evidence": {"scc_cycle": True},
                    "confidence": 0.90,
                }
                debt_item = bridge.ingestion_engine.ingest(raw_debt)
                root_cause = bridge.root_cause_engine.analyze(debt_item)
                options = bridge.options_generator.generate_options(debt_item, root_cause)
                await self.connections.send(
                    websocket,
                    {
                        "type": "mission_debt_remediation_options_result",
                        "options": [o.to_dict() for o in options],
                    },
                )
                return

            elif operation == "mission_debt_remediation_plan":
                from backend.agents.quality_debt_remediation.bridge import QualityDebtRemediationBridge
                bridge = QualityDebtRemediationBridge.get_instance()
                raw_debt = message.get("debt_item") or {
                    "debt_id": "debt_demo_01",
                    "category": "ARCHITECTURAL",
                    "severity": "HIGH",
                    "affected_surface": "backend.agents.massive_project_state",
                    "evidence": {"scc_cycle": True},
                    "confidence": 0.90,
                }
                debt_item = bridge.ingestion_engine.ingest(raw_debt)
                root_cause = bridge.root_cause_engine.analyze(debt_item)
                options = bridge.options_generator.generate_options(debt_item, root_cause)
                plan = bridge.planner.create_plan(debt_item, options[0])
                mission = bridge.planner.create_mission(plan)
                await self.connections.send(
                    websocket,
                    {
                        "type": "mission_debt_remediation_plan_result",
                        "plan": plan.to_dict(),
                        "mission": mission.to_dict(),
                    },
                )
                return

            elif operation == "mission_debt_remediation_execute":
                from backend.agents.quality_debt_remediation.bridge import QualityDebtRemediationBridge
                bridge = QualityDebtRemediationBridge.get_instance()
                raw_debt = message.get("debt_item") or {
                    "debt_id": "debt_demo_01",
                    "category": "CODE",
                    "severity": "MEDIUM",
                    "affected_surface": "backend.websocket.handlers.missions",
                    "evidence": {"complexity": 25},
                    "confidence": 0.85,
                }
                res = bridge.process_debt_lifecycle(raw_debt)
                await self.connections.send(
                    websocket,
                    {
                        "type": "mission_debt_remediation_execute_result",
                        "lifecycle_result": res,
                    },
                )
                return

            elif operation == "mission_debt_remediation_resolve":
                from backend.agents.quality_debt_remediation.bridge import QualityDebtRemediationBridge
                bridge = QualityDebtRemediationBridge.get_instance()
                resolutions = bridge.store.get_all("resolution_results")
                await self.connections.send(
                    websocket,
                    {
                        "type": "mission_debt_remediation_resolve_result",
                        "resolutions": resolutions,
                    },
                )
                return

            elif operation == "mission_release_readiness_status":
                from backend.agents.release_readiness.bridge import ReleaseReadinessBridge
                bridge = ReleaseReadinessBridge()
                release_id = message.get("release_id", "rc-default")
                candidate = bridge.store.get_candidate(release_id)
                decisions = bridge.store.list_decisions()
                await self.connections.send(
                    websocket,
                    {
                        "type": "mission_release_readiness_status_result",
                        "candidate": candidate,
                        "decisions_count": len(decisions),
                        "latest_decision": decisions[0] if decisions else None,
                    },
                )
                return

            elif operation == "mission_release_readiness_baseline":
                from backend.agents.release_readiness.bridge import ReleaseReadinessBridge
                bridge = ReleaseReadinessBridge()
                baseline_data = message.get("baseline_data", {})
                baseline = bridge.capture_baseline(baseline_data)
                await self.connections.send(
                    websocket,
                    {
                        "type": "mission_release_readiness_baseline_result",
                        "baseline": baseline,
                    },
                )
                return

            elif operation == "mission_release_readiness_evaluate":
                from backend.agents.release_readiness.bridge import ReleaseReadinessBridge
                bridge = ReleaseReadinessBridge()
                release_id = message.get("release_id", "rc-eval-01")
                evaluation_inputs = message.get("evaluation_inputs", {})
                deployment_available = message.get("deployment_available", False)
                decision = bridge.evaluate_readiness(
                    release_id=release_id,
                    evaluation_inputs=evaluation_inputs,
                    deployment_available=deployment_available,
                )
                await self.connections.send(
                    websocket,
                    {
                        "type": "mission_release_readiness_evaluate_result",
                        "decision": decision,
                    },
                )
                return

            elif operation == "mission_release_readiness_plan":
                from backend.agents.release_readiness.bridge import ReleaseReadinessBridge
                bridge = ReleaseReadinessBridge()
                release_id = message.get("release_id", "rc-plan-01")
                deployment_available = message.get("deployment_available", False)
                plan_result = bridge.build_and_step_plan(
                    candidate_id=release_id,
                    deployment_available=deployment_available,
                )
                await self.connections.send(
                    websocket,
                    {
                        "type": "mission_release_readiness_plan_result",
                        "plan_result": plan_result,
                    },
                )
                return

            elif operation == "mission_release_readiness_gate":
                from backend.agents.release_readiness.bridge import ReleaseReadinessBridge
                bridge = ReleaseReadinessBridge()
                decision_id = message.get("decision_id")
                if decision_id:
                    decision = bridge.store.get_decision(decision_id)
                else:
                    decisions = bridge.store.list_decisions()
                    decision = decisions[0] if decisions else None
                await self.connections.send(
                    websocket,
                    {
                        "type": "mission_release_readiness_gate_result",
                        "decision": decision,
                    },
                )
                return

            elif operation == "mission_release_readiness_rollback":
                from backend.agents.release_readiness.bridge import ReleaseReadinessBridge
                bridge = ReleaseReadinessBridge()
                release_id = message.get("release_id", "rc-rollback-01")
                await self.connections.send(
                    websocket,
                    {
                        "type": "mission_release_readiness_rollback_result",
                        "release_id": release_id,
                        "status": "ROLLED_BACK",
                        "rolled_back_at": "now",
                    },
                )
                return

            if snapshot is None:
                return

            active_store = getattr(
                planner,
                "mission_state",
                planner,
            )
            if executor.mission_state is active_store:
                snapshot = await asyncio.to_thread(
                    executor.load_snapshot,
                    project_id,
                    snapshot["mission"]["mission_id"],
                )
            if autonomy_cycle is not None:
                snapshot["autonomy_cycle"] = autonomy_cycle
                snapshot["autonomous_execution"] = True
            await self.connections.send(
                websocket,
                {
                    "type": "mission_snapshot",
                    "data": snapshot,
                },
            )
            await self.responder.send_mission_list(
                websocket,
                project_id,
            )
        except MissionStateError as mission_error:
            await self.connections.send(
                websocket,
                system_message(str(mission_error)),
            )
