from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, Callable, Mapping

from agents.mission_state import MissionStateError
from backend.application_services import ApplicationServices
from backend.errors import safe_user_error
from backend.logging_config import log_event
from backend.message_protocol import (
    CLIENT_MESSAGE_TYPES,
    system_message,
)
from backend.services.voice_service import normalize_voice_prompt
from backend.websocket_dispatcher import (
    MessageHandler,
    WebSocketDispatcher,
    WebSocketSessionState,
)
from backend.websocket_gateway import ConnectionManager
from intelligence.coding_session import CodingSessionError
from intelligence.project_context import (
    ProjectContextError,
)


def message_type(message: Mapping[str, Any]) -> str:
    return str(message.get("type", ""))


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
        services: ApplicationServices,
        connections: ConnectionManager,
    ) -> None:
        self.services = services
        self.connections = connections

    async def send_project_context(
        self,
        websocket: Any,
        project_id: str,
        *,
        reindex: bool = False,
    ) -> None:
        payload = await asyncio.to_thread(
            self.services.project_context.project_payload,
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
            self.services.coding_sessions.latest,
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
            self.services.mission_planner.list_missions,
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
        services: ApplicationServices,
        responder: WebSocketResponder,
        callbacks: WebSocketRuntimeCallbacks,
        logger: Any,
    ) -> None:
        self.services = services
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
                self.services.agents,
                "active_template_name",
                "builder_swarm",
            )
        )
        self.services.agents.active_template_name = template_name
        await send(
            websocket,
            self.callbacks.build_template_payload(template_name),
        )

        await send(
            websocket,
            {
                "type": "rules_list",
                "rules": (
                    self.services.database.get_compounding_rules()
                ),
            },
        )
        await send(
            websocket,
            {
                "type": "architecture_list",
                "architecture": (
                    self.services.database.get_architecture_memory()
                ),
            },
        )
        await send(
            websocket,
            {
                "type": "decisions_list",
                "decisions": (
                    self.services.database.get_engineering_decisions()
                ),
            },
        )
        notes = await self.services.agents.run_obsidian_list_notes()
        await send(
            websocket,
            {
                "type": "notes_list",
                "notes": _notes_from_output(notes),
            },
        )

        projects = self.services.project_context.list_projects()
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


class ChatWebSocketHandler:
    def __init__(
        self,
        services: ApplicationServices,
        connections: ConnectionManager,
        callbacks: WebSocketRuntimeCallbacks,
        logger: Any,
    ) -> None:
        self.services = services
        self.connections = connections
        self.callbacks = callbacks
        self.logger = logger

    def routes(self) -> dict[str, MessageHandler]:
        return {
            "directive": self.directive,
            "select_template": self.select_template,
        }

    async def directive(
        self,
        websocket: Any,
        message: dict,
        _session: WebSocketSessionState,
    ) -> None:
        prompt = str(message.get("text") or "").strip()
        if not prompt:
            return
        prompt = normalize_voice_prompt(prompt)
        if prompt.startswith("/"):
            await self.callbacks.handle_slash_command(
                prompt,
                websocket,
                1,
            )
            return

        prompt_with_context = self.callbacks.parse_file_context(
            prompt
        )
        if prompt_with_context != prompt:
            mentions_count = prompt_with_context.count(
                "--- ConteÃºdo do ficheiro @"
            )
            await self.connections.send(
                websocket,
                {
                    "type": "system",
                    "content": (
                        f"ðŸ“Ž {mentions_count} ficheiro(s) "
                        "injetados como contexto via @mention."
                    ),
                },
            )

        history = self.callbacks.conversation_history
        history.append(
            {"role": "user", "content": prompt_with_context}
        )
        if len(history) > 100:
            history.pop(0)
        log_event(
            self.logger,
            "websocket.directive.received",
            prompt_length=len(prompt),
        )
        database_session = self.services.database.create_session(
            prompt
        )
        await self.callbacks.broadcast_state("processing")
        await self.connections.broadcast(
            {
                "type": "system",
                "content": f"OrquestraÃ§Ã£o iniciada: {prompt}",
            }
        )
        asyncio.create_task(
            self.callbacks.run_orchestration_task(
                prompt_with_context,
                database_session.id,
            )
        )

    async def select_template(
        self,
        websocket: Any,
        message: dict,
        _session: WebSocketSessionState,
    ) -> None:
        requested = message.get("template", "builder_swarm")
        template_name = self.callbacks.normalize_template_name(
            requested
        )
        self.services.agents.active_template_name = template_name
        if requested != template_name:
            await self.connections.send(
                websocket,
                {
                    "type": "system",
                    "content": (
                        f"Template desconhecido '{requested}'. "
                        "A usar Builder Swarm."
                    ),
                },
            )
        await self.connections.broadcast(
            self.callbacks.build_template_payload(template_name)
        )


class VoiceWebSocketHandler:
    def __init__(
        self,
        connections: ConnectionManager,
        callbacks: WebSocketRuntimeCallbacks,
    ) -> None:
        self.connections = connections
        self.callbacks = callbacks

    def routes(self) -> dict[str, MessageHandler]:
        return {"toggle_voice": self.toggle_voice}

    async def toggle_voice(
        self,
        websocket: Any,
        message: dict,
        _session: WebSocketSessionState,
    ) -> None:
        voice_service = self.callbacks.get_voice_service()
        active = bool(message.get("active", False))
        if active:
            try:
                if voice_service:
                    voice_service.start()
                    await self.connections.send(
                        websocket,
                        {
                            "type": "system",
                            "content": (
                                "Reconhecimento de Voz Jarvis OS "
                                "(VAD Python) ativado no Servidor."
                            ),
                        },
                    )
                    await self.connections.broadcast(
                        {
                            "type": "voice_status",
                            "status": "idle",
                        }
                    )
                else:
                    await self.connections.send(
                        websocket,
                        {
                            "type": "system",
                            "content": (
                                "Reconhecimento de Voz estÃ¡ "
                                "desativado no .env "
                                "(VOICE_MODE=none)."
                            ),
                        },
                    )
            except Exception as voice_error:
                await self.connections.send(
                    websocket,
                    {
                        "type": "system",
                        "content": safe_user_error(
                            "Erro ao ativar voz",
                            voice_error,
                        ),
                    },
                )
            return

        if voice_service:
            voice_service.stop()
        await self.connections.send(
            websocket,
            {
                "type": "system",
                "content": (
                    "Reconhecimento de Voz Jarvis OS "
                    "(VAD Python) desativado."
                ),
            },
        )
        await self.connections.broadcast(
            {"type": "voice_status", "status": "offline"}
        )


class ProjectWebSocketHandler:
    def __init__(
        self,
        services: ApplicationServices,
        responder: WebSocketResponder,
        callbacks: WebSocketRuntimeCallbacks,
        logger: Any,
    ) -> None:
        self.services = services
        self.responder = responder
        self.callbacks = callbacks
        self.logger = logger
        self.connections = responder.connections

    def routes(self) -> dict[str, MessageHandler]:
        return {
            "run_project": self.run_project,
            "stop_project": self.stop_project,
            "list_projects": self.list_projects,
            "open_project": self.open_project,
            "save_project_file": self.save_project_file,
            "index_project": self.index_project,
            "find_references": self.find_references,
            "semantic_search": self.semantic_search,
        }

    async def run_project(
        self,
        websocket: Any,
        message: dict,
        session: WebSocketSessionState,
    ) -> None:
        project_id = (
            message.get("project_id")
            or session.selected_project_id
        )
        if not project_id:
            await self.connections.send(
                websocket,
                system_message(
                    "Selecione um projeto antes de iniciar o preview."
                ),
            )
            return
        await self.connections.send(
            websocket,
            {
                "type": "project_output",
                "content": (
                    f"[Project] A preparar preview de "
                    f"{project_id}...\n"
                ),
            },
        )

        def on_sandbox_output(content: str) -> None:
            self.callbacks.run_in_main_loop(
                self.connections.broadcast(
                    {
                        "type": "project_output",
                        "content": content,
                    }
                )
            )

        try:
            project_run = (
                self.services.project_context.preview_project(
                    project_id,
                    on_sandbox_output,
                )
            )
            session.selected_project_id = project_id
        except ProjectContextError as project_error:
            await self.connections.send(
                websocket,
                system_message(str(project_error)),
            )
            await self.connections.send(
                websocket,
                {
                    "type": "project_status",
                    "running": False,
                    "preview_url": "",
                },
            )
            return

        if isinstance(project_run, dict):
            project_running = bool(project_run.get("running"))
            preview_url = project_run.get("preview_url")
        else:
            project_running = bool(project_run)
            preview_url = None
        await self.connections.send(
            websocket,
            {
                "type": "project_status",
                "running": project_running,
                "preview_url": preview_url,
            },
        )

    async def stop_project(
        self,
        websocket: Any,
        _message: dict,
        _session: WebSocketSessionState,
    ) -> None:
        self.services.sandbox.stop_custom_project()
        await self.connections.send(
            websocket,
            {"type": "project_status", "running": False},
        )
        await self.connections.send(
            websocket,
            {
                "type": "project_output",
                "content": (
                    "[Sandbox] ExecuÃ§Ã£o interrompida.\n"
                ),
            },
        )

    async def list_projects(
        self,
        websocket: Any,
        _message: dict,
        _session: WebSocketSessionState,
    ) -> None:
        await self.connections.send(
            websocket,
            {
                "type": "projects_list",
                "projects": (
                    self.services.project_context.list_projects()
                ),
            },
        )

    async def open_project(
        self,
        websocket: Any,
        message: dict,
        session: WebSocketSessionState,
    ) -> None:
        project_id = message.get("project_id")
        try:
            await self.responder.send_project_context(
                websocket,
                project_id,
            )
            await self.responder.send_latest_coding_session(
                websocket,
                project_id,
            )
            await self.responder.send_mission_list(
                websocket,
                project_id,
            )
            session.selected_project_id = project_id
        except ProjectContextError as project_error:
            await self.connections.send(
                websocket,
                system_message(str(project_error)),
            )

    async def save_project_file(
        self,
        websocket: Any,
        message: dict,
        session: WebSocketSessionState,
    ) -> None:
        project_id = (
            message.get("project_id")
            or session.selected_project_id
        )
        filename = str(message.get("filename") or "")
        try:
            result = await asyncio.to_thread(
                self.services.project_context.save_project_file,
                project_id,
                filename,
                message.get("content"),
                message.get("expected_sha256"),
            )
            session.selected_project_id = project_id
            await self.connections.send(
                websocket,
                {
                    "type": "project_file_save_result",
                    "ok": True,
                    **result,
                },
            )
            await self.responder.send_project_context(
                websocket,
                project_id,
            )
        except (ProjectContextError, OSError) as save_error:
            await self.connections.send(
                websocket,
                {
                    "type": "project_file_save_result",
                    "ok": False,
                    "project_id": project_id,
                    "filename": filename,
                    "error": str(save_error),
                },
            )

    async def index_project(
        self,
        websocket: Any,
        message: dict,
        session: WebSocketSessionState,
    ) -> None:
        project_id = (
            message.get("project_id")
            or session.selected_project_id
        )
        if not project_id:
            await self.connections.send(
                websocket,
                system_message(
                    "Selecione um projeto antes de reindexar."
                ),
            )
            return
        try:
            await self.responder.send_project_context(
                websocket,
                project_id,
                reindex=True,
            )
            session.selected_project_id = project_id
        except ProjectContextError as project_error:
            await self.connections.send(
                websocket,
                system_message(str(project_error)),
            )

    async def find_references(
        self,
        websocket: Any,
        message: dict,
        session: WebSocketSessionState,
    ) -> None:
        project_id = (
            message.get("project_id")
            or session.selected_project_id
        )
        try:
            reference_data = await asyncio.to_thread(
                self.services.project_context.find_references,
                project_id,
                message.get("symbol", ""),
            )
            await self.connections.send(
                websocket,
                {
                    "type": "project_references",
                    "data": reference_data,
                },
            )
        except ProjectContextError as project_error:
            await self.connections.send(
                websocket,
                system_message(str(project_error)),
            )

    async def semantic_search(
        self,
        websocket: Any,
        message: dict,
        session: WebSocketSessionState,
    ) -> None:
        project_id = (
            message.get("project_id")
            or session.selected_project_id
        )
        query = str(message.get("query") or "").strip()
        if not project_id or not query:
            await self.connections.send(
                websocket,
                system_message(
                    "Selecione um projeto e indique uma pesquisa."
                ),
            )
            return
        try:
            results = await asyncio.to_thread(
                self.services.project_context.semantic_search,
                project_id,
                query,
            )
            await self.connections.send(
                websocket,
                {
                    "type": "semantic_results",
                    "query": query,
                    "content": results,
                },
            )
        except Exception as search_error:
            log_event(
                self.logger,
                "project.semantic_search_error",
                level="warning",
                error=str(search_error),
            )
            await self.connections.send(
                websocket,
                system_message(
                    safe_user_error(
                        "Pesquisa semantica indisponivel",
                        search_error,
                    )
                ),
            )


class CodingSessionWebSocketHandler:
    def __init__(
        self,
        services: ApplicationServices,
        responder: WebSocketResponder,
    ) -> None:
        self.services = services
        self.responder = responder
        self.connections = responder.connections

    def routes(self) -> dict[str, MessageHandler]:
        return {
            "create_coding_session": self.create_session,
            "apply_coding_session": self.apply_session,
            "rollback_coding_session": self.rollback_session,
            "get_coding_session": self.get_session,
        }

    async def create_session(
        self,
        websocket: Any,
        message: dict,
        session: WebSocketSessionState,
    ) -> None:
        project_id = (
            message.get("project_id")
            or session.selected_project_id
        )
        objective = str(message.get("objective") or "").strip()
        if not project_id or not objective:
            await self.connections.send(
                websocket,
                system_message(
                    "Selecione um projeto e indique o objetivo "
                    "da alteracao."
                ),
            )
            return
        try:
            coding_session = (
                await self.services.coding_sessions
                .create_assisted_session(project_id, objective)
            )
            session.selected_project_id = project_id
            await self.connections.send(
                websocket,
                {
                    "type": "coding_session",
                    "data": coding_session.to_dict(),
                },
            )
        except (
            CodingSessionError,
            ProjectContextError,
        ) as coding_error:
            await self.connections.send(
                websocket,
                system_message(str(coding_error)),
            )

    async def apply_session(
        self,
        websocket: Any,
        message: dict,
        session: WebSocketSessionState,
    ) -> None:
        project_id = (
            message.get("project_id")
            or session.selected_project_id
        )
        try:
            coding_session = await asyncio.to_thread(
                self.services.coding_sessions.apply_session,
                project_id,
                message.get("session_id"),
            )
            await self.connections.send(
                websocket,
                {
                    "type": "coding_session",
                    "data": coding_session.to_dict(),
                },
            )
            await self.responder.send_project_context(
                websocket,
                project_id,
            )
        except (
            CodingSessionError,
            ProjectContextError,
        ) as coding_error:
            await self.connections.send(
                websocket,
                system_message(str(coding_error)),
            )

    async def rollback_session(
        self,
        websocket: Any,
        message: dict,
        session: WebSocketSessionState,
    ) -> None:
        project_id = (
            message.get("project_id")
            or session.selected_project_id
        )
        try:
            coding_session = await asyncio.to_thread(
                self.services.coding_sessions.rollback_session,
                project_id,
                message.get("session_id"),
                bool(message.get("confirmed")),
            )
            await self.connections.send(
                websocket,
                {
                    "type": "coding_session",
                    "data": coding_session.to_dict(),
                },
            )
            await self.responder.send_project_context(
                websocket,
                project_id,
            )
        except (
            CodingSessionError,
            ProjectContextError,
        ) as coding_error:
            await self.connections.send(
                websocket,
                system_message(str(coding_error)),
            )

    async def get_session(
        self,
        websocket: Any,
        message: dict,
        session: WebSocketSessionState,
    ) -> None:
        project_id = (
            message.get("project_id")
            or session.selected_project_id
        )
        if project_id:
            await self.responder.send_latest_coding_session(
                websocket,
                project_id,
            )


class KnowledgeWebSocketHandler:
    def __init__(
        self,
        services: ApplicationServices,
        connections: ConnectionManager,
    ) -> None:
        self.services = services
        self.connections = connections

    def routes(self) -> dict[str, MessageHandler]:
        return {
            "get_notes": self.get_notes,
            "read_note": self.read_note,
            "save_note": self.save_note,
            "get_rules": self.get_rules,
            "delete_rule": self.delete_rule,
            "delete_architecture": self.delete_architecture,
            "delete_decision": self.delete_decision,
        }

    async def get_notes(
        self,
        websocket: Any,
        _message: dict,
        _session: WebSocketSessionState,
    ) -> None:
        notes = await self.services.agents.run_obsidian_list_notes()
        await self.connections.send(
            websocket,
            {
                "type": "notes_list",
                "notes": _notes_from_output(notes),
            },
        )

    async def read_note(
        self,
        websocket: Any,
        message: dict,
        _session: WebSocketSessionState,
    ) -> None:
        filename = message.get("filename")
        content = await self.services.agents.run_obsidian_read_note(
            filename
        )
        await self.connections.send(
            websocket,
            {
                "type": "note_content",
                "filename": filename,
                "content": content,
            },
        )

    async def save_note(
        self,
        websocket: Any,
        message: dict,
        _session: WebSocketSessionState,
    ) -> None:
        filename = message.get("filename")
        result = await self.services.agents.run_obsidian_write_note(
            filename,
            message.get("content"),
        )
        notes = await self.services.agents.run_obsidian_list_notes()
        await self.connections.broadcast(
            {
                "type": "notes_list",
                "notes": _notes_from_output(notes),
            }
        )
        await self.connections.send(
            websocket,
            {
                "type": "note_saved",
                "filename": filename,
                "result": result,
            },
        )

    async def get_rules(
        self,
        websocket: Any,
        _message: dict,
        _session: WebSocketSessionState,
    ) -> None:
        await self.connections.send(
            websocket,
            {
                "type": "rules_list",
                "rules": (
                    self.services.database.get_compounding_rules()
                ),
            },
        )

    async def delete_rule(
        self,
        _websocket: Any,
        message: dict,
        _session: WebSocketSessionState,
    ) -> None:
        self.services.database.delete_compounding_rule(
            message.get("key")
        )
        rules = self.services.database.get_compounding_rules()
        await self.connections.broadcast(
            {"type": "rules_list", "rules": rules}
        )
        await self.connections.broadcast(
            {"type": "rules_updated", "rules": rules}
        )

    async def delete_architecture(
        self,
        _websocket: Any,
        message: dict,
        _session: WebSocketSessionState,
    ) -> None:
        self.services.database.delete_architecture_memory(
            message.get("module")
        )
        architecture = (
            self.services.database.get_architecture_memory()
        )
        await self.connections.broadcast(
            {
                "type": "architecture_updated",
                "architecture": architecture,
            }
        )

    async def delete_decision(
        self,
        _websocket: Any,
        message: dict,
        _session: WebSocketSessionState,
    ) -> None:
        self.services.database.delete_engineering_decision(
            message.get("decision")
        )
        decisions = (
            self.services.database.get_engineering_decisions()
        )
        await self.connections.broadcast(
            {
                "type": "decisions_updated",
                "decisions": decisions,
            }
        )


class SystemWebSocketHandler:
    def __init__(
        self,
        services: ApplicationServices,
        connections: ConnectionManager,
        callbacks: WebSocketRuntimeCallbacks,
    ) -> None:
        self.services = services
        self.connections = connections
        self.callbacks = callbacks

    def routes(self) -> dict[str, MessageHandler]:
        return {
            "get_planner_state": self.get_planner_state,
            "get_ast_state": self.get_ast_state,
        }

    async def get_planner_state(
        self,
        websocket: Any,
        _message: dict,
        _session: WebSocketSessionState,
    ) -> None:
        await self.connections.send(
            websocket,
            {
                "type": "planner_state",
                "data": (
                    self.callbacks.read_persistent_plan_state()
                ),
            },
        )

    async def get_ast_state(
        self,
        websocket: Any,
        message: dict,
        session: WebSocketSessionState,
    ) -> None:
        project_id = (
            message.get("project_id")
            or session.selected_project_id
        )
        ast_data = (
            self.services.project_context.load_index(project_id)
            if project_id
            else {}
        )
        await self.connections.send(
            websocket,
            {
                "type": "ast_state",
                "data": ast_data or None,
            },
        )


class MissionWebSocketHandler:
    OPERATIONS = frozenset(
        {
            "mission_list",
            "mission_create",
            "mission_get",
            "mission_update",
            "mission_set_status",
            "work_package_create",
            "work_package_update",
            "work_package_set_status",
            "work_package_add_dependency",
            "deliverable_create",
            "deliverable_update",
            "deliverable_set_status",
            "evidence_attach",
            "criterion_create",
            "criterion_set_status",
            "mission_resume_snapshot",
            "mission_execute_work_package",
            "mission_apply_execution",
            "mission_review_execution",
            "mission_retry_execution",
            "mission_cancel_execution",
            "mission_release_stale_lock",
            "mission_autonomy_run",
        }
    )

    def __init__(
        self,
        services: ApplicationServices,
        responder: WebSocketResponder,
    ) -> None:
        self.services = services
        self.responder = responder
        self.connections = responder.connections

    def routes(self) -> dict[str, MessageHandler]:
        return {
            operation: self.handle
            for operation in self.OPERATIONS
        }

    async def handle(
        self,
        websocket: Any,
        message: dict,
        session: WebSocketSessionState,
    ) -> None:
        operation = message_type(message)
        project_id = str(
            message.get("project_id")
            or session.selected_project_id
            or ""
        ).strip()
        try:
            snapshot = None
            autonomy_cycle = None
            planner = self.services.mission_planner
            executor = self.services.mission_executor
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
                    await self.services.mission_autonomy.run_cycle(
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


def create_websocket_handlers(
    *,
    services: ApplicationServices,
    connections: ConnectionManager,
    callbacks: WebSocketRuntimeCallbacks,
    logger: Any,
) -> tuple[WebSocketDispatcher, InitialSyncHandler]:
    responder = WebSocketResponder(services, connections)
    dispatcher = WebSocketDispatcher()
    domains = {
        "chat": ChatWebSocketHandler(
            services,
            connections,
            callbacks,
            logger,
        ).routes(),
        "voice": VoiceWebSocketHandler(
            connections,
            callbacks,
        ).routes(),
        "project": ProjectWebSocketHandler(
            services,
            responder,
            callbacks,
            logger,
        ).routes(),
        "coding": CodingSessionWebSocketHandler(
            services,
            responder,
        ).routes(),
        "knowledge": KnowledgeWebSocketHandler(
            services,
            connections,
        ).routes(),
        "system": SystemWebSocketHandler(
            services,
            connections,
            callbacks,
        ).routes(),
        "mission": MissionWebSocketHandler(
            services,
            responder,
        ).routes(),
    }
    for domain, routes in domains.items():
        dispatcher.register_many(routes, domain=domain)

    missing = CLIENT_MESSAGE_TYPES - dispatcher.message_types
    extra = dispatcher.message_types - CLIENT_MESSAGE_TYPES
    if missing or extra:
        raise RuntimeError(
            "WebSocket handler registry diverges from protocol: "
            f"missing={sorted(missing)}, extra={sorted(extra)}"
        )
    initial_sync = InitialSyncHandler(
        services,
        responder,
        callbacks,
        logger,
    )
    return dispatcher, initial_sync


def _notes_from_output(notes: str) -> list[str]:
    return [
        line.strip()
        for line in notes.split("\n")
        if line.strip() and not line.startswith("(Nenhuma")
    ]
