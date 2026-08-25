from __future__ import annotations

import asyncio
import os
import re
import time
from dataclasses import dataclass
from typing import Any, Callable

from backend.application_services import ApplicationServices
from backend.errors import safe_user_error
from backend.logging_config import log_event
from backend.services.model_service import ModelExecutionService
from backend.websocket.gateway import ConnectionManager


@dataclass(slots=True)
class ChatCommandCallbacks:
    broadcast_state: Callable[..., Any]
    on_agent_message: Callable[..., Any]
    on_file_update: Callable[..., Any]


class ChatCommandService:
    def __init__(
        self,
        *,
        services: ApplicationServices,
        models: ModelExecutionService,
        connections: ConnectionManager,
        callbacks: ChatCommandCallbacks,
        logger: Any,
    ) -> None:
        self.services = services
        self.models = models
        self.connections = connections
        self.callbacks = callbacks
        self.logger = logger

    async def query_arena_model(
        self,
        model_id: str,
        model_name: str,
        prompt: str,
    ) -> None:
        start_time = time.time()
        result_text = ""
        await self.connections.broadcast(
            {
                "type": "arena_update",
                "model_id": model_id,
                "status": "generating",
                "content": "",
                "time": 0,
                "tokens": 0,
            }
        )
        try:
            if model_id == "gemini":
                if os.getenv("GEMINI_API_KEY"):
                    response = await self.models.execute(
                        provider="gemini",
                        model="gemini-2.5-flash",
                        operation="arena_gemini",
                        system_prompt=(
                            "Responde diretamente ao pedido "
                            "do utilizador."
                        ),
                        user_prompt=prompt,
                        temperature=0.7,
                        max_output_tokens=800,
                        timeout_seconds=30.0,
                    )
                    result_text = response.raw_text
                else:
                    result_text = "SimulaÃ§Ã£o Gemini: " + prompt
            elif model_id == "qwen":
                response = await self.models.execute_local(
                    operation="arena_qwen",
                    system_prompt=(
                        "Responde diretamente ao pedido "
                        "do utilizador."
                    ),
                    user_prompt=prompt,
                    temperature=0.7,
                    max_output_tokens=400,
                    timeout_seconds=30.0,
                )
                result_text = response.raw_text
            elif model_id == "claude":
                if os.getenv("ANTHROPIC_API_KEY"):
                    response = await self.models.execute(
                        provider="anthropic",
                        model="claude-3-5-haiku-latest",
                        operation="arena_claude",
                        system_prompt=(
                            "Responde diretamente ao pedido "
                            "do utilizador."
                        ),
                        user_prompt=prompt,
                        temperature=0.7,
                        max_output_tokens=800,
                        timeout_seconds=30.0,
                    )
                    result_text = response.raw_text
                else:
                    try:
                        response = await self.models.execute_local(
                            operation=(
                                "arena_claude_local_fallback"
                            ),
                            system_prompt=(
                                "Responde diretamente ao pedido "
                                "do utilizador."
                            ),
                            user_prompt=prompt,
                            temperature=0.7,
                            max_output_tokens=400,
                            timeout_seconds=30.0,
                        )
                        result_text = response.raw_text
                    except Exception:
                        result_text = (
                            "Simulacao Claude (Sem chave "
                            "Anthropic configurada): "
                            + prompt
                        )
        except Exception as model_error:
            result_text = safe_user_error(
                f"Erro ao chamar {model_name}",
                model_error,
            )
        duration = time.time() - start_time
        token_count = len(result_text.split()) * 4 // 3
        await self.connections.broadcast(
            {
                "type": "arena_update",
                "model_id": model_id,
                "status": "complete",
                "content": result_text,
                "time": round(duration, 2),
                "tokens": token_count,
            }
        )

    async def run_arena(self, prompt: str) -> None:
        await self.connections.broadcast(
            {
                "type": "system",
                "content": (
                    "Arena Swarm iniciada para o prompt: "
                    f"'{prompt}'"
                ),
            }
        )
        await self.connections.broadcast(
            {
                "type": "arena_update",
                "model_id": "groq",
                "status": "disabled",
                "content": (
                    "Desativado (Groq API Key removida)"
                ),
                "time": "-",
                "tokens": "-",
            }
        )
        await asyncio.gather(
            self.query_arena_model(
                "gemini",
                "Gemini 3.5 Flash",
                prompt,
            ),
            self.query_arena_model(
                "qwen",
                "Qwen 2.5 (Local)",
                prompt,
            ),
            self.query_arena_model(
                "claude",
                "Claude 3.5 (Sonnet)",
                prompt,
            ),
        )
        await self.connections.broadcast(
            {
                "type": "system",
                "content": (
                    "Arena Swarm finalizada. Todos os "
                    "modelos responderam!"
                ),
            }
        )

    async def handle(
        self,
        command: str,
        _websocket: Any,
        _session_id: int,
    ) -> None:
        parts = command.split(" ", 1)
        name = parts[0].lower()
        arguments = (
            parts[1].strip()
            if len(parts) > 1
            else ""
        )
        await self._chat(
            "OPENCLAW",
            "Orquestrador",
            f"ðŸ› ï¸ **Comando Executado:** `{command}`",
        )
        if name == "/review":
            await self._review()
        elif name == "/refactor":
            await self._refactor()
        elif name == "/theme":
            await self._theme(arguments)
        elif name == "/spawn":
            await self._spawn(arguments)
        elif name == "/arena":
            await self._arena(arguments)
        elif name == "/rules":
            await self._rules()
        elif name == "/learn":
            await self._learn(arguments)
        elif name == "/forget":
            await self._forget(arguments)
        elif name == "/help":
            await self._help()
        else:
            await self._chat(
                "OPENCLAW",
                "Orquestrador",
                (
                    "⚠️ Tema desconhecido. Temas validos: "
                    "`/theme neon`, `/theme cyberpunk`, "
                    "`/theme clean`"
                ),
            )

    async def _spawn(self, arguments: str) -> None:
        try:
            parts = arguments.split("|")
            if len(parts) < 3:
                raise ValueError("Formato invalido.")
            name = parts[0].strip()
            specialty = parts[1].strip()
            task = parts[2].strip()
            if not name or not specialty or not task:
                raise ValueError("Nome, especialidade e tarefa sao obrigatorios.")
            await self.callbacks.broadcast_state("processing")
            await self.connections.broadcast(
                {
                    "type": "system",
                    "content": (
                        f"A criar e executar subagente especialista {name} ({specialty})..."
                    ),
                }
            )
            result = (
                await self.services.agents
                .spawn_specialist_agent(
                    nome=name,
                    especialidade=specialty,
                    backstory=(
                        f"Es o subagente especialista {name}, "
                        f"focado em {specialty}."
                    ),
                    tarefa=task,
                    contexto_projeto=(
                        "Criacao ad-hoc via comando de barra."
                    ),
                    on_msg=self.callbacks.on_agent_message,
                )
            )
            await self._chat(
                name.upper(),
                specialty,
                result or f"Tarefa concluida pelo especialista {name}.",
            )
            await self.callbacks.broadcast_state("idle")
        except ValueError:
            await self._chat(
                "OPENCLAW",
                "Orquestrador",
                (
                    "⚠️ Formato invalido. Uso: "
                    "`/spawn Nome | Especialidade | Tarefa` "
                    "(ex: `/spawn Marta | Dev SQL | Cria uma "
                    "query para clientes`)"
                ),
            )
            await self.callbacks.broadcast_state("idle")
        except Exception as exc:
            log_event(
                self.logger,
                "chat_command.spawn_error",
                level="error",
                error=str(exc),
            )
            await self._chat(
                "OPENCLAW",
                "Orquestrador",
                f"❌ Erro ao executar subagente: {exc}",
            )
            await self.callbacks.broadcast_state("idle")

    async def _arena(self, arguments: str) -> None:
        prompt = arguments.strip()
        if not prompt:
            await self._chat(
                "OPENCLAW",
                "Orquestrador",
                (
                    "âš ï¸ Introduza um prompt para a Arena "
                    "(ex: `/arena Criar um botÃ£o pulsante neon`)"
                ),
            )
            return
        await self.callbacks.broadcast_state("processing")
        await self.connections.broadcast(
            {"type": "ui", "action": "show_arena_tab"}
        )
        asyncio.create_task(self.run_arena(prompt))

    async def _rules(self) -> None:
        rules = self.services.database.get_compounding_rules()
        if not rules:
            text = (
                "ðŸ§  **Compounding Memory:** Nenhuma regra ou "
                "liÃ§Ã£o aprendida guardada no SQLite."
            )
        else:
            text = "ðŸ§  **Compounding Memory (Regras Ativas):**\n"
            for rule in rules:
                text += (
                    f"- `{rule['rule_key']}`: "
                    f"{rule['description']} -> "
                    f"*{rule['correction']}*\n"
                )
        await self._chat("OPENCLAW", "Orquestrador", text)

    async def _learn(self, arguments: str) -> None:
        try:
            parts = arguments.split("|")
            key = parts[0].strip().replace(" ", "_").lower()
            description = parts[1].strip()
            correction = parts[2].strip()
            self.services.database.add_compounding_rule(
                key,
                description,
                correction,
            )
            rules = (
                self.services.database.get_compounding_rules()
            )
            await self.connections.broadcast(
                {"type": "rules_list", "rules": rules}
            )
            await self.connections.broadcast(
                {"type": "rules_updated", "rules": rules}
            )
            await self._chat(
                "OPENCLAW",
                "Orquestrador",
                (
                    "âœ… Nova regra de memÃ³ria "
                    f"`{key}` gravada com sucesso!"
                ),
            )
        except Exception:
            await self._chat(
                "OPENCLAW",
                "Orquestrador",
                (
                    "âš ï¸ Formato invÃ¡lido. Uso: "
                    "`/learn chave | descriÃ§Ã£o | correÃ§Ã£o` "
                    "(ex: `/learn python_venv | O utilizador usa "
                    "venv/Scripts/python | Sempre usar o caminho "
                    "completo da venv`)"
                ),
            )

    async def _forget(self, arguments: str) -> None:
        key = arguments.strip().lower()
        if not key:
            await self._chat(
                "OPENCLAW",
                "Orquestrador",
                (
                    "âš ï¸ Introduza a chave da regra a apagar "
                    "(ex: `/forget python_venv`)"
                ),
            )
            return
        deleted = (
            self.services.database.delete_compounding_rule(key)
        )
        if deleted:
            rules = (
                self.services.database.get_compounding_rules()
            )
            await self.connections.broadcast(
                {"type": "rules_list", "rules": rules}
            )
            await self.connections.broadcast(
                {"type": "rules_updated", "rules": rules}
            )
            text = (
                f"âœ… Regra `{key}` esquecida/apagada "
                "com sucesso!"
            )
        else:
            text = (
                f"âš ï¸ Regra `{key}` nÃ£o encontrada "
                "no SQLite."
            )
        await self._chat("OPENCLAW", "Orquestrador", text)

    async def _help(self) -> None:
        await self._chat(
            "OPENCLAW",
            "Orquestrador",
            (
                "ðŸ“– **Comandos de Barra DisponÃ­veis:**\n"
                "- `/review` : Audita o cÃ³digo na sandbox "
                "(QA Quinn)\n- `/refactor` : Otimiza e limpa "
                "o cÃ³digo sandbox (Devon)\n"
                "- `/theme [neon|cyberpunk|clean]` : Muda o "
                "tema visual da app\n"
                "- `/spawn Nome | Especialidade | Tarefa` : "
                "Cria e executa um subagente especialista ad-hoc\n"
                "- `/arena [prompt]` : Compara a velocidade e o "
                "cÃ³digo gerado por mÃºltiplos modelos na Swarm "
                "Arena\n- `/rules` : Lista as regras de "
                "compounding memory ativas no SQLite\n"
                "- `/learn chave | desc | corr` : Cria ou "
                "atualiza manualmente uma regra de memÃ³ria\n"
                "- `/forget chave` : Remove uma regra de "
                "memÃ³ria da base de dados\n"
                "- `/help` : Mostra esta ajuda"
            ),
        )

    def _read_sandbox_files(self) -> tuple[str, str, str]:
        contents = []
        for filename in ("index.html", "styles.css", "app.js"):
            path = os.path.join(
                self.services.sandbox.SANDBOX_DIR,
                filename,
            )
            try:
                if os.path.exists(path):
                    with open(
                        path,
                        "r",
                        encoding="utf-8",
                    ) as source_file:
                        contents.append(source_file.read())
                else:
                    contents.append("")
            except Exception as read_error:
                log_event(
                    self.logger,
                    "sandbox_files.read_error",
                    level="error",
                    error=str(read_error),
                )
                contents.append("")
        return tuple(contents)

    def _write_sandbox_files(self, *matches: Any) -> list[str]:
        refined = []
        for filename, match in zip(
            ("index.html", "styles.css", "app.js"),
            matches,
        ):
            if not match:
                continue
            content = match.group(1).strip()
            path = os.path.join(
                self.services.sandbox.SANDBOX_DIR,
                filename,
            )
            with open(path, "w", encoding="utf-8") as target:
                target.write(content)
            self.callbacks.on_file_update(filename, content)
            refined.append(filename)
        return refined

    async def _chat(
        self,
        sender: str,
        role: str,
        content: str,
    ) -> None:
        await self.connections.broadcast(
            {
                "type": "chat",
                "sender": sender,
                "role": role,
                "content": content,
            }
        )
