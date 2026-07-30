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
                    f"âš ï¸ Comando desconhecido: `{name}`. "
                    "Digite `/help` para ajuda."
                ),
            )

    async def _review(self) -> None:
        await self.callbacks.broadcast_state("processing")
        await self.connections.broadcast(
            {
                "type": "system",
                "content": (
                    "A iniciar auditoria QA automÃ¡tica nos "
                    "ficheiros da sandbox..."
                ),
            }
        )
        html, css, javascript = self._read_sandbox_files()
        task = (
            "Analisa os ficheiros da sandbox:\n"
            f"HTML:\n{html}\n\nCSS:\n{css}\n\n"
            f"JS:\n{javascript}\n\nFaz um relatÃ³rio "
            "detalhado de testes, indicando se existem erros "
            "de visualizaÃ§Ã£o, sintaxe ou de caminho de imagens. "
            "Termina com 'APROVAÃ‡ÃƒO: SIM' ou "
            "'APROVAÃ‡ÃƒO: NÃƒO'."
        )
        report = (
            await self.services.agents.spawn_specialist_agent(
                nome="Quinn",
                especialidade="Auditor QA",
                backstory=(
                    "Ã‰s o Quinn, o auditor de qualidade "
                    "experiente da agÃªncia. Analisas cÃ³digo "
                    "para garantir que tudo funciona."
                ),
                tarefa=task,
                contexto_projeto=(
                    "Auditoria de qualidade manual via "
                    "slash command."
                ),
                on_msg=self.callbacks.on_agent_message,
            )
        )
        await self._chat(
            "QUINN",
            "QA Engineer (Slash Command)",
            report,
        )
        await self.callbacks.broadcast_state("idle")

    async def _refactor(self) -> None:
        await self.callbacks.broadcast_state("processing")
        await self.connections.broadcast(
            {
                "type": "system",
                "content": (
                    "ðŸ”„ A iniciar ciclo Self-Healing "
                    "(Devon â†’ Quinn, atÃ© 3 tentativas)..."
                ),
            }
        )
        maximum_cycles = 3
        feedback = ""
        approved = False
        for cycle in range(1, maximum_cycles + 1):
            await self.connections.broadcast(
                {
                    "type": "system",
                    "content": (
                        f"ðŸ”§ Ciclo {cycle}/{maximum_cycles} "
                        "â€” Devon a refatorar..."
                    ),
                }
            )
            html, css, javascript = (
                self._read_sandbox_files()
            )
            feedback_section = (
                "\n\nâš ï¸ Feedback do QA "
                f"(ciclo anterior):\n{feedback}"
                if feedback
                else ""
            )
            task = (
                "Otimiza o cÃ³digo da sandbox para garantir "
                "mÃ¡xima performance e conformidade com as "
                f"regras de visualizaÃ§Ã£o:{feedback_section}\n"
                f"HTML:\n{html}\n\nCSS:\n{css}\n\n"
                f"JS:\n{javascript}\n\nRetorna as versÃµes "
                "completas otimizadas e limpas em blocos de "
                "cÃ³digo markdown: ```html ... ```, "
                "```css ... ``` e ```javascript ... ```."
            )
            refactor_report = (
                await self.services.agents
                .spawn_specialist_agent(
                    nome="Devon",
                    especialidade="Programador OtimizaÃ§Ã£o",
                    backstory=(
                        "Ã‰s o Devon, o programador core da "
                        "agÃªncia. Refatoras cÃ³digo para "
                        "garantir clareza, performance e beleza."
                    ),
                    tarefa=task,
                    contexto_projeto=(
                        f"Ciclo Self-Healing {cycle}/"
                        f"{maximum_cycles}."
                    ),
                    on_msg=self.callbacks.on_agent_message,
                )
            )
            matches = (
                re.search(
                    r"```html\n(.*?)\n```",
                    refactor_report,
                    re.DOTALL,
                ),
                re.search(
                    r"```css\n(.*?)\n```",
                    refactor_report,
                    re.DOTALL,
                ),
                re.search(
                    r"```(?:javascript|js)\n(.*?)\n```",
                    refactor_report,
                    re.DOTALL,
                ),
            )
            refined = self._write_sandbox_files(*matches)
            if refined:
                await self._chat(
                    "DEVON",
                    f"Programador (Ciclo {cycle})",
                    (
                        "âœ… CÃ³digo atualizado na sandbox: "
                        + ", ".join(refined)
                    ),
                )
            else:
                await self._chat(
                    "DEVON",
                    f"Programador (Ciclo {cycle})",
                    refactor_report,
                )
                break
            await self.connections.broadcast(
                {
                    "type": "system",
                    "content": (
                        "ðŸ” Quinn a auditar cÃ³digo "
                        f"(ciclo {cycle})..."
                    ),
                }
            )
            new_html, new_css, new_javascript = (
                self._read_sandbox_files()
            )
            review_task = (
                "Analisa os ficheiros da sandbox (ciclo "
                f"Self-Healing {cycle}):\nHTML:\n{new_html}\n\n"
                f"CSS:\n{new_css}\n\nJS:\n{new_javascript}\n\n"
                "Faz um relatÃ³rio detalhado de testes, "
                "indicando se existem erros de visualizaÃ§Ã£o, "
                "sintaxe ou de caminho de imagens. Termina com "
                "'APROVAÃ‡ÃƒO: SIM' ou 'APROVAÃ‡ÃƒO: NÃƒO'."
            )
            qa_report = (
                await self.services.agents
                .spawn_specialist_agent(
                    nome="Quinn",
                    especialidade="Auditor QA",
                    backstory=(
                        "Ã‰s o Quinn, o auditor de qualidade "
                        "experiente da agÃªncia. Analisas "
                        "cÃ³digo para garantir que tudo funciona."
                    ),
                    tarefa=review_task,
                    contexto_projeto=(
                        "Auto-auditoria Self-Healing "
                        f"ciclo {cycle}."
                    ),
                    on_msg=self.callbacks.on_agent_message,
                )
            )
            await self._chat(
                "QUINN",
                f"QA (Ciclo {cycle})",
                qa_report,
            )
            if "APROVAÃ‡ÃƒO: SIM" in qa_report.upper():
                await self._chat(
                    "OPENCLAW",
                    "Orquestrador",
                    (
                        "âœ… **Self-Healing concluÃ­do** em "
                        f"{cycle} ciclo(s). QA aprovou o cÃ³digo!"
                    ),
                )
                approved = True
                break
            feedback = qa_report
            await self.connections.broadcast(
                {
                    "type": "system",
                    "content": (
                        "âš ï¸ QA rejeitou "
                        f"(ciclo {cycle}). Devon irÃ¡ corrigir "
                        "automaticamente..."
                    ),
                }
            )
        if not approved:
            await self._chat(
                "OPENCLAW",
                "Orquestrador",
                (
                    "âš ï¸ **Self-Healing atingiu o limite de "
                    f"{maximum_cycles} ciclos.** RevÃª o cÃ³digo "
                    "manualmente."
                ),
            )
        await self.callbacks.broadcast_state("idle")

    async def _theme(self, arguments: str) -> None:
        theme = arguments.strip().lower()
        if theme in {"neon", "cyberpunk", "clean"}:
            await self.connections.broadcast(
                {"type": "ui_theme", "theme": theme}
            )
            await self._chat(
                "OPENCLAW",
                "Orquestrador",
                (
                    "ðŸŽ¨ Tema visual alterado para: "
                    f"**{theme.upper()}**"
                ),
            )
        else:
            await self._chat(
                "OPENCLAW",
                "Orquestrador",
                (
                    "âš ï¸ Tema desconhecido. Temas vÃ¡lidos: "
                    "`/theme neon`, `/theme cyberpunk`, "
                    "`/theme clean`"
                ),
            )

    async def _spawn(self, arguments: str) -> None:
        try:
            parts = arguments.split("|")
            name = parts[0].strip()
            specialty = parts[1].strip()
            task = parts[2].strip()
            await self.callbacks.broadcast_state("processing")
            await self.connections.broadcast(
                {
                    "type": "system",
                    "content": (
                        "A criar e executar subagente "
                        f"especialista {name}..."
                    ),
                }
            )
            result = (
                await self.services.agents
                .spawn_specialist_agent(
                    nome=name,
                    especialidade=specialty,
                    backstory=(
                        f"Ã‰s o subagente especialista {name}, "
                        f"focado em {specialty}."
                    ),
                    tarefa=task,
                    contexto_projeto=(
                        "CriaÃ§Ã£o ad-hoc via comando de barra."
                    ),
                    on_msg=self.callbacks.on_agent_message,
                )
            )
            await self._chat(
                name.upper(),
                specialty,
                result,
            )
            await self.callbacks.broadcast_state("idle")
        except Exception:
            await self._chat(
                "OPENCLAW",
                "Orquestrador",
                (
                    "âš ï¸ Formato invÃ¡lido. Uso: "
                    "`/spawn Nome | Especialidade | Tarefa` "
                    "(ex: `/spawn Marta | Dev SQL | Cria uma "
                    "query para clientes`)"
                ),
            )

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
