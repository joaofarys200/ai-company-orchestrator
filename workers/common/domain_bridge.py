"""Shared stdio JSON-RPC domain dispatcher bridge for Python sidecar workers.

Connects each specialized worker role (`ai`, `study`, `knowledge`, `mission`, `voice`) to
its existing domain handlers (`WebSocketDispatcher` + `ApplicationServices`) over
authenticated Rust <-> Python NDJSON pipes without opening TCP sockets or WebSocket ports.
"""

from __future__ import annotations

import asyncio
from contextvars import ContextVar
import importlib
import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from backend.logging_config import get_logger
from backend.message_protocol import (
    WebSocketPayloadError,
    normalize_ws_message,
    system_message,
    validate_client_message,
)
from backend.websocket.context import (
    WebSocketSessionState,
    bind_response_request_id,
    reset_response_request_id,
)
from backend.websocket.dispatcher import WebSocketDispatcher
from backend.websocket.gateway import ConnectionManager
from backend.websocket.handlers.common import (
    WebSocketResponder,
    WebSocketRuntimeCallbacks,
)
from workers.common.stdio_rpc import TaskCancelledError, WorkerContext, WorkerRpcServer


WORKER_ROLE_DOMAINS: dict[str, tuple[str, ...]] = {
    "ai": ("chat", "coding", "project", "system"),
    "study": ("study", "lecture"),
    "knowledge": ("knowledge",),
    "mission": ("mission", "sentinel", "permissions"),
    "voice": ("voice", "lecture"),
}

_active_ctx_var: ContextVar[WorkerContext | None] = ContextVar(
    "jarvis_worker_active_ctx",
    default=None,
)


def current_worker_context() -> WorkerContext | None:
    """Return the active `WorkerContext` for cooperative cancellation and Reverse RPC."""
    return _active_ctx_var.get()


class _WorkerEventStreamClient:
    """Virtual WebSocket client forwarding handler emissions directly over NDJSON `stream.chunk`."""

    def __init__(
        self,
        ctx: WorkerContext,
        request_id: str,
        sink: list[dict[str, Any]],
        seq_counter: list[int],
    ) -> None:
        self._ctx = ctx
        self._request_id = request_id
        self._sink = sink
        self._seq_counter = seq_counter

    async def send(self, payload: str | dict[str, Any]) -> None:
        await self.emit_raw(payload)

    async def emit_raw(self, payload: str | dict[str, Any]) -> None:
        if isinstance(payload, str):
            try:
                parsed: Any = json.loads(payload)
            except json.JSONDecodeError:
                parsed = {"type": "system", "content": payload}
        else:
            parsed = dict(payload)

        if not isinstance(parsed, dict):
            return

        event = normalize_ws_message(parsed) if isinstance(parsed.get("type"), str) else dict(parsed)
        if self._request_id and not event.get("request_id"):
            event["request_id"] = self._request_id

        self._sink.append(event)
        seq = self._seq_counter[0]
        self._seq_counter[0] += 1
        encoded = json.dumps(
            {"event": event},
            ensure_ascii=False,
            separators=(",", ":"),
        )
        self._ctx.stream_chunk(seq, encoded)


class DomainWorkerRuntime:
    """Lazy-initialized domain execution runtime for a specialized Python worker role."""

    def __init__(
        self,
        worker_type: str,
        *,
        project_root: str | Path | None = None,
        dispatcher: WebSocketDispatcher | None = None,
        connections: ConnectionManager | None = None,
    ) -> None:
        if worker_type not in WORKER_ROLE_DOMAINS:
            raise ValueError(f"Unsupported domain worker role: {worker_type}")
        self.worker_type = worker_type
        self.project_root = str(
            Path(project_root).resolve()
            if project_root is not None
            else Path(__file__).resolve().parents[2]
        )
        self.logger = get_logger(f"worker.{worker_type}")
        self.session_state = WebSocketSessionState()
        self.connections = connections or ConnectionManager()
        self._dispatcher = dispatcher
        self._services: Any = None
        self._conversation_history: list[dict[str, Any]] = []
        self._pending_background_tasks: set[asyncio.Task[Any]] = set()
        self._broadcast_lock = asyncio.Lock()
        self._initialized = dispatcher is not None

    @property
    def domains(self) -> tuple[str, ...]:
        return WORKER_ROLE_DOMAINS[self.worker_type]

    def register_on_server(self, server: WorkerRpcServer) -> None:
        """Bind standard domain RPC methods onto the `WorkerRpcServer`."""
        server.register("domain.dispatch", self.rpc_domain_dispatch)
        server.register("domain.capabilities", self.rpc_capabilities)
        server.register("domain.initial_sync", self.rpc_initial_sync)
        if self.worker_type == "ai":
            server.register("model.execute", self.rpc_model_execute)
        elif self.worker_type == "study":
            server.register("study.refresh_catalog", self.rpc_study_refresh_catalog)
        elif self.worker_type == "voice":
            server.register("voice.status", self.rpc_voice_status)

    def _build_callbacks(self) -> WebSocketRuntimeCallbacks:
        from backend.server_helpers import (
            build_template_payload,
            normalize_template_name,
            parse_file_context,
            read_persistent_plan_state,
        )

        async def _broadcast_state(value: str) -> None:
            await self.connections.broadcast({"type": "state", "status": value})

        def _run_in_main_loop(coro: Any) -> Any:
            try:
                loop = asyncio.get_running_loop()
                task = loop.create_task(coro)
                self._pending_background_tasks.add(task)
                task.add_done_callback(self._pending_background_tasks.discard)
                return task
            except RuntimeError:
                return asyncio.run(coro)

        async def _run_orchestration_task(
            prompt: str,
            session_id: int,
            project_id: str | None = None,
            correlation_id: str | None = None,
            study_context: dict | None = None,
            chat_session_id: str | None = None,
        ) -> None:
            from backend.services.orchestration_runtime import (
                OrchestrationCallbacks,
                OrchestrationService,
            )
            from backend.services.model_service import ModelExecutionService

            svc = self._ensure_ai_services()
            orch = OrchestrationService(
                services=svc,
                models=ModelExecutionService(svc.model_harness),
                connections=self.connections,
                callbacks=OrchestrationCallbacks(
                    broadcast_state=_broadcast_state,
                    open_local_application=_open_local_app,
                    run_in_main_loop=_run_in_main_loop,
                    on_agent_message=lambda s, r, c: _run_in_main_loop(
                        self.connections.broadcast(
                            {"type": "chat", "sender": s.upper(), "role": r, "content": c}
                        )
                    ),
                    on_file_update=lambda f, c: _run_in_main_loop(
                        self.connections.broadcast(
                            {"type": "file_update", "filename": f, "content": c}
                        )
                    ),
                    on_kanban_update=lambda cid, st: _run_in_main_loop(
                        self.connections.broadcast(
                            {"type": "kanban_update", "card_id": cid, "status": st}
                        )
                    ),
                    build_template_payload=lambda name: build_template_payload(
                        name, agents_module=getattr(svc, "agents", None)
                    ),
                ),
                conversation_history=self._conversation_history,
                logger=self.logger,
            )
            await orch.run_task(
                prompt,
                session_id,
                project_id,
                correlation_id=correlation_id,
                study_context=study_context,
                chat_session_id=chat_session_id,
            )

        async def _handle_slash_command(
            command_str: str,
            websocket: Any,
            session_id: int,
            chat_session_id: str | None = None,
        ) -> None:
            from backend.services.chat_command_service import (
                ChatCommandCallbacks,
                ChatCommandService,
            )
            from backend.services.model_service import ModelExecutionService

            svc = self._ensure_ai_services()
            cmd = ChatCommandService(
                services=svc,
                models=ModelExecutionService(svc.model_harness),
                connections=self.connections,
                callbacks=ChatCommandCallbacks(
                    broadcast_state=_broadcast_state,
                    on_agent_message=lambda s, r, c: _run_in_main_loop(
                        self.connections.broadcast(
                            {"type": "chat", "sender": s.upper(), "role": r, "content": c}
                        )
                    ),
                    on_file_update=lambda f, c: _run_in_main_loop(
                        self.connections.broadcast(
                            {"type": "file_update", "filename": f, "content": c}
                        )
                    ),
                ),
                logger=self.logger,
            )
            await cmd.handle(
                command_str,
                websocket,
                session_id,
                chat_session_id=chat_session_id,
            )

        def _open_local_app(app_request: Any) -> Any:
            from backend.services.local_app_service import (
                open_local_application_helper,
            )

            return open_local_application_helper(app_request, logger=self.logger)

        def _get_voice_service() -> Any:
            if getattr(self, "_voice_runtime", None) is None:
                try:
                    import voice

                    self._voice_runtime = voice.VoiceService()
                except Exception:
                    self._voice_runtime = None
            return self._voice_runtime

        sandbox_dir = os.path.join(self.project_root, "sandbox_workspace")
        return WebSocketRuntimeCallbacks(
            handle_slash_command=_handle_slash_command,
            parse_file_context=lambda prompt: parse_file_context(
                prompt,
                project_root=self.project_root,
                sandbox_root=sandbox_dir,
                logger=self.logger,
            ),
            run_orchestration_task=_run_orchestration_task,
            broadcast_state=_broadcast_state,
            run_in_main_loop=_run_in_main_loop,
            normalize_template_name=normalize_template_name,
            build_template_payload=lambda name: build_template_payload(
                name,
                agents_module=getattr(self._services, "agents", None),
            ),
            read_persistent_plan_state=lambda: read_persistent_plan_state(
                os.path.join(self.project_root, ".jarvis_plan.json"),
                logger=self.logger,
            ),
            get_voice_service=_get_voice_service,
            conversation_history=self._conversation_history,
        )

    def _safe_import(self, module_name: str) -> Any:
        try:
            return importlib.import_module(module_name)
        except Exception as exc:
            self.logger.warning("worker module %s unavailable: %s", module_name, exc)
            return None

    def _ensure_ai_services(self) -> Any:
        if self._services is not None:
            return self._services

        from backend.model_harness import get_model_harness
        from intelligence.coding_session import CodingSessionService
        from intelligence.project_context import ProjectContextService

        database_mod = self._safe_import("database")
        agents_mod = self._safe_import("agents")
        sandbox_mod = self._safe_import("sandbox")
        project_ctx = ProjectContextService()
        coding_sessions = CodingSessionService(project_ctx)

        self._services = SimpleNamespace(
            project_root=self.project_root,
            database=database_mod or SimpleNamespace(
                create_session=lambda prompt: SimpleNamespace(id=1, name=prompt),
                get_compounding_rules=lambda: [],
                get_architecture_memory=lambda: [],
                get_engineering_decisions=lambda: [],
            ),
            agents=agents_mod or SimpleNamespace(active_template_name="builder_swarm"),
            sandbox=sandbox_mod,
            model_harness=get_model_harness(),
            project_context=project_ctx,
            coding_sessions=coding_sessions,
            mission_planner=None,
            mission_executor=None,
            mission_autonomy=None,
            sentinel_watchdog=None,
            study_service=None,
        )
        return self._services

    def _ensure_initialized(self) -> WebSocketDispatcher:
        if self._initialized and self._dispatcher is not None:
            return self._dispatcher

        callbacks = self._build_callbacks()

        if self.worker_type == "study":
            from backend.websocket.handlers.lectures import LectureWebSocketHandler
            from backend.websocket.handlers.study import StudyWebSocketHandler
            from services.study_service import StudyService

            study_service = StudyService(workspace_root=self.project_root)
            try:
                from services.study_integration import StudyOrchestrationCoordinator

                setattr(
                    study_service,
                    "_study_coordinator",
                    StudyOrchestrationCoordinator(study_service),
                )
            except Exception:
                pass
            services = SimpleNamespace(
                project_root=self.project_root,
                study_service=study_service,
            )
            dispatcher = WebSocketDispatcher(
                services=services,
                result_sender=self.connections.send,
                result_broadcaster=self.connections.broadcast,
            )
            dispatcher.register_many(
                StudyWebSocketHandler(
                    connections=self.connections,
                    study_service=study_service,
                    logger=self.logger,
                ).routes(),
                domain="study",
            )
            dispatcher.register_many(
                LectureWebSocketHandler(
                    connections=self.connections,
                    logger=self.logger,
                ).routes(),
                domain="lecture",
            )
            self._services = services
            self._dispatcher = dispatcher

        elif self.worker_type == "voice":
            from backend.websocket.handlers.lectures import LectureWebSocketHandler
            from backend.websocket.handlers.voice import VoiceWebSocketHandler

            services = SimpleNamespace(project_root=self.project_root)
            dispatcher = WebSocketDispatcher(
                services=services,
                result_sender=self.connections.send,
                result_broadcaster=self.connections.broadcast,
            )
            dispatcher.register_many(
                VoiceWebSocketHandler(self.connections, callbacks).routes(),
                domain="voice",
            )
            dispatcher.register_many(
                LectureWebSocketHandler(
                    connections=self.connections,
                    logger=self.logger,
                ).routes(),
                domain="lecture",
            )
            self._services = services
            self._dispatcher = dispatcher

        elif self.worker_type == "knowledge":
            from backend.websocket.handlers.knowledge import KnowledgeWebSocketHandler

            database_mod = self._safe_import("database") or SimpleNamespace(
                get_compounding_rules=lambda: [],
                delete_compounding_rule=lambda _k: None,
                delete_architecture_memory=lambda _m: None,
                delete_engineering_decision=lambda _i: None,
            )
            agents_mod = self._safe_import("agents") or SimpleNamespace()
            services = SimpleNamespace(
                project_root=self.project_root,
                database=database_mod,
                agents=agents_mod,
            )
            dispatcher = WebSocketDispatcher(
                services=services,
                result_sender=self.connections.send,
                result_broadcaster=self.connections.broadcast,
            )
            dispatcher.register_many(
                KnowledgeWebSocketHandler(
                    agents_mod,
                    database_mod,
                    self.connections,
                ).routes(),
                domain="knowledge",
            )
            self._services = services
            self._dispatcher = dispatcher

        elif self.worker_type == "mission":
            from agents.mission_autonomy import MissionAutonomyController
            from agents.mission_executor import MissionExecutorService
            from agents.planner_engine import PersistentPlanner
            from backend.websocket.handlers.missions import MissionWebSocketHandler
            from backend.websocket.handlers.permissions import (
                PermissionGatewayWebSocketHandler,
            )
            from backend.websocket.handlers.sentinel import SentinelWebSocketHandler
            from intelligence.coding_session import CodingSessionService
            from intelligence.project_context import ProjectContextService
            from security.permission_gateway.gateway import (
                get_permission_gateway_service,
            )
            from security.sentinel.watchdog import SentinelWatchdogService

            project_ctx = ProjectContextService()
            coding_sessions = CodingSessionService(project_ctx)
            mission_planner = PersistentPlanner(self.project_root)
            mission_executor = MissionExecutorService(
                self.project_root,
                mission_state=mission_planner.mission_state,
                coding_service=coding_sessions,
            )
            mission_autonomy = MissionAutonomyController(
                self.project_root,
                mission_state=mission_planner.mission_state,
                executor_service=mission_executor,
            )
            services = SimpleNamespace(
                project_root=self.project_root,
                project_context=project_ctx,
                coding_sessions=coding_sessions,
                mission_planner=mission_planner,
                mission_executor=mission_executor,
                mission_autonomy=mission_autonomy,
            )
            responder = WebSocketResponder(
                project_ctx,
                coding_sessions,
                mission_planner,
                self.connections,
            )
            dispatcher = WebSocketDispatcher(
                services=services,
                result_sender=self.connections.send,
                result_broadcaster=self.connections.broadcast,
            )
            dispatcher.register_many(
                MissionWebSocketHandler(
                    mission_planner,
                    mission_executor,
                    mission_autonomy,
                    responder,
                ).routes(),
                domain="mission",
            )
            dispatcher.register_many(
                SentinelWebSocketHandler(
                    watchdog=SentinelWatchdogService(),
                    connections=self.connections,
                ).routes(),
                domain="sentinel",
            )
            dispatcher.register_many(
                PermissionGatewayWebSocketHandler(
                    gateway=get_permission_gateway_service(),
                    connections=self.connections,
                ).routes(),
                domain="permissions",
            )
            self._services = services
            self._dispatcher = dispatcher

        else:
            # "ai" role: chat + coding + project + system
            from backend.websocket.handlers.chat import ChatWebSocketHandler
            from backend.websocket.handlers.coding import CodingSessionWebSocketHandler
            from backend.websocket.handlers.projects import ProjectWebSocketHandler
            from backend.websocket.handlers.system import SystemWebSocketHandler

            services = self._ensure_ai_services()
            responder = WebSocketResponder(
                services.project_context,
                services.coding_sessions,
                services.mission_planner,
                self.connections,
            )
            dispatcher = WebSocketDispatcher(
                services=services,
                result_sender=self.connections.send,
                result_broadcaster=self.connections.broadcast,
            )
            dispatcher.register_many(
                ChatWebSocketHandler(
                    services.agents,
                    services.database,
                    self.connections,
                    callbacks,
                    self.logger,
                ).routes(),
                domain="chat",
            )
            dispatcher.register_many(
                CodingSessionWebSocketHandler(
                    services.coding_sessions,
                    responder,
                    model_harness=services.model_harness,
                ).routes(),
                domain="coding",
            )
            dispatcher.register_many(
                ProjectWebSocketHandler(
                    services.project_context,
                    services.sandbox,
                    responder,
                    callbacks,
                    self.logger,
                ).routes(),
                domain="project",
            )
            dispatcher.register_many(
                SystemWebSocketHandler(
                    services.project_context,
                    self.connections,
                    callbacks,
                ).routes(),
                domain="system",
            )
            self._dispatcher = dispatcher

        self._initialized = True
        assert self._dispatcher is not None
        return self._dispatcher

    async def _await_pending_tasks_with_cancellation(
        self,
        ctx: WorkerContext,
        tasks_before: set[asyncio.Task[Any]],
    ) -> None:
        spawned = [
            t for t in self._pending_background_tasks if t not in tasks_before and not t.done()
        ]
        if not spawned:
            return
        cancel_waiter = asyncio.create_task(ctx.cancel_event.wait())
        try:
            gather_fut = asyncio.gather(*spawned, return_exceptions=True)
            done, _ = await asyncio.wait(
                {gather_fut, cancel_waiter},
                return_when=asyncio.FIRST_COMPLETED,
            )
            if cancel_waiter in done:
                for t in spawned:
                    t.cancel()
                await asyncio.gather(*spawned, return_exceptions=True)
                raise TaskCancelledError("user_cancelled")
        finally:
            cancel_waiter.cancel()

    async def rpc_capabilities(
        self,
        _ctx: WorkerContext,
        _params: dict[str, Any],
    ) -> dict[str, Any]:
        dispatcher = self._ensure_initialized()
        return {
            "worker_type": self.worker_type,
            "domains": list(self.domains),
            "message_types": sorted(dispatcher.message_types),
        }

    async def rpc_domain_dispatch(
        self,
        ctx: WorkerContext,
        params: dict[str, Any],
    ) -> dict[str, Any]:
        """Dispatch a client message dictionary through this worker's domain handlers."""
        ctx.raise_if_cancelled()
        raw_msg = params.get("message") if isinstance(params.get("message"), dict) else params
        message = dict(raw_msg or {})
        request_id = str(message.get("request_id") or ctx.request_id)
        message["request_id"] = request_id

        emitted_events: list[dict[str, Any]] = []
        seq_counter = [0]
        emitter = _WorkerEventStreamClient(ctx, request_id, emitted_events, seq_counter)

        msg_type = message.get("type")
        if bool(params.get("validate", True)):
            validation_err: str | None = None
            try:
                message = validate_client_message(message)
                if request_id and not message.get("request_id"):
                    message["request_id"] = request_id
                msg_type = message.get("type")
            except WebSocketPayloadError as exc:
                validation_err = str(exc)
            if validation_err:
                if isinstance(msg_type, str) and msg_type.startswith("study_"):
                    err_event = {
                        "type": "study_error",
                        "error": validation_err,
                        "message": validation_err,
                        "request_id": request_id,
                    }
                else:
                    err_event = system_message(
                        f"Mensagem IPC invalida: {validation_err}",
                        request_id=request_id,
                    )
                await emitter.emit_raw(err_event)
                return {
                    "status": "validation_error",
                    "worker_type": self.worker_type,
                    "request_id": request_id,
                    "events_emitted": len(emitted_events),
                    "events": emitted_events,
                }

        dispatcher = self._ensure_initialized()
        if isinstance(msg_type, str) and msg_type not in dispatcher.message_types:
            raise KeyError(
                f"Worker role '{self.worker_type}' does not own message type '{msg_type}'"
            )

        async def _broadcast_hook(msg: dict[str, Any]) -> None:
            await emitter.emit_raw(msg)

        token_ctx = _active_ctx_var.set(ctx)
        token_req = bind_response_request_id(request_id)
        self.connections.add_broadcast_hook(_broadcast_hook)
        legacy_server_conn = getattr(sys.modules.get("server"), "connection_manager", None)
        if legacy_server_conn is not None and legacy_server_conn is not self.connections:
            legacy_server_conn.add_broadcast_hook(_broadcast_hook)
        tasks_before = set(self._pending_background_tasks)
        try:
            ctx.raise_if_cancelled()
            await dispatcher.dispatch(emitter, message, self.session_state)
            await self._await_pending_tasks_with_cancellation(ctx, tasks_before)
        finally:
            if legacy_server_conn is not None and legacy_server_conn is not self.connections:
                legacy_server_conn.remove_broadcast_hook(_broadcast_hook)
            self.connections.remove_broadcast_hook(_broadcast_hook)
            reset_response_request_id(token_req)
            _active_ctx_var.reset(token_ctx)

        return {
            "status": "ok",
            "worker_type": self.worker_type,
            "request_id": request_id,
            "events_emitted": len(emitted_events),
            "events": emitted_events,
        }

    async def rpc_initial_sync(
        self,
        ctx: WorkerContext,
        params: dict[str, Any],
    ) -> dict[str, Any]:
        """Emit role-scoped initial hydration snapshots over `stream.chunk`."""
        ctx.raise_if_cancelled()
        dispatcher = self._ensure_initialized()
        request_id = str(params.get("request_id") or ctx.request_id)
        emitted_events: list[dict[str, Any]] = []
        seq_counter = [0]
        emitter = _WorkerEventStreamClient(ctx, request_id, emitted_events, seq_counter)

        sync_messages: list[dict[str, Any]] = []
        if self.worker_type == "ai":
            sync_messages.append({"type": "list_projects"})
        elif self.worker_type == "study":
            sync_messages.extend(
                [{"type": "study_list_documents"}, {"type": "study_list_collections"}]
            )
        elif self.worker_type == "knowledge":
            sync_messages.extend([{"type": "get_notes"}, {"type": "get_rules"}])
        elif self.worker_type == "mission":
            sync_messages.append(
                {"type": "mission_list", "project_id": params.get("project_id") or "ALL"}
            )

        token_req = bind_response_request_id(request_id)
        try:
            for msg in sync_messages:
                if msg["type"] in dispatcher.message_types:
                    await dispatcher.dispatch(
                        emitter,
                        {**msg, "request_id": request_id},
                        self.session_state,
                    )
        finally:
            reset_response_request_id(token_req)

        return {
            "status": "ok",
            "worker_type": self.worker_type,
            "request_id": request_id,
            "events_emitted": len(emitted_events),
            "events": emitted_events,
        }

    async def rpc_model_execute(
        self,
        ctx: WorkerContext,
        params: dict[str, Any],
    ) -> dict[str, Any]:
        """Direct Ollama / ModelHarness execution endpoint inside the AI worker."""
        ctx.raise_if_cancelled()
        from backend.model_harness import OutputFormat
        from backend.services.model_service import ModelExecutionService

        services = self._ensure_ai_services()
        model_service = ModelExecutionService(services.model_harness)
        fmt_raw = str(params.get("output_format") or "text").lower()
        fmt = OutputFormat.JSON if fmt_raw == "json" else OutputFormat.TEXT
        response = await model_service.execute(
            provider=str(params.get("provider") or "ollama"),
            model=str(params.get("model") or "qwen2.5-coder:7b"),
            operation=str(params.get("operation") or "worker_chat"),
            system_prompt=str(params.get("system_prompt") or ""),
            user_prompt=str(params.get("user_prompt") or ""),
            conversation_messages=params.get("conversation_messages"),
            output_format=fmt,
            temperature=float(params.get("temperature") or 0.0),
            max_output_tokens=int(params.get("max_output_tokens") or 512),
            timeout_seconds=float(params.get("timeout_seconds") or 30.0),
        )
        return {
            "status": "ok",
            "provider": getattr(response, "provider", params.get("provider", "ollama")),
            "model": getattr(response, "model", params.get("model", "")),
            "raw_text": getattr(response, "raw_text", ""),
            "parsed_json": getattr(response, "parsed_json", None),
        }

    async def rpc_study_refresh_catalog(
        self,
        ctx: WorkerContext,
        _params: dict[str, Any],
    ) -> dict[str, Any]:
        ctx.raise_if_cancelled()
        self._ensure_initialized()
        svc = getattr(self._services, "study_service", None)
        docs = svc.list_documents() if svc is not None else []
        collections = svc.list_collections() if svc is not None else []
        return {
            "status": "ok",
            "documents_count": len(docs),
            "collections_count": len(collections),
        }

    async def rpc_voice_status(
        self,
        ctx: WorkerContext,
        _params: dict[str, Any],
    ) -> dict[str, Any]:
        ctx.raise_if_cancelled()
        return {
            "status": "ok",
            "worker_type": "voice",
            "active": getattr(getattr(self, "_voice_runtime", None), "is_running", False),
        }
