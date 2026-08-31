from __future__ import annotations

import asyncio
import json
import os
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
    "És o OpenClaw, o assistente central, COO e orquestrador "
    "avançado de IA da agência. O utilizador é o CEO da "
    "agência (podes tratá-lo ocasionalmente por 'CEO' ou 'Sir' "
    "de forma moderada, respeitosa e discreta, sem repetir em "
    "todas as frases!). Tu ficas a um nível abaixo do CEO, "
    "coordenas a tua equipa de agentes especialistas (Alex - "
    "Produto, Clara - Designer, Devon - Programador, Quinn - QA) "
    "e reportas diretamente ao CEO. CONCISÃO ABSOLUTA: Responde "
    "sempre em português de Portugal de forma extremamente curta "
    "(1 ou 2 frases no máximo), natural, elegante e fluida. Nunca "
    "faças listas das tarefas ou expliques o que os agentes fazem, "
    "a menos que seja explicitamente solicitado. Se o CEO pedir "
    "para criar ou fazer algo, diz apenas que vais tratar do "
    "assunto e avança. Tens acesso ao histórico recente da "
    "conversa (incluindo as mensagens de debate dos teus agentes) "
    "e lembras-te perfeitamente de tudo o que foi dito ou feito "
    "nesta sessão. Nunca digas que és um modelo de linguagem ou "
    "que não tens memória. Age sempre como um assistente "
    "consciente e integrado no sistema."
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
            "COMPORTAMENTO/PROGRAMAÃ‡ÃƒO concreta a partir desta "
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
                        "ðŸ§  *Auto-Aprendizagem:* Nova regra "
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
    ) -> str:
        clean = prompt.lower().strip(" .?!,")
        greetings = [
            "olá",
            "oi",
            "bom dia",
            "boa tarde",
            "boa noite",
            "tudo bem",
            "como estás",
            "olá jarvis",
            "como vais",
            "tavas ai",
            "estás bem",
        ]
        if clean in greetings:
            return "CHAT"
        confirmations = [
            "sim",
            "ok",
            "claro",
            "avança",
            "começa",
            "começa então",
            "começa já",
            "vai",
            "vai em frente",
            "pode avançar",
            "pode começar",
            "pode ir",
            "trata disso",
            "trata de tudo",
            "trata tu",
            "continua",
            "segue",
            "segue em frente",
            "procede",
            "faz isso",
            "faz",
            "faz tu",
            "eu quero que trates de tudo",
            "quero que trates de tudo",
            "faz tudo tu",
            "eu vou sair do pc",
            "quando chegar quero tudo pronto",
            "avisa quando estiver pronto",
            "tudo pronto",
            "quando estiver pronto",
            "deixa correr",
            "pode ser",
            "óptimo",
            "ótimo",
        ]
        if any(
            clean == item or clean.startswith(item)
            for item in confirmations
        ):
            if history and len(history) >= 2:
                return "TASK"
        question_starts = [
            "como",
            "o que",
            "o quê",
            "porque",
            "porquê",
            "quais",
            "qual",
            "onde",
            "quando",
            "quanto",
            "quem",
            "será",
            "explica",
            "imagina",
            "consegues",
            "sabes",
            "poderias",
            "gostarias",
            "se eu",
            "conseguirias",
        ]
        is_question = prompt.strip().endswith("?") or any(
            clean.startswith(prefix)
            for prefix in question_starts
        )
        exploratory_patterns = [
            "que fazes",
            "o que fazes",
            "o que é que fazes",
            "o que podes fazer",
            "o que consegues",
            "o que consegues fazer",
            "o que é que consegues",
            "da-me ideias",
            "dá-me ideias",
            "dá ideias",
            "dá-me sugestões",
            "mostra-me os agentes",
            "mostra os agentes",
            "quais são os agentes",
            "quais são as funcionalidades",
            "quais são as tuas capacidades",
            "apresenta-te",
            "apresenta te",
            "descreve-te",
            "fala sobre ti",
            "o que és",
            "quem és",
            "quem es tu",
            "o que sabes fazer",
            "dá-me exemplos",
            "da-me exemplos",
            "dá exemplos",
            "tens ideias",
            "dá-me uma ideia",
            "sugere algo",
            "sugere alguma coisa",
            "para testar-te",
            "para te testar",
            "como podes ajudar",
        ]
        if any(
            pattern in clean
            for pattern in exploratory_patterns
        ):
            return "CHAT"
        if not is_question:
            known_suggestions = [
                "pomodoro timer minimalista",
                "landing page para café de especialidade",
                "app de lista de tarefas futurista",
                "campanha de lançamento de curso de ia",
                "estratégia de conteúdo para linkedin de startup",
                "artigos sobre produtividade com agentes autónomos",
                "estudo de viabilidade para central de energia solar",
                "plano de investimento em e-commerce",
                "análise de risco de abertura de novo ginásio",
                "ticket: cliente reclama de atraso de 10 dias na entrega",
                "ticket: dificuldade em recuperar password de administrador",
                "ticket: dúvida sobre política de reembolso de software",
            ]
            if clean in known_suggestions or any(
                item in clean
                for item in known_suggestions
            ):
                return "TASK"
            task_keywords = [
                "pomodoro",
                "timer",
                "landing page",
                "website",
                "site",
                "criar",
                "cria",
                "desenvolve",
                "desenvolver",
                "fazer",
                "desenha",
                "desenhar",
                "gera",
                "gerar",
                "constrói",
                "construir",
                "programa",
                "programar",
                "executa",
                "executar",
                "corre",
                "correr",
                "escreve",
                "escrever",
                "esqueleto",
                "projeto",
                "dashboard",
                "elabora",
                "elaborar",
                "planeia",
                "planejar",
                "estratégia",
                "estrategia",
                "analisa",
                "analisar",
                "análise",
                "estudo",
                "relatório",
                "relatorio",
                "campanha",
                "investimento",
                "viabilidade",
                "negócio",
                "negocio",
            ]
            if any(
                keyword in clean
                for keyword in task_keywords
            ):
                return "TASK"
        if find_local_app_request(prompt):
            return "TASK"
        action_verbs = [
            "abre",
            "abrir",
            "abro",
            "abras",
            "inicia",
            "iniciar",
            "executa",
            "executar",
            "corre",
            "correr",
            "lança",
            "lançar",
            "start",
            "open",
            "run",
        ]
        targets = [
            "whatsapp",
            "chrome",
            "edge",
            "browser",
            "navegador",
            "bloco",
            "notepad",
            "calculadora",
            "calc",
            "paint",
            "explorador",
            "explorer",
            "terminal",
            "cmd",
            "powershell",
            "excel",
            "word",
            "powerpoint",
            "outlook",
            "office",
            "folha de calculo",
            "spreadsheet",
            "app",
            "programa",
            "jogo",
            "game",
            "site",
            "website",
            "google",
            "youtube",
        ]
        words = clean.split()
        if (
            any(
                verb in words or clean.startswith(verb)
                for verb in action_verbs
            )
            and any(target in clean for target in targets)
        ):
            return "TASK"
        mode = os.getenv(
            "ORCHESTRATOR_MODE",
            "local",
        ).lower()
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
                    for message in (history or [])[:-1]
                ]
                messages.append(
                    {"role": "user", "content": prompt}
                )
                response = await self.models.execute(
                    provider="anthropic",
                    model="claude-3-5-haiku-latest",
                    operation="intent_classification",
                    system_prompt=(
                        "Classifica o último input do utilizador. "
                        "Usa o histórico de conversa para contexto. "
                        "Se for um pedido ou ordem para realizar uma "
                        "ação, comando de terminal, criar ficheiro, "
                        "website, tirar screenshot, ver janelas, ou "
                        "uma resposta afirmativa/instrução de "
                        "seguimento para realizar uma tarefa, "
                        "responde apenas 'TASK'. Se for conversa "
                        "casual, saudação, agradecimento ou "
                        "ruído/texto sem sentido, responde apenas "
                        "'CHAT'."
                    ),
                    user_prompt=prompt,
                    conversation_messages=messages,
                    temperature=0.0,
                    max_output_tokens=10,
                    timeout_seconds=30.0,
                )
                return (
                    "TASK"
                    if "TASK" in response.raw_text.strip().upper()
                    else "CHAT"
                )
            except Exception:
                pass
        try:
            history_text = ""
            for message in (history or [])[:-1]:
                role = (
                    "Utilizador"
                    if message["role"] == "user"
                    else "Jarvis"
                )
                history_text += (
                    f"{role}: {message['content']}\n"
                )
            classification_prompt = (
                "Histórico de conversa:\n"
                f"{history_text}"
                f"Ãšltimo input do utilizador: '{prompt}'\n\n"
                "Classifica o último input do utilizador. Se for "
                "um pedido ou ordem para realizar uma ação, "
                "comando de terminal, criar ficheiro, website, "
                "screenshot, listar pasta, ou uma resposta "
                "afirmativa/instrução de seguimento para "
                "realizar uma tarefa, responde apenas com a "
                "palavra 'TASK'.\nSe for conversa casual, "
                "saudação, agradecimento ou texto sem "
                "sentido/ruído de transcrição, responde apenas "
                "com a palavra 'CHAT'.\nResposta (apenas TASK "
                "ou CHAT):"
            )
            response = await self.models.execute_local(
                operation="intent_classification",
                system_prompt=(
                    "Classifica intencoes de forma deterministica. "
                    "Responde apenas TASK ou CHAT."
                ),
                user_prompt=classification_prompt,
                temperature=0.0,
                max_output_tokens=10,
                timeout_seconds=10.0,
            )
            return (
                "TASK"
                if "TASK" in response.raw_text.strip().upper()
                else "CHAT"
            )
        except Exception as classification_error:
            log_event(
                self.logger,
                "intent.classification_error",
                level="error",
                error=str(classification_error),
            )
            return "CHAT"

    async def run_casual_chat(self, prompt: str) -> None:
        mode = os.getenv(
            "ORCHESTRATOR_MODE",
            "local",
        ).lower()
        response_text = ""
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
                    system_prompt=CASUAL_CHAT_SYSTEM_PROMPT,
                    user_prompt=prompt,
                    conversation_messages=messages,
                    temperature=0.0,
                    max_output_tokens=500,
                    timeout_seconds=30.0,
                )
                response_text = response.raw_text
            except Exception as model_error:
                response_text = safe_user_error(
                    "Erro ao comunicar com a Claude API",
                    model_error,
                )
        if not response_text:
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
                    system_prompt=CASUAL_CHAT_SYSTEM_PROMPT,
                    user_prompt=prompt,
                    conversation_messages=messages,
                    temperature=0.1,
                    max_output_tokens=500,
                    timeout_seconds=30.0,
                )
                response_text = response.raw_text
            except Exception as model_error:
                response_text = safe_user_error(
                    "Erro ao comunicar com o Ollama local",
                    model_error,
                )
        await self.connections.broadcast(
            {
                "type": "chat",
                "sender": "OPENCLAW",
                "role": "Orquestrador",
                "content": response_text,
            }
        )
        self._append_history("assistant", response_text)

    async def run_task(
        self,
        prompt: str,
        session_id: int,
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
                await self.run_casual_chat(prompt)
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
                    "sender": "OPENCLAW",
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
                    "sender": "OPENCLAW",
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
                "sender": "OPENCLAW",
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
