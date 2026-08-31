from __future__ import annotations

import asyncio
from typing import Any

from backend.errors import safe_user_error
from backend.logging_config import log_event
from backend.message_protocol import system_message
from backend.websocket.context import WebSocketSessionState
from backend.websocket.contracts import MessageHandler
from backend.websocket.handlers import bind_handler_methods
from backend.websocket.handlers.common import (
    WebSocketResponder,
    WebSocketRuntimeCallbacks,
)
from intelligence.project_context import ProjectContextError


PROJECT_HANDLERS = {
    "run_project": "run_project",
    "stop_project": "stop_project",
    "list_projects": "list_projects",
    "create_project": "create_project",
    "open_project": "open_project",
    "save_project_file": "save_project_file",
    "delete_project_file": "delete_project_file",
    "delete_project": "delete_project",
    "index_project": "index_project",
    "find_references": "find_references",
    "semantic_search": "semantic_search",
}


class ProjectWebSocketHandler:
    def __init__(
        self,
        project_context: Any,
        sandbox: Any,
        responder: WebSocketResponder,
        callbacks: WebSocketRuntimeCallbacks,
        logger: Any,
    ) -> None:
        self.project_context = project_context
        self.sandbox = sandbox
        self.responder = responder
        self.callbacks = callbacks
        self.logger = logger
        self.connections = responder.connections

    def routes(self) -> dict[str, MessageHandler]:
        return bind_handler_methods(self, PROJECT_HANDLERS)

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
                self.project_context.preview_project(
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
        self.sandbox.stop_custom_project()
        await self.connections.send(
            websocket,
            {"type": "project_status", "running": False},
        )
        await self.connections.send(
            websocket,
            {
                "type": "project_output",
                "content": (
                    "[Sandbox] Execução interrompida.\n"
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
                    self.project_context.list_projects()
                ),
            },
        )

    async def create_project(
        self,
        websocket: Any,
        message: dict,
        session: WebSocketSessionState,
    ) -> None:
        project_id = str(message.get("project_id", "")).strip()
        project_name = message.get("project_name")
        template = message.get("template")
        try:
            context = await asyncio.to_thread(
                self.project_context.create_project,
                project_id,
                project_name,
                template,
            )
            session.selected_project_id = context.project_id
            await self.responder.send_project_context(
                websocket,
                context.project_id,
            )
            projects = self.project_context.list_projects()
            await self.connections.broadcast(
                {
                    "type": "projects_list",
                    "projects": projects,
                }
            )
            await self.connections.send(
                websocket,
                system_message(f"Projeto '{context.project_name}' criado com sucesso."),
            )
        except Exception as project_error:
            await self.connections.send(
                websocket,
                system_message(f"Erro ao criar projeto: {project_error}"),
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
                self.project_context.save_project_file,
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

    async def delete_project(
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
            result = await asyncio.to_thread(
                self.project_context.delete_project,
                project_id,
            )
            was_active = session.selected_project_id == project_id
            if was_active:
                session.selected_project_id = None
            await self.connections.send(
                websocket,
                {
                    "type": "project_deleted",
                    "ok": True,
                    "project_id": project_id,
                    "was_active": was_active,
                },
            )
            await self.list_projects(websocket, {}, session)
            await self.connections.send(
                websocket,
                system_message(f"Projeto '{project_id}' eliminado com sucesso."),
            )
        except (ProjectContextError, OSError, Exception) as delete_error:
            await self.connections.send(
                websocket,
                {
                    "type": "project_delete_error",
                    "project_id": project_id,
                    "error": str(delete_error),
                },
            )
            await self.connections.send(
                websocket,
                system_message(f"Erro ao eliminar projeto: {delete_error}"),
            )

    async def delete_project_file(
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
                self.project_context.delete_project_file,
                project_id,
                filename,
            )
            await self.connections.send(
                websocket,
                {
                    "type": "project_file_deleted",
                    "ok": True,
                    **result,
                },
            )
            await self.responder.send_project_context(
                websocket,
                project_id,
            )
            await self.connections.send(
                websocket,
                system_message(f"Ficheiro '{filename}' eliminado com sucesso."),
            )
        except (ProjectContextError, OSError, Exception) as delete_error:
            await self.connections.send(
                websocket,
                {
                    "type": "project_file_delete_error",
                    "project_id": project_id,
                    "filename": filename,
                    "error": str(delete_error),
                },
            )
            await self.connections.send(
                websocket,
                system_message(f"Erro ao eliminar ficheiro: {delete_error}"),
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
                self.project_context.find_references,
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
                self.project_context.semantic_search,
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
