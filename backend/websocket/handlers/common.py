from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, Callable

from backend.logging_config import log_event
from backend.message_protocol import system_message
from backend.websocket.context import WebSocketSessionState
from backend.websocket.gateway import ConnectionManager
from intelligence.project_context import ProjectContextError


@dataclass(slots=True)
class WebSocketRuntimeCallbacks:
    handle_slash_command: Callable[..., Any]
    parse_file_context: Callable[[str], str]
    run_orchestration_task: Callable[..., Any]
    broadcast_state: Callable[..., Any]
    run_in_main_loop: Callable[..., Any]
    normalize_template_name: Callable[[str], str]
    build_template_payload: Callable[[str], dict]
    read_persistent_plan_state: Callable[[], Any]
    get_voice_service: Callable[[], Any]
    conversation_history: list[dict]


class WebSocketResponder:
    def __init__(
        self,
        project_context: Any,
        coding_sessions: Any,
        mission_planner: Any,
        connections: ConnectionManager,
    ) -> None:
        self.project_context = project_context
        self.coding_sessions = coding_sessions
        self.mission_planner = mission_planner
        self.connections = connections

    async def send_project_context(
        self,
        websocket: Any,
        project_id: str,
        *,
        reindex: bool = False,
    ) -> None:
        payload = await asyncio.to_thread(
            self.project_context.project_payload,
            project_id,
            reindex,
        )
        await self.connections.send(
            websocket,
            {"type": "project_context", **payload},
        )
        await self.connections.send(
            websocket,
            {
                "type": "ast_state",
                "data": payload.get("symbols") or None,
            },
        )

    async def send_latest_coding_session(
        self,
        websocket: Any,
        project_id: str,
    ) -> None:
        coding_session = await asyncio.to_thread(
            self.coding_sessions.latest,
            project_id,
        )
        await self.connections.send(
            websocket,
            {
                "type": "coding_session",
                "data": (
                    coding_session.to_dict()
                    if coding_session
                    else None
                ),
            },
        )

    async def send_mission_list(
        self,
        websocket: Any,
        project_id: str,
    ) -> None:
        missions = await asyncio.to_thread(
            self.mission_planner.list_missions,
            project_id,
        )
        await self.connections.send(
            websocket,
            {
                "type": "mission_list",
                "project_id": project_id,
                "missions": missions,
            },
        )


class InitialSyncHandler:
    def __init__(
        self,
        agents: Any,
        database: Any,
        project_context: Any,
        responder: WebSocketResponder,
        callbacks: WebSocketRuntimeCallbacks,
        logger: Any,
    ) -> None:
        self.agents = agents
        self.database = database
        self.project_context = project_context
        self.responder = responder
        self.callbacks = callbacks
        self.logger = logger

    async def handle(
        self,
        websocket: Any,
        session: WebSocketSessionState,
    ) -> None:
        send = self.responder.connections.send
        await send(
            websocket,
            system_message(
                "Conectado ao servidor Jarvis WebSocket na porta 8001!"
            ),
        )

        template_name = self.callbacks.normalize_template_name(
            getattr(
                self.agents,
                "active_template_name",
                "builder_swarm",
            )
        )
        self.agents.active_template_name = template_name
        await send(
            websocket,
            self.callbacks.build_template_payload(template_name),
        )

        await send(
            websocket,
            {
                "type": "rules_list",
                "rules": (
                    self.database.get_compounding_rules()
                ),
            },
        )
        await send(
            websocket,
            {
                "type": "architecture_list",
                "architecture": (
                    self.database.get_architecture_memory()
                ),
            },
        )
        await send(
            websocket,
            {
                "type": "decisions_list",
                "decisions": (
                    self.database.get_engineering_decisions()
                ),
            },
        )
        notes = await self.agents.run_obsidian_list_notes()
        await send(
            websocket,
            {
                "type": "notes_list",
                "notes": notes_from_output(notes),
            },
        )

        projects = self.project_context.list_projects()
        await send(
            websocket,
            {"type": "projects_list", "projects": projects},
        )
        if not projects:
            return

        project_ids = [
            project["project_id"]
            for project in projects
        ]
        session.selected_project_id = (
            "task-app"
            if "task-app" in project_ids
            else project_ids[0]
        )
        try:
            await self.responder.send_project_context(
                websocket,
                session.selected_project_id,
            )
            await self.responder.send_latest_coding_session(
                websocket,
                session.selected_project_id,
            )
            await self.responder.send_mission_list(
                websocket,
                session.selected_project_id,
            )
        except ProjectContextError as project_error:
            log_event(
                self.logger,
                "project_context.initial_error",
                level="warning",
                error=str(project_error),
            )


def notes_from_output(notes: str) -> list[str]:
    return [
        line.strip()
        for line in notes.split("\n")
        if line.strip() and not line.startswith("(Nenhuma")
    ]
