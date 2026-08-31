from __future__ import annotations

import asyncio
from typing import Any

from backend.logging_config import log_event
from backend.services.voice_service import normalize_voice_prompt
from backend.websocket.context import WebSocketSessionState
from backend.websocket.contracts import MessageHandler
from backend.websocket.gateway import ConnectionManager
from backend.websocket.handlers import bind_handler_methods
from backend.websocket.handlers.common import WebSocketRuntimeCallbacks


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
                "--- Conteúdo do ficheiro @"
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
        database_session = self.database.create_session(
            prompt
        )
        await self.callbacks.broadcast_state("processing")
        await self.connections.broadcast(
            {
                "type": "system",
                "content": f"Orquestração iniciada: {prompt}",
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
