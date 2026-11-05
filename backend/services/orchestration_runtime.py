from __future__ import annotations

import asyncio
import json
import os
import re
from dataclasses import dataclass
from typing import Any, Callable

from backend.application_services import ApplicationServices
from backend.errors import safe_user_error
from backend.logging_config import log_event
from backend.model_harness import OutputFormat
from backend.server_helpers import (
    env_bool,
    is_orchestration_result_error,
    normalize_template_name,
)
from backend.services.local_app_service import (
    find_local_app_request,
)
from backend.services.model_service import ModelExecutionService
from backend.websocket.gateway import ConnectionManager


CASUAL_CHAT_SYSTEM_PROMPT = (
    "És o JARVIS, assistente técnico de engenharia de software e orquestrador avançado de sistemas. "
    "Responde sempre em português de Portugal de forma natural, concisa, elegante e estritamente técnica.\n"
    "DIRETIVAS ANTI-TEATRO E DE PRECISÃO TÉCNICA (OBRIGATÓRIO):\n"
    "1. NUNCA FAÇAS TEATRO: NUNCA digas 'vou coordenar a equipa', 'estou a coordenar a equipa', "
    "'a equipa de especialistas vai tratar', ou 'vou tratar do assunto' em conversação de chat. "
    "Se não estás ativamente a executar tarefas ou um pipeline em tempo real, é terminantemente proibido "
    "fingir ou prometer que agentes ou equipas estão a trabalhar nos bastidores.\n"
    "2. RESPOSTAS TÉCNICAS DIRETAS E CONCRETAS: Se o utilizador perguntar 'como garanto X no projeto Y?', "
    "'como faço X?', 'como funciona X?' ou colocar qualquer questão técnica/arquitetural, responde "
    "IMEDIATAMENTE com a solução técnica concreta, arquitetura, bibliotecas reais adequadas e exemplos "
    "de código ou comandos aplicáveis. Nunca substituas uma resposta técnica por promessas de futuro.\n"
    "3. FUNDAMENTAÇÃO NO PROJETO: Quando a questão envolver um projeto do workspace (ex: dina), baseia a "
    "resposta no código, estrutura e tecnologias reais do projeto fornecidos no contexto. Sê direto e prático.\n"
    "4. CONSCIÊNCIA DE ESTADO: Tens acesso ao histórico recente da conversa. Se não souberes algo, indica com "
    "honestidade em vez de inventar tarefas imaginárias."
)



@dataclass(slots=True)
class OrchestrationCallbacks:
    broadcast_state: Callable[..., Any]
    open_local_application: Callable[..., Any]
    run_in_main_loop: Callable[..., Any]
    on_agent_message: Callable[..., Any]
    on_file_update: Callable[..., Any]
    on_kanban_update: Callable[..., Any]
    build_template_payload: Callable[[str], dict]


class OrchestrationService:
    def __init__(
        self,
        *,
        services: ApplicationServices,
        models: ModelExecutionService,
        connections: ConnectionManager,
        callbacks: OrchestrationCallbacks,
        conversation_history: list[dict],
        logger: Any,
    ) -> None:
        self.services = services
        self.models = models
        self.connections = connections
        self.callbacks = callbacks
        self.conversation_history = conversation_history
        self.logger = logger
        from backend.services.chat_mission_bridge import ChatMissionBridge
        self.bridge = ChatMissionBridge(
            mission_state=getattr(services.mission_planner, "mission_state", None) if services.mission_planner else None,
            mission_planner=services.mission_planner,
            mission_executor=services.mission_executor,
            mission_autonomy=services.mission_autonomy,
            project_intake=getattr(services.project_context, "intake", None) if services.project_context else None,
            project_context=services.project_context,
            orchestration_service=self,
            connections=connections,
            callbacks=callbacks,
            logger=logger,
        )

    async def auto_extract_correction(
        self,
        prompt: str,
        history: list,
    ) -> None:
        clean = prompt.lower().strip(" .?!,")
        correction_signals = [
            "não",
            "no",
            "errado",
            "corrige",
            "correção",
            "correcao",
            "prefiro",
            "deves",
            "deves usar",
            "esquece",
            "tenta outra vez",
            "tenta de novo",
            "muda",
        ]
        if not any(
            clean.startswith(signal)
            for signal in correction_signals
        ):
            return
        if not history or len(history) < 2:
            return
        last_assistant_message = next(
            (
                message["content"]
                for message in reversed(history)
                if message["role"] == "assistant"
                and message.get("content")
            ),
            "",
        )
        if not last_assistant_message:
            return
        system_instruction = (
            "Estás a monitorizar a conversa entre o utilizador "
            "(CEO) e o Jarvis/OpenClaw (orquestrador de IA). "
            "O CEO acabou de fazer uma correção ou expressar uma "
            "preferência sobre a resposta anterior do Jarvis.\n"
            "A tua tarefa é extrair uma REGRA DE "
            "COMPORTAMENTO/PROGRAMAÇÃƒO concreta a partir desta "
            "correção para evitar que o Jarvis cometa o mesmo "
            "erro no futuro.\nResponde EXCLUSIVAMENTE em formato "
            "JSON com três chaves:\n1. 'rule_key': Uma "
            "palavra-chave única (slug, sem espaços, minúscula, "
            "ex: 'neon_theme_default', 'venv_python_path').\n"
            "2. 'description': Resumo de 1 frase do erro ou "
            "contexto detetado (ex: 'Jarvis usou tema cyberpunk "
            "mas o utilizador corrigiu que prefere neon.').\n"
            "3. 'correction': Instrução corretiva clara em "
            "português de Portugal (ex: 'Sempre que o tema visual "
            "for solicitado ou alterado, usar neon por defeito, a "
            "menos que o utilizador especifique o contrário.').\n"
            "Se o input não for realmente uma correção de "
            "comportamento técnica relevante, responde apenas '{}'."
        )
        user_context = (
            "Resposta Anterior do Jarvis:\n"
            f"{last_assistant_message}\n\n"
            f"Correção/Feedback do CEO:\n{prompt}"
        )
        try:
            response = await self.models.execute_local(
                operation="auto_extract_correction",
                system_prompt=system_instruction,
                user_prompt=user_context,
                output_format=OutputFormat.JSON,
                temperature=0.0,
                max_output_tokens=300,
                timeout_seconds=10.0,
            )
            rule_data = json.loads(response.raw_text)
            if (
                not rule_data
                or "rule_key" not in rule_data
                or "correction" not in rule_data
            ):
                return
            key = rule_data["rule_key"].strip().lower()
            description = rule_data.get(
                "description",
                "Auto-extraído via feedback",
            )
            self.services.database.add_compounding_rule(
                key,
                description,
                rule_data["correction"],
            )
            log_event(
                self.logger,
                "auto_learning.rule_saved",
                rule_key=key,
            )
            await self.connections.broadcast(
                {
                    "type": "chat",
                    "sender": "SISTEMA",
                    "role": "System",
                    "content": (
                        "🧠 *Auto-Aprendizagem:* Nova regra "
                        f"`{key}` gravada na minha Compounding "
                        "Memory com base no seu feedback."
                    ),
                }
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
        except Exception as extraction_error:
            log_event(
                self.logger,
                "auto_learning.rule_extract_error",
                level="error",
                error=str(extraction_error),
            )

    async def classify_intent(
        self,
        prompt: str,
        history: list | None = None,
        binary: bool = False,
    ) -> str:
        """Canonical intent classification delegated to ChatMissionBridge resolver."""
        if self.bridge and hasattr(self.bridge, "resolver"):
            resolved = self.bridge.resolver.resolve_request(prompt, history=history)
            canonical = resolved.intent.value
            if binary:
                return "CHAT" if canonical in {"CHAT", "CONVERSATIONAL"} else "TASK"
            return canonical
        clean = prompt.lower().strip(" .?!,")
        greetings = ["olá", "oi", "bom dia", "boa tarde", "boa noite", "tudo bem", "como estás"]
        if clean in greetings:
            return "CHAT"
        return "TASK"

    async def run_casual_chat(
        self,
        prompt: str,
        project_id: str | None = None,
        correlation_id: str | None = None,
    ) -> None:
        mode = os.getenv(
            "ORCHESTRATOR_MODE",
            "local",
        ).lower()
        response_text = ""

        # Enriquecimento com contexto técnico real do projeto quando aplicável
        system_prompt = CASUAL_CHAT_SYSTEM_PROMPT
        target_proj = project_id
        proj_match = re.search(
            r"(?:ao\s+projeto|do\s+projeto|no\s+projeto|projeto|project)\s+[:=]?\s*([a-zA-Z0-9_\-]+)",
            prompt.lower(),
        )
        if proj_match:
            candidate_proj = proj_match.group(1).strip()
            if candidate_proj not in {"novo", "atual", "default", "meu", "este", "esse", "qualquer", "web"}:
                target_proj = candidate_proj

        if target_proj and target_proj not in {"default-project", "default"}:
            projects_root = "workspace/projects"
            if hasattr(self.services, "mission_planner") and self.services.mission_planner:
                ms = getattr(self.services.mission_planner, "mission_state", None)
                if ms and hasattr(ms, "projects_root"):
                    projects_root = ms.projects_root
            proj_dir = os.path.join(projects_root, target_proj)
            if not os.path.isdir(proj_dir):
                proj_dir = os.path.join("workspace", "projects", target_proj)

            if os.path.isdir(proj_dir):
                try:
                    entries = [
                        f
                        for f in os.listdir(proj_dir)
                        if not f.startswith(".") and f not in {"node_modules", "__pycache__"}
                    ][:15]
                    snippets = []
                    for kf in ["app.js", "package.json", "main.py", "server.js", "index.html"]:
                        kf_path = os.path.join(proj_dir, kf)
                        if os.path.isfile(kf_path):
                            with open(kf_path, "r", encoding="utf-8", errors="ignore") as f:
                                snippets.append(f"--- {kf} ---\n{f.read(3000)}")
                    system_prompt = (
                        f"{system_prompt}\n\n"
                        f"[Contexto Técnico Real do Projeto '{target_proj}']:\n"
                        f"Ficheiros existentes: {', '.join(entries)}\n"
                        + "\n".join(snippets)
                    )
                except Exception as ctx_err:
                    log_event(self.logger, "casual_chat.project_context_error", error=str(ctx_err))

        chat_max_tokens = int(os.getenv("CHAT_MAX_TOKENS", "4096"))
        chat_timeout = float(os.getenv("CHAT_TIMEOUT_SECONDS", "45.0"))

        if (
            mode == "claude"
            and os.getenv("ANTHROPIC_API_KEY")
        ):
            try:
                messages = [
                    {
                        "role": message["role"],
                        "content": message["content"],
                    }
                    for message in self.conversation_history
                ]
                if (
                    not messages
                    or messages[-1]["content"] != prompt
                ):
                    messages.append(
                        {"role": "user", "content": prompt}
                    )
                response = await self.models.execute(
                    provider="anthropic",
                    model="claude-3-5-sonnet-latest",
                    operation="casual_chat",
                    system_prompt=system_prompt,
                    user_prompt=prompt,
                    conversation_messages=messages,
                    temperature=0.0,
                    max_output_tokens=chat_max_tokens,
                    timeout_seconds=chat_timeout,
                )
                response_text = response.raw_text
            except Exception as model_error:
                response_text = safe_user_error(
                    "Erro ao comunicar com a Claude API",
                    model_error,
                )
        if not response_text:
            local_timeout = float(os.getenv("OLLAMA_CHAT_TIMEOUT", "60.0"))
            try:
                messages = [
                    {
                        "role": message["role"],
                        "content": message["content"],
                    }
                    for message in self.conversation_history
                ]
                if (
                    not messages
                    or messages[-1]["content"] != prompt
                ):
                    messages.append(
                        {"role": "user", "content": prompt}
                    )
                response = await self.models.execute_local(
                    operation="casual_chat",
                    system_prompt=system_prompt,
                    user_prompt=prompt,
                    conversation_messages=messages,
                    temperature=0.1,
                    max_output_tokens=chat_max_tokens,
                    timeout_seconds=local_timeout,
                )
                response_text = response.raw_text
            except Exception as model_error:
                allow_fallback = env_bool("ALLOW_EXTERNAL_FALLBACK", False) or mode in ("gemini", "cloud")
                if allow_fallback and os.getenv("GEMINI_API_KEY"):
                    try:
                        gemini_model = os.getenv("GEMINI_CREW_MODEL", "gemini-2.5-flash").replace("gemini/", "").strip()
                        gemini_res = await self.models.execute(
                            provider="gemini",
                            model=gemini_model,
                            operation="casual_chat",
                            system_prompt=system_prompt,
                            user_prompt=prompt,
                            conversation_messages=messages,
                            temperature=0.2,
                            max_output_tokens=chat_max_tokens,
                            timeout_seconds=chat_timeout,
                        )
                        response_text = gemini_res.raw_text
                    except Exception as gemini_err:
                        response_text = f"Erro no fallback externo (Gemini): {gemini_err}"
                else:
                    response_text = f"Erro no modelo local: {model_error}. O fallback para fornecedores externos está desativado por política de privacidade."

        # Fiscalização da Verdade de Execução: proibir afirmações de que código foi alterado sem ferramentas/evidências
        from security.delivery_governance.decision_model import ExecutionTruthEnforcer, ExecutionTruthState
        _, response_text = ExecutionTruthEnforcer.audit_response_truth(
            response_text,
            tools_called_count=0,
            files_modified_count=0,
            execution_state=ExecutionTruthState.REQUEST_RECEIVED,
        )

        if self.bridge and hasattr(self.bridge, "broadcast_chat"):
            await self.bridge.broadcast_chat(
                "JARVIS",
                "Assistant",
                response_text,
                correlation_id=correlation_id,
            )
        else:
            await self.connections.broadcast(
                {
                    "type": "chat",
                    "sender": "JARVIS",
                    "role": "Assistant",
                    "content": response_text,
                }
            )
            self._append_history("assistant", response_text)

    async def run_task(
        self,
        prompt: str,
        session_id: int,
        project_id: str | None = None,
        correlation_id: str | None = None,
    ) -> None:
        try:
            clean_prompt = prompt.lower().strip(" .?!,")
            if await self._handle_ui_command(clean_prompt):
                return
            local_app = find_local_app_request(prompt)
            if local_app:
                await self._open_local_app(local_app)
                return
            if env_bool("ORCHESTRATOR_AUTO_LEARN", False):
                asyncio.create_task(
                    self.auto_extract_correction(
                        prompt,
                        self.conversation_history,
                    )
                )

            # ── Canonical Chat -> Mission Integration ────────────────────────
            if self.bridge:
                bridge_res = await self.bridge.handle_directive(
                    prompt=prompt,
                    session_id=session_id,
                    project_id=project_id,
                    correlation_id=correlation_id,
                )
                if bridge_res.get("status") in {"COMPLETED", "FAILED", "REFUSED", "BLOCKED"}:
                    return

            intent = await self.classify_intent(
                prompt,
                self.conversation_history,
            )
            log_event(
                self.logger,
                "orchestration.intent_classified",
                intent=intent,
                prompt_length=len(prompt),
            )
            if intent == "CHAT":
                await self.run_casual_chat(prompt, project_id=project_id, correlation_id=correlation_id)
                await self.callbacks.broadcast_state("idle")
                return

            try:
                from intelligence.artifact_inference import CapabilityDetector
                detected_caps = CapabilityDetector().detect(prompt)
                log_event(
                    self.logger,
                    "orchestration.capabilities_detected",
                    capabilities=[c.value for c in detected_caps],
                )
            except Exception:
                pass

            if await self._run_project_builder_if_requested(
                prompt
            ):
                return
            await self._run_agent_orchestration(
                prompt,
                session_id,
            )
        except Exception as orchestration_error:
            log_event(
                self.logger,
                "orchestration.task_error",
                level="error",
                error=str(orchestration_error),
            )
            await self.callbacks.broadcast_state("idle")
            await self.connections.broadcast(
                {
                    "type": "system",
                    "content": safe_user_error(
                        "Erro na orquestracao",
                        orchestration_error,
                    ),
                }
            )

    async def _handle_ui_command(
        self,
        clean_prompt: str,
    ) -> bool:
        commands = (
            (
                "open_chat",
                (
                    "abre o chat",
                    "abrir o chat",
                    "mostra o chat",
                    "mostrar o chat",
                    "chat",
                    "abre a conversa",
                    "abrir conversa",
                    "mostra a conversa",
                    "exibe o chat",
                    "spawna o chat",
                    "spawna a janela de chat",
                    "abre janela de chat",
                    "quero o chat",
                    "mostra chat",
                    "exibir chat",
                ),
                (
                    "abre o chat",
                    "mostra o chat",
                    "abre a conversa",
                ),
                "Janela de conversa aberta, Sir.",
            ),
            (
                "close_chat",
                (
                    "fecha o chat",
                    "fechar o chat",
                    "oculta o chat",
                    "ocultar o chat",
                    "minimiza o chat",
                    "esconde o chat",
                    "esconder o chat",
                    "fecha a conversa",
                    "fechar conversa",
                    "ocultar conversa",
                    "fechar janela de chat",
                ),
                (
                    "fecha o chat",
                    "oculta o chat",
                    "fecha a conversa",
                ),
                "Ocultei a janela de conversa.",
            ),
            (
                "open_dev",
                (
                    "abre o painel dev",
                    "abrir o painel dev",
                    "mostra o painel dev",
                    "mostrar o painel dev",
                    "painel dev",
                    "abre painel de desenvolvimento",
                    "mostra painel dev",
                    "abre o dev panel",
                    "mostra dev panel",
                    "abre a consola dev",
                    "mostrar consola dev",
                    "abrir dev",
                    "abrir consola de desenvolvimento",
                    "mostra o painel de desenvolvimento",
                    "abre painel de controlo",
                    "abre painel de controle",
                ),
                (
                    "abre o painel dev",
                    "mostra o painel dev",
                    "abre o dev panel",
                ),
                "Painel de desenvolvimento expandido.",
            ),
            (
                "close_dev",
                (
                    "fecha o painel dev",
                    "fechar o painel dev",
                    "oculta o painel dev",
                    "ocultar o painel dev",
                    "minimiza o painel dev",
                    "fecha dev",
                    "fechar dev",
                    "esconde dev",
                    "esconder dev",
                    "fecha o dev panel",
                    "fechar dev panel",
                ),
                (
                    "fecha o painel dev",
                    "oculta o painel dev",
                    "fecha o dev panel",
                ),
                "Painel de desenvolvimento ocultado.",
            ),
        )
        for action, keywords, contains, response in commands:
            if clean_prompt in keywords or any(
                fragment in clean_prompt
                for fragment in contains
            ):
                await self.connections.broadcast(
                    {"type": "ui_action", "action": action}
                )
                await self.callbacks.broadcast_state("idle")
                await self._broadcast_orchestrator(response)
                return True
        dashboard_keywords = (
            "abre a dashboard",
            "abrir a dashboard",
            "mostra a dashboard",
            "mostrar a dashboard",
            "ver a dashboard",
            "dashboard",
            "abrir painel",
            "mostrar painel",
            "abre o painel",
            "mostra o painel",
            "abrir dashboard",
            "mostrar dashboard",
            "mostra-me a dashboard",
            "mostra-me o painel",
            "exibe a dashboard",
            "exibir a dashboard",
        )
        if clean_prompt in dashboard_keywords or any(
            fragment in clean_prompt
            for fragment in (
                "abre a dashboard",
                "mostra a dashboard",
                "mostra-me a dashboard",
                "abrir a dashboard",
                "abrir o painel",
            )
        ):
            await self.connections.broadcast(
                {"type": "ui", "action": "show_dashboard"}
            )
            await self.callbacks.broadcast_state("idle")
            await self._broadcast_orchestrator(
                "Painel de trabalho e dashboard expandidos, Sir."
            )
            return True
        main_keywords = (
            "volta ao ecra principal",
            "volta ao ecrã principal",
            "ecra principal",
            "ecrã principal",
            "volta para o inicio",
            "volta para o início",
            "volta ao inicio",
            "volta ao início",
            "limpa o ecra",
            "limpa o ecrã",
            "clean",
            "clean hud",
            "ja nao preciso de nada",
            "já não preciso de nada",
            "modo clean",
            "oculta a dashboard",
            "fecha a dashboard",
            "minimiza a dashboard",
            "ocultar dashboard",
            "fechar dashboard",
            "voltar ao ecrã principal",
            "voltar ao ecra principal",
            "voltar ao início",
            "voltar ao inicio",
            "volta ao menu principal",
            "voltar ao menu principal",
            "ja nao preciso de ajuda",
            "já não preciso de ajuda",
        )
        if clean_prompt in main_keywords or any(
            fragment in clean_prompt
            for fragment in (
                "volta ao ecra principal",
                "volta ao ecrã principal",
                "volta para o inicio",
                "volta para o início",
                "ja nao preciso de nada",
                "já não preciso de nada",
                "modo clean",
            )
        ):
            await self.connections.broadcast(
                {"type": "ui", "action": "show_main_screen"}
            )
            await self.callbacks.broadcast_state("idle")
            await self._broadcast_orchestrator(
                "Voltando ao ecrã principal e ativando o "
                "modo clean, Sir."
            )
            return True
        return False

    async def _open_local_app(self, app_request: dict) -> None:
        ok, details = await self.callbacks.open_local_application(
            app_request
        )
        await self.callbacks.broadcast_state("idle")
        if ok:
            log_event(
                self.logger,
                "local_app.opened",
                app=app_request["id"],
            )
            content = f"Abri o {app_request['label']}."
        else:
            log_event(
                self.logger,
                "local_app.open_error",
                level="error",
                app=app_request["id"],
                error=details,
            )
            content = (
                f"Tentei abrir o {app_request['label']}, mas "
                f"o Windows devolveu erro: {details}"
            )
        await self._broadcast_orchestrator(content)

    async def _run_project_builder_if_requested(
        self,
        prompt: str,
    ) -> bool:
        from agents.orchestrator.project_builder import (
            ProjectBuilderError,
            build_project,
            is_project_creation_request,
        )

        if not is_project_creation_request(prompt):
            return False
        await self.connections.broadcast(
            {
                "type": "project_output",
                "content": (
                    "[ProjectBuilder] A gerar plano JSON e "
                    "criar projeto isolado...\n"
                ),
            }
        )

        def on_project_log(content: str) -> None:
            self.callbacks.run_in_main_loop(
                self.connections.broadcast(
                    {
                        "type": "project_output",
                        "content": content,
                    }
                )
            )

        try:
            result = await build_project(
                prompt,
                on_file=self.callbacks.on_file_update,
                on_log=on_project_log,
            )
            report = result.report()
            self._append_history("assistant", report)
            await self.connections.broadcast(
                {
                    "type": "project_output",
                    "content": report + "\n",
                }
            )
            await self.connections.broadcast(
                {
                    "type": "project_status",
                    "running": result.preview_started,
                    "preview_url": result.preview_url or None,
                }
            )
            project_id = os.path.basename(result.project_dir)
            payload = await asyncio.to_thread(
                self.services.project_context.project_payload,
                project_id,
                True,
            )
            await self.connections.broadcast(
                {
                    "type": "projects_list",
                    "projects": (
                        self.services.project_context.list_projects()
                    ),
                }
            )
            await self.connections.broadcast(
                {"type": "project_context", **payload}
            )
            await self.connections.broadcast(
                {
                    "type": "chat",
                    "sender": "JARVIS",
                    "role": "Project Builder",
                    "content": report,
                }
            )
            await self.callbacks.broadcast_state("idle")
            await self.connections.broadcast(
                {"type": "complete", "result": report}
            )
        except ProjectBuilderError as project_error:
            report = f"Project Builder falhou: {project_error}"
            self._append_history("assistant", report)
            await self.connections.broadcast(
                {
                    "type": "chat",
                    "sender": "JARVIS",
                    "role": "Project Builder",
                    "content": report,
                }
            )
            await self.connections.broadcast(
                {
                    "type": "project_output",
                    "content": report + "\n",
                }
            )
            await self.callbacks.broadcast_state("idle")
            await self.connections.broadcast(
                {"type": "complete", "result": report}
            )
        return True

    async def _run_agent_orchestration(
        self,
        prompt: str,
        session_id: int,
    ) -> None:
        async def on_template_change(name: str) -> None:
            normalized = normalize_template_name(name)
            self.services.agents.active_template_name = normalized
            await self.connections.broadcast(
                self.callbacks.build_template_payload(normalized)
            )

        template_name = getattr(
            self.services.agents,
            "active_template_name",
            "builder_swarm",
        )
        clean_prompt = prompt.lower().strip(" .?!,")
        coding_keywords = [
            "criar website",
            "criar site",
            "criar landing page",
            "desenvolver app",
            "desenvolver website",
            "programar",
            "cria um site",
            "cria uma app",
            "cria um jogo",
            "code a",
            "build a website",
            "write code",
            "escrever código",
            "criar api",
            "criar base de dados",
        ]
        research_keywords = [
            "pesquisa",
            "procura",
            "vaga",
            "vagas",
            "emprego",
            "analisa",
            "lê o",
            "ler o",
            "resume",
            "sugestões",
            "melhorar",
            "cv",
            "currículo",
            "curriculo",
            "informação",
            "investiga",
            "sugere",
            "explica",
            "dá ideias",
            "ideias para",
        ]
        if (
            any(
                keyword in clean_prompt
                for keyword in research_keywords
            )
            and not any(
                keyword in clean_prompt
                for keyword in coding_keywords
            )
            and template_name != "research_swarm"
        ):
            template_name = "research_swarm"
            self.services.agents.active_template_name = template_name
            await on_template_change(template_name)
        result = await self.services.agents.run_jarvis_orchestration(
            prompt,
            session_id,
            self.callbacks.on_agent_message,
            self.callbacks.on_file_update,
            self.callbacks.on_kanban_update,
            history=self.conversation_history,
            template_name=template_name,
            on_template_change=on_template_change,
        )
        self._append_history("assistant", result)
        self._persist_legacy_sandbox_project(
            session_id,
            prompt,
        )
        await self.callbacks.broadcast_state("idle")
        if is_orchestration_result_error(result):
            message = (
                "Orquestração terminou com erro/aviso. "
                "Ver detalhes na mensagem final."
            )
        else:
            message = (
                "Orquestração concluída com sucesso!"
            )
        await self.connections.broadcast(
            {"type": "system", "content": message}
        )
        await self.connections.broadcast(
            {"type": "complete", "result": result}
        )
        if result and not is_orchestration_result_error(result):
            if result.startswith("[OK]") or "[OK]" in result:
                clean_reply = f"Concluí a orquestração do pedido '{prompt}'. Todos os passos e verificações de qualidade foram validados com sucesso."
            else:
                clean_reply = result
            if not getattr(self, "_suppress_chat_broadcast", False):
                await self.connections.broadcast({
                    "type": "chat",
                    "sender": "JARVIS",
                    "role": "Assistant",
                    "content": clean_reply,
                })
        return result

    def _persist_legacy_sandbox_project(
        self,
        session_id: int,
        prompt: str,
    ) -> None:
        try:
            root = self.services.sandbox.SANDBOX_DIR
            contents = []
            for filename in (
                "index.html",
                "styles.css",
                "app.js",
            ):
                path = os.path.join(root, filename)
                if os.path.exists(path):
                    with open(
                        path,
                        "r",
                        encoding="utf-8",
                    ) as source_file:
                        contents.append(source_file.read())
                else:
                    contents.append("")
            if any(contents):
                self.services.database.save_project(
                    session_id,
                    "Projeto Gerado",
                    prompt,
                    *contents,
                )
        except Exception as persistence_error:
            log_event(
                self.logger,
                "project.persist_error",
                level="error",
                error=str(persistence_error),
            )

    async def _broadcast_orchestrator(
        self,
        content: str,
    ) -> None:
        await self.connections.broadcast(
            {
                "type": "chat",
                "sender": "JARVIS",
                "role": "Orquestrador",
                "content": content,
            }
        )

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
