from __future__ import annotations

import asyncio
import json
import os
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
