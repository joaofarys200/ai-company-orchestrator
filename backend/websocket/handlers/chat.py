from __future__ import annotations

import asyncio
import inspect
import uuid
from typing import Any

from backend.logging_config import log_event
from backend.services.voice_service import normalize_voice_prompt
from backend.websocket.context import WebSocketSessionState
from backend.websocket.contracts import MessageHandler
from backend.websocket.gateway import ConnectionManager
from backend.websocket.handlers import bind_handler_methods
from backend.websocket.handlers.common import WebSocketRuntimeCallbacks
from services.study_integration.contracts import normalize_chat_session_id


CHAT_HANDLERS = {
    "directive": "directive",
    "select_template": "select_template",
}


class ChatWebSocketHandler:
    def __init__(
        self,
        agents: Any,
        database: Any,
        connections: ConnectionManager,
        callbacks: WebSocketRuntimeCallbacks,
        logger: Any,
    ) -> None:
        self.agents = agents
        self.database = database
        self.connections = connections
        self.callbacks = callbacks
        self.logger = logger

    def routes(self) -> dict[str, MessageHandler]:
        return bind_handler_methods(self, CHAT_HANDLERS)

    @staticmethod
    def _supports_kwarg(fn: Any, kwarg: str) -> bool:
        try:
            sig = inspect.signature(fn)
            return kwarg in sig.parameters or any(
                p.kind == inspect.Parameter.VAR_KEYWORD
                for p in sig.parameters.values()
            )
        except (TypeError, ValueError):
            return False

    async def directive(
        self,
        websocket: Any,
        message: dict,
        _session: WebSocketSessionState,
    ) -> None:
        prompt = str(message.get("text") or "").strip()
        if not prompt:
            return
        raw_study_ctx = message.get("study_context")
        study_context = dict(raw_study_ctx) if isinstance(raw_study_ctx, dict) else None
        explicit_chat_sid = normalize_chat_session_id(
            (study_context.get("chat_session_id") if study_context else None)
            or message.get("chat_session_id")
        )
        if explicit_chat_sid:
            study_context = {**(study_context or {}), "chat_session_id": explicit_chat_sid}
        elif study_context and "chat_session_id" in study_context:
            study_context.pop("chat_session_id", None)

        prompt = normalize_voice_prompt(prompt)
        if prompt.startswith("/"):
            if explicit_chat_sid and self._supports_kwarg(
                self.callbacks.handle_slash_command,
                "chat_session_id",
            ):
                await self.callbacks.handle_slash_command(
                    prompt,
                    websocket,
                    1,
                    chat_session_id=explicit_chat_sid,
                )
            else:
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
                "--- Conteúdo do ficheiro @"
            )
            await self.connections.send(
                websocket,
                {
                    "type": "system",
                    "content": (
                        f"📎 {mentions_count} ficheiro(s) "
                        "injetados como contexto via @mention."
                    ),
                },
            )

        attachments = message.get("attachments") or []
        if isinstance(attachments, list) and attachments:
            extra_blocks = []
            for att in attachments:
                if not isinstance(att, dict):
                    continue
                name = str(att.get("name") or "anexo").strip()
                att_type = str(att.get("type") or "document").lower()
                size = att.get("size") or 0
                text_content = att.get("textContent")
                if text_content and isinstance(text_content, str):
                    safe_content = text_content[:15000]
                    if len(text_content) > 15000:
                        safe_content += "\n... [truncado para 15000 caracteres para preservar orçamento de contexto] ..."
                    extra_blocks.append(
                        f"\n--- Conteúdo do Anexo [{att_type.upper()}: {name} ({size} bytes)] ---\n{safe_content}\n--- Fim do Anexo {name} ---"
                    )
                elif att_type == "image":
                    extra_blocks.append(
                        f"\n--- Anexo [IMAGEM MULTIMODAL: {name} ({size} bytes)] ---\n[Imagem fornecida pelo utilizador como contexto visual da sessão]"
                    )
            if extra_blocks:
                prompt_with_context = prompt_with_context + "\n" + "\n".join(extra_blocks)
                await self.connections.send(
                    websocket,
                    {
                        "type": "system",
                        "content": f"📎 {len(extra_blocks)} anexo(s) integrados com sucesso no contexto do Jarvis.",
                    },
                )

        history = self.callbacks.conversation_history
        history.append(
            {"role": "user", "content": prompt_with_context}
        )
        if len(history) > 100:
            history.pop(0)
        correlation_id = str(message.get("correlation_id") or "").strip() or uuid.uuid4().hex[:12]
        log_event(
            self.logger,
            "websocket.directive.received",
            prompt_length=len(prompt),
            correlation_id=correlation_id,
        )
        database_session = self.database.create_session(
            prompt
        )
        await self.callbacks.broadcast_state("processing")
        project_id = str(
            message.get("project_id")
            or _session.selected_project_id
            or ""
        ).strip() or None
        task_kwargs: dict[str, Any] = {
            "project_id": project_id,
            "correlation_id": correlation_id,
        }
        if study_context is not None:
            task_kwargs["study_context"] = study_context
        asyncio.create_task(
            self.callbacks.run_orchestration_task(
                prompt_with_context,
                database_session.id,
                **task_kwargs,
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
        self.agents.active_template_name = template_name
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
