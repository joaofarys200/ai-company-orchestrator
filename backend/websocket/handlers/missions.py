from __future__ import annotations

import asyncio
from typing import Any, Mapping

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
                    message.get(
                        "work_package_type",
                        "GENERIC",
                    ),
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
                    message.get("dependency_id"),
                    message.get("expected_version"),
                )
            elif operation == "deliverable_create":
                snapshot = await asyncio.to_thread(
                    planner.create_deliverable,
                    project_id,
                    message.get("mission_id"),
                    message.get("work_package_id"),
                    message.get("name"),
                    message.get("kind", "GENERIC"),
                    message.get("description", ""),
                    message.get("artifact_refs"),
                    message.get("required", False),
                    message.get(
                        "expected_work_package_version"
                    ),
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
