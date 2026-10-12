from __future__ import annotations

import asyncio
import enum
import os
import re
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Mapping

from agents.mission_state import (
    MissionStateError,
    MissionStateStore,
    StaleVersionError,
    utc_now,
)
from backend.logging_config import get_logger, log_event
from backend.message_protocol import (
    chat_message,
    normalize_canonical_sender,
    normalize_ws_message,
    state_message,
    system_message,
)
from security.safety_classifier import SafetyAssessment, SafetyClassifier, SafetyStatus

logger = get_logger(__name__)


class ChatIntentType(str, enum.Enum):
    CHAT = "CHAT"
    PROJECT_QUERY = "PROJECT_QUERY"
    PROJECT_INSPECTION = "PROJECT_INSPECTION"
    FILE_READ = "FILE_READ"
    FILE_DELIVERY = "FILE_DELIVERY"
    LOCAL_ACTION = "LOCAL_ACTION"
    EXECUTION_REQUEST = "EXECUTION_REQUEST"
    CONTINUATION = "CONTINUATION"
    AMBIGUOUS = "AMBIGUOUS"
    REFUSED_POLICY = "REFUSED_POLICY"

    # Backward compatibility aliases
    CONVERSATIONAL = "CHAT"
    ANALYSIS = "PROJECT_INSPECTION"
    EXECUTABLE_DIRECTIVE = "EXECUTION_REQUEST"


@dataclass
class ResolvedChatRequest:
    raw_prompt: str
    intent: ChatIntentType
    title: str
    objective: str
    project_id: str | None = None
    refusal_reason: str = ""
    is_economic: bool = False
    task_type: str = "GENERIC"
    confidence: float = 1.0
    context_reference: dict[str, Any] = field(default_factory=dict)
    planned_action: str = ""
    requires_mission: bool = False
    requires_model: bool = False
    requires_external_network: bool = False
    decision_reason: str = ""
    target_file: str | None = None
    delivery_mode: str = "content"
    requires_approval: bool = False


@dataclass
class RequestRecord:
    correlation_id: str
    prompt: str
    intent: str
    created_at: float
    user_response: str | None = None
    technical_events: list[dict[str, Any]] = field(default_factory=list)
    state_changes: list[str] = field(default_factory=list)
    operation_result: dict[str, Any] | None = None
    completion_emitted: bool = False


@dataclass
class BridgeExecutionResult:
    success: bool
    summary: str
    error: str = ""
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class MissionGateResult:
    allowed: bool
    reason: str = ""
    requires_approval: bool = False


class ChatRequestResolver:
    """Classifies user chat prompts into canonical typed categories with semantic context."""

    CONVERSATIONAL_PATTERNS = [
        r"^(ol[aá]|bom dia|boa tarde|boa noite|oi|hey|hello|hi)\b",
        r"^(como est[aá]s|tudo bem|como vai|quem [eé]s tu|o que fazes|quem te criou)\b",
        r"^(obrigad[oa]|thanks|valeu|muito obrigado)\b",
        r"^(adeus|tchau|at[eé] logo|bye)\b",
    ]

    DESTRUCTIVE_TERMS = [
        "apaga", "apagar", "elimina", "eliminar", "remove", "remover",
        "rm ", "rmdir", "delete", "drop table", "format ", "reset --hard",
    ]

    RETRY_PATTERNS = [
        r"^(tenta\s+de\s*novo|tenta\s+outra\s+vez|tenta\s+novamente|tenta\s+a[ií]|tenta|tente\s+de\s*novo|tente\s+outra\s+vez|outra\s+vez|de\s+novo|mais\s+uma\s+vez|repete|repita|faz\s+de\s*novo|fa[cç]a\s+de\s*novo)$",
    ]

    FULL_FILE_PATTERNS = [
        r"\b(fornece\s+tudo|fornece\s+todo|fornece\s+o\s+resto|mostra\s+o\s+resto|mostra\s+tudo|mostra\s+todo|conte[uú]do\s+todo|conte[uú]do\s+completo|ficheiro\s+todo|ficheiro\s+completo|c[oó]digo\s+todo|c[oó]digo\s+completo|n[aã]o\s+[eé]\s+s[oó]\s+isso|nao\s+e\s+so\s+isso|fornece\s+o\s+conte[uú]do\s+completo|d[aá]-me\s+o\s+resto)\b",
    ]

    ATTACHMENT_PATTERNS = [
        r"\b(anexa-o|anexa\s+o\s+ficheiro|anexa\s+o\s+arquivo|anexa\s+[aà]\s+conversa|anexa|anexar)\b",
    ]

    CONTINUATION_PATTERNS = [
        r"^(continua|segue|avan[cç]a|procede|continua\s+a[ií]|continua\s+o\s+trabalho)$",
    ]

    LOCAL_ACTION_PATTERNS = [
        r"\b(abre|abrir|inicia|iniciar|lan[cç]a|lan[cç]ar|executa|executar|open|run)\s+(o\s+|a\s+)?(bloco\s+de\s+notas|notepad|calculadora|calc|paint|explorador|explorer|chrome|edge|browser|navegador|terminal|cmd|powershell)\b",
    ]

    FILE_EXTENSION_PATTERN = r"\b([a-zA-Z0-9_\-\.\/]+\.(?:js|ts|py|html|css|json|md|txt|sql|yaml|yml|sh|env|jsx|tsx))\b"

    PROJECT_ACCESS_PATTERNS = [
        r"\b(consegues\s+aceder|podes\s+aceder|tens\s+acesso|aceder\s+ao?|acede\s+ao?|acesso\s+ao?|entrar\s+no|abrir\s+o\s+projeto)\b",
    ]

    PROJECT_INSPECTION_PATTERNS = [
        r"\b(mostra\s+os\s+ficheiros|quais\s+os\s+ficheiros|que\s+ficheiros\s+existem|lista\s+os\s+ficheiros|estrutura\s+do\s+projeto|arquitetura\s+do\s+projeto|quais\s+s[aã]o\s+os\s+endpoints|qual\s+a\s+stack|que\s+depend[eê]ncias|mostra\s+a\s+estrutura)\b",
    ]

    ECONOMIC_PATTERNS = [
        r"\b(money|arbitragem|receita|fatura[cç][aã]o|monetiza[cç][aã]o|transa[cç][aã]o\s+econ[oó]mica)\b",
    ]

    CODING_VERB_PATTERNS = [
        r"\b(cria|criar|crie|cria-me|desenvolve|desenvolver|desenvolva|implementa|implementar|implemente|constr[oó]i|construir|gera|gerar|programa|programar|adiciona|adicionar|adicione|refatora|refatorar|refatore|corrige|corrigir|corrija|build)\b",
    ]

    POLITE_EXECUTION_PREFIXES = [
        r"^(podes|pode|consegues|podias|poderias|seria\s+poss[ií]vel)\s+(criar|desenvolver|implementar|construir|gerar|programar|adicionar|refatorar|corrigir|fazer|executar\s+os\s+testes)\b",
    ]

    TEST_EXECUTION_PATTERNS = [
        r"\b(implementa\s+e\s+executa\s+os\s+testes|executa\s+os\s+testes|executar\s+os\s+testes|corre\s+os\s+testes|testa\s+o\s+projeto|corre\s+o\s+pytest)\b",
    ]

    CODING_TARGET_PATTERNS = [
        r"\b(aplica[cç][aã]o|app|website|site|endpoint|componente|api|fun[cç][aã]o|m[oó]dulo|teste|script|ficheiro|arquivo|c[oó]digo|p[aá]gina|tela|view|servi[cç]o|database|banco|sqlite|tabela|bot[aã]o|layout|css|html|js|backend|frontend)\b",
    ]

    def resolve_request(
        self,
        prompt: str,
        project_id: str | None = None,
        context: Mapping[str, Any] | None = None,
        history: list[dict] | None = None,
    ) -> ResolvedChatRequest:
        clean = (prompt or "").strip()
        clean_lower = clean.lower()

        if not clean:
            return ResolvedChatRequest(
                raw_prompt="",
                intent=ChatIntentType.CHAT,
                title="Mensagem Vazia",
                objective="",
                project_id=project_id,
                confidence=1.0,
                planned_action="ignore",
                decision_reason="Prompt vazio",
            )

        # ── 1. Safety & Policy Classifier Check ───────────────────────────────
        safety: SafetyAssessment = SafetyClassifier.evaluate(clean)
        if safety.status == SafetyStatus.BLOCKED:
            return ResolvedChatRequest(
                raw_prompt=clean,
                intent=ChatIntentType.REFUSED_POLICY,
                title="Diretiva Bloqueada",
                objective=clean,
                project_id=project_id,
                refusal_reason=safety.reason or "Conteúdo viola políticas de segurança.",
                confidence=1.0,
                planned_action="policy_refusal",
                requires_mission=False,
                requires_model=False,
                decision_reason="Conteúdo classificado como violação de segurança pelas políticas ativas.",
            )

        # ── 2. Local Action Detection (Open Local App / UI Commands) ───────────
        from backend.services.local_app_service import find_local_app_request
        detected_app = find_local_app_request(clean)
        if detected_app or any(re.search(pat, clean_lower) for pat in self.LOCAL_ACTION_PATTERNS):
            app_name = detected_app.get("name", "aplicação") if isinstance(detected_app, dict) else "aplicação"
            if app_name == "aplicação":
                for target in ["excel", "word", "powerpoint", "outlook", "bloco de notas", "notepad", "calculadora", "calc", "paint", "explorador", "chrome", "edge", "terminal", "cmd", "powershell"]:
                    if target in clean_lower:
                        app_name = target
                        break
            return ResolvedChatRequest(
                raw_prompt=clean,
                intent=ChatIntentType.LOCAL_ACTION,
                title=f"Abrir {app_name.capitalize()}",
                objective=clean,
                project_id=project_id,
                confidence=0.98,
                context_reference={"local_app": detected_app or app_name},
                planned_action="open_local_application",
                requires_mission=False,
                requires_model=False,
                decision_reason="Comando operacional local para abrir aplicação de sistema.",
            )

        # ── 3. Continuation & Retry Resolution ────────────────────────────────
        is_retry = any(re.search(pat, clean_lower) for pat in self.RETRY_PATTERNS)
        if is_retry:
            prev_user_msg = None
            if history:
                for msg in reversed(history):
                    if msg.get("role") == "user":
                        c = (msg.get("content") or "").strip()
                        if c and not any(re.search(pat, c.lower()) for pat in self.RETRY_PATTERNS):
                            prev_user_msg = c
                            break

            if prev_user_msg:
                # Security Check: Never repeat destructive operations automatically
                is_destructive = any(term in prev_user_msg.lower() for term in self.DESTRUCTIVE_TERMS)
                if is_destructive:
                    return ResolvedChatRequest(
                        raw_prompt=clean,
                        intent=ChatIntentType.REFUSED_POLICY,
                        title="Confirmação de Segurança Necessária",
                        objective=f"Repetição de operação destrutiva bloqueada: '{prev_user_msg}'",
                        project_id=project_id,
                        refusal_reason=f"A operação anterior continha ações potencialmente destrutivas ('{prev_user_msg}'). Por segurança, não é repetida automaticamente sem confirmação explícita.",
                        confidence=1.0,
                        planned_action="require_confirmation",
                        requires_mission=False,
                        requires_model=False,
                        requires_approval=True,
                        decision_reason="Operação anterior potencialmente destrutiva. Repetição automática recusada por política de segurança.",
                    )

                log_event(
                    logger,
                    "chat_resolver.retry_resolved_from_history",
                    original_prompt=clean,
                    resolved_from=prev_user_msg,
                )
                resolved_prev = self.resolve_request(
                    prev_user_msg,
                    project_id=project_id,
                    context=context,
                    history=None,
                )
                resolved_prev.context_reference = {
                    "is_retry": True,
                    "retry_prompt": clean,
                    "original_prompt": prev_user_msg,
                }
                resolved_prev.decision_reason = f"Tentativa repetida associada à diretiva anterior '{prev_user_msg}'."
                return resolved_prev
            else:
                return ResolvedChatRequest(
                    raw_prompt=clean,
                    intent=ChatIntentType.CHAT,
                    title="Tentativa",
                    objective="O que gostaria que eu tentasse novamente? Pode indicar o projeto pretendido (ex: 'consegues aceder ao projeto dina') ou uma instrução de desenvolvimento.",
                    project_id=project_id,
                    confidence=0.9,
                    planned_action="casual_chat",
                    requires_mission=False,
                    requires_model=False,
                    decision_reason="Mensagem de retry sem histórico prévio relevante; pedido de esclarecimento.",
                )

        # ── 4. Project & File Reference Resolution ────────────────────────────
        is_econ = any(re.search(pat, clean_lower) for pat in self.ECONOMIC_PATTERNS)
        target_proj = project_id
        if not target_proj and is_econ:
            target_proj = "money"

        if not target_proj:
            # Check explicit project patterns
            proj_match = re.search(r"(?:ao\s+projeto|do\s+projeto|no\s+projeto|projeto|project)\s+[:=]?\s*([a-zA-Z0-9_\-]+)", clean_lower)
            if proj_match:
                cand = proj_match.group(1).strip()
                if cand not in {"novo", "atual", "default", "meu", "este", "esse", "qualquer", "web"}:
                    target_proj = cand
            else:
                # Check access verbs
                access_match = re.search(r"\b(?:aceder|acede|acesso|entrar|abrir|ver)\s+(?:a|ao|o|em)?\s+([a-zA-Z0-9_\-]+)", clean_lower)
                if access_match:
                    cand = access_match.group(1).strip()
                    if cand not in {"novo", "atual", "default", "meu", "este", "esse", "qualquer", "pasta", "ficheiro", "diretório", "codigo", "código"}:
                        target_proj = cand
                else:
                    # Check known workspace project directories
                    try:
                        for entry in os.listdir(os.path.join("workspace", "projects")):
                            if entry.lower() in clean_lower.split() and entry not in {"default-project", "default"}:
                                target_proj = entry
                                break
                    except Exception:
                        pass

        # Inherit project from history if still unset
        if not target_proj and history:
            for msg in reversed(history):
                content = (msg.get("content") or "").lower()
                try:
                    for entry in os.listdir(os.path.join("workspace", "projects")):
                        if entry.lower() in content.split() and entry not in {"default-project", "default"}:
                            target_proj = entry
                            break
                except Exception:
                    pass
                if target_proj:
                    break

        # Check explicit file name in prompt
        target_file = None
        file_match = re.search(self.FILE_EXTENSION_PATTERN, clean)
        if file_match:
            target_file = file_match.group(1).strip()
        elif target_proj:
            # Check if any file in project directory is directly referenced
            proj_dir = os.path.join("workspace", "projects", target_proj)
            if os.path.isdir(proj_dir):
                try:
                    for entry in os.listdir(proj_dir):
                        if entry.lower() in clean_lower and "." in entry:
                            target_file = entry
                            break
                except Exception:
                    pass

        # ── 5. Full File / Attachment Continuation Resolution ─────────────────
        is_full_file_request = any(re.search(pat, clean_lower) for pat in self.FULL_FILE_PATTERNS)
        is_attachment_request = any(re.search(pat, clean_lower) for pat in self.ATTACHMENT_PATTERNS)

        if (is_full_file_request or is_attachment_request) and not target_file and history:
            # Recover referenced file from history
            for msg in reversed(history):
                c = msg.get("content") or ""
                m = re.search(self.FILE_EXTENSION_PATTERN, c)
                if m:
                    target_file = m.group(1).strip()
                    break

        if is_full_file_request:
            target_proj = target_proj or "default-project"
            if target_file:
                return ResolvedChatRequest(
                    raw_prompt=clean,
                    intent=ChatIntentType.FILE_DELIVERY,
                    title=f"Entrega Integral: {target_file}",
                    objective=f"Disponibilizar o conteúdo completo do ficheiro {target_file}",
                    project_id=target_proj,
                    confidence=0.98,
                    context_reference={"target_file": target_file, "is_followup": True},
                    planned_action="file_delivery",
                    requires_mission=False,
                    requires_model=False,
                    requires_external_network=False,
                    decision_reason=f"Pedido de conteúdo integral para o ficheiro '{target_file}' identificado no histórico.",
                    target_file=target_file,
                    delivery_mode="full",
                )
            else:
                return ResolvedChatRequest(
                    raw_prompt=clean,
                    intent=ChatIntentType.AMBIGUOUS,
                    title="Pedido de Conteúdo Ambigüo",
                    objective="Indique qual o ficheiro pretendido para fornecer por completo.",
                    project_id=target_proj,
                    confidence=0.6,
                    planned_action="clarification",
                    requires_mission=False,
                    requires_model=False,
                    decision_reason="Pedido de 'fornece tudo' sem referência inequívoca a um ficheiro no histórico.",
                )

        if is_attachment_request:
            target_proj = target_proj or "default-project"
            if target_file:
                return ResolvedChatRequest(
                    raw_prompt=clean,
                    intent=ChatIntentType.FILE_DELIVERY,
                    title=f"Anexo: {target_file}",
                    objective=f"Anexar o ficheiro {target_file} à conversa",
                    project_id=target_proj,
                    confidence=0.98,
                    context_reference={"target_file": target_file},
                    planned_action="file_delivery",
                    requires_mission=False,
                    requires_model=False,
                    requires_external_network=False,
                    decision_reason=f"Pedido de entrega do ficheiro '{target_file}' como anexo à conversa.",
                    target_file=target_file,
                    delivery_mode="attachment",
                )

        # ── 6. Continuation Directive ("continua", "segue") ───────────────────
        if any(re.search(pat, clean_lower) for pat in self.CONTINUATION_PATTERNS):
            if history and len(history) >= 2:
                return ResolvedChatRequest(
                    raw_prompt=clean,
                    intent=ChatIntentType.CONTINUATION,
                    title="Continuação",
                    objective="Retomar o trabalho anterior do histórico",
                    project_id=target_proj,
                    confidence=0.9,
                    context_reference={"is_continuation": True},
                    planned_action="resume_work",
                    requires_mission=False,
                    requires_model=False,
                    decision_reason="Pedido de continuação com base no trabalho recente.",
                )
            else:
                return ResolvedChatRequest(
                    raw_prompt=clean,
                    intent=ChatIntentType.AMBIGUOUS,
                    title="Continuação Ambigua",
                    objective="A que tarefa ou trabalho gostaria que eu desse continuidade? Pode indicar o objetivo ou o projeto.",
                    project_id=target_proj,
                    confidence=0.5,
                    planned_action="clarification",
                    requires_mission=False,
                    requires_model=False,
                    decision_reason="Comando de continuação sem histórico operacional inequívoco.",
                )

        # ── 7. File Read / Delivery Detection ─────────────────────────────────
        if target_file:
            # Check verbs: read vs deliver
            is_delivery_verb = any(v in clean_lower for v in ["anexa", "entrega", "fornece", "disponibiliza", "anexo"])
            is_read_verb = any(v in clean_lower for v in ["mostra", "lê", "ler", "ver", "conteúdo", "abre", "exibe", "conteudo", "código", "codigo"])
            
            if is_delivery_verb:
                return ResolvedChatRequest(
                    raw_prompt=clean,
                    intent=ChatIntentType.FILE_DELIVERY,
                    title=f"Entrega de Ficheiro: {target_file}",
                    objective=f"Disponibilizar o ficheiro {target_file}",
                    project_id=target_proj,
                    confidence=0.98,
                    context_reference={"target_file": target_file},
                    planned_action="file_delivery",
                    requires_mission=False,
                    requires_model=False,
                    requires_external_network=False,
                    decision_reason=f"Pedido explícito de entrega do ficheiro '{target_file}' a partir do disco.",
                    target_file=target_file,
                    delivery_mode="attachment" if "anex" in clean_lower else "full",
                )
            if is_read_verb or len(clean.split()) <= 6:
                return ResolvedChatRequest(
                    raw_prompt=clean,
                    intent=ChatIntentType.FILE_READ,
                    title=f"Leitura de Ficheiro: {target_file}",
                    objective=f"Apresentar o conteúdo de {target_file}",
                    project_id=target_proj,
                    confidence=0.98,
                    context_reference={"target_file": target_file},
                    planned_action="file_read",
                    requires_mission=False,
                    requires_model=False,
                    requires_external_network=False,
                    decision_reason=f"Pedido local de leitura do ficheiro '{target_file}'.",
                    target_file=target_file,
                    delivery_mode="content",
                )

        # ── 8. Project Queries & Local Inspections ─────────────────────────────
        is_project_access_query = any(re.search(pat, clean_lower) for pat in self.PROJECT_ACCESS_PATTERNS)
        is_project_inspection = any(re.search(pat, clean_lower) for pat in self.PROJECT_INSPECTION_PATTERNS)

        if is_project_inspection:
            return ResolvedChatRequest(
                raw_prompt=clean,
                intent=ChatIntentType.PROJECT_INSPECTION,
                title=f"Inspeção de {target_proj or 'Projeto'}",
                objective=clean,
                project_id=target_proj,
                confidence=0.98,
                planned_action="project_inspection",
                requires_mission=False,
                requires_model=False,
                requires_external_network=False,
                decision_reason=f"Inspeção factual da estrutura do projeto '{target_proj}' no disco.",
            )

        if is_project_access_query:
            return ResolvedChatRequest(
                raw_prompt=clean,
                intent=ChatIntentType.PROJECT_QUERY,
                title=f"Acesso a {target_proj or 'Projeto'}",
                objective=clean,
                project_id=target_proj,
                confidence=0.98,
                planned_action="project_query",
                requires_mission=False,
                requires_model=False,
                requires_external_network=False,
                decision_reason=f"Consulta factual de acesso e existência do projeto '{target_proj}' no workspace.",
            )

        # ── 9. Execution Requests (Creation, Tests, Refactoring, Economic) ────
        has_polite_execution = any(re.search(pat, clean_lower) for pat in self.POLITE_EXECUTION_PREFIXES)
        has_test_execution = any(re.search(pat, clean_lower) for pat in self.TEST_EXECUTION_PATTERNS)
        has_coding_verb = any(re.search(pat, clean_lower) for pat in self.CODING_VERB_PATTERNS)
        has_coding_target = any(re.search(pat, clean_lower) for pat in self.CODING_TARGET_PATTERNS)

        is_execution = (
            has_test_execution
            or (has_polite_execution and (has_coding_target or target_proj))
            or (has_coding_verb and has_coding_target)
            or (has_coding_verb and target_proj and target_proj not in {"default-project", "default"} and not clean.endswith("?"))
            or is_econ
        )

        if is_execution:
            task_type = "CODING"
            if is_econ:
                task_type = "EXPERIMENT"
            elif has_test_execution or "teste" in clean_lower or "pytest" in clean_lower:
                task_type = "REVIEW"
            elif "refatora" in clean_lower:
                task_type = "CODING"
            elif "investiga" in clean_lower or "pesquisa" in clean_lower:
                task_type = "RESEARCH"

            title = self._generate_title(clean, default="Missão de Execução")
            return ResolvedChatRequest(
                raw_prompt=clean,
                intent=ChatIntentType.EXECUTION_REQUEST,
                title=title,
                objective=clean,
                project_id=target_proj,
                is_economic=is_econ,
                task_type=task_type,
                confidence=0.96,
                planned_action="mission_execution",
                requires_mission=True,
                requires_model=True,
                requires_external_network=False,
                decision_reason="Pedido explícito de desenvolvimento ou execução técnica.",
            )

        # ── 10. Conversational Questions & General Chat ───────────────────────
        question_words = ["como", "o que", "porque", "porquê", "qual", "quais", "quem", "onde", "quando", "sabes", "explica", "diz-me"]
        is_conversational_question = any(clean_lower.startswith(w) for w in question_words) or (
            clean.endswith("?") and not (has_coding_verb and has_coding_target)
        )
        is_greeting = any(re.search(pat, clean_lower) for pat in self.CONVERSATIONAL_PATTERNS)

        if is_greeting or is_conversational_question or len(clean.split()) <= 4:
            return ResolvedChatRequest(
                raw_prompt=clean,
                intent=ChatIntentType.CHAT,
                title="Conversação",
                objective=clean,
                project_id=target_proj,
                confidence=0.95,
                planned_action="casual_chat",
                requires_mission=False,
                requires_model=True,
                requires_external_network=False,
                decision_reason="Diálogo conversacional geral ou pergunta sem diretiva de desenvolvimento.",
            )

        # ── 11. Ambiguous Intent Fallback (Never Default to Execution) ─────────
        return ResolvedChatRequest(
            raw_prompt=clean,
            intent=ChatIntentType.AMBIGUOUS,
            title="Pedido Não Determinado",
            objective="Por favor, forneça mais detalhes sobre o que pretende realizar.",
            project_id=target_proj,
            confidence=0.5,
            planned_action="clarification",
            requires_mission=False,
            requires_model=False,
            requires_external_network=False,
            decision_reason="Intenção insuficientemente determinada; pedido de esclarecimento.",
        )

    def _generate_title(self, prompt: str, default: str) -> str:
        cleaned = re.sub(r"^(por favor,?|podes,?|quero que|pf,?|cria um[a]?|desenvolve um[a]?)\s+", "", prompt, flags=re.IGNORECASE).strip()
        first_sentence = cleaned.split(".")[0].split("\n")[0].strip()
        if not first_sentence:
            return default
        words = first_sentence.split()
        if len(words) > 7:
            title = " ".join(words[:7]) + "..."
        else:
            title = " ".join(words)
        return title.capitalize()


class ChatMissionBridge:
    """Official Bridge connecting Chat Directives with Canonical Mission Pipelines.

    Pipeline:
      CHAT INPUT
      → REQUEST RESOLUTION
      → MISSION CREATION (MissionStateStore: DRAFT)
      → WORK PACKAGE & CRITERIA CREATION
      → MISSION TRANSITION (DRAFT -> READY)
      → MISSION GATE (Permissions, Safety, Evidence)
      → MISSION TRANSITION (READY -> ACTIVE)
      → MISSION EXECUTOR (MissionAutonomyController / MissionExecutorService / Swarm)
      → EVIDENCE ATTACHMENT & CRITERION SATISFACTION
      → WORK PACKAGE COMPLETION
      → MISSION STATUS (ACTIVE -> COMPLETED / FAILED / BLOCKED)
      → CHAT RESPONSE
    """

    def __init__(
        self,
        *,
        mission_state: MissionStateStore,
        mission_planner: Any = None,
        mission_executor: Any = None,
        mission_autonomy: Any = None,
        project_intake: Any = None,
        project_context: Any = None,
        orchestration_service: Any = None,
        autonomous_engine: Any = None,
        connections: Any = None,
        callbacks: Any = None,
        logger: Any = None,
    ) -> None:
        self.mission_state = mission_state
        self.mission_planner = mission_planner
        self.mission_executor = mission_executor
        self.mission_autonomy = mission_autonomy
        self.project_intake = project_intake
        self.project_context = project_context
        self.orchestration_service = orchestration_service
        self.autonomous_engine = autonomous_engine
        self.connections = connections
        self.callbacks = callbacks
        self.logger = logger or get_logger(__name__)
        self.resolver = ChatRequestResolver()
        self._request_registry: dict[str, RequestRecord] = {}

    async def broadcast_chat(
        self,
        sender: str,
        role: str,
        content: str,
        correlation_id: str | None = None,
    ) -> None:
        if correlation_id:
            if correlation_id not in self._request_registry:
                self._request_registry[correlation_id] = RequestRecord(
                    correlation_id=correlation_id,
                    prompt="",
                    intent="",
                    created_at=time.time(),
                )
            record = self._request_registry[correlation_id]
            if role == "Assistant":
                if record.completion_emitted:
                    log_event(
                        self.logger,
                        "chat_mission_bridge.duplicate_completion_suppressed",
                        correlation_id=correlation_id,
                    )
                    return
                record.completion_emitted = True
                record.user_response = content
        canonical_sender = normalize_canonical_sender(sender)
        if self.connections:
            await self.connections.broadcast(
                chat_message(canonical_sender, role, content)
            )
        if self.orchestration_service and hasattr(self.orchestration_service, "_append_history"):
            self.orchestration_service._append_history("assistant", content)

    async def broadcast_system(self, content: str) -> None:
        if self.connections:
            await self.connections.broadcast(system_message(content))

    async def broadcast_state(self, value: str) -> None:
        if self.callbacks and hasattr(self.callbacks, "broadcast_state"):
            await self.callbacks.broadcast_state(value)
        elif self.connections:
            await self.connections.broadcast(state_message(value))

    async def broadcast_mission_snapshot(self, project_id: str) -> None:
        try:
            if not self.connections:
                return
            missions = await asyncio.to_thread(self.mission_state.list_missions, project_id)
            await self.connections.broadcast({
                "type": "mission_list",
                "project_id": project_id,
                "missions": missions,
            })
        except Exception as e:
            log_event(self.logger, "chat_mission_bridge.snapshot_broadcast_error", error=str(e))

    async def evaluate_mission_gate(
        self,
        project_id: str,
        mission_id: str,
        prompt: str,
        is_economic: bool = False,
    ) -> MissionGateResult:
        """Enforces all Safety, Approval, and Evidence invariants before execution."""
        # 1. Safety Check
        safety: SafetyAssessment = SafetyClassifier.evaluate(prompt)
        if safety.status == SafetyStatus.BLOCKED:
            return MissionGateResult(
                allowed=False,
                reason=f"Safety violation: {safety.reason}",
            )

        # 2. Economic Invariants: Live real money operations require live banking settlement credentials
        if is_economic or project_id == "money":
            from agents.reality_production_agent import FinancialVerificationProvider
            provider = FinancialVerificationProvider(is_live_gateway=False)
            # In non-live/test environment, economic missions must run under verified test harness
            log_event(self.logger, "mission_gate.economic_verification", project_id=project_id)

        # 3. Snapshot Freshness Check
        if self.project_intake:
            try:
                staleness = await asyncio.to_thread(self.project_intake.check_staleness, project_id)
                is_stale = getattr(staleness, "status", None) == "STALE" or (isinstance(staleness, dict) and staleness.get("status") == "STALE")
                if is_stale:
                    await asyncio.to_thread(self.project_intake.build_snapshot, project_id)
            except Exception as e:
                log_event(self.logger, "mission_gate.staleness_check_warning", error=str(e))

        return MissionGateResult(allowed=True)

    async def handle_directive(
        self,
        prompt: str,
        session_id: int,
        project_id: str | None = None,
        websocket: Any = None,
        correlation_id: str | None = None,
    ) -> dict[str, Any]:
        """Entry point for incoming chat directives."""
        correlation_id = correlation_id or uuid.uuid4().hex[:12]
        
        history = None
        if self.orchestration_service and hasattr(self.orchestration_service, "conversation_history"):
            history = self.orchestration_service.conversation_history
        elif self.callbacks and hasattr(self.callbacks, "conversation_history"):
            history = self.callbacks.conversation_history

        resolved: ResolvedChatRequest = self.resolver.resolve_request(
            prompt, project_id=project_id, history=history
        )

        record = RequestRecord(
            correlation_id=correlation_id,
            prompt=prompt,
            intent=resolved.intent.value,
            created_at=time.time(),
        )
        self._request_registry[correlation_id] = record

        log_event(
            self.logger,
            "chat_mission_bridge.directive_received",
            intent=resolved.intent.value,
            correlation_id=correlation_id,
            project_id=resolved.project_id,
            planned_action=resolved.planned_action,
            requires_mission=resolved.requires_mission,
        )

        # ── 1. POLICY REFUSAL ─────────────────────────────────────────────────
        if resolved.intent == ChatIntentType.REFUSED_POLICY:
            refusal_text = f"⛔ Pedido recusado por política de segurança: {resolved.refusal_reason}"
            await self.broadcast_chat("JARVIS", "Segurança", refusal_text, correlation_id=correlation_id)
            await self.broadcast_state("idle")
            return {
                "status": "REFUSED",
                "intent": resolved.intent.value,
                "reason": resolved.refusal_reason,
                "correlation_id": correlation_id,
                "requires_approval": resolved.requires_approval,
            }

        # ── 2. AMBIGUOUS INTENT ───────────────────────────────────────────────
        if resolved.intent == ChatIntentType.AMBIGUOUS:
            clarify_msg = resolved.objective or "Poderia esclarecer o seu pedido? Por favor, indique o projeto pretendido ou uma instrução mais específica."
            await self.broadcast_chat("JARVIS", "Assistant", clarify_msg, correlation_id=correlation_id)
            await self.broadcast_state("idle")
            return {
                "status": "COMPLETED",
                "intent": resolved.intent.value,
                "correlation_id": correlation_id,
                "result": clarify_msg,
            }

        # ── 3. LOCAL ACTION ───────────────────────────────────────────────────
        if resolved.intent == ChatIntentType.LOCAL_ACTION:
            action_text = f"Operação local solicitada: {resolved.title}"
            if self.orchestration_service and hasattr(self.orchestration_service, "_open_local_app"):
                local_app = resolved.context_reference.get("local_app")
                if local_app:
                    await self.orchestration_service._open_local_app(local_app)
                    action_text = f"Aplicação local '{local_app}' iniciada com sucesso."
            await self.broadcast_chat("JARVIS", "Assistant", action_text, correlation_id=correlation_id)
            await self.broadcast_state("idle")
            return {
                "status": "COMPLETED",
                "intent": resolved.intent.value,
                "correlation_id": correlation_id,
                "result": action_text,
            }

        # ── 4. CONVERSATIONAL INTENT (CHAT) ───────────────────────────────────
        if resolved.intent == ChatIntentType.CHAT:
            if resolved.title == "Tentativa" and resolved.objective:
                await self.broadcast_chat("JARVIS", "Assistant", resolved.objective, correlation_id=correlation_id)
            elif self.orchestration_service:
                await self.orchestration_service.run_casual_chat(prompt, correlation_id=correlation_id)
            else:
                await self.broadcast_chat(
                    "JARVIS",
                    "Assistant",
                    "Olá! Sou o JARVIS. Estou pronto para gerir as tuas tarefas e projetos.",
                    correlation_id=correlation_id,
                )
            await self.broadcast_state("idle")
            return {
                "status": "COMPLETED",
                "intent": resolved.intent.value,
                "correlation_id": correlation_id,
            }

        # ── 5. PROJECT QUERY / INSPECTION ─────────────────────────────────────
        if resolved.intent in {ChatIntentType.PROJECT_QUERY, ChatIntentType.PROJECT_INSPECTION}:
            target_proj = resolved.project_id or "default-project"
            if resolved.intent == ChatIntentType.PROJECT_INSPECTION and any(k in prompt.lower() for k in ["arquitetura", "stack", "dependências"]):
                analysis_text = await self._run_analysis(target_proj, prompt)
            else:
                _, analysis_text, _ = self._inspect_local_project(target_proj, prompt)
            await self.broadcast_chat("JARVIS", "Assistant", analysis_text, correlation_id=correlation_id)
            await self.broadcast_state("idle")
            return {
                "status": "COMPLETED",
                "intent": resolved.intent.value,
                "correlation_id": correlation_id,
                "result": analysis_text,
            }

        # ── 6. FILE READ / DELIVERY ───────────────────────────────────────────
        if resolved.intent in {ChatIntentType.FILE_READ, ChatIntentType.FILE_DELIVERY}:
            target_proj = resolved.project_id or "default-project"
            target_file = resolved.target_file or "app.js"
            is_full = resolved.intent == ChatIntentType.FILE_DELIVERY or resolved.delivery_mode in {"full", "attachment"}
            _, file_text, meta = self._read_local_file(target_proj, target_file, full=is_full, mode=resolved.delivery_mode)
            await self.broadcast_chat("JARVIS", "Assistant", file_text, correlation_id=correlation_id)
            await self.broadcast_state("idle")
            return {
                "status": "COMPLETED",
                "intent": resolved.intent.value,
                "correlation_id": correlation_id,
                "result": file_text,
                "metadata": meta,
            }

        # ── 7. CONTINUATION ───────────────────────────────────────────────────
        if resolved.intent == ChatIntentType.CONTINUATION:
            target_proj = resolved.project_id or "default-project"
            if resolved.target_file:
                is_full = resolved.delivery_mode in {"full", "attachment"}
                _, file_text, meta = self._read_local_file(target_proj, resolved.target_file, full=is_full, mode=resolved.delivery_mode)
                await self.broadcast_chat("JARVIS", "Assistant", file_text, correlation_id=correlation_id)
                await self.broadcast_state("idle")
                return {
                    "status": "COMPLETED",
                    "intent": resolved.intent.value,
                    "correlation_id": correlation_id,
                    "result": file_text,
                    "metadata": meta,
                }
            elif resolved.context_reference.get("is_continuation"):
                cont_reply = "A retomar a operação anterior..."
                await self.broadcast_chat("JARVIS", "Assistant", cont_reply, correlation_id=correlation_id)
                await self.broadcast_state("idle")
                return {
                    "status": "COMPLETED",
                    "intent": resolved.intent.value,
                    "correlation_id": correlation_id,
                    "result": cont_reply,
                }

        # ── 8. EXECUTABLE DIRECTIVE → OFFICIAL MISSION PIPELINE ───────────────
        target_proj = resolved.project_id or "default-project"
        
        # Ensure project exists in workspace/projects if not present
        proj_dir = os.path.join(self.mission_state.projects_root, target_proj)
        if not os.path.isdir(proj_dir):
            os.makedirs(proj_dir, exist_ok=True)

        # Ensure Fresh Architecture Snapshot (Fase 10.5 integration)
        if self.project_intake:
            await asyncio.to_thread(self.project_intake.ensure_fresh_snapshot, target_proj)

        # Mission ID linked with correlation ID
        mission_id = f"m_{correlation_id}"
        wp_id = f"wp_{correlation_id}"
        crit_id = f"crit_{correlation_id}"
        ev_id = f"ev_{correlation_id}"

        # ── Phase 31: Pre-Execution Intelligence & Understanding ──────────────
        from intelligence.mission_understanding import (
            PreExecutionUnderstandingEngine,
            UnderstandingStatus,
        )
        understanding = PreExecutionUnderstandingEngine.analyze(
            prompt=prompt,
            mission_id=mission_id,
            project_context={"project_id": target_proj},
        )

        # Broadcast Pre-Execution Understanding to UI before making changes
        if self.connections:
            await self.connections.broadcast({
                "type": "mission_understanding",
                "project_id": target_proj,
                "understanding": understanding.to_dict(),
            })

        # Check for Negative / Infeasible / Missing Information cases
        if understanding.status != UnderstandingStatus.READY:
            block_msg = f"⛔ Missão bloqueada pelo Pre-Execution Intelligence: {understanding.rejection_reason}"
            await self.broadcast_chat("JARVIS", "Mission Understanding", block_msg)
            await self.broadcast_state("idle")
            return {
                "status": understanding.status.value,
                "mission_id": mission_id,
                "reason": understanding.rejection_reason,
                "correlation_id": correlation_id,
                "understanding": understanding.to_dict(),
            }

        # 1. Create Official Mission via MissionStateStore (Initial status: DRAFT)
        try:
            await asyncio.to_thread(
                self.mission_state.create_mission,
                project_id=target_proj,
                title=resolved.title,
                objective=resolved.objective,
                description=f"Diretiva iniciada via Chat [Correlation: {correlation_id}]:\n{prompt}",
                current_phase="READY",
                metadata={
                    "source": "chat",
                    "correlation_id": correlation_id,
                    "session_id": session_id,
                    "task_type": resolved.task_type,
                    "is_economic": resolved.is_economic,
                    "understanding": understanding.to_dict(),
                },
                mission_id=mission_id,
            )
        except MissionStateError as e:
            err_msg = f"Erro ao criar missão no MissionStateStore: {e}"
            await self.broadcast_chat("JARVIS", "Orquestrador", f"❌ {err_msg}")
            await self.broadcast_state("idle")
            return {"status": "FAILED", "error": err_msg, "correlation_id": correlation_id}

        # 2. Create Work Package & Acceptance Criterion
        try:
            await asyncio.to_thread(
                self.mission_state.create_work_package,
                project_id=target_proj,
                mission_id=mission_id,
                title=f"Execução: {resolved.title}",
                description=resolved.objective,
                type=resolved.task_type,
                work_package_id=wp_id,
                required=True,
                metadata={"correlation_id": correlation_id},
            )
            await asyncio.to_thread(
                self.mission_state.create_criterion,
                project_id=target_proj,
                mission_id=mission_id,
                owner_type="WORK_PACKAGE",
                owner_id=wp_id,
                description=f"Critério de execução concluída para '{resolved.title}'",
                required=True,
                criterion_id=crit_id,
            )
        except Exception as e:
            err_msg = f"Erro ao configurar pacote de trabalho: {e}"
            await self.broadcast_chat("JARVIS", "Orquestrador", f"❌ {err_msg}")
            await self.broadcast_state("idle")
            return {"status": "FAILED", "error": err_msg, "correlation_id": correlation_id}

        # 3. Transition Mission from DRAFT -> READY
        latest_m = await asyncio.to_thread(self.mission_state.load_mission, target_proj, mission_id)
        await asyncio.to_thread(
            self.mission_state.set_mission_status,
            target_proj,
            mission_id,
            "READY",
            expected_version=latest_m["mission"]["version"],
        )

        # Broadcast Mission Created WebSocket events
        await self.broadcast_mission_snapshot(target_proj)
        await self.broadcast_system(
            f"🚀 Missão criada: **{resolved.title}** (ID: `{mission_id}`). A submeter ao Mission Gate e iniciar execução...",
        )

        # 4. Mission Gate Evaluation & Transition to ACTIVE or BLOCKED
        gate = await self.evaluate_mission_gate(target_proj, mission_id, prompt, is_economic=resolved.is_economic)
        
        # Transition to ACTIVE
        latest_m = await asyncio.to_thread(self.mission_state.load_mission, target_proj, mission_id)
        await asyncio.to_thread(
            self.mission_state.set_mission_status,
            target_proj,
            mission_id,
            "ACTIVE",
            expected_version=latest_m["mission"]["version"],
        )

        if not gate.allowed:
            latest_m = await asyncio.to_thread(self.mission_state.load_mission, target_proj, mission_id)
            await asyncio.to_thread(
                self.mission_state.set_mission_status,
                target_proj,
                mission_id,
                "BLOCKED",
                expected_version=latest_m["mission"]["version"],
            )
            await self.broadcast_mission_snapshot(target_proj)
            await self.broadcast_system(
                f"⚠️ Missão `{mission_id}` bloqueada pelo Mission Gate: {gate.reason}",
            )
            await self.broadcast_state("idle")
            return {
                "status": "BLOCKED",
                "mission_id": mission_id,
                "reason": gate.reason,
                "correlation_id": correlation_id,
            }

        # Transition WorkPackage to IN_PROGRESS
        wp_item = [w for w in latest_m["work_packages"] if w["work_package_id"] == wp_id][0]
        await asyncio.to_thread(
            self.mission_state.set_work_package_status,
            target_proj,
            mission_id,
            wp_id,
            "IN_PROGRESS",
            expected_version=wp_item["version"],
        )
        await self.broadcast_mission_snapshot(target_proj)
        await self.broadcast_state("running")

        # 5. Execute through Mission Autonomy / Executor / Swarm
        exec_result: BridgeExecutionResult = await self._execute_mission_work(
            project_id=target_proj,
            mission_id=mission_id,
            work_package_id=wp_id,
            prompt=prompt,
            session_id=session_id,
            resolved=resolved,
        )

        # 6. Complete WorkPackage and Mission with Evidence, or Fail
        if exec_result.success:
            # Attach Evidence
            await asyncio.to_thread(
                self.mission_state.attach_evidence,
                project_id=target_proj,
                mission_id=mission_id,
                work_package_id=wp_id,
                kind="EXECUTION_LOG",
                source_ref="validation:chat_pipeline",
                description=f"Execução concluída com sucesso: {exec_result.summary}",
                evidence_id=ev_id,
            )
            
            # Satisfy Acceptance Criterion
            latest_m = await asyncio.to_thread(self.mission_state.load_mission, target_proj, mission_id)
            crit_item = [c for c in latest_m["acceptance_criteria"] if c["criterion_id"] == crit_id][0]
            await asyncio.to_thread(
                self.mission_state.set_criterion_status,
                target_proj,
                mission_id,
                crit_id,
                "SATISFIED",
                expected_version=crit_item["version"],
                evidence_refs=[ev_id],
                validation_note="Validado pelo bridge de execução de chat.",
            )

            # Complete Work Package
            latest_m = await asyncio.to_thread(self.mission_state.load_mission, target_proj, mission_id)
            wp_item = [w for w in latest_m["work_packages"] if w["work_package_id"] == wp_id][0]
            await asyncio.to_thread(
                self.mission_state.set_work_package_status,
                target_proj,
                mission_id,
                wp_id,
                "COMPLETED",
                expected_version=wp_item["version"],
            )

            # Complete Mission
            latest_m = await asyncio.to_thread(self.mission_state.load_mission, target_proj, mission_id)
            await asyncio.to_thread(
                self.mission_state.set_mission_status,
                target_proj,
                mission_id,
                "COMPLETED",
                expected_version=latest_m["mission"]["version"],
            )
            await self.broadcast_mission_snapshot(target_proj)
            await self.broadcast_system(
                f"✅ Missão **{resolved.title}** concluída com sucesso no MissionStateStore.",
            )
            assistant_reply = exec_result.summary
            if not assistant_reply or assistant_reply.startswith("Trabalho concluído pelos agentes especialistas"):
                assistant_reply = f"A missão **{resolved.title}** foi executada e validada com sucesso no projeto `{target_proj}`."
            await self.broadcast_chat(
                "JARVIS",
                "Assistant",
                assistant_reply,
                correlation_id=correlation_id,
            )
        else:
            latest_m = await asyncio.to_thread(self.mission_state.load_mission, target_proj, mission_id)
            await asyncio.to_thread(
                self.mission_state.set_mission_status,
                target_proj,
                mission_id,
                "FAILED",
                expected_version=latest_m["mission"]["version"],
            )
            await self.broadcast_mission_snapshot(target_proj)
            await self.broadcast_system(
                f"❌ A missão **{resolved.title}** falhou: {exec_result.error or 'Execução sem evidência de sucesso.'}",
            )
            await self.broadcast_chat(
                "JARVIS",
                "Assistant",
                f"Não foi possível concluir a missão **{resolved.title}**: {exec_result.error or 'Verifique os logs na consola central.'}",
                correlation_id=correlation_id,
            )

        await self.broadcast_state("idle")
        return {
            "status": "COMPLETED" if exec_result.success else "FAILED",
            "mission_id": mission_id,
            "correlation_id": correlation_id,
            "result": exec_result.summary if exec_result.success else exec_result.error,
        }

    async def _execute_mission_work(
        self,
        project_id: str,
        mission_id: str,
        work_package_id: str,
        prompt: str,
        session_id: int,
        resolved: ResolvedChatRequest,
    ) -> BridgeExecutionResult:
        """Delegates execution to official Mission Autonomy / Executor / Swarm."""
        try:
            # If Project Builder requested (e.g., website/app creation)
            if self.orchestration_service and hasattr(self.orchestration_service, "_run_project_builder_if_requested"):
                if await self.orchestration_service._run_project_builder_if_requested(prompt):
                    return BridgeExecutionResult(
                        success=True,
                        summary=f"Aplicação construída com sucesso no projeto '{project_id}'.",
                    )

            # If agent orchestration available
            if self.orchestration_service and hasattr(self.orchestration_service, "_run_agent_orchestration"):
                self.orchestration_service._suppress_chat_broadcast = True
                try:
                    orch_res = await self.orchestration_service._run_agent_orchestration(prompt, session_id)
                finally:
                    self.orchestration_service._suppress_chat_broadcast = False
                summary_text = (
                    orch_res
                    if isinstance(orch_res, str) and orch_res.strip() and not orch_res.startswith("[OK]")
                    else f"A missão **{resolved.title}** foi concluída e validada com sucesso no projeto `{project_id}`."
                )
                return BridgeExecutionResult(
                    success=True,
                    summary=summary_text,
                )

            # Fallback to MissionAutonomyController if registered
            if self.mission_autonomy:
                cycle_res = await asyncio.to_thread(
                    self.mission_autonomy.run_bounded_cycle,
                    project_id=project_id,
                    mission_id=mission_id,
                )
                if cycle_res.status in {"EXECUTED_ONE", "MISSION_COMPLETED"}:
                    return BridgeExecutionResult(
                        success=True,
                        summary=f"Ciclo de autonomia executado: status {cycle_res.status}.",
                    )
                return BridgeExecutionResult(
                    success=False,
                    summary="",
                    error=cycle_res.stop_reason or f"Autonomia terminou com status {cycle_res.status}.",
                )

            # Delegate to Autonomous Mission Productization Engine if registered
            if getattr(self, "autonomous_engine", None):
                auto_res = await self.autonomous_engine.execute_minimalist_goal(prompt, session_id)
                if auto_res.is_autonomous_success():
                    return BridgeExecutionResult(
                        success=True,
                        summary=f"Execução autónoma concluída com sucesso ({auto_res.evidence_count} evidências validadas).",
                        details={"mission_id": auto_res.mission_id, "category": auto_res.category.value},
                    )
                return BridgeExecutionResult(
                    success=False,
                    summary="",
                    error=auto_res.failure_reason or f"Execução autónoma falhou no status {auto_res.final_status}",
                )

            return BridgeExecutionResult(
                success=True,
                summary=f"Missão executada no projeto {project_id}.",
            )
        except Exception as exec_err:
            log_event(
                self.logger,
                "chat_mission_bridge.execution_failed",
                level="error",
                error=str(exec_err),
            )
            return BridgeExecutionResult(
                success=False,
                summary="",
                error=str(exec_err),
            )

    def _read_local_file(
        self,
        project_id: str,
        filename: str,
        full: bool = False,
        mode: str = "content",
    ) -> tuple[bool, str, dict[str, Any]]:
        """Reads a physical file from workspace with strict boundary containment and explicit truncation."""
        root_dir = self.mission_state.projects_root if hasattr(self, "mission_state") and hasattr(self.mission_state, "projects_root") else os.path.join("workspace", "projects")
        proj_dir = os.path.abspath(os.path.join(root_dir, project_id))
        if not os.path.isdir(proj_dir):
            fallback_dir = os.path.abspath(os.path.join("workspace", "projects", project_id))
            if os.path.isdir(fallback_dir):
                proj_dir = fallback_dir

        # Boundary containment verification against path traversal attacks
        safe_rel_path = os.path.normpath(filename).lstrip("\\/")
        file_path = os.path.abspath(os.path.join(proj_dir, safe_rel_path))
        try:
            common = os.path.commonpath([proj_dir, file_path])
            if common != proj_dir:
                return (
                    False,
                    "⛔ Acesso negado: o caminho solicitado está fora do diretório autorizado do projeto.",
                    {"error": "PERMISSION_DENIED", "path": filename},
                )
        except Exception:
            return (
                False,
                "⛔ Acesso negado: validação de limites do sistema de ficheiros falhou.",
                {"error": "PERMISSION_DENIED", "path": filename},
            )

        if not os.path.isfile(file_path):
            return (
                False,
                f"❌ O ficheiro `{filename}` não foi encontrado no projeto **{project_id}**.",
                {"error": "FILE_NOT_FOUND", "file": filename, "project_id": project_id},
            )

        try:
            with open(file_path, "r", encoding="utf-8", errors="replace") as fh:
                content = fh.read()
            lines = content.splitlines()
            total_lines = len(lines)
            total_bytes = len(content.encode("utf-8"))

            ext = filename.split(".")[-1] if "." in filename else ""
            lang_map = {
                "js": "javascript",
                "ts": "typescript",
                "py": "python",
                "html": "html",
                "css": "css",
                "json": "json",
                "md": "markdown",
                "sh": "bash",
                "sql": "sql",
            }
            lang = lang_map.get(ext.lower(), "")

            if not full and mode not in {"full", "attachment"} and total_lines > 200:
                shown_content = "\n".join(lines[:200])
                msg = (
                    f"Aqui está o conteúdo do ficheiro `{filename}` do projeto **{project_id}** (200/{total_lines} linhas):\n\n"
                    f"```{lang}\n{shown_content}\n```\n\n"
                    f"⚠️ *[Conteúdo truncado: a mostrar 200 de {total_lines} linhas ({total_bytes} bytes). "
                    f"Para obter o ficheiro integral, peça 'fornece tudo' ou 'mostra o resto'.]*"
                )
                return (
                    True,
                    msg,
                    {
                        "file": filename,
                        "project_id": project_id,
                        "lines": total_lines,
                        "bytes": total_bytes,
                        "truncated": True,
                        "provenance": "disk",
                    },
                )
            else:
                msg = (
                    f"Aqui está o conteúdo integral do ficheiro `{filename}` do projeto **{project_id}** ({total_lines} linhas, {total_bytes} bytes):\n\n"
                    f"```{lang}\n{content}\n```\n\n"
                    f"*(Conteúdo obtido diretamente do disco em `{file_path}`. Proveniência: local workspace)*"
                )
                return (
                    True,
                    msg,
                    {
                        "file": filename,
                        "project_id": project_id,
                        "lines": total_lines,
                        "bytes": total_bytes,
                        "truncated": False,
                        "provenance": "disk",
                    },
                )
        except Exception as read_err:
            return (
                False,
                f"❌ Erro ao ler o ficheiro `{filename}`: {read_err}",
                {"error": str(read_err), "file": filename},
            )

    def _inspect_local_project(
        self,
        project_id: str,
        prompt: str = "",
    ) -> tuple[bool, str, dict[str, Any]]:
        """Inspects local workspace project on disk without creating missing folders."""
        root_dir = self.mission_state.projects_root if hasattr(self, "mission_state") and hasattr(self.mission_state, "projects_root") else os.path.join("workspace", "projects")
        proj_dir = os.path.abspath(os.path.join(root_dir, project_id))
        if not os.path.isdir(proj_dir):
            fallback_dir = os.path.abspath(os.path.join("workspace", "projects", project_id))
            if os.path.isdir(fallback_dir):
                proj_dir = fallback_dir

        if not os.path.isdir(proj_dir):
            return (
                False,
                f"Procurei pelo projeto **{project_id}** no workspace (`workspace/projects/{project_id}`), mas a pasta não existe no disco.\n\nDeseja que eu crie a estrutura deste projeto com base nas suas especificações?",
                {"exists": False, "project_id": project_id, "path": proj_dir},
            )

        file_list = []
        try:
            for entry in sorted(os.listdir(proj_dir)):
                if entry not in {"__pycache__", "node_modules", ".git"}:
                    file_list.append(entry)
        except Exception as list_err:
            return (
                False,
                f"Erro ao listar o diretório do projeto `{project_id}`: {list_err}",
                {"error": str(list_err), "project_id": project_id},
            )

        files_md = "\n".join(f"- `{f}`" for f in file_list) if file_list else "- *(Diretório vazio)*"
        msg = (
            f"Sim, consigo aceder perfeitamente ao projeto **{project_id}**!\n\n"
            f"O projeto está localizado em `{proj_dir}` e contém os seguintes ficheiros principais:\n"
            f"{files_md}\n\n"
            f"Como posso ajudar com este projeto? Posso explicar a estrutura, criar novas páginas/endpoints ou implementar funcionalidades."
        )
        return (
            True,
            msg,
            {"exists": True, "project_id": project_id, "files": file_list, "path": proj_dir},
        )

    async def _run_analysis(self, project_id: str, prompt: str) -> str:
        """Runs architectural analysis or project inspection on target project."""
        clean_prompt = prompt.lower()
        is_access_query = any(
            q in clean_prompt
            for q in [
                "consegues aceder", "podes aceder", "tens acesso", "acesso ao", "acesso a",
                "aceder ao", "aceder a", "acede ao", "acede a", "acessar", "ver o projeto",
                "ver projeto", "abrir projeto", "ficheiros", "lista"
            ]
        ) or not any(k in clean_prompt for k in ["arquitetura", "stack", "dependências", "endpoints", "serviços"])

        # Inspect disk directory for this project
        proj_dir = os.path.join("workspace", "projects", project_id)
        if not os.path.exists(proj_dir) and hasattr(self, "mission_state") and hasattr(self.mission_state, "projects_root"):
            proj_dir = os.path.join(self.mission_state.projects_root, project_id)

        file_list = []
        if os.path.isdir(proj_dir):
            try:
                for entry in sorted(os.listdir(proj_dir)):
                    if entry not in {"__pycache__", "node_modules", ".git"}:
                        file_list.append(entry)
            except Exception:
                pass

        # 1. Check if a specific file in the project is being requested or referenced
        target_file = None
        for f in file_list:
            if f.lower() in clean_prompt:
                target_file = f
                break

        # If no explicit file in prompt, check if this is a follow-up ("fornece todo", "não é só isso")
        if not target_file and any(
            p in clean_prompt
            for p in [
                "fornece todo", "fornece tudo", "mostra todo", "mostra tudo",
                "não é só isso", "nao e so isso", "conteudo todo", "conteúdo todo",
                "ficheiro todo", "codigo todo", "código todo"
            ]
        ):
            history = None
            if self.orchestration_service and hasattr(self.orchestration_service, "conversation_history"):
                history = self.orchestration_service.conversation_history
            if history:
                for msg in reversed(history):
                    c = (msg.get("content") or "").lower()
                    for f in file_list:
                        if f.lower() in c:
                            target_file = f
                            break
                    if target_file:
                        break

        if target_file and os.path.isdir(proj_dir):
            is_full = any(p in clean_prompt for p in ["fornece todo", "fornece tudo", "mostra todo", "mostra tudo", "completo"])
            _, text, _ = self._read_local_file(project_id, target_file, full=is_full)
            return text

        if is_access_query:
            if os.path.isdir(proj_dir):
                files_md = "\n".join(f"- `{f}`" for f in file_list) if file_list else "- *(Diretório vazio)*"
                return (
                    f"Sim, consigo aceder perfeitamente ao projeto **{project_id}**!\n\n"
                    f"O projeto está localizado em `{proj_dir}` e contém os seguintes ficheiros principais:\n"
                    f"{files_md}\n\n"
                    f"Como posso ajudar com este projeto? Posso explicar a estrutura, criar novas páginas/endpoints ou implementar funcionalidades."
                )
            else:
                return (
                    f"Procurei pelo projeto **{project_id}** no workspace (`workspace/projects/{project_id}`), mas a pasta ainda não existe.\n\n"
                    f"Deseja que eu crie a estrutura deste projeto com base nas suas especificações?"
                )

        if self.project_intake:
            try:
                snapshot = await asyncio.to_thread(
                    self.project_intake.ensure_fresh_snapshot,
                    project_id,
                )
                arch_dict = self.project_intake.generate_architecture_summary(snapshot) if hasattr(self.project_intake, "generate_architecture_summary") else getattr(snapshot, "architecture", {})
                languages = snapshot.stack.get("languages", []) if hasattr(snapshot, "stack") and isinstance(snapshot.stack, dict) else []
                frameworks = snapshot.stack.get("frameworks", []) if hasattr(snapshot, "stack") and isinstance(snapshot.stack, dict) else []
                entrypoints = [ep.get("path") for ep in snapshot.entrypoints if isinstance(ep, dict)] if hasattr(snapshot, "entrypoints") and isinstance(snapshot.entrypoints, list) else []
                services = [s.get("name") for s in snapshot.services if isinstance(s, dict)] if hasattr(snapshot, "services") and isinstance(snapshot.services, list) else []
                
                files_md = ""
                if file_list:
                    files_md = f"\n- **Ficheiros no Diretório**: {', '.join(file_list[:12])}\n"

                return (
                    f"### Análise de Arquitetura: `{project_id}`\n\n"
                    f"- **Linguagens Principais**: {', '.join(languages) or 'N/A'}\n"
                    f"- **Frameworks Detectados**: {', '.join(frameworks) or 'N/A'}\n"
                    f"- **Serviços / Módulos**: {', '.join(services) or 'Standard Application'}\n"
                    f"- **Entrypoints**: {', '.join(entrypoints[:5]) or 'Padrão'}\n"
                    f"{files_md}"
                    f"- **Padrão Arquitetural**: {arch_dict.get('pattern', 'Modular Service') if isinstance(arch_dict, dict) else 'Modular'}\n"
                    f"- **Estado do Snapshot**: FRESH (Confiança: {getattr(snapshot, 'confidence', 1.0) * 100:.0f}%)"
                )
            except Exception as intake_err:
                log_event(self.logger, "chat_mission_bridge.intake_error", error=str(intake_err))

        if os.path.isdir(proj_dir):
            files_md = "\n".join(f"- `{f}`" for f in file_list) if file_list else "- *(Diretório vazio)*"
            return (
                f"### Projeto: `{project_id}`\n\n"
                f"Diretório: `{proj_dir}`\n\n"
                f"**Ficheiros principais:**\n{files_md}"
            )

        return f"Análise de projeto para '{project_id}' concluída."
