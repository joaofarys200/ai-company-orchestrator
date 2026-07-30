from __future__ import annotations

import asyncio
import os
import time
from dataclasses import dataclass
from typing import Any, Callable

from backend.application_services import ApplicationServices
from backend.logging_config import log_event
from backend.server_helpers import env_bool, env_int
from backend.services.local_app_service import (
    find_local_app_request,
    normalize_voice_command_text,
)
from backend.services.voice_service import normalize_voice_prompt
from backend.websocket.gateway import ConnectionManager


VOICE_CONFIRMATION_WORDS = {
    "confirma",
    "confirmo",
    "confirmar",
    "executa",
    "executar",
    "avanca",
    "arranca",
    "podes avancar",
    "sim confirma",
    "sim executa",
}
VOICE_CANCEL_WORDS = {
    "cancela",
    "cancelar",
    "anula",
    "para",
    "esquece",
    "ignora",
    "nao executes",
    "nao executar",
}
VOICE_READ_ONLY_REQUEST_TERMS = (
    "pesquisa",
    "pesquisar",
    "procura",
    "procurar",
    "vagas",
    "emprego",
    "oportunidades",
    "noticias",
    "fontes",
    "ver o meu ambiente",
    "ve o meu ambiente",
    "mostra o meu ecra",
    "ve o que esta aberto",
    "ver o que esta aberto",
    "janelas abertas",
    "captura o ecra",
    "tira uma captura",
    "screenshot",
)


@dataclass(slots=True)
class VoiceRuntimeState:
    service: Any = None
    pending_directive: dict | None = None


@dataclass(slots=True)
class VoiceRuntimeCallbacks:
    run_in_main_loop: Callable[..., Any]
    broadcast_state: Callable[..., Any]
    run_orchestration_task: Callable[..., Any]
    open_local_application: Callable[..., Any]


class VoiceDirectiveService:
    def __init__(
        self,
        *,
        services: ApplicationServices,
        connections: ConnectionManager,
        callbacks: VoiceRuntimeCallbacks,
        conversation_history: list[dict],
        logger: Any,
    ) -> None:
        self.services = services
        self.connections = connections
        self.callbacks = callbacks
        self.conversation_history = conversation_history
        self.logger = logger
        self.state = VoiceRuntimeState()

    @property
    def voice_service(self) -> Any:
        return self.state.service

    @property
    def pending_directive(self) -> dict | None:
        return self.state.pending_directive

    def confirmation_enabled(self) -> bool:
        return env_bool("VOICE_CONFIRMATION_MODE", True)

    def is_confirmation(self, text: str) -> bool:
        return (
            normalize_voice_command_text(text)
            in VOICE_CONFIRMATION_WORDS
        )

    def is_cancel(self, text: str) -> bool:
        return (
            normalize_voice_command_text(text)
            in VOICE_CANCEL_WORDS
        )

    def is_read_only_request(self, text: str) -> bool:
        if not env_bool("VOICE_AUTO_READONLY", True):
            return False
        normalized = normalize_voice_command_text(text)
        return any(
            term in normalized
            for term in VOICE_READ_ONLY_REQUEST_TERMS
        )

    def initialize(self) -> Any:
        mode = os.getenv("VOICE_MODE", "none").lower()
        if mode == "none":
            log_event(
                self.logger,
                "voice.disabled",
                mode=mode,
            )
            self.state.service = None
            return None
        if mode == "gemini_live":
            from gemini_live import GeminiLiveService

            def on_state_change(state: str) -> None:
                self._schedule(
                    self.connections.broadcast(
                        {
                            "type": "voice_status",
                            "status": state,
                        }
                    )
                )

            def on_message(text: str) -> None:
                self._schedule(
                    self.connections.broadcast(
                        {
                            "type": "chat",
                            "sender": "OPENCLAW",
                            "role": "Orquestrador",
                            "content": text,
                        }
                    )
                )
                self._append_history("assistant", text)

            def on_voice_directive(prompt: str) -> None:
                normalized = normalize_voice_prompt(prompt)
                self._schedule(
                    self.handle_candidate(
                        normalized,
                        source="gemini_live",
                    )
                )

            def on_voice_confirm(confirmation: str) -> None:
                self._schedule(
                    self.confirm(
                        confirmation,
                        source="gemini_live",
                    )
                )

            def on_voice_cancel(cancel: str) -> None:
                self._schedule(
                    self.cancel(
                        cancel,
                        source="gemini_live",
                    )
                )

            voice_name = os.getenv(
                "GEMINI_LIVE_VOICE",
                "Puck",
            )
            self.state.service = GeminiLiveService(
                api_key=os.getenv("GEMINI_API_KEY", ""),
                voice_name=voice_name,
                on_state_change=on_state_change,
                on_message=on_message,
                on_voice_directive=on_voice_directive,
                on_voice_confirm=on_voice_confirm,
                on_voice_cancel=on_voice_cancel,
            )
            log_event(
                self.logger,
                "voice.gemini_live.initialized",
                voice=voice_name,
            )
            return self.state.service

        from voice_service import VoiceService

        def on_speech_start() -> None:
            self._schedule(
                self.connections.broadcast(
                    {
                        "type": "voice_status",
                        "status": "listening",
                    }
                )
            )

        def on_speech_end() -> None:
            self._schedule(
                self.connections.broadcast(
                    {
                        "type": "voice_status",
                        "status": "idle",
                    }
                )
            )

        def on_transcribing() -> None:
            self._schedule(
                self.connections.broadcast(
                    {
                        "type": "voice_status",
                        "status": "transcribing",
                    }
                )
            )

        def on_transcription(text: str) -> None:
            normalized = normalize_voice_prompt(text)
            self._schedule(
                self.connections.broadcast(
                    {
                        "type": "voice_status",
                        "status": "transcribed",
                        "text": normalized,
                    }
                )
            )
            self._schedule(
                self.handle_candidate(
                    normalized,
                    source="local",
                )
            )

        model_name = os.getenv("VOICE_MODEL", "tiny")
        self.state.service = VoiceService(
            on_speech_start=on_speech_start,
            on_speech_end=on_speech_end,
            on_transcribing=on_transcribing,
            on_transcription=on_transcription,
            model_name=model_name,
        )
        log_event(
            self.logger,
            "voice.local.initialized",
            model=model_name,
        )
        return self.state.service

    async def start_orchestration(self, prompt: str) -> None:
        prompt = prompt.strip()
        if not prompt:
            return
        self._append_history("user", prompt)
        log_event(
            self.logger,
            "voice.directive.received",
            prompt_length=len(prompt),
        )
        session = self.services.database.create_session(prompt)
        await self.callbacks.broadcast_state("processing")
        await self.connections.broadcast(
            {
                "type": "system",
                "content": (
                    "OrquestraÃ§Ã£o iniciada via Voz: "
                    f"{prompt}"
                ),
            }
        )
        asyncio.create_task(
            self.callbacks.run_orchestration_task(
                prompt,
                session.id,
            )
        )

    def pending_expired(self) -> bool:
        pending = self.state.pending_directive
        if not pending:
            return False
        ttl = env_int(
            "VOICE_CONFIRMATION_TTL_SECONDS",
            600,
            30,
            3600,
        )
        return (
            time.time() - pending.get("created_at", 0)
        ) > ttl

    async def clear_expired(self) -> None:
        if not self.pending_expired():
            return
        pending = self.state.pending_directive or {}
        prompt = pending.get("prompt", "")
        self.state.pending_directive = None
        await self.connections.broadcast(
            {"type": "voice_status", "status": "idle"}
        )
        await self.connections.broadcast(
            {
                "type": "system",
                "content": (
                    "Diretiva de voz expirada e descartada: "
                    f"{prompt}"
                ),
            }
        )

    async def handle_candidate(
        self,
        prompt: str,
        source: str = "voice",
    ) -> str:
        prompt = (prompt or "").strip()
        if not prompt:
            return "Sem texto de voz para processar."
        await self.clear_expired()
        if not self.confirmation_enabled():
            await self.start_orchestration(prompt)
            return "Orquestracao iniciada sem confirmacao."
        if self.is_confirmation(prompt):
            return await self.confirm(prompt, source=source)
        if self.is_cancel(prompt):
            return await self.cancel(prompt, source=source)
        if self.is_read_only_request(prompt):
            await self.start_orchestration(prompt)
            return "Consulta read-only iniciada."
        self.state.pending_directive = {
            "prompt": prompt,
            "source": source,
            "created_at": time.time(),
        }
        await self.connections.broadcast(
            {
                "type": "voice_status",
                "status": "pending_confirmation",
                "text": prompt,
            }
        )
        await self.connections.broadcast(
            {
                "type": "system",
                "content": (
                    "Diretiva de voz preparada. Diz 'confirma' "
                    "ou 'executa' para iniciar, ou 'cancela' "
                    "para descartar."
                ),
            }
        )
        await self.connections.broadcast(
            {
                "type": "chat",
                "sender": "OPENCLAW",
                "role": "Voz",
                "content": f"Entendi esta tarefa: {prompt}",
            }
        )
        log_event(
            self.logger,
            "voice.directive.pending",
            source=source,
            prompt_length=len(prompt),
        )
        return "Diretiva preparada e a aguardar confirmacao."

    async def confirm(
        self,
        spoken_confirmation: str = "confirma",
        source: str = "voice",
    ) -> str:
        await self.clear_expired()
        pending = self.state.pending_directive
        if not pending:
            await self.connections.broadcast(
                {
                    "type": "system",
                    "content": (
                        "Nao ha diretiva de voz pendente "
                        "para confirmar."
                    ),
                }
            )
            return "Nao ha diretiva pendente."
        if (
            self.confirmation_enabled()
            and not self.is_confirmation(spoken_confirmation)
        ):
            await self.connections.broadcast(
                {
                    "type": "system",
                    "content": (
                        "Confirmacao de voz ignorada porque "
                        "nao foi uma frase explicita de "
                        "confirmacao."
                    ),
                }
            )
            return "Confirmacao ignorada."
        prompt = pending["prompt"]
        self.state.pending_directive = None
        await self.connections.broadcast(
            {
                "type": "voice_status",
                "status": "confirmed",
                "text": prompt,
            }
        )
        log_event(
            self.logger,
            "voice.directive.confirmed",
            source=source,
            prompt_length=len(prompt),
        )
        local_app = find_local_app_request(prompt)
        if local_app:
            ok, details = (
                await self.callbacks.open_local_application(
                    local_app
                )
            )
            await self.callbacks.broadcast_state("idle")
            if ok:
                log_event(
                    self.logger,
                    "local_app.opened",
                    app=local_app["id"],
                    source="voice",
                )
                await self.connections.broadcast(
                    {
                        "type": "chat",
                        "sender": "OPENCLAW",
                        "role": "Voz",
                        "content": (
                            f"Abri o {local_app['label']}."
                        ),
                    }
                )
                return "Aplicacao aberta."
            log_event(
                self.logger,
                "local_app.open_error",
                level="error",
                app=local_app["id"],
                error=details,
            )
            await self.connections.broadcast(
                {
                    "type": "chat",
                    "sender": "OPENCLAW",
                    "role": "Voz",
                    "content": (
                        f"Tentei abrir o {local_app['label']}, "
                        "mas o Windows devolveu erro: "
                        f"{details}"
                    ),
                }
            )
            return (
                "Nao foi possivel abrir a aplicacao: "
                f"{details}"
            )
        await self.start_orchestration(prompt)
        return (
            "Diretiva confirmada e orquestracao iniciada."
        )

    async def cancel(
        self,
        spoken_cancel: str = "cancela",
        source: str = "voice",
    ) -> str:
        await self.clear_expired()
        pending = self.state.pending_directive
        if not pending:
            await self.connections.broadcast(
                {
                    "type": "system",
                    "content": (
                        "Nao ha diretiva de voz pendente "
                        "para cancelar."
                    ),
                }
            )
            return "Nao ha diretiva pendente."
        if (
            self.confirmation_enabled()
            and not self.is_cancel(spoken_cancel)
        ):
            await self.connections.broadcast(
                {
                    "type": "system",
                    "content": (
                        "Cancelamento de voz ignorado porque "
                        "nao foi uma frase explicita de "
                        "cancelamento."
                    ),
                }
            )
            return "Cancelamento ignorado."
        prompt = pending["prompt"]
        self.state.pending_directive = None
        await self.connections.broadcast(
            {
                "type": "voice_status",
                "status": "cancelled",
                "text": prompt,
            }
        )
        await self.connections.broadcast(
            {
                "type": "system",
                "content": (
                    f"Diretiva de voz cancelada: {prompt}"
                ),
            }
        )
        log_event(
            self.logger,
            "voice.directive.cancelled",
            source=source,
            prompt_length=len(prompt),
        )
        return "Diretiva cancelada."

    def _schedule(self, coroutine: Any) -> None:
        self.callbacks.run_in_main_loop(coroutine)

    def _append_history(
        self,
        role: str,
        content: str,
    ) -> None:
        self.conversation_history.append(
            {"role": role, "content": content}
        )
        if len(self.conversation_history) > 100:
            self.conversation_history.pop(0)
